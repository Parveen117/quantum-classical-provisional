# NRQC-3: exact cut pairing with measurement and classical memory

Status: algebraic derivation for the declared circuit model, with bounded
computational verification. This extends NRQC-2 from unitary circuits to quantum
instruments and classical feedback. It uses established channel duality, Pauli
algebra and the Fourier/Walsh basis of binary classical memory. These are not
claimed as new physical laws or newly discovered simulation principles.

## 1. State, observer and pairing

At a cut, let the classical memory be c in {0,1}^m. A joint state is a family of
unnormalized positive matrices rho_c with sum_c Tr(rho_c)=1. An observation is a
Hermitian matrix-valued function F(c). Its reading is

\[
 \langle F,\rho\rangle=\sum_c\operatorname{Tr}(F(c)\rho_c).
\]

For a trace-preserving instrument E, define its dual by

\[
 \boxed{\langle F,E(\rho)\rangle=\langle E^*(F),\rho\rangle.}
\]

**Theorem (dynamic cut compatibility).** Transporting the requested observation
backwards by each instruction's exact dual preserves this reading at every cut.
The final source evaluation equals the requested output reading, including
measurement outcomes, overwritten memory, reset and conditional gates.

Proof: apply the displayed identity successively to the finite composition of
instructions. The local identities are derived below. The source is the declared
all-zero quantum state and all-zero classical memory. Preparing another input is
part of the circuit. A dual observable map does not assert a physical inverse of
an irreversible measurement.

The implementation expands F in the basis

\[
 F(c)=\sum_{x,z,s} a_{x,z,s} P(x,z)\chi_s(c),\qquad
 P(x,z)=i^{|x\cap z|}X^xZ^z,\quad
 \chi_s(c)=(-1)^{s\cdot c}.
\]

Here P is a Hermitian tensor product of I/X/Y/Z and chi_s is a classical parity
character. Products of characters obey chi_s chi_t=chi_(s XOR t). Coefficients
are retained exactly in Q(sqrt(2),i); the Hermitian observer coefficients are real.

## 2. Measurement with overwrite

Measure quantum site q in the Z basis and overwrite classical bit j. Write
Pi_b=(I+(-1)^b Z_q)/2. Its dual is

\[
 (M_{q\to j}^*F)(c)=\sum_{b=0}^1\Pi_b F(c[j\leftarrow b])\Pi_b.
\]

Proof: a forward branch has matrix Pi_b rho_c Pi_b and destination memory
c[j<-b]. Move each projector around the trace and sum the old memories. This
includes both old values of the overwritten bit; no old outcome is implicitly
retained in the current classical register.

For a basis term P(x,z) chi_s, set a=s_j. Substitution gives
chi_(s without j)(c) sum_b (-1)^(ab) Pi_b P Pi_b. Therefore:

- If x_q=1, the term vanishes because Pi_b X Pi_b=Pi_b Y Pi_b=0.
- If x_q=0 and a=0, retain the Pauli term and remove j from its character.
- If x_q=0 and a=1, toggle z_q and remove j from its character.

This is precisely the term map in `dynamic.py`. Removing X/Y here is licensed by
the measurement channel itself. It is not premature evaluation against the
initial |0> boundary. Later basis changes and correlations are still carried.

## 3. Reset, conditional gates and rational noise

**Reset.** The forward channel replaces site q by |0><0| while tracing its old
state. The dual maps the local Pauli factors I,Z to I and X,Y to zero. Other
quantum sites and classical memory are unchanged. Consequently, reset can remove
entanglement while retaining an earlier measurement's classical correlation.

**Conditional gate.** For an equality predicate d(c) in {0,1}, apply U when
d(c)=1. The dual action is

\[
 F\longmapsto F+d(c)(U^\dagger F U-F).
\]

For the conjunction c_j=b_j over a set J,

\[
 d(c)=\prod_{j\in J}\frac{1+(-1)^{b_j}\chi_{\{j\}}(c)}2.
\]

This gives an exact character expansion, including conditions on zero bits.
Multiplication uses XOR of character masks. If the complete difference
U^dagger F U-F vanishes, the predicate need not be expanded. Conditions use the
memory at that instruction; later overwrites are propagated backwards first.

**Pauli mixture.** With nonnegative rational weights w_A summing to one,
N(rho)=sum_A w_A A rho A. For a Pauli P its dual is

\[
 N^*(P)=\left(\sum_A w_A\,\epsilon(A,P)\right)P,
 \qquad \epsilon(A,P)\in\{-1,+1\}.
\]

The sign is determined by Pauli anticommutation. The implementation supports
single-site I/X/Y/Z mixtures. This is an explicit synthetic channel model; the
weights are not inferred from hardware or fitted to make the checks pass.

