"""H1 test runner for rnke_thermo_decoherence_hypothesis.md.

Inputs (both must exist; fail-closed otherwise):
  hardware_evidence/<job>_calibration_snapshot.json   (GPT task; schema below)
  generated/rnke_theorem_binding_hw_certificate.json  (from rnke_theorem_binding_hw.py)

Calibration schema (per job):
  {"job_id": "...", "backend": "...", "snapshot_time": "...",
   "qubits": {"<physical_index>": {"T1_us": float, "T2_us": float,
               "readout_error": float}},
   "ancilla_map": {"<stabilizer_index 0..7>": <physical_index>}}

Outputs: δ_q per ancilla, non-Markovian flags (T2 > 2 T1), renaming control
Γ_q ≡ 1, Spearman ρ(δ_q, confidence) with exact-permutation p (8 points),
verdict PASS_H1 / FAIL_H1 / ABSTAIN_NONMARKOVIAN / ABSTAIN_NO_DATA. Certificate.
Pure stdlib. Exact where possible (Fractions for ranks/rho).
"""
from __future__ import annotations

import glob
import hashlib
import itertools
import json
import math
import pathlib
import sys
from fractions import Fraction as Fr

HERE = pathlib.Path(__file__).resolve().parent
PROTOCOL = "rnke-thermo-decoherence-h1-test-v1"


def cj(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(o):
    return hashlib.sha256(cj(o).encode()).hexdigest()


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [Fr(0)] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = Fr(i + j + 2, 2)  # 1-based average rank
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def spearman(x, y):
    rx, ry = ranks(x), ranks(y)
    n = len(x)
    mx = sum(rx) / n; my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx); dy = sum((b - my) ** 2 for b in ry)
    if dx == 0 or dy == 0:
        return None
    return num / Fr(math.isqrt(int(dx * dy)) or 1)  # exact if perfect square; else approx via float below


def spearman_float(x, y):
    rx = [float(r) for r in ranks(x)]; ry = [float(r) for r in ranks(y)]
    n = len(x); mx = sum(rx) / n; my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def perm_p_one_sided(x, y, observed):
    """Exact permutation p for H1: rho < 0 expected (more δ_q → less confidence)."""
    n = len(x); cnt = 0; tot = 0
    for perm in itertools.permutations(range(n)):
        yy = [y[i] for i in perm]
        r = spearman_float(x, yy)
        tot += 1
        if r <= observed + 1e-12:
            cnt += 1
    return cnt / tot


def main(out=None):
    cal_files = sorted(glob.glob(str(HERE / "hardware_evidence" / "*_calibration_snapshot.json")))
    tb_file = HERE / "generated" / "rnke_theorem_binding_hw_certificate.json"
    body = {"protocol": PROTOCOL}
    if not cal_files or not tb_file.exists():
        body.update({"verdict": "ABSTAIN_NO_DATA",
                     "missing": {"calibration_snapshot": not bool(cal_files),
                                 "theorem_binding_certificate": not tb_file.exists()},
                     "note": "fail-closed: test not executed; no claim"})
        body["certificate_sha256"] = sha(body)
        print(json.dumps(body, indent=1)); return body
    cal = json.load(open(cal_files[0])); tb = json.load(open(tb_file))
    if cal["job_id"] != tb["job_id"]:
        body.update({"verdict": "ABSTAIN_JOB_MISMATCH", "cal_job": cal["job_id"], "tb_job": tb["job_id"]})
        body["certificate_sha256"] = sha(body); print(json.dumps(body, indent=1)); return body

    # confidence per stabilizer: average |<S_i>| over the four cases
    confs = [[Fr(c) for c in case["T3_orientation_confidence"]] for case in tb["cases"]]
    conf8 = [sum(cs[i] for cs in confs) / len(confs) for i in range(8)]

    rows = []; flags = []; delta = []; conf_used = []
    for s in range(8):
        q = str(cal["ancilla_map"][str(s)])
        t1, t2 = float(cal["qubits"][q]["T1_us"]), float(cal["qubits"][q]["T2_us"])
        nonmarkov = t2 > 2 * t1
        dq = math.log(2 * t1 / t2) if t2 > 0 else float("nan")
        gamma1 = 1 / t1; gamma2 = 1 / t2; gphi = gamma2 - gamma1 / 2
        renaming = (gamma1 / (gamma1 / 2 + gphi)) * (t1 / t2)  # ≡ 1 identically
        rows.append({"stabilizer": s, "physical_qubit": q, "T1_us": t1, "T2_us": t2,
                     "delta_q": dq, "confidence": str(conf8[s]),
                     "nonmarkovian_flag": nonmarkov, "renaming_control_gamma_q": renaming})
        flags.append(nonmarkov); delta.append(dq); conf_used.append(float(conf8[s]))

    renaming_ok = all(abs(r["renaming_control_gamma_q"] - 1) < 1e-9 for r in rows)
    if any(flags):
        verdict = "ABSTAIN_NONMARKOVIAN"; rho = p = None
    else:
        rho = spearman_float(delta, conf_used)
        p = perm_p_one_sided(delta, conf_used, rho)
        verdict = "PASS_H1" if (rho < 0 and p < 0.05) else "FAIL_H1"
    body.update({"job_id": cal["job_id"], "backend": cal["backend"],
                 "source_theorem_binding_sha256": tb["certificate_sha256"],
                 "rows": rows, "renaming_control_identity_holds": renaming_ok,
                 "spearman_rho": rho, "permutation_p_one_sided": p, "n": 8,
                 "verdict": verdict if renaming_ok else "ABSTAIN_RENAMING_CONTROL_FAILED",
                 "claim_boundary": "Predeclared H1 test on one backend epoch; 8 points; not a physics claim."})
    body["certificate_sha256"] = sha(body)
    if out:
        pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(out).write_text(cj(body) + "\n")
    print(json.dumps({k: body[k] for k in ("verdict", "spearman_rho", "permutation_p_one_sided", "renaming_control_identity_holds", "certificate_sha256")}, indent=1))
    return body


if __name__ == "__main__":
    main(out=sys.argv[1] if len(sys.argv) > 1 else str(HERE / "generated" / "rnke_thermo_h1_certificate.json"))
