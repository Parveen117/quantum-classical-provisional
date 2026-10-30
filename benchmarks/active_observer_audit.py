"""Fixed train/freeze/evaluate protocol for learned local observation order.

No optimization on validation/test. Same callback, noise realization, contract,
and max budget for every policy. Oracle derivatives are used only by the scorer.
The learned controller is classical; the existing QNN checkpoint is unchanged.
"""
from collections import Counter
from fractions import Fraction as Q
import hashlib
import io
import json
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_relational_qc.active_observer import Contract, fit_policy, observe, load_policy, predict_hessian
from native_relational_qc.active_observer_tasks import make_splits, sensor, blind_pair
from native_relational_qc.self_learning import digest

NOISE = Q(1, 200000)
POLICIES = ("learned", "s_first", "v_first", "sensitivity", "full")


def collect_training(cases):
    rows = []
    contract = Contract(noise=NOISE)
    for case in cases:
        a, b = [observe(sensor(case, NOISE), case.point, contract=contract, policy=policy)
                for policy in ("s_first", "v_first")]
        assert a['features'] == b['features']
        costs = [r['blocks'] + (10 if r['prediction'] is None else 0) for r in (a, b)]
        rows.append(dict(family=case.family, point=[str(x) for x in case.point],
                         features=a['features'], costs=costs,
                         acquired_training_blocks=a['blocks']+b['blocks']))
    return rows


def numeric_rows(rows):
    return [dict(features=[Q(x) for x in r['features']], costs=r['costs']) for r in rows]


def evaluate(cases, model, noise):
    contract = Contract(noise=noise)
    totals = {p:dict(cases=len(cases), answered=0, correct=0, wrong_certificates=0, total_blocks=0,
                     total_scalar_readings=0, derivative_bound_violations=0, curvature_bound_violations=0,
                     histogram=Counter(), absolute_error_sum=Q(0), max_absolute_error=Q(0), wall_seconds=0.0,
                     forecast_bound_violations=0, forecast_error_sum=Q(0), forecast_bound_sum=Q(0)) for p in POLICIES}
    details = []
    for case in cases:
        # Truth stays on the scorer side; observe receives only the callback.
        truth = case.energy.curvature(case.point)
        jets = case.energy.jets(case.point)
        sign = (truth > 0)-(truth < 0)
        row = dict(family=case.family, point=[str(x) for x in case.point], true_curvature=str(truth), policies={})
        for policy in POLICIES:
            start = time.perf_counter()
            r = observe(sensor(case, noise), case.point, contract=contract, policy=policy, model=model)
            t = totals[policy]
            t['wall_seconds'] += time.perf_counter()-start
            t['total_blocks'] += r['blocks']
            t['total_scalar_readings'] += r['scalar_readings']
            t['histogram'][r['blocks']] += 1
            if r['prediction'] is not None:
                t['answered'] += 1
                t['correct'] += int(r['prediction'] == sign)
                t['wrong_certificates'] += int(r['prediction'] != sign)
            for estimate, exact, error in zip(r['derivative_estimates'], jets, r['derivative_error_bounds']):
                t['derivative_bound_violations'] += sum(abs(Q(a)-b) > Q(error) for a, b in zip(estimate, exact))
            if r['curvature_interval'] is not None:
                lo, hi = map(Q, r['curvature_interval'])
                t['curvature_bound_violations'] += int(not lo <= truth <= hi)
            error = abs(Q(r['estimate'])-truth)
            t['absolute_error_sum'] += error
            t['max_absolute_error'] = max(t['max_absolute_error'], error)
            forecast = predict_hessian(r, (Q(1, 16), Q(-1, 16)), contract=contract)
            target = tuple(Q(x) for x in forecast['point'])
            assert forecast['point'] not in [reading['point'] for reading in r['readings']]
            actual_response = case.energy.hessian(target)  # held-out scoring only
            forecast_error = max(abs(Q(a)-b) for a, b in zip(forecast['estimate'], actual_response))
            forecast_bound = Q(forecast['component_error_bound'])
            t['forecast_error_sum'] += forecast_error
            t['forecast_bound_sum'] += forecast_bound
            t['forecast_bound_violations'] += int(forecast_error > forecast_bound)
            record = dict(blocks=r['blocks'], status=r['status'], prediction=r['prediction'], refinement_order=r['refinement_order'])
            if policy == 'learned':
                record.update(estimate=r['estimate'], curvature_interval=r['curvature_interval'],
                              derivative_estimates=r['derivative_estimates'], derivative_error_bounds=r['derivative_error_bounds'],
                              withheld_response_forecast=forecast,
                              actual_withheld_response=[str(x) for x in actual_response])
            row['policies'][policy] = record
        details.append(row)
    for policy, t in totals.items():
        assert not (t['wrong_certificates'] or t['derivative_bound_violations'] or t['curvature_bound_violations'] or t['forecast_bound_violations'])
        t['coverage'] = str(Q(t['answered'], len(cases)))
        t['conditional_accuracy'] = str(Q(t['correct'], t['answered'])) if t['answered'] else None
        t['correct_fraction_all_cases'] = str(Q(t['correct'], len(cases)))
        t['mean_blocks'] = str(Q(t['total_blocks'], len(cases)))
        # Fractions across different inverse Hessians can grow extremely large.
        # Scores are presentation-only floats; certificates and per-case bounds
        # remain exact rational arithmetic.
        t['mean_absolute_curvature_error'] = float(t.pop('absolute_error_sum')/len(cases))
        t['max_absolute_curvature_error'] = float(t.pop('max_absolute_error'))
        t['mean_forecast_max_entry_error'] = float(t.pop('forecast_error_sum')/len(cases))
        t['mean_forecast_entry_bound'] = float(t.pop('forecast_bound_sum')/len(cases))
        t['histogram'] = dict(sorted(t['histogram'].items()))
    full = totals['full']['total_blocks']
    comparisons = {p:dict(blocks_saved_vs_full=full-t['total_blocks'],
                         fractional_saving_vs_full=str(Q(full-t['total_blocks'], full))) for p, t in totals.items()}
    return dict(summary=totals, comparisons=comparisons, cases=details)


