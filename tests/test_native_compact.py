"""Exact identities, independent circuit comparisons, resource failure controls."""
from fractions import Fraction
import importlib.util
import random
import unittest
import numpy as np
from numpy.testing import assert_allclose

from native_relational_qc.exact import Exact, ZERO, ONE, IMAG, HALF, INV_SQRT2, OMEGA, exact_gate
from native_relational_qc.compact import CompactCircuit, CompactState, ResourceLimit
from native_relational_qc.compact_qiskit import to_qiskit, from_qiskit


class ExactArithmeticTests(unittest.TestCase):
    def test_field_identities(self):
        self.assertEqual(IMAG**2, -ONE)
        self.assertEqual(INV_SQRT2**2, HALF)
        self.assertEqual(OMEGA**8, ONE)
        self.assertEqual(OMEGA.norm2(), ONE)
        self.assertEqual(OMEGA**-1, OMEGA.conjugate())

    def test_nontrivial_inverse_and_distributivity(self):
        a, b, c = Exact(1, 2, 3, 4), Exact(3, -1, 2, 1), Exact(-2, 1, 0, -1)
        self.assertEqual(a/a, ONE)
        self.assertEqual(a*a.inverse(), ONE)
        self.assertEqual((a*b)/b, a)
        self.assertEqual(a*(b+c), a*b+a*c)
        self.assertEqual(a.conjugate()*a, a.norm2())
        self.assertAlmostEqual(abs(complex(a*b) - complex(a)*complex(b)), 0)

    def test_exact_gate_unitarity(self):
        for name in ("id", "x", "y", "z", "r", "k", "rk", "h", "s", "sdg", "t", "tdg", "sx", "sxdg"):
            matrix = exact_gate(name)
            for i in range(2):
                for j in range(2):
                    value = sum((matrix[k][i].conjugate()*matrix[k][j] for k in range(2)), ZERO)
                    self.assertEqual(value, ONE if i == j else ZERO)

    def test_float_and_zero_inverse_rejected(self):
        for value in (0.5, float("nan"), 1j, True):
            with self.assertRaises(TypeError):
                Exact(value)
        with self.assertRaises(ZeroDivisionError):
            ZERO.inverse()


class CompactTests(unittest.TestCase):
    def test_bell_exact_probabilities(self):
        state = CompactCircuit(2).add("h",0).add("cx",0,1).state()
        self.assertEqual(state.probability(), ONE)
        self.assertEqual(state.probability({0:0,1:0}), HALF)
        self.assertEqual(state.probability({0:0,1:1}), ZERO)
        self.assertEqual(state.amplitude("11"), INV_SQRT2)
        self.assertEqual(state.expectation_z([0,1]), ONE)
        self.assertEqual(state.expectation_z([0]), ZERO)

    def test_phase_not_erased(self):
        state = CompactCircuit(1).add("h",0).add("t",0).add("h",0).state()
        expected = Exact(Fraction(1,2), Fraction(1,4))
        self.assertEqual(state.probability({0:0}), expected)
        self.assertEqual(state.probability({0:1}), ONE-expected)
        self.assertEqual(state.expectation_z([0]), INV_SQRT2)

    def test_native_order_sign_retained(self):
        rk = CompactCircuit(1).add("k",0).add("r",0).state()
        kr = CompactCircuit(1).add("r",0).add("k",0).state()
        self.assertEqual(rk.amplitude(1), ONE)
        self.assertEqual(kr.amplitude(1), -ONE)
        self.assertNotEqual(rk.fingerprint(), kr.fingerprint())

    def test_inverse_restores_canonical_graph(self):
        state = CompactState(3)
        original = state.fingerprint()
        for name, qs in (("h",(1,)),("t",(1,)),("cx",(1,0)),("ccx",(0,1,2))):
            state.apply(name,*qs)
        for name, qs in (("ccx",(0,1,2)),("cx",(1,0)),("tdg",(1,)),("h",(1,))):
            state.apply(name,*qs)
        self.assertEqual(state.fingerprint(), original)
        self.assertEqual(state.stats()["live_nodes"], 3)

    def test_large_superposition_and_nonclifford_phase(self):
        state = CompactState(64)
        for q in range(64):
            state.apply("h",q).apply("t",q)
        self.assertEqual(state.stats()["live_nodes"], 64)
        self.assertEqual(state.probability({0:1,63:0}), Exact(Fraction(1,4)))
        self.assertEqual(state.amplitude("0"*64), Exact(Fraction(1,2**32)))
        with self.assertRaises(ResourceLimit):
            state.to_dense()

    def test_large_ghz_phase_and_return(self):
        circuit = CompactCircuit(64).add("h",0)
        for q in range(1,64):
            circuit.add("cx",0,q)
        state = circuit.add("t",0).state()
        self.assertEqual(state.stats()["live_nodes"], 127)
        self.assertEqual(state.probability({0:1,63:0}), ZERO)
        self.assertEqual(state.amplitude("1"*64), INV_SQRT2*OMEGA)
        for q in reversed(range(1,64)):
            state.apply("cx",0,q)
        state.apply("h",0)
        self.assertEqual(state.probability({0:0}), Exact(Fraction(1,2),Fraction(1,4)))

    def test_control_target_orders_and_toffoli(self):
        for control,target in ((0,2),(2,0),(1,2),(2,1)):
            state=CompactState(3).apply("x",control).apply("cx",control,target)
            self.assertEqual(state.amplitude((1<<control)+(1<<target)), ONE)
        state=CompactState(3).apply("x",0).apply("x",2).apply("ccx",2,0,1)
        self.assertEqual(state.amplitude(7), ONE)

    def test_transactional_node_budget(self):
        state=CompactState(5,max_nodes=5)
        before=state.fingerprint()
        with self.assertRaises(ResourceLimit):
            state.apply("h",0)
        self.assertEqual(state.fingerprint(),before)
        self.assertEqual(state.probability(),ONE)
        self.assertEqual(state.stats()["live_nodes"],5)

    def test_transactional_work_budget(self):
        state=CompactState(5,max_work=5)
        before=state.fingerprint()
        with self.assertRaises(ResourceLimit):
            state.apply("h",0)
        self.assertEqual(state.fingerprint(),before)

    def test_transactional_coefficient_budget(self):
        state=CompactState(8,max_coefficient_bits=4)
        failed=False
        for q in range(8):
            before=state.fingerprint()
            try:state.apply('h',q)
            except ResourceLimit:
                self.assertEqual(state.fingerprint(),before)
                failed=True
                break
        self.assertTrue(failed)

    def test_invalid_gate_query_and_dense_limit(self):
        state=CompactState(3)
        for name,qs in (("rx",(0,)),("cx",(0,0)),("x",(3,)),("swap",(1,))):
            with self.assertRaises(ValueError):
                state.apply(name,*qs)
        for assignments in ({-1:0},{0:2},{True:1}):
            with self.assertRaises(ValueError):
                state.probability(assignments)
        with self.assertRaises(ValueError):
            state.amplitude("01")


