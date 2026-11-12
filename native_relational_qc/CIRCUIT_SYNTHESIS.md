# Pāṇini-inspired circuit construction from a state goal

Monty · 12 November 2026

`nrqc synthesize` constructs a gate sequence from a complete set of target
stabilizers. The user supplies the target state, admitted gates, directed
couplings and search limits. The implementation extends the calculator's
existing typed rewrite application from modular arithmetic to a bounded
state-preparation search. The exact quantum identities remain those of
`modular_rewrite.py` and the existing cyclotomic executor.

```bash
nrqc synthesize native_relational_qc/calculator_examples/bell_goal.json --out bell-built.json
python3.12 benchmarks/panini_synthesis_audit.py --out synthesis-audit.json
```

The example supplies `XX=+1` and `ZZ=+1`, which uniquely specify the positive
Bell state. It supplies the directed edge `0 → 1` and no circuit. The search
finds `H(0), CX(0,1)`. Changing the first eigenvalue to `-1` requests the
negative Bell state, whose computational-basis probabilities coincide with
the positive state's. Exact phase-sensitive expectation checks distinguish
the two goals. Three- and four-wire GHZ targets work through the same input
schema and search, including a directed chain coupling map.

## Conditions, scope and derivation

The Pāṇini-inspired design uses an explicit domain, contextual eligibility,
restricted transformations and a retained derivation. The written grammar's
prefix examples, including its separate treatment of augment and
reduplication, motivate preserving the conditions of a rule. The
[PG274 source discussion](https://github.com/Parveen117/Recognition-Kernel-Framework/blob/3861c38680913b411b608cf43894c09813811954/research/panini_grammar/cutting_and_striking_ordered_prefix_and_reduplication/README.md)
records that linguistic work. The quantum gate productions and identities
are defined and checked separately in this application.

| Stage | Implemented condition |
| --- | --- |
| Target | Exactly `n_qubits` commuting, independent, nonidentity Pauli generators with eigenvalues ±1 |
| Gate production | A selected member of `h`, `x`, `z`, `cx`, acting on an existing wire |
| Controlled production | An ordered pair explicitly admitted by the coupling map |
| Reduction | Existing `X/CX/CCX` involution rules and their commuting-context conditions, independently replayed |
| State reuse | Exact equality up to global phase for evolution starting from the specified all-zero state |
| Acceptance | Every target expectation equals its requested eigenvalue exactly, followed by fresh execution through `calculator.calculate` |

The initial prototype admits 1–4 qubits and a real Clifford gate alphabet.
An independent generator set fixes a unique pure stabilizer state. Gate words
are explored breadth-first, with source-indexed production steps in the
successful result. Search states share the same future gate alphabet and
couplings, so equal state rays can share a search node. The existing
involution rewrite preserves the full unitary, including global phase.

The result includes an ordinary `nrqc-calculator-v1` request in
`calculator_request`, the exact calculator report, the accepted gate
derivation, rewrite certificates and examples of pruned words. The exported
request can be passed directly to `nrqc calculate`. `rewrite_examples` binds
the source and reduced word and includes replay verification for each of up
to four retained examples.

## Resource and validation results

`max_gates` is a depth-in-gate-count cap. `max_candidates` caps the number of
words checked, including duplicates and rewrite-pruned candidates.
`max_work` covers exact preparation, target readouts and final calculator
verification across the run. Other Python search and state-key overhead is
covered by the wall-time guard. `max_seconds` is checked between bounded
four-wire evaluations and again after final verification. The report records
each of these counts and elapsed wall time. The exact executor's failure
counter includes the work unit that exceeded its cap.

Budget exhaustion returns `incomplete` and no circuit request. A gate-count
boundary returns `depth_limit`. Exhausting the reachable state set returns
`search_exhausted`. Each of these statuses describes only the stated gate
family, couplings, initial state and limits. Successful packets set
`optimality_certified` to false.

The reproducible audit covers positive and negative Bell goals, three- and
four-wire GHZ goals, independent NumPy amplitude comparisons and a gate
alphabet lacking `H` as a negative control. The tests also cover unreachable
single-wire `Y` eigenstates, conflicting/dependent targets, zero-gate goals,
resource failures, certificate replay and the regular CLI entry point.
The existing self-learning classifier continues to use its existing phase
parameter trainer; the new entry point searches circuit topology from a
specified state goal. General unitary synthesis, non-Clifford target search,
hardware calibration and importing the full Sanskrit grammar remain future
integration work.
