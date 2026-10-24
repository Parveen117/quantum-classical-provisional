"""Exact algebra checks for a specified threshold model; no device inference.

Classical calibration scores are converted to a Boolean function only after
all four rows satisfy the requested margin. Quantum execution uses its coherent
XOR oracle, never thresholding amplitudes or assigning an unmeasured heat cost.
"""
from dataclasses import dataclass
from fractions import Fraction

from .compact import _integer
from .reversible_logic import BooleanMap


def _rational(value):
    if isinstance(value,bool) or not isinstance(value,(int,Fraction)):
        raise TypeError('use explicit int/Fraction coefficients; floats are not inferred')
    return Fraction(value)


@dataclass(frozen=True)
class ThresholdModel:
    """Score b + k1*x*theta + k2*y*theta + k3*x*y*theta**2, x,y bits.

    Coefficient units must match this expression. This class cannot establish a
    material-specific map from transport coefficients to the score parameters.
    """
    k1: Fraction = Fraction(0)
    k2: Fraction = Fraction(0)
    k3: Fraction = Fraction(0)
    bias: Fraction = Fraction(0)
    theta: Fraction = Fraction(1)
    threshold: Fraction = Fraction(1,2)
    margin: Fraction = Fraction(1,4)
    high_is_one: bool = True

    def __post_init__(self):
        for field in ('k1','k2','k3','bias','theta','threshold','margin'):
            object.__setattr__(self,field,_rational(getattr(self,field)))
        if self.theta <= 0 or self.margin <= 0:
            raise ValueError('theta and requested margin must be positive')
        if type(self.high_is_one) is not bool:
            raise ValueError('high_is_one must be boolean')

    def score(self,x,y):
        _integer(x,'x bit',0,1);_integer(y,'y bit',0,1)
        return self.bias+self.k1*x*self.theta+self.k2*y*self.theta+self.k3*x*y*self.theta**2

    def check(self, function):
        if not isinstance(function,BooleanMap) or (function.input_bits,function.output_bits)!=(2,1):
            raise ValueError('threshold check needs a two-input, one-output BooleanMap')
        rows = []
        for index,wanted in enumerate(function.table):
            x,y = index&1,(index>>1)&1
            score = self.score(x,y)
            sign = 1 if wanted == int(self.high_is_one) else -1
            achieved = sign*(score-self.threshold)
            rows.append(dict(x=x,y=y,wanted=wanted,score=str(score),
                             signed_margin=str(achieved),passed=achieved>=self.margin))
        return dict(passed=all(row['passed'] for row in rows),rows=rows,
                    requested_margin=str(self.margin),high_is_one=self.high_is_one,
                    scope='four exact Boolean rows of the supplied score model; no physical calibration')

    def certified_function(self, function):
        report = self.check(function)
        if not report['passed']:
            raise ValueError('threshold model fails requested truth table or margin')
        return function


def transport_split(matrix, forces):
    """Exact real 2x2 quadratic-form audit: X^T L X = X^T sym(L) X.

    Antisymmetric transport can alter fluxes but contributes zero to this
    scalar. The PSD test applies when these are conjugate entropy forces.
    """
    if len(matrix)!=2 or any(len(row)!=2 for row in matrix) or len(forces)!=2:
        raise ValueError('expected a 2x2 transport matrix and two forces')
    l = tuple(tuple(_rational(v) for v in row) for row in matrix)
    x = tuple(_rational(v) for v in forces)
    symmetric = tuple(tuple((l[i][j]+l[j][i])/2 for j in range(2)) for i in range(2))
    antisymmetric = tuple(tuple((l[i][j]-l[j][i])/2 for j in range(2)) for i in range(2))
    quadratic = lambda m:sum((x[i]*m[i][j]*x[j] for i in range(2) for j in range(2)),Fraction(0))
    determinant = symmetric[0][0]*symmetric[1][1]-symmetric[0][1]**2
    return dict(total=quadratic(l),symmetric=quadratic(symmetric),antisymmetric=quadratic(antisymmetric),
                symmetric_matrix=symmetric,antisymmetric_matrix=antisymmetric,
                symmetric_psd=symmetric[0][0]>=0 and symmetric[1][1]>=0 and determinant>=0)


def expected_carry_activity(width, cin_probability=Fraction(1,2)):
    """Dimensionless E[sum_i (Ai Bi + (Ai XOR Bi) Ci)] for fair input words.

    A and B have independent fair bits; Cin is independent with the supplied
    probability. This is not entropy, joules, power, a reset cost or a noise law.
    AB*(A XOR B)*Cin is identically zero on bits, not an independent product.
    """
    n = _integer(width,'activity width',1,256)
    p = _rational(cin_probability)
    if not 0<=p<=1:
        raise ValueError('Cin probability must be in [0,1]')
    return Fraction(n,2)+(p-Fraction(1,2))*(1-Fraction(1,2**n))