@unittest.skipUnless(importlib.util.find_spec("qiskit"), "optional Qiskit SDK not installed")
class CompactQiskitTests(unittest.TestCase):
    def test_named_gate_export_and_independent_reference(self):
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import Statevector
        for name in ("h","x","y","z","s","sdg","t","tdg","sx","sxdg"):
            qc=QuantumCircuit(3)
            qc.h(0)
            qc.cx(0,2)
            getattr(qc,name)(2)
            native=from_qiskit(qc).state()
            assert_allclose(native.to_dense(),Statevector.from_instruction(qc).data,atol=1e-13)

    def test_seeded_nonclifford_circuits(self):
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import Statevector
        rng=random.Random(8817)
        for n in range(1,7):
            for trial in range(6):
                qc=QuantumCircuit(n)
                for step in range(20):
                    if n>1 and step%3==0:
                        a,b=rng.sample(range(n),2)
                        getattr(qc,rng.choice(("cx","cz","ch")))(a,b)
                    else:
                        getattr(qc,rng.choice(("h","t","tdg","x","y","s","sx")))(rng.randrange(n))
                native=from_qiskit(qc).state()
                reference=Statevector.from_instruction(qc)
                assert_allclose(native.to_dense(),reference.data,atol=2e-13)
                self.assertEqual(native.probability(),ONE)
                self.assertAlmostEqual(complex(native.probability({0:1})).real,
                                       float(reference.probabilities([0])[1]),places=12)

    def test_controlled_nonclifford_and_native_operations(self):
        from qiskit.quantum_info import Statevector
        circuit=CompactCircuit(4).add("h",0).add("h",2).add("ct",0,2)
        circuit.add("ccx",0,2,3).add("swap",1,3).add("r",0).add("k",2)
        assert_allclose(circuit.state().to_dense(),Statevector.from_instruction(to_qiskit(circuit)).data,atol=1e-13)

    def test_import_does_not_guess_float_or_name(self):
        from qiskit import QuantumCircuit
        from qiskit.circuit.library import UnitaryGate, XGate
        bad=[]
        qc=QuantumCircuit(1); qc.rz(np.pi/3,0); bad.append(qc)
        qc=QuantumCircuit(1); qc.global_phase=0.1; bad.append(qc)
        qc=QuantumCircuit(1,1); qc.measure(0,0); bad.append(qc)
        qc=QuantumCircuit(1); qc.append(UnitaryGate(np.eye(2),label="h"),[0]); bad.append(qc)
        qc=QuantumCircuit(2); qc.append(XGate().control(ctrl_state=0),[0,1]); bad.append(qc)
        for qc in bad:
            with self.assertRaises(ValueError):
                from_qiskit(qc)


if __name__=="__main__":
    unittest.main()
