"""RNKE theorem binding over measured Shor syndrome shots (hardware).

Two certified-theorem hooks from the Recognition framework, applied to the
IBM ancilla-extraction run, exact rational arithmetic, certificate-bound:

(T1) Seam integer  k_Σ = n₊(B − I)  (D03 compact seam integer, LEAN-2 BSInertia)
     Here the Birman–Schwinger object is the diagonal of stabilizer
     expectations on the cut: B_ii = (1 − ⟨S_i⟩)/1 with threshold at 1.
     ⟨S_i⟩ = +1 (no syndrome) ⇒ B_ii = 0 < 1 ; ⟨S_i⟩ = −1 ⇒ B_ii = 2 > 1.
     k_Σ = #{i : ⟨S_i⟩ < 0} is the operator-level syndrome weight, computed
     from expectations (not from per-shot bitstring voting).  We compare it
     with the declared injected-error weight and with the bitstring modal
     syndrome.

(T2) Square-sourced residue  (SOS-1: PSD ⟺ explicit weighted SOS via exact LDL;
     cut-square positivity a†★a)
     Form the 8×8 second-moment Gram G = (1/N) Σ_shots s sᵀ with s ∈ {±1}^8.
     G is PSD by construction (it is a sum of squares) — SOS-1 gives the
     explicit weights.  The RESIDUE is the departure of G from the ideal
     square G_ideal = σσᵀ (σ = expected syndrome signs): D = G − G_ideal is
     indefinite in general; its inertia (n₊, n₀, n₋) and the most-negative
     witness direction are the typed residue.  Ideal hardware ⇒ D = 0 ⇒ K=0
     (recognition collapse).  Everything exact over ℚ (Fractions, LDL with
     pivoting-free symmetric elimination; zero pivots handled).

Claim boundary: these are executable consequences of finite theorems on
finite measured data.  No claim about RH, K₀, thresholds, or fault tolerance.
"""
from __future__ import annotations

import glob
import hashlib
import json
import pathlib
from fractions import Fraction as Fr
from typing import Sequence

HERE = pathlib.Path(__file__).resolve().parent
PROTOCOL = "rnke-theorem-binding-shor-hardware-v1"


