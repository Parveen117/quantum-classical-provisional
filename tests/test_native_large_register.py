import copy
from fractions import Fraction
import importlib.util
import random
import unittest

from native_relational_qc.compact import CompactCircuit,ResourceLimit
from native_relational_qc.large_register import LargeCircuit
from native_relational_qc.exact import Exact,ONE,ZERO,INV_SQRT2
from native_relational_qc import stabilizer,clifford_t,observer,factored
from native_relational_qc.pauli_engine import _conjugate,_sign,CLIFFORD_GATES
from native_relational_qc.calculator import calculate,validate,run_calculation
from native_relational_qc.reduction import reduce_circuit
from native_relational_qc.emk_tensor import geometry


def ghz(n,phase=False):
    c=LargeCircuit(n).add('h',0)
    for q in range(n-1):c.add('cx',q,q+1)
    if phase:c.add('t',0)
    return c


def doc(c,backend='stabilizer',queries=None,**options):
    return dict(schema='nrqc-calculator-v1',n_qubits=c.n_qubits,
                operations=[[name,list(qs)] for name,qs in c.operations],backend=backend,
                queries=queries or [dict(id='x',kind='expectation',paulis={str(q):'X' for q in range(c.n_qubits)})],
                **options)


def random_circuit(n,seed,with_t=False):
    rng=random.Random(seed);c=LargeCircuit(n)
    singles=['h','s','sdg','x','y','z','sx','sxdg','r','k','rk']+(['t','tdg'] if with_t else [])
    for _ in range(30):
        if n>1 and rng.randrange(3)==0:
            c.add(rng.choice(('cx','cz','swap')),*rng.sample(range(n),2))
        else:c.add(rng.choice(singles),rng.randrange(n))
    return c


