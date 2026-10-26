"""Measurement-based compilation of the four-qubit parity classifier (v0.29).

The self-learning branch (pinned below) trains a four-qubit, five-angle, three-
CNOT circuit on the PC through the exact calculator. The route of this branch
has no deterministic CNOT: dual-rail linear optics gives single-site unitaries
(Theorem D1, four heaters) and a heralded type-I fusion (Theorem D2, success
1/2). This module compiles that circuit *exactly* into the one form the route
can execute: a fixed 13-photon tree cluster, built offline by fusions, read by
single-photon measurements whose angles are the trained parameters.

What is exact here: the gadget identity for every one of the 64 native angles
(Lemma G1), the Pauli propagation through pre-applied edges (Lemma G2), the
RY rewrite (Lemma G3), and an end-to-end witness in Q(zeta_64) that the
pattern's readout probability equals the circuit's for declared inputs, with
every measurement branch checked and negative controls. What is not here: any
photonic device, any measured number, any claim of learning speed or quantum
advantage (the pinned source itself reports a one-coefficient classical
baseline at 100 % on its task). Training stays on the PC; the chip receives
frozen heater settings.
"""
from fractions import Fraction

from native_relational_qc.cyclotomic64 import Cyclotomic64 as F, ZERO, ONE, ZETA
from native_relational_qc.exact import INV_SQRT2
from native_relational_qc.phase_backend import Phase64Circuit, prepare

from .model import ResourceLimit, integer, rational
from .photonic_response import unit_jet
from .temperature_sweep import _point
from .tree_build import attachments, star

H2 = F(INV_SQRT2)
SQRT2 = H2 + H2
ARCHITECTURE = "four-qubit-parity-five-ry-v1"
SOURCE_PIN = dict(branch="codex/native-self-learning-v1-20261024", commit="cfa04da8f8cdeba8d5c80908d49859f1e9733c12",
                  circuit="native_relational_qc/self_learning.py", checkpoint="native_relational_qc/learning/xor_bits_model.json",
                  note="read-only pin; that branch is not modified or merged here")
XOR_CHECKPOINT = (32, 0, 0, 32, 0)          # phase_steps of the pinned xor_bits_model.json
XOR_EXAMPLES = tuple(((32 * a, 32 * b), a ^ b) for a in (0, 1) for b in (0, 1))
CX_EDGES = ((0, 2), (1, 2), (2, 3))
MAX_LIVE = 12                                # engine bound: at most 2^12 amplitudes
GRADES = ("COMPILED", "CLUSTER_RECORDED", "PATTERN_RECORDED")
NEVER_GRANTED = ("TRAINED_ON_CHIP", "QUANTUM_ADVANTAGE", "ROOM_TEMPERATURE_CLASSIFIER")


def _steps(values, n):
    if not isinstance(values, (tuple, list)) or len(values) != n:
        raise ValueError(f"exactly {n} phase-step integers required")
    out = tuple(integer(v, "phase step") for v in values)
    if any(not 0 <= v <= 63 for v in out):
        raise ValueError("phase steps in [0, 63]")
    return out


# ------------------------------------------------------------------ circuit side

def _ry(circuit, q, steps):
    """RY(theta) as the pinned source writes it, S H P(theta) H S^dagger, theta = steps*pi/32."""
    if not steps:
        return
    circuit.add("sdg", q).add("h", q)
    for bit, name in enumerate(("p64", "p32", "p16", "t", "s", "z")):   # t = p8, s = p4, z = p2
        if steps & (1 << bit):
            circuit.add(name, q)
    circuit.add("h", q).add("s", q)


def classifier_circuit(features, parameters):
    """The pinned architecture on the repo's own Q(zeta_64) backend."""
    f, p = _steps(features, 2), _steps(parameters, 5)
    c = Phase64Circuit(4)
    for q, step in enumerate(f):
        _ry(c, q, step)
    for q, step in enumerate(p[:4]):
        _ry(c, q, step)
    for a, b in CX_EDGES:
        c.add("cx", a, b)
    _ry(c, 3, p[4])
    return c


def circuit_probability(features, parameters):
    """Exact P(qubit 3 = 1) of the circuit, from the phase backend (independent of the pattern engine)."""
    state = prepare(classifier_circuit(features, parameters), max_work=1_000_000, max_branches=16, max_coefficient_bits=4096)
    return state.probability({3: 1})


