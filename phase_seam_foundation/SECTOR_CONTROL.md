# Continuous control inside the native closure sector

Author: Monty. Version 0.8. Status: conditional operator theorem, native
control targets and exact verification through the existing calculator.

The previous controller preserves the phase sum at source-operation
boundaries. Its binary arithmetic can leave the sector between gates.
This extension constructs a different **continuous operator path** that
stays in the sector for every real pulse angle. It also supplies binary
verification circuits for exact samples of that path. Those circuits are
not themselves a physical implementation confined to the sector.

## 1. Reuse, scope and assumptions

All seven branch heads were rechecked; the other six tips remain at the
previously audited commits. Existing `JOINT_READOUT.md` already specifies
a two-site EMK coupling. It does not implement the four-mode phase-sum
controller. `sector_control.py` reuses:

- the v0.7 controller's source admission, layouts, records and history;
- the existing full/compressed phase-register compiler and closure codec;
- the existing constant adder and controlled-gate ladder;
- `Phase64Circuit` and its exact arithmetic for verification.

No second amplitude simulator or probability engine is added. The existing
source model, controller and calculator implementations remain unchanged.

The derivation starts with native label transformations, involutions and
projectors. Interpreting them as coherent quantum operations retains the
earlier complex adjoint, positive-state, composition and orthogonal-label
assumptions. Their finite representation is compatible with ordinary
Hilbert-space quantum mechanics; this is not a claim to have disproved or
eliminated that representation.

The **new engineering assumption** is access to the specified native
generator, with a controllable real pulse area. The pointer register is a
spectator under the *data* closure operator: that operator counts only the
four native modes. A material implementation must realize this assignment
or explicitly account for any extra physical charge carried by the pointer.
The logical modular sum is not automatically electric charge, energy or
particle number.

