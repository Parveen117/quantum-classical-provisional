# Native read/reset with retained controller records

Author: Monty. Version 0.6. Status: finite coherent record model, executable
gate compiler and export to the existing dynamic measurement engine.

The phase-register model can now read a native phase and reset a mode while
retaining its old relative phase in an explicit register. The original
reversible compiler remains unchanged in scope: it still rejects read/reset.
`controller.py` composes that compiler with record operations.

## 1. Existing work reused

The seven branch heads were rechecked before development; the other six tips
were unchanged from the earlier complete tree audit. Local searches found
measurement, reset and feedback already implemented in
[dynamic.py](../native_relational_qc/dynamic.py) and documented in
[DYNAMIC.md](../native_relational_qc/DYNAMIC.md). The existing `joint.py`
also implements positive states, projector branches and complete channels.

Those engines have not been recreated. The missing part was translation of
the native **multi-bit phase read/reset** operations into an explicit
data-plus-record circuit with storage accounting. This adapter reuses:

- `register.py` for full/compressed layouts, reversible source operations
  and whole-sector checks;
- `modular_arithmetic._add` for exact constant arithmetic and carry cleanup;
- `DynamicCircuit` for record measurement, classical outcomes and later feedback;
- `phase_backend.prepare` for exact coherent verification;
- the original `Cell` for lift, Gamma, event order, outcome and cost replay.

The [source manifest](register_source_manifest.json) records this check and
the choices added here. No existing IBM experiment was submitted or modified.

## 2. What the record contains

For grid \(L=2^w\), the native relative reading is
\[
r=(x_j-a)\bmod L.
\]
Each read or reset receives its own fresh \(w\)-bit record \(M_k\), initially
\(|0\rangle\), in a product state with the data and all other registers.
Temporary carry workspace is separate and is returned to zero.

The record contains a **wrapped relative phase label**. It does not contain
the unwrapped lift, elapsed physical time, full path, Gamma or charged-cut
cost. Those remain in the original classical Cell and source instruction
tape. Calling this a coherent record of the complete native history would
be incorrect.

Before measurement, a record is a quantum subsystem; superpositions can
entangle it with the data. Reading it into classical bits is a separate
operation. The adapter allocates a fresh record for every event and never
overwrites an earlier one. This is a transparent allocation policy, not a
claim of minimum memory for an entire protocol.

## 3. Read as an isometry and an instrument

On clean record input the compiler implements
\[
W_{j,a}|x\rangle|0\rangle_M
 =|x\rangle|x_j-a\bmod L\rangle_M.
\]
For a stored mode, bitwise CX gates copy its basis label to the fresh
record, followed by the existing constant adder for \(-a\). The data
register is unchanged. If the requested mode was omitted by fixed-sector
compression, the compiler computes
\[
r=s-a-\sum_{i\ne j}x_i\pmod L
\]
directly into the record using existing controlled additions. It does not
materialize a hidden fourth phase register.

This copies a basis label. For \(\sum_x c_x|x\rangle\), the result is
\(\sum_xc_x|x\rangle|r(x)\rangle\), generally an entangled state, not a
second copy of the unknown input quantum state.

Let \(P_r\) project onto labels with \(x_j-a=r\bmod L\). The orthogonal
projectors sum to identity on the chosen data domain, and
\[
W=\sum_r P_r\otimes|r\rangle,\qquad W^\dagger W=\sum_rP_r=I.
\]
For an arbitrary input density operator \(\rho\), measuring the record
gives the unnormalized branch
\[
\mathcal I_r(\rho)=P_r\rho P_r,\qquad
p_r=\operatorname{Tr}(P_r\rho).
\]
Thus \(p_r\ge0\), \(\sum_rp_r=1\); normalization of a selected branch is
only defined when \(p_r>0\). Ignoring the record produces
\[
\mathcal D(\rho)=\sum_rP_r\rho P_r.
\]
Coherences between different readings disappear from the reduced data,
while the full coherent data-plus-record state retains their phases.
This agrees with the original nondisturbing classical read on diagonal
basis-label mixtures. It adds the existing quantum measurement law for
coherent inputs; that law is not derived from the classical phase rules.

## 4. Reset transfers information into the record

