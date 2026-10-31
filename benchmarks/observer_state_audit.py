"""Freeze a joint-state observer, then retain exact equal-probe comparisons."""
from __future__ import annotations

import argparse
from fractions import Fraction as Q
import hashlib
from itertools import product
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from native_relational_qc.calculator import run_calculation, display, real_sign
from native_relational_qc.certify import flat_field
from native_relational_qc.delta_ogmt import digest
from native_relational_qc.observer_tracking import calculator_request, likelihoods, seal
from native_relational_qc.observer_state import (
    AXES, GRID, Model, Planner, coherence, exact_evaluate, frame_acceleration,
    legacy_policy, no_record_policy, source_mixtures, transport,
)
from benchmarks.moving_observer_tracking_audit import reference as primitive_reference, write

PROTOCOL_PATH = ROOT / 'benchmarks/protocols/observer_state_v1.json'
LEGACY_PATH = ROOT / 'native_relational_qc/calculator_examples/moving_observer_policy.json'
POLICIES = ('coupled_adaptive', 'coupled_open_loop', 'phase_axes_joint_decoder',
            'constant_radius_adaptive', 'legacy_phase', 'no_records')


def protocol():
    return dict(schema='nrqc-observer-state-protocol-v1', model=Model().record(),
        policies=list(POLICIES), probes_per_decision=6, target_time=6,
        source_channel='rho_next = (3/4) U rho U_dagger + (1/4) rho_drive',
        source_resources='fresh probe at every time; rotation and mixing with declared equatorial preparations; no cloning or free unknown-state translation',
        radius='transverse Bloch contrast, not spatial distance or statevector normalization',
        primary_loss='abs(z_target - z_estimate)^2 / 4; smaller is better, not a classification probability',
        secondary_loss='(abs(z_target)^2 - predicted_radius^2)^2',
        selection='uniform declared prior only; all policies frozen before evaluation cases are scored',
        ranking='NumPy utilities rounded to 13 decimal places; first candidate wins ties; exact optimality not claimed',
        open_loop_search='all 4^5 schedules after first axis 0; same prior, actions and joint decoder',
        adaptive_search='full six-probe Bellman tree, first axis 0 by rotation symmetry',
        phase_axes_control='old shipped adaptive axes unchanged; refit only its terminal joint decoder under the driven prior',
        constant_radius_control=Model('constant_radius').record(),
        legacy_control='old shipped phase-only policy, unchanged axes and unit-radius predictions; explicitly mismatched model',
        no_records_control='six nominal probes ignored; output prior mean zero',
        primary_criterion='at least 5 percent relative mean loss reduction versus coupled_open_loop AND strictly lower mean loss than phase_axes_joint_decoder on both model_grid and shifted_phase',
        cases=dict(model_grid='16 even starts x velocities -1,0,+1 x drive offsets -8,+8',
                   shifted_phase='16 odd starts x velocities -1,0,+1 x offsets -8,+8',
                   faster_drift='16 odd starts x velocities -2,+2 x offsets -8,+8',
                   retention_mismatch='shifted_phase sources with retention 7/8; controller unchanged',
                   readout_flip_5pct='shifted_phase sources with independent readout flip 1/20; controller unchanged',
                   randomized_readout='shifted_phase sources with independent flip 1/2; records independent of source; prior-mean prediction minimizes average loss'),
        reference_cases='starts 2,3 x velocities -1,+1 x offsets -8,+8, plus start 3 velocity +1 offset +8 at flips 1/20 and 1/2; all six policies',
        exact_composition='32 exact calculator one-probe distributions; rational convex mixtures; all 64 record paths per source and policy; not one coherent mixed-state calculator job',
        frame_controls='full affine transport agrees with transformed lab trajectory; dropping displacement rotation fails; exact rotating-frame acceleration identity includes Coriolis, Euler and centrifugal terms',
        uncertainty='finite-family exact expectations and certified rounding enclosures, not physical confidence intervals',
        hardware_validated=False, computational_speedup_claimed=False)


def evaluation_cases():
    rows = []
    for family, starts, velocities, retention, flip in (
        ('model_grid', range(0,32,2), (-1,0,1), Q(3,4), Q(0)),
        ('shifted_phase', range(1,32,2), (-1,0,1), Q(3,4), Q(0)),
        ('faster_drift', range(1,32,2), (-2,2), Q(3,4), Q(0)),
        ('retention_mismatch', range(1,32,2), (-1,0,1), Q(7,8), Q(0)),
        ('readout_flip_5pct', range(1,32,2), (-1,0,1), Q(3,4), Q(1,20)),
        ('randomized_readout', range(1,32,2), (-1,0,1), Q(3,4), Q(1,2))):
        for start, velocity, offset in product(starts, velocities, (-8,8)):
            rows.append(dict(id=f'{family}_{start:02d}_{velocity:+d}_{offset:+d}', family=family,
                             start=start, velocity=velocity, offset=offset,
                             retention=str(retention), flip=str(flip)))
    return rows


