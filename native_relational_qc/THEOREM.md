# NRQC-1: static relational circuit equivalence

Status: written algebraic derivation for the declared representation, with finite
floating-point software tests. This is not a proof-assistant certificate.

## Declared native quantum sector

Choose the complex representation

\[
 K=\begin{pmatrix}1&0\\0&-1\end{pmatrix},\qquad
 R=\begin{pmatrix}0&-1\\1&0\end{pmatrix}.
\]

Then \(K^2=I\), \(R^2=-I\), \(RK=-KR\), and
\(X=RK,\ Y=iR,\ Z=K\). The complex span of \(I,K,R,RK\) is
\(M_2(\mathbb C)\). Indeed, for any matrix \(U=(u_{ij})\),

\[
 U=aI+bK+cR+dRK,\quad
 a=\frac{u_{00}+u_{11}}2,\quad b=\frac{u_{00}-u_{11}}2,\quad
 c=\frac{u_{10}-u_{01}}2,\quad d=\frac{u_{01}+u_{10}}2.
\]

The quantum gate sector is the subset satisfying \(U^\dagger U=I\).
In particular \(H=(K+RK)/\sqrt2\), phase rotations and an entangling
controlled-\(RK\) operation are available. Tensor products of these local
matrix spaces span the joint operator space. A joint state has all \(2^n\)
complex amplitudes; it is not represented as a list of independent qubit ratios.

Complex scalars, the tensor-product composition, positive comparison metric
\(G=I\), and the Born observation rule below are **declared quantum-sector
choices**. They do not follow from the three EMK multiplication relations alone.
Nonunitary hyperbolic maps are excluded from this gate engine unless a separate
channel/postselection semantics is specified.

## Theorem

Let \(v\ne0\) represent a joint ray \([v]\in\mathbb{CP}^{2^n-1}\).
Let a finite circuit consist of unitary matrices \(U_1,\ldots,U_m\), each
embedded in explicitly ordered qubits, a global phase, and an injective terminal
qubit-to-classical-bit observation map. Unmeasured classical bits start at zero.
Suppose native and reference circuits use the same matrices, embeddings,
initial ray and observation map.

Then:

1. Each circuit induces a well-defined transformation of rays, independent of
   the common nonzero complex scale chosen for \(v\).
2. Both executions produce the same final ray and the same terminal outcome
   probabilities. With the same normalized representative and explicit global
   phase, their final vectors agree as well.
3. For two input rays transported by the same circuit, the relational overlap
   \(\mathcal F(v,w)=|v^\dagger w|^2/[(v^\dagger v)(w^\dagger w)]\)
   is invariant.
4. The equivalence survives composition of supported circuits before terminal
   observation, including controlled operations with their full operator phases.

### Proof

Put \(W=e^{i\phi}\widetilde U_m\cdots\widetilde U_1\), where
\(\widetilde U_j\) embeds local bit \(r\) in the circuit's explicitly
declared qubit \(q_r\). Each embedding is a permutation conjugate of a
unitary tensored with identities. Thus \(W\) is unitary.
Linearity gives \(W(cv)=cWv\), proving the ray statement. At each step the
two representations use the identical embedded matrix, so induction gives the
same final vector. This induction concerns mathematical semantics; it does not
turn a finite floating-point regression suite into a universal code proof.

For a classical outcome \(b\), let \(S_b\) be the computational basis
indices consistent with the terminal measurement map (and zero unused bits).
The observation rule is

\[
 P(b\mid[v])=\frac{\sum_{x\in S_b}|(Wv)_x|^2}{v^\dagger v}.
\]

The sets \(S_b\) partition the basis indices, so these probabilities are
nonnegative and sum to one. Equal final vectors and equal observation maps give
equal probabilities. Finally \((Wv)^\dagger Ww=v^\dagger w\) proves the
overlap invariant. Products of supported unitaries obey the same argument. QED.

## Relational chart and coherent control

For a single qubit \(z=\beta/\alpha\) in the \(\alpha\ne0\) chart,
\(U=\left(\begin{smallmatrix}a&b\\c&d\end{smallmatrix}\right)\) gives

\[
 z'=(c+dz)/(a+bz).
\]

A zero denominator means a change of chart, not a missing state. The code keeps
homogeneous amplitudes and chooses a nonzero chart pivot when ratios are requested.
For several qubits, complete joint amplitudes retain entanglement.

Although \(v\sim e^{i\phi}v\), it is generally false that controlled-\(U\)
and controlled-\(e^{i\phi}U\) are interchangeable. The phase becomes relative
between the control branches. In particular \((RK)^\dagger KR=-I\): an
ancilla prepared and read in the X basis detects this sign. The negative control
replaces \(KR\) by \(RK\), giving \(+I\) instead.

## Scope of the IBM target

The theorem gives a precise target for static ideal circuit compatibility:
the same computational task and circuit semantics, expressed in the declared
native quantum sector. The implementation accepts arbitrary resolvable unitary
gates up to its explicit gate/register resource limits, so it is not restricted
to the named Bell/GHZ examples. Large gates can be decomposed first.

Mid-circuit measurement, reset, classical feed-forward, channels, noisy hardware,
and timing require further semantics. Matching ideal calculations establishes
computational representation compatibility. It does not establish equal runtime,
memory scaling, a physical native processor, or gravitational dynamics.

IBM conventions used: [bit ordering](https://quantum.cloud.ibm.com/docs/en/guides/bit-ordering),
[target/ISA compilation](https://quantum.cloud.ibm.com/docs/en/guides/transpile), and
[Statevector reference](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.quantum_info.Statevector).