def cj(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(o) -> str:
    return hashlib.sha256(cj(o).encode()).hexdigest()


# ---------------------------------------------------------------- exact LDLᵀ
def ldl_inertia(M: list[list[Fr]]) -> tuple[tuple[int, int, int], list[Fr], list[list[Fr]]]:
    """Exact symmetric elimination returning inertia via Sylvester (signs of pivots).
    Diagonal pivoting; when all remaining diagonals vanish, a congruence
    row/col addition creates a nonzero pivot (inertia-preserving). L is the
    elimination multiplier table for the (possibly congruence-modified) matrix;
    for PSD inputs with nonzero pivots it is the exact LDLᵀ factor."""
    n = len(M)
    A = [row[:] for row in M]
    perm = list(range(n))
    L = [[Fr(0)] * n for _ in range(n)]
    D = [Fr(0)] * n
    for k in range(n):
        # pick largest |A[j][j]| among remaining
        j = max(range(k, n), key=lambda t: abs(A[t][t]))
        if j != k:
            A[k], A[j] = A[j], A[k]
            for r in A:
                r[k], r[j] = r[j], r[k]
            perm[k], perm[j] = perm[j], perm[k]
            L[k], L[j] = L[j], L[k]
            for r in L:
                r[k], r[j] = r[j], r[k]
        p = A[k][k]
        if p == 0:
            # all remaining diagonals zero: find off-diagonal a=A[k][j]!=0 and apply the
            # congruence (row_k += row_j, col_k += col_j) => new A[k][k] = 2a != 0.
            # Congruence preserves inertia (Sylvester). If none, column is zero.
            j = next((t for t in range(k + 1, n) if A[k][t] != 0), None)
            if j is None:
                D[k] = Fr(0); L[k][k] = Fr(1); continue
            for t in range(n):
                A[k][t] += A[j][t]
            for t in range(n):
                A[t][k] += A[t][j]
            p = A[k][k]
            L[k][k] = Fr(1)
        D[k] = p
        L[k][k] = Fr(1)
        for i in range(k + 1, n):
            L[i][k] = A[i][k] / p
        for i in range(k + 1, n):
            for jj in range(k + 1, n):
                A[i][jj] -= L[i][k] * p * L[jj][k]
    pos = sum(1 for d in D if d > 0)
    neg = sum(1 for d in D if d < 0)
    zer = n - pos - neg
    return (pos, zer, neg), D, L


def sos_certificate(G: list[list[Fr]]) -> dict:
    (p, z, m), D, L = ldl_inertia(G)
    return {"inertia": [p, z, m], "psd": m == 0,
            "weights": [str(d) for d in D],
            "note": "G = L diag(D) Lᵀ exactly; PSD ⟺ all weights ≥ 0 (SOS-1)"}


# ------------------------------------------------------------- per-case hook
def analyse_case(case: dict) -> dict:
    counts: dict[str, int] = case["syndrome_counts"]
    exp_bits = case["expected_syndrome"]
    N = sum(counts.values())
    nbits = len(exp_bits)
    # stabilizer ±1 values: bit 0 -> +1 (no flip), bit 1 -> -1
    def sv(bits: str) -> list[int]:
        return [1 if b == "0" else -1 for b in bits]
    sigma = sv(exp_bits)
    # expectations (exact)
    E = [Fr(0)] * nbits
    G = [[Fr(0)] * nbits for _ in range(nbits)]
    for bits, n in counts.items():
        s = sv(bits)
        for i in range(nbits):
            E[i] += n * s[i]
            for j in range(nbits):
                G[i][j] += n * s[i] * s[j]
    E = [e / N for e in E]
    G = [[g / N for g in row] for row in G]
    # (T1) seam integer: threshold count on B = diag(1 - <S_i>), threshold 1
    B_diag = [1 - e for e in E]
    k_sigma = sum(1 for b in B_diag if b > 1)          # n₊(B − I)
    on_threshold = sum(1 for b in B_diag if b == 1)    # <S_i> = 0 exactly
    declared_weight = exp_bits.count("1")
    expectation_syndrome = "".join("1" if b > 1 else "0" for b in B_diag)
    # (T2) residue vs ideal square
    D = [[G[i][j] - sigma[i] * sigma[j] for j in range(nbits)] for i in range(nbits)]
    inertia_D, Dd, _ = ldl_inertia(D)
    gram_sos = sos_certificate(G)
    # residue magnitude: Frobenius of D (exact) and max |entry|
    frob2 = sum(D[i][j] ** 2 for i in range(nbits) for j in range(nbits))
    maxabs = max(abs(D[i][j]) for i in range(nbits) for j in range(nbits))
    # per-stabilizer orientation confidence (LEAN-3 one-bit label, noise exposed)
    conf = [abs(e) for e in E]
    return {
        "label": case["label"], "shots": N,
        "expected_syndrome": exp_bits,
        "stabilizer_expectations": [str(e) for e in E],
        "T1_seam_integer": {
            "k_sigma": k_sigma, "on_threshold": on_threshold,
            "declared_error_weight": declared_weight,
            "expectation_syndrome": expectation_syndrome,
            "matches_expected": expectation_syndrome == exp_bits,
            "bitstring_modal_syndrome": case["modal_syndromes"][0],
        },
        "T2_square_residue": {
            "gram_sos": gram_sos,
            "residue_inertia_D=G-σσᵀ": list(inertia_D),
            "residue_frobenius_sq": str(frob2),
            "residue_max_abs": str(maxabs),
            "recognition_collapse_K0": frob2 == 0,
        },
        "T3_orientation_confidence": [str(c) for c in conf],
    }


def build() -> dict:
    cert_path = sorted(glob.glob(str(HERE / "hardware_evidence" / "*_hardware_certificate.json")))[0]
    hw = json.load(open(cert_path))
    cases = [analyse_case(c) for c in hw["cases"]]
    checks = {
        "seam_integer_equals_declared_weight_all_cases":
            all(c["T1_seam_integer"]["k_sigma"] == c["T1_seam_integer"]["declared_error_weight"] for c in cases),
        "expectation_syndrome_matches_expected_all_cases":
            all(c["T1_seam_integer"]["matches_expected"] for c in cases),
        "expectation_syndrome_equals_bitstring_mode_all_cases":
            all(c["T1_seam_integer"]["expectation_syndrome"] == c["T1_seam_integer"]["bitstring_modal_syndrome"] for c in cases),
        "all_grams_psd_with_explicit_sos": all(c["T2_square_residue"]["gram_sos"]["psd"] for c in cases),
        "no_case_in_recognition_collapse": all(not c["T2_square_residue"]["recognition_collapse_K0"] for c in cases),
        "no_stabilizer_on_threshold": all(c["T1_seam_integer"]["on_threshold"] == 0 for c in cases),
    }
    body = {
        "protocol": PROTOCOL,
        "source_hardware_certificate_sha256": hw["certificate_sha256"],
        "backend": hw["backend"], "job_id": hw["job_id"],
        "theorems_bound": {
            "T1": "D03 compact seam integer / LEAN-2 BSInertia: k_Σ = n₊(B−I), B=diag(1−⟨S_i⟩)",
            "T2": "SOS-1 PSD⟺weighted-SOS (exact LDL) + cut-square positivity; residue D=G−σσᵀ typed by inertia",
            "T3": "LEAN-3 sign localization: stabilizer label is one orientation bit; |⟨S_i⟩| = exposed confidence",
        },
        "cases": cases, "checks": checks,
        "classification": "PASS_RNKE_THEOREM_BINDING_HW_V1" if all(checks.values()) else "FAIL_RNKE_THEOREM_BINDING_HW_V1",
        "claim_boundary": ("Executable finite-theorem consequences on one IBM ancilla-extraction round "
                           "(4 cases × 4096 shots). Not RH, K₀, threshold, or fault-tolerance evidence."),
    }
    body["certificate_sha256"] = sha(body)
    return body


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=str(HERE / "generated" / "rnke_theorem_binding_hw_certificate.json"))
    a = ap.parse_args()
    cert = build()
    pathlib.Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(a.output).write_text(cj(cert) + "\n")
    slim = {"classification": cert["classification"], "checks": cert["checks"],
            "cases": [{k: c[k] for k in ("label", "T1_seam_integer")} | {"residue_inertia": c["T2_square_residue"]["residue_inertia_D=G-σσᵀ"], "residue_max_abs": c["T2_square_residue"]["residue_max_abs"], "conf": c["T3_orientation_confidence"]} for c in cert["cases"]],
            "certificate_sha256": cert["certificate_sha256"]}
    print(json.dumps(slim, indent=1, ensure_ascii=False))
