"""Reproduce v0.30 optical instruments, factory, channel and resource budget.

No device calls. Optical coefficients are exact; parameter sweeps are declared
pure-loss models. Source hashes include every imported repository Python file.
"""
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_relational_qc.exact import Exact
from phase_seam_foundation.dual_rail import F
from phase_seam_foundation.loss_refresh import recovery_plan
from phase_seam_foundation.optical_refresh import (
    bell_analyser_certificate, decoder_plan, encoded_bell_factory_certificate,
    fusion_merge_certificate, optical_budget, optical_witness, physical_plan,
)


def scalar(value):
    if isinstance(value, (Exact, F)):
        return value.to_dict()
    if isinstance(value, Fraction):
        return dict(exact=str(value), decimal=float(value))
    if isinstance(value, dict):
        return {str(k): scalar(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [scalar(v) for v in value]
    return value


def write_json(path, value):
    path.write_text(json.dumps(scalar(value), indent=2)+'\n', encoding='utf-8')


def source_hashes():
    paths = {'README.md', 'phase_seam_foundation/README.md',
             'phase_seam_foundation/OPTICAL_REFRESH.md', 'phase_seam_foundation/LOSS_REFRESH.md',
             'phase_seam_foundation/TREE_CODE.md', 'phase_seam_foundation/TREE_BUILD.md'}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            p = Path(filename).resolve()
            if p.is_relative_to(ROOT) and p.suffix == '.py':
                paths.add(p.relative_to(ROOT).as_posix())
    return {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    start = time.perf_counter()
    names = ('loss_refresh', 'cluster_compile', 'optical_refresh')
    suite = unittest.TestSuite(unittest.defaultTestLoader.discover(
        str(ROOT/'tests'), pattern=f'test_phase_seam_{name}.py') for name in names)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    out = ROOT/'phase_seam_foundation/optical_refresh'
    out.mkdir(exist_ok=True)
    (out/'test_results.txt').write_text(stream.getvalue(), encoding='utf-8')
    if not result.wasSuccessful():
        print(stream.getvalue())
        write_json(out/'qualification.json', dict(status='TEST_FAILURE',
                   tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors)))
        return 1

    known = [optical_witness(lost_masks=(lost,)) for lost in range(64)
             if recovery_plan([2, 2], lost)['recoverable']]
    fixed_masks = [lost for lost in range(64) if not lost & decoder_plan()['required_mask']]
    fixed = [optical_witness(lost_masks=(lost,), known_erasures=False) for lost in fixed_masks]
    budgets = []
    for known_erasures in (False, True):
        for wait in (0, 1):
            budgets.append(optical_budget(memory='99/100', storage_rounds=10,
                decoder_efficiency='9/10', bell_efficiency='9/10', resource_ready=1,
                pre_bell_rounds=wait, post_bell_rounds=wait, known_erasures=known_erasures))
    factory = encoded_bell_factory_certificate()
    netlist = dict(schema='native-optical-refresh-netlists-v1',
                   status='IDEAL_COMPONENT_PLAN_NO_FABRICATED_DEVICE',
                   fixed_without_loss_map=physical_plan(),
                   conditional_known_loss_example=physical_plan(known_lost_mask=1),
                   offline_factory=factory, local_fusion_instrument=fusion_merge_certificate())
    write_json(out/'netlist.json', netlist)
    report = dict(schema='native-optical-refresh-audit-v1', author='Monty',
        status='IDEAL_OPTICAL_INSTRUMENT_AND_FACTORY_VERIFIED_NO_DEVICE',
        generated_at=datetime.now(timezone.utc).isoformat(),
        checkout_base_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        seconds=round(time.perf_counter()-start, 3), source_sha256=source_hashes(),
        netlist_sha256=hashlib.sha256((out/'netlist.json').read_bytes()).hexdigest(),
        test_log_sha256=hashlib.sha256((out/'test_results.txt').read_bytes()).hexdigest(),
        bell_instrument=bell_analyser_certificate(), factory=factory,
        correctable_known_masks=len(known), known_erasure_transfers=known,
        fixed_no_oracle_masks=fixed_masks, fixed_no_oracle_transfers=fixed,
        two_transfer_witness=optical_witness(lost_masks=(1, 16)),
        no_feedback_control=optical_witness(lost_masks=(1,), corrections=False),
        declared_pure_loss_budgets=budgets,
        boundaries=[
            'ideal passive optics with indistinguishable photons, correct supplied resources and resolved photon counts',
            'conditional Choi fidelity and herald probability are separate; decoder outcomes are averaged',
            'known-erasure selection requires an external loss map; the fixed policy accepts only four masks',
            'the dynamic Bell CNOT is a verification adapter; the physical plan uses two passive couplers',
            'factory certificate covers only the seven-photon [2,2] encoded Bell resource',
            '48 expected ideal Bell pairs includes source/factory failures under the full-restart zero-storage-loss policy',
            'factory star preparation latency and real source/switch/buffer losses are not priced',
            'budget supply is full-resource or no launch; partly populated/incorrect source false heralds excluded',
            'fresh payload losses may be unheralded; Bell clicks alone do not certify an intact fresh block',
            'no measured noise, temperature, fabricated chip or physical repeated-refresh demonstration'])
    write_json(out/'qualification.json', report)
    print(json.dumps({k: report[k] for k in ('status', 'tests_run', 'failures', 'errors', 'skipped',
                                           'correctable_known_masks', 'fixed_no_oracle_masks', 'seconds')}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
