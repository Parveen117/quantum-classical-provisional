# Native cuts on an orthogonal phase register

Author: Monty. Version 0.4. Status: exact software compiler and conditional
coherent realization of wrapped-phase permutations. No physical device.

The [v0.3 code](ENCODING.md) cannot implement every native balanced cut by
a fixed channel on its two-site state alone. This revision supplies a
**different encoding** with more distinguishable states. It reuses the
existing reversible arithmetic and circuit engine, adding the missing
translation from native phase operations.

## 1. Duplicate-work check and reuse

The [source manifest](register_source_manifest.json) pins the seven branch
tips checked on 2026-10-24. All recursive trees were complete. The working
branch's Python/Markdown files were searched; relevant source implementations
and the current master README were read. Master's implementation files match
ones already present locally. Differences on older branches concern QEC,
calibration, tests and documentation. No existing four-phase native-operation
compiler was found in this scope; deleted branches and other repos were not
searched in this revision.

| Existing work | Reused or distinguished here |
| --- | --- |
| `model.py` | Original Config, Operation, Cell, cost and history validation |
| `modular_arithmetic._add` | Existing controlled constant addition and clean carry ladder |
| `CompactCircuit` | Existing gate IR, returned directly by the new adapter |
| `phase_backend.prepare` | Existing exact engine for coherent tests; no new simulator |
| `reversible_logic.py` | Already supplies Boolean oracles and an adder; neither is recreated |
| Operator-memory / multi-ledger IBM scripts | Different existing experiments; read, not executed |
| Observer “cut compatibility” | Transport across circuit boundaries, distinct from phase reflection |
| `encoding.py` | Previous tomographic bridge retained; its obstruction is unchanged |

The adapter imports a private existing helper, `_add`. Its source hash is
retained in the audit; changes to that helper require rerunning this adapter's
tests. There is no duplicate implementation of the carry ladder.

## 2. Encoding and information budget

For \(L=2^w\), \(2\leq w\leq12\), write each wrapped coordinate
\(x_j\in\mathbb Z_L\) into one little-endian \(w\)-bit register:

\[
E(x)=|x_0,x_1,x_2,x_3\rangle,\qquad
\rho_x=|x\rangle\langle x|.
\]

This is an orthogonal-label choice. The cyclic phase coordinate is the
register **label**, not a quantum amplitude's argument. Algebraically,
the label projectors are orthogonal idempotents; each reversible map
permutes them. Extending to off-diagonal matrix units supplies the usual
coherent quantum representation. That extension and the quantum measurement
law are explicit assumptions, not derived from the manuscript cut rules.
There is no claim of a Hilbert-free alternative physical theory here.

All four labels can be read exactly from one ideal computational-basis
measurement on a basis preparation. A coherent superposition instead yields
one label probabilistically and is disturbed. A classical mixture
\(\sum_xp_x|x\rangle\langle x|\) reproduces the v0.1 wrapped-label statistics.
Preparing coherent superpositions is an additional physical capability.

At \(L=64\), the layout is 24 phase wires plus 4 clean workspace wires:
**28 logical circuit wires**. Basis labels can also be stored as 24 ordinary
classical bits. The circuit notation does not mean 28 physical qubits were
built or that the PC gained a quantum speedup.

With fixed closure sign/twist there are \(L^3\) allowed labels, giving an
18-bit information lower bound at \(L=64\). A compressed 18-wire compiler
is **not implemented**; the present layout still uses 24+4 wires.
Gamma, integer winding lifts, event records and path-dependent cost remain
in the original classical Cell. They are additional storage, absent from the
28-wire count. The new register is not a complete quantum encoding of Cell.

## 3. Compilation identities

All equations below are modulo \(L\); other coordinates stay fixed.

