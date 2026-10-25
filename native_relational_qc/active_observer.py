"""Learn a reading order; certify a native curvature sign from bounded readings.

Classical acquisition controller, in one declared affine (s,v) chart. A reading
is the three independent entries of a symmetric energy Hessian, not one scalar
or a hardware shot. No derivatives, energy coefficients, or labels are passed
to the controller. Existing EMK multiplication evaluates the point estimate.

Contract: U is a polynomial of degree <=5, |partial_i^3 H_jk| <= fifth_bound,
and each recorded Hessian entry has absolute error <= noise. Central differences
have error B*h*h/6 + noise/h. After sampling h/2, Richardson cancellation is
exact for the polynomial part; its noise error is <=3*noise/h. These are
conditional deterministic bounds, not statistical confidence or a test of the
polynomial assumption. General smooth fields require an extra remainder bound.
For a local response forecast, |partial_i partial_j H_kl| <= fourth_bound
throughout the declared square supplies a separate first-order Taylor remainder.
"""
from dataclasses import dataclass
from fractions import Fraction as Q

from .emk_tensor import EMKBlock
from .self_learning import digest


def rational(x):
    if type(x) not in (int, Q):
        raise TypeError("exact int/Fraction required")
    x = Q(x)
    if max(abs(x.numerator).bit_length(), x.denominator.bit_length()) > 4096:
        raise ValueError("rational size limit")
    return x


@dataclass(frozen=True)
class Interval:
    low: Q
    high: Q

    def __post_init__(self):
        object.__setattr__(self, "low", rational(self.low))
        object.__setattr__(self, "high", rational(self.high))
        if self.low > self.high:
            raise ValueError("inverted interval")

    def __add__(self, other):
        other = interval(other)
        return Interval(self.low + other.low, self.high + other.high)

    __radd__ = __add__

    def __neg__(self):
        return Interval(-self.high, -self.low)

    def __sub__(self, other):
        return self + -interval(other)

    def __rsub__(self, other):
        return interval(other) + -self

    def __mul__(self, other):
        other = interval(other)
        ends = [a*b for a in (self.low, self.high) for b in (other.low, other.high)]
        return Interval(min(ends), max(ends))

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = interval(other)
        if other.low <= 0 <= other.high:
            raise ValueError("denominator interval contains zero")
        return self * Interval(1/other.high, 1/other.low)

    @property
    def width(self):
        return self.high - self.low

    def contains(self, x):
        return self.low <= x <= self.high

    def record(self):
        return [str(self.low), str(self.high)]


def interval(x):
    return x if type(x) is Interval else Interval(rational(x), rational(x))


def enclosure(x, error):
    return Interval(x-error, x+error)


def triple(values):
    if not isinstance(values, (list, tuple)) or len(values) != 3:
        raise ValueError("three symmetric Hessian entries required")
    return tuple(rational(v) for v in values)


def _block(h):
    a, b, c = h
    return EMKBlock((a+c)/2, (a-c)/2, 0, b)


def native_curvature(h, ds, dv):
    """Same selected NT curvature as constitutive_response, via native EMK."""
    a, b, c = triple(h)
    ds, dv = triple(ds), triple(dv)
    det = a*c-b*b
    if a <= 0 or det <= 0:
        raise ValueError("positive Hessian required")
    inv = _block((c/det, -b/det, a/det))
    x, y = inv*_block(ds), inv*_block(dv)
    xy, yx = x*y, y*x
    f = EMKBlock(*((r-l)/4 for l, r in zip(xy.coefficients, yx.coefficients)))
    value = (_block((a, b, c))*f).matrix()[0][1]/det
    if value.b or value.c or value.d:
        raise ArithmeticError("curvature left the rational carrier")
    return value.a


def _mm(a, b):
    return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(2)) for j in range(2)) for i in range(2))


def curvature_interval(h, ds, dv):
    """Independent interval matrix arithmetic enclosing the selected component."""
    a, b, c = map(interval, h)
    det = a*c-b*b
    if a.low <= 0 or det.low <= 0:
        raise ValueError("positive Hessian not established by readings")
    inv = ((c/det, -b/det), (-b/det, a/det))
    mats = [((v[0], v[1]), (v[1], v[2])) for v in (ds, dv)]
    x, y = (_mm(inv, m) for m in mats)
    xy, yx = _mm(x, y), _mm(y, x)
    f = tuple(tuple((yx[i][j]-xy[i][j])/4 for j in range(2)) for i in range(2))
    return _mm(((a, b), (b, c)), f)[0][1]/det


