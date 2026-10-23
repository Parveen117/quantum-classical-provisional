# Exact Surya/jya local-return adapter

Author: Monty. 23 October 2026 (Asia/Kolkata).

The explicit `jya_frame` backend adds a measured repeated-local-word shortcut
to the calculator. On the qualified 2056-site entangled GHZ circuit with 256
repetitions of the execution word H,T on qubit zero, the global X expectation
takes **0.383 s**, versus **0.727 s** for `clifford_frame` and **0.610 s** for
sequential local fusion (median of three fresh processes). Every answer is
algebraically exact. Peak RSS is approximately 26.8 MiB in all three cases.

The improvement concerns these structured observations. Twelve independent
T-phase sites are slower here, and coefficient, residual-branch and pair growth
still stop harder calculations. The backend remains an explicit choice.

## Source connection and what is implemented

The [immutable source map](jya_source_pins.json) binds the actual RKF sources:

| Source | Consumed result | Adapter boundary |
| --- | --- | --- |
| [SE44, b07ccf7](https://github.com/Parveen117/Recognition-Kernel-Framework/blob/b07ccf7a97fbc1371119a3bfdb70c98ddeded14f/research/lambda_counting/SE44_TVSP_LINES_ANGLE_AND_NATIVE_JYA.md) | Retained two-channel jya and fixed-operator recurrence, equations 44.13–44.18 | An exact two-by-two trace/determinant specialization for named one-qubit words |
| [SE45, f4643e2](https://github.com/Parveen117/Recognition-Kernel-Framework/blob/f4643e2ea3e3be843903e4856ced8be0baf2a43e/research/lambda_counting/SE45_VARIABLE_JYA_CURVATURE_AND_TRACKING.md) | Changing-source identity with ordered conjugation, equation 45.14 | Ordered block application in the retained Clifford frame |

SE44 and SE45 record scoped replay passes, respectively 32 and 36 controls,
and an inherited whole-engine source-pin mismatch. Those historical records
are unchanged. This upgrade inspected their source and scope and tested the
finite quantum adapter independently; it did not rerun or recertify RKF.

This implementation uses standard two-by-two matrix algebra and binary
composition. It claims no new general recurrence identity or quantum advantage.
It does not implement SE44/45's sine-feedback calibration, curvature-flux
decoder or physical noise tracking. In particular, no nonlinear sine correction
is applied to a quantum state to make its branches disappear.

## Exact local recurrence

For a local gate word executed as G1, ..., Gp, define

\[
U=G_p\cdots G_1,\qquad t=\operatorname{tr}U,\quad d=\det U.
\]

Direct multiplication of a two-by-two matrix proves

\[
U^2-tU+dI=0,\qquad
U^{n+2}=tU^{n+1}-dU^n.
\]

For determinant one, U+U^{-1}=tI. Thus this is exactly the scalar-coefficient
specialization of SE44's operator recurrence. For a circular turn
U=cI+sJ, J²=-I, it reduces to the jya rule with t=2c, d=1. The tests include
SE44's rational turn c=4/5, s=3/5 and radius 3438.

Quantum words need not have determinant one. We retain d rather than divide
by an unrepresented square-root phase. Consequently this adapter stays in
the existing exact field Q(sqrt(2),i), including the full global phase.

Represent each power as aI+bU. Multiplying two such pairs uses

\[
(a,b)\star(c,e)=(ac-dbe,\;ae+bc+tbe).
\]

Starting with (1,0) and (0,1), binary composition yields U^m in O(log m)
pair compositions. It uses no division by sine or eigenvalue separation.
Identity, half-turn and repeated-eigenvalue cases therefore need no singular
decoder. This counts algebraic compositions, not constant-cost arithmetic:
coefficient bit lengths can grow with m and are explicitly capped.

The compiler scans the actual operation list. A contiguous one-wire run
containing T/Tdg becomes a local return. A linear prefix-function scan finds
its shortest period, including a possible trailing partial copy. For a run
word^m followed by tail, the executed matrix is U_tail U_word^m. The prefix
word and tail are multiplied exactly, and the repeated part uses the pair
recurrence. Pure Clifford runs retain the original Clifford skeleton.

An entangling gate or an operation on another wire ends a run. No gate is
commuted across another gate. Nonperiodic runs use sequential local fusion;
this is separately isolated by the benchmark's `linear_fusion` ablation.
Input still lists every gate, so parsing/scanning costs O(input length).

## Source retention in the quantum frame

Let the complete circuit operator be C V, where C is the retained Clifford
skeleton and V is a virtual unitary residual. Only v=V|0...0> is stored.
For a new local return D, keep C fixed and update

\[
v'=(C^\dagger D C)v,\qquad Cv'=DCv.
\]

At the operator level this is SE45's source-retention identity with B=C,
W=V and calibration correction R=I. Invertibility is asserted for V, not
for the stored vector v. A Clifford gate G instead updates C to GC while
leaving v unchanged. Thus both event types preserve the full ordered source.

For D=[[a,b],[c,d]], its exact Pauli expansion is

\[
D=\frac{a+d}{2}I+\frac{b+c}{2}X+
\frac{c-b}{2i}Y+\frac{a-d}{2}Z.
\]

Each Pauli is conjugated through C with its exact sign/phase, then applied
to the sparse residual. Coefficients are summed only at identical basis
addresses. Each compiled local matrix satisfies D†D=I exactly; the final
residual satisfies sum |v_x|²=1 exactly. No threshold or truncation is used.

The [existing frame readout](CLIFFORD_FRAME.md) then computes expectations
or joint probabilities through generator elimination and sparse matrix
elements. Its two readout bodies were factored into shared functions; the
original frame preparation, mathematics and public defaults are unchanged.

These local two-channel blocks may act inside an entangled 2056-site circuit.
This does not assert that the whole circuit has a two-dimensional invariant
space. The residual may still reach exponentially many basis addresses.

## Measured qualification

The [protocol](jya_protocol.json) was frozen after correctness testing and
before the paired timing runs. It contains six paired cases, three execution
strategies, five failure controls, and three repetitions: **69 runs**.
The [raw results](jya_results.json) retain every run, exact value, semantic
hash, cost counter and failure. There are **54 exact completions, 12 resource
rejections and three deliberate wall timeouts**. Every expected outcome passed.

| Circuit/query | Clifford frame | Linear fusion | Jya recurrence |
| --- | ---: | ---: | ---: |
| One qubit, (H,T) repeated 512 times, Y | 0.774 s | 1.154 s | 0.624 s |
| Entangled GHZ, 2056 sites, 256 repeats on q0, global X | 0.727 s | 0.610 s | 0.383 s |
| Entangled GHZ, 2056 sites, 64 repeats on q0, full zero assignment | 2.547 s | 2.483 s | 2.450 s |
| Three sites, changing returns interleaved with CX | 0.167 s | 0.207 s | 0.177 s |
| Twelve independent H,T sites, global X | 0.702 s | 0.967 s | 1.050 s |
| Clifford-only GHZ, 2056 sites, global X | 0.123 s | 0.117 s | 0.115 s |

Times are median whole fresh-process wall times, including startup. The
2056-site repeated/global case is about 1.90x faster than the old frame and
1.59x faster than linear fusion. The full-assignment case remains dominated
by generator readout; its small timing difference is not a robust speed claim.
The independent-phase case is about 1.49x slower than the old frame.

For the 512-repeat local word, linear fusion uses 8,200 scalar matrix products;
the recurrence route uses 30 local products plus 60 recurrence products.
Both retain two residual amplitudes with the same maximum coefficient size.
This isolates a recurrence arithmetic saving while showing that Python,
exact-number and process overhead remain in the wall measurement.

Maximum measured RSS across the paired cases is approximately 25.2–27.2 MiB.
It includes interpreter/import overhead; these runs do not establish a memory
improvement. Different algorithms' work counters are not CPU-instruction counts.

References use independent sequential two-by-two multiplication with analytic
GHZ/Y identities, unchanged exact Pauli expansion for the changing-return
case, and analytic 1/64 and 1 controls. No reference answer is generated by
the new recurrence. Small full complex-state comparisons also use Qiskit.

## Use

```python
from native_relational_qc.large_register import LargeCircuit
from native_relational_qc.jya_frame import expectation

circuit = LargeCircuit(2056).add('h', 0)
for q in range(2055):
    circuit.add('cx', q, q + 1)
for _ in range(256):
    circuit.add('h', 0).add('t', 0)
answer = expectation(circuit, {q: 'X' for q in range(2056)})
print(answer.value.to_dict())
print(answer.statistics)
```

For the JSON calculator select `"backend": "jya_frame"`. Probability,
expectation, distribution and EMK geometry queries are supported. The gate
alphabet is the same as `clifford_frame`; CH/CS/CT/CCX are rejected before
simplification. Continuous rotations, noise and arbitrary input states are
not added. See the runnable [example](calculator_examples/jya_return.json)
and [its result](calculator_examples/jya_return.result.json).

Defaults remain 10 million work units, 4096 coefficient bits, 4096 residual
branches, one million candidate pairs and 2056 measurement generators.
Coefficient inspection includes compilation/recurrence intermediates, which
can exceed the final result's size. Budget failure returns no approximate
value. The CLI's default 20-second wall cap covers its child batch; no hard
RSS cap is claimed. The benchmark uses the same caps except its explicit guards.

## Validation and reproduction

**231 native test methods pass, with no failures, errors or skips**, including
12 new methods. The new checks cover the rational jya witness; periodic and
partial-tail words; every small output; full complex state without global-phase
alignment on 31 Qiskit cases; changing noncommuting blocks; sine-blind order
readings; retained R²=-I; entangler/wire boundaries; a 2056-site entangled joint
probability; all failure guards; and calculator/geometry integration.

```bash
python -m unittest discover -s tests -p 'test_native*.py' -v
python -m native_relational_qc.jya_qualification --run \
  --out /tmp/jya_rerun.json
python -m native_relational_qc calculate \
  native_relational_qc/calculator_examples/jya_return.json
```

The protocol refuses changed Python/test hashes. Historical protocols and
results remain immutable snapshots of their own commits; shared-file edits
mean those earlier protocols must be replayed at their original revisions.
See [test output](jya_test_results.txt) and [verification](jya_verification.json).
