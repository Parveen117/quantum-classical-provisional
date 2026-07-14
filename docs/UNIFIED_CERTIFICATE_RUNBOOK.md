# Unified Quantum Certificate Runbook

This runbook converts the existing local `trial-*` evidence files into one reviewer-facing certificate without rewriting or manually summarizing the underlying evidence.

## Inputs currently recognized

- `trial-bell-evaluation.json`
- `trial-bell-stability-report.json`
- `trial-calibration-report.json`
- `trial-backend-comparison-report.json`
- `trial-expected-integrated-ledger.jsonl`
- `trial-integrated-quantum-evidence-bundle.json`
- `trial-quantum-certificate.json`
- `trial-quantum-evidence-bundle.json`
- `trial-quantum-ledger.jsonl`

Missing files are reported as optional unless `--require-all-defaults` is used.

## Command-line run

From the repository root:

```bash
python tools/build_unified_quantum_certificate.py --root .
```

Expected output:

```text
generated_certificates/unified_quantum_certificate.json
```

Strict completeness mode:

```bash
python tools/build_unified_quantum_certificate.py --root . --require-all-defaults
```

## Jupyter run on Windows

```python
from pathlib import Path
import subprocess
import sys

repo = Path(
    r"C:\Users\abc\Desktop\New Folder (2)\New folder"
    r"\PROVISNAL RELATED\Quantum classical"
)

pull = subprocess.run(
    ["git", "pull", "--rebase", "origin", "master"],
    cwd=repo,
    text=True,
    capture_output=True,
)
print(pull.stdout)
print(pull.stderr)

run = subprocess.run(
    [
        sys.executable,
        str(repo / "tools" / "build_unified_quantum_certificate.py"),
        "--root",
        str(repo),
    ],
    cwd=repo,
    text=True,
    capture_output=True,
)
print("return code:", run.returncode)
print(run.stdout)
print(run.stderr)
```

## Test command

```bash
python -m unittest tests.test_unified_quantum_certificate -v
```

## Scientific interpretation

The resulting certificate aggregates existing computational evidence and records a SHA-256 hash for every source. It does not silently convert missing residue sectors into zero and does not claim that computational aggregation proves a universal law. Its purpose is provenance, consistency, and reviewer inspectability.