def dataset_manifest(splits):
    out = {}
    for name, cases in splits.items():
        functions = {}
        for c in cases:
            if c.family not in functions:
                functions[c.family] = dict(energy=c.energy.record(), noise_seed=c.noise_seed,
                                          positive_patch=c.energy.positive_patch(), points=[])
            functions[c.family]['points'].append([str(x) for x in c.point])
        out[name] = functions
    return out


def main():
    start_all = time.perf_counter()
    suite = unittest.TestSuite()
    for name in ('test_active_observer.py', 'test_self_learning.py', 'test_constitutive_response.py'):
        found = unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern=name)
        if not found.countTestCases():
            raise ValueError('missing regression suite: '+name)
        suite.addTests(found)
    stream = io.StringIO()
    tests = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    if not tests.wasSuccessful():
        print(stream.getvalue())
        raise SystemExit(1)
    print('Tests passed:', tests.testsRun, flush=True)
    splits = make_splits()
    manifest = dataset_manifest(splits)
    start = time.perf_counter()
    training = collect_training(splits['train'])
    model = fit_policy(numeric_rows(training), depth=2, min_leaf=8)
    fit_seconds = time.perf_counter()-start
    frozen = json.loads(json.dumps(model))
    load_policy(frozen)
    print('Policy frozen; tree:', frozen['tree'], 'fit_seconds:', round(fit_seconds, 3), flush=True)
    evaluations = {}
    for name in ('validation', 'test'):
        evaluations[name] = {}
        for label, noise in (('clean', Q(0)), ('bounded_noise', NOISE)):
            report = evaluate(splits[name], frozen, noise)
            evaluations[name][label] = report
            print(name, label, {p:(v['correct'], v['answered'], v['mean_blocks']) for p, v in report['summary'].items()}, flush=True)
    assert frozen == model
    challenge = []
    for c in blind_pair():
        before = observe(sensor(c, 0), c.point, max_readings=5)
        after = observe(sensor(c, 0), c.point, policy='learned', model=frozen)
        challenge.append(dict(family=c.family, true_curvature=str(c.energy.curvature(c.point)),
                              initial=before, adaptive=after))
    assert challenge[0]['initial']['readings'] == challenge[1]['initial']['readings']
    files = ('native_relational_qc/active_observer.py', 'native_relational_qc/active_observer_tasks.py',
             'tests/test_active_observer.py', 'benchmarks/active_observer_audit.py',
             'native_relational_qc/emk_tensor.py', 'native_relational_qc/self_learning.py',
             'phase_seam_foundation/constitutive_response.py')
    report = dict(schema='native-active-observer-audit-v1', author='Monty',
                  status='SYNTHETIC_BOUNDED_ACQUISITION_EXPERIMENT',
                  tests=dict(count=tests.testsRun, passed=True, failures=0, errors=0, skipped=len(tests.skipped)),
                  python_version=sys.version.split()[0], fit_wall_seconds=fit_seconds,
                  training_sensor_blocks=sum(r['acquired_training_blocks'] for r in training),
                  savings_exclude_training_acquisition_and_computation=True,
                  protocol=dict(contract=Contract(noise=NOISE).record(), seeds=dict(train=3101, validation=3102, test=3103),
                      energy_functions=dict(train=64, validation=16, test=40), points_per_function=2,
                      whole_function_split=True, test_adds_unseen_quintic_mixed_supports=['s^3*v^2', 's^2*v^3'],
                      initial_blocks=5, refinement_blocks_per_axis=2, maximum_blocks=9,
                      depth=2, min_leaf=8, training_only_noisy=True,
                      selection='training acquisition cost only; validation and test after checkpoint freeze',
                      external_blind_test=False, sensor_noise='deterministic SHA256 indexed bounded uniform 21 levels',
                      unseen_training_noise_seeds=True, reward='negative block count, plus 10 penalty for abstention',
                      quantum_policy_training=False, existing_qnn_checkpoint_unchanged=True,
                      withheld_forecast_displacement=['1/16', '-1/16'],
                      forecast_truth_only_in_scorer_not_controller=True,
                      evaluation_oracle_readings_excluded_from_acquisition_counts=True,
                      general_rsc_transport_implemented=False, coordinate_frame='one fixed affine s,v chart'),
                  model_fingerprint=model['fingerprint'], dataset_sha256=digest(manifest),
                  training_cost_rows_sha256=digest(training), evaluations=evaluations,
                  indistinguishable_initial_reading_challenge=challenge,
                  checked_sources_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},
                  hardware_jobs=0, measured_device_data=False, quantum_advantage_claim=False,
                  total_wall_seconds=time.perf_counter()-start_all)
    folder = ROOT/'native_relational_qc'/'learning'/'active_observer'
    folder.mkdir(exist_ok=True)
    for filename, content in (('qualification.json', report), ('datasets.json', manifest),
                              ('policy.json', model), ('training_costs.json', training)):
        (folder/filename).write_text(json.dumps(content, indent=2, allow_nan=False)+'\n')
    (folder/'test_results.txt').write_text(stream.getvalue())
    print('Saved reproducible audit; total_seconds:', round(report['total_wall_seconds'], 3), flush=True)


if __name__ == '__main__':
    main()
