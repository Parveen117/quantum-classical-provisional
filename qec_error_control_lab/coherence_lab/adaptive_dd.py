"""coherence_lab — recognition-adaptive dynamical decoupling (DD) experiment.

Goal (predeclared): measure effective transverse coherence under DD on IBM
hardware and test whether an RNKE-selected per-qubit schedule beats the best
fixed schedule. Certificate conforms to RNKE_Q_CERTIFICATE_SPEC v0.1.

Arms (per qubit, per delay τ in a sweep):
  ramsey      : H – idle(τ) – H            (T2*, control)
  hahn        : H – τ/2 – X – τ/2 – H      (T2 echo, control)
  cpmg_n      : H – [τ/2n – X – τ/2n]×n – H (fixed)
  xy4_n       : H – [XYXY with equal gaps]×n – H (fixed)
  adaptive    : sequence+n chosen per qubit by select_schedule() from the
                calibration snapshot (T1, T2, readout error) and, if present,
                syndrome confidence from rnke_theorem_binding_hw.
  random_ctrl : sequence+n drawn uniformly (renaming control, seeded)

Metric: survival P(|0>) vs τ, fit A·exp(−(τ/T)^β)+0.5 with bootstrap CI;
report T_eff per arm; headline = T_adaptive / max(T_fixed) with CI, plus
T_cpmg_best / T_hahn (the DD extension itself, a standard effect).

Claim boundary: effective coherence under DD on the measured qubits/epoch;
not bare device T2, not FT, not a vendor benchmark. DD is a standard technique;
the object under test is the SELECTION + certification.

Offline: circuit construction + self-test + analysis on synthetic counts run
with no credentials. Hardware submission is a separate step (GPT) that writes
counts JSON into coherence_lab/hardware_evidence/.
"""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import random
from dataclasses import dataclass, asdict

HERE = pathlib.Path(__file__).resolve().parent
PROTOCOL = "rnke-q-adaptive-dd-v1"
DELAYS_US = [0, 10, 20, 40, 80, 120, 160, 240, 320]
N_PULSES = {"cpmg": [2, 4, 8, 16], "xy4": [1, 2, 4]}      # xy4 unit = 4 pulses
SEQS = ("hahn", "cpmg", "xy4")


def cj(o): return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
def sha(o): return hashlib.sha256(cj(o).encode()).hexdigest()


# ----------------------------------------------------------------- selector
@dataclass(frozen=True)
class Schedule:
    seq: str
    n: int
    reason: str


def select_schedule(t1_us: float, t2_us: float, readout_err: float,
                    confidence: float | None = None) -> Schedule:
    """RNKE selection rule (predeclared; no tuning after data):
    δ_q = log(2T1/T2) ≥ 0 measures pure-dephasing share ('stiffness residue').
    - δ_q small (T2 ≈ 2T1, relaxation-limited): DD cannot help → hahn (n=1).
    - δ_q moderate: cpmg, n grows with δ_q (more dephasing → more refocusing).
    - δ_q large or low confidence: xy4 (robust to pulse errors), n by δ_q.
    Non-Markovian flag (T2 > 2T1): DEFERRED → fall back to hahn, flagged."""
    if t2_us > 2 * t1_us:
        return Schedule("hahn", 1, "DEFERRED_nonmarkovian_flag")
    dq = math.log(2 * t1_us / t2_us) if t2_us > 0 else 3.0
    low_conf = confidence is not None and confidence < 0.5
    if dq < 0.15:
        return Schedule("hahn", 1, f"dq={dq:.3f}<0.15 relaxation-limited")
    if dq < 0.7 and not low_conf and readout_err < 0.05:
        n = 4 if dq < 0.4 else 8
        return Schedule("cpmg", n, f"dq={dq:.3f} moderate")
    n = 2 if dq < 1.0 else 4
    return Schedule("xy4", n, f"dq={dq:.3f} large or low_conf={low_conf}")


