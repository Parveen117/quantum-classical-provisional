# NRQC-2: exact transport of an observation across native cuts

Status: written algebraic derivation and bounded computational verification.
The complex quantum sector, tensor composition and Born observation rule remain
the explicit assumptions declared in NRQC-1. This is not a new physical law.

## 1. The retained quantity

Let the forward circuit be U_m ... U_1 on |0...0>. At a cut after gate j,
let psi_j = U_j ... U_1 |0...0>. Starting with the requested final Hermitian
observation O_m, define

\[
 O_{j-1}=U_j^\dagger O_j U_j.
\]

**Theorem (cut compatibility).** For every cut,

\[
 \boxed{\langle\psi_j,O_j\psi_j\rangle
       =\langle\psi_{j-1},O_{j-1}\psi_{j-1}\rangle.}
\]

Proof: substitute psi_j = U_j psi_{j-1} and move U_j to the other side of the
pairing by its adjoint. Induction gives the requested answer as
<0...0|O_0|0...0>, without requiring the algorithm to construct any psi_j.
The identity follows from declared circuit semantics, not from a new assumption
about a numerical certificate.

For a Z-basis assignment b on a selected set Q of qubits, use

\[
 O_m=\prod_{q\in Q}\frac{I+(-1)^{b_q}Z_q}{2}.
\]

For a Pauli-string expectation, use that Pauli string directly. These are different
queries; the engine does not claim to produce a full distribution in the time
needed for one selected query.

## 2. Exact algebra and complete memory

The native matrices are K=Z, R=-iY and RK=X. H=(K+RK)/sqrt(2), and the T
phase is omega=(1+i)/sqrt(2). All implemented gates have entries in

\[
 \mathbb F=\mathbb Q(\sqrt2,i).
\]

Elements are stored as four rational coefficients of 1, sqrt(2), i, i sqrt(2).
Addition, multiplication, conjugation and nonzero division stay in this field.
For z=u+iv, u,v in Q(sqrt(2)), z^{-1}=(u-iv)/(u^2+v^2); a nonzero real
quadratic a+b sqrt(2) has inverse (a-b sqrt(2))/(a^2-2b^2).
Thus equality, cancellation and phase retention do not use floating tolerances.

Expand each observer as O_j=sum_P c_{j,P} P in the Hermitian Pauli basis.
Every supported gate acts on at most three sites. Its complete local expansion is
calculated from the exact matrix using

\[
 c_{Q}=2^{-k}\operatorname{Tr}(Q\,U^\dagger P U).
\]

Trace orthogonality of the k-site Pauli basis makes this decomposition exact.
The algorithm carries every resulting coefficient, combines equal global Pauli
strings and removes only coefficients exactly equal to zero. There is no
small-coefficient truncation. On the final source boundary, a Pauli product has
expectation zero if it contains X or Y, and one otherwise. Only at that boundary
does the algorithm sum the surviving coefficients. Dropping off-diagonal terms
before this point would be invalid; a test of <X> after H detects that error.

Consequently, until an explicit resource limit is reached, the implementation's
algebraic procedure computes the exact declared-model answer. Finite tests assess
the code; they are not an exhaustive machine proof of the implementation.

## 3. Observation invariance and groups of operations

For a fixed O, define its unitary stabilizer

\[
 \mathcal S_O=\{U:U^\dagger O U=O\}.
\]

**Theorem (invariance under composition).** S_O is a group. If a set of unitary
generators fixes O, every word in those generators and their inverses fixes O.

Proof: I fixes O. If U and V fix O, then
(UV)^dagger O(UV)=V^dagger(U^dagger O U)V=O. From U^dagger O U=O,
multiplying by U and U^dagger gives U O U^dagger=O, so U^{-1} fixes O.
This is the standard unitary stabilizer/commutant argument, now used operationally.

Fixing the **sum** does not require fixing each term separately. For example,

\[
 O=(I+Z_1+X_0+X_0Z_1)/4
\]

is fixed by CZ(0,1), which exchanges X_0 and X_0 Z_1. The code checks both
termwise invariance and equality of the complete returned sum. Its gate counter
records equal complete observers as invariant; a joint-invariance regression
test covers this term-permutation case.

An invariant gate is relative to the observer at that cut. It is not necessarily
irrelevant for another measurement. Detecting the equality still costs work; the
benchmark reports all gates examined, not just the gates that change O.

## 4. Exact sharing of conditional states

