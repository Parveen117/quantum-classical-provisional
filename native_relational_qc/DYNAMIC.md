# Exact dynamic execution: measurement, memory and recovery

The NRQC-3 extension calculates selected results of circuits containing
mid-circuit measurement, reset, classical feedback and rational Pauli noise.
It carries quantum Pauli terms together with classical parity characters, so
measurement outcomes and overwritten memory enter the calculation explicitly.
The native evaluator constructs no statevector, density matrix or trajectory
list. All retained arithmetic is exact in the declared gate/channel model.

The [derivation](DYNAMIC_THEOREM.md) gives the local dual maps and resource
conditions. This is an implementation of established quantum-instrument and
observer mathematics, with the native phase/ratio representation retained.

## Executable interface

```python
from fractions import Fraction
from native_relational_qc.dynamic import DynamicCircuit, probability, expectation
from native_relational_qc.dynamic_examples import teleport, bitflip_recovery, bell_fidelity

# Measure, keep the outcome, then correct using the current classical bit.
c = DynamicCircuit(1, 1).add('h', 0).measure(0, 0)
c.add('x', 0, condition={0: 1})
assert probability(c, quantum={0: 0}).value.a == 1

# Teleport H,T|0>; the X and Y readings are both sqrt(2)/2 exactly.
t = teleport()
print(expectation(t, {2: 'X'}).value.to_dict())
# {'basis': '1,sqrt(2),i,i*sqrt(2)', 'coefficients': ['0','1/2','0','0']}
print(probability(t, classical={0: 1, 1: 0}).value.to_dict())  # 1/4

# Synthetic independent X error probability 1/10 per data qubit, one round.
recovery = bitflip_recovery(probability=Fraction(1, 10))
fidelity, readings = bell_fidelity(recovery, logical=0, reference=4)
print(fidelity.to_dict())  # 243/250 = 0.972, exactly
```

The initial quantum state and classical memory are zero. Qubit/bit 0 is least
significant. `measure(q,c)` overwrites c; `reset(q)` preserves the classical
memory. A condition such as `{0: 0, 2: 1}` is a conjunction of current bit values.
Classical conditions are supported on gates. Measurement/reset are unconditional.
Finite repeated rounds are explicitly unrolled; general loops are not supported.

`probability(c, quantum=..., classical=...)` returns a **joint** probability;
unspecified outputs are marginalized. `expectation(..., classical=event)` returns
an unnormalized joint moment. Divide by the nonzero event probability explicitly
if a conditional expectation is wanted. The evaluator never silently postselects.

`pauli_channel(q, {'I': ..., 'X': ..., 'Y': ..., 'Z': ...})` accepts nonnegative
`int`/`Fraction` weights summing exactly to one. Floats, negative weights and
unnormalized mixtures are rejected. Channel invocations describe independent
mixtures, not correlated hardware noise unless that correlation is modeled
explicitly in the circuit.

## Verification actually performed

[dynamic_verification.json](dynamic_verification.json) records source hashes,
exact coefficients, independent references and the following results:

| Check | Recorded result |
|---|---|
| Native regression suite | 83 methods passed; zero failures, errors or skips |
| Independent forward density crosschecks | 32 seeded dynamic programs, 1–4 qubits; joint outputs and joint moments |
| Teleportation | Eight input preparations, including non-Clifford states; all X/Y/Z readings preserved |
| Teleportation branch check | All four outcomes for the H,T input have probability 1/4 and the correct joint moments |
| Shor recovery | No error plus all 27 single-qubit X/Y/Z errors: exact decoded Bell fidelity 1 |
| Shor syndrome | All eight deterministic bits matched in every case |
| Independent Aer comparison | Exported teleportation and Shor circuits agreed; maximum teleport error 6.67e-16, Shor error 0 |
| Rational-noise recovery | Exact one-round logical error 7/250 = 2.8%, from 10% independent physical X noise |
| Repeated recovery | 1, 3, 8, 32 and 128 rounds matched the analytic formula exactly |

The Shor workload uses nine data qubits, one reused syndrome ancilla and one
external reference: **11 qubits total**. It checks preservation of the logical
qubit's entanglement, not only a known final bit. The largest observed term
dictionary for its three Bell readings had 256 terms.

The repeated bit-flip workload uses five qubits, two overwritten classical bits
and a reused syndrome ancilla. At 128 rounds it has 1,799 instructions; the
largest term dictionary has 16 entries and the largest recorded observer
coefficient has 892 bits. These are representation counters, not process-memory
measurements. Several temporary dictionaries may coexist.

Recovery reduces each round's error but does not eliminate accumulated logical
errors. With ideal syndrome operations and independent p=0.1 physical X noise:

| Corrected rounds | Exact-model Bell fidelity, decimal display |
|---|---:|
| 1 | 0.972 |
| 3 | 0.920616192 |
| 128 | 0.5003128853827924 |

The full exact fractions are retained in the report. The formula is
`pL=3*p*p-2*p*p*p`, `F(r)=(1+(1-2*pL)**r)/2`.

Negative controls are part of the record: removing teleportation feedback
erases the output Bloch readings; removing Shor correction gives fidelity zero
for the tested Z0 error; removing bit-flip correction gives one-round fidelity
0.9 instead of 0.972. The checks therefore respond to missing recovery.

## Independent references and Qiskit exchange

`dynamic_reference.py` is a deliberately different forward implementation. It
uses unnormalized density matrices grouped by actual classical bitstrings, with
Qiskit unitary evolution and reset. It is limited to six qubits and six classical
bits and is used only for verification. It imports no observer-transfer code.

`dynamic_qiskit.to_qiskit` exports gates, measurement, reset and nested bit-equality
conditions. Rational Pauli channels export through Aer using floating weights.
No Runtime account or hardware job is involved.

The strict importer accepts the standard exact named gate classes already
declared in the compact adapter, measurement, reset, and if-only blocks with
bit/register equality. It preserves local-to-global wire maps. Else blocks,
loops, arbitrary expressions, conditional instruments, floating rotations and
noise instructions are rejected. Exported native R/custom-unitary and CT gates
may require a supported explicit decomposition before import, as in NRQC-2;
export is broader than import. No rational channel is guessed from Aer floats.

The Aer runs save state expectation values. One trajectory per Shor case is
sufficient for that comparison because the syndrome is deterministic, separately
checked exactly. Corrected teleportation readings agree in every outcome branch,
also checked by exact joint queries and forward density branches. These are not
probability estimates made from a single measured output bit.

## Reproduce and scope

Use the Python 3.12 environment pinned in `requirements-compact.txt`:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv-native/bin/python -m native_relational_qc.dynamic_verify \
  --out native_relational_qc/dynamic_verification.json
```

The exact engine uses the standard library plus the existing local exact gate
tables. Qiskit/Aer are verification and export dependencies. Native queries
accept `max_terms`, `max_work` and `max_coefficient_bits`; exceeding a budget
raises `ResourceLimit` without modifying the circuit or approximating a result.

This closes the earlier measurement/reset/feedback gap for the **declared finite
circuit subset**. General dynamic Qiskit programs, arbitrary noise channels,
device timing/calibration/noise and broad resource-advantage benchmarks remain
open. These Shor/recovery circuits are classically tractable; reproducing them
establishes useful compatibility, not quantum-computer obsolescence. No hardware
job was submitted, and no physical error-correction performance is inferred.