class LargeRegisterTests(unittest.TestCase):
    def test_each_clifford_pauli_image_against_exact_matrices(self):
        from native_relational_qc.observer import _conjugate as reference
        for name in CLIFFORD_GATES:
            n=2 if name in ('cx','cz','swap') else 1
            gate=(name,1,2 if n==2 else 0)
            for x in range(1<<n):
                for z in range(1<<n):
                    nx,nz,p=_conjugate(x,z,(x&z).bit_count()%4,gate)
                    self.assertEqual(reference(name,n,x,z),((nx,nz,Exact(_sign(nx,nz,p))),))

    def test_all_requested_outcomes_random_clifford_against_exact_observer(self):
        for n in range(1,5):
            for seed in range(6):
                c=random_circuit(n,seed)
                for outcome in range(1<<n):
                    assignments={q:(outcome>>q)&1 for q in range(n)}
                    self.assertEqual(stabilizer.probability(c,assignments).value,
                                     observer.probability(c,assignments).value)
                rng=random.Random(seed+100)
                for _ in range(5):
                    paulis={q:rng.choice('IXYZ') for q in range(n)}
                    self.assertEqual(stabilizer.expectation(c,paulis).value,
                                     observer.expectation(c,paulis).value)

    def test_clifford_t_exact_agreement_multiple_phases(self):
        for n in range(1,5):
            for seed in range(8):
                c=random_circuit(n,seed,True)
                for word in ({q:'Y' for q in range(n)},{q:'X' for q in range(n)},{0:'Z'}):
                    self.assertEqual(clifford_t.expectation(c,word).value,observer.expectation(c,word).value)
                for bits in range(1<<min(n,2)):
                    assignment={q:(bits>>q)&1 for q in range(min(n,2))}
                    self.assertEqual(clifford_t.probability(c,assignment).value,observer.probability(c,assignment).value)

    def test_large_ghz_global_correlations_and_full_joint_probability(self):
        c=ghz(2056)
        self.assertEqual(stabilizer.expectation(c,{q:'X' for q in range(2056)}).value,ONE)
        self.assertEqual(stabilizer.expectation(c,{q:'Z' for q in range(2056)}).value,ONE)
        self.assertEqual(stabilizer.expectation(c,{0:'Z'}).value,ZERO)
        self.assertEqual(stabilizer.expectation(c,{0:'Z',2055:'Z'}).value,ONE)
        full=stabilizer.probability(c,{q:0 for q in range(2056)})
        self.assertEqual(full.value,Exact(Fraction(1,2)))
        self.assertEqual(full.statistics['x_rank'],1)
        self.assertEqual(full.statistics['measurement_generators'],2056)
        self.assertEqual(stabilizer.probability(c,{0:0,2055:1}).value,ZERO)

    def test_large_non_clifford_phase_and_geometry(self):
        c=ghz(2056,True)
        x={q:'X' for q in range(2056)};y={**x,0:'Y'}
        for word in (x,y):
            result=clifford_t.expectation(c,word)
            self.assertEqual(result.value,INV_SQRT2)
            self.assertEqual(result.statistics['non_clifford_term_splits'],1)
        g=geometry(c,[(1,x),(1,y),(1,{0:'Z'})],backend='clifford_t')
        self.assertEqual(g['dependencies']['rank'],2)
        self.assertEqual(g['complex_gram_rank'],1)
        self.assertEqual(g['curvature'][1][2],INV_SQRT2)
        self.assertEqual(g['curvature'][2][0],INV_SQRT2)

    def test_large_uniform_output_bit_budget_and_no_enumeration(self):
        c=LargeCircuit(2056)
        for q in range(2056):c.add('h',q)
        answer=stabilizer.probability(c,{q:0 for q in range(2056)})
        self.assertEqual(answer.value,Exact(Fraction(1,1<<2056)))
        self.assertEqual(answer.statistics['x_rank'],2056)
        self.assertFalse(answer.statistics['statevector_constructed'])
        with self.assertRaises(ResourceLimit):
            stabilizer.probability(c,{q:0 for q in range(2056)},max_coefficient_bits=2048)

    def test_global_phase_and_reducer_preserve_observations_and_ir(self):
        c=ghz(2056).add('r',2055).add('r',2055)
        reduced=reduce_circuit(c)
        self.assertIsInstance(reduced.circuit,LargeCircuit)
        self.assertEqual(reduced.phase,-ONE)
        word={q:'X' for q in range(2056)}
        self.assertEqual(stabilizer.expectation(c,word).value,
                         stabilizer.expectation(reduced.circuit,word).value)

    def test_no_recursive_state_or_implicit_old_backend_extension(self):
        c=LargeCircuit(2056)
        with self.assertRaises(ValueError):c.state()
        with self.assertRaises(ValueError):CompactCircuit(2056)
        with self.assertRaises(ValueError):observer.expectation(c,{0:'Z'})
        with self.assertRaises(ValueError):factored.expectation(c,{0:'Z'})
        with self.assertRaises(ValueError):LargeCircuit(2057)

    def test_backend_eligibility_and_gate_order(self):
        for name,qs in [('ch',(0,1)),('cs',(0,1)),('ct',(0,1)),('ccx',(0,1,2))]:
            c=LargeCircuit(3).add(name,*qs)
            for backend in ('stabilizer','clifford_t'):
                with self.assertRaises(ValueError):validate(doc(c,backend))
        with self.assertRaises(ValueError):validate(doc(ghz(2,True)))
        x=LargeCircuit(1).add('h',0).add('t',0).add('h',0)
        self.assertEqual(clifford_t.expectation(x,{0:'Z'}).value,INV_SQRT2)
        y=LargeCircuit(1).add('h',0).add('h',0).add('t',0)
        self.assertEqual(clifford_t.expectation(y,{0:'Z'}).value,ONE)

    def test_exact_cancellation_and_t_inverse(self):
        c=LargeCircuit(1).add('h',0)
        for _ in range(8):c.add('t',0)
        self.assertEqual(clifford_t.expectation(c,{0:'X'}).value,ONE)
        c.add('t',0).add('tdg',0)
        self.assertEqual(clifford_t.expectation(c,{0:'Y'}).value,ZERO)

    def test_all_resource_guards_fail_without_fabricated_values(self):
        c=ghz(3,True)
        for options in ({'max_terms':1},{'max_work':1}):
            with self.assertRaises(ResourceLimit) as failure:
                clifford_t.expectation(c,{q:'X' for q in range(3)},**options)
            self.assertNotIn('value',failure.exception.statistics)
        with self.assertRaises(ResourceLimit):clifford_t.probability(c,{0:0,1:0,2:0},max_terms=4)
        with self.assertRaises(ResourceLimit):stabilizer.probability(ghz(3),{0:0,1:0},max_generators=1)
        events=[]
        result=stabilizer.expectation(ghz(3),{0:'Z'},progress=events.append)
        self.assertEqual(result.value,ZERO);self.assertEqual(events[-1]['event'],'completed')

    def test_calculator_large_batch_distribution_and_explicit_options(self):
        c=ghz(2056,True)
        queries=[dict(id='global',kind='expectation',paulis={str(q):'X' for q in range(2056)}),
                 dict(id='ends',kind='distribution',qubits=[2055,0])]
        d=doc(c,'clifford_t',queries,simplify='exact')
        report=run_calculation(d,timeout_seconds=20)
        self.assertEqual(report['status'],'completed')
        self.assertEqual(report['answers'][0]['value']['exact'],INV_SQRT2.to_dict())
        self.assertEqual(report['answers'][1]['normalization'],ONE.to_dict())
        bad=copy.deepcopy(d);bad['contraction']='streaming'
        with self.assertRaises(ValueError):validate(bad)
        bad=copy.deepcopy(d);bad['limits']={'max_generators':4}
        with self.assertRaises(ValueError):validate(bad)
        bad=doc(ghz(3));bad['limits']={'max_terms':4}
        with self.assertRaises(ValueError):validate(bad)
        for backend in ('factored','observer'):
            with self.assertRaises(ValueError):validate(doc(c,backend))

    def test_partial_query_failure_and_whole_batch_timeout(self):
        d=doc(ghz(2,True),'clifford_t',[
            dict(id='phase',kind='expectation',paulis={'0':'X','1':'X'}),
            dict(id='identity',kind='expectation',paulis={})],limits={'max_terms':1})
        report=calculate(d)
        self.assertEqual(report['status'],'incomplete')
        self.assertNotIn('value',report['answers'][0])
        self.assertEqual(report['answers'][1]['value']['exact'],ONE.to_dict())
        self.assertEqual(run_calculation(d,timeout_seconds=1e-9)['answers'],[])

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional Qiskit reference')
    def test_independent_qiskit_statevector_random_circuits(self):
        from qiskit.quantum_info import Statevector,Pauli
        from native_relational_qc.compact_qiskit import to_qiskit
        for n in (2,4,6):
            for seed in (71,117,2056):
                c=random_circuit(n,seed,True)
                state=Statevector.from_instruction(to_qiskit(c))
                rng=random.Random(seed)
                for _ in range(4):
                    word={q:rng.choice('IXYZ') for q in range(n)}
                    reference=state.expectation_value(Pauli(''.join(word[q] for q in reversed(range(n)))))
                    self.assertAlmostEqual(complex(clifford_t.expectation(c,word).value),reference,delta=2e-13)
                p=sum(abs(state.data[j])**2 for j in range(1<<n) if j&3==1)
                self.assertAlmostEqual(complex(clifford_t.probability(c,{0:1,1:0}).value).real,p,delta=2e-13)


if __name__=='__main__':unittest.main()
