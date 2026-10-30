# 40–50 qubit random-brickwork stress test

**Result: selected 40/50-qubit answers can be obtained exactly, but this test does
not demonstrate a breakthrough or superiority over Aer MPS.** The expanded exact
Pauli observer hits its term/time budgets well before MPS on this workload.
Avoiding a full statevector alone does not establish a quantum advantage or
an advantage over other classical simulation algorithms.

The primary run contains 49 isolated measurements, with 15 explicitly adaptive
follow-ups. Two small plumbing pilots are retained separately. Every failure is
retained; no failed query is assigned an approximate or guessed answer.

## What was run

Open one-dimensional random Clifford+T brickwork, input |0...0>. All sites start
with H then T. Each round applies a random H/SX/SXdg gate and random T/Tdg gate
on every site, followed by an alternating even/odd nearest-neighbor CZ matching.
A final H layer exposes the last entangling layer to the Z readout. There is no
seed search, Clifford-only replacement, or hand-selected cancellation circuit.
This is a concrete non-Clifford family, not a claim of generic classical hardness.

- Primary seed: **20261018**; additional 50-qubit checks use **20261019**.
- Primary sizes: **40 and 50**; rounds: **4, 8, 12, 16, 20, 24**.
- One round has three parallel gate layers. The unoptimized layer count is
  **3r+3**, so these circuits have 15–75 layers. At 50 qubits, 4 rounds has
  648 gates including 250 T/Tdg and 98 CZ; 24 rounds has 3,138 gates.