Hamiltonian control that stays inside an encoded subspace is established
in prior quantum-control work; see
[Kempe, Bacon, Lidar and Whaley](https://arxiv.org/abs/quant-ph/0004064).
Here the specific objects are the native phase-sum sectors and their
retained-record operations. The paper's decoherence-free noise assumptions,
universality and two-body exchange constructions are not imported as
properties of this code.

## 2. Balanced reset as an involutive exchange

Let \(L=2^w\), with \(j\ne b\). Write the data phases as \(x\), the new
pointer value as \(m\), and the reset reference as \(a\). All arithmetic
in this section is modulo \(L\). Define
\[
P_{j,b,a}:\quad
(x_j,x_b,m)\longmapsto
(a+m,\ x_b+x_j-a-m,\ x_j-a).
\]
Other data modes and earlier records are unchanged.

Two direct identities give the construction:
\[
x'_j+x'_b=x_j+x_b\pmod L,\qquad P_{j,b,a}^2=I.
\]
For the second identity, a second application gives
\(x_j''=a+(x_j-a)=x_j\), \(m''=(a+m)-a=m\), and \(x_b''=x_b\).
Thus \(P\) is a permutation involution and \(P^\dagger=P\).

On a fresh record \(m=0\),
\[
|x_j,x_b,0\rangle\longmapsto
|a,x_b+x_j-a,x_j-a\rangle .
\]
This is exactly the v0.7 balanced-reset isometry, including all amplitudes
and reference correlations. On a dirty record it is a **different unitary
extension** from the earlier read-then-shift construction. The new extension
is deliberate: it is its own inverse and preserves the data sum for every
record value.

In coordinates \(u=x_j-a\), \(q=x_j+x_b\), the operation simply exchanges
\(u\) and \(m\) while keeping \(q\) fixed. This gives a useful engineering
target without claiming that a change of coordinates supplies a material
interaction.

## 3. All-angle conservation theorem

Let \(Q_s\) be the projector onto data labels with
\(\sum_i x_i=s\bmod L\), tensored with identity on records. Every involution
used below obeys
\[
P^\dagger=P,\qquad P^2=I,\qquad [P,Q_s]=0
\]
for every residue \(s\). Equivalently, it commutes with the modular closure
operator \(C|x,m\rangle=e^{2\pi i\sum_i x_i/L}|x,m\rangle\).

Define the orthogonal spectral projectors and the proposed control path:
\[
E_+=\frac{I+P}{2},\qquad E_-=\frac{I-P}{2},\qquad
U_P(\theta)=E_++e^{-i\theta}E_-.
\]
From \(P^2=I\), one obtains
\(E_\pm^2=E_\pm\), \(E_+E_-=0\), and \(E_++E_-=I\). Therefore, for all
real \(\theta,\phi\),
\[
U_P(\theta)^\dagger U_P(\theta)=I,\quad
U_P(\theta)U_P(\phi)=U_P(\theta+\phi),\quad
[U_P(\theta),Q_s]=0.
\]
The last identity follows because both projectors are polynomials in \(P\).
Also \(U_P(0)=I\) and \(U_P(\pi)=P\), with no omitted relative or global phase.

Consequently an input in sector \(s\) remains there at **every real point
of this operator path**, including coherent superpositions and states
entangled with an external reference. This is an algebraic all-angle
statement. The finite numerical samples below are checks of its implementation,
not a replacement for the proof.

If a laboratory implements
\[
H_P(t)=\hbar g(t)E_-,\qquad
\theta(t)=\int_0^t g(\tau)\,d\tau ,
\]
then its evolution is \(U_P(\theta(t))\), since generators at different
times commute. An integrated area \(\pi\) completes the involution.
At \(\theta=\pi/2\), a basis state not fixed by \(P\) has amplitudes
\((1-i)/2\) on its old label and \((1+i)/2\) on its partner. Each has
probability \(1/2\); both labels remain in the same sector.

The laboratory parameter \(t\) and rate \(g\) are added controls. This
does not derive the native time tensor, an absolute gate duration, or a
thermal-energy law. Partial pulse angles need not implement a completed
reset or have a unique classical four-phase trajectory.

## 4. Supported native operations

The control adapter supports these source operations:

| Source operation | Involution target(s) | Retained record |
| --- | --- | --- |
| `pair_cut(j,b,h)` | Existing balanced reflection \(x_j'=h-x_j,\ x_b'=x_b+2x_j-h\) | None |
| `swap(j,b)` | Existing data-mode swap | None |
| `pair_shift(j,b,d)` | Balanced reflection at 0, then at \(d\) | None |
| `read(j,a)` | Pointer reflection \(m'=x_j-a-m\), data unchanged | Fresh width-bit pointer |
| `pair_reset(j,b,a)` | Balanced exchange in Section 2 | Fresh width-bit pointer |

Every listed involution preserves the data sum. The two completed reflections
for pair_shift give \((x_j,x_b)\mapsto(x_j+d,x_b-d)\). Their intermediate
native pulse paths also stay in the sector.

The read reflection is another explicit dirty-record extension; for \(m=0\)
it agrees with the previous controller. It does not clone an unknown state:
it correlates a pointer with the relative phase label. New records remain
allocated and may become entangled.

General cut, single-mode shift/shear and ordinary reset are outside this
adapter's declared control alphabet. Its ordinary reset restriction is
not relaxed. The original compiler remains available for those operations
on its previously admitted domains.

Each completed source word agrees with the old controller on fresh record
inputs. Intermediate pulse angles are coherent control states, not extra
classical Cell events. In particular, the two pulse targets used to synthesize
one pair_shift are not silently added to the source charged-cut counter.
That counter remains an external declared accounting rule, not physical
pulse-energy accounting.

## 5. Compressed code and endpoint synthesis

For known closure sign and twist, let \(J\) insert the omitted phase
\(x_o=s-\sum_{i\ne o}x_i\bmod L\). Restrict each permutation to that code:
\[
P_{\rm full}J=JP_{\rm reduced}.
\]
Applying the same polynomial formula gives
\[
U_{\rm full}(\theta)J=JU_{\rm reduced}(\theta)
\]
for all real angles. Unlike the v0.7 read/shift extension, the new balanced
exchange and pointer reflection have the **same reduced action even on
dirty pointer values**. Exact tests compare all omissions, including the
reset mode itself.

For binary endpoint verification, the balanced exchange is synthesized as
\(A^{-1}SA\), with \(S\) a register swap:

- If both participating modes are stored, \(A\) subtracts \(a\) from the
  target and adds that result to the reservoir.
- If the reservoir is omitted, \(A\) only subtracts \(a\) from the target;
  its compensation is derived from closure.
- If the target is omitted, \(A\) uses the existing compressed mode swap
  to put the derived target into the reservoir coordinate, then subtracts
  \(a\). The register swap exchanges that coordinate with the record.

The endpoint gate word is a conjugated swap, using the existing arithmetic.
It realizes the stated label map with clean carry workspace. This is a
verification and endpoint synthesis route; the gates inside \(A\) do not
provide the continuous native Hamiltonian above.

## 6. Exact fractional verification without a new simulator

The identity
\[
U_P(\theta)=\alpha I+\beta P,\qquad
\alpha=(1+e^{-i\theta})/2,\quad
\beta=(1-e^{-i\theta})/2
\]
has exact coefficients in the existing \(\mathbb Q(\zeta_{64})\) field
when \(\theta=k\pi/32\). `pulse_coefficients(k)` exposes those coefficients
for integer \(k\in[-64,64]\).

`verification_circuit(phase_steps)` exports a circuit to the existing
`Phase64Circuit` engine. A clean flag detects the \(P\)-eigenspace through
`H → controlled-P → H`. A phase \(e^{-i\theta}\) on flag value 1, followed
by uncomputation, yields \(U_P(\theta)\) and restores the flag. One additional
clean ladder bit implements the extra control on existing CCX gates.
The phase engine, probability implementation and exact fields are unchanged.

These are two extra **verification** wires. Controlled-P is decomposed
into the existing binary arithmetic; its physical intermediate path may
leave the native sector. Agreement at gadget boundaries verifies the
sampled operator, not a pulse implementation of \(H_P(t)\). A negative
test explicitly detects sector excursions in both the previous controller
and the new binary endpoint synthesis.

Example: half of a balanced exchange on the grid-64 compressed code:

```python
from fractions import Fraction
from phase_seam_foundation.model import Config, Operation
from phase_seam_foundation.sector_control import compile_sector_control
from native_relational_qc.phase_backend import Phase64Circuit, prepare

program = compile_sector_control(
    (Operation("pair_reset", (0, 2, 0)),),
    config=Config(sector=1), omit_mode=2,
)
# Stored target 1 means the derived reservoir is 63, keeping sum = 0 mod 64.
circuit = Phase64Circuit(program.n_qubits + 2).add("x", 0)
for name, wires in program.verification_circuit((16,)).operations:
    circuit.add(name, *wires)
state = prepare(circuit)
assert state.probability({q: 0 for q in program.controller.layout.registers[0]}) == circuit.field(Fraction(1, 2))
assert all(sum(program.controller.unpack(label)[0]) % 64 == 0 for label in state.amplitudes)
```

At 32 steps the reset completes; at 0 steps nothing changes. Two 16-step
pulses equal the 32-step endpoint, including phases. Negative angles undo
the corresponding coherent evolution. Inverse recovery still requires
available coherent records.

## 7. Resources and bounds

For `pair_reset(0,2,0)` at grid 64, sign +1 and twist 0:

| Layout | Allocated endpoint wires | New endpoint gates | Previous endpoint gates | Half-angle verification wires / gates |
| --- | ---: | ---: | ---: | --- |
| Full | 34 | 140 | 193 | 36 / 740 |
| Omit target 0 | 28 | 570 | 439 | 30 / 2968 |
| Omit unrelated mode 1 or 3 | 28 | 140 | 193 | 30 / 740 |
| Omit reservoir 2 | 28 | 18 | 132 | 30 / 56 |

Endpoint widths retain the inherited four arithmetic workspace bits and
six record bits. The abstract native generator leaves carry workspace
inert. These are logical allocations; a physical mode may require a
different encoding and more hardware.

Each balanced reset is one **native involution target**, not one demonstrated
physical pulse or elementary quantum gate. In the full description it
couples two \(L\)-level data modes and one \(L\)-level pointer. No one-body
or two-body qubit-local realization, locality bound, optimal gate count or
hardware speedup is inferred. Target omission is costlier in this synthesis.
Full/compressed conversion remains separate and can itself leave the sector;
direct preparation or a compatible physical encoding is still needed.

The adapter inherits controller source/record bounds and its 256-wire cap,
limits native targets to 2048, and bounds endpoint synthesis to 100,000
gates. Fractional verification has its own 100,000-gate cap and requires
two more wires within the same 256-wire IR. A valid native plan can therefore
fail binary verification export at a tighter resource cap. No partial circuit
is returned on failure.

## 8. Symmetry errors versus pulse errors

If every realized control term commutes with \(Q_s\), arbitrary pulse-shape
and area errors still preserve that sector. They can give the wrong logical
answer or an incomplete reset. Sector preservation alone is not gate fidelity.
Overlapping symmetric drives also preserve the sector, although they need
not realize the intended ordered source word.

For a closed finite system with ideal \(H_0(t)\) commuting with \(Q=Q_s\),
write the actual Hamiltonian as \(H_0(t)+V(t)\). Starting in \(Q\), put
\[
\epsilon(t)=\int_0^t
\frac{\|(I-Q)V(\tau)Q\|}{\hbar}\,d\tau .
\]
The complementary component satisfies an inhomogeneous Schrödinger equation
with Hermitian within-complement generator and source \((I-Q)VQ\psi_Q\).
Variation of constants, unitarity inside the complement, and
\(\|\psi_Q\|\le1\) give
\[
\|\psi_{I-Q}(t)\|\le\epsilon(t),\qquad
p_{\rm leak}(t)\le\min(1,\epsilon(t)^2).
\]
The same bound extends to mixed inputs supported in \(Q\) by convexity.
No measured value of \(\epsilon\) is supplied. This does not model arbitrary
open-system noise, establish decoherence-free behavior, or protect logical
coherence within a sector.

The negative control uses a single data-bit \(X\) in place of the balanced
involution. Its half-angle path from all-zero data places exactly \(1/2\)
of the probability outside sum-zero closure. Native balanced-exchange
samples have exactly zero leakage. This is a concrete acceptance distinction
between a symmetric generator and an endpoint-only check.

## 9. Qualification and remaining work

The existing serial audit passes **170 tests in 110.823 seconds**, with
no failures, errors or skips: 14 control tests plus the prior 156.
New checks cover
exhaustive grid-4 full involutions including dirty records; compressed
sign/twist/omission checks; every supported width; clean endpoint agreement;
exact coefficient group/unitarity identities; fractional verification with
ancilla cleanup; full/compressed equality and external reference coherence;
inverse recovery; negative controls; and resource/tampering guards.

Run `python benchmarks/phase_seam_register_audit.py`.
[Qualification](register_qualification.json) ·
[Source/reuse manifest](register_source_manifest.json) ·
[Test output](register_test_results.txt).
Source/gate verifiers recompile shared code and are consistency checks,
not independent formal theorem provers. The finite proofs above, independent
label/bit interpretations and the existing exact phase engine supply
different checks. Full native/Shor suites and hardware jobs are not rerun.

Closed mathematically under the declared quantum assumptions: an explicit
all-angle closure-preserving path for the admitted native controls,
including balanced reset with retained information, plus compressed-code
compatibility and an off-sector perturbation criterion.

Unresolved physically: a material carrier realizing the generator, pointer
charge assignment, locality and interaction synthesis, calibration of
coupling/time/energy, leakage and coherence measurements, initialization
and record recycling. Coherent unwrapped lift/path/cost storage remains open.
The next hardware milestone is a carrier-specific implementation of this
interaction and its intermediate-angle acceptance tests.