The alternative `CompactState` backend represents a conditional vector by a
weighted binary node. For children a and b, select the first nonzero incoming
scalar f and store (a/f,b/f), returning f on the incoming edge. Store an identical
normalized node only once, using exact field equality. Zero edges are canonical.

**Theorem (lossless sharing).** At fixed variable order, replacing repeated
proportional conditional vectors with a shared normalized node and their exact
incoming weights preserves every amplitude, including the root/global phase.

Proof: f(a/f,b/f)=(a,b). Induct on the remaining number of sites; each nonzero
normalized node has first nonzero amplitude one, so equal normalized vectors
have equal canonical children and the same unique node. No nonzero residual is
deleted. Linear combination, local gate action and controlled action
(I-P)psi+U P psi are therefore exact graph operations. Queries sum the exact
squared amplitudes recursively without enumerating all basis strings.

This is a weighted decision-diagram method, not a newly discovered compression
principle. Its relevance here is executable native ratio and phase retention.

## 5. Resource theorem and its boundary

For the observer backend, let G be the gate count, S the maximum retained Pauli
term count and B the maximum rational coefficient bit length. With local gate
size at most three, each local table has constant maximum size. The arithmetic
operation count is O(G S) up to that local constant; integer-mask and exact-rational
operation costs must also be included. Storage is polynomial in S, B and the mask
length n. Preparing a k-bit outcome projector initially needs 2^k terms.

For the state backend, resources depend on the live and transient graph size,
exact coefficient bits and recursive work. Node sharing alone does not bound
those quantities polynomially for arbitrary circuits. All explicit budgets fail
closed. Gate failures collect temporary nodes and retain the prior state.

There is a simple obstruction to a blanket compression claim: for m Bell pairs
with each pair's two halves separated into two consecutive variable blocks,
the fixed-order state graph has 3*2^m-3 nodes. Its upper block forms a complete
binary tree with 2^m-1 nodes; the lower block contains every basis suffix, with
2+4+...+2^m nodes. Interleaving the pair halves instead gives three nodes per
pair, or 3m. Both counts are checked through m=7 in the benchmark. This is a
representation-ordering limitation, not a hard quantum problem: stabilizer
methods can handle the same Bell states efficiently.

No polynomial bound on S or graph size is asserted for all circuits. Different
observables can have different costs. General hardware replacement would require
much broader computational evidence and complexity results.

## 6. A derived, size-independent reading in a structured family

For n>=2, prepare H then T at each site, apply nearest-neighbor CZ gates,
then H at site 0. Query P(q0=0,q1=0).

Conditioning on q1=0 makes the first CZ phase trivial. Remaining diagonal phases
do not affect the required marginal. The first site's relative phase is omega,
so its final zero probability conditional on q1=0 is |1+omega|^2/4. Therefore

\[
 \boxed{P(q_0=0,q_1=0)=(2+\sqrt2)/8.}
\]

The input after H,T has full support and nearest-neighbor CZ entangles the chain.
The state stays full-support after the final H because 1+omega and 1-omega are
both nonzero. This is a structured classically tractable family, not a proposed
quantum-advantage workload. The engine does not have this answer hard-coded: the
general exact gate/query procedures calculate it; the analytic value is used
only as the verification target.

For this observer, the backwards expansion has at most six Pauli terms. Of the
3n gates, 3n-4 leave the complete observer unchanged at their cuts. The four
changes are the final H0, T0 and the two relevant preparation Hadamards. These
counts are checked at n=8,16,20,32,64,128. At n=128, 380 of 384 gates are
recognized as invariant, while every gate is still examined.

## Prior methods and attribution

- Giles and Selinger, [Exact synthesis of multiqubit Clifford+T circuits](https://arxiv.org/abs/1212.0506): exact Clifford+T arithmetic setting.
- Wille, Hillmich and Burgholzer, [Decision Diagrams for Quantum Computing](https://arxiv.org/abs/2302.04687): weighted graph simulation and verification.
- Burgholzer, Ploier and Wille, [Tensor Networks or Decision Diagrams?](https://arxiv.org/abs/2302.06616): different representations have different useful regimes.
- Angrisani et al., [Pauli propagation with local noise](https://arxiv.org/abs/2501.13101): related Pauli-propagation family; its approximation/noise theorems are not invoked here. This implementation retains all terms for its noiseless declared circuit.

These sources identify established mathematical methods. The contribution in
this repository is the native implementation, exact scope, invariant checks and
reproducible comparisons; no priority claim for the underlying methods is made.
