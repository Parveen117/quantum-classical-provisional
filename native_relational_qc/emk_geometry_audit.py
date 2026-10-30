"""Replay the pinned native-source certificates and test the quantum adapter boundary.

python -m native_relational_qc.emk_geometry_audit --ugd-source PATH --emk-source PATH
The original source files are read and hash-checked, never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

PINS = {'ugd':'c833e6d1f85772dea171906ac11135976ac06b09',
        'emk':'eaf3c3f65476f37165c75031fcd6cfb2cb66f710'}
SOURCE_COMMIT = '35d63e4ac0d8cf161c549654ce6b430d68afbde4'


def _load(path, name):
    raw=Path(path).read_bytes()
    digest=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    if digest != PINS[name]:
        raise ValueError('source differs from pinned Publications blob: '+name)
    spec=importlib.util.spec_from_file_location('pinned_'+name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module,dict(git_blob=digest,sha256=hashlib.sha256(raw).hexdigest())


def audit(ugd_source, emk_source):
    ugd,ugd_pin=_load(ugd_source,'ugd')
    emk,emk_pin=_load(emk_source,'emk')
    source_certificates={}
    for name,module in [('ugd',ugd),('emk',emk)]:
        certificate=module.build_certificate()
        verdicts={key:value['verdict'] for key,value in certificate.items()
                  if isinstance(value,dict) and 'verdict' in value}
        if not verdicts or any(value!='PASS' for value in verdicts.values()):
            raise AssertionError('pinned source certificate did not replay: '+name)
        source_certificates[name]=dict(verdicts=verdicts,
            canonical_json_sha256=hashlib.sha256(json.dumps(certificate,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    x,y,z=[ugd.digit(0,0,s,K=4) for s in (-1,1,1)]
    left=ugd.add_digits(ugd.add_digits(x,y),z)
    right=ugd.add_digits(x,ugd.add_digits(y,z))
    assert left != right and left.total_seam()==right.total_seam()==1
    phase=ugd.mul_digits(ugd.digit(1,0,0,K=4),ugd.digit(1,0,0,K=4))
    actual=phase.digits[0][0]
    expected=(1+1)%4
    assert actual==1 and expected==2
    def state(n):return dict(digits=n.digits,ledger=n.ledger,total_seam=n.total_seam())
    return dict(schema='nrqc-native-source-adapter-audit-v1',status='PASS',
        source_repository='Parveen117/Publications',source_commit=SOURCE_COMMIT,
        source_pins=dict(ugd=ugd_pin,emk=emk_pin),source_certificates=source_certificates,
        strict_carry_witness=dict(left=state(left),right=state(right),strict_equality=False,
                                  equal_total_charge=True),
        phase_adapter_witness=dict(K=4,left_exponent=1,right_exponent=1,
            source_product_exponent=actual,quantum_phase_product_exponent=expected,
            quantum_phase_homomorphism=False),
        interpretation='Scoped source certificates replay; strict numeral carry and digit product are not substituted for the circuit coefficient field.',
        source_modified=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ugd-source',required=True,type=Path)
    parser.add_argument('--emk-source',required=True,type=Path)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    result=audit(args.ugd_source,args.emk_source)
    rendered=json.dumps(result,sort_keys=True,indent=2)+'\n'
    if args.out:args.out.write_text(rendered)
    print(rendered,end='')


if __name__=='__main__':main()
