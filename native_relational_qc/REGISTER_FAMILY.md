# Register family: 2056 as one point, not a ceiling

**Author: Monty.** The number 2056 in [DESIGN_2056.md](DESIGN_2056.md) is a
design choice: 64 banks of 32 data sites plus 8 workspace sites on an open
chain. Nothing in the semantics, the cost laws or the engines singles it out.
This note makes the register a parametric family `N = banks * width +
workspace`, turns the engines' constant into a declared bound, and runs the
whole-register qualification families well beyond 2056.

[Code](register_family.py) · [Tests](../tests/test_native_register_family.py) ·
[Audit](../benchmarks/register_family_audit.py) · [Qualification](register_family/qualification.json).

## 1. What changed in the engines

`large_register.MAX_LARGE_QUBITS` was a fixed constant read by the Pauli
engine and the Clifford frame at compile time. It is now the default of a
declared bound: `register_bound()` reads it and `declare_register_bound(n)`
sets it (ceiling 2^22, to keep Pauli bit words finite). The default stays
2056, so every existing test, pin and report is unchanged; the Pauli engine
and Clifford frame now read the live bound instead of an imported copy. No
engine semantics, gate alphabet, budget or exactness rule changed. The
historical source pins of earlier milestones reject the edited files by
design; those milestones replay from their recorded commits.

## 2. The family

`register_plan(banks, width, workspace)` returns the chain allocation and
its edge counts for any size: `N - 1` edges split as `banks*(width-1)` within
banks, `banks-1` between banks, `workspace-1` within workspace and one data
to workspace link. The design point reproduces the table of DESIGN_2056
section 1 exactly: 2055 = 1984 + 63 + 7 + 1.

`cost_laws(N, chi_max)` states the section 4 bounds for every N: tableau
bits `2N(2N+1)` and MPS coefficient bound `2N chi^2`. Both are polynomial in
N. `family_predictions(N)` gives the symbolic answers of qualification
families A and B for every N. None of these had a cutoff at 2056; the
derivations in the design note never used the value.

## 3. Wider exact runs

`qualify_ghz(N)` raises the bound for the call, runs family A on the
`stabilizer` engine (all-X expectation, end-to-end ZZ, two-site 00 marginal)
and family B on `clifford_t` (all-X and Y0 X-rest with the retained T
phase), compares exactly, and restores the bound. The audit records:

| N | Family A | seconds | Family B | seconds |
| ---: | --- | ---: | --- | ---: |
| 2056 | pass | 0.008 | pass | 0.155 |
| 4112 | pass | 0.018 | pass | 0.361 |
| 8224 | pass | 0.049 | pass | 0.811 |
| 16448 | pass | 0.253 | pass | 1.479 |
| 32896 | pass | 0.87 | pass | 3.109 |

Timings are from one container run and are orientation only. They show the
cost growing polynomially with N for these admitted families, which is what
the design note's admission policy predicts. They do not show efficient
simulation of arbitrary circuits at any N; deep T-rich circuits still hit
the declared term and work budgets, exactly as before.

## 4. What does not generalise: the single-photon carrier

`carrier_scaling(N, encoding)` counts optical resources for the same N:

| Encoding | Photons | Paths or modes | Scales |
| --- | ---: | --- | --- |
| Single-photon path (the v0.9 exchange core) | 1 | `2^N` paths; `2^2056` at the design point | No |
| Banked path, width 4 | `N/4` | 16 paths per bank | Only at tiny widths |
| Dual rail, one photon per site | `N` | `2N` modes; 4112 at the design point | Yes, in count |

So "as large as you like" is true for the verification layer and false for
the present carrier. Making the hardware a family too means moving from the
single-photon path code to dual-rail (or an equivalent one-photon-per-site)
encoding, where the exchange MZI is the single-site gate and two-site gates
need photon-photon interference. That is why the temperature-sweep protocol
already carries a two-photon HOM point: it is the first measurement of the
scalable route, not a decoration of the single-photon one.

## 5. Reproduction

```bash
python benchmarks/register_family_audit.py
```

Closed: the parametric register family with exact chain counts and cost
laws, a declared and restorable engine bound, exact family A and B runs at
2056 to 32896 sites, and the carrier-count comparison.

Open: everything the design note left open (hardware technology, error
correction, calibration), plus the dual-rail carrier design itself.
