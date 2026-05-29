"""
Example 8: Quantum Fredholm Recognition-Kernel Engine
=====================================================

Purpose:
    Filing/enablement-grade prototype for a quantum / quantum-classical
    Recognition-Kernel embodiment.

Core PCT alignment:
    - Uses notational index n, not physical time.
    - Uses recognition operator R_q over quantum-state signatures.
    - Uses evolution/error operator E_q over a candidate successor state.
    - Computes kernel gaps and technical actions.
    - Includes Recognition--Null Fredholm determinant split:
          D_{xi,eta}(lambda) = Delta_R(lambda; xi) + Delta_N(lambda; xi, eta)
          K_Fred = |Delta_N| / (|Delta_R| + eps)

No external quantum library required.
Uses only numpy, pandas, matplotlib, json.

Run in Jupyter:
    %run quantum_fredholm_recognition_kernel_engine.py

Generated outputs:
    TABLE_ENABLEMENT_08_Quantum_Fredholm_Recognition_Result.csv
    RESULT_ENABLEMENT_08_Quantum_Fredholm_Recognition_Result.json
    FIG_ENABLEMENT_08A_Quantum_Fredholm_Recognition_Gap_Result.png
    FIG_ENABLEMENT_08B_Quantum_Error_Control_Action_Result.png
    FIG_PATENT_13_Quantum_Fredholm_Recognition_Kernel_Pipeline.png

Important:
    This is an enablement simulation / technical embodiment.
    It is not a claim that this is production quantum hardware control.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch


EPS = 1e-12
OUT = Path(".")


# ---------------------------------------------------------------------
# Basic matrices
# ---------------------------------------------------------------------

I2 = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.array([[1, 0], [0, -1]], dtype=complex)

# EMK/Recognition operators in 2D real sector:
# R = circular rotation, R^2 = -I
# K = seam flip, K^2 = I
R2 = np.array([[0, -1], [1, 0]], dtype=float)
K2 = np.array([[0, 1], [1, 0]], dtype=float)


def kron(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.kron(a, b)


def density_from_state(psi: np.ndarray) -> np.ndarray:
    psi = np.asarray(psi, dtype=complex).reshape(-1, 1)
    return psi @ psi.conj().T


def bell_phi_plus() -> np.ndarray:
    psi = np.zeros(4, dtype=complex)
    psi[0] = 1 / np.sqrt(2)
    psi[3] = 1 / np.sqrt(2)
    return psi


def expectation(rho: np.ndarray, obs: np.ndarray) -> float:
    return float(np.real(np.trace(rho @ obs)))


def apply_unitary(rho: np.ndarray, U: np.ndarray) -> np.ndarray:
    return U @ rho @ U.conj().T


def depolarize(rho: np.ndarray, p: float) -> np.ndarray:
    dim = rho.shape[0]
    return (1 - p) * rho + p * np.eye(dim, dtype=complex) / dim


# ---------------------------------------------------------------------
# Matrix exponential for the 2x2 circular-hyperbolic generator
# G = xi R + eta K.
# Uses eigendecomposition to avoid scipy dependency.
# ---------------------------------------------------------------------

def expm_2x2(A: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eig(A)
    return vecs @ np.diag(np.exp(vals)) @ np.linalg.inv(vecs)


def circular_hyperbolic_block(distance: float, xi: float, eta: float) -> np.ndarray:
    """
    Phi(distance; xi, eta) = exp(-distance * (xi R + eta K)).
    R^2 = -I, K^2 = I.
    """
    G = xi * R2 + eta * K2
    return expm_2x2(-float(distance) * G)


def fredholm_discretization(
    xi: float,
    eta: float,
    grid_points: int = 12,
    length: float = 1.0,
) -> np.ndarray:
    """
    Finite-rank / Nyström-style Fredholm approximation.
    Produces a 2N x 2N block matrix using the circular-hyperbolic kernel.
    """
    xs = np.linspace(0.0, length, grid_points)
    dx = length / max(grid_points - 1, 1)

    blocks = []
    for x in xs:
        row_blocks = []
        for y in xs:
            block = circular_hyperbolic_block(abs(x - y), xi, eta) * dx
            row_blocks.append(block)
        blocks.append(row_blocks)

    return np.block(blocks)


def fredholm_det_split(
    xi: float,
    eta: float,
    lam: float = 0.08,
    grid_points: int = 12,
) -> Dict[str, float]:
    """
    Recognition--Null Fredholm determinant split.

    D_full = det(I - lambda F_{xi,eta})
    D_rec  = det(I - lambda F_{xi,0})     recognized/circular collapse component
    D_null = D_full - D_rec               non-recognition residue
    K_Fred = |D_null| / (|D_rec| + eps)
    """
    F_full = fredholm_discretization(xi=xi, eta=eta, grid_points=grid_points)
    F_rec = fredholm_discretization(xi=xi, eta=0.0, grid_points=grid_points)

    eye_full = np.eye(F_full.shape[0], dtype=complex)
    eye_rec = np.eye(F_rec.shape[0], dtype=complex)

    D_full = np.linalg.det(eye_full - lam * F_full)
    D_rec = np.linalg.det(eye_rec - lam * F_rec)
    D_null = D_full - D_rec

    gap = abs(D_null) / (abs(D_rec) + EPS)

    return {
        "D_full_real": float(np.real(D_full)),
        "D_full_imag": float(np.imag(D_full)),
        "Delta_R_abs": float(abs(D_rec)),
        "Delta_N_abs": float(abs(D_null)),
        "fredholm_gap": float(gap),
    }


# ---------------------------------------------------------------------
# Quantum Recognition Kernel
# ---------------------------------------------------------------------

STABILIZERS = {
    "ZZ": kron(Z, Z),
    "XX": kron(X, X),
}

PHASE_OBSERVABLES = {
    "ZI": kron(Z, I2),
    "IZ": kron(I2, Z),
}


def recognition_signature(rho: np.ndarray) -> np.ndarray:
    """
    Recognition operator R_q:
        Extract stabilizer/code-space and phase signatures.
    """
    values = []
    for obs in STABILIZERS.values():
        values.append(expectation(rho, obs))
    for obs in PHASE_OBSERVABLES.values():
        values.append(expectation(rho, obs))
    purity = float(np.real(np.trace(rho @ rho)))
    values.append(purity)
    return np.asarray(values, dtype=float)


def quantum_recognition_gap(sig0: np.ndarray, sig1: np.ndarray) -> float:
    """
    Normed recognition gap between successive notational states n and n+1.
    """
    return float(np.linalg.norm(sig1 - sig0) / (np.linalg.norm(sig0) + EPS))


def syndrome_gap(sig1: np.ndarray) -> float:
    """
    For |Phi+>, ZZ and XX should be near +1.
    Syndrome gap measures code-space departure.
    """
    zz, xx = sig1[0], sig1[1]
    return float((abs(1 - zz) + abs(1 - xx)) / 2.0)


def classify_gap(unified_gap: float, syndrome: float) -> Tuple[str, str]:
    """
    Thresholded technical action.
    """
    if syndrome > 0.95:
        return (
            "APPLY_QUANTUM_CORRECTION",
            "Apply correction, repeat syndrome extraction, or route to recovery."
        )
    if unified_gap < 0.15:
        return (
            "ACCEPT_Q_STATE",
            "Accept state; recognition collapse is within tolerance."
        )
    if unified_gap < 0.30:
        return (
            "MONITOR_REPEAT_SYNDROME",
            "Monitor bounded residue and repeat syndrome or phase-consistency check."
        )
    return (
        "REJECT_OR_REINITIALIZE",
        "Reject state, reinitialize, or flag decoherence / non-recognition."
    )


@dataclass
class QuantumRecognitionResult:
    case: str
    notational_index_n: int
    evolution_description: str
    quantum_recognition_gap: float
    syndrome_gap: float
    fredholm_gap: float
    unified_gap: float
    phase_signature_ZZ: float
    phase_signature_XX: float
    purity: float
    decision: str
    technical_action: str
    Delta_R_abs: float
    Delta_N_abs: float


def build_cases() -> List[Dict]:
    """
    Notational transition cases S(n) -> S(n+1).
    """
    psi = bell_phi_plus()
    rho0 = density_from_state(psi)

    cases = []

    # Case A: identity / valid code-space state
    cases.append({
        "case": "Valid code-space state",
        "description": "Identity evolution, recognition preserved",
        "rho1": rho0.copy(),
        "eta": 0.0,
    })

    # Case B: bounded phase drift on first qubit
    theta = 0.16
    U_phase = kron(np.array([[np.exp(-1j * theta / 2), 0],
                             [0, np.exp(1j * theta / 2)]], dtype=complex), I2)
    cases.append({
        "case": "Bounded phase drift",
        "description": "Small phase drift, bounded recognition residue",
        "rho1": apply_unitary(rho0, U_phase),
        "eta": 0.08,
    })

    # Case C: bit flip on first qubit: correctable syndrome-like departure
    U_bit = kron(X, I2)
    cases.append({
        "case": "Bit-flip error",
        "description": "Bit-flip error creates code-space syndrome",
        "rho1": apply_unitary(rho0, U_bit),
        "eta": 0.35,
    })

    # Case D: phase flip on first qubit
    U_phase_flip = kron(Z, I2)
    cases.append({
        "case": "Phase-flip error",
        "description": "Phase-flip error creates stabilizer-sign change",
        "rho1": apply_unitary(rho0, U_phase_flip),
        "eta": 0.32,
    })

    # Case E: strong decoherence / depolarization
    cases.append({
        "case": "Severe decoherence",
        "description": "Depolarized mixed state, recognition loss",
        "rho1": depolarize(rho0, p=0.70),
        "eta": 0.75,
    })

    return cases


def run_quantum_recognition_engine() -> pd.DataFrame:
    rho0 = density_from_state(bell_phi_plus())
    sig0 = recognition_signature(rho0)

    rows: List[QuantumRecognitionResult] = []

    xi = 1.0
    lam = 0.08

    for n, c in enumerate(build_cases()):
        rho1 = c["rho1"]
        sig1 = recognition_signature(rho1)

        q_gap = quantum_recognition_gap(sig0, sig1)
        s_gap = syndrome_gap(sig1)

        fred = fredholm_det_split(
            xi=xi,
            eta=float(c["eta"]),
            lam=lam,
            grid_points=12,
        )

        # Weighted unified Recognition--Fredholm quantum gap.
        unified = 0.45 * q_gap + 0.35 * s_gap + 0.20 * fred["fredholm_gap"]

        decision, action = classify_gap(unified, s_gap)

        rows.append(QuantumRecognitionResult(
            case=c["case"],
            notational_index_n=int(n),
            evolution_description=c["description"],
            quantum_recognition_gap=float(q_gap),
            syndrome_gap=float(s_gap),
            fredholm_gap=float(fred["fredholm_gap"]),
            unified_gap=float(unified),
            phase_signature_ZZ=float(sig1[0]),
            phase_signature_XX=float(sig1[1]),
            purity=float(sig1[4]),
            decision=decision,
            technical_action=action,
            Delta_R_abs=float(fred["Delta_R_abs"]),
            Delta_N_abs=float(fred["Delta_N_abs"]),
        ))

    df = pd.DataFrame([asdict(r) for r in rows])
    df.to_csv(OUT / "TABLE_ENABLEMENT_08_Quantum_Fredholm_Recognition_Result.csv", index=False)

    with open(OUT / "RESULT_ENABLEMENT_08_Quantum_Fredholm_Recognition_Result.json", "w", encoding="utf-8") as f:
        json.dump(df.to_dict(orient="records"), f, indent=2)

    return df


# ---------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------

def make_gap_figure(df: pd.DataFrame) -> None:
    x = np.arange(len(df))
    width = 0.25

    plt.figure(figsize=(15, 7))
    plt.bar(x - width, df["quantum_recognition_gap"], width, label="Quantum Recognition Gap")
    plt.bar(x, df["fredholm_gap"], width, label="Recognition-Null Fredholm Gap")
    plt.bar(x + width, df["unified_gap"], width, label="Unified Gap")

    plt.axhline(0.15, linestyle="--", linewidth=1.5, label="Bounded Threshold = 0.15")
    plt.axhline(0.30, linestyle=":", linewidth=2.0, label="Actionable Threshold = 0.30")

    for i, row in df.iterrows():
        plt.text(i + width, row["unified_gap"] + 0.025, f"{row['unified_gap']:.3f}", ha="center", fontsize=8)

    plt.xticks(x, df["case"], rotation=25, ha="right")
    plt.ylabel("Gap Score")
    plt.title("Example 8A: Quantum Recognition--Null Fredholm Kernel Gap Result")
    plt.legend()
    plt.tight_layout()

    fname = OUT / "FIG_ENABLEMENT_08A_Quantum_Fredholm_Recognition_Gap_Result.png"
    plt.savefig(fname, dpi=300, bbox_inches="tight")
    plt.show()
    print("Saved:", fname)


def make_action_figure(df: pd.DataFrame) -> None:
    score_map = {
        "ACCEPT_Q_STATE": 1.0,
        "MONITOR_REPEAT_SYNDROME": 0.70,
        "APPLY_QUANTUM_CORRECTION": 0.45,
        "REJECT_OR_REINITIALIZE": 0.0,
    }
    action_scores = df["decision"].map(score_map).fillna(0.0)

    plt.figure(figsize=(15, 7))
    plt.bar(df["case"], action_scores)

    for i, row in df.iterrows():
        plt.text(
            i,
            action_scores.iloc[i] + 0.035,
            row["decision"].replace("_", "\n"),
            ha="center",
            fontsize=8,
        )

    plt.ylim(0, 1.25)
    plt.ylabel("Control Decision Score")
    plt.title("Example 8B: Quantum-Classical Error Recognition and Technical Action")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()

    fname = OUT / "FIG_ENABLEMENT_08B_Quantum_Error_Control_Action_Result.png"
    plt.savefig(fname, dpi=300, bbox_inches="tight")
    plt.show()
    print("Saved:", fname)


def make_pipeline_figure() -> None:
    fig, ax = plt.subplots(figsize=(17, 6))
    ax.set_xlim(0, 17)
    ax.set_ylim(0, 6)
    ax.axis("off")

    boxes = [
        (0.4, 2.7, 2.2, 1.0, "Quantum /\nHybrid State"),
        (3.1, 2.7, 2.2, 1.0, "Recognition\nOperator"),
        (5.8, 2.7, 2.4, 1.0, "Syndrome /\nInvariant Gap"),
        (8.8, 2.7, 2.6, 1.0, "Recognition-Null\nFredholm Split"),
        (12.0, 2.7, 2.0, 1.0, "Threshold\nClassifier"),
        (14.5, 2.7, 2.1, 1.0, "Technical\nAction"),
    ]

    for bx, by, bw, bh, text in boxes:
        rect = Rectangle((bx, by), bw, bh, linewidth=1.8, edgecolor="black", facecolor="white")
        ax.add_patch(rect)
        ax.text(bx + bw/2, by + bh/2, text, ha="center", va="center", fontsize=10)

    for i in range(len(boxes) - 1):
        x1 = boxes[i][0] + boxes[i][2]
        y1 = boxes[i][1] + boxes[i][3] / 2
        x2 = boxes[i+1][0]
        y2 = boxes[i+1][1] + boxes[i+1][3] / 2
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->", mutation_scale=18, linewidth=1.8))

    ax.text(
        0.8,
        0.70,
        "Notational index n supplies succession. The engine extracts quantum/code-space invariants,\n"
        "computes recognition and Fredholm determinant gaps, then accepts, monitors, corrects, or reinitializes.",
        fontsize=10,
        ha="left"
    )

    plt.title("Example 8: Quantum Recognition--Null Fredholm Error-Control Pipeline")
    plt.tight_layout()

    fname = OUT / "FIG_PATENT_13_Quantum_Fredholm_Recognition_Kernel_Pipeline.png"
    plt.savefig(fname, dpi=300, bbox_inches="tight")
    plt.show()
    print("Saved:", fname)


def make_caption_and_map(df: pd.DataFrame) -> None:
    embodiment_map = pd.DataFrame([
        {
            "Embodiment": "Example 8A: Quantum Recognition Gap",
            "Input": "Quantum or quantum-classical state at notational index n",
            "Recognition-Kernel Operation": "Extract stabilizer-like and phase signatures, compare against successive state, and compute recognition gap.",
            "Generated_Figure": "FIG_ENABLEMENT_08A_Quantum_Fredholm_Recognition_Gap_Result.png",
            "Generated_Table": "TABLE_ENABLEMENT_08_Quantum_Fredholm_Recognition_Result.csv",
            "Technical_Effect": "Detects preservation or loss of quantum code-space recognition."
        },
        {
            "Embodiment": "Example 8B: Recognition--Null Fredholm Split",
            "Input": "Circular-hyperbolic finite-rank kernel with xi and eta parameters",
            "Recognition-Kernel Operation": "Compute Delta_R, Delta_N, and K_Fred = |Delta_N|/(|Delta_R|+eps).",
            "Generated_Figure": "FIG_ENABLEMENT_08A_Quantum_Fredholm_Recognition_Gap_Result.png",
            "Generated_Table": "RESULT_ENABLEMENT_08_Quantum_Fredholm_Recognition_Result.json",
            "Technical_Effect": "Separates recognized circular component from non-recognition curvature/memory residue."
        },
        {
            "Embodiment": "Example 8C: Quantum Error Technical Action",
            "Input": "Unified quantum recognition gap, syndrome gap, and Fredholm gap",
            "Recognition-Kernel Operation": "Classify state into accept, monitor, correction, or reject/reinitialize state.",
            "Generated_Figure": "FIG_ENABLEMENT_08B_Quantum_Error_Control_Action_Result.png",
            "Generated_Table": "TABLE_ENABLEMENT_08_Quantum_Fredholm_Recognition_Result.csv",
            "Technical_Effect": "Generates quantum-classical technical control action."
        },
        {
            "Embodiment": "Example 8D: Quantum Fredholm Pipeline",
            "Input": "Quantum/hybrid state and recognition operators",
            "Recognition-Kernel Operation": "Process state through recognition operator, syndrome gap, Fredholm split, threshold classifier, and action output.",
            "Generated_Figure": "FIG_PATENT_13_Quantum_Fredholm_Recognition_Kernel_Pipeline.png",
            "Generated_Table": "TABLE_ENABLEMENT_08_Quantum_Embodiment_Map.csv",
            "Technical_Effect": "Shows end-to-end quantum Recognition--Kernel architecture."
        },
    ])

    embodiment_map.to_csv(OUT / "TABLE_ENABLEMENT_08_Quantum_Embodiment_Map.csv", index=False)

    caption_text = """
