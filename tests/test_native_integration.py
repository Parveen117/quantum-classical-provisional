"""Integration contracts: exact phase transport, shared budgets and certificates."""
from fractions import Fraction as Q
import importlib.util
import math
from pathlib import Path
import random
import unittest

from native_relational_qc.calculator import calculate, validate
from native_relational_qc.cyclotomic_pow2 import field_of_order
from native_relational_qc.phase_backend import PowerPhaseCircuit, prepare
from native_relational_qc import openqasm


def request(c,**kwargs):
    return dict(schema='nrqc-calculator-v1',backend='cyclotomic_pow2',n_qubits=c.n_qubits,
        operations=[[n,list(qs)] for n,qs in c.operations],
        queries=[dict(id='p',kind='probability',outcomes={'0':1}),
                 dict(id='x',kind='expectation',paulis={'0':'X'}),
                 dict(id='d',kind='distribution',qubits=[0])],**kwargs)


class ExactInteropTests(unittest.TestCase):
    def test_all_phase_orders_qasm_roundtrip(self):
        for bits in range(1,13):
            k=1<<bits;c=PowerPhaseCircuit(2,max(8,k)).add('h',0).add('h',1)
            for prefix,qs in (('',(0,)),('c',(0,1))):
                c.add(f'{prefix}p{k}',*qs).add(f'{prefix}p{k}dg',*qs)
            back=openqasm.loads(openqasm.dumps(c))
            self.assertEqual(c.operations,back.operations)
            self.assertEqual(prepare(c).amplitudes,prepare(back).amplitudes)

    def test_symbolic_rotations_retain_full_operator_phase(self):
        for expr,n,d in [('pi/4',1,8),('-3*pi/16',-3,32),('2*pi',1,1),('0',0,1)]:
            for bit in (0,1):
                text='OPENQASM 2.0; qreg q[1]; '+('x q[0];' if bit else '')+f'rz({expr}) q[0];'
                c=openqasm.loads(text);state=prepare(c).amplitudes
                turns=Q(n,d)*(1 if bit else -1)/2;F=field_of_order(c.order)
                self.assertEqual(state,{bit:F.root(int(turns*c.order))})
        for expr in ('pi/3','0.1','pi/4096','pi+1','sin(pi)','pi*pi','pi/0'):
            with self.assertRaises(ValueError):openqasm.loads(f'OPENQASM 2.0; qreg q[1]; rz({expr}) q[0];')

    @unittest.skipUnless(importlib.util.find_spec('qiskit'),'optional Qiskit')
    def test_qiskit_phase_and_rz_roundtrip(self):
        import numpy as np
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import Operator
        from native_relational_qc.compact_qiskit import to_qiskit,from_qiskit
        for bits in range(1,13):
            k=1<<bits
            c=PowerPhaseCircuit(2,max(8,k)).add('h',0).add(f'p{k}',0).add(f'cp{k}dg',0,1)
            back=from_qiskit(to_qiskit(c))
            self.assertEqual(back.operations,c.operations)
        for angle in (math.pi/4,-3*math.pi/16,2*math.pi):
            qc=QuantumCircuit(1);qc.rz(angle,0)
            np.testing.assert_allclose(Operator(to_qiskit(from_qiskit(qc))).data,Operator(qc).data,atol=1e-14)
        for angle in (math.pi/3,0.1,np.nextafter(math.pi/4,math.inf)):
            qc=QuantumCircuit(1);qc.rz(angle,0)
            with self.assertRaises(ValueError):from_qiskit(qc)

    def test_rejects_unsupported_qasm(self):
        for text in ('OPENQASM 3.0; qubit q;', 'OPENQASM 2.0; qreg q[1]; measure q[0];',
                     'OPENQASM 2.0; qreg q[1]; u1(pi/4) q[1];',
                     'OPENQASM 2.0; qreg q[2]; cu1(pi/4) q[0],q[0];'):
            with self.assertRaises(ValueError):openqasm.loads(text)


