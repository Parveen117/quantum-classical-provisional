"""Reproduce two noisy purification levels without inter-round sector filtering."""
from datetime import datetime,timezone
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
sys.path.insert(0,str(ROOT))
from native_relational_qc.exact import Exact
from phase_seam_foundation.dual_rail import F
from phase_seam_foundation.purification_cascade import (
    cascade,projection_bias,scan_schedules,physical_plan,
)


def serial(value):
    if isinstance(value,(Exact,F)): return value.to_dict()
    if isinstance(value,Fraction): return dict(exact=str(value),decimal=float(value))
    if isinstance(value,dict): return {str(k):serial(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [serial(v) for v in value]
    return value


def write_json(path,data):
    path.write_text(json.dumps(serial(data),indent=2)+'\n',encoding='utf-8')


def state_packet(state):
    return dict(basis='unnormalised_creation_monomials',
                trace_rule='sum diagonal coefficient times product of occupation factorials',
                coefficients=[[list(n),list(m),str(c)] for (n,m),c in sorted(state.items())])


def state_bytes(state):
    return (json.dumps(state_packet(state),separators=(',',':'))+'\n').encode('utf-8')


def summary(result):
    return dict({k:v for k,v in result.items() if k != 'final_state'},
                full_state_sha256=hashlib.sha256(state_bytes(result['final_state'])).hexdigest())


def source_hashes():
    paths = {'README.md','phase_seam_foundation/README.md'}
    paths.update('phase_seam_foundation/'+p for p in (
        'PURIFICATION_CASCADE.md','SOURCE_DISTILLATION.md','CLUSTER_FAULTS.md',
        'ENCODED_BELL.md','OPTICAL_REFRESH.md','CLUSTER_BUILD.md','SOURCE_SPEC_810.md'))
    for module in tuple(sys.modules.values()):
        filename = getattr(module,'__file__',None)
        if filename:
            p = Path(filename).resolve()
            if p.is_relative_to(ROOT) and p.suffix == '.py':
                paths.add(p.relative_to(ROOT).as_posix())
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(paths)}


class AuditResult(unittest.TextTestResult):
    def stopTest(self,test):
        super().stopTest(test)
        if self.testsRun % 10 == 0:
            print(json.dumps(dict(tests_completed=self.testsRun)),flush=True)


def main():
    start = time.perf_counter()
    names = ('purification_cascade','source_distillation','cluster_faults','dual_rail',
             'source_spec','optical_refresh','encoded_bell','cluster_build')
    suite = unittest.TestSuite(unittest.defaultTestLoader.discover(str(ROOT/'tests'),
              pattern=f'test_phase_seam_{name}.py') for name in names)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=AuditResult).run(suite)
    out = ROOT/'phase_seam_foundation/cascade';out.mkdir(exist_ok=True)
    (out/'test_results.txt').write_text(stream.getvalue(),encoding='utf-8')
    if not result.wasSuccessful():
        print(stream.getvalue())
        write_json(out/'qualification.json',dict(status='TEST_FAILURE',tests_run=result.testsRun,
                   failures=len(result.failures),errors=len(result.errors)))
        return 1
    weights = (Fraction(3,4),)+(Fraction(1,12),)*3
    operating = [summary(cascade(weights,'ZX',input_survival=e,detector_efficiency=e,dark_per_mode=h))
                 for e,h in ((1,0),('9/10',0),('99/100',0),('99/100','1/1000000'),
                              ('999/1000','1/1000000'),('9997/10000','1/1000000'),
                              ('9998/10000','1/1000000'),('9999/10000','1/1000000'))]
    waits = [summary(cascade(weights,'ZX',input_survival='999/1000',detector_efficiency='999/1000',
                            dark_per_mode='1/1000000',memory='99/100',left_wait_rounds=t,right_wait_rounds=0))
             for t in (0,1,4,10)]
    full = cascade(weights,'ZX',input_survival='9/10',detector_efficiency='4/5',dark_per_mode='1/50')
    (out/'payload_state.json').write_bytes(state_bytes(full['final_state']))
    write_json(out/'netlist.json',physical_plan())
    report = dict(schema='native-purification-cascade-audit-v1',author='Monty',
        status='EXACT_TWO_NOISY_LEVELS_FULL_PAYLOAD_NO_DEVICE',
        generated_at=datetime.now(timezone.utc).isoformat(),
        checkout_base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        last_reviewed_collaborator_commit='90bc68dd73aaf6126b87a315346f301f069641d9',
        branch_head_at_development_start='dbb840a23e6a44b5981b6cb118f77560edd04e1c',
        later_collaborator_commit_present_at_start=False,
        tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        test_suites=names,seconds=round(time.perf_counter()-start,3),source_sha256=source_hashes(),
        artifact_sha256={name:hashlib.sha256((out/name).read_bytes()).hexdigest()
                         for name in ('netlist.json','payload_state.json','test_results.txt')},
        supplied_bell_weights=weights,operating_points=operating,fixed_wait_points=waits,
        full_state_example=summary(full),
        ideal_schedule_scan=scan_schedules(weights),
        noisy_schedule_scan=scan_schedules(weights,input_survival='99/100',detector_efficiency='99/100',dark_per_mode='1/1000000'),
        extra_sector_flag_negative_control=projection_bias(weights,input_survival='9/10',detector_efficiency='9/10'),
        dark_only_control=summary(cascade(weights,'ZX',input_survival=0,dark_per_mode='1/100')),
        no_herald_control=summary(cascade(weights,'ZX',detector_efficiency=0)),
        boundaries=[
            'supplied independent Bell-diagonal raw pairs; no raw-source certification',
            'all photon sectors are carried between levels; no hidden valid-sector flag or truncation',
            'at most two noisy levels and four photons per output site; larger requests fail explicitly',
            'uniform independent pure loss, ideal mode overlap and calibrated phase/H actions are assumptions',
            'PNR thinning plus independent Bernoulli dark counts per detector mode',
            'fixed waits charged at each level; no random latency or time-per-source estimate',
            'recursive retry costs count every accepted herald, not certified good pairs',
            'seven declared schedules only; operating points are not global device thresholds',
            'no four-round noisy result, encoded-factory propagation or measured physical device'])
    write_json(out/'qualification.json',report)
    print(json.dumps({k:report[k] for k in ('status','tests_run','failures','errors','skipped','seconds')},indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