# ------------------------------------------------------------------ exact lemmas

def _rz(k):
    return ((ONE, ZERO), (ZERO, ZETA ** (k % 64)))


def _mm(a, b):
    n, m, l = len(a), len(b[0]), len(b)
    return tuple(tuple(sum((a[i][t] * b[t][j] for t in range(l)), ZERO) for j in range(m)) for i in range(n))


HAD = ((H2, H2), (H2, -H2))
PX = ((ZERO, ONE), (ONE, ZERO))
PZ = ((ONE, ZERO), (ZERO, -ONE))


def j_gate(k):
    """J(k) = H Rz(k), Rz(k) = diag(1, zeta^k)."""
    return _mm(HAD, _rz(k))


def gadget_lemma(k):
    """Lemma G1: with |psi> on wire 1 and |+> on wire 2, after CZ, measuring wire 1 in the
    basis B(a) = {Rz(a)|+>, Rz(a)|->} with outcome s leaves X^s J(-a)|psi>/sqrt2 on wire 2.
    So J(k) is the measurement at angle a = -k. Checked as an exact 2x2 operator identity."""
    k = integer(k, "steps") % 64
    a = (-k) % 64
    out = {}
    for s in (0, 1):
        # Kraus operator on the input: rows of <s_a| applied to the first wire of CZ(I (x) |+>)
        bra = (H2, (H2 if s == 0 else -H2) * ZETA ** ((-a) % 64))        # <s_a| = (<0| +- zeta^{-a} <1|)/sqrt2
        kraus = [[ZERO, ZERO], [ZERO, ZERO]]
        for i in (0, 1):            # input basis |i> on wire 1 -> bra[i] * (CZ acting on |i>|+>)
            for o in (0, 1):        # output basis on wire 2: |+> amplitude H2, CZ sign (-1)^{i o}
                amp = bra[i] * H2 * (-ONE if i and o else ONE)
                kraus[o][i] = kraus[o][i] + amp
        if s:
            kraus = [list(r) for r in _mm(PX, tuple(tuple(r) for r in kraus))]
        target = tuple(tuple(v * H2 for v in row) for row in j_gate(k))
        out[s] = all(kraus[r][c] == target[r][c] for r in range(2) for c in range(2))
    return dict(steps=k, measurement_angle=a, holds=out[0] and out[1], outcomes=out)


def propagation_lemma():
    """Lemma G2: CZ (X (x) I) CZ = X (x) Z, so an X byproduct on a node whose edges are already
    applied becomes X on that node and Z on each of its other neighbours. Exact 4x4 check."""
    cz = tuple(tuple((-ONE if (i == 3 and j == 3) else ONE) if i == j else ZERO for j in range(4)) for i in range(4))
    x1 = tuple(tuple(ONE if (i ^ j) == 2 else ZERO for j in range(4)) for i in range(4))      # X on wire a (bit 1)
    xz = tuple(tuple((ONE if not (j & 1) else -ONE) if (i ^ j) == 2 else ZERO for j in range(4)) for i in range(4))
    lhs = _mm(_mm(cz, x1), cz)
    return dict(holds=all(lhs[i][j] == xz[i][j] for i in range(4) for j in range(4)))


def ry_lemma(k):
    """Lemma G3: RY(k)|0> = S J(k) |+> exactly, and RY(a) RY(b) = RY(a+b); the pinned RY is
    S H Rz(k) H S^dagger, whose Rz(k) H S^dagger|0> part is J(k)|+> after the first S^dagger H."""
    k = integer(k, "steps") % 64
    s_gate = _rz(16)
    ry = _mm(_mm(_mm(_mm(s_gate, HAD), _rz(k)), HAD), _rz(48))
    lhs = tuple(row[0] for row in ry)                                    # RY(k)|0>
    plus = ((H2,), (H2,))
    rhs = tuple(row[0] for row in _mm(_mm(s_gate, j_gate(k)), plus))
    comp = _mm(_mm(_mm(_mm(_mm(s_gate, HAD), _rz(k)), HAD), _rz(48)), _mm(_mm(_mm(_mm(s_gate, HAD), _rz(7)), HAD), _rz(48)))
    summed = _mm(_mm(_mm(_mm(s_gate, HAD), _rz(k + 7)), HAD), _rz(48))
    return dict(steps=k, prep_holds=all(lhs[i] == rhs[i] for i in range(2)),
                additive_holds=all(comp[i][j] == summed[i][j] for i in range(2) for j in range(2)))


