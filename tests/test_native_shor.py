import copy
from fractions import Fraction
import importlib.util
import unittest

from native_relational_qc.compact import CompactState
from native_relational_qc.large_register import LargeCircuit
from native_relational_qc.exact import Exact,ONE,ZERO,INV_SQRT2,OMEGA
from native_relational_qc.calculator import calculate,run_calculation
from native_relational_qc.shor import (append_ccx,append_controlled_swap,append_inverse_phase,
    append_inverse_qft,append_mod15_multiplier,build,exact_phase_law,decode,assess)


def apply_basis(circuit,bits):
    state=CompactState(circuit.n_qubits)
    for q in range(circuit.n_qubits):
        if bits&(1<<q):state.apply('x',q)
    for name,qs in circuit.operations:state.apply(name,*qs)
    return state


class ShorTests(unittest.TestCase):
    def test_toffoli_full_exact_basis_action_including_phase(self):
        c=LargeCircuit(3);append_ccx(c,0,1,2)
        for bits in range(8):
            target=bits^(4 if bits&3==3 else 0)
            self.assertEqual(apply_basis(c,bits).amplitude(target),ONE)

    def test_controlled_swap_full_exact_basis_action(self):
        c=LargeCircuit(3);append_controlled_swap(c,0,1,2)
        for bits in range(8):
            target=bits^(6 if bits&1 and bool(bits&2)!=bool(bits&4) else 0)
            self.assertEqual(apply_basis(c,bits).amplitude(target),ONE)

    def test_controlled_phase_clean_workspace_and_dirty_counterexample(self):
        for distance in (1,2):
            c=LargeCircuit(3);append_inverse_phase(c,0,1,distance,clean_ancilla=2)
            for bits in range(4):
                phase=OMEGA**(-2 if distance==1 else -1) if bits==3 else ONE
                state=apply_basis(c,bits)
                self.assertEqual(state.amplitude(bits),phase)
                self.assertEqual(state.probability({2:0}),ONE)
        c=LargeCircuit(3);append_inverse_phase(c,0,1,2,clean_ancilla=2)
        self.assertEqual(apply_basis(c,7).amplitude(7)/apply_basis(c,4).amplitude(4),OMEGA)
        self.assertNotEqual(OMEGA,OMEGA.conjugate())

    def test_inverse_qft_full_exact_matrix_and_phase(self):
        for m in (1,2,3):
            c=LargeCircuit(m+(m==3));append_inverse_qft(c,range(m),clean_ancilla=m if m==3 else None)
            size=1<<m;root=OMEGA**(8//size)
            for x in range(size):
                state=apply_basis(c,x)
                for y in range(size):self.assertEqual(state.amplitude(y),INV_SQRT2**m*root**((-x*y)%size))
                if m==3:self.assertEqual(state.probability({m:0}),ONE)

    def test_mod15_multipliers_every_control_and_work_label(self):
        for multiplier in (1,2,4,8):
            c=LargeCircuit(5);append_mod15_multiplier(c,0,range(1,5),multiplier)
            for control in (0,1):
                for work in range(16):
                    target=(multiplier*work)%15 if control and work<15 else work
                    self.assertEqual(apply_basis(c,control+2*work).amplitude(control+2*target),ONE)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional independent Qiskit reference')
    def test_full_shor_complex_states_against_function_fourier_formula(self):
        import numpy as np
        from qiskit.quantum_info import Statevector
        from native_relational_qc.compact_qiskit import to_qiskit
        cases=[(15,2,2,'rotation15',True),(15,2,3,'rotation15',True),
               (15,2,3,'table',True),(15,7,3,'table',True),(21,2,3,'table',True),
               (15,14,3,'table',True),(15,2,3,'rotation15',False)]
        for n,a,m,oracle,iqft in cases:
            program=build(n,a,precision=m,oracle=oracle,inverse_qft=iqft)
            size=1<<m;root=OMEGA**(8//size)
            expected=[ZERO]*(1<<program.circuit.n_qubits)
            for x in range(size):
                output=pow(a,x,n)
                if iqft:
                    for y in range(size):expected[y+(output<<m)]+=Exact(Fraction(1,size))*root**((-x*y)%size)
                else:expected[x+(output<<m)]=INV_SQRT2**m
            actual=Statevector.from_instruction(to_qiskit(program.circuit)).data
            np.testing.assert_allclose(actual,[complex(v) for v in expected],atol=8e-13,rtol=0)
            for y,value in exact_phase_law(n,a,m,inverse_qft=iqft).items():
                self.assertAlmostEqual(float(value.a)+float(value.b)*2**.5,
                    sum(abs(actual[i])**2 for i in range(len(actual)) if i%(1<<m)==y),delta=8e-13)

    def test_same_low_precision_shor_distribution_on_both_backends(self):
        p=build(15,2,precision=2)
        for backend in ('clifford_frame','jya_frame'):
            result=calculate(p.request(backend));assessment=assess(p,result)
            self.assertEqual(result['status'],'completed')
            self.assertEqual(assessment['policies']['convergents_only']['exact_success_probability'],Exact(Fraction(1,2)).to_dict())
            self.assertEqual(assessment['policies']['convergents_and_doubles']['exact_success_probability'],Exact(Fraction(3,4)).to_dict())

    def test_verified_postprocessing_and_limited_precision_boundary(self):
        self.assertEqual(decode(2,15,2,3)['factors'],[3,5])
        self.assertEqual(decode(4,15,2,3)['status'],'no_nontrivial_factor')
        self.assertEqual(decode(4,15,2,3,double_denominators=True)['factors'],[3,5])
        self.assertEqual(decode(3,21,2,3)['status'],'no_nontrivial_factor')
        result=decode(3,21,2,3,double_denominators=True)
        self.assertEqual(result['factors'],[3,7])
        self.assertTrue(result['attempts'][-1]['period_verified'])
        self.assertEqual(result['attempts'][-1]['candidate_period'],6)
        self.assertEqual(decode(4,15,14,3)['status'],'no_nontrivial_factor')
        self.assertEqual(decode(0,15,2,3)['status'],'no_information')

    def test_no_qft_control_changes_the_distribution(self):
        p=build(15,2,precision=2,inverse_qft=False)
        result=calculate(p.request());assessment=assess(p,result)
        self.assertEqual(assessment['status'],'verified')
        self.assertEqual(set(tuple(v['exact']['coefficients']) for v in result['answers'][0]['probabilities'].values()),{('1/4','0','0','0')})
        self.assertNotEqual(exact_phase_law(15,2,3),exact_phase_law(15,2,3,inverse_qft=False))

    def test_invalid_cases_and_unsupported_precision_fail_explicitly(self):
        for args in ({'modulus':16},{'base':3},{'precision':4},{'precision':True},
                     {'modulus':21},{'base':7},{'oracle':'magic'},{'inverse_qft':'yes'}):
            with self.assertRaises(ValueError):build(**args)
        with self.assertRaises(ValueError):append_inverse_qft(LargeCircuit(5),range(4),clean_ancilla=4)
        with self.assertRaises(ValueError):append_inverse_qft(LargeCircuit(3),range(3))
        with self.assertRaises(ValueError):append_inverse_phase(LargeCircuit(3),0,1,2,clean_ancilla=0)
        with self.assertRaises(ValueError):decode(8,15,2,3)

    def test_failed_calculation_does_not_claim_factors(self):
        p=build();d=p.request();d['limits']={'max_work':1}
        result=calculate(d)
        self.assertEqual(result['status'],'incomplete')
        self.assertEqual(assess(p,result)['status'],'unavailable')
        result=run_calculation(p.request(),timeout_seconds=1e-9)
        self.assertEqual(result['status'],'time_limit')
        self.assertEqual(assess(p,result)['status'],'unavailable')

    def test_assessment_rejects_a_different_circuit_or_readout(self):
        p=build(15,2,precision=1);result=calculate(p.request())
        wrong=copy.deepcopy(result);wrong['circuit_sha256']='bad'
        with self.assertRaises(ValueError):assess(p,wrong)
        wrong=copy.deepcopy(result);wrong['answers'][0]['bitstring_qubits_left_to_right']=[1]
        with self.assertRaises(ValueError):assess(p,wrong)
        wrong=copy.deepcopy(result);wrong['answers'][0]['probabilities'].pop('0')
        with self.assertRaises(ValueError):assess(p,wrong)


if __name__=='__main__':unittest.main()
