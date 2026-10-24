import copy
from fractions import Fraction
import importlib.util
import random
import unittest

from native_relational_qc import jya_frame as jya,clifford_frame as frame,clifford_t
from native_relational_qc.compact import ResourceLimit
from native_relational_qc.large_register import LargeCircuit
from native_relational_qc.exact import Exact,ONE,ZERO,IMAG,HALF,exact_gate
from native_relational_qc.pauli_engine import compile_plan
from native_relational_qc.calculator import calculate,run_calculation,validate
from native_relational_qc.emk_tensor import geometry


def budget(c,**changes):
    options=dict(max_work=10_000_000,max_coefficient_bits=4096,max_branches=4096,
                 max_pairs=1_000_000,max_generators=2056,progress=None)
    options.update(changes)
    return jya._Budget(c,*options.values())


def document(c,queries,**options):
    return dict(schema='nrqc-calculator-v1',n_qubits=c.n_qubits,backend='jya_frame',
        operations=[[name,list(qs)] for name,qs in c.operations],queries=queries,**options)


def repeated(n=1,count=8,word=('h','t'),q=0):
    c=LargeCircuit(n)
    for _ in range(count):
        for name in word:c.add(name,q)
    return c


def mixed(n,seed):
    rng=random.Random(seed);c=LargeCircuit(n)
    for _ in range(6):
        q=rng.randrange(n)
        word=rng.choice((('h','t'),('sx','tdg'),('r','t','s'),('t','h','tdg')))
        for _ in range(rng.randrange(1,5)):
            for name in word:c.add(name,q)
        if n>1:c.add(rng.choice(('cx','cz','swap')),*rng.sample(range(n),2))
    return c


