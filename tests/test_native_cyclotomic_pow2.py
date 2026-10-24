from decimal import Decimal,localcontext
from fractions import Fraction as F
import random
import unittest

from native_relational_qc.exact import OMEGA,IMAG,INV_SQRT2
from native_relational_qc.cyclotomic64 import Cyclotomic64
from native_relational_qc.cyclotomic_pow2 import field_of_order,_pi_bounds,_cos_bounds
from native_relational_qc.phase_backend import PowerPhaseCircuit,Phase64Circuit,required_order
from native_relational_qc.calculator import calculate,validate
from native_relational_qc.shor import build,assess,decode,exact_phase_law


def request(c,backend='cyclotomic_pow2',qubits=None):
    return dict(schema='nrqc-calculator-v1',n_qubits=c.n_qubits,backend=backend,
        operations=[[n,list(q)] for n,q in c.operations],
        queries=[dict(id='d',kind='distribution',qubits=qubits or list(reversed(range(min(c.n_qubits,6)))))])


def decimal_cos(e,M,places=60):
    """Independent Decimal cosine for comparing certified enclosures."""
    with localcontext() as ctx:
        ctx.prec=places+20
        pi=Decimal(0);k=0
        # Bailey-Borwein-Plouffe series, independent of the Machin bounds.
        while k<places:
            pi+=(Decimal(4)/(8*k+1)-Decimal(2)/(8*k+4)-Decimal(1)/(8*k+5)-Decimal(1)/(8*k+6))/Decimal(16)**k;k+=1
        x=2*pi*e/M;term=Decimal(1);total=Decimal(1);j=0
        while abs(term)>Decimal(10)**-(places+10):
            j+=1;term*=-x*x/((2*j-1)*(2*j));total+=term
        return total


