import importlib.util
import io
import json
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from fractions import Fraction
from pathlib import Path

from native_relational_qc.__main__ import main
from native_relational_qc.compact import CompactCircuit
from native_relational_qc.exact import ONE
from native_relational_qc.openqasm import loads
from native_relational_qc.panini_sandhi import join, sandhi_oracle, search, search_circuit


# Independent grammatical reference, rows = left and columns = right.
VOWELS = ("i", "ī", "u", "ū")
TABLE = (("ī", "ī", "yu", "yū"),
         ("ī", "ī", "yu", "yū"),
         ("vi", "vī", "ū", "ū"),
         ("vi", "vī", "ū", "ū"))
CODES = {"ī": 0b000, "ū": 0b010, "vi": 0b100, "vī": 0b101, "yu": 0b110, "yū": 0b111}


class PaniniSandhiTests(unittest.TestCase):
    def test_all_pairs_on_every_initial_output_word(self):
        oracle = sandhi_oracle()
        self.assertEqual(oracle.circuit.n_qubits, 7)
        self.assertEqual(oracle.scratch, ())
        self.assertEqual(Counter(name for name, _ in oracle.circuit.operations), {"cx": 3, "ccx": 2})
        for left, row in enumerate(TABLE):
            for right, surface in enumerate(row):
                word = 4 * left + right
                _, forward = join(VOWELS[left], VOWELS[right])
                self.assertEqual(forward["surface"], surface)
                self.assertEqual(forward["rule"], "6.1.101" if surface in ("ī", "ū") else "6.1.77")
                for initial_output in range(8):
                    circuit = CompactCircuit(7)
                    initial = word | (initial_output << 4)
                    for wire in range(7):
                        if initial & (1 << wire):
                            circuit.add("x", wire)
                    oracle.append_to(circuit)
                    expected = word | ((initial_output ^ CODES[surface]) << 4)
                    self.assertEqual(circuit.state().amplitude(expected), ONE,
                                     (left, right, initial_output))

    def test_inverse_restores_relative_phases(self):
        circuit = CompactCircuit(7)
        for wire in range(7):
            circuit.add("h", wire)
        circuit.add("t", 2).add("s", 4).add("cz", 1, 6)
        before = circuit.state()
        oracle = sandhi_oracle()
        oracle.append_to(circuit)
        after = circuit.state()
        for word in range(128):
            surface = TABLE[(word >> 2) & 3][word & 3]
            self.assertEqual(after.amplitude(word ^ (CODES[surface] << 4)), before.amplitude(word))
        oracle.append_to(circuit, inverse=True)
        self.assertEqual(circuit.state().fingerprint(), before.fingerprint())

    def test_reverse_search_distributions_for_all_six_surfaces(self):
        for target in CODES:
            circuit, report = search(target)
            self.assertEqual(circuit.n_qubits, 7)
            self.assertEqual(report["clean_workspace_probability"], "1")
            merged = target in ("ī", "ū")
            self.assertEqual(report["uniform_matching_probability"], "1/4" if merged else "1/8")
            self.assertEqual(report["matching_probability"], "1" if merged else "25/32")
            expected_pairs = [(left, right) for left in VOWELS for right in VOWELS]
            self.assertEqual([(row["left"], row["right"]) for row in report["candidates"]], expected_pairs)
            for index, candidate in enumerate(report["candidates"]):
                wanted = TABLE[index // 4][index % 4] == target
                self.assertEqual(candidate["matches"], wanted)
                if merged:
                    probability = Fraction(1, 4) if wanted else Fraction(0)
                else:
                    probability = Fraction(25 if wanted else 1, 64)
                self.assertEqual(Fraction(candidate["probability"]), probability)

    def test_command_script_input_and_openqasm_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            filename = Path(temp) / "surface.qasm"
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["panini-sandhi", "search", "यू", "--qasm", str(filename)]), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["surface"], "yū")
            self.assertIsNone(report["hardware_job_id"])
            replay = loads(filename.read_text())
            self.assertEqual(replay.operations, search_circuit("yū").operations)
        for vowel in ("ई", "i\u0304"):
            self.assertEqual(join(vowel, "उ")[1]["surface"], "yu")
        for args in (["join", "a", "i"], ["search", "ya"]):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
                main(["panini-sandhi", *args])
            self.assertEqual(exc.exception.code, 2)

    @unittest.skipUnless(importlib.util.find_spec("qiskit"), "optional independent Qiskit statevector")
    def test_qiskit_openqasm_complex_amplitudes(self):
        from qiskit import qasm2
        from qiskit.quantum_info import Statevector
        from native_relational_qc.openqasm import dumps

        for target in CODES:
            circuit = search_circuit(target)
            qiskit_state = Statevector.from_instruction(qasm2.loads(dumps(circuit)))
            native = circuit.state()
            for index, amplitude in enumerate(qiskit_state.data):
                self.assertAlmostEqual(abs(amplitude - complex(native.amplitude(index))), 0.0, places=12)
