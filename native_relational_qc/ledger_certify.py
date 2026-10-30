"""Re-derive four photonic ledger targets with the calculator's flat field.

This certifies bounded ideal model arithmetic, never a measured device or a
lab grader status. Every expected target is checked against a fresh derivation.
"""
import argparse
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
from time import perf_counter

from .cyclotomic_pow2 import field_of_order
from .calculator import display, loads

F=field_of_order(64)
EXPECTED={'fusion_success':'1/2','purification_fidelity':'841/932',
          'source_bell_weights':['3/4','1/12','1/12','1/12']}


def _r(v):
    v=F(v)
    if any(e for e,c in v.terms):raise ArithmeticError('expected a rational derived result')
    return Q(v._list()[0],v.den)


def _bell_weights(rho, norm):
    vectors=((1,0,0,1),(1,0,0,-1),(0,1,1,0),(0,1,-1,0))
    return tuple(_r(sum((F(v[i])*F(rho[i][j])*F(v[j]) for i in range(4) for j in range(4)),F())/(2*norm)) for v in vectors)


def _shown(value,digits):
    return dict(rational=str(_r(value)),**display(F(value),digits))


def certify(*, claims=None, decimal_places=12):
    from phase_seam_foundation.dual_rail import fusion_outcomes, total_probability, MEASURED
    from phase_seam_foundation.source_distillation import dilation_certificate, optical_round, purification_schedule
    from phase_seam_foundation.cluster_noise import first_order_error, XOR_CHECKPOINT, source_map
    start=perf_counter()
    if claims is not None:
        if not isinstance(claims,dict) or set(claims)!=set(EXPECTED):raise ValueError('claims must contain exactly '+', '.join(EXPECTED))
        if not isinstance(claims['source_bell_weights'],list) or len(claims['source_bell_weights'])!=4:raise ValueError('four source weights required')
    expected=EXPECTED if claims is None else claims
    for key in ('fusion_success','purification_fidelity'):
        if type(expected[key]) is not str:raise ValueError('claims must be rational strings')
    if any(type(v) is not str for v in expected['source_bell_weights']):raise ValueError('claims must be rational strings')

    fusion=fusion_outcomes()
    success=_r(fusion['success_probability'])
    single_click=_r(total_probability({k:v for k,v in fusion['success'].items() if k[MEASURED[0]]==1}))
    dilation=dilation_certificate()
    weights=_bell_weights(dilation['density'],dilation['probability'])
    if sum(weights)!=1:raise ArithmeticError('source weights do not normalize')
    rounds=[];p=weights
    for basis in 'ZX':
        result=optical_round(p,basis)
        if result['false_payload_probability']!=0:raise ArithmeticError('ideal purification accepted an invalid payload')
        p=_bell_weights(result['valid_payload_density'],result['herald_probability'])
        rounds.append(dict(basis=basis,success=_shown(result['herald_probability'],decimal_places),
                           weights=[_shown(v,decimal_places) for v in p]))
    fidelity=p[0]
    noise=first_order_error((0,32),XOR_CHECKPOINT,'1/40','243/4000')
    w=noise['double_fraction'];first=_r(noise['first_order']);remainder=noise['remainder']
    upper=first+remainder;ratio=upper/w
    high_w=Q(1,5)
    high_bound=(first/w)*high_w+1-(1-high_w/4)**12-12*(high_w/4)*(1-high_w/4)**11
    negative={
        'single_click_is_not_total_success':single_click!=success,
        'discarding_source_coherence_changes_fidelity':(dilation['density'][0][0]+dilation['density'][3][3])/(2*dilation['probability'])!=weights[0],
        'repeating_Z_is_not_ZX':purification_schedule(weights,'ZZ')['fidelity']!=fidelity,
        'rounded_2_8w_does_not_bound_the_full_expression':high_bound>Q(14,5)*high_w,
    }
    values={'fusion_success':str(success),'purification_fidelity':str(fidelity),
            'source_bell_weights':[str(v) for v in weights]}
    matches={key: (tuple(map(Q,values[key]))==tuple(map(Q,expected[key])) if key=='source_bell_weights' else Q(values[key])==Q(expected[key])) for key in EXPECTED}
    files=['native_relational_qc/cyclotomic_pow2.py','native_relational_qc/certify.py','native_relational_qc/ledger_certify.py',
           'phase_seam_foundation/dual_rail.py','phase_seam_foundation/source_distillation.py',
           'phase_seam_foundation/cluster_noise.py','phase_seam_foundation/cluster_compile.py']
    root=Path(__file__).resolve().parents[1]
    hashes={f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in files}
    return dict(schema='nrqc-ledger-certification-v1',status='certified' if all(matches.values()) and all(negative.values()) else 'failed',
        evidence_class='LOCAL_IDEAL_MODEL_DERIVATION',hardware_job_id=None,
        field='cyclotomic_pow2:64',source_sha256=hashes,expected_claims=expected,claim_checks=matches,
        fusion=dict(success=_shown(success,decimal_places),single_click=_shown(single_click,decimal_places),
                    normalization=_shown(success+_r(fusion['failure_probability']),decimal_places),method='permanent-derived Fock amplitudes and factorial norm'),
        source=dict(weights=[_shown(v,decimal_places) for v in weights],method='eight-mode four-photon dilation, environment trace, Bell projections'),
        purification=dict(fidelity=_shown(fidelity,decimal_places),rounds=rounds,method='two ideal optical density contractions, Z then X'),
        readout_bound=dict(x='1/40',eta='243/4000',double_fraction=_shown(w,decimal_places),
            first_order=_shown(first,decimal_places),remainder=_shown(remainder,decimal_places),
            total_upper_bound=_shown(upper,decimal_places),coefficient_at_declared_point=_shown(ratio,decimal_places),
            first_order_coefficient=_shown(first/w,decimal_places),
            formula='A*w + 1-(1-w/4)^12-12*(w/4)*(1-w/4)^11; A derived from circuit response',
            rounded_2_8_is_universal=False,
            negative_control_w=str(high_w),negative_control_expression=_shown(high_bound,decimal_places),
            negative_control_scope='counterexample to bounding this expression by 2.8w; not a measured readout error',
            bell_pairs=source_map()['bell_pairs']),
        negative_controls=negative,
        assumptions=['ideal type-I fusion','fully supplied independent Bell pairs for purification',
                     'independent pair errors; worst-pattern bounds on the two larger stars',
                     'no dark counts, distinguishability, correlated loss or physical calibration'],
        execution_seconds=perf_counter()-start)


def main(argv=None):
    parser=argparse.ArgumentParser(prog='nrqc certify',description=__doc__,epilog='Cluster witness: nrqc certify cluster --help')
    parser.add_argument('--claims',type=Path,help='optional exact claims JSON; mismatches return exit 1')
    parser.add_argument('--out',type=Path)
    parser.add_argument('--decimal-places',type=int,default=12)
    args=parser.parse_args(argv)
    try:
        result=certify(claims=loads(args.claims.read_text()) if args.claims else None,decimal_places=args.decimal_places)
    except (ValueError,TypeError,OSError) as error:
        result=dict(schema='nrqc-ledger-certification-v1',status='invalid_request',error=str(error))
    text=json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+'\n'
    if args.out:args.out.write_text(text)
    print(text,end='')
    return 0 if result['status']=='certified' else 2 if result['status']=='invalid_request' else 1
