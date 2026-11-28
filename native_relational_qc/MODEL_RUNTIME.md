# Saved-model execution and device-target compilation

Monty · 12 November 2026

`nrqc predict` loads a saved classifier, compiles its circuit to a declared
device profile, verifies the mapped operation and OpenQASM export exactly,
and executes the resulting calculator request. The record retains the model,
features, device contract, initial/final wire labels and exact probability.
`nrqc verify-prediction` reproduces that record from its inputs.

```bash
nrqc predict native_relational_qc/learning/structure_model.json \
  --features 5 17 --view first_layer \
  --device native_relational_qc/calculator_examples/three_wire_line.json \
  --out model-run.json
nrqc verify-prediction model-run.json
```

The supplied checkpoint is the selected model from the
[phase/structure experiment](../benchmarks/records/structure_learning_20261112.json).
It retains fingerprint
`e1d2389394de1274736c7b35eaade1cec59461090427c229d8613cdd2ba2b815`.
The runtime also accepts original v1 checkpoints and completed fit documents
whose top-level `model` contains a valid checkpoint. The feature-view argument
must match the saved model's encoding contract.

## Device contract and routing

A profile declares its name, wire count, directed CX edges, supported native
gate names and emitted-gate cap. The current model adapter supports up to four
target wires. Its gate vocabulary is H, S, S†, CX and the native phase powers
P2 through P64. A missing phase primitive or disconnected required route gives
a rejected request. The example profile describes a three-wire bidirectional
line in the software model.

The compiler enumerates the at-most-24 initial placements and ranks their CX
distance estimates. Each remote CX routes along a shortest usable path by
moving the control with SWAPs. SWAP is emitted as three CX operations. A
reverse-direction CX is emitted by conjugating the available direction with
H on both wires. The compiler updates logical wire positions after each SWAP,
then records the final physical readout wire. All emitted CXs use declared
directed edges. The placement/routing procedure is deterministic and bounded.

The selected classifier uses logical wires 0, 1 and 3. Logical wire 2 is idle
and starts at zero, so its program fits the three-wire example target. The
original three-CX classifier uses all four logical wires. Its program can be
routed on a four-wire directed line, with the corresponding extra gates.

## Exact acceptance and export

The verifier executes every basis input of the active logical register, both
before mapping and after mapping. It relabels the resulting amplitudes with
the final layout and checks equality including the retained global phase.
Omitted logical wires and spare target wires are initialized to zero. Thus the
three-active-wire case checks eight columns and a four-active-wire case checks
16. The record explicitly states this active-register scope.

The existing dependency-free OpenQASM 2 bridge emits symbolic dyadic phase
angles, reads the exported program back, and checks it on those same basis
inputs. Fresh execution through `calculator.calculate` then checks the final
readout against the source classifier. One exact-work budget spans every
verification preparation and the final calculation. Budget exhaustion returns
an incomplete CLI result and no accepted prediction record.

The successful JSON contains the following usable outputs.

| Field | Content |
| --- | --- |
| `calculator_request` | Runnable exact calculator input with the mapped readout query |
| `openqasm` | Unmeasured static OpenQASM 2 program with exact symbolic phases |
| `mapping` | Initial/final logical-to-physical labels and native source spans |
| `probability_one` | Exact Q(zeta_64) value for the classifier's output |
| `predicted` | Class selected by the existing strict-above-one-half rule |
| `verification` | Basis-column count, admitted input scope and QASM check |
| `fingerprint` | Content binding for replay |

The hardware adapter can obtain the measurement wire from
`mapping.final_layout["3"]`. The OpenQASM program leaves terminal measurement
and shot collection to that adapter. Profile declarations and these exact
ideal calculations provide an offline target contract. Device calibration,
hardware execution and recorded measurement evidence have their own work items
in [finalization](FINALIZATION.md).

## Reproduce the deployment qualification

```bash
python3.12 benchmarks/model_runtime_audit.py --out model-runtime-audit.json
```

The [12 November record](../benchmarks/records/model_runtime_20261112.json)
covers 136 labelled cases over 73 distinct model/input/device programs.
Identical point-only inputs reuse their exact checked program. The 73 programs
cover 656 active-register basis inputs and each program is replayed. Independent
NumPy predictions have maximum absolute probability error approximately
3.33e-16.

| Saved-model task and target | Correct / cases | Declared target wires |
| --- | ---: | ---: |
| Selected curvature, three-wire line | 64 / 64 | 3 |
| Original XOR, software all-to-all | 4 / 4 | 4 |
| Original point-only control | 32 / 64 | 4 |
| Original curvature, directed four-wire line | 4 / 4 | 4 |

The point-only control retains its information limitation. All runs are local
ideal calculations, with zero hardware jobs.