Example 8: Quantum Recognition--Null Fredholm Error-Control Embodiment

In this illustrative embodiment, the Recognition--Kernel Machine receives a quantum state,
encoded quantum state, syndrome state, measurement-state representation, or
quantum-classical transcript indexed by a notational index n. A recognition operator
extracts one or more invariants including stabilizer-like signatures, phase relations,
code-space conditions, or measurement-consistency conditions. The engine computes a
quantum recognition gap and a Recognition--Null Fredholm determinant gap. The
Fredholm determinant is split into a recognized component Delta_R and a non-recognition
component Delta_N, and the ratio |Delta_N|/(|Delta_R|+eps) contributes to a unified
gap score. Based on the unified gap, the machine accepts the state, monitors bounded
residue, applies correction, rejects the state, reinitializes the state, or flags decoherence.

Generated embodiment figures:
1. FIG_ENABLEMENT_08A_Quantum_Fredholm_Recognition_Gap_Result.png
2. FIG_ENABLEMENT_08B_Quantum_Error_Control_Action_Result.png
3. FIG_PATENT_13_Quantum_Fredholm_Recognition_Kernel_Pipeline.png
"""
    with open(OUT / "CAPTION_ENABLEMENT_08_Quantum_Fredholm_Recognition_Kernel.txt", "w", encoding="utf-8") as f:
        f.write(caption_text)

    print("Saved:", OUT / "TABLE_ENABLEMENT_08_Quantum_Embodiment_Map.csv")
    print("Saved:", OUT / "CAPTION_ENABLEMENT_08_Quantum_Fredholm_Recognition_Kernel.txt")


def main() -> None:
    df = run_quantum_recognition_engine()
    print("\nQuantum Recognition--Null Fredholm Result:")
    print(df[[
        "case",
        "quantum_recognition_gap",
        "syndrome_gap",
        "fredholm_gap",
        "unified_gap",
        "decision",
    ]])

    make_gap_figure(df)
    make_action_figure(df)
    make_pipeline_figure()
    make_caption_and_map(df)

    print("\nGenerated files:")
    for name in [
        "TABLE_ENABLEMENT_08_Quantum_Fredholm_Recognition_Result.csv",
        "RESULT_ENABLEMENT_08_Quantum_Fredholm_Recognition_Result.json",
        "FIG_ENABLEMENT_08A_Quantum_Fredholm_Recognition_Gap_Result.png",
        "FIG_ENABLEMENT_08B_Quantum_Error_Control_Action_Result.png",
        "FIG_PATENT_13_Quantum_Fredholm_Recognition_Kernel_Pipeline.png",
        "TABLE_ENABLEMENT_08_Quantum_Embodiment_Map.csv",
        "CAPTION_ENABLEMENT_08_Quantum_Fredholm_Recognition_Kernel.txt",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