def preparations(row, rounds=6):
    return source_mixtures(row['start'], row['velocity'], row['offset'], retention=Q(row['retention']), rounds=rounds)


def renamed(policy, name):
    return seal(dict({k:v for k,v in policy.items() if k != 'fingerprint'}, name=name))


def freeze_policies():
    old = json.loads(LEGACY_PATH.read_text())
    planner = Planner()
    adaptive = renamed(planner.adaptive(), 'coupled_adaptive')
    open_loop, search = planner.open_loop_search()
    policies = dict(coupled_adaptive=adaptive,
        coupled_open_loop=renamed(open_loop, 'coupled_open_loop'),
        phase_axes_joint_decoder=planner.redecode(old),
        constant_radius_adaptive=renamed(Planner(Model('constant_radius')).adaptive(), 'constant_radius_adaptive'),
        legacy_phase=legacy_policy(old), no_records=no_record_policy())
    return policies, search


def frame_controls():
    F = flat_field(); i = F.imag()
    # Independently specified lab path z(t)=1+(1+i)t, observer angle a(t)=t.
    # Differentiation at zero gives q=1, qdot=1, qddot=1-2i.
    terms = frame_acceleration(F(1), F(1), F(), F(), 0, 1, 0)
    correct = terms['total'] == 1-2*i
    reconstructed_lab = terms['total']+2*i*F(1)-F(1)
    omitted_coriolis_lab = terms['total']-terms['coriolis']+2*i*F(1)-F(1)
    # A finite translation of +1 followed by a 90-degree observer turn.
    affine = transport(F(1), 0, F(1), 8)
    omitted_displacement_rotation = F.root(-16)+1
    checks = dict(acceleration_identity=correct, reconstructed_lab_is_straight=reconstructed_lab == 0,
                  omitted_coriolis_fails=omitted_coriolis_lab == 2*i,
                  full_affine_transport=affine == -2*i,
                  omitted_displacement_rotation_fails=omitted_displacement_rotation != affine)
    # An actual driven source trajectory under a nonuniform observer schedule.
    states = [coherence(m) for m in source_mixtures(3, 1, 8)]
    angles = (0, 3, 8, 7, 12, 19, 30)
    checks['driven_source_frame_covariance'] = all(
        transport(Q(3,4)*F.root(-2*angles[t])*states[t], 1,
                  Q(1,4)*F.root(2*(11-angles[t])), angles[t+1]-angles[t])
        == F.root(-2*angles[t+1])*states[t+1] for t in range(6))
    if not all(checks.values()):
        raise ArithmeticError('rotating frame identity or negative control failed')
    return checks


def reference(policy, row, exact):
    """Independent Kraus/density-matrix propagation, then every record branch."""
    from qiskit import __version__
    from qiskit.quantum_info import DensityMatrix, Kraus
    theta = 2*np.pi/GRID
    lam = float(Q(row['retention']))
    vector = np.array([1, np.exp(1j*row['start']*theta)])/np.sqrt(2)
    drive = np.array([1, np.exp(1j*(row['start']+row['offset'])*theta)])/np.sqrt(2)
    rotation = np.diag([1, np.exp(1j*row['velocity']*theta)])
    matrices = [np.sqrt(lam)*rotation] + [np.sqrt(1-lam)*np.outer(drive, bra) for bra in np.eye(2)]
    channel = Kraus(matrices)
    state = DensityMatrix(vector)
    states = [state]
    rounds = policy['model']['rounds']
    for _ in range(rounds):
        state = state.evolve(channel)
        states.append(state)
    completeness = float(np.max(np.abs(sum(k.conj().T@k for k in matrices)-np.eye(2))))
    valid = all(s.is_valid() for s in states) and channel.is_cptp()
    table = []
    for state in states[:-1]:
        probabilities = []
        for axis in AXES:
            ket = np.array([1, np.exp(1j*axis*theta)])/np.sqrt(2)
            p = float(np.real(ket.conj()@state.data@ket))
            probabilities.append(p*(1-2*float(Q(row['flip'])))+float(Q(row['flip'])))
        table.append(probabilities)
    target = 2*states[-1].data[1,0]
    loss, radial, norm = 0., 0., 0.
    branch_errors = []
    def visit(node, t, weight, bits):
        nonlocal loss, radial, norm
        if t == rounds:
            radius = float(Q(node['radius']))
            guess = radius*np.exp(1j*node['phase']*theta)
            loss += weight*abs(target-guess)**2/4
            radial += weight*(abs(target)**2-radius*radius)**2
            norm += weight
            branch_errors.append(abs(weight-float(display(exact['branches'][bits])['decimal'])))
            return
        p = table[t][AXES.index(node['axis'])]
        visit(node['zero'], t+1, weight*p, bits+'0')
        visit(node['one'], t+1, weight*(1-p), bits+'1')
    visit(policy['tree'], 0, 1., '')
    error = max(branch_errors+[completeness, abs(norm-1),
                abs(loss-float(display(exact['error'])['decimal'])),
                abs(radial-float(display(exact['squared_contrast_error'])['decimal'])),
                abs(abs(target)**2-float(display(exact['target_radius_squared'])['decimal']))])
    return dict(passed=bool(valid and error < 2e-10), max_absolute_error=float(error),
                kraus_complete=bool(completeness < 1e-12), density_matrices_valid=bool(valid),
                branches_checked=len(branch_errors), qiskit_version=__version__)