class SharedExecutionTests(unittest.TestCase):
    def test_parallel_matches_serial_and_whole_batch_budget(self):
        c=PowerPhaseCircuit(3,128).add('h',0).add('p128',0).add('cx',0,2).add('h',0)
        serial=calculate(request(c));parallel=calculate(request(c,readout_workers=3))
        for a,b in zip(serial['answers'],parallel['answers']):
            a.pop('execution_seconds');b.pop('execution_seconds');self.assertEqual(a,b)
        self.assertEqual(serial['statistics'],parallel['statistics'])
        used=serial['statistics']['work_used']
        for workers in (1,3):
            ok=calculate(request(c,readout_workers=workers,limits={'max_work':used}))
            failed=calculate(request(c,readout_workers=workers,limits={'max_work':used-1}))
            self.assertEqual(ok['status'],'completed')
            self.assertEqual(failed['answers'],[])
            self.assertEqual(failed['statistics']['work_used'],used)

    def test_branch_ceiling_is_explicit_and_only_flat(self):
        c=PowerPhaseCircuit(17,8)
        for q in range(17):c.add('h',q)
        # Exercise actual support beyond the old ceiling, not just validation.
        state=prepare(c,max_branches=131072,max_work=10_000_000)
        self.assertEqual(len(state.amplitudes),131072)
        self.assertEqual(state.probability({0:1}),field_of_order(8)(Q(1,2)))
        doc=request(c,limits={'max_branches':131072})
        validate(doc)
        with self.assertRaises(ValueError):validate(dict(doc,backend='cyclotomic64'))
        with self.assertRaises(ValueError):validate(dict(doc,limits={'max_branches':1048577}))

    def test_sparse_dense_and_wide_product_against_integer_reference(self):
        rng=random.Random(3010);F=field_of_order(256)
        for dense in (False,True):
            for wide in (False,True):
                a=[rng.randrange(-5,6)*(2**80 if wide else 1) if dense or i%13==0 else 0 for i in range(F.N)]
                b=[rng.randrange(-3,4) if i%11==0 else 0 for i in range(F.N)]
                ref=[0]*F.N
                for i,x in enumerate(a):
                    for j,y in enumerate(b):ref[(i+j)%F.N]+=x*y*(1 if i+j<F.N else -1)
                self.assertEqual(F._build(a,3)*F._build(b,7),F._build(ref,21))


class LedgerCertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from native_relational_qc.certify import certify
        cls.report=certify()

    def test_derived_numbers_enclosures_and_negative_controls(self):
        r=self.report
        self.assertEqual(r['status'],'certified');self.assertTrue(all(r['negative_controls'].values()))
        self.assertEqual(r['purification']['fidelity']['rational'],'841/932')
        self.assertEqual(r['readout_bound']['first_order_coefficient']['rational'],'5/2')
        self.assertTrue(r['claim_checks']['readout_bound_at_declared_point'])
        bound=r['readout_bound']
        self.assertGreaterEqual(Q(bound['margin_below_declared_bound']['rational']),0)
        self.assertLessEqual(Q(bound['coefficient_at_declared_point']['rational']),Q(14,5))
        for row in [r['fusion']['success'],r['purification']['fidelity'],*r['source']['weights'],r['readout_bound']['total_upper_bound']]:
            bounds=row['decimal_enclosure'];exact=Q(row['rational'])
            self.assertLessEqual(Q(bounds['lower']),exact);self.assertGreaterEqual(Q(bounds['upper']),exact)

    def test_wrong_claim_is_rejected(self):
        from native_relational_qc.certify import certify,EXPECTED
        report=certify(claims=dict(EXPECTED,purification_fidelity='9/10'))
        self.assertEqual(report['status'],'failed');self.assertFalse(report['claim_checks']['purification_fidelity'])

    def test_violated_readout_bound_is_not_certified(self):
        from unittest.mock import patch
        from native_relational_qc.certify import certify
        from phase_seam_foundation.cluster_noise import first_order_error
        def excessive_error(*args,**kwargs):
            result=dict(first_order_error(*args,**kwargs))
            result['first_order']=3*result['double_fraction']
            return result
        with patch('phase_seam_foundation.cluster_noise.first_order_error',side_effect=excessive_error):
            report=certify()
        self.assertEqual(report['status'],'failed')
        self.assertFalse(report['claim_checks']['readout_bound_at_declared_point'])