# ------------------------------------------------------------------ the pattern

NODES = 13
EDGES = ((0, 1), (2, 3), (4, 5), (5, 6), (6, 7), (8, 9), (9, 10), (10, 11), (11, 12), (1, 6), (3, 6), (7, 10))
FLOW = {0: 1, 2: 3, 4: 5, 5: 6, 8: 9, 9: 10, 6: 7, 10: 11, 11: 12}
ORDER = (0, 2, 4, 5, 8, 9, 6, 10, 11)      # measured for J gates, in flow order
READOUT = 12
DISCARDED = (1, 3, 7)                        # outputs of wires 0, 1, 2: never read


def neighbours(node):
    return tuple(b if a == node else a for a, b in EDGES if node in (a, b))


def pattern(features, parameters):
    """The classifier as J gates and CZ edges on |+>^4, then as cluster measurements.

    Wire q carries a_q = f_q + p_q (RY angles add, Lemma G3); RY(a)|0> = S J(a)|+>, and the S
    on each wire is either dropped (wires 0, 1: it commutes with CZ and the wire is traced) or
    absorbed as J(16) = H S. CX(c, t) = H_t CZ H_t. Wire 3 ends with J(0) J(48) J(p4) and a
    Z readout, and 'J(p4) then Z' is the readout node measured at angle -p4.
    """
    f, p = _steps(features, 2), _steps(parameters, 5)
    a = ((f[0] + p[0]) % 64, (f[1] + p[1]) % 64, p[2], p[3])
    j_steps = {0: a[0], 2: a[1], 4: a[2], 5: 16, 8: a[3], 9: 16, 6: 0, 10: 0, 11: 48}
    angles = {node: (-k) % 64 for node, k in j_steps.items()}
    angles[READOUT] = (-p[4]) % 64
    wires = {0: (0, 1), 1: (2, 3), 2: (4, 5, 6, 7), 3: (8, 9, 10, 11, 12)}
    return dict(nodes=NODES, edges=EDGES, wires=wires, flow=dict(FLOW), order=ORDER, readout=READOUT,
                discarded=DISCARDED, j_steps=j_steps, measurement_angles=angles,
                corrections={i: dict(x=FLOW[i], z=tuple(n for n in neighbours(FLOW[i]) if n != i)) for i in ORDER})


def is_tree():
    seen, stack = {0}, [0]
    while stack:
        v = stack.pop()
        for w in neighbours(v):
            if w not in seen:
                seen.add(w)
                stack.append(w)
    return len(seen) == NODES and len(EDGES) == NODES - 1


# ------------------------------------------------------------------ exact engine

class _State:
    """Amplitudes in Q(zeta_64) over the live nodes; nodes are allocated as |+> with every edge
    to an already-live node applied at allocation (graph-first semantics, Lemma G2 note)."""

    def __init__(self):
        self.live = []
        self.dead = set()          # measured nodes are never re-allocated
        self.amps = {0: ONE}

    def _pos(self, node):
        return self.live.index(node)

    def ensure(self, node):
        if node in self.live or node in self.dead:
            return
        if len(self.live) >= MAX_LIVE:
            raise ResourceLimit(f"more than {MAX_LIVE} live nodes")
        pos = len(self.live)
        self.live.append(node)
        new = {}
        for key, amp in self.amps.items():
            amp = amp * H2
            new[key] = amp
            new[key | (1 << pos)] = amp
        self.amps = new
        for w in neighbours(node):
            if w in self.live and w != node:
                self.cz(node, w)

    def cz(self, a, b):
        pa, pb = self._pos(a), self._pos(b)
        self.amps = {k: (-v if (k >> pa) & 1 and (k >> pb) & 1 else v) for k, v in self.amps.items()}

    def x(self, node):
        p = self._pos(node)
        self.amps = {k ^ (1 << p): v for k, v in self.amps.items()}

    def z(self, node):
        p = self._pos(node)
        self.amps = {k: (-v if (k >> p) & 1 else v) for k, v in self.amps.items()}

    def measure(self, node, angle):
        """Both outcome branches of a measurement in B(angle); the node is removed."""
        p = self._pos(node)
        phase = ZETA ** ((-angle) % 64)
        low, high = (1 << p) - 1, ~((1 << (p + 1)) - 1)
        branches = []
        for s in (0, 1):
            sign = ONE if s == 0 else -ONE
            out = {}
            for k, v in self.amps.items():
                k2 = (k & low) | ((k & high) >> 1)
                term = v * H2 if not (k >> p) & 1 else v * phase * sign * H2
                out[k2] = out.get(k2, ZERO) + term
            st = _State()
            st.live = [n for n in self.live if n != node]
            st.dead = self.dead | {node}
            st.amps = {k: v for k, v in out.items() if v}
            branches.append(st)
        return branches

    def norm2(self):
        return sum((v.norm2() for v in self.amps.values()), ZERO)

    def equals(self, other):
        return self.live == other.live and self.amps == other.amps


