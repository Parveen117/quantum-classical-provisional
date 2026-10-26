"""Reproduce v0.32 encoded Bell instruments, channels, counts and resource cost."""
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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from native_relational_qc.exact import Exact
from phase_seam_foundation.dual_rail import F
from phase_seam_foundation.encoded_bell import (
    basis_bridge_certificate, budget, coarse_instrument_certificate, decode_counts,
    loss_coefficients, mask_success, measurement_handoff, physical_plan, resource_factory_certificate,
    resource_stabiliser_witness, success_probability, transfer_witness,
)
from phase_seam_foundation.optical_refresh import optical_budget


def scalar(v):
    if isinstance(v,(Exact,F)): return v.to_dict()
    if isinstance(v,Fraction): return dict(exact=str(v),decimal=float(v))
    if isinstance(v,dict): return {str(k):scalar(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [scalar(x) for x in v]
    return v


def write_json(path,value):
    path.write_text(json.dumps(scalar(value),indent=2)+'\n',encoding='utf-8')


def source_hashes():
    paths={'README.md','phase_seam_foundation/README.md'}
    paths.update('phase_seam_foundation/'+p for p in
                 ('ENCODED_BELL.md','OPTICAL_REFRESH.md','CLUSTER_COMPILE.md','CLUSTER_BUILD.md','LOSS_REFRESH.md','TREE_CODE.md'))
    for module in tuple(sys.modules.values()):
        filename=getattr(module,'__file__',None)
        if filename:
            p=Path(filename).resolve()
            if p.is_relative_to(ROOT) and p.suffix=='.py': paths.add(p.relative_to(ROOT).as_posix())
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(paths)}


class AuditResult(unittest.TextTestResult):
    def stopTest(self,test):
        super().stopTest(test)
        if self.testsRun % 10 == 0:
            print(json.dumps(dict(tests_completed=self.testsRun)),flush=True)


def main():
    start=time.perf_counter()
    names=('loss_refresh','cluster_compile','cluster_build','optical_refresh','encoded_bell')
    suite=unittest.TestSuite(unittest.defaultTestLoader.discover(str(ROOT/'tests'),
              pattern=f'test_phase_seam_{name}.py') for name in names)
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=AuditResult).run(suite)
    out=ROOT/'phase_seam_foundation/encoded_bell'; out.mkdir(exist_ok=True)
    (out/'test_results.txt').write_text(stream.getvalue(),encoding='utf-8')
    if not result.wasSuccessful():
        print(stream.getvalue())
        write_json(out/'qualification.json',dict(status='TEST_FAILURE',tests_run=result.testsRun,
                   failures=len(result.failures),errors=len(result.errors)))
        return 1
    masks=[mask_success((2,2),m) for m in range(64)]
    witnesses=[transfer_witness(pair_lost_mask=r['pair_lost_mask']) for r in masks if r['success_probability']]
    larger=[transfer_witness(br) for br in ((3,2),(4,3),(8,1))]
    comparisons=[]
    for m,t,d,wait in ((Fraction(1),0,Fraction(1),0),(Fraction(1),0,Fraction(9,10),0),
                       (Fraction(99,100),10,Fraction(9,10),0),(Fraction(99,100),10,Fraction(9,10),1)):
        new=budget(memory=m,storage_rounds=t,detector_efficiency=d,resource_ready=1,
                   pre_bell_rounds=wait,post_bell_rounds=wait)
        old=optical_budget(memory=m,storage_rounds=t,decoder_efficiency=d,bell_efficiency=d,
                          resource_ready=1,pre_bell_rounds=wait,post_bell_rounds=wait)
        comparisons.append(dict(encoded=new,previous_fixed_decoder=old))
    scan=[]
    for eta in (Fraction(1),Fraction(99,100),Fraction(9,10),Fraction(81,100),Fraction(1,2)):
        rows=[dict(branching=[b,c],photons=b*(c+1),success=success_probability((b,c),eta))
              for b in range(1,9) for c in range(1,16) if b*(c+1)<=16]
        best=max(rows,key=lambda r:(r['success'],-r['photons']))
        scan.append(dict(complete_pair_survival=eta,rows=rows,best_by_probability_only=best,
                         source_cost_and_availability_optimised=False))
    factory=resource_factory_certificate()
    records=coarse_instrument_certificate()['records']
    def counts(zz,xx=0):
        return next(r['counts'] for r in records if r['possible'] and r['zz']==zz and (not zz or r['xx']==xx))
    raw_counts=[counts(0),counts(1,1),counts(0),counts(0),counts(1),counts(1)]
    decoded=decode_counts((2,2),raw_counts)
    handoff=dict(detector_counts=raw_counts,decoded_frame=decoded,
                 terminal_readout=measurement_handoff((2,2),decoded,(5,17,22,9,50,14)))
    plan=dict(six_photon_code=physical_plan(),sixteen_photon_code_assumed_source=physical_plan((8,1)),
              six_plus_six_resource_factory=factory,collaborator_readout_handoff_example=handoff)
    write_json(out/'netlist.json',plan)
    report=dict(schema='native-encoded-bell-audit-v1',author='Monty',
        status='IDEAL_ENCODED_OPTICAL_CHANNEL_VERIFIED_NO_DEVICE',
        generated_at=datetime.now(timezone.utc).isoformat(),
        checkout_base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        reviewed_collaborator_commit='78a7599f9364503188efba81bccedf7f99d046fa',
        reused_collaborator_interfaces=['cluster_compile.heater_setting','cluster_build.adaptation_lemma'],
        tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        seconds=round(time.perf_counter()-start,3),source_sha256=source_hashes(),
        netlist_sha256=hashlib.sha256((out/'netlist.json').read_bytes()).hexdigest(),
        test_log_sha256=hashlib.sha256((out/'test_results.txt').read_bytes()).hexdigest(),
        basis_bridge=basis_bridge_certificate(),coarse_instrument=coarse_instrument_certificate(),
        collaborator_readout_handoff=handoff,
        six_photon_mask_probabilities=masks,six_photon_coherent_witnesses=witnesses,
        larger_shape_witnesses=larger,no_feedback_control=transfer_witness(corrections=False),
        weighted_mask_coefficients=[loss_coefficients(br) for br in ((1,1),(2,2),(3,2),(4,3),(8,1))],
        encoded_resource_factory=factory,encoded_resource_stabilisers=resource_stabiliser_witness(),
        resource_missing_feedback_control=resource_stabiliser_witness(corrections=False),
        declared_budget_comparisons=comparisons,declared_shape_scan=scan,
        boundaries=[
            'one logical qubit per encoded block; physical photon counts are not independent logical qubit counts',
            'all accepted first-odd-group events included; unresolved even phase bits are never used',
            'loss flags arise from photon counts; no nondestructive erasure oracle; Bell measurement bases are static',
            'terminal angle-adaptation handoff assumes no intervening gates; no encoded classifier is compiled',
            'uniform independent loss, ideal indistinguishable interference, resolved counts, no dark or multipair counts',
            'larger transfer witnesses assume supplied encoded Bell resources; explicit source factory only for [2,2]',
            '192 expected ideal Bell pairs uses prepare-both-first restart and zero factory storage/switch loss',
            'supply is full correct resource or no launch; partial-source false heralds are not absorbed into readiness',
            'fresh-payload loss may be unheralded; physical fidelity, throughput and temperature are unmeasured',
            'classifier heater and frame-adaptation interfaces are reused; a complete encoded classifier and general fault tolerance remain open'])
    write_json(out/'qualification.json',report)
    print(json.dumps({k:report[k] for k in ('status','tests_run','failures','errors','skipped','seconds')},indent=2))
    return 0


if __name__=='__main__':
    sys.exit(main())
