# Original IBM logical workloads executed by the native engine

The native engine now executes the repository's original **17-qubit Shor
syndrome workloads**, including their measurements, classical register mapping
and three-round ancilla resets. Results are calculated locally from saved native
instructions. IBM Runtime and IBM hardware are not used for this execution.

The registers here are **software representations of qubits**. This project has
not constructed a physical quantum processor. The demonstrated capability is
independent exact computation of these quantum-circuit output distributions.

## Source and experiment identity

The original builders and evidence are pinned to repository commit
`2a9eaf3e54e56236f1a92caf0a799f2e953ec125`:

- `qec_error_control_lab/qec_circuit_spec.py`: original single-round materializer.
- `qec_error_control_lab/ibm_shor_3round_hardware.py`: original three-round materializer.
- The sibling encoding, stabilizer and repetition modules are also hash-pinned.
- Recorded single-round IBM job: `da2raps3jnrc73ae9n80`, backend `ibm_marrakesh`,
  4,096 shots per case, with the stored hardware certificate.
- Three-round submission receipt: `da2sogk3jnrc73aebcfg`. Its protocol-specification
  hash matches the pinned builder. The saved receipt says QUEUED; there is no
  three-round hardware result in this pinned source set. No current status was
  requested, and the historical receipt is not presented as a completed run.

Preparation calls the **original builders**, then imports their operations and
register maps into the native IR. It does not substitute the newer 11-qubit
recovery example. Every pinned source's Git blob and SHA-256 are checked. Two
inert barriers are omitted in each three-round native program.

This binds the logical source and experimental protocol. An archived full
device-transpiled ISA circuit is not available in this source set, so this is not
a claim of bit-for-bit replay of the submitted physical routing or pulse schedule.
Neither original workload applies conditional recovery; it extracts syndromes.

## Recorded native results

Eight complete logical circuits were executed: four cases each for one and three
rounds, with 17 quantum registers and respectively 17 or 33 classical output bits.

| Case | Computed syndrome, each round | Complete joint output support |
|---|---|---:|
| no_error | `00000000` | 8 outcomes, each exactly 1/8 |
| x_q0 | `00000001` | 8 outcomes, each exactly 1/8 |
| z_q0 | `01000000` | 8 outcomes, each exactly 1/8 |
| y_q4 | `11001100` | 8 outcomes, each exactly 1/8 |

These are complete distributions of the **classical readout**, not lists of all
quantum amplitudes. They include the joint correlations between the data readout
and every syndrome register. Each expected syndrome has exact ideal probability
one. Expected labels are used only after calculation to validate the result.

- **89 native test methods passed**, no failures, errors or skips.
- All eight complete distributions matched an independent local Aer stabilizer
  reference, including support; maximum probability discrepancy was **0**.
- A subprocess blocked imports of `qiskit`, `qiskit_aer` and
  `qiskit_ibm_runtime` and successfully calculated the original single-round
  complete distribution with the native engine.
- One-round runs used 52 native marginal queries; three-round runs used 68.
  The largest query expansion was 512 terms. Recorded local calculation times
  were approximately 5.6–7.4 seconds per complete distribution; no speed claim
  against hardware or optimized stabilizer implementations is made.
- A wrong-syndrome negative control returned probability zero.

The saved [input snapshot](ibm_workload_inputs.json) includes the native programs,
original register maps, pinned provenance and historical evidence. The
[verification record](ibm_workload_verification.json) includes every exact output
probability, source hashes and reference comparisons.

## Native execution without a quantum SDK

From the repository root, using the existing Python 3.12/NumPy environment:

```bash
.venv-native/bin/python -m native_relational_qc.ibm_workloads \
  --out native_relational_qc/ibm_workload_native_run.json
```

This default path reads the saved native input JSON, reconstructs the native
circuit and computes its output law. It imports no Qiskit/Aer/Runtime module and
opens no account or network session. NumPy is still imported by the package's
older root module; the exact observer calculations use Python rational algebra.

Rebuilding the snapshot or running the optional local reference uses the pinned
Qiskit/Aer environment from `requirements-compact.txt`:

```bash
.venv-native/bin/python -m native_relational_qc.ibm_workloads --prepare
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  .venv-native/bin/python -m native_relational_qc.ibm_workloads \
  --compare-aer --run-tests \
  --out native_relational_qc/ibm_workload_verification.json
```

The reference starts from the original Qiskit builders and checks that their
native encoding equals the snapshot. It replaces only the nine terminal data
measurements with a saved Z-basis probability distribution. The syndrome
instruments remain. One simulator trajectory suffices for their deterministic
syndrome; the eight data probabilities are saved state probabilities, not
estimates from one sampled data outcome. The native calculation finishes before
the reference is requested and does not read its answers.

## Why the full readout remains small here

`readout.classical_distribution` first computes each requested bit's marginal.
Bits whose probabilities are exactly zero or one are proven deterministic. It
then branches over the remaining bits using exact joint-prefix probabilities.

**Theorem (complete sparse readout).** For the declared trace-preserving circuit
model, this procedure returns the full requested classical distribution when it
finishes within its budgets.

Proof: if each fixed bit equals its assigned value almost surely, the probability
that any fixed bit differs is bounded by the sum of its zero mismatch
probabilities. Their joint assignment therefore has probability one; no
independence assumption is required. At each remaining prefix, the zero-child
mass is an exact joint probability and the one-child mass is the parent mass
minus that zero-child mass. The two children partition the parent event. Induct
over the bit sequence, retain all nonzero leaves and verify that their sum is
one. Exact ordering in Q(sqrt(2)) checks nonnegative masses without float tests.

Output count, query count and individual observer budgets raise `ResourceLimit`
instead of returning an incomplete law. Many stochastic output bits can still
produce exponentially many outcomes; this improvement does not remove that
limitation. Here the syndrome bits are deterministic and only eight correlated
data outcomes remain.

## Recorded hardware versus the ideal model

The earlier IBM hardware observations are retained unchanged:

| Single-round case | Recorded hardware expected-syndrome rate | Native ideal rate |
|---|---:|---:|
| no_error | 36.4990% | 100% |
| x_q0 | 33.6914% | 100% |
| z_q0 | 33.2520% | 100% |
| y_q4 | 19.1162% | 100% |

This difference measures hardware-versus-ideal disagreement, not proof that a
software simulation is physically more accurate than IBM. No calibration/noise
model was fitted, and the native result does not reproduce the noisy shot counts.
The report includes the syndrome-distribution total variation distance from the
ideal point mass, equal to one minus the recorded expected-syndrome rate.

The completed milestone is **running an existing IBM logical workload on our own
calculation engine**, with complete exact output laws for these eight circuits.
An independent physical qubit device and broad quantum-workload replacement
remain separate, unestablished capabilities.