def _touch(state, *nodes):
    for n in nodes:
        state.ensure(n)
        for w in neighbours(n):
            state.ensure(w)


def _correct(state, spec, node, rule):
    if rule == "none":
        return
    c = spec["corrections"][node]
    _touch(state, c["x"])
    state.x(c["x"])
    if rule == "flow":
        for w in c["z"]:
            _touch(state, w)
            state.z(w)


def pattern_run(features, parameters, *, rule="flow", path=None):
    """Run the pattern. rule='flow': full corrections, both branches of every measurement are
    compared exactly after correction and must coincide (the witness), one is kept and
    renormalised. rule='x_only' or 'none': negative controls; `path` (tuple of outcomes) picks
    the branch followed. Returns the exact readout probability P(readout = 1) and the trace."""
    if rule not in ("flow", "x_only", "none"):
        raise ValueError("rule in flow, x_only, none")
    spec = pattern(features, parameters)
    st = _State()
    trace = []
    for idx, node in enumerate(ORDER):
        c = spec["corrections"][node]
        _touch(st, node, c["x"], *c["z"])      # same live set in both branches (allocation commutes)
        b0, b1 = st.measure(node, spec["measurement_angles"][node])
        n0, n1 = b0.norm2(), b1.norm2()
        _correct(b1, spec, node, rule)          # the outcome-1 branch carries the byproduct
        same = b0.equals(b1)
        trace.append(dict(node=node, angle=spec["measurement_angles"][node], p0=n0, p1=n1, branches_equal_after_correction=same))
        if rule == "flow":
            if not same:
                return dict(readout_probability=None, witness=False, failed_at=node, trace=trace)
            st = b0
            st.amps = {k: v * SQRT2 for k, v in st.amps.items()}
        else:
            s = 0 if path is None else path[idx]
            st = b1 if s else b0
            if st.norm2() != H2 * H2:
                raise ArithmeticError("branch weight other than 1/2 is not expected in this pattern")
            st.amps = {k: v * SQRT2 for k, v in st.amps.items()}
    _touch(st, READOUT)
    _, r1 = st.measure(READOUT, spec["measurement_angles"][READOUT])
    p1 = r1.norm2()
    return dict(readout_probability=p1, witness=rule == "flow", trace=trace, rule=rule,
                measurement_angles=spec["measurement_angles"])


def witness(features, parameters):
    """Exact equality of the pattern readout and the circuit probability, with controls."""
    circuit = circuit_probability(features, parameters)
    run = pattern_run(features, parameters, rule="flow")
    ok = run["witness"] and run["readout_probability"] == circuit
    zeros = pattern_run(features, parameters, rule="none", path=(0,) * len(ORDER))
    ones = pattern_run(features, parameters, rule="none", path=(1,) * len(ORDER))
    xonly = pattern_run(features, parameters, rule="x_only")
    return dict(features=list(features), parameters=list(parameters), circuit_probability=circuit,
                pattern_probability=run["readout_probability"], exact_equality=ok,
                branches_checked=len(ORDER), every_branch_weight_half=all(t["p0"] == H2 * H2 and t["p1"] == H2 * H2 for t in run["trace"]),
                control_no_corrections=dict(all_zero_path=zeros["readout_probability"], all_one_path=ones["readout_probability"],
                                            outcome_dependent=zeros["readout_probability"] != ones["readout_probability"]),
                control_x_only=dict(branches_diverge=any(not t["branches_equal_after_correction"] for t in xonly["trace"])),
                trace=run["trace"])