@dataclass(frozen=True)
class Contract:
    step: Q = Q(1, 4)
    noise: Q = Q(0)
    fifth_bound: Q = Q(6)
    fourth_bound: Q = Q(5)
    domain_radius: Q = Q(1, 2)
    degree_limit: int = 5

    def __post_init__(self):
        for key in ("step", "noise", "fifth_bound", "fourth_bound", "domain_radius"):
            object.__setattr__(self, key, rational(getattr(self, key)))
        if not 0 < self.step <= 1 or min(self.noise, self.fifth_bound, self.fourth_bound) < 0 or self.domain_radius <= 0:
            raise ValueError("invalid observation contract")
        if type(self.degree_limit) is not int or not 2 <= self.degree_limit <= 5:
            raise ValueError("only declared polynomial degree 2..5 supported")

    def record(self):
        return dict(step=str(self.step), noise=str(self.noise), fifth_bound=str(self.fifth_bound),
                    fourth_bound=str(self.fourth_bound), domain_radius=str(self.domain_radius),
                    degree_limit=self.degree_limit, frame="fixed_affine_s_v",
                    reading_unit="one_symmetric_Hessian_block_three_scalar_entries")


class Acquisition:
    """Bounded cached callback interface. Only read(point) exposes the system."""
    def __init__(self, read, point, contract, *, max_readings=9):
        if type(contract) is not Contract:
            raise TypeError("explicit Contract required")
        if type(max_readings) is not int or not 5 <= max_readings <= 9:
            raise ValueError("reading budget must be 5..9 blocks")
        if not isinstance(point, (tuple, list)) or len(point) != 2:
            raise ValueError("two-coordinate point required")
        self.read = read
        self.point = tuple(rational(x) for x in point)
        if max(abs(x) for x in self.point)+contract.step > contract.domain_radius:
            raise ValueError("initial stencil leaves the declared square")
        self.contract = contract
        self.max_readings = max_readings
        self.cache = {}
        self.log = []
        self.refined = set()

    def _read(self, point):
        if point not in self.cache:
            if len(self.cache) >= self.max_readings:
                raise RuntimeError("reading budget exhausted before callback")
            value = triple(self.read(point))
            self.cache[point] = value
            self.log.append(dict(point=[str(x) for x in point], value=[str(x) for x in value]))
        return self.cache[point]

    def pair(self, axis, step):
        rows = []
        for sign in (-1, 1):
            point = tuple(x + (sign*step if j == axis else 0) for j, x in enumerate(self.point))
            rows.append(self._read(point))
        return tuple((plus-minus)/(2*step) for minus, plus in zip(*rows))

    def initial(self):
        self.h = self._read(self.point)
        self.coarse = [self.pair(i, self.contract.step) for i in (0, 1)]
        self.estimates = list(self.coarse)

    def refine(self, axis):
        if type(axis) is not int or axis not in (0, 1) or axis in self.refined:
            raise ValueError("one unrefined axis required")
        if len(self.cache)+2 > self.max_readings:
            return False
        finer = self.pair(axis, self.contract.step/2)
        self.estimates[axis] = tuple((4*f-c)/3 for f, c in zip(finer, self.coarse[axis]))
        self.refined.add(axis)
        return True

    def errors(self):
        h, eps, b = self.contract.step, self.contract.noise, self.contract.fifth_bound
        return tuple(3*eps/h if i in self.refined else b*h*h/6+eps/h for i in (0, 1))

    def bounds(self):
        hs = tuple(enclosure(v, self.contract.noise) for v in self.h)
        jets = [tuple(enclosure(v, e) for v in row) for row, e in zip(self.estimates, self.errors())]
        return curvature_interval(hs, *jets)

    def features(self):
        """Only currently measured values. No case ID, coefficient, or label."""
        a, b, c = self.h
        ds, dv = self.coarse
        ns, nv = sum(abs(x) for x in ds), sum(abs(x) for x in dv)
        denom = ns+nv+Q(1, 10**9)
        return (ns/denom, abs(ds[0])/denom, abs(dv[2])/denom,
                (abs(ds[1])+abs(ds[2]))/denom, (abs(dv[0])+abs(dv[1]))/denom,
                b/a if a else Q(0), b/c if c else Q(0), (a-c)/(a+c) if a+c else Q(0))

    def sensitivity_axis(self):
        """Untrained greedy baseline: shrink each jet's interval at its midpoint."""
        widths = []
        hs = tuple(enclosure(v, self.contract.noise) for v in self.h)
        for candidate in (0, 1):
            errors = list(self.errors())
            errors[candidate] = 3*self.contract.noise/self.contract.step
            jets = [tuple(enclosure(v, e) for v in row) for row, e in zip(self.estimates, errors)]
            widths.append(curvature_interval(hs, *jets).width)
        return min((0, 1), key=lambda i: (widths[i], i))