## 4. Exactness and the meaning of a query

The supported unitary matrices have entries in Q(sqrt(2),i). Projectors introduce
only rational halves; character products introduce signs; Pauli channels use
rational weights. Thus every dual step stays in this number field. No square
root of a branch probability or normalized conditional state is needed.

For a joint quantum Z outcome and classical event, the final observation is the
product of their projectors/indicators. Unspecified outputs are marginalized.
For a Pauli expectation with a classical event, the answer is the **joint moment**
E[P 1_event], not the conditional expectation E[P|event]. The latter requires
division by P(event), and is undefined when that denominator is zero.

On the all-zero source, each classical character is +1 and a quantum Pauli has
expectation zero if its x mask is nonzero, otherwise +1. Summing the surviving
coefficients therefore gives the exact reading. Every coefficient is retained;
only exact zeros are removed. Finite tests verify implementations on stated
inputs and are not an exhaustive machine proof of all code paths.

## 5. Resources and explicit limits

Let G be the instruction count, S the largest term dictionary, B the largest
coefficient bit length and k the largest conditional predicate width. Local
unitary gates involve at most three qubits. A direct conservative arithmetic
bound is O(G S 2^k), in addition to exact arithmetic and integer-mask costs. A
requested r-bit joint outcome initially has 2^r terms in this representation.
S and B are not guaranteed to remain small for general circuits.

The evaluator bounds individual term dictionaries, coefficient lengths and
counted work. Multiple current/temporary dictionaries can coexist; `peak_terms`
is their largest individual size, not total bytes or peak process memory. Local
unitary transfer tables use the bounded caches inherited from NRQC-2.

Budgets raise ResourceLimit, never silently truncate. A query does not mutate its
circuit. The code does not enumerate measurement trajectories, but that alone
does not imply polynomial complexity: terms and classical predicates can grow
exponentially. Explicit loops and general classical programs are outside the IR;
the examples unroll a finite number of rounds.

## 6. Recovery readings and what they establish

For an external reference entangled with the input logical qubit, define the
decoded Bell projector

\[
 B=(II+XX-YY+ZZ)/4,\qquad F_e=\langle B\rangle.
\]

**Theorem (identity-channel reading).** If a completely positive trace-preserving
qubit channel gives F_e=1 on half of a maximally entangled pair, its channel on
that qubit is the identity.

Proof: the normalized Choi state is positive with trace one. Unit expectation
of the rank-one Bell projector forces that state to equal the Bell projector.
The channel's action on every matrix unit is determined by the Choi state, so it
equals the identity channel. This is the standard Choi-state argument, not a new
criterion particular to this framework.

The recorded Shor workload checks the three readings exactly for no error and
each of 27 single-site Pauli errors. All give XX=1, YY=-1, ZZ=1. The ideal model
therefore passes this complete logical-qubit reading in those cases; it is more
informative than checking only a computational-basis output. The eight syndrome
bits are also checked against their expected deterministic values. This is a new
ideal recovery circuit, not a replay of a measured IBM hardware job.

For the three-qubit bit-flip code, independent X error probability p on each data
qubit gives a logical X error exactly when two or three data errors occur:

\[
 p_L=3p^2(1-p)+p^3=3p^2-2p^3.
\]

After each ideal correction, the state returns to the code space. Independent
rounds compose this logical I/X channel. Its XX reading is one, while the ZZ
reading is (1-2p_L)^r and YY is its negative. Thus

\[
 \boxed{F_e(r)=\frac{1+(1-2p_L)^r}{2}.}
\]

At p=1/10, p_L=7/250 and F_e(1)=243/250. The reported runs calculate this value
through 128 rounds, with the final fidelity decaying toward 1/2 as predicted.
Compact calculation of that degradation is not a claim of perfect long-term
error correction. Syndrome gates and readout are ideal in this noise example.

## Attribution and operational references

- [IBM Quantum: channel basics](https://quantum.cloud.ibm.com/learning/en/courses/general-formulation-of-quantum-information/quantum-channels/quantum-channel-basics), including reset and Pauli mixtures.
- [IBM Quantum: dynamic circuits and feedforward](https://quantum.cloud.ibm.com/docs/en/guides/classical-feedforward-and-control-flow).
- [IBM Quantum: nine-qubit Shor code](https://quantum.cloud.ibm.com/learning/en/courses/foundations-of-quantum-error-correction/correcting-quantum-errors/shor-code).

The native contribution here is the executable exact quantum/classical observer
representation, its declared semantics and reproducible verification. Hardware
replacement, computational supremacy and new error-correction principles are not
conclusions of this milestone.
