# Native cuts and fixed-closure register compression

Author: Monty. Version 0.5. Status: exact software compiler and conditional
coherent realization of wrapped-phase permutations. No physical device.

The [v0.3 code](ENCODING.md) cannot implement every native balanced cut by
a fixed channel on its two-site state alone. This revision supplies a
**different encoding** with more distinguishable states. It reuses the
existing reversible arithmetic and circuit engine, adding the missing
translation from native phase operations.

The v0.5 extension uses the existing closure constraint to omit one phase
register, without recreating the compiler or arithmetic. At grid 64 it
reduces the phase storage from 24 to 18 wires and the total from 28 to 22
wires. Full-to-compressed conversion has a separate 28-wire peak and gate
cost. Section 8 gives the construction and its exact limits.

The subsequent [controller](CONTROLLER.md) composes this compiler with
explicit read/reset records and the existing dynamic measurement engine.
The permutation-only `compile_register` interface still rejects instruments.
Version 0.7 adds explicit balanced reset with a compensating native mode.
Read/reset/pair_reset remain instruments outside this permutation compiler.
The [v0.8 native control targets](SECTOR_CONTROL.md) supply continuous
sector-preserving operator paths, with a separate binary verification export.
The [v0.9 photonic adapter](PHOTONIC_EXCHANGE.md) adds a restricted encoded
carrier netlist and characterization plan. The current combined audit
includes 199 tests with physical phase/profile checks from the [v0.11 layout](PHOTONIC_LAYOUT.md)
in addition to the [v0.10 optical I/O extension](PHOTONIC_IO.md);
the v0.4/v0.5 results below retain
their milestone context.

## 1. Duplicate-work check and reuse

The [source manifest](register_source_manifest.json) pins the seven branch
tips checked on 2026-10-24. All recursive trees were complete. The working
branch's Python/Markdown files were searched; relevant source implementations
and the current master README were read. Master's implementation files match
ones already present locally. Differences on older branches concern QEC,
calibration, tests and documentation. No existing four-phase native-operation
compiler was found in this scope; deleted branches and other repos were not
searched in this revision.

Before v0.5, all seven heads were checked again: the six other branches were
unchanged, while the working branch was at the v0.4 commit. The existing
notes explicitly marked the compressed layout as unimplemented. The new
option, conversion codec and qualification therefore extend the same files.

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

At \(L=64\), the default full layout is 24 phase wires plus 4 clean workspace wires:
**28 logical circuit wires**. Basis labels can also be stored as 24 ordinary
classical bits. The circuit notation does not mean 28 physical qubits were
built or that the PC gained a quantum speedup.

With fixed closure sign/twist there are \(L^3\) allowed labels, giving an
18-bit information lower bound at \(L=64\). The optional `omit_mode` layout
now attains 18 phase wires with the same 4 clean workspace wires: 22 total.
Gamma, integer winding lifts, event records and path-dependent cost remain
in the original classical Cell. They are additional storage, absent from the
register-wire count. Neither layout is a complete quantum encoding of Cell.

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

Read/reset remain unsupported by this permutation compiler. The separate
[controller adapter](CONTROLLER.md) now provides their explicit records and
measurement export; neither instrument is silently substituted here.

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
The v0.4 run passed **103 tests in 47.541 seconds**, with no failures,
errors or skips: 16 register tests plus the 87 prior targeted checks.
The current saved audit additionally covers the v0.5 compression and codec
tests: **117 tests in 53.016 seconds**, with no failures, errors or skips.
Its source hashes and unrounded runtime are in the qualification JSON.
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

## 8. Exact compression within a known closure sector

Fix the known residue \(s\) from the closure sign and twist, and choose an
omitted mode \(o\). Let \(R=\{0,1,2,3\}\setminus\{o\}\). Store the three
coordinates \(y=(x_j)_{j\in R}\), in increasing mode order, and reconstruct
\[
x_o=s-\sum_{j\in R}y_j\pmod L.
\]
This is a bijection between \(\mathbb Z_L^3\) and the fixed sector. In
particular, it loses no wrapped-phase information **within that sector**.
The coherent embedding
\[
J_s|y\rangle=|x(y)\rangle
\]
is an isometry because different \(y\)'s give distinct orthogonal labels.
For every admitted source permutation \(f\), its reduced permutation is
\(g(y)=(f(x(y)))_R\). Sector preservation gives
\[
U_fJ_s=J_sU_g,\qquad U_g^\dagger U_g=I.
\]
The equality holds for arbitrary superpositions in the fixed sector and
when an untouched external reference is present. It does not compress an
unknown closure sign/twist or a superposition spanning different sectors.
No new physical postulate is used beyond the v0.4 circuit assumptions.

