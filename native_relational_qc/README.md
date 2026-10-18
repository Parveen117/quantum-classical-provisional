# Native Relational Quantum Computing — v0.1

**New: [exact dynamic execution and recovery](DYNAMIC.md).** NRQC-3 adds
measurement, reset, overwritten classical memory, conditional gates and rational
Pauli channels. It includes teleportation, all 27 single-Pauli Shor recovery
cases and 128 rounds of a declared noisy bit-flip recovery model.

**New: [exact compact execution and direct observer calculations](COMPACT.md).**
The NRQC-2 extension computes selected answers without expanding the amplitude
vector, using exact phase/ratio arithmetic and retained operator memory. It includes
128-qubit structured-query runs, resource-growth controls and an Aer MPS comparison.
The dense engine documented below remains the broader floating-unitary reference.

**Target:** express a quantum task once, calculate it in the native relational
engine, compile the same semantics for an IBM-compatible target, and compare
the declared observations. This is the first static ideal-circuit milestone.

The evaluator is independent NumPy code. Qiskit is an optional input/output,
compilation and reference adapter. No Runtime service, account discovery or job
submission is performed by this package.

## What exists

| Layer | Implemented meaning |
|---|---|
| Native state | Complex ray, nonzero ratio charts, relative phases, full entangled joint amplitudes |
| Native algebra | Explicit EMK representation with R²=-I, K²=I, RK=-KR; unitary gate sector |
| Native calculation | Arbitrary local unitary tensor contraction; full operator phases retained |
| Observation | Computational basis or explicit basis-changing gates; terminal partial measurements with classical wiring |
| Circuit exchange | Strict JSON document and SHA-256; Qiskit static-unitary import/export |
| IBM compilation | Offline compilation against a supplied Qiskit Target, preserving returned layout |
| Existing evidence bridge | Circuit-derived ExpectedModel with a declared TVD tolerance and circuit hash |
| Software verification | Analytic answers, independent Qiskit comparisons, phase/order negative controls |

The mathematical bridge and its explicit hypotheses are in [THEOREM.md](THEOREM.md).
Evidence from this package is labeled LOCAL_IDEAL or MODEL_PREDICTION. It does
not relabel simulated predictions as measured hardware observations.

## Run with Python 3.12

From the repository root:

```bash
python3.12 -m venv .venv-native
.venv-native/bin/python -m pip install -r native_relational_qc/requirements.txt
.venv-native/bin/python -m unittest discover -s tests -p 'test_native*.py' -v
.venv-native/bin/python -m native_relational_qc bell --compare-qiskit
.venv-native/bin/python -m native_relational_qc bv --compare-qiskit
.venv-native/bin/python -m native_relational_qc grover --compare-qiskit
```

Native-only use requires NumPy; Qiskit tests explicitly skip when the optional
SDK is absent. A skipped SDK suite is not a compatibility pass.

```python
from native_relational_qc import Circuit, K, R, RelationalState
from native_relational_qc.qiskit_adapter import to_qiskit, from_qiskit, compile_for_target

native = Circuit(2).add("h", 0).add("cx", 0, 1).measure_all()
print(native.probabilities())  # 00: 1/2, 11: 1/2
qc = to_qiskit(native)
restored = from_qiskit(qc)
# isa_circuit = compile_for_target(native, backend.target)
# Compilation returns a circuit; it does not run a hardware job.
```

To preserve a real IBM circuit, import its bound Qiskit circuit or construct the
same operations. A supported custom Gate is converted to its complete unitary
matrix, not replaced by a guessed gate based on its name. Terminal measurements
must have unique quantum and classical wires. Barrier instructions are inert.
Unsupported operations fail explicitly.

## Ordering and resource contract

- Qubit 0 is the least significant bit. A displayed string is `q[n-1]...q[0]`.
- For a local gate on `(q0, q1, ...)`, its matrix's bit 0 is the first qarg.
- `low.tensor(high)` puts `low` in the low-order register.
- `state()` is the state before terminal observation; `probabilities()` applies
  the observation map. It does not sample or return a collapsed conditional state.
- Native state allocation is limited to 20 qubits, individual gate matrices to
  5 qubits, and classical output registers to 20 bits. These are resource guards,
  not physical claims. The dense engine stores O(2^n) complex amplitudes and has
  no demonstrated scaling advantage over other statevector simulators.
- On an already transpiled input, indices are physical indices. A returned ISA
  circuit can include additional idle hardware qubits and exceed the local cap.
  Keep the compiled circuit, its layout and measurement map together; do not
  compare permuted physical amplitudes directly with logical amplitudes.
- Multiple Qiskit classical registers are flattened by their actual bit index.
  Imported raw count strings must be converted to that same convention first.

## First analytic targets

| Program | Ideal expected answer |
|---|---|
| Bell ZZ and XX | P(00)=P(11)=1/2 |
| Bell YY | P(01)=P(10)=1/2 |
| Bell ZX | All four outcomes have probability 1/4 |
| GHZ | P(00...0)=P(11...1)=1/2 |
| Bernstein–Vazirani | Secret 1011 with probability 1 |
| Two-qubit Grover | Marked item 11 with probability 1 |
| RK/KR order-memory | Ancilla 1; erased-order control gives ancilla 0 |

The oracle/problem definition is part of each program. These examples establish
correctness checks, not quantum speedup on the classical host.

## Next compatibility gates

1. Static ideal circuit equivalence: this implementation and its recorded checks.
2. Dynamic circuits: [NRQC-3](DYNAMIC.md) implements exact measurement, reset and
   classical feed-forward for a declared finite subset, with new ideal Shor and
   repeated-recovery workloads. General control flow and replay of the historical
   measured Shor workload remain open.
3. Measured hardware comparison: predeclare circuits, bases, raw-count ordering,
   job IDs, calibration/noise assumptions, shots and statistical tolerances.
   Compare with the existing bridge without fitting away discrepancies.
4. Scale: [NRQC-2](COMPACT.md) adds exact structured state and observer engines,
   matched dense/MPS comparisons and an exponential graph-growth control.
   Broader workloads and best-known-classical comparisons remain open.
5. Separate native physical processor: requires a coherent hardware realization
   and new physical evidence.

Passing one gate does not automatically pass the later gates. The scientific
value of the present milestone is a reproducible, explicit computational bridge.
