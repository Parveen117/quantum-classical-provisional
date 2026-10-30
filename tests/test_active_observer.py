import copy
from fractions import Fraction as Q
import itertools
import json
import random
import unittest

from native_relational_qc.active_observer import (
    Acquisition, Contract, Interval, choose, curvature_interval, enclosure,
    fit_policy, load_policy, native_curvature, observe, predict_hessian,
)
from native_relational_qc.active_observer_tasks import PolynomialEnergy, blind_pair, make_splits, sensor
from native_relational_qc.self_learning import digest
from phase_seam_foundation.constitutive_response import CubicEnergy, response_record


class ActiveObserverTests(unittest.TestCase):
    def test_energy_derivative_has_independent_monomial_values(self):
        # U=s^3*v^2, so Hss=6*s*v^2, Hsv=6*s^2*v, Hvv=2*s^3.
        energy = PolynomialEnergy(((3, 2, Q(12)),))
        self.assertEqual(energy.hessian((Q(2), Q(3))), (Q(108), Q(72), Q(16)))
        self.assertEqual(energy.jets((Q(2), Q(3))), ((Q(54), Q(72), Q(24)), (Q(72), Q(24), Q(0))))

    def test_native_curvature_agrees_with_existing_adapter_at_many_points(self):
        rng = random.Random(5201)
        for _ in range(20):
            third = tuple(Q(rng.randrange(-3, 4), 8) for _ in range(4))
            source = CubicEnergy((4, 1, 5), third, (10, -10))
            point = (Q(rng.randrange(-1, 2), 8), Q(rng.randrange(-1, 2), 8))
            record = response_record(source, point)
            h = record['hessian']
            ds, dv = record['hessian_first']
            flatten = lambda m: (m[0][0], m[0][1], m[1][1])
            self.assertEqual(native_curvature(flatten(h), flatten(ds), flatten(dv)), record['selected_response_curvature'])

    def test_interval_curvature_contains_independent_sampled_native_values(self):
        h, ds, dv = (Q(4), Q(1), Q(5)), (Q(1), Q(1, 8), Q(-1, 4)), (Q(1, 8), Q(-1, 4), Q(-2))
        radius = Q(1, 100)
        box = curvature_interval(*(tuple(enclosure(x, radius) for x in row) for row in (h, ds, dv)))
        rng = random.Random(5202)
        for _ in range(40):
            sample = [tuple(x+rng.choice((-1, 0, 1))*radius for x in row) for row in (h, ds, dv)]
            self.assertTrue(box.contains(native_curvature(*sample)))
        with self.assertRaises(ValueError):
            curvature_interval((enclosure(0, 1), interval_one(), interval_one()), ds, dv)

    def test_initial_blindness_requires_new_observation(self):
        cases = blind_pair()
        outputs = [observe(sensor(c, 0), c.point, max_readings=5) for c in cases]
        self.assertEqual(outputs[0]['readings'], outputs[1]['readings'])
        self.assertLess(cases[0].energy.curvature(cases[0].point)*cases[1].energy.curvature(cases[1].point), 0)
        self.assertTrue(all(r['prediction'] is None for r in outputs))
        refined = [observe(sensor(c, 0), c.point) for c in cases]
        self.assertEqual([r['blocks'] for r in refined], [7, 7])
        self.assertEqual([r['prediction'] for r in refined], [1, -1])

    def test_richardson_recovers_all_jets_of_quintic_models(self):
        for case in make_splits()['train'][:12]:
            acq = Acquisition(sensor(case, 0), case.point, Contract())
            acq.initial()
            acq.refine(0)
            acq.refine(1)
            self.assertEqual(tuple(acq.estimates), case.energy.jets(case.point))
            self.assertEqual(acq.errors(), (0, 0))

    def test_noise_and_truncation_bounds_contain_exact_derivatives(self):
        noise = Q(1, 200000)
        for case in make_splits()['train'][:12]:
            acq = Acquisition(sensor(case, noise), case.point, Contract(noise=noise))
            acq.initial()
            exact = case.energy.jets(case.point)
            for step in range(3):
                for row, true, error in zip(acq.estimates, exact, acq.errors()):
                    self.assertTrue(all(abs(a-b) <= error for a, b in zip(row, true)))
                self.assertTrue(acq.bounds().contains(case.energy.curvature(case.point)))
                if step < 2:
                    acq.refine(step)

    def test_no_silent_budget_overrun_or_duplicate_reads(self):
        case = blind_pair()[0]
        seen = []
        def read(point):
            self.assertNotIn(point, seen)
            seen.append(point)
            return case.energy.hessian(point)
        output = observe(read, case.point, policy='v_first', max_readings=7)
        self.assertEqual(len(seen), 7)
        self.assertEqual(output['status'], 'READING_BUDGET_EXHAUSTED')
        self.assertIsNone(output['prediction'])
        self.assertEqual(output['scalar_readings'], 21)

    def test_zero_curvature_abstains_after_full_budget(self):
        energy = PolynomialEnergy(((2, 0, Q(4)), (1, 1, Q(1)), (0, 2, Q(5))))
        result = observe(energy.hessian, (0, 0))
        self.assertEqual(result['blocks'], 9)
        self.assertIsNone(result['prediction'])
        self.assertEqual(result['curvature_interval'], ['0', '0'])

    def test_nonpositive_hessian_fails_closed(self):
        result = observe(lambda point: (0, 0, 0), (0, 0))
        self.assertIsNone(result['prediction'])
        self.assertEqual(result['status'], 'HESSIAN_POSITIVITY_UNRESOLVED')

    def test_function_splits_and_new_mixed_support_are_disjoint(self):
        splits = make_splits()
        groups = [{digest(c.energy.record()) for c in rows} for rows in splits.values()]
        self.assertEqual([len(x) for x in groups], [64, 16, 40])
        self.assertTrue(all(not a & b for a, b in itertools.combinations(groups, 2)))
        self.assertFalse(any(i+j == 5 and i in (2, 3) for c in splits['train'] for i, j, _ in c.energy.terms))
        self.assertTrue(any(i+j == 5 and i in (2, 3) for c in splits['test'] for i, j, _ in c.energy.terms))
        for rows in splits.values():
            for c in rows:
                self.assertGreater(Q(c.energy.positive_patch()['lower_eigenvalue']), 0)
                self.assertTrue(all(abs(t) <= 6 for i, j, t in c.energy.terms if i+j == 5))

    def test_cost_sensitive_training_uses_only_supplied_rows(self):
        rows = [dict(features=[Q(i), *([Q(0)]*7)], costs=[7, 9] if i < 8 else [9, 7]) for i in range(16)]
        model = fit_policy(rows, depth=2, min_leaf=4)
        self.assertEqual(choose(model, [Q(-10), *([0]*7)]), 0)
        self.assertEqual(choose(model, [Q(100), *([0]*7)]), 1)
        self.assertEqual(model, fit_policy(copy.deepcopy(rows), depth=2, min_leaf=4))
        swapped = fit_policy([dict(features=r['features'], costs=r['costs'][::-1]) for r in rows], min_leaf=4)
        self.assertEqual(choose(swapped, [Q(-10), *([0]*7)]), 1)

    def test_checkpoint_tampering_and_invalid_inputs_rejected(self):
        model = fit_policy([dict(features=[0]*8, costs=[7, 9])])
        changed = copy.deepcopy(model)
        changed['tree']['action'] = 1
        with self.assertRaises(ValueError):
            load_policy(changed)
        with self.assertRaises(ValueError):
            Contract(degree_limit=6)
        with self.assertRaises(TypeError):
            Contract(noise=0.1)
        with self.assertRaises(ValueError):
            observe(lambda p: (4, 1, 5), (0, 0), max_readings=4)

    def test_constant_policy_cannot_change_certified_answer(self):
        for action in (0, 1):
            model = fit_policy([dict(features=[0]*8, costs=[7, 9] if action == 0 else [9, 7])])
            for case in blind_pair():
                result = observe(sensor(case, 0), case.point, policy='learned', model=model)
                truth = case.energy.curvature(case.point)
                self.assertEqual(result['prediction'], 1 if truth > 0 else -1)
                self.assertEqual(result['blocks'], 7 if action == 0 else 9)

    def test_audit_results_roundtrip_as_json(self):
        from benchmarks.active_observer_audit import evaluate
        model = fit_policy([dict(features=[0]*8, costs=[7, 9])])
        result = evaluate(blind_pair(), model, Q(0))
        replay = json.loads(json.dumps(result, allow_nan=False))
        self.assertEqual(replay['summary']['learned']['correct'], 2)
        self.assertEqual(replay['summary']['learned']['mean_blocks'], '7')

    def test_unobserved_response_forecast_respects_taylor_bound(self):
        contract = Contract(noise=Q(1, 200000))
        for case in make_splits()['train'][:12]:
            result = observe(sensor(case, contract.noise), case.point, contract=contract)
            forecast = predict_hessian(result, (Q(1, 16), Q(-1, 16)), contract=contract)
            target = tuple(Q(x) for x in forecast['point'])
            self.assertNotIn(list(forecast['point']), [x['point'] for x in result['readings']])
            truth = case.energy.hessian(target)
            bound = Q(forecast['component_error_bound'])
            self.assertTrue(all(abs(Q(a)-b) <= bound for a, b in zip(forecast['estimate'], truth)))
            self.assertEqual(forecast['extra_acquisition_blocks'], 0)
        with self.assertRaises(ValueError):
            predict_hessian(result, (1, 1), contract=contract)
        with self.assertRaises(ValueError):
            predict_hessian(result, (0, 0), contract=Contract())

    def test_fourth_derivative_envelope_on_whole_declared_square(self):
        for cases in make_splits().values():
            for case in cases[::2]:
                for i in range(5):
                    for point in itertools.product((Q(-1, 2), Q(1, 2)), repeat=2):
                        self.assertLessEqual(abs(case.energy.derivative(point, (i, 4-i))), 5)


def interval_one():
    return Interval(Q(1), Q(1))


if __name__ == '__main__':
    unittest.main()
