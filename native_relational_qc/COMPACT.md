# Exact compact execution and observer calculations

For measurement, reset, classical feedback and rational Pauli channels, see the
subsequent [NRQC-3 dynamic extension](DYNAMIC.md). This page records NRQC-2's
static-circuit methods and benchmark snapshot.

The goal is to return quantum-circuit answers with practical classical resources,
using native relational operations. This extension performs the calculation; it
does not merely check an answer supplied by another engine.

Two exact computation paths are available:

| Path | What is retained | Requested output |
|---|---|---|
| `observer` | Complete sparse Pauli expansion of a backwards-transported observation | Exact selected probability or X/Y/Z product expectation |
| `CompactState` | Shared proportional conditional states and exact incoming phase ratios | Exact amplitudes, marginals and Z-product expectations |

Both use rational coefficients of `1, sqrt(2), i, i*sqrt(2)`. There is no floating
rounding inside their algebra, and no approximate truncation. Floating conversion
is used only for display and comparisons. This gives exactness for the declared
gate model; it is not a claim of infinitely precise physical controls.

The algebra, cut-pairing invariant, group composition and cost conditions are
proved in [COMPACT_THEOREM.md](COMPACT_THEOREM.md). The representation families
(decision diagrams and Heisenberg/Pauli propagation) are established methods.

## Calculate a result

From the repository root, using Python 3.12:

```python
from native_relational_qc.compact import CompactCircuit
from native_relational_qc.observer import probability, expectation

n = 128
c = CompactCircuit(n)
for q in range(n):
    c.add('h', q).add('t', q)
for q in range(n - 1):
    c.add('cz', q, q + 1)
c.add('h', 0)

answer = probability(c, {0: 0, 1: 0})
print(answer.value.to_dict())
# coefficients ['1/4', '1/8', '0', '0']: (2 + sqrt(2))/8 exactly
print(answer.peak_terms)                 # 6
print(answer.gates_proved_invariant)     # 380 of the 384 gates examined
print(complex(answer.value).real)        # display-only floating conversion

small = CompactCircuit(2).add('h', 0).add('cx', 0, 1)
state = small.state()
print(state.amplitude('11'))             # sqrt(2)/2 exactly
print(expectation(small, {0: 'Y', 1: 'Y'}).value)  # -1 exactly
```

Supported gates: I, X, Y, Z, H, S/Sdg, T/Tdg, SX/SXdg, native R/K/RK,
CX, CZ, CH, CS, CT, CCX and SWAP. Qubit 0 is least significant. Queries use
qubit indices and the all-zero initial state. The fixed ordering is explicit.

`compact_qiskit.to_qiskit` exports these programs. `from_qiskit` accepts declared
standard exact gate classes and rejects arbitrary floating rotations, unknown
gate names, unresolved parameters, nonzero global circuit phase and measurements.
It does not guess that a floating angle is an exact multiple of pi. The earlier
dense adapter remains available for its wider floating unitary input class.

## Recorded results

[compact_verification.json](compact_verification.json) contains the actual runs,
source hashes, exact answers, timing samples and resource counters.

- **64 test methods passed**, zero failures, errors or skips. Subcases include
  36 seeded non-Clifford state comparisons and 30 seeded observer comparisons,
  plus the earlier dense engine's regression suite.
- Exact chain queries were calculated at **8, 16, 20, 32, 64 and 128 qubits**.
  Each returned `(2+sqrt(2))/8` with at most **six observer terms**, without
  constructing a statevector or state graph in that computation path.
- The alternative 64-qubit state calculation retained **127 graph nodes** and
  **67,288 bytes of retained Python graph objects** in this environment.
  A dense complex128 vector would have `2^64` entries. That is a theoretical
  storage comparison; no such dense vector was attempted.
- The ordering control grew from **3 to 381 nodes** for 1–7 separated Bell pairs;
  the equivalent adjacent-pair arrangement grew from **3 to 21 nodes**.
  This demonstrates a real limitation of the fixed-order state representation.

### Matched selected-query timing

Warm figures below are medians of three calls in the recorded environment.
Local operator transfer tables are cleared for each first observer call, then
reused. The result is the same local marginal in every path.

| Circuit size | Exact observer, first call | Exact observer, warm | Aer MPS, first call | Aer MPS, warm |
|---|---:|---:|---:|---:|
| 20 qubits | 10.23 ms | 0.600 ms | 1.67 ms | 1.03 ms |
| 64 qubits | 10.58 ms | 0.588 ms | 3.73 ms | 2.49 ms |
| 128 qubits | 10.42 ms | 0.801 ms | 6.06 ms | 4.61 ms |

On this 128-qubit local-query benchmark the warm observer path was about 5.8x
faster than this Aer MPS call path, while its first call was slower. This is a
bounded engineering result, not a general advantage over MPS or quantum hardware.
Aer timings include its local `run/result` and probability-save overhead; this is
an end-to-end API comparison, not an isolated numerical-kernel throughput test.
Circuit construction is outside both timings. Full MPS tensor export and memory
accounting happen in a separate execution outside timing. MPS has no
bond-dimension cap and zero truncation threshold; its retained numeric tensors
are small too.

The dense Qiskit reference was executed only through 20 qubits. Its recorded
20-qubit SDK marginal differed by about 1.14e-12. A compensated `math.fsum` over
the same selected amplitudes differed by about 2e-15. The report retains both
values; it does not hide the first aggregate check's failure or loosen its 1e-12
independent-reference tolerance. The compensated audit is outside timing. The
exact native answers have no algebraic rounding error in this gate model.

## Reproduce

```bash
python3.12 -m venv .venv-native
.venv-native/bin/python -m pip install -r native_relational_qc/requirements-compact.txt
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv-native/bin/python -m native_relational_qc.compact_benchmark \
  --out native_relational_qc/compact_verification.json
```

The exact arithmetic and observer/state engines themselves use only the Python
standard library. NumPy, Qiskit and Aer are comparison/export dependencies.
The package's existing root imports NumPy for its older engine.

## Boundaries that affect computation

- This is a structured, classically tractable circuit family. The code is general
  over its declared exact gates, but this benchmark does not certify arbitrary
  128-qubit circuits or a full 2^128-outcome distribution.
- The observer term count and rational coefficient length can grow. The state
  graph can grow exponentially. Node/term, coefficient-bit and work budgets raise
  `ResourceLimit`; they do not silently discard memory or approximate the answer.
- State gates are transactional: a failed update retains the previous exact
  state. Full dense expansion requires an explicit request and a small limit.
- No hardware job, device-noise experiment, dynamic measurement/reset or
  feed-forward was performed. Ideal circuit equivalence does not establish
  physical gravity claims or a separate native quantum processor.
- The meaningful advance over the previous repository milestone is **direct
  compact calculation with exact retained memory**. Universal quantum-computer
  replacement and a best-known-classical advantage remain unestablished.