class JyaFrameTests(unittest.TestCase):
    def test_native_jya_witness_and_no_sine_division(self):
        # SE44's r=1/3 gives c=4/5, s=3/5, kappa=2/5.
        c,s=Exact(Fraction(4,5)),Exact(Fraction(3,5))
        turn=((c,-s),(s,c));b=budget(LargeCircuit(1))
        previous=ZERO;current=Exact(3438)*s
        for n in range(1,13):
            nxt=2*c*current-previous
            power=jya._power(turn,n+1,b)
            self.assertEqual(Exact(3438)*power[1][0],nxt)
            self.assertEqual(power[0][0].norm2()+power[1][0].norm2(),ONE)
            previous,current=current,nxt
        for matrix in (jya.IDENTITY,((-ONE,ZERO),(ZERO,-ONE)),exact_gate('r'),exact_gate('t')):
            sequential=jya.IDENTITY
            for n in range(17):
                self.assertEqual(jya._power(matrix,n,b),sequential)
                sequential=jya._matmul(matrix,sequential,b)

    def test_period_and_partial_tail_against_linear_compilation(self):
        rng=random.Random(271)
        names=('id','x','y','z','h','s','sdg','sx','sxdg','r','k','rk','t','tdg')
        for width in range(1,8):
            word=[rng.choice(names) for _ in range(width)]
            for count in (1,2,3,8,13):
                sequence=word*count+word[:width//2]
                b=budget(LargeCircuit(1));linear=budget(LargeCircuit(1))
                self.assertEqual(jya._local_return(sequence,b),jya._local_return(sequence,linear,fold=False))

    def test_every_small_probability_against_original_exact_engine(self):
        for n in range(1,5):
            for seed in (3,17,81):
                c=mixed(n,seed);total=ZERO
                for ket in range(1<<n):
                    target={q:(ket>>q)&1 for q in range(n)}
                    result=jya.probability(c,target)
                    self.assertEqual(result.value,frame.probability(c,target).value)
                    total+=result.value
                self.assertEqual(total,ONE)

    def test_all_pauli_axes_and_changing_noncommuting_blocks(self):
        for n in (2,4):
            for seed in (19,2056):
                c=mixed(n,seed)
                for axis in ('X','Y','Z'):
                    word={q:axis for q in range(n)}
                    self.assertEqual(jya.expectation(c,word).value,clifford_t.expectation(c,word).value)
        a=repeated(count=3,word=('h','t'))
        b=repeated(count=3,word=('t','h'))
        # The Z reading is blind to this order change; Y separates it.
        self.assertEqual(jya.expectation(a,{0:'Z'}).value,jya.expectation(b,{0:'Z'}).value)
        self.assertNotEqual(jya.expectation(a,{0:'Y'}).value,jya.expectation(b,{0:'Y'}).value)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional Qiskit reference')
    def test_full_complex_state_against_qiskit_without_phase_alignment(self):
        import numpy as np
        from qiskit.quantum_info import Statevector,Operator
        from native_relational_qc.compact_qiskit import to_qiskit
        cases=[mixed(n,seed) for n in range(1,6) for seed in (2,13,79)]
        cases += [repeated(count=m,word=w) for m in (2,3,8,17)
                  for w in (('r','t','tdg'),('y','t','tdg'),('t',),('h','t'))]
        for c in cases:
            plan=compile_plan(c,True);b=budget(c)
            _,amplitudes=jya._prepare(plan,b)
            residual=np.zeros(1<<c.n_qubits,dtype=complex)
            for ket,value in amplitudes.items():residual[ket]=complex(value)
            skeleton=LargeCircuit(c.n_qubits)
            for kind,event in jya._events(plan,budget(c)):
                if kind=='clifford':
                    name,x,y=event
                    qs=[x.bit_length()-1]+([y.bit_length()-1] if y else [])
                    skeleton.add(name,*qs)
            actual=Operator(to_qiskit(skeleton)).data@residual
            expected=Statevector.from_instruction(to_qiskit(c)).data
            np.testing.assert_allclose(actual,expected,atol=8e-13,rtol=0)

    def test_global_phase_is_retained_in_residual(self):
        for word,expected in ((('r','t','tdg'),-ONE),(('y','t','tdg'),ONE)):
            c=repeated(count=2,word=word)
            cliffords,amplitudes=jya._prepare(compile_plan(c,True),budget(c))
            self.assertEqual(cliffords,[])
            self.assertEqual(amplitudes,{0:expected})
        c=repeated(count=2,word=('t',)).add('x',0)
        _,amplitudes=jya._prepare(compile_plan(c,True),budget(c))
        self.assertEqual(amplitudes,{1:ONE})

    def test_two_qubit_gate_and_other_wire_are_compiler_boundaries(self):
        c=repeated(n=2,count=4).add('cx',0,1)
        for _ in range(4):c.add('h',0).add('t',0)
        c.add('t',1).add('h',0).add('t',0)
        b=budget(c);events=list(jya._events(compile_plan(c,True),b))
        self.assertEqual([kind for kind,_ in events],['local','clifford','local','local','local'])
        self.assertEqual(b.stats['repeated_blocks'],2)
        self.assertEqual(jya.probability(c,{0:1,1:0}).value,frame.probability(c,{0:1,1:0}).value)

    def test_2056_entangled_register_with_repeated_local_return(self):
        c=LargeCircuit(2056).add('h',0)
        for q in range(2055):c.add('cx',q,q+1)
        for _ in range(32):c.add('h',0).add('t',0)
        # All other qubits zero selects the initial GHZ zero component.
        local=repeated(count=32)
        expected=frame.probability(local,{0:0}).value*HALF
        result=jya.probability(c,{q:0 for q in range(2056)})
        self.assertEqual(result.value,expected)
        self.assertEqual(result.statistics['largest_repeat'],32)
        self.assertEqual(result.statistics['measurement_generators'],2056)
        self.assertFalse(result.statistics['dense_statevector_constructed'])

    def test_resource_guards_report_no_value(self):
        c=repeated(count=32)
        for limits in ({'max_work':1},{'max_coefficient_bits':8},{'max_branches':1}):
            with self.assertRaises(ResourceLimit) as failure:jya.expectation(c,{0:'X'},**limits)
            self.assertNotIn('value',failure.exception.statistics)
        c=LargeCircuit(2).add('h',0).add('t',0).add('h',1)
        with self.assertRaises(ResourceLimit):jya.probability(c,{1:0},max_pairs=1)
        with self.assertRaises(ResourceLimit):jya.probability(c,{0:0,1:0},max_generators=1)
        self.assertEqual(jya.probability(c,{},max_pairs=1).value,ONE)

    def test_cli_distribution_geometry_and_strict_validation(self):
        c=repeated(n=3,count=5).add('cx',0,2)
        queries=[dict(id='dist',kind='distribution',qubits=[2,0]),
                 dict(id='tensor',kind='geometry',generators=[dict(paulis={'0':'X'}),dict(paulis={'2':'Y'})])]
        d=document(c,queries);result=run_calculation(d)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(result['answers'][0]['normalization'],ONE.to_dict())
        other=copy.deepcopy(d);other['backend']='clifford_frame'
        reference=calculate(other)
        self.assertEqual(result['answers'][0]['probabilities'],reference['answers'][0]['probabilities'])
        for field in ('metric','curvature','complex_gram_rank'):
            self.assertEqual(result['answers'][1]['geometry'][field],reference['answers'][1]['geometry'][field])
        for key in ('max_bond','max_terms'):
            bad=copy.deepcopy(d);bad['limits']={key:4}
            with self.assertRaises(ValueError):validate(bad)
        bad=copy.deepcopy(d);bad['contraction']='streaming'
        with self.assertRaises(ValueError):validate(bad)

    def test_unsupported_gates_rejected_before_simplification(self):
        for name,qs in (('ch',(0,1)),('cs',(0,1)),('ct',(0,1)),('ccx',(0,1,2))):
            c=LargeCircuit(3).add(name,*qs).add(name,*qs)
            with self.assertRaises(ValueError):jya.probability(c,{})
            with self.assertRaises(ValueError):validate(document(c,[dict(id='p',kind='probability',outcomes={})],simplify='exact'))
        with self.assertRaises(TypeError):jya.expectation(object(),{})

    def test_progress_work_accounting_and_timeout(self):
        c=repeated(count=8);events=[]
        result=jya.expectation(c,{0:'Z'},progress=events.append)
        self.assertEqual(events[-1]['event'],'completed')
        costs=('plan_gates','gate_visits','branch_updates','normalization_terms','row_products',
               'constraint_checks','pair_visits','compile_gates','period_comparisons',
               'local_products','recurrence_products','local_unitarity_checks')
        self.assertEqual(result.statistics['work_used'],sum(result.statistics[k] for k in costs))
        d=document(c,[dict(id='p',kind='probability',outcomes={'0':0})])
        result=run_calculation(d,timeout_seconds=1e-9)
        self.assertEqual(result['status'],'time_limit');self.assertEqual(result['answers'],[])


if __name__=='__main__':unittest.main()