def audit(output, protocol_commit, *, compare=False, timeout=30):
    if type(protocol_commit) is not str or len(protocol_commit) != 40 or any(c not in '0123456789abcdef' for c in protocol_commit):
        raise ValueError('full protocol commit SHA required')
    plan = json.loads(PROTOCOL_PATH.read_text())
    if plan != protocol():
        raise ValueError('checked-in protocol differs from implementation')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for name in ('inputs', 'results', 'evaluations'):
        (output/name).mkdir()
    write(output/'protocol.json', plan)
    write(output/'status.json', dict(status='running', protocol_commit=protocol_commit))
    started = time.perf_counter()
    try:
        policies, searched = freeze_policies()
        write(output/'frozen_policies.json', policies)
        write(output/'open_loop_search.json', searched)
        frozen = (output/'frozen_policies.json').read_bytes()
        print('All six policies frozen before evaluation', flush=True)
        calculator_results, references = [], {}
        for phase in range(GRID):
            request = calculator_request([phase], [0])
            label = f'likelihood_{phase:02d}'
            write(output/'inputs'/(label+'.json'), request)
            result = run_calculation(request, timeout_seconds=timeout)
            write(output/'results'/(label+'.json'), result)
            if result['status'] != 'completed':
                raise RuntimeError(label+': '+result['status'])
            calculator_results.append(result)
            if compare:
                references[label] = primitive_reference(request, result)
                if not references[label]['passed']:
                    raise ArithmeticError('primitive reference disagrees: '+label)
        bank = likelihoods(calculator_results)
        rows = evaluation_cases()
        write(output/'evaluation_cases.json', rows)
        F = flat_field()
        scores, exact_scores, per_case = {}, {}, {}
        keys = ('error', 'squared_contrast_error', 'axis_changes', 'target_radius_squared')
        for name, policy in policies.items():
            evaluated, grouped = [], {}
            per_case[name] = {}
            for row in rows:
                result = exact_evaluate(policy, preparations(row), bank, flip=Q(row['flip']))
                per_case[name][row['id']] = result['error']
                evaluated.append(dict(row, **{k:display(result[k]) for k in keys+('normalization',)}))
                grouped.setdefault(row['family'], []).append(result)
            scores[name], exact_scores[name] = {}, {}
            for family, values in grouped.items():
                means = {key:sum((r[key] for r in values), F())*Q(1,len(values)) for key in keys}
                exact_scores[name][family] = means
                scores[name][family] = dict(cases=len(values), **{k:display(v) for k,v in means.items()})
                print(name, family, 'joint loss', scores[name][family]['error']['decimal'], flush=True)
            write(output/'evaluations'/(name+'.json'), evaluated)
        comparisons, criterion = {}, True
        for family in scores['coupled_adaptive']:
            a = exact_scores['coupled_adaptive'][family]['error']
            b = exact_scores['coupled_open_loop'][family]['error']
            old_axes = exact_scores['phase_axes_joint_decoder'][family]['error']
            counts = dict(better=0, tied=0, worse=0)
            for row in rows:
                if row['family'] == family:
                    sign = real_sign(per_case['coupled_open_loop'][row['id']]-per_case['coupled_adaptive'][row['id']])
                    counts['better' if sign > 0 else 'worse' if sign < 0 else 'tied'] += 1
            comparisons[family] = dict(open_loop_minus_adaptive=display(b-a),
                phase_axes_minus_adaptive=display(old_axes-a),
                five_percent_improvement=bool(real_sign(Q(19,20)*b-a) >= 0),
                better_than_old_axes=bool(real_sign(old_axes-a) > 0), per_case_vs_open_loop=counts)
            if family in ('model_grid', 'shifted_phase'):
                criterion &= comparisons[family]['five_percent_improvement'] and comparisons[family]['better_than_old_axes']
        # Completely randomized bits are independent of the hidden source.
        # A still-informative decoder may make nonzero guesses: its average loss
        # cannot beat the calibrated uninformative/prior-mean decoder, zero.
        baseline = exact_scores['no_records']['randomized_readout']['error']
        controls = {name:bool(real_sign(exact_scores[name]['randomized_readout']['error']-baseline) >= 0) for name in policies}
        random_row = next(r for r in rows if r['family'] == 'randomized_readout')
        for name, policy in policies.items():
            paths = exact_evaluate(policy, preparations(random_row), bank, flip=Q(1,2), keep_branches=True)['branches']
            controls[name+'_uniform_records'] = all(w == Q(1,64) for w in paths.values())
        if not all(controls.values()):
            raise ArithmeticError('uninformative-record negative control failed')
        witnesses = []
        if compare:
            chosen = [dict(start=s, velocity=v, offset=o, retention='3/4', flip='0') for s,v,o in product((2,3),(-1,1),(-8,8))]
            chosen += [dict(start=3, velocity=1, offset=8, retention='3/4', flip=f) for f in ('1/20','1/2')]
            for index, row in enumerate(chosen):
                for name, policy in policies.items():
                    exact = exact_evaluate(policy, preparations(row), bank, flip=Q(row['flip']), keep_branches=True)
                    label = f'mixed_path_{index}_{name}'
                    references[label] = reference(policy, row, exact)
                    if not references[label]['passed']:
                        raise ArithmeticError('mixed-state reference disagrees: '+label)
                    witnesses.append(dict(id=label, source=row, policy=name,
                        exact_error=display(exact['error']),
                        probabilities={b:display(p) for b,p in exact['branches'].items()}))
        write(output/'mixed_state_witnesses.json', witnesses)
        if (output/'frozen_policies.json').read_bytes() != frozen:
            raise AssertionError('frozen policies changed during evaluation')
        sources = ('native_relational_qc/observer_state.py', 'native_relational_qc/observer_tracking.py',
                   'native_relational_qc/calculator.py', 'native_relational_qc/cyclotomic_pow2.py',
                   'native_relational_qc/certify.py', 'native_relational_qc/phase_interop.py',
                   'native_relational_qc/__main__.py', 'benchmarks/observer_state_audit.py',
                   'benchmarks/protocols/observer_state_v1.json', str(LEGACY_PATH.relative_to(ROOT)))
        report = dict(schema='nrqc-observer-state-audit-v1', status='completed', verification_passed=True,
            primary_improvement_passed=bool(criterion), protocol_commit=protocol_commit,
            protocol_sha256=digest(plan), frozen_policies_sha256=hashlib.sha256(frozen).hexdigest(),
            scores=scores, comparisons=comparisons, randomized_readout_controls=controls,
            frame_controls=frame_controls(), numeric_references=references,
            exact_calculator_requests=GRID, exact_trajectory_evaluations=len(rows)*len(policies),
            additional_reference_evaluations=len(witnesses), records_per_trajectory=64,
            evidence_class='DECLARED_CPTP_FRESH_PROBE_SOURCE_WITH_STATED_READOUT_STRESS',
            no_evaluation_trajectory_used_for_planning=True, hardware_job_id=None,
            hardware_validated=False, computational_advantage_established=False,
            source_preparation_cost_measured=False, python=platform.python_version(),
            wall_seconds=time.perf_counter()-started,
            source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
            caveat='Finite-family model expectations; coordinate coupling is not evidence of a new force or hardware speedup. Shifted phase grids share exact Fourier averages, not independent generalization evidence.')
        write(output/'summary.json', report)
        write(output/'status.json', dict(status='completed'))
        write(output/'manifest.sha256.json', {p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.rglob('*.json'))})
        return report
    except Exception as error:
        write(output/'status.json', dict(status='incomplete', verification_passed=False, error=str(error)))
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--protocol-commit', required=True)
    parser.add_argument('--compare-qiskit', action='store_true')
    args = parser.parse_args(argv)
    result = audit(args.out, args.protocol_commit, compare=args.compare_qiskit)
    print(json.dumps({k:result[k] for k in ('status','verification_passed','primary_improvement_passed','wall_seconds')}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
