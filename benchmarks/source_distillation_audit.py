"""Reproduce v0.34 source correction, purification and accepted-output faults."""
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
from phase_seam_foundation.source_distillation import (
    dilation_certificate, double_pair_channel, fused_double_pair_channel,
    loss_environment_vectors, optical_round, physical_plan,
    purification_schedule, source_sector,
)
from phase_seam_foundation.cluster_faults import fault_grade


def serial(value):
    if isinstance(value, (Exact, F)): return value.to_dict()
    if isinstance(value, Fraction): return dict(exact=str(value), decimal=float(value))
    if isinstance(value, dict): return {str(k): serial(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [serial(v) for v in value]
    return value


def write_json(path, data):
    path.write_text(json.dumps(serial(data), indent=2)+'\n', encoding='utf-8')


def source_hashes():
    paths = {'README.md', 'phase_seam_foundation/README.md'}
    paths.update('phase_seam_foundation/'+p for p in (
        'SOURCE_DISTILLATION.md', 'CLUSTER_FAULTS.md', 'ENCODED_BELL.md',
        'OPTICAL_REFRESH.md', 'CLUSTER_BUILD.md', 'CHAIN_MEMORY.md',
        'LEDGER_VIOLATIONS.md', 'SOURCE_SPEC_810.md'))
    paths.add('benchmarks/cluster_faults_audit.py')
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if filename:
            p = Path(filename).resolve()
            if p.is_relative_to(ROOT) and p.suffix == '.py':
                paths.add(p.relative_to(ROOT).as_posix())
    return {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(paths)}


class AuditResult(unittest.TextTestResult):
    def stopTest(self, test):
        super().stopTest(test)
        if self.testsRun % 10 == 0:
            print(json.dumps(dict(tests_completed=self.testsRun)), flush=True)


def main():
    start = time.perf_counter()
    names = ('source_distillation', 'cluster_faults', 'dual_rail', 'source_spec',
             'optical_refresh', 'encoded_bell', 'cluster_build')
    suite = unittest.TestSuite(unittest.defaultTestLoader.discover(str(ROOT/'tests'),
                              pattern=f'test_phase_seam_{name}.py') for name in names)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=AuditResult).run(suite)
    out = ROOT/'phase_seam_foundation/distillation'; out.mkdir(exist_ok=True)
    (out/'test_results.txt').write_text(stream.getvalue(), encoding='utf-8')
    if not result.wasSuccessful():
        print(stream.getvalue())
        write_json(out/'qualification.json', dict(status='TEST_FAILURE', tests_run=result.testsRun,
                   failures=len(result.failures), errors=len(result.errors)))
        return 1
    noisy = (Fraction(3,4),)+(Fraction(1,12),)*3
    rounds = [optical_round(noisy, input_survival=m, detector_efficiency=d, dark_per_mode=h)
              for m,d,h in ((1,1,0), ('99/100','99/100',0), ('9/10','9/10',0),
                            ('99/100','99/100','1/1000000'))]
    controls = [optical_round((1,0,0,0), **kwargs) for kwargs in (
        {}, dict(detector_efficiency='9/10'), dict(input_survival='9/10'),
        dict(input_survival=0, dark_per_mode='1/1000'),
        dict(detector_efficiency=0, dark_per_mode='1/100'), dict(detector_efficiency=0))]
    example_record = dict(source=dict(evidence_class='LAB_RECORDED', heralded_g2='1/500',
                                     herald_readout='number_resolving', herald_efficiency='9/10'),
                          nodes=dict(evidence_class='LAB_RECORDED', dark_count_bound='1/1000000',
                                     site_efficiency='243/4000', hom_visibility='99/100'))
    write_json(out/'netlist.json', physical_plan())
    report = dict(schema='native-source-distillation-audit-v1', author='Monty',
        status='EXACT_CONDITIONAL_SOURCE_AND_SINGLE_ROUND_OPTICAL_CHANNEL_NO_DEVICE',
        generated_at=datetime.now(timezone.utc).isoformat(),
        checkout_base_commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        reviewed_collaborator_commit='90bc68dd73aaf6126b87a315346f301f069641d9',
        corrected_collaborator_claims=['zero-coherence P1 partial trace', 'eta-independent first-order 4x',
                                       '13-node product as physical witness bound', 'general g2/2 source-mixture inference'],
        reused_interfaces=['optical_refresh.fusion_merge_certificate', 'dual_rail Fock permanent engine',
                           'encoded_bell.basis_bridge_certificate'],
        tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        test_suites=names, seconds=round(time.perf_counter()-start,3), source_sha256=source_hashes(),
        netlist_sha256=hashlib.sha256((out/'netlist.json').read_bytes()).hexdigest(),
        test_log_sha256=hashlib.sha256((out/'test_results.txt').read_bytes()).hexdigest(),
        loss_environment_vectors=loss_environment_vectors(), independent_dilation=dilation_certificate(),
        source_channels=[double_pair_channel(e) for e in ('243/4000','1/2','9/10',0,1)],
        fused_source_channel=fused_double_pair_channel('1/2'),
        declared_source_sectors=[source_sector('1/40',e) for e in ('243/4000','1/2','9/10')],
        ideal_schedules=[purification_schedule(noisy,b) for b in ('','Z','ZZ','ZX','ZXZ','ZXZX')],
        noisy_single_rounds=rounds, perfect_pair_and_dark_controls=controls,
        synthetic_record_grade=dict(input_is_lab_evidence=False, verdict=fault_grade(example_record)),
        boundaries=[
            'all numbers follow declared mathematical models; no fabricated or measured device',
            'selected one-survivor source sector is not nondestructively certified reusable supply',
            'purification starts with two independent supplied Bell-diagonal two-photon pairs',
            'one/double-pair mixture weight is not identified from g2 without its source-conditioning model',
            'one-round channel includes uniform independent loss, PNR inefficiency and Bernoulli dark counts',
            'herald-conditioned fidelity includes invalid payloads; valid-sector selection is not observed',
            'ideal multi-round costs require perfect storage, optics, detectors and recursive retry',
            'no noisy multi-round composition, higher source-pair numbers or 12-photon factory noise propagation',
            'legacy classifier product retained only as toy score; no physical witness qualification'])
    write_json(out/'qualification.json', report)
    print(json.dumps({k:report[k] for k in ('status','tests_run','failures','errors','skipped','seconds')}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
