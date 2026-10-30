# Exact dyadic phase transport

The exact circuit spelling `pK` means diag(1, exp(2πi/K)); `pKdg` uses the
negative angle. Controlled forms act only on the all-one control/target entry.
K is a power of two from 2 through 4096.

```python
from native_relational_qc.phase_backend import PowerPhaseCircuit
from native_relational_qc.compact_qiskit import to_qiskit, from_qiskit
from native_relational_qc.openqasm import dumps, loads
c = PowerPhaseCircuit(2, 4096).add('h', 0).add('p4096', 0).add('cp128dg', 0, 1)
assert from_qiskit(to_qiskit(c)).operations == c.operations
assert loads(dumps(c)).operations == c.operations
```

The Qiskit export uses `PhaseGate(2*pi*n/d)` and its controlled gate. Import
recognizes only binary64 values exactly equal to that canonical expression on
the bounded dyadic grid, within ±4π; it never uses a numerical tolerance or
`limit_denominator`. A neighbouring float is rejected. This is an explicit
interop convention, not proof that an arbitrary float originally denoted an exact
irrational. Unbound parameters, external global phases, measurements, dynamic
instructions, arbitrary unitary matrices and open controls are rejected.

For symbolic exactness, the OpenQASM 2 subset preserves expressions such as
`u1(2*pi/4096)`, `cu1(-pi/64)` and `rz(3*pi/16)`. Only integer rational
arithmetic with pi is admitted; decimal literals are not guessed to be phases.
Static qregs and named supported gates are accepted. Unsupported syntax fails
rather than passing through a floating-point parser. A generic Qiskit QASM
serializer may emit decimal literals; those must not be mistaken for exact pi.

RZ(θ) has diagonal entries exp(−iθ/2), exp(iθ/2). The importer emits, in execution
order, X, P(−θ/2), X, P(θ/2), retaining the scalar phase. The denominator of θ/2
must fit the 4096 field cap. Thus `rz(pi/1024)` is accepted, `rz(pi/2048)` is
rejected for field capacity, and `rz(pi/3)` is rejected as non-dyadic.

Both bridges preserve the full unitary, not merely output probabilities on one
initial state. Tests check every supported phase order, inverse/controlled gates,
RZ basis-state phases, Qiskit operators and nearby invalid angles.
