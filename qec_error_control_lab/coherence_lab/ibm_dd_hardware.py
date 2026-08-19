"""Submit / collect the recognition-adaptive DD experiment on IBM hardware.

    python ibm_dd_hardware.py submit --qubits 0,1,2,3,4,5 [--backend ibm_marrakesh] [--shots 2000]
    python ibm_dd_hardware.py collect JOB_ID

submit: pulls current backend properties for the chosen physical qubits (T1/T2/
readout), builds the predeclared plan (adaptive_dd.plan), builds all circuits
with initial_layout pinned to the physical qubit, transpiles with
scheduling_method="alap" (delays preserved), runs SamplerV2, writes a
submission receipt + the plan + the calibration snapshot into coherence_lab/
hardware_evidence/. collect: fetches counts, writes <job>_dd_counts.json in the
schema adaptive_dd.analyse expects, runs analyse, writes certificate + pin.
Never stores credentials; uses the saved QiskitRuntimeService account.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).resolve().parent
EVID = HERE / "hardware_evidence"
sys.path.insert(0, str(HERE))
from adaptive_dd import plan, build_circuits, analyse, sha, cj, DELAYS_US  # noqa: E402

DEFAULT_BACKEND = "ibm_marrakesh"


def _service(instance):
    from qiskit_ibm_runtime import QiskitRuntimeService
    return QiskitRuntimeService(instance=instance) if instance != "auto" else QiskitRuntimeService()


def submit(args):
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    from qiskit_ibm_runtime import SamplerV2
    service = _service(args.instance)
    backend = service.backend(args.backend)
    props = backend.properties()
    qubits = [int(q) for q in args.qubits.split(",")]
    cal = {"schema": "rnke-q-dd-calibration-snapshot-v1", "backend": backend.name,
           "snapshot_time": str(getattr(props, "last_update_date", "")),
           "qubits": {str(q): {"T1_us": float(props.t1(q)) * 1e6, "T2_us": float(props.t2(q)) * 1e6,
                               "readout_error": float(props.readout_error(q))} for q in qubits}}
    p = plan(cal)
    pm = generate_preset_pass_manager(backend=backend, optimization_level=1,
                                      scheduling_method="alap", seed_transpiler=20260819)
    isa, meta = [], []
    for q in qubits:
        for m, qc in build_circuits(q, p["qubits"][str(q)]["arms"]):
            pm_q = generate_preset_pass_manager(backend=backend, optimization_level=1,
                                                scheduling_method="alap", seed_transpiler=20260819,
                                                initial_layout=[q])
            isa.append(pm_q.run(qc)); meta.append(m)
    sampler = SamplerV2(mode=backend)
    job = sampler.run(isa, shots=args.shots)
    receipt = {"job_id": job.job_id(), "backend": backend.name, "shots": args.shots,
               "submitted_at": datetime.now(timezone.utc).isoformat(), "n_circuits": len(isa),
               "qubits": qubits, "plan_sha256": p["plan_sha256"], "circuit_meta": meta}
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / f"{job.job_id()}_dd_submission.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (EVID / f"{job.job_id()}_dd_plan.json").write_text(json.dumps(p, indent=2) + "\n")
    cal["certificate_sha256"] = sha(cal)
    (EVID / f"{job.job_id()}_dd_calibration_snapshot.json").write_text(json.dumps(cal, indent=2) + "\n")
    print(f"JOB ID : {job.job_id()}\nSTATUS : {job.status()}\nCIRCUITS: {len(isa)}\nPLAN   : {p['plan_sha256']}")


def collect(args):
    service = _service(args.instance)
    job = service.job(args.job_id)
    receipt = json.loads((EVID / f"{args.job_id}_dd_submission.json").read_text())
    p = json.loads((EVID / f"{args.job_id}_dd_plan.json").read_text())
    res = job.result()
    counts: dict = {}
    for m, pub in zip(receipt["circuit_meta"], res):
        c = pub.data.c.get_counts() if hasattr(pub.data, "c") else list(pub.data.values())[0].get_counts()
        q = str(m["qubit"]); counts.setdefault(q, {}).setdefault(m["arm"], {})[str(m["tau_us"])] = {
            "0": int(c.get("0", 0)), "1": int(c.get("1", 0))}
    (EVID / f"{args.job_id}_dd_counts.json").write_text(json.dumps(counts, indent=1, sort_keys=True) + "\n")
    cert = analyse(p, counts)
    cert.update({"job_id": args.job_id, "backend": receipt["backend"], "shots": receipt["shots"],
                 "evidence_class": "hardware_observation"})
    cert["certificate_sha256"] = sha(cert)
    out = EVID / f"{args.job_id}_dd_certificate.json"
    out.write_text(cj(cert) + "\n")
    (HERE / "EXPECTED_DD_HW.sha256").write_text(cert["certificate_sha256"] + "\n")
    print(json.dumps(cert["checks"], indent=1))
    for q, r in cert["per_qubit"].items():
        print(q, {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k != "fits"})
    print("SHA256 :", cert["certificate_sha256"], "\nSAVED  :", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit"); s.add_argument("--qubits", required=True); s.add_argument("--backend", default=DEFAULT_BACKEND)
    s.add_argument("--shots", type=int, default=2000); s.add_argument("--instance", default="auto")
    c = sub.add_parser("collect"); c.add_argument("job_id"); c.add_argument("--instance", default="auto")
    a = ap.parse_args(); (submit if a.cmd == "submit" else collect)(a)