- Local query: **P(q[n//2-1]=0, q[n//2]=0)**, with all other outputs marginalized.
- Global query: **expectation of Z on all 50 sites**, at 4/8/12 rounds.
- These are selected scalar observations, not all 2^n probabilities or amplitudes.

[Frozen primary protocol](stress_protocol.json), [primary raw results](stress_results.json),
[adaptive protocol](stress_followup_protocol.json), [adaptive raw results](stress_followup_results.json),
[pilot records](stress_pilots.json), [integrity/test record](stress_verification.json).
Each row contains the actual circuit SHA-256, gate counts and query support.
The structural backward lightcone is reported for interpretation; it is not used
to replace the circuit with a smaller one by the benchmark controller.

## (a) Exact answers

The native engine retains every Pauli coefficient in Q(sqrt(2),i), without
discarding small terms. Completed local queries include:

| Qubits | Rounds | Exact P(00) | Decimal display | Peak terms | Cone qubits |
| --- | --- | --- | --- | --- | --- |
| 8 | 4 | 2701/8192 + (-37/4096)√2 | 0.316937035691454 | 9,605 | 8 |
| 40 | 4 | 2271/8192 + (-39/1024)√2 | 0.223360030339306 | 9,605 | 8 |
| 50 | 2 | 65/256 | 0.253906250000000 | 637 | 6 |
| 50 | 3 | 121/512 + (-7/256)√2 | 0.197658222903861 | 694 | 6 |
| 50 | 4 | 33423/131072 + (-127/4096)√2 | 0.211148346576811 | 147,241 | 10 |

In particular, the 50-qubit, 4-round answer is
**33423/131072 − (127/4096)sqrt(2) = 0.21114834657681078...**.
It required a larger-budget rerun: the original 16,384-term run failed; a
262,144-term/60-second run completed in **29.485 seconds**, peaking at
**147,241 terms** and **180.9 MiB process RSS**. Its matching MPS result was
0.2111483465766823, differing by approximately 1.28e-13.

This success has a **10-qubit structural causal region** for the chosen local
observable. The 40-qubit, 4-round local query has an 8-qubit region. These are
not demonstrations of an irreducible 50-qubit global computation. The global
50-qubit queries have full support and did not finish in the native engine.

Aer MPS returns double-precision numerical values, not algebraically exact
certificates. A zero requested truncation threshold does not remove floating
point/SVD error or intrinsic numerical zero handling. The small dense checks
below measure absolute differences; the tiny 50-qubit parity values are not
independently certified to a given relative accuracy by this experiment.

## (b,c) Expansion, execution time and memory

Primary limits: **16,384 terms, 10,000,000 term visits, 4,096 coefficient bits,
20 seconds of execution, 1,280 MiB process RSS**. The larger follow-ups permit
262,144 terms, 100,000,000 visits and 60 seconds, retaining the same RSS cap.
These are declared experimental budgets, not fundamental computational limits.

The following tables use seed 20261018. `term limit` means no answer, with the
expansion observed at 16,385 entries when the 16,384 cap was crossed.
`time limit` means no answer. Times for killed processes include termination
latency and therefore slightly exceed the nominal limit. Memory on killed
workers is a sampled lower bound, not the memory needed to finish the task.

| Qubits | Rounds | Cone qubits | Observer | Peak terms | Observer s / MiB | MPS | MPS s / MiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | 4 | 8 | complete | 9,605 | 1.752 / 41.4 | complete | 0.009 / 100.6 |
| 40 | 8 | 16 | term limit | 16,385 | 3.812 / 45.3 | complete | 0.017 / 101.8 |
| 40 | 12 | 24 | term limit | 16,385 | 3.549 / 45.5 | complete | 0.254 / 110.9 |
| 40 | 16 | 32 | term limit | 16,385 | 3.428 / 45.1 | complete | 19.219 / 218.0 |
| 40 | 20 | 40 | term limit | 16,385 | 3.387 / 45.8 | time limit | 20.523 / 193.8 |
| 40 | 24 | 40 | term limit | 16,385 | 3.559 / 45.3 | time limit | 20.587 / 194.9 |
| 50 | 4 | 10 | term limit | 16,385 | 2.158 / 45.3 | complete | 0.009 / 101.8 |
| 50 | 8 | 18 | term limit | 16,385 | 3.614 / 45.0 | complete | 0.028 / 103.6 |
| 50 | 12 | 26 | term limit | 16,385 | 3.216 / 45.0 | complete | 0.314 / 114.3 |
| 50 | 16 | 34 | term limit | 16,385 | 3.299 / 45.3 | time limit | 20.551 / 201.0 |
| 50 | 20 | 42 | term limit | 16,385 | 3.572 / 44.8 | time limit | 20.601 / 202.0 |
| 50 | 24 | 50 | term limit | 16,385 | 3.295 / 45.4 | time limit | 20.861 / 202.2 |

MPS bond dimensions are measured from its operation log for completed rows.
The 4/8/12-round primary runs reached maximum bond dimensions **4/16/64**;
the completed 40-qubit, 16-round run reached **256**. No final bond dimension
is claimed for killed runs. No run reached the 1,280 MiB RSS guard; time or term
limits stopped the unsuccessful runs first.

Global parity, 50 qubits:

| Rounds | Observer | Peak terms | Observer s / MiB | MPS s / MiB | MPS numerical value |
| --- | --- | --- | --- | --- | --- |
| 4 | term limit | 16,385 | 2.224 / 47.7 | 0.009 / 101.5 | 1.00355228e-09 |
| 8 | term limit | 16,385 | 2.411 / 47.7 | 0.029 / 103.3 | -1.49208031e-08 |
| 12 | term limit | 16,385 | 2.400 / 48.1 | 0.391 / 109.8 | -3.92447394e-08 |

Adaptive larger-budget observer runs on the identical primary circuits:

| Qubits | Rounds | Query | Outcome | Observed peak terms | Seconds | RSS MiB |
| --- | --- | --- | --- | --- | --- | --- |
| 50 | 4 | local00 | complete | 147,241 | 29.485 | 180.9 |
| 50 | 8 | local00 | time limit | ≥ 147,241 | 60.264 | 181.4 |
| 50 | 4 | parity | term limit | 262,145 | 35.499 | 297.3 |

For the 50-qubit, 8-round timeout, **147,241 is only the last checkpoint's
peak**, before the current gate finished. Its checkpoint had examined 736 of
1,146 gates in reverse order; the actual unfinished expansion may be larger.
For global parity, the 262,145-term crossing occurred at the 111th of 648
reverse-processed gates, on T at qubit 31. The complete required expansion is
unknown because propagation was deliberately stopped. The completed 50-qubit,
4-round local query visited 7,684,453 terms across gates and used at most 18-bit
coefficient numerators/denominators. Coefficient bit growth was not its bottleneck.

Adaptive boundary and secondary-seed runs:

| Qubits | Rounds | Seed | Observer | Peak terms | Observer s / MiB | MPS | MPS s / MiB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | 5 | 20261018 | term limit | 16,385 | 3.392 / 45.2 | complete | 0.009 / 101.2 |
| 40 | 6 | 20261018 | term limit | 16,385 | 3.472 / 45.5 | complete | 0.011 / 102.4 |
| 50 | 2 | 20261018 | complete | 637 | 0.106 / 32.1 | complete | 0.006 / 101.3 |
| 50 | 3 | 20261018 | complete | 694 | 0.126 / 32.9 | complete | 0.008 / 102.0 |
| 50 | 5 | 20261018 | term limit | 16,385 | 2.253 / 45.3 | complete | 0.011 / 102.3 |
| 50 | 6 | 20261018 | term limit | 16,385 | 3.412 / 44.1 | complete | 0.012 / 102.1 |
| 50 | 8 | 20261019 | term limit | 16,385 | 3.747 / 44.4 | complete | 0.023 / 103.6 |
| 50 | 16 | 20261019 | term limit | 16,385 | 3.606 / 45.4 | time limit | 20.478 / 201.0 |

## Full-state comparison: measured where feasible, analytical at 40–50 qubits

A complex128 dense statevector needs **16 × 2^n bytes for amplitudes alone**.
At 40 qubits that is **16 TiB**, and at 50 qubits **16 PiB**, excluding working
buffers. The host has an **8 GiB cgroup memory limit** and no swap. Dense
40/50-qubit executions were **not attempted**; their runtimes are **not measured**.
The memory estimates are not evidence that MPS, tensor contraction or other
classical approaches also require that much memory.

The same generator and queries were actually run with Aer statevector at
8/12/20/24 qubits. Maximum observed MPS versus dense absolute difference was
**1.0162e-11**. All completed native results with a completed reference agreed
within **5.88e-13** against MPS; the raw comparison list retains every difference.

| Qubits | Rounds | Query | Observer | Observer s / MiB | MPS s / MiB | Dense s / MiB | MPS–dense error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 8 | 4 | local00 | complete | 1.885 / 40.7 | 0.005 / 101.4 | 0.003 / 100.1 | 3.495e-13 |
| 8 | 4 | parity | term limit | 3.489 / 45.5 | 0.003 / 101.2 | 0.004 / 100.7 | 1.016e-11 |
| 12 | 8 | local00 | term limit | 3.823 / 45.3 | 0.005 / 101.4 | 0.008 / 100.7 | 2.041e-13 |
| 20 | 8 | local00 | term limit | 3.933 / 45.0 | 0.012 / 102.1 | 0.499 / 117.3 | 1.316e-12 |
| 24 | 8 | local00 | term limit | 3.685 / 45.4 | 0.012 / 101.2 | 11.332 / 357.5 | 1.357e-12 |

## (d) Where this implementation fails, and what follows

1. **Exact Pauli expansion is the first boundary.** At the primary budget, the
   40-qubit local query passes at 4 rounds and fails at 5/6/8; the 50-qubit local
   query passes at 2/3 rounds and fails at 4. Raising the budget recovers the
   50-qubit 4-round answer, but the 8-round query still times out at 60 seconds.
   These are sampled, seed-specific boundaries, not a monotonicity theorem.
2. **Global support is substantially harder for this representation.** The
   50-site parity query crosses 262,144 terms even at 4 rounds. T conjugation
   branches X/Y Pauli factors, and the retained expanded dictionary grows despite
   exact cancellation. This is computational resource failure, not physical
   wavefunction collapse or evidence of an unsolvable mathematical problem.
3. **MPS also slows with depth.** Its bond dimension grows in these circuits;
   40-qubit 16 rounds completes in 19.219 seconds, whereas 20/24 rounds exceed
   the 20-second limit. At 50 qubits, 12 rounds completes and 16/20/24 do not
   within that limit. Larger budgets or other implementations may succeed.
4. **The requested breakthrough is not established.** In the successful
   50-qubit 4-round comparison, native exact propagation is slower and uses more
   peak process memory than MPS, while providing stronger arithmetic exactness.
   Lower memory on a failed run is not a successful memory advantage. No broad
   best-classical comparison, hardware replacement or new complexity result is
   supported by these measurements.

The next substantive research target is an exact factored observer representation
that avoids materializing the full Pauli sum, with this failed 50-qubit/8-round
local case and 50-qubit global parity as fixed regression workloads. Lightcone
pruning and faster Clifford updates may improve constants, but do not by
themselves establish a way around generic exponential growth. Such an improvement
is a future target; it has not been implemented or demonstrated in this report.

## Measurement and reproducibility

- Python 3.12.14, NumPy 2.5.4, Qiskit 2.6.0, Aer 0.17.2, Linux x86_64.
  Single-thread OpenMP/BLAS settings; each row runs in a fresh isolated process,
  sequentially. These are host measurements, not runs on a particular laptop.
- Execution timing excludes imports, circuit construction and backend creation;
  includes native cold transition-table construction or Aer submission/execution
  and selected-result retrieval. Setup and full process wall time are also saved.
  Each reported row is one run; no confidence intervals or stable speedup ratios
  are claimed. Pilot and primary repeated small rows remain separate.
- Peak RSS is Linux VmHWM measured at execution end, including interpreter,
  imports and setup. Parent RSS sampling runs about every 25 ms; killed workers
  retain that sampled peak. This is not allocator-only or tensor-only memory.
  The initial pilot exposed a PID-namespace sampling error; it was fixed before
  primary runs. Invalid pilot memory readings are explicitly marked and excluded.
- Aer uses selected `save_probabilities` (four entries) or a Pauli expectation.
  It never exports a complete MPS tensor or full dense output vector here.
  `enable_truncation=False` prevents pruning unused qubits; requested MPS bond cap
  is unlimited and truncation threshold is zero. Bond logging is enabled and its
  overhead is included. This is a full-circuit MPS API baseline, not the fastest
  possible causal-cone contraction or a survey of optimized classical solvers.
- Observer telemetry is observational only. Callback-disabled and callback-enabled
  results match in tests; budget exceptions carry partial statistics and no value.
  Gate-boundary checkpoints are lower bounds during a killed in-progress gate.
- **93 native test methods passed, zero failures/errors/skips.** The integrity
  record binds current source/tests/protocols/results by SHA-256. Earlier
  verification JSON files remain historical snapshots: their observer.py hashes
  differ after this instrumentation change. They are not relabeled as fresh runs.
- All calculations are local software. No IBM account, hardware job or Runtime
  access is involved. The existing private draft PR remains unmerged.

From the repository root, in a Python 3.12 environment:

```bash
python -m pip install -r native_relational_qc/requirements-benchmark.txt
python -m unittest discover -s tests -p 'test_native*.py' -v
python -m native_relational_qc.stress_benchmark --protocol native_relational_qc/stress_protocol.json --output /tmp/stress-primary.json
python -m native_relational_qc.stress_benchmark --protocol native_relational_qc/stress_followup_protocol.json --output /tmp/stress-followup.json
```

The controller retains checkpoints and result rows as it proceeds; failed
workers do not erase earlier results. Re-running uses the same seeds and circuits,
but wall times, memory readings and time-limit outcomes may vary by host.

Primary API references: [AerSimulator options](https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.AerSimulator.html),
[dense statevector storage](https://qiskit.github.io/qiskit-aer/stubs/qiskit_aer.StatevectorSimulator.html).
Installed versions and accepted options are retained in the raw evidence.
