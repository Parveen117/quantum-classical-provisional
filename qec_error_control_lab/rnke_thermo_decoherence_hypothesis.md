# Thermodynamic-response decoherence hypothesis (bounded, testable)

**Status: HYPOTHESIS UNDER TEST — not a theorem, not in the certified ledger.**
Claim boundary: this note proposes a *physically admissible* form for a
recognition dissipator and one *falsifiable* invariant that can be checked on
IBM backend calibration data. It establishes nothing until the test in §4 is
run and passes on predeclared thresholds.

## 1. What was proposed (and why it is not admissible as written)

Proposed: `D̂ = λ_p ∇² + Z_s ∂/∂t + χ Ĥ`, `ρ̇ = −(i/ħ)[H,ρ] + D̂[ρ]`.

Problems, each fatal for a master equation:
- `∇²` acting on a density *operator* is undefined (needs a phase-space or
  position-kernel representation to mean anything).
- `Z_s ∂/∂t` inside the dissipator gives `(1 − Z_s) ρ̇ = …` — a rescaling,
  not memory. Memory is a kernel `∫ K(t−s) ρ(s) ds` (Nakajima–Zwanzig).
- `χ Ĥ[ρ]` leaves the superoperator unspecified (`Hρ`, `[H,ρ]`, `{H,ρ}` differ).
- Nothing guarantees `tr ρ = 1` and `ρ ≥ 0` are preserved.

## 2. Admissible form (Lindblad / GKSL, same three channels)

    ρ̇ = −(i/ħ)[H + χ H_rec , ρ]  +  Σ_k γ_k ( L_k ρ L_k† − ½{L_k†L_k, ρ} )
         + ∫_0^t K_Z(t−s) 𝓛_mem[ρ(s)] ds            (memory, optional, NZ form)

with the three Recognition-framework channels mapped as rates, not operators:

| channel | framework object | Lindblad role |
|---|---|---|
| λ_p  (entropy–capacity, λ_p^th = −ST/C_p) | response-cost coordinate | amplitude-damping rate γ₁ ∝ 1/T₁ |
| Z_s  (isentropic stiffness, from K_S = −C_s) | memory/return strength | dephasing rate γ_φ ∝ 1/T_φ, or NZ kernel strength |
| χ    (Hamiltonian coupling) | recognition Hamiltonian H_rec | coherent Lamb-type shift (unitary, no dissipation) |

Jump operators are square-sourced (`L_k†L_k ≥ 0`), so CPTP is automatic — this is
exactly where the framework's cut-square positivity (a†★a) belongs: it is the
reason the dissipator is physical, not an extra axiom.

## 3. The one invariant this buys (the only thing worth testing now)

In the thermodynamic capsule (01_response_tetrad), the flat-closure identity
Γ_c Γ_m = 1 says the caloric ratio (C_v/C_p) and the mechanical ratio (K_S/K_T)
are reciprocal on the equilibrium sector. The decoherence analogue:

    Γ_q := (γ₁ / γ₂) · (T₁ / T₂)      with γ₂ = γ₁/2 + γ_φ ,  1/T₂ = 1/(2T₁) + 1/T_φ

is identically **1** for *any* Markovian qubit — so it is a *renaming test*, not a
finding (TAUT-1 discipline). The non-trivial, falsifiable statement is the
**sector projection**:

    δ_q := log( 2T₁ / T₂ )  ≥ 0   on the Markovian flat sector  (T₂ ≤ 2T₁),

and the hypothesis H1: *across qubits of one backend at one calibration epoch,
the residue δ_q correlates with the recognition residue measured by the QEC
theorem binding (per-stabilizer |⟨S_i⟩| confidence) on the same qubits.*
That is: qubits with larger δ_q (more pure dephasing relative to relaxation —
"less stiff") show lower syndrome-bit confidence.

Falsified if: Spearman ρ(δ_q, confidence) ≤ 0 on ≥ 8 qubits with p < 0.05, or
if any T₂ > 2T₁ (non-Markovian flag → model form inadmissible at that epoch).

## 4. Test protocol (predeclared, needs one data pull)

1. Pull backend properties for the 17 qubits of job `da2raps3jnrc73ae9n80`
   at run time: T₁, T₂, readout error, CX error per edge. Pin JSON (GPT task).
2. Compute δ_q per ancilla qubit; flag any T₂ > 2T₁.
3. Pair each stabilizer ancilla with its confidence |⟨S_i⟩| from
   `rnke_theorem_binding_hw` (already certified, `EXPECTED_THEOREM_BINDING_HW`).
4. Report Spearman ρ, exact bootstrap CI, and the renaming control
   (Γ_q ≡ 1 must reproduce — if it doesn't, the data pull is wrong).
5. Verdict: PASS_H1 / FAIL_H1 / ABSTAIN (non-Markovian flags) — certificate, pin.

Whatever the verdict, the deliverable is a *test*, not a claim. It goes on a
deck slide as "hypothesis under test", never as a result, until §4 is executed.

## 5. What this does NOT do

No new physics, no RH, no K₀, no "decoherence from thermodynamics" claim.
It gives the proposed equation a physical form and one honest experiment.
