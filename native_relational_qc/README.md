# Native Relational Quantum Computing — v0.1

**Latest: [minimum linear future banks](LINEAR_RECOGNITION.md).** Exact row-space
closure reduces a seven-qubit CCX observer bank from 64 coordinates to eight
combined readings. A separate verifier checks independence, reachability and
all-future updates; the execution API replays declared words using the bank.
Compilation cost, coefficient storage and no-reduction cases remain explicit.

**Previous: [exact phase observers and future-complete recognition](OBSERVER_RECOGNITION.md).**
`observer32` pulls back selected p16/p32 measurements without amplitude
preparation. A separate bounded compiler returns exact future-closed Pauli
banks. Source-pinned morphic/representation/analytic review, paired successes
and failures, and 279 passing native tests accompany the adapter.

**Previous: [modular arithmetic and five phase bits](MODULAR_SHOR.md).**
`cyclotomic32` adds exact 11.25-degree phases. The `arithmetic` Shor oracle
constructs reversible modular multipliers without truth tables, restores clean
workspace and gives nonzero strict-CF factor recovery for N=21 at five bits.

**New: [exact 22.5-degree phases](PHASE_EXTENSION.md).** The explicit `cyclotomic`
backend embeds the original number field, reuses one sparse state per batch and
supports four-bit Shor phase estimation. It has separate resource accounting;
the old frame engines retain their gate sets and large-register capabilities.

**New: [small Shor factoring test](SHOR.md).** Exact modular exponentiation,
inverse QFT and verified factor extraction run through both frame backends.
N=15 and N=21 demonstrate correctness and the original three-bit phase boundary;
structured 2056-site support does not imply general Shor execution at that size.

**New: [Surya/jya local returns](JYA_FRAME.md).** `jya_frame` folds repeated
single-qubit words with exact trace/determinant recurrence and retained phase.
It accepts the same 1–2056-site circuits as `clifford_frame`, preserves
entangling-gate boundaries, and supports all calculator observation types.

**New: [exact Clifford frame](CLIFFORD_FRAME.md).** `clifford_frame` removes the
mandatory 2^k projector expansion for wide T-phase probability queries. It
retains a bounded sparse residual vector, full interference and the Clifford
circuit, with explicit branch/pair limits and paired 2056-site measurements.

**New: [2056-qubit exact selected observations](LARGE_REGISTER.md).** Explicit
`stabilizer` and `clifford_t` backends execute supported large-register circuits
using bit-packed Pauli pullback, generator elimination and bounded exact phase
expansion. Measured whole-register checks and an independent 14,392-gate
Clifford reference accompany the implementation. The existing factored and
expanded-observer backends retain their 256-qubit input cap.

**New: [custom quantum-circuit calculator](CALCULATOR.md).** Supply a circuit and
probability, Pauli-expectation or marginal-distribution queries as JSON. Obtain
exact answers, certified decimal display intervals and explicit resource status
with `python -m native_relational_qc calculate INPUT.json`.

**New: [exact factored evaluation](FACTORED.md).** A product-observer suffix and
exact sparse MPS boundary contraction recover previously failed 50-qubit local
and global-parity answers. The 57-row comparison retains deeper failures and
factorization ablations; Aer MPS remains faster on these workloads.

**New: [40–50 qubit random-brickwork stress test](STRESS_BENCHMARK.md).**
Exact observer expansion, isolated process memory/time, Aer MPS and feasible
dense references are measured with retained failed runs. This broader workload
exposes a term-growth boundary; the earlier structured 128-qubit example is not
evidence of general performance superiority.

**New: [original IBM workloads executed natively](IBM_WORKLOADS.md).** The pinned
17-qubit Shor logical builders now run as saved native programs, with complete
classical output distributions for all four cases at one and three rounds.
Default execution needs no quantum SDK; it uses software quantum registers.

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
