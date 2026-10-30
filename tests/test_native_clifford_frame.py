import copy
from fractions import Fraction
import importlib.util
import random
import unittest

from native_relational_qc import clifford_frame as frame,clifford_t,stabilizer
from native_relational_qc.compact import ResourceLimit
from native_relational_qc.large_register import LargeCircuit
from native_relational_qc.exact import Exact,ONE,ZERO,HALF,INV_SQRT2
from native_relational_qc.calculator import calculate,run_calculation,validate
from native_relational_qc.emk_tensor import geometry
from native_relational_qc.reduction import reduce_circuit


def circuit(n,seed):
    rng=random.Random(seed);c=LargeCircuit(n)
    for step in range(36):
        if step%7==0:
            c.add(rng.choice(('t','tdg')),rng.randrange(n))
        elif n>1 and rng.randrange(3)==0:
            c.add(rng.choice(('cx','cz','swap')),*rng.sample(range(n),2))
        else:c.add(rng.choice(('id','h','s','sdg','sx','sxdg','x','y','z','r','k','rk')),rng.randrange(n))
    return c


def ghz(n,phase='t'):
    c=LargeCircuit(n).add('h',0)
    for q in range(n-1):c.add('cx',q,q+1)
    return c.add(phase,0)


def request(c,queries,**options):
    return dict(schema='nrqc-calculator-v1',n_qubits=c.n_qubits,backend='clifford_frame',
        operations=[[name,list(qs)] for name,qs in c.operations],queries=queries,**options)