# ----------------------------------------------------------------- circuits
def build_circuits(qubit: int, arms: list[tuple[str, str, int]], delays_us=DELAYS_US):
    """arms: list of (arm_label, seq, n). Returns list of (meta, QuantumCircuit).
    Uses qiskit; delays in dt via Delay(unit='us')."""
    from qiskit import QuantumCircuit
    out = []
    for label, seq, n in arms:
        for tau in delays_us:
            qc = QuantumCircuit(1, 1, name=f"{label}_q{qubit}_t{tau}")
            qc.h(0)
            if seq == "ramsey":
                if tau > 0: qc.delay(tau, 0, unit="us")
            elif seq == "hahn":
                gap = tau / 2
                if gap > 0: qc.delay(gap, 0, unit="us")
                qc.x(0)
                if gap > 0: qc.delay(gap, 0, unit="us")
            elif seq == "cpmg":
                gap = tau / (2 * n)
                for _ in range(n):
                    if gap > 0: qc.delay(gap, 0, unit="us")
                    qc.x(0)
                    if gap > 0: qc.delay(gap, 0, unit="us")
            elif seq == "xy4":
                gap = tau / (4 * n * 2)
                for _ in range(n):
                    for g in ("x", "y", "x", "y"):
                        if gap > 0: qc.delay(gap, 0, unit="us")
                        getattr(qc, g)(0)
                        if gap > 0: qc.delay(gap, 0, unit="us")
            else:
                raise ValueError(seq)
            qc.h(0)
            qc.measure(0, 0)
            out.append(({"arm": label, "seq": seq, "n": n, "tau_us": tau, "qubit": qubit}, qc))
    return out


def plan(calibration: dict, confidence: dict | None = None, seed: int = 20260819) -> dict:
    """Predeclared experiment plan from a calibration snapshot. Deterministic."""
    rng = random.Random(seed)
    qubits = calibration["qubits"]
    plan_ = {"protocol": PROTOCOL, "delays_us": DELAYS_US, "qubits": {}}
    for q, props in qubits.items():
        conf = None if not confidence else confidence.get(q)
        ad = select_schedule(props["T1_us"], props["T2_us"], props["readout_error"], conf)
        rseq = rng.choice(SEQS); rn = 1 if rseq == "hahn" else rng.choice(N_PULSES[rseq])
        arms = [("ramsey", "ramsey", 0), ("hahn", "hahn", 1)]
        arms += [(f"cpmg_{n}", "cpmg", n) for n in N_PULSES["cpmg"]]
        arms += [(f"xy4_{n}", "xy4", n) for n in N_PULSES["xy4"]]
        arms += [("adaptive", ad.seq, ad.n), ("random_ctrl", rseq, rn)]
        plan_["qubits"][q] = {"adaptive": asdict(ad), "random_ctrl": {"seq": rseq, "n": rn}, "arms": arms}
    plan_["plan_sha256"] = sha(plan_)
    return plan_


# ----------------------------------------------------------------- analysis
def fit_decay(taus, p0s, bootstrap=200, seed=1):
    """Fit p0 = 0.5 + A·exp(−(τ/T)^β) by grid search on (T, β), A fixed by LS.
    Returns T, β, A, bootstrap CI for T. Deterministic, no scipy."""
    def loss(T, b):
        f = [math.exp(-(t / T) ** b) if T > 0 else 0.0 for t in taus]
        A = sum((p - 0.5) * x for p, x in zip(p0s, f)) / max(sum(x * x for x in f), 1e-12)
        return sum((p - 0.5 - A * x) ** 2 for p, x in zip(p0s, f)), A
    Ts = [5 * 1.15 ** k for k in range(60)]            # 5 µs .. ~22 ms
    Bs = [0.8, 1.0, 1.2, 1.5, 2.0]
    best = min(((loss(T, b)[0], T, b) for T in Ts for b in Bs))
    _, T, b = best; A = loss(T, b)[1]
    rng = random.Random(seed); Tb = []
    n = len(taus)
    for _ in range(bootstrap):
        idx = [rng.randrange(n) for _ in range(n)]
        tt = [taus[i] for i in idx]; pp = [p0s[i] for i in idx]
        def l2(T_, b_):
            f = [math.exp(-(t / T_) ** b_) for t in tt]
            A_ = sum((p - 0.5) * x for p, x in zip(pp, f)) / max(sum(x * x for x in f), 1e-12)
            return sum((p - 0.5 - A_ * x) ** 2 for p, x in zip(pp, f))
        Tb.append(min(((l2(T_, b_), T_) for T_ in Ts for b_ in Bs))[1])
    Tb.sort()
    return {"T_us": T, "beta": b, "A": A, "T_ci95": [Tb[int(0.025 * bootstrap)], Tb[int(0.975 * bootstrap) - 1]]}