class FlatFieldTests(unittest.TestCase):
    def test_pi_enclosure_is_tight_and_correct(self):
        low,high=_pi_bounds(256)
        with localcontext() as ctx:
            ctx.prec=90
            reference=Decimal('3.14159265358979323846264338327950288419716939937510582097494459230781640628620899')
        self.assertLess(low,high);self.assertLess(high-low,F(1,2**250))
        self.assertLessEqual(Decimal(low.numerator)/Decimal(low.denominator),reference)
        self.assertGreaterEqual(Decimal(high.numerator)/Decimal(high.denominator),reference-Decimal(10)**-75)

    def test_cosine_enclosures_contain_independent_values(self):
        for M in (8,16,128,4096):
            for e in sorted({0,1,M//8,M//4,M//4+1,M//2-1,M//2,M-1}|{random.Random(M).randrange(M) for _ in range(20)}):
                low,high=_cos_bounds(M,e,200)
                ref=decimal_cos(e,M)
                lo=Decimal(low.numerator)/Decimal(low.denominator);hi=Decimal(high.numerator)/Decimal(high.denominator)
                self.assertLessEqual(lo,ref+Decimal(10)**-55,(M,e));self.assertGreaterEqual(hi,ref-Decimal(10)**-55,(M,e))
                self.assertLess(high-low,F(1,2**190))

    def test_root_relations_and_embedding_of_exact_field(self):
        for M in (8,16,64,256,4096):
            Z=field_of_order(M);z=Z.root()
            power=Z(1)
            for _ in range(M//2):power=power*z
            self.assertEqual(power,Z(-1))
            self.assertEqual(Z(OMEGA),Z.root(M//8));self.assertEqual(Z(IMAG),Z.root(M//4))
            self.assertEqual(Z(INV_SQRT2)*Z(INV_SQRT2),Z(F(1,2)))
            self.assertEqual(Z.sqrt2()*Z.sqrt2(),Z(2))
            # The power basis is canonical: distinct exponents never collide.
            self.assertEqual(len({Z.root(e) for e in range(M)}),M)

    def test_field_axioms_on_random_elements(self):
        rng=random.Random(7)
        for M in (32,1024):
            Z=field_of_order(M)
            def element():
                out=Z()
                for _ in range(rng.randrange(1,6)):out=out+Z(F(rng.randrange(-9,10),rng.randrange(1,9)))*Z.root(rng.randrange(M))
                return out
            for _ in range(30):
                a,b,c=element(),element(),element()
                self.assertEqual(a*(b+c),a*b+a*c);self.assertEqual((a*b)*c,a*(b*c));self.assertEqual(a*b,b*a)
                self.assertEqual((a*b).conjugate(),a.conjugate()*b.conjugate())
                self.assertAlmostEqual(complex(a*b),complex(a)*complex(b),places=9)
                self.assertAlmostEqual(complex(a.conjugate()),complex(a).conjugate(),places=9)
                self.assertEqual(Z.from_dict(a.to_dict()),a)

    def test_roots_match_nested_zeta64(self):
        rng=random.Random(64);Z=field_of_order(64)
        for _ in range(40):
            k=rng.randrange(64);n=rng.randrange(64)
            nested=complex(Phase64Circuit.root**k)*complex(Phase64Circuit.root**n)
            self.assertAlmostEqual(complex(Z.root(k)*Z.root(n)),nested,places=12)

    def test_sign_and_display_are_certified(self):
        Z=field_of_order(4096)
        tiny=Z.root(1)+Z.root(-1)-Z(2)   # 2cos(2pi/4096)-2 < 0, about -2.35e-6
        self.assertEqual(tiny.real_sign(),-1)
        shown=tiny.display(20)
        ref=2*decimal_cos(1,4096)-2
        self.assertLessEqual(Decimal(shown['decimal_enclosure']['lower']),ref)
        self.assertGreaterEqual(Decimal(shown['decimal_enclosure']['upper']),ref)
        with self.assertRaises(ValueError):Z.root(3).real_sign()
        with self.assertRaises(ValueError):Z.root(3).display(4)

    def test_order_validation(self):
        for bad in (4,12,8192):
            with self.assertRaises(ValueError):field_of_order(bad)
        with self.assertRaises(ValueError):field_of_order(64)(field_of_order(128).root())


class FlatBackendTests(unittest.TestCase):
    def test_gate_names_and_inferred_order(self):
        self.assertEqual(required_order([('h',(0,)),('cp1024dg',(0,1))]),1024)
        self.assertEqual(required_order([('t',(0,))]),8)
        with self.assertRaises(ValueError):required_order([('p24',(0,))])
        c=PowerPhaseCircuit(2,256)
        c.add('p256',0).add('cp4',0,1)
        with self.assertRaises(ValueError):c.add('p512',0)
        with self.assertRaises(ValueError):c.add('cp8',0,0)

    def test_phase_interference_matches_closed_form(self):
        # H p_K H on one wire: P(1)=(1-cos(2pi/K))/2.
        for K in (8,128,4096):
            c=PowerPhaseCircuit(1,K).add('h',0).add(f'p{K}',0).add('h',0)
            report=calculate(request(c,qubits=[0]))
            self.assertEqual(report['status'],'completed')
            Z=field_of_order(K)
            p1=Z.from_dict(report['answers'][0]['probabilities']['1']['exact'])
            self.assertEqual(p1,(Z(2)-Z.root(1)-Z.root(-1))/4)

    def test_agrees_with_nested_backend_on_same_request(self):
        c=Phase64Circuit(3)
        for name,qs in (('h',(0,)),('h',(1,)),('cp64',(0,1)),('p32dg',(1,)),('ccx',(0,1,2)),('t',(2,)),('h',(2,)),('cp16',(2,0)),('h',(0,))):
            c.add(name,*qs)
        nested=calculate(request(c,'cyclotomic64',[2,1,0]));flat=calculate(request(c,'cyclotomic_pow2',[2,1,0]))
        self.assertEqual(nested['status'],'completed');self.assertEqual(flat['status'],'completed')
        Z=field_of_order(64)
        for label,value in nested['answers'][0]['probabilities'].items():
            a=Cyclotomic64.from_dict(value['exact']);b=Z.from_dict(flat['answers'][0]['probabilities'][label]['exact'])
            self.assertAlmostEqual(complex(a).real,complex(b).real,places=13)
            self.assertEqual(value['decimal'],flat['answers'][0]['probabilities'][label]['decimal'])

    def test_rejections_and_whole_batch_budget(self):
        c=PowerPhaseCircuit(2,16).add('h',0).add('cp16',0,1)
        doc=request(c);doc['simplify']='exact'
        with self.assertRaises(ValueError):validate(doc)
        doc=request(c);doc['limits']={'max_work':3}
        report=calculate(doc)
        self.assertEqual(report['status'],'incomplete');self.assertEqual(report['answers'],[])


class FlatShorTests(unittest.TestCase):
    def test_flat_law_equals_nested_law(self):
        for N,a,m in ((15,7,3),(21,2,4),(33,5,5),(141,2,6)):
            nested=exact_phase_law(N,a,m);flat=exact_phase_law(N,a,m,field='flat')
            Z=field_of_order(max(8,1<<m))
            self.assertEqual(sum(flat.values(),Z()),Z(1))
            for y in nested:self.assertAlmostEqual(complex(nested[y]).real,complex(flat[y]).real,places=13)

    def test_seven_bit_arithmetic_shor_verified_against_fourier_law(self):
        program=build(21,2,precision=7,oracle='arithmetic',rewrite='panini',field='flat')
        phases={name for name,_ in program.circuit.operations if name.startswith('cp')}
        self.assertEqual(phases,{f'cp{1<<k}dg' for k in range(2,8)})  # one native gate per QFT distance
        report=calculate(program.request('cyclotomic_pow2'))
        self.assertEqual(report['status'],'completed')
        result=assess(program,report)
        self.assertEqual(result['status'],'verified')
        Z=field_of_order(128)
        success=Z.from_dict(result['policies']['convergents_and_doubles']['exact_success_probability'])
        self.assertGreater(success.real_sign(),0)

    def test_flat_program_requires_flat_backend_and_precision_limit(self):
        program=build(15,2,precision=7,oracle='arithmetic',field='flat')
        with self.assertRaises(ValueError):program.request('cyclotomic64')
        with self.assertRaises(ValueError):build(15,2,precision=7,oracle='arithmetic')
        with self.assertRaises(ValueError):build(15,2,precision=13,oracle='arithmetic',field='flat')
        self.assertEqual(decode(0,141,2,12)['status'],'no_information')


if __name__=='__main__':unittest.main()
