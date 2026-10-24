"""Reproduce the local software evidence; no hardware service is imported.

Run from the repository root with Python 3.12:
    python -m native_relational_qc.verify --out native_relational_qc/verification.json
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
from pathlib import Path
import platform
import unittest

import numpy as np
import qiskit
from qiskit import QuantumCircuit

from .examples import bell, bernstein_vazirani, ghz, grover_11, order_memory
from .qiskit_adapter import compare_qiskit, to_qiskit


ROOT = Path(__file__).resolve().parents[1]
LEGACY_COMMIT = "2a9eaf3e54e56236f1a92caf0a799f2e953ec125"
LEGACY_BLOB = "d1248943ca5347e3f153c4a5c3fb3aaf7c7818e1"


def legacy_builder():
    """Load only the pinned pure circuit builder, not the hardware entry point."""
    path = ROOT / "run_ugd_seam_ledger_test.py"
    data = path.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if blob != LEGACY_BLOB:
        raise ValueError("legacy circuit source changed; inspect and explicitly re-pin before comparison")
    tree = ast.parse(data, filename=str(path))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                 and node.name == "build_circuit"]
    if len(functions) != 1 or functions[0].decorator_list:
        raise ValueError("unexpected legacy builder structure")
    # The inspected function only constructs circuits. No module-level imports,
    # environment reads, service construction, submission or main() are executed.
    namespace = {"QuantumCircuit": QuantumCircuit}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["build_circuit"]


def run_verification():
    if platform.python_version_tuple()[:2] != ("3", "12"):
        raise RuntimeError("this evidence protocol is pinned to Python 3.12")
    stream = io.StringIO()
    suite = unittest.TestLoader().discover(str(ROOT / "tests"), pattern="test_native*.py")
    tests = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    programs = {
        "bell_zz": bell(), "bell_xx": bell("XX"), "bell_yy": bell("YY"),
        "bell_zx": bell("ZX"), "ghz_5": ghz(5),
        "bv_1011": bernstein_vazirani("1011"), "grover_11": grover_11(),
        "rk_kr_memory": order_memory(), "erased_order_control": order_memory(True),
    }
    examples = {name: compare_qiskit(to_qiskit(circuit)) for name, circuit in programs.items()}
    builder = legacy_builder()
    legacy = []
    for topology in ("star", "delta"):
        for mode in ("ordinary", "seam", "commuting", "order_erased"):
            for epsilon in (0.0, 0.15, 0.30, 0.45):
                result = compare_qiskit(builder(topology, mode, epsilon))
                # Keep the bounded verification record compact; full vectors are reproducible.
                result.pop("native_probabilities")
                result.pop("reference_probabilities")
                legacy.append({"topology": topology, "mode": mode, "epsilon": epsilon, **result})
    passed = (tests.wasSuccessful() and not tests.skipped
              and all(result["passed"] for result in examples.values())
              and all(result["passed"] for result in legacy))
    source_files = sorted((ROOT / "native_relational_qc").glob("*.py"))
    source_files += sorted((ROOT / "tests").glob("test_native*.py"))
    source_files += [ROOT / "quantum_native_bridge_pro" / name
                     for name in ("__init__.py", "bridge.py", "expected_models.py")]
    source_files += [ROOT / "run_ugd_seam_ledger_test.py"]
    return {
        "schema": "native-relational-local-verification-v1",
        "evidence_class": "LOCAL_IDEAL_SOFTWARE_VERIFICATION",
        "passed": bool(passed), "python_version": platform.python_version(),
        "numpy_version": np.__version__, "qiskit_version": qiskit.__version__,
        "tests": {"run": tests.testsRun, "failures": len(tests.failures),
                  "errors": len(tests.errors), "skipped": len(tests.skipped),
                  "failure_details": [details for _, details in tests.failures + tests.errors]},
        "analytic_program_comparisons": examples,
        "legacy_source": {"repository": "Parveen117/quantum-classical-provisional",
                          "commit": LEGACY_COMMIT, "path": "run_ugd_seam_ledger_test.py",
                          "git_blob_sha1": LEGACY_BLOB, "function": "build_circuit"},
        "legacy_7_qubit_comparisons": legacy,
        "legacy_max_amplitude_error": max(r["max_amplitude_error_including_global_phase"] for r in legacy),
        "legacy_max_probability_tvd": max(r["probability_tvd"] for r in legacy),
        "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in source_files},
        "hardware_job_id": None, "hardware_submissions": 0,
        "claim": "Bounded local static ideal-circuit compatibility only; no hardware or speedup claim.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = run_verification()
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "passed", "python_version", "numpy_version", "qiskit_version", "tests",
        "legacy_max_amplitude_error", "legacy_max_probability_tvd", "hardware_submissions")}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