class CliffordFrameTests(unittest.TestCase):
    def test_every_small_outcome_against_exact_pauli_expansion(self):
        for n in range(1,5):
            for seed in range(4):
                c=circuit(n,seed);total=ZERO
                for bits in range(1<<n):
                    assignment={q:(bits>>q)&1 for q in range(n)}
                    actual=frame.probability(c,assignment).value
                    self.assertEqual(actual,clifford_t.probability(c,assignment).value)
                    total+=actual
                self.assertEqual(total,ONE)

    def test_random_marginals_and_paulis_against_exact_expansion(self):
        for n in (2,4,6):
            for seed in (71,117,2056,313):
                c=circuit(n,seed);rng=random.Random(seed)
                for _ in range(4):
                    sites=rng.sample(range(n),min(n,3))
                    assignment={q:rng.randrange(2) for q in sites}
                    word={q:rng.choice('IXYZ') for q in range(n)}
                    self.assertEqual(frame.probability(c,assignment).value,clifford_t.probability(c,assignment).value)
                    self.assertEqual(frame.expectation(c,word).value,clifford_t.expectation(c,word).value)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional Qiskit reference')
    def test_entire_frame_state_and_marginals_against_independent_qiskit(self):
        import numpy as np
        from qiskit.quantum_info import Statevector,Operator
        from native_relational_qc.compact_qiskit import to_qiskit
        from native_relational_qc.pauli_engine import compile_plan
        for n in range(1,7):
            for seed in range(4):
                c=circuit(n,seed)
                budget=frame._Budget(c,10_000_000,4096,4096,1_000_000,2056,None)
                _,amplitudes=frame._prepare(compile_plan(c,True),budget)
                residual=np.zeros(1<<n,dtype=complex)
                for ket,value in amplitudes.items():residual[ket]=complex(value)
                skeleton=LargeCircuit(n)
                for name,qs in c.operations:
                    if name not in ('t','tdg'):skeleton.add(name,*qs)
                actual=Operator(to_qiskit(skeleton)).data@residual
                reference=Statevector.from_instruction(to_qiskit(c)).data
                np.testing.assert_allclose(actual,reference,atol=2e-13,rtol=0)
                for bit in (0,1):
                    expected=sum(abs(v)**2 for ket,v in enumerate(reference) if ket&1==bit)
                    self.assertAlmostEqual(complex(frame.probability(c,{0:bit}).value).real,expected,delta=2e-13)

    def test_negative_diagonal_constraint_selects_nonzero_residual_ket(self):
        c=LargeCircuit(1).add('h',0).add('t',0).add('h',0)
        result=frame.probability(c,{0:1})
        self.assertEqual(result.value,(ONE-INV_SQRT2)*HALF)
        self.assertEqual(result.statistics['x_rank'],0)
        self.assertEqual(result.statistics['accepted_branches'],1)
        self.assertEqual(result.statistics['final_branches'],2)

    def test_imaginary_off_diagonal_projector_phase(self):
        for rotation,expected in (('s',(ONE-INV_SQRT2)*HALF),('sdg',(ONE+INV_SQRT2)*HALF)):
            c=LargeCircuit(1).add('h',0).add('t',0).add(rotation,0).add('h',0)
            result=frame.probability(c,{0:0})
            self.assertEqual(result.value,expected)
            self.assertEqual(result.statistics['pair_candidates'],3)
            self.assertEqual(result.statistics['accepted_branches'],2)

    def test_inverse_phases_exact_cancellation_and_inactive_t_gates(self):
        c=LargeCircuit(1).add('h',0).add('t',0).add('tdg',0)
        result=frame.expectation(c,{0:'X'})
        self.assertEqual(result.value,ONE)
        self.assertEqual(result.statistics['final_branches'],1)
        c=LargeCircuit(1).add('h',0)
        for _ in range(8):c.add('t',0)
        self.assertEqual(frame.expectation(c,{0:'X'}).value,ONE)
        c=LargeCircuit(2056)
        for q in range(128):c.add('t',q)
        result=frame.probability(c,{2055:0},max_branches=1)
        self.assertEqual(result.value,ONE)
        self.assertEqual(result.statistics['peak_branches'],1)

    def test_actual_2056_full_assignment_with_retained_phase(self):
        c=ghz(2056);outcomes={q:0 for q in range(2056)}
        with self.assertRaises(ResourceLimit):clifford_t.probability(c,outcomes)
        result=frame.probability(c,outcomes)
        self.assertEqual(result.value,HALF)
        self.assertEqual(result.statistics['final_branches'],2)
        self.assertEqual(result.statistics['measurement_generators'],2056)
        self.assertTrue(result.statistics['projector_expansion_avoided'])
        self.assertFalse(result.statistics['dense_statevector_constructed'])
        self.assertTrue(result.statistics['sparse_residual_constructed'])
        self.assertEqual(frame.probability(c,{0:1,2055:0}).value,ZERO)

    def test_actual_2056_global_interference_probability(self):
        c=ghz(2056)
        for q in range(2056):c.add('h',q)
        result=frame.probability(c,{q:0 for q in range(2056)})
        self.assertEqual(result.value,(ONE+INV_SQRT2)*Exact(Fraction(1,1<<2056)))

    def test_six_independent_t_gates_and_wide_outcome(self):
        c=LargeCircuit(24)
        for q in range(24):c.add('h',q)
        for q in range(6):c.add('t',q).add('h',q)
        result=frame.probability(c,{q:0 for q in range(24)})
        self.assertEqual(result.value,(ONE+INV_SQRT2)**6*Exact(Fraction(1,1<<24)))
        self.assertEqual(result.statistics['final_branches'],64)
        self.assertEqual(result.statistics['accepted_branches'],1)

    def test_clifford_only_and_empty_observations(self):
        c=LargeCircuit(9).add('h',0)
        for q in range(8):c.add('cx',q,q+1)
        self.assertEqual(frame.probability(c,{q:1 for q in range(9)}).value,
                         stabilizer.probability(c,{q:1 for q in range(9)}).value)
        c=circuit(5,71)
        self.assertEqual(frame.probability(c,{},max_pairs=1).value,ONE)
        self.assertEqual(frame.expectation(c,{}).value,ONE)

    def test_geometry_retains_both_tensor_halves_at_2056(self):
        x={q:'X' for q in range(2056)};y={**x,0:'Y'}
        for phase,sign in (('t',1),('tdg',-1)):
            c=ghz(2056,phase)
            g=geometry(c,[(1,x),(1,y),(1,{0:'Z'})],backend='clifford_frame')
            self.assertEqual(g['dependencies']['rank'],2)
            self.assertEqual(g['complex_gram_rank'],1)
            self.assertEqual(g['curvature'][1][2],INV_SQRT2)
            self.assertEqual(g['curvature'][2][0],sign*INV_SQRT2)
            self.assertTrue(g['full_tensor_reconstruction_exact'])

    def test_resource_guards_and_progress_have_no_fabricated_value(self):
        c=LargeCircuit(2).add('h',0).add('t',0)
        for options in ({'max_branches':1},{'max_work':1},{'max_coefficient_bits':2},{'max_pairs':1}):
            with self.assertRaises(ResourceLimit) as failure:
                frame.probability(c,{0:0},**options)
            self.assertNotIn('value',failure.exception.statistics)
        with self.assertRaises(ResourceLimit):frame.probability(c,{0:0,1:0},max_generators=1)
        with self.assertRaises(ResourceLimit):frame.expectation(c,{0:'X'},max_pairs=1)
        events=[]
        result=frame.probability(c,{},progress=events.append)
        self.assertEqual(result.value,ONE);self.assertEqual(events[-1]['event'],'completed')
        costs=('plan_gates','gate_visits','branch_updates','normalization_terms','row_products','constraint_checks','pair_visits')
        self.assertEqual(result.statistics['work_used'],sum(result.statistics[k] for k in costs))

    def test_public_batch_distribution_geometry_and_simplification(self):
        c=ghz(5).add('r',4).add('r',4)
        d=request(c,[dict(id='law',kind='distribution',qubits=[4,0]),
                     dict(id='tensor',kind='geometry',generators=[dict(paulis={'0':'Z'}),dict(paulis={'4':'Z'})])],
                  simplify='exact')
        r=run_calculation(d)
        self.assertEqual(r['status'],'completed')
        self.assertEqual(r['answers'][0]['normalization'],ONE.to_dict())
        reduced=reduce_circuit(c)
        self.assertEqual(reduced.phase,-ONE)
        self.assertEqual(frame.expectation(c,{q:'X' for q in range(5)}).value,
                         frame.expectation(reduced.circuit,{q:'X' for q in range(5)}).value)

    def test_original_gate_validation_limits_and_no_implicit_fallback(self):
        for name,qs in (('ch',[0,1]),('cs',[0,1]),('ct',[0,1]),('ccx',[0,1,2])):
            c=LargeCircuit(3).add(name,*qs).add(name,*qs)
            with self.assertRaises(ValueError):validate(request(c,[dict(id='id',kind='probability',outcomes={})],simplify='exact'))
            with self.assertRaises(ValueError):frame.probability(c,{})
        with self.assertRaises(TypeError):frame.expectation(object(),{})
        c=ghz(3);d=request(c,[dict(id='id',kind='probability',outcomes={})])
        for key in ('max_terms','max_bond'):
            bad=copy.deepcopy(d);bad['limits']={key:4}
            with self.assertRaises(ValueError):validate(bad)
        bad=copy.deepcopy(d);bad['contraction']='streaming'
        with self.assertRaises(ValueError):validate(bad)
        for options in ({'max_branches':True},{'max_pairs':0},{'max_generators':2057}):
            with self.assertRaises((TypeError,ValueError)):frame.probability(c,{},**options)

    def test_independent_partial_failure_and_whole_batch_timeout(self):
        c=LargeCircuit(1).add('h',0).add('t',0)
        d=request(c,[dict(id='wide',kind='probability',outcomes={'0':0}),
                     dict(id='identity',kind='probability',outcomes={})],limits={'max_pairs':1})
        r=calculate(d)
        self.assertEqual(r['status'],'incomplete')
        self.assertNotIn('value',r['answers'][0])
        self.assertEqual(r['answers'][1]['value']['exact'],ONE.to_dict())
        self.assertEqual(run_calculation(d,timeout_seconds=1e-9)['answers'],[])


if __name__=='__main__':unittest.main()