FEATURES = ("relative_ds_norm", "relative_ds_00", "relative_dv_11",
            "relative_ds_mixed", "relative_dv_mixed", "H01_over_H00", "H01_over_H11", "H_anisotropy")


def fit_policy(rows, *, depth=2, min_leaf=8):
    """Small exact cost-sensitive decision tree; training rows only.

    Costs are actual acquired blocks under s-first/v-first with the same
    deterministic bounded sensor. Unresolved outcomes incur a fixed penalty.
    No validation/test or truth is accepted by the deployed policy interface.
    """
    if type(depth) is not int or not 0 <= depth <= 3 or type(min_leaf) is not int or min_leaf < 1:
        raise ValueError("invalid tree limits")
    if not isinstance(rows, (tuple, list)) or not 1 <= len(rows) <= 4096:
        raise ValueError("bounded nonempty training rows required")
    normalized = []
    for row in rows:
        x, costs = tuple(map(rational, row["features"])), tuple(map(rational, row["costs"]))
        if len(x) != len(FEATURES) or len(costs) != 2 or min(costs) < 0:
            raise ValueError("invalid training row")
        normalized.append((x, costs))

    def grow(indices, remaining):
        sums = tuple(sum(normalized[i][1][a] for i in indices) for a in (0, 1))
        action = int(sums[1] < sums[0])
        leaf = dict(action=action, examples=len(indices), cost=str(sums[action]))
        best = (sums[action], None)
        if not remaining:
            return leaf
        for feature in range(len(FEATURES)):
            values = sorted({normalized[i][0][feature] for i in indices})
            for lo, hi in zip(values, values[1:]):
                threshold = (lo+hi)/2
                left = [i for i in indices if normalized[i][0][feature] <= threshold]
                right = [i for i in indices if normalized[i][0][feature] > threshold]
                if min(len(left), len(right)) < min_leaf:
                    continue
                score = sum(min(sum(normalized[i][1][a] for i in group) for a in (0, 1)) for group in (left, right))
                if score < best[0]:
                    best = (score, (feature, threshold, left, right))
        if best[1] is None:
            return leaf
        f, t, left, right = best[1]
        return dict(feature=f, threshold=str(t), left=grow(left, remaining-1), right=grow(right, remaining-1))

    model = dict(schema="native-active-observer-policy-v1", feature_names=list(FEATURES),
                 tree=grow(list(range(len(normalized))), depth), depth_limit=depth, min_leaf=min_leaf,
                 training_sha256=digest([dict(features=[str(v) for v in x], costs=[str(v) for v in c]) for x, c in normalized]),
                 execution="CLASSICAL_ACQUISITION_POLICY", training_examples=len(rows))
    return dict(model, fingerprint=digest(model))


def load_policy(model):
    if type(model) is not dict:
        raise ValueError("policy object required")
    record = dict(model)
    fingerprint = record.pop("fingerprint", None)
    if fingerprint != digest(record) or record.get("schema") != "native-active-observer-policy-v1" or record.get("feature_names") != list(FEATURES):
        raise ValueError("policy metadata or fingerprint mismatch")
    if record.get("execution") != "CLASSICAL_ACQUISITION_POLICY":
        raise ValueError("unexpected execution class")

    def check(node, level=0):
        if type(node) is not dict or level > 3:
            raise ValueError("invalid policy tree")
        if "action" in node:
            if type(node["action"]) is not int or node["action"] not in (0, 1):
                raise ValueError("invalid policy action")
        else:
            if type(node.get("feature")) is not int or not 0 <= node["feature"] < len(FEATURES):
                raise ValueError("invalid feature")
            rational(Q(node["threshold"]))
            check(node["left"], level+1)
            check(node["right"], level+1)
    try:
        check(record["tree"])
    except (KeyError, TypeError, ZeroDivisionError) as error:
        raise ValueError("malformed policy") from error
    return record["tree"]