For the full affine witness \(x'=Ax+b\), the stored map is explicitly
\[
M_{ij}=A_{ij}-A_{io},\qquad
d_i=b_i+A_{io}s\pmod L,\qquad i,j\in R.
\]
`stored_affine()` returns this \(3\times3\) matrix and offset.
The compiler still checks the original full source map at every native
boundary, so the reduced coordinates do not silently admit forbidden words.

### Direct lowering without a hidden fourth register

The source instructions are first rewritten using the closure identity,
then passed to the **same** existing gate lowerer. No fourth register is
materialized during compressed execution.

| Source operation involving \(o\) | Action on retained coordinates |
| --- | --- |
| pair_shift(j,o,d) | \(x_j'=x_j+d\) |
| pair_shift(o,r,d) | \(x_r'=x_r-d\) |
| pair_cut(j,o,h) | \(x_j'=h-x_j\) |
| pair_cut(o,r,h) | \(x_r'=2s-h-x_r-2\sum_{j\in R\setminus\{r\}}x_j\) |
| swap(o,r) | \(x_r'=s-x_r-\sum_{j\in R\setminus\{r\}}x_j\) |

The last two rows are one retained cut followed by two existing shears.
Operations not involving \(o\) retain their earlier lowering. Source shifts
by a multiple of \(L\) and shears with coefficient a multiple of \(L\) have
identity wrapped action; their native events and changed lifts are still
retained by Cell replay. Single cuts and nontrivial single shears do not
preserve the whole fixed sector for these grids and remain rejected.
Read/reset remain outside this reversible compiler.

```python
cfg = Config(sector=1)
program = compile_register(
    (Operation("pair_cut", (0, 2, 0)),),
    config=cfg, omit_mode=2,
)
assert program.n_qubits == 22
assert len(program.gates) == 24
assert program.unpack(program.pack((16, 48, 0, 0))) == (16, 48, 0, 0)
assert program.image((16, 48, 0, 0)) == (48, 48, 32, 0)
```

The four independent-register layout remains the default. Omitting a mode
requires explicit `sector=+1` or `sector=-1`. `pack` rejects off-sector
labels; `unpack` rejects nonzero workspace. Existing source history and
lift/cost/resource guards still apply when binding a Cell.

### Reversible conversion and the off-sector control

`closure_codec(config, omit_mode)` acts on the **full** layout:
\[
C_s:|x_R,x_o\rangle\longmapsto
|x_R,\ x_o+\sum_{j\in R}x_j-s\rangle.
\]
The displayed register ordering is schematic; wire positions remain those
of the original four-mode layout. This modular-addition map is bijective
on all inputs. On the fixed sector the omitted register becomes the pure
zero state, uncorrelated with the retained data and any external reference.
It can then be detached. The inverse codec restores the dependent fourth
label from zero. The three retained wire groups are relabelled in increasing
mode order; physical SWAP routing is not included.

Off-sector input leaves a nonzero residual in the omitted register.
Superpositions over sectors can entangle it with retained data. Dropping it
then need not be lossless. The codec performs no measurement, reset,
postselection or silent projection onto the desired sector.

At grid 64, sign +1 and twist 0, either conversion direction uses 183
logical gates and a **28-wire peak**. For the example cut, compress →
24-gate cut → expand totals 390 gates, compared with 59 gates for direct
full-register execution. The 22-wire figure describes compressed execution
or direct compressed preparation, not this conversion's peak. Conversion
therefore makes sense when its cost can be justified by the intended use;
this revision reports no universal runtime improvement.

### Layout-dependent gate costs

All rows use grid 64, sign +1 and twist 0. Reduced layouts each use 22 wires;
the full layout uses 28.

| Source word | Full gates | Omit 0 | Omit 1 | Omit 2 | Omit 3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| pair_cut(0,2,0) | 59 | 154 | 59 | 24 | 59 |
| pair_shift(0,2,1) | 59 | 41 | 59 | 18 | 59 |
| swap(0,2) | 18 | 276 | 18 | 276 | 18 |
| Saved three-operation closed word | 145 | 488 | 368 | 86 | 121 |

The last word is pair_cut(0,2,7), pair_shift(1,3,-5), swap(0,1).
Omitting the reservoir of the example cut reduces gates; exchanging an
omitted mode can increase them sharply. The counts compare four declared
layouts, not all possible circuit optimizations. No automatic physical
device selection or optimized pulse synthesis is claimed.

### Verification and physical consequence

The 14 new tests cover every grid-4 sector label for 86 generator words
under all four omissions; all grid-8 labels for one composed word under
both signs, four twists and four omissions; 4096 active grid-64 pairs per
omission for another word; and all supported widths. The codec is checked
on **all** full grid-4 inputs, including off-sector ones, under both signs,
four twists and four omissions. Negative controls cover dirty workspace,
wrong sectors, invalid layouts, modified witnesses and source limits.

A direct 22-wire coherent execution retains the exact \(\zeta_{64}\)
relative phase and restores interference under its inverse. Separately,
full → compressed → transformed → full agrees in every exact amplitude
with direct full execution for an eight-term coherent input entangled with
an external reference, under all four omissions.

The phase-storage reduction is 24→18 bits, or 25%; total logical width is
28→22, about 21.43%. It exploits a known invariant constraint, not generic
compression of arbitrary quantum states. Gamma, winding, cost and history
remain external. An omitted phase reconstructed by definition is **not an
independent experimental confirmation of closure**. A carrier experiment
must measure an independent closure residual or validate the preparation
and transfer laws; otherwise the constraint is only assumed.
