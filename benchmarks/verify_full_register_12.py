"""Replay retained N=141 qualification evidence without rerunning the simulator."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from native_relational_qc.calculator import _digest,validate
from native_relational_qc.cyclotomic_pow2 import field_of_order
from native_relational_qc.shor import assess,build


def digest_file(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    data=path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix=='.gz' else data)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--result',type=Path,required=True)
    p.add_argument('--trials',type=Path,nargs='+',required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if len(a.trials)<2:raise ValueError('qualification requires at least two retained trials')
    document=read_json(a.input);_,canonical=validate(document)
    result=read_json(a.result)
    program=build(141,2,precision=12,oracle='arithmetic',rewrite='panini',field='flat')
    expected=program.request('cyclotomic_pow2')
    expected['limits']={'max_work':1_000_000_000,'max_branches':1_048_576}
    assert canonical==validate(expected)[1], 'different workload or resource limits'
    assert result['status']=='completed'
    assert result['request_sha256']==_digest(canonical)
    exact={label:value['exact'] for label,value in result['answers'][0]['probabilities'].items()}
    exact_sha=hashlib.sha256(json.dumps(exact,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert len(exact)==4096
    answers_sha=hashlib.sha256(json.dumps(result['answers'],sort_keys=True).encode()).hexdigest()
    trials=[];full_result_matches_trial=False
    for path in a.trials:
        trial=read_json(path)
        assert trial['status']=='completed'
        assert trial['timeout_seconds']==300 and trial['wall_seconds']<300
        assert trial['request_sha256']==result['request_sha256']
        assert trial['exact_distribution_sha256']==exact_sha
        assert trial['distribution_bins']==4096
        assert trial['assessment']['status']=='verified'
        assert trial['assessment']['exact_fourier_law_agrees']
        assert trial['statistics']==result['statistics']
        full_result_matches_trial|=trial['answers_sha256']==answers_sha
        for name,expected_sha in trial['source_sha256'].items():
            assert digest_file(ROOT/name)==expected_sha, f'changed qualification source: {name}'
        trials.append(dict(file=path.name,sha256=digest_file(path),wall_seconds=trial['wall_seconds']))
    assert full_result_matches_trial, 'retained answers differ from every timed trial'
    assessment=assess(program,result)
    assert assessment['status']=='verified' and assessment['exact_fourier_law_agrees']
    controls={}
    for name in ('changed_probability','missing_bin'):
        corrupted=copy.deepcopy(result)
        probabilities=corrupted['answers'][0]['probabilities']
        label=sorted(probabilities)[0]
        if name=='changed_probability':
            field=field_of_order(4096)
            probabilities[label]['exact']=(field.from_dict(probabilities[label]['exact'])+1).to_dict()
        else:del probabilities[label]
        try:assess(program,corrupted)
        except (AssertionError,ValueError) as error:controls[name]=dict(rejected=True,reason=str(error))
        else:raise AssertionError(f'negative control was accepted: {name}')
    summary=dict(schema='nrqc-full-register-runtime-qualification-v1',status='qualified',
        author='Monty',evidence_class='LOCAL_IDEAL_CALCULATION',hardware_job_id=None,
        scope='N=141, base 2, 12 phase bits, full-register arithmetic oracle with Panini rewrite',
        input=dict(file=a.input.name,sha256=digest_file(a.input),request_sha256=_digest(canonical)),
        result=dict(file=a.result.name,sha256=digest_file(a.result)),trials=trials,
        exact_distribution_sha256=exact_sha,exact_bins_checked=4096,
        exact_fourier_law_agrees=True,negative_controls=controls,statistics=result['statistics'],
        verifier_sha256=digest_file(Path(__file__)),
        qualification_boundary='Two local trials under 300 seconds; no hardware-independent runtime guarantee')
    a.out.write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))


if __name__=='__main__':main()