| Native instruction | Register action | Lowering |
| --- | --- | --- |
| cut(j,h) | \(x_j'=h-x_j\) | Complement all bits, then add \(h+1\) |
| shift(j,d) | \(x_j'=x_j+d\) | Existing constant adder |
| pair_shift(j,s,d) | \(x_j'=x_j+d,\ x_s'=x_s-d\) | Two constant additions |
| swap(j,s) | Exchange labels | Three CX per corresponding bit |
| shear(c,t,k,a) | \(x_t'=x_t+k(x_c-a)\) | Controlled additions of \(k2^i\), then \(-ka\) |
| pair_cut(j,s,h) | \(x_s'=x_s+2x_j-h,\ x_j'=h-x_j\) | Update reservoir from old \(x_j\), then cut |

Bitwise complement on \(w\) bits is \(-x-1\bmod 2^w\), proving the cut
identity. Write \(x_c=\sum_i2^i b_i\); conditional addition of \(k2^i\)
on each control bit sums to \(kx_c\), proving the shear and reservoir
updates. Control and target modes are required to differ.

The reused adder increments a suffix for each set constant bit. High targets
toggle first, so carry predicates see the original lower bits. A multiple
control is decomposed using the existing clean ladder and its reverse.
Each ladder restores its workspace. There are at most \(w\) controls in
this adapter, so \(w-2\) clean bits suffice. Negative constants and products
are reduced modulo \(L\) before reaching the adder.

Each source map is bijective: cuts, balanced cuts and swaps are involutions;
translations and shears invert by negating their increments or coefficient.
Composition therefore defines a permutation \(f\), and the circuit obeys

\[
V_f|x,0_{\rm work}\rangle=|f(x),0_{\rm work}\rangle.
\]

Because X/CX/CCX are phase-free permutations, linearity gives the same
identity for arbitrary complex superpositions, including those entangled
with an untouched external reference. No measurement/repreparation is used.
Reversing the elementary gate list is its exact inverse, even on dirty
workspace; the desired phase-map promise itself requires clean workspace.
The test suite includes a dirty-workspace counterexample.

The phase permutation matrix satisfies \(U_f^\dagger U_f=I\), hence
\(\rho_{f(x)}=U_f\rho_xU_f^\dagger\). This is the conventional reversible
embedding, not a new synthesis theorem; see Shende, Prasad, Markov and Hayes,
[Reversible Logic Circuit Synthesis](https://arxiv.org/abs/quant-ph/0207001).
The new contribution is this native-operation adapter and its exact scope.
Reflection of these angle labels is linear on the quantum register; it is
not universal complex conjugation of unknown amplitudes.

## 4. Closure and lifted-state guards

The compiler independently composes the source affine map \(x\mapsto Ax+b\)
over \(\mathbb Z_L\). A fixed closure sign/twist specifies
\[
\mathbf1^Tx=s\pmod L,\qquad
s=(0\ \text{or}\ L/2)-(L/4)\,\text{twist}.
\]
This whole sector is preserved exactly when every column sum of \(A\)
equals the same \(q\bmod L\), and
\[
qs+\mathbf1^Tb=s\pmod L.
\]
To prove necessity, vary \(x\) by every \(e_i-e_3\), which stays in the
sector. Sufficiency follows by substituting the common column sum.
Every source map is invertible, so preservation is onto on this finite set.

This criterion is checked at **every native-operation boundary**. An
individual cut that happens to preserve one example is rejected if it fails
on the rest of the fixed sector. A word that temporarily exits and later
returns is also rejected. Elementary carry/complement gates may temporarily
leave the sector, so this is not yet a gate design for a carrier with a hard
superselection constraint at every physical instant.

`bind_cell(cell,program)` replays the original Cell implementation and checks
the resulting phases against \(Ax+b\). It preserves Gamma and the full
original history while enforcing lift, event and rational-cost limits.
The finite register compiler alone does not promise acceptance for every
possible unwrapped lift. It also does not coherently store branch-dependent
cut charges or winding on a superposition. Binding a known classical Cell
does not copy or measure an unknown quantum register.

`verify_program` re-derives the source/gate binding and rejects modifications.
It shares the compiler, so it is a consistency verifier, **not an independent
formal proof checker**. The written identities, independent bit interpreter,
original Cell reference and exact coherent engine provide different checks.

Read/reset remain unsupported by this permutation compiler. Reading can be
specified as an instrument, while resetting and keeping the old outcome
requires an explicit record/environment. Neither is silently discarded.

## 5. What happened to the old obstruction?

The v0.3 pair \(x=(0,0,0,0)\), \(y=(16,48,0,0)\) had trace distance
\(\sqrt2/10\) in its two-site mixed encoding. Its proposed balanced-cut
outputs could be distinguished by at least \(1/5\), violating channel
contractivity for that encoding.

Here the two inputs are orthogonal labels, with trace distance 1. The cut
maps them to \((0,0,0,0)\) and \((48,48,32,0)\), also orthogonal: distance
remains 1. More distinguishable states remove that particular obstruction.
There is **no deterministic conversion** of the old code into these labels:
such a conversion would itself increase the same pair's trace distance.
The old limitation has not been disproved or bypassed with free information.

## 6. Reproduce and inspect

```python
from phase_seam_foundation.model import Cell, Config, Operation
from phase_seam_foundation.register import compile_register, bind_cell

cfg = Config(sector=1)
program = compile_register((Operation("pair_cut", (0, 2, 0)),), config=cfg)
transition = bind_cell(Cell.start((16, -16, 0, 0), config=cfg), program)
assert transition.after.phases == (48, 48, 32, 0)
circuit = program.to_circuit()  # Existing CompactCircuit, workspace starts zero.
print(program.resources())
```

```bash
python -m phase_seam_foundation.register_qualification
python benchmarks/phase_seam_register_audit.py
```

The saved [qualification](register_qualification.json) contains the compiled
gate word, affine witness, known-cell transition, exact coherent output and
resource counts. [Test output](register_test_results.txt) records the combined
suite.
The combined run passes **103 tests in 47.541 seconds**, with no failures,
errors or skips: 16 register tests plus the 87 prior targeted checks.
The full native/Shor suite was not rerun; those implementations are unchanged.
New coverage includes all 256 grid-4 tuples for 46 declared words;
all 4096 active input pairs for one grid-64 balanced cut and one shear;
all 4096 axis/input combinations for a single-mode grid-64 cut; every
supported width; both closure signs and four twists at grid 4; inverse,
dirty-workspace, tampering and resource controls.

The coherent control maps
\[
(|0,0,0,0\rangle+i|1,0,63,0\rangle)/\sqrt2
\quad\longmapsto\quad
(|0,0,0,0\rangle+i|63,0,1,0\rangle)/\sqrt2.
\]
Undoing the cut and preparation gives all-zero probability 1. This checks
relative phase as well as labels. A separate test retains a \(\zeta_{64}\)
relative phase and entanglement with an external reference.

At grid 64: cut axis 0 uses 24 elementary gates; balanced cut (0,2,0) uses
59; shear (0,2,-3,5) uses 129; the saved three-operation closed word uses
145. These are logical X/CX/CCX counts, not optimized or routed native-device
counts, pulse counts, depth, time, energy, error correction or fault tolerance.
Synthesis is bounded at 100,000 gates and returns no partial circuit.

## 7. Hardware consequence and remaining foundational work

There is now a concrete reversible phase-register interface against which a
candidate carrier can be compared. A classical carrier can implement these
label transformations; quantum use additionally needs coherent preparation,
coherence-preserving interactions, clean workspace and the appropriate
measurement law. This compiler does not derive those physical capabilities
from the LaTeX manuscripts.

The material-neutral next requirements are a carrier state/preparation law,
a physical implementation of at least one balanced cut on superpositions,
independent phase-sensitive readout, and an explicit controller/environment
for reset and retained path records. The 2056-site plan, general quantum
simulation limits and Shor results are unchanged.