def xor_witnesses(parameters=XOR_CHECKPOINT):
    """The pinned checkpoint on all four XOR inputs: exact equality and the predicted label."""
    rows = []
    for feats, label in XOR_EXAMPLES:
        w = witness(feats, parameters)
        p = w["pattern_probability"]
        rows.append(dict(features=list(feats), label=label, exact_equality=w["exact_equality"], p_one=p,
                         predicted=(1 if (p - H2 * H2).real_sign() > 0 else 0), x_only_control_diverges=w["control_x_only"]["branches_diverge"],
                         uncorrected_paths_differ=w["control_no_corrections"]["outcome_dependent"]))
    return rows


# ------------------------------------------------------------------ resources

def cluster_resources(spare=0):
    """The tree cluster from stars (v0.27 law): rooted at the hub node 6; a child's star centre is
    fused into a spare leaf of its parent; each fusion is heralded at 1/2. Leaves of the tree
    are star leaves and cost no fusion. Bell-pair counts are conditional on success as in v0.27."""
    r = integer(spare, "spare")
    if not 0 <= r <= 16:
        raise ValueError("spare in [0, 16]")
    def cost(size):
        s = star(size)
        return s["expected_bell_pairs"] / s["p_reach"]
    def consumed(blocks):
        a = attachments(blocks, r)
        return a["expected_blocks_consumed"] / blocks, a["p_build"]
    c10 = cost(3 + r); k, p10 = consumed(2); c10 += k * (1 + 1)                     # 9 and 11 are Bell pairs
    c7 = cost(2 + r); k, p7 = consumed(1); c7 += k * c10
    c6 = cost(5 + r); k, p6 = consumed(4); c6 += k * (1 + 1 + 1 + c7)               # 1, 3, 5 are Bell pairs
    fusions = len(EDGES) - sum(1 for n in range(NODES) if len(neighbours(n)) == 1)
    return dict(photons=NODES, edges=len(EDGES), tree=is_tree(), fusions=fusions, spare_leaves_per_parent=r,
                p_build_all=p6 * p7 * p10, one_shot_no_spare=Fraction(1, 2) ** fusions,
                expected_bell_pairs_conditional_on_success=c6,
                stars=dict(hub6=5 + r, node10=3 + r, node7=2 + r, bell_pairs=("1", "3", "5", "9", "11")),
                memory_requirement="Theorem B1 (TREE_BUILD.md): offline multiplexed building pays only at m >~ 0.99 per 0.1 us attempt; storage survival of this cluster is not computed here")


# ------------------------------------------------------------------ heater codebook

def heater_setting(angle):
    """Measurement in B(angle) on a dual-rail site with the four-heater unit of Theorem D1:
    inner exchange at theta = pi/2 (16 steps), output trim at the nominal 48, and the input
    trim `before` found exactly so that Rz(angle)|+> exits on rail 0 and Rz(angle)|-> on rail 1."""
    k = integer(angle, "angle") % 64
    l, u, _, a = _point(16)
    plus = ((H2,), (H2 * ZETA ** k,))
    minus = ((H2,), (-H2 * ZETA ** k,))
    for b in range(64):
        word, _ = unit_jet((l, u, b, a))
        if _mm(word, plus)[1][0] == ZERO and _mm(word, minus)[0][0] == ZERO:
            return dict(angle=k, heaters=dict(lower=l, upper=u, before=b, after=a), unit="pi/32 steps", click_rail_for_plus=0)
    raise ArithmeticError("no exact heater setting found")


def heater_codebook(features, parameters):
    spec = pattern(features, parameters)
    rows = []
    for node in ORDER + (READOUT,):
        angle = spec["measurement_angles"][node]
        h = heater_setting(angle)
        rows.append(dict(node=node, role="readout" if node == READOUT else f"J({spec['j_steps'][node]})",
                         angle=angle, before_steps=h["heaters"]["before"], trained=(node in (0, 2, 4, 8, READOUT))))
    return dict(rows=rows, trained_heaters=sum(1 for r in rows if r["trained"]), fixed_heaters=sum(1 for r in rows if not r["trained"]),
                detectors=2 * (len(ORDER) + 1 + len(DISCARDED)),
                note="training changes five 'before' trims only; the cluster, the fusions and the fixed angles do not change")


