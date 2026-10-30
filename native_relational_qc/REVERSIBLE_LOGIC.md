# Coherent Boolean logic, arithmetic and clean workspace

The native calculator now has a bounded Boolean-oracle compiler, a reversible
ripple adder and working phase-interference/search examples. The same exact
coefficient and observation engines execute the resulting circuits. This adds
algorithm-building capabilities; it does not change the generic 16-round
brickwork contraction limit or establish a physical entropy-logic device.

## The information-preserving bridge

A two-input, one-output Boolean function generally loses input information.
For example, XOR maps both `00` and `11` to zero. Its output alone cannot be a
reversible quantum evolution on that input space. We instead implement

\[
U_f\,|x,y,0^k\rangle=|x,y\oplus f(x),0^k\rangle.
\]

The input is retained, the output is XORed into a distinct register, and clean
scratch is restored. Each generated X, CX and CCX is an exact permutation matrix,
so it introduces no extra relative or global phase. The action on arbitrary
superpositions follows by linearity. This is the standard reversible embedding
and compute/uncompute construction, used here as an explicit native interface.

References: [Bennett, 1973, Logical Reversibility of Computation](https://doi.org/10.1147/rd.176.0525)
and [IBM's Boolean-circuit and workspace construction](https://quantum.cloud.ibm.com/learning/en/courses/fundamentals-of-quantum-algorithms/quantum-algorithmic-foundations/simulating-classical-computations).
These methods are not claimed as new discoveries. The new contribution here is
the implementation, exact checks and connection to this calculator's gate model.

### Finite truth-table synthesis

`BooleanMap(n, m, table)` stores `2**n` output words, with bit 0 least significant
in both input row indices and output words. A Boolean Möbius transform gives
the exact algebraic normal form over GF(2):

\[
f_j(x)=\bigoplus_S c_{j,S}\prod_{i\in S}x_i.
\]

Each monomial toggles output bit `j`. Degree zero uses X, degree one uses CX,
and degree two uses CCX. Higher-degree terms compute a chain of partial ANDs,
toggle the target and reverse the chain. A degree-`d` term needs `d-2` clean
scratch bits and `2d-3` CCX gates when `d>=2`. Scratch is reused between terms.
No approximation or probability-only merge occurs.

The compiler accepts at most **eight input bits and eight output bits**, and
checks its requested gate budget before allocation. A truth table has exponential
input size; this interface is not a scalable synthesis promise for arbitrary
large functions. Structured addition has its own linear construction.

```python
from native_relational_qc.reversible_logic import compile_oracle, gate_function

nand = compile_oracle(gate_function('nand'))
print(nand.circuit.operations)  # X on output, then CCX from the two inputs
print(nand.to_dict())
```

`gate_function` provides NOT, AND, OR, NAND, NOR, XOR and XNOR. Even NOT is
compiled in the common out-of-place XOR-oracle convention, so its output starts
as `y` and becomes `y XOR (1 XOR x)`. An in-place single-qubit NOT remains the
ordinary native X gate.

## Ripple arithmetic and the carry identity

For Boolean bits, let `P=A XOR B` and `G=AB`. Then `GP=0`, so

\[
C_{i+1}=A_iB_i\lor((A_i\oplus B_i)C_i)
       =A_iB_i\oplus((A_i\oplus B_i)C_i).
\]

The implementation toggles the carry target by `AB`, temporarily changes B to
`A XOR B`, toggles by that value times Cin, and restores B. This takes two CCX
and two CX gates. After computing all carries, three CX gates per output bit
write `A XOR B XOR Cin` into Sum. Reversing the internal carry computation
restores every scratch bit while retaining the sum and final carry outputs.

For width `n` the clean-workspace contract is

\[
|A,B,c,Y,0^{n-1}\rangle\mapsto
|A,B,c,Y\oplus\operatorname{bits}_{n+1}(A+B+c),0^{n-1}\rangle.
\]

`Y` can be any initial output word, and the formula extends coherently to
entangled input/output registers. Scratch must initially be zero. The generated
gates remain unitary on dirty scratch, but the declared arithmetic formula does
not hold there; the API does not insert a measurement or reset to hide this
precondition.

| Resource | Width n | Four-bit example |
| --- | --- | --- |
| Total qubits | 4n+1 | 17 |
| Clean internal-carry scratch | n-1 | 3 |
| CCX gates | 4n-2 | 14 |
| CX gates | 7n-2 | 26 |
| Total gates | 11n-4 | 40 |

A direct three-product majority construction with the same compute/uncompute
schedule uses `6n-3` CCX and `3n` CX. Thus the four-bit version trades **seven
fewer CCX for fourteen more CX**. This is a logical gate-resource comparison,
not a claim about device latency, physical energy or an optimal adder.
The constructor allows widths 1..63 within the native 256-qubit IR limit;
constructibility does not imply that arbitrary coherent executions fit budgets.

```python
from native_relational_qc.reversible_logic import ripple_adder
from native_relational_qc.compact import CompactCircuit

adder = ripple_adder(4)
circuit = CompactCircuit(17)
# Prepare inputs and, if wanted, phase-bearing superpositions here.
adder.append_to(circuit)
# Reverse exactly when required:
adder.append_to(circuit, inverse=True)
```

`append_to` supports a distinct-wire mapping and validates it before changing
the destination. Register ordering and scratch requirements are in `to_dict()`.

## A quantum-search check that needs cleanup

The 11-qubit search example prepares a uniform two-bit A register and asks
`A+1=3`. It computes the sum, marks equality through a phase-marker qubit,
uncomputes the entire sum register, and performs one Grover diffusion on A.
The exact result is **P(A=2)=1**. All comparison/carry/sum workspace returns zero.

The deliberate negative control omits sum uncomputation. The same readout then
has **P(A=2)=1/4**. The still-correlated sum register prevents the required
interference. Merely getting the classical arithmetic truth table right is
therefore not sufficient for a usable quantum subroutine.

This is a four-candidate ideal demonstration, not a hardware experiment or a
PC runtime advantage. The existing H and phase gates provide the superposition
and interference operations; a library of Boolean permutations alone would not.

## Classical threshold checks and physical scope

`entropy_logic.ThresholdModel` checks a supplied classical score

\[
T_O=b+k_1x\Theta+k_2y\Theta+k_3xy\Theta^2,
\qquad x,y\in\{0,1\}.
\]

All four rows must satisfy a strictly positive requested margin with exact
rational coefficients. The complement decoder is explicit, so a NAND gate can
use the verified AND score with inverted classification. The `Theta**2` term,
bias and zero-input row are retained. Float coefficients are not inferred.

```python
from native_relational_qc.entropy_logic import ThresholdModel
from native_relational_qc.reversible_logic import compile_oracle, gate_function

model = ThresholdModel(k3=1, theta=2, threshold=2, margin=1, high_is_one=False)
oracle = compile_oracle(model.certified_function(gate_function('nand')))
```

This verifies a *specified score model*, not a material-specific map from
lambda/Onsager parameters to that score. Thresholding is a classical calibration
step; it is never applied to quantum amplitudes during coherent execution.
The Boolean identities also cannot be extended to arbitrary analog values as if
every reused signal were independent.

Two exact audit helpers prevent unsupported physical interpretations:

- `transport_split` verifies `X^T L X = X^T sym(L) X` for real 2x2 data.
  `X^T antisym(L) X=0`. Antisymmetry can affect fluxes, but is not itself an
  additive term in this scalar entropy production. The symmetric PSD check is
  conditional on having correctly defined conjugate forces and units.
- `expected_carry_activity` keeps the correlation `AB*(A XOR B)*Cin=0`.
  For independent fair A/B bits and independent Cin with probability `p`,
  the dimensionless expected total carry activity is
  `n/2 + (p-1/2)*(1-2**(-n))`. Four bits give **2** for fair Cin and **49/32**
  for Cin fixed zero. This number is not joules, entropy, entropy rate or power.

Logical reversibility alone does not establish zero dissipated heat in a real
implementation. No energy, latency, noise-filtering or quantum-memory performance
is inferred from these software checks. Those need a device model, dimensional
accounting and measurements.

## Run and verify

The generated examples explicitly select the existing `observer` backend,
which supports nonadjacent CX/CCX. No routing or backend fallback is implicit.

```bash
python -m native_relational_qc.reversible_logic_demo --example addition --out /tmp/addition.json
python -m native_relational_qc calculate /tmp/addition.json --timeout 20

python -m native_relational_qc.reversible_logic_demo --example search --out /tmp/search.json
python -m native_relational_qc calculate /tmp/search.json --timeout 20

python -m native_relational_qc.reversible_logic_demo --verify --out /tmp/logic-verification.json
python -m unittest discover -s tests -p 'test_native*.py' -v
```

Saved inputs/results are in `calculator_examples/reversible_*.json`; the
reproducible packet is [reversible_logic_verification.json](reversible_logic_verification.json).
All **160 native test methods passed**, with no failures, errors or skips;
the [test record](reversible_logic_test_results.json) and
[source manifest](reversible_logic_manifest.json) bind this result to the files.
The native path imports no quantum SDK. An optional Qiskit dense statevector is
used only as an independent test reference.

The verification covers every one of the 256 three-input Boolean functions,
all 16,384 four-bit-adder combinations of inputs and arbitrary output words,
and all 512 complex amplitudes of a coherent four-bit addition with T/S phases.
Scratch cleanup and inverse restoration are checked exactly. The independent
17-qubit dense reference checks the complete vector, including zero amplitudes
outside the expected support. These are finite tests, not formal verification
of the Python runtime or physical validation.