def choose(model, features):
    node = load_policy(model)
    if len(features) != len(FEATURES):
        raise ValueError("feature count mismatch")
    features = tuple(map(rational, features))
    while "action" not in node:
        node = node["left"] if features[node["feature"]] <= Q(node["threshold"]) else node["right"]
    return node["action"]


def observe(read, point, *, contract=Contract(), policy="s_first", model=None, max_readings=9):
    """Return a conditional sign certificate or abstain, using <=9 read calls."""
    if policy not in ("s_first", "v_first", "sensitivity", "learned", "full"):
        raise ValueError("unknown acquisition policy")
    if policy == "learned":
        load_policy(model)
    acq = Acquisition(read, point, contract, max_readings=max_readings)
    acq.initial()
    features = acq.features()
    trace = []
    order = []
    status = "INFORMATION_INSUFFICIENT"
    prediction = None
    bounds = None
    for step in range(3):
        try:
            bounds = acq.bounds()
        except ValueError:
            status = "HESSIAN_POSITIVITY_UNRESOLVED"
            break
        sign = -1 if bounds.high < 0 else 1 if bounds.low > 0 else 0
        trace.append(dict(blocks=len(acq.cache), interval=bounds.record(), sign=sign))
        if sign and (policy != "full" or len(acq.refined) == 2):
            prediction = sign
            status = "CONDITIONAL_SIGN_CERTIFIED"
            break
        if len(acq.refined) == 2:
            break
        if acq.refined:
            axis = 1-next(iter(acq.refined))
        elif policy == "learned":
            axis = choose(model, features)
        elif policy == "sensitivity":
            axis = acq.sensitivity_axis()
        else:
            axis = int(policy == "v_first")
        if not acq.refine(axis):
            status = "READING_BUDGET_EXHAUSTED"
            break
        order.append(axis)
    estimate = None
    try:
        estimate = str(native_curvature(acq.h, *acq.estimates))
    except ValueError:
        pass
    return dict(status=status, prediction=prediction, blocks=len(acq.cache), scalar_readings=3*len(acq.cache),
                features=[str(x) for x in features], derivative_estimates=[[str(x) for x in r] for r in acq.estimates],
                derivative_error_bounds=[str(x) for x in acq.errors()], estimate=estimate,
                curvature_interval=None if bounds is None else bounds.record(), refinement_order=order,
                trace=trace, readings=acq.log, contract=contract.record())


def predict_hessian(observation, displacement, *, contract):
    """First-order local response prediction, without acquiring a new reading.

    Each entry error <= eps + sum_i(error_i*|delta_i|)
                           + fourth_bound*||delta||_1^2/2.
    This bound is conditional on the declared derivative envelope throughout
    the square. It is not a learned law or a full recognition-seam transport.
    """
    if type(contract) is not Contract or observation['contract'] != contract.record():
        raise ValueError("observation and prediction contracts differ")
    if not isinstance(displacement, (tuple, list)) or len(displacement) != 2:
        raise ValueError("two-coordinate displacement required")
    delta = tuple(rational(x) for x in displacement)
    origin = tuple(Q(x) for x in observation['readings'][0]['point'])
    target = tuple(x+d for x, d in zip(origin, delta))
    if max(abs(x) for x in target) > contract.domain_radius:
        raise ValueError("forecast leaves the declared square")
    h = tuple(Q(x) for x in observation['readings'][0]['value'])
    jets = [tuple(Q(x) for x in row) for row in observation['derivative_estimates']]
    errors = tuple(Q(x) for x in observation['derivative_error_bounds'])
    predicted = tuple(h[j]+sum(delta[i]*jets[i][j] for i in (0, 1)) for j in range(3))
    remainder = contract.fourth_bound*sum(abs(x) for x in delta)**2/2
    bound = contract.noise+sum(abs(d)*e for d, e in zip(delta, errors))+remainder
    return dict(point=[str(x) for x in target], estimate=[str(x) for x in predicted],
                component_error_bound=str(bound), taylor_remainder_bound=str(remainder),
                extra_acquisition_blocks=0)