# ------------------------------------------------------------------ plan and grader

def compile_plan():
    res = cluster_resources(0)
    res4 = cluster_resources(4)
    return dict(schema="native-cluster-compile-v1", author="Monty", status="COMPILED_NO_DEVICE", architecture=ARCHITECTURE,
                source=SOURCE_PIN, photons=NODES, edges=len(EDGES), fusions=res["fusions"], measured_nodes=len(ORDER) + 1,
                discarded_nodes=list(DISCARDED), one_shot_build=str(res["one_shot_no_spare"]),
                p_build_spare4=str(res4["p_build_all"]), bell_pairs_spare4=str(res4["expected_bell_pairs_conditional_on_success"]),
                postselected_alternative="three KLM-type CNOTs at 1/9 each: 1/729 per shot and no herald; not a route",
                claims=dict(exact=["Lemmas G1-G3", "end-to-end readout equality in Q(zeta_64) for declared inputs", "resource law from v0.27"],
                            never=list(NEVER_GRANTED), open=["optical build and storage of the 13-photon tree", "angle adaptation versus active correction in hardware",
                                                               "loss, multi-pair and dark counts on the measured nodes (LEDGER_VIOLATIONS.md)", "every measured number"]))


def compile_grade(record):
    """Fail-closed: COMPILED -> CLUSTER_RECORDED (LAB_RECORDED 13-photon cluster with at least 12
    stabiliser witnesses) -> PATTERN_RECORDED (LAB_RECORDED readout frequencies with feedforward on,
    within tolerance of the exact probability on every declared input). Any record that asserts a
    never-granted claim is rejected outright."""
    if type(record) is not dict:
        raise ValueError("record must be a dict")
    for key in NEVER_GRANTED:
        if record.get(key.lower()) or record.get(key):
            return dict(grade="REJECTED", reasons=[f"{key} is never granted by this grader"])
    reasons = []
    c = record.get("cluster")
    if not (type(c) is dict and c.get("evidence_class") == "LAB_RECORDED" and c.get("photons") == NODES
            and type(c.get("stabiliser_witnesses")) is int and c["stabiliser_witnesses"] >= len(EDGES)):
        reasons.append("cluster block needs LAB_RECORDED photons == 13 and an integer count of at least 12 stabiliser witnesses")
        return dict(grade="COMPILED", reasons=reasons)
    r = record.get("readout")
    if not (type(r) is dict and r.get("evidence_class") == "LAB_RECORDED" and r.get("feedforward") is True
            and type(r.get("parameters")) in (list, tuple) and type(r.get("rows")) is list and r["rows"]):
        reasons.append("readout block needs LAB_RECORDED feedforward=True, parameters and non-empty rows")
        return dict(grade="CLUSTER_RECORDED", reasons=reasons)
    tol = rational(Fraction(str(r.get("tolerance", "1/20"))), "tolerance", 256)
    if not 0 <= tol < 1:
        raise ValueError("tolerance in [0, 1)")
    for row in r["rows"]:
        if not (type(row) is dict and type(row.get("features")) in (list, tuple) and row.get("shots") and row.get("ones") is not None):
            reasons.append("each readout row needs features, shots, ones")
            return dict(grade="CLUSTER_RECORDED", reasons=reasons)
        shots, ones = integer(row["shots"], "shots"), integer(row["ones"], "ones")
        if shots < 1 or not 0 <= ones <= shots:
            raise ValueError("shots >= 1 and 0 <= ones <= shots")
        exact = circuit_probability(row["features"], r["parameters"])
        lo, hi = exact.real_bounds(40)
        freq = Fraction(ones, shots)
        if freq < lo - tol or freq > hi + tol:
            reasons.append(f"features {list(row['features'])}: recorded frequency {freq} outside [{float(lo):.4f}, {float(hi):.4f}] +- tolerance")
            return dict(grade="CLUSTER_RECORDED", reasons=reasons)
    return dict(grade="PATTERN_RECORDED", reasons=reasons, allowed=["recorded pattern readout agrees with the exact compiled probability"],
                never=list(NEVER_GRANTED))