def analyse(plan_: dict, counts: dict) -> dict:
    """counts: {qubit: {arm: {tau_us(str): {"0": n0, "1": n1}}}} → certificate body."""
    res = {}; checks = {}
    for q, qp in plan_["qubits"].items():
        arm_fits = {}
        for label, seq, n in qp["arms"]:
            c = counts.get(q, {}).get(label)
            if not c: continue
            taus = sorted(int(t) for t in c); p0 = []
            for t in taus:
                d = c[str(t)]; tot = d.get("0", 0) + d.get("1", 0)
                p0.append(d.get("0", 0) / tot if tot else 0.5)
            arm_fits[label] = fit_decay(taus, p0) | {"seq": seq, "n": n}
        if not arm_fits: continue
        fixed = {k: v for k, v in arm_fits.items() if k not in ("adaptive", "random_ctrl", "ramsey")}
        best_fixed = max(fixed.items(), key=lambda kv: kv[1]["T_us"]) if fixed else None
        out = {"fits": arm_fits}
        if best_fixed and "hahn" in arm_fits:
            out["dd_extension_best_fixed_over_hahn"] = best_fixed[1]["T_us"] / arm_fits["hahn"]["T_us"]
            out["best_fixed_arm"] = best_fixed[0]
        if "adaptive" in arm_fits and best_fixed:
            out["adaptive_over_best_fixed"] = arm_fits["adaptive"]["T_us"] / best_fixed[1]["T_us"]
            lo_a = arm_fits["adaptive"]["T_ci95"][0]; hi_f = best_fixed[1]["T_ci95"][1]
            out["adaptive_beats_best_fixed_ci_separated"] = lo_a > hi_f
        if "random_ctrl" in arm_fits and "adaptive" in arm_fits:
            out["adaptive_over_random_ctrl"] = arm_fits["adaptive"]["T_us"] / arm_fits["random_ctrl"]["T_us"]
        res[q] = out
    wins = [r.get("adaptive_beats_best_fixed_ci_separated", False) for r in res.values()]
    checks["n_qubits"] = len(res)
    checks["adaptive_ci_wins"] = sum(wins)
    checks["headline"] = ("ADAPTIVE_SELECTION_EFFECT" if wins and sum(wins) >= max(1, math.ceil(0.6 * len(wins)))
                          else "NO_ADAPTIVE_EFFECT_DD_EXTENSION_ONLY")
    return {"protocol": PROTOCOL, "plan_sha256": plan_["plan_sha256"], "per_qubit": res, "checks": checks,
            "claim_boundary": ("Effective coherence under DD on measured qubits/epoch. DD extension over Hahn is a "
                               "standard effect (renaming-class); only adaptive-vs-best-fixed with CI separation "
                               "is a selection finding. Not bare T2, not FT, not vendor benchmark.")}


# ----------------------------------------------------------------- self-test
def _synthetic_counts(plan_: dict, shots=2000, seed=3) -> dict:
    """Synthetic hardware: T_eff depends on seq/n; adaptive given true-best on half the qubits."""
    rng = random.Random(seed); counts = {}
    for q, qp in plan_["qubits"].items():
        base = 60 + 10 * int(q) % 50
        def T_of(seq, n):
            return {"ramsey": base * 0.4, "hahn": base, "cpmg": base * (1 + 0.35 * math.log2(max(n, 1))),
                    "xy4": base * (1 + 0.4 * math.log2(max(4 * n, 1)))}[seq]
        counts[q] = {}
        for label, seq, n in qp["arms"]:
            T = T_of(seq, n); counts[q][label] = {}
            for t in plan_["delays_us"]:
                p0 = 0.5 + 0.5 * math.exp(-(t / T) ** 1.2)
                n0 = sum(1 for _ in range(shots) if rng.random() < p0)
                counts[q][label][str(t)] = {"0": n0, "1": shots - n0}
    return counts


def self_test() -> dict:
    cal = {"qubits": {str(i): {"T1_us": 150 + 10 * i, "T2_us": [30, 80, 120, 250, 290][i % 5],
                              "readout_error": 0.02} for i in range(6)}}
    p = plan(cal)
    # circuits build for one qubit (qiskit present)
    try:
        circs = build_circuits(0, p["qubits"]["0"]["arms"][:3])
        assert len(circs) == 3 * len(DELAYS_US)
        qiskit_ok = True
    except ImportError:
        qiskit_ok = False
    cert = analyse(p, _synthetic_counts(p))
    cert["self_test"] = {"qiskit_circuits_built": qiskit_ok, "selector_examples":
                         {q: p["qubits"][q]["adaptive"] for q in p["qubits"]}}
    cert["certificate_sha256"] = sha(cert)
    return cert


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        c = self_test()
        print(json.dumps({"checks": c["checks"], "self_test": c["self_test"],
                          "sha": c["certificate_sha256"]}, indent=1))
    else:
        print("usage: --self-test | (hardware path: see README)")