For a full unrestricted phase register, the clean-record action is
\[
V_{j,a}|x_j\rangle|0\rangle_M
   =|a\bmod L\rangle|x_j-a\bmod L\rangle_M.
\]
Other data modes remain untouched. The implementation shifts the data by
\(-a\), swaps its bits with the record using three CX per bit, then shifts
the data by \(a\). On an arbitrary, possibly dirty record value \(y\), the
complete reversible map is
\[
|x_j,y\rangle\longmapsto|a+y,\ x_j-a\rangle\pmod L.
\]
The displayed arithmetic action assumes clean carry workspace. The complete
elementary gate word remains invertible even with dirty workspace, but then
the declared arithmetic promise need not hold. Dirty record input does **not** reset the data to the requested
reference; it is never silently cleared.

The reset Kraus operators on mode \(j\) are
\[
K_r=|a\rangle\langle a+r|,\qquad
\sum_rK_r^\dagger K_r=I.
\]
For that mode and all other systems \(B\), including an external reference,
\[
\operatorname{Tr}_M(V\rho_{jB}V^\dagger)
=|a\rangle\langle a|_j\otimes\operatorname{Tr}_j\rho_{jB}.
\]
The remote marginal is unchanged. The old local quantum state and its
correlations are transferred to the coherent record, with the declared
reference shift. Measuring that record adds the pointer-basis dephasing.

The complete circuit has an inverse while **all records remain coherent
and available**. Inverting its gate list does not reverse an actual
measurement, discarded record, lost coherence or thermodynamic erasure.

