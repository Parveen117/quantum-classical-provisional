# Repository maintenance

`master` is the canonical branch for the public calculator, observer tools,
QEC evidence and photonic research packages. Use short-lived topic branches,
review their changed scope, and integrate them into `master` after the relevant
checks pass. A draft label alone does not mean its work is still missing:
check ancestry and the actual diff before reopening or duplicating a stage.

## Pull requests and checks

The [calculator CI](../.github/workflows/quantum-native-bridge-pro.yml) checks
three environments: Python 3.11 with the core test dependencies, Python 3.12
with the core test dependencies, and Python 3.12 with Qiskit and benchmark
extras. The core jobs explicitly verify that Qiskit is absent. All three jobs
must pass for the revision being integrated; an old failed run is superseded
only by a passing run for the relevant revised code.

CI builds the wheel, exercises the installed command, runs the existing test
suite and checks the evidence-bridge ledger. It uses a read-only repository
token. The observer tracking and joint contrast/phase commands are included in
the installed-command smoke checks.

For local development, use a separate virtual environment and the dependency
set appropriate to the change:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
```

Use `'.[test,qiskit,benchmark]'` to include the optional reference backends.
Missing optional dependencies must be reported as skipped checks. Repository
maintenance does not require an IBM account or submitting hardware jobs.
Preserve archived scientific results and expected hashes; new runs belong in
new outputs, not over the retained evidence.

## Branch cleanup and recovery

The [November branch inventory](BRANCH_ARCHIVE_2026_11_01.json) records all 13
non-default branch tips before cleanup. Before deleting a reference, verify:

```bash
git fetch origin
git merge-base --is-ancestor <recorded-tip-sha> origin/master
```

A zero exit status establishes that its commits remain reachable from the
canonical branch. Resolve any unique work before removing its reference.
Keep release tags and evidence archives. If a historical name is needed again:

```bash
git branch <recorded-branch-name> <recorded-tip-sha>
git push origin <recorded-branch-name>
```

Ancestry, matching source bytes and a passing computation are separate checks.
Merging an evidence packet retains its existing scientific scope; it does not
upgrade a simulator result into measured device performance.
