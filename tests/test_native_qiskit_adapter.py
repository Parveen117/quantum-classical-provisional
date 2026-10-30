"""Independent Qiskit comparisons, including negative controls and ISA compilation."""
import importlib.util
import unittest
import numpy as np
from numpy.testing import assert_allclose

from native_relational_qc import Circuit, RelationalState, I, K, R, gate
from native_relational_qc.examples import bell, ghz, bernstein_vazirani, grover_11, order_memory
from native_relational_qc.qiskit_adapter import from_qiskit, to_qiskit, compare_qiskit, compile_for_target

HAS_QISKIT = importlib.util.find_spec("qiskit") is not None


@unittest.skipUnless(HAS_QISKIT, "optional Qiskit SDK not installed")
class QiskitAdapterTests(unittest.TestCase):
    def assert_matches(self, qc):
        result = compare_qiskit(qc)
        self.assertTrue(result["passed"], result)
        self.assertIsNone(result["hardware_job_id"])

    def test_independent_standard_gate_semantics(self):
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import Operator
        for name in ("id", "h", "x", "y", "z", "s", "sdg", "t", "tdg", "sx", "cx", "cz", "swap"):
            n = 2 if name in {"cx", "cz", "swap"} else 1
            qc = QuantumCircuit(n)
            getattr(qc, name)(*range(n))
            native = Circuit(n).add(name, *range(n))
            assert_allclose(native.operations[0].matrix, Operator(qc).data, atol=1e-14)
        for name in ("rx", "ry", "rz", "rzz", "p"):
            n = 2 if name == "rzz" else 1
            qc = QuantumCircuit(n)
            getattr(qc, name)(0.731, *range(n))
            assert_allclose(gate(name, 0.731), Operator(qc).data, atol=1e-14)

    def test_native_r_bridge_and_controlled_phase(self):
        from qiskit.circuit.library import RYGate
        from qiskit.quantum_info import Operator
        assert_allclose(R, Operator(RYGate(np.pi)).data, atol=1e-14)
        for phase in (0.3, np.pi):
            circuit = Circuit(2).add("h", 0).control(np.exp(1j * phase) * K, 0, 1).add("h", 0)
            self.assert_matches(to_qiskit(circuit))

    def test_analytic_program_roundtrips(self):
        for circuit in (bell(), bell("XX"), bell("YY"), bell("ZX"), ghz(5),
                        bernstein_vazirani("1011"), grover_11(), order_memory(), order_memory(True)):
            self.assert_matches(to_qiskit(circuit))

    def test_seeded_mixed_circuits(self):
        from qiskit import QuantumCircuit
        rng = np.random.default_rng(117)
        # 60 independent circuits, 1--6 qubits, 24 gates each; deterministic inputs.
        for n in range(1, 7):
            for _ in range(10):
                qc = QuantumCircuit(n)
                qc.global_phase = float(rng.uniform(-np.pi, np.pi))
                for step in range(24):
                    q = int(rng.integers(n))
                    if n > 1 and step % 3 == 0:
                        a, b = map(int, rng.choice(n, 2, replace=False))
                        if step % 2:
                            qc.ecr(a, b)
                        else:
                            qc.cx(a, b)
                    elif step % 4 == 0:
                        qc.sx(q)
                    else:
                        getattr(qc, ("rx", "ry", "rz")[step % 3])(float(rng.normal()), q)
                self.assert_matches(qc)

    def test_custom_unitary_and_permuted_qargs(self):
        from qiskit import QuantumCircuit
        rng = np.random.default_rng(13)
        raw = rng.normal(size=(8, 8)) + 1j * rng.normal(size=(8, 8))
        u, _ = np.linalg.qr(raw)
        for qargs in ([0, 2, 3], [3, 0, 1], [1, 3, 2]):
            qc = QuantumCircuit(4)
            qc.h(1)
            qc.unitary(u, qargs)
            self.assert_matches(qc)

    def test_partial_measurement_register_order(self):
        from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
        qc = QuantumCircuit(QuantumRegister(3, "q"), ClassicalRegister(2, "a"), ClassicalRegister(2, "b"))
        qc.x(0)
        qc.h(1)
        qc.measure(0, 2)
        qc.measure(1, 0)
        qc.barrier()
        self.assert_matches(qc)
        p = from_qiskit(qc).probabilities()
        self.assertAlmostEqual(p["0100"], 0.5)
        self.assertAlmostEqual(p["0101"], 0.5)

    def test_fails_closed_on_dynamic_nonunitary_and_unbound(self):
        from qiskit import QuantumCircuit
        from qiskit.circuit import Parameter
        bad = []
        reset = QuantumCircuit(1)
        reset.reset(0)
        bad.append(reset)
        mid = QuantumCircuit(1, 1)
        mid.h(0)
        mid.measure(0, 0)
        mid.x(0)
        bad.append(mid)
        param = QuantumCircuit(1)
        param.rz(Parameter("theta"), 0)
        bad.append(param)
        timed = QuantumCircuit(1)
        timed.delay(5, 0)
        bad.append(timed)
        initialize = QuantumCircuit(1)
        initialize.initialize([1, 0], 0)
        bad.append(initialize)
        conditional = QuantumCircuit(1, 1)
        with conditional.if_test((conditional.clbits[0], 1)):
            conditional.x(0)
        bad.append(conditional)
        for qc in bad:
            with self.assertRaises(ValueError):
                from_qiskit(qc)

    def test_bound_parameters_are_accepted(self):
        from qiskit import QuantumCircuit
        from qiskit.circuit import Parameter
        theta = Parameter("theta")
        qc = QuantumCircuit(1)
        qc.ry(theta, 0)
        self.assert_matches(qc.assign_parameters({theta: 0.47}))

    def test_explicit_global_phase_gate(self):
        from qiskit import QuantumCircuit
        from qiskit.circuit.library import GlobalPhaseGate
        qc = QuantumCircuit(1)
        qc.h(0)
        qc.append(GlobalPhaseGate(0.71), [])
        self.assert_matches(qc)

    def test_labels_cannot_override_matrix_semantics(self):
        circuit = Circuit(1).append(gate("x"), [0], name="h")
        self.assert_matches(to_qiskit(circuit))
        self.assertAlmostEqual(from_qiskit(to_qiskit(circuit)).probabilities()["1"], 1)

    def test_offline_hardware_target_compilation(self):
        from qiskit.providers.fake_provider import GenericBackendV2
        for two_qubit_gate in ("cx", "cz", "ecr"):
            target = GenericBackendV2(3, basis_gates=["rz", "sx", "x", two_qubit_gate],
                                      coupling_map=[[0, 1], [1, 0], [1, 2], [2, 1]], seed=7).target
            circuit = ghz(3)
            isa = compile_for_target(circuit, target, seed_transpiler=117)
            for item in isa.data:
                if item.operation.name != "barrier":
                    qargs = tuple(isa.find_bit(q).index for q in item.qubits)
                    self.assertTrue(target.instruction_supported(operation_name=item.operation.name, qargs=qargs))
            self.assert_matches(isa)
            assert_allclose(list(from_qiskit(isa).probabilities().values()),
                            list(circuit.probabilities().values()), atol=1e-10)
            # An asymmetric state exposes a wrong physical/logical wire mapping.
            asymmetric = (Circuit(3).add("x", 0).add("h", 2)
                          .add("cx", 2, 1).add("ry", 0, theta=0.31).measure_all())
            isa_asymmetric = compile_for_target(asymmetric, target, seed_transpiler=117)
            assert_allclose(list(from_qiskit(isa_asymmetric).probabilities().values()),
                            list(asymmetric.probabilities().values()), atol=1e-10)

    def test_phase_erasure_negative_control(self):
        coherent = Circuit(1).add("h", 0).add("s", 0)
        lost_phase = RelationalState(np.abs(coherent.state().amplitudes))
        # Same Z probabilities conceal a phase error, but an X observer detects it.
        observe = Circuit(1).add("h", 0)
        p = observe.probabilities(coherent.state())["0"]
        wrong = observe.probabilities(lost_phase)["0"]
        self.assertAlmostEqual(p, 0.5)
        self.assertAlmostEqual(wrong, 1)

    def test_compiler_needs_explicit_target(self):
        with self.assertRaises(ValueError):
            compile_for_target(bell(), None)


if __name__ == "__main__":
    unittest.main()