These are explicit finite instances of the established Kraus/Stinespring
channel construction; see John Watrous,
[The Theory of Quantum Information, `2.2 / Corollary 2.27](https://jhwatrous.github.io/TQI.pdf).
The contribution here is the native-operation implementation, source matching,
and accounted registers, not a new theorem asserting that arbitrary reset
is reversible on the data alone.

## 5. Full gate action and memory preconditions

The clean-record equations are the public instrument contract. For dirty
records, the emitted unitary extensions are explicit:

| Operation | Record/data action modulo \(L\) |
| --- | --- |
| Read stored mode | data unchanged, \(y'=(y\mathbin{\mathrm{XOR}}x_j)-a\) |
| Read omitted mode | data unchanged, \(y'=y+x_j-a\), with \(x_j\) reconstructed |
| Reset stored mode | \(x_j'=a+y,\ y'=x_j-a\) |

The two read extensions agree on the required clean input. The bitwise XOR
in the first row is not modular addition. Tests exercise dirty inputs and
their complete inverses. All carry ladders require clean workspace for the
declared arithmetic semantics; no new workspace-reset instruction is added.

For a single exact reset of an arbitrary \(L\)-label input, with all other
inputs fixed and one common output data state, a reversible environment
must distinguish \(L\) orthogonal alternatives. Indeed,
\(\langle x|y\rangle=\langle a|a\rangle\langle e_x|e_y\rangle\) forces
\(\langle e_x|e_y\rangle=\delta_{xy}\). This construction uses \(w=\log_2 L\)
record bits for that local information. It does **not** prove that \(m\)
events need \(mw\) independent bits: repeated readings can be perfectly
correlated and entire histories may permit compression.

## 6. Fixed-closure reset boundary

If the data initially obeys \(\sum_i x_i=s\bmod L\), resetting only mode
\(j\) gives
\[
\sum_i x_i'=s-x_j+a\pmod L.
\]
This preserves the same sector only on the subset \(x_j=a\bmod L\), not
on every allowed input. A state-specific no-change example does not justify
a channel on the whole fixed sector.

The controller therefore supports:

| Layout | Read | Single-mode reset |
| --- | --- | --- |
| Full unrestricted, sector 0 | Supported | Supported with retained record |
| Full fixed sector | Supported | Rejected |
| Compressed fixed sector | Supported, including omitted mode | Rejected |

A balanced reset with compensating transfer into another native mode would
be a separate operation and model extension. It has not been silently
substituted for the original reset. The compiler does not release or change
the user's closure constraint automatically.

## 7. Existing measurement and feedback engine

`to_dynamic(preparation=...)` returns the existing `DynamicCircuit`. It
appends the compiled coherent gates, then measures each record bit into
its own classical bit. The order is record-event order, little-endian
within each record. The existing engine computes exact joint probabilities
and supports subsequent classical feedback.

This terminal measurement is equivalent to measuring each record just
after its creation because later controller operations never touch that
record. This equivalence applies to the current straight-line program;
adaptive native instructions between events are not implemented here.

```python
from phase_seam_foundation.model import Config, Operation
from phase_seam_foundation.controller import compile_controller
from native_relational_qc.dynamic import probability
from fractions import Fraction

program = compile_controller(
    (Operation("read", (0, 0)), Operation("reset", (0, 0))),
    config=Config(grid=4),
)
circuit = program.to_dynamic((("h", (0,)), ("t", (0,))))
assert probability(circuit, quantum={0: 0, 1: 0}).value.a == 1
assert probability(circuit, classical={0: 1, 1: 0, 2: 1, 3: 0}).value.a == Fraction(1, 2)
```

The preparation uses the dynamic engine's existing exact named gate alphabet.
The caller owns the clean-record, clean-workspace and fixed-sector input
conditions. A classical outcome measurement does not demonstrate that a
physical carrier prepared those conditions.

`bind_controller(cell,program)` replays the unchanged original Cell,
retains every event, and returns its ordered read/reset outcomes. Existing
lift, cost, parameter and event limits remain enforced. This binding is for
known classical source data, not for copying an unknown coherent history.

## 8. Counted resources and qualification

Each row uses grid 64. The compressed example has sign +1, twist 0 and
omitted mode 2.

| Program | Phase bits | Workspace | Records | Total wires | Logical gates |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full read(0,0) | 24 | 4 | 6 | 34 | 6 |
| Full reset(0,0) | 24 | 4 | 6 | 34 | 18 |
| Full read(0,1), reset(0,2) | 24 | 4 | 12 | 40 | 99 |
| Compressed read(2,0), derived omitted label | 18 | 4 | 6 | 28 | 378 |

Workspace is the inherited fixed allocation even when a particular word
does not need every workspace bit. Records are additional retained storage,
not recycled scratch. Measurement export also reserves the corresponding
classical output bits; it does not free or erase record qubits.

Default maximum retained records: 16; configurable up to 64, still subject
to the existing 256-wire IR cap. The total is
\[
(4\ \text{or}\ 3)w+(w-2)+mw.
\]
The compiler also applies the 100,000-gate cap and original source limits.
Exceeding a limit returns no partial program. These logical counts do not
include physical routing, pulse synthesis, noise correction, energy or time.

The current [qualification](register_qualification.json) includes exact
record outcomes, coherent reset amplitudes, dynamic measurement comparisons
and counts. [Test output](register_test_results.txt) and source hashes are
regenerated by:

```bash
python benchmarks/phase_seam_register_audit.py
```

The 16 new controller tests cover all grid-4 full inputs for both operations,
every mode and reference; all grid-64 values/references for one mode;
compressed readings under both signs, four twists and four omissions;
all supported widths; ordered records; dirty memory; tampering and budgets.
Coherent tests check record-induced reduced-state dephasing, exact phase
retention, transfer of reference entanglement, unchanged remote marginals,
inverse recovery and correlated repeated reads. Exported instruments and
feedback are compared with the earlier dynamic engine.

Seven relevant existing dynamic checks and all 117 previous targeted
foundation/calculator checks are retained: **140 tests pass in 52.509 seconds**,
with no failures, errors or skips. The full native/Shor suite and
hardware jobs are not rerun.

## 9. Closed interface and open physical work

Closed within the declared circuit model: finite native phase read/reset,
explicit pointer records, exact source outcomes, coherent information
transfer, measured joint outcomes through the existing engine, and bounded
memory/gate accounting.

Added choices: fresh zero product records, one record per event, declared
pointer basis, terminal measurement export and no record reuse. The earlier
quantum probability/composition assumptions remain in force.

Open: physical record initialization and calibration, a native
closure-preserving balanced reset, coherent unwrapped winding/cost records,
record recycling and environment/heat accounting, and physical carrier
dynamics. Logical reversibility does not establish a thermal-energy law.
