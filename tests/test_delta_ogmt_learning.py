"""Unseen-input isolation, circuit semantics, and finite-readout certification."""
from collections import Counter
from copy import deepcopy
from fractions import Fraction
import contextlib
import importlib.util
import io
import json
from math import comb
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from native_relational_qc.calculator import calculate
from native_relational_qc import delta_ogmt as original
from native_relational_qc import delta_ogmt_learning as learning
from benchmarks import delta_ogmt_learning_audit as campaign


def row(history, target):
    return dict(history=history, target=target, group=learning.group_key(history))


class LearningTests(unittest.TestCase):
    def test_split_is_balanced_and_keeps_related_sequences_together(self):
        splits = learning.make_splits()
        self.assertEqual({k: len(v) for k, v in splits.items()},
                         dict(train=32, validation=32, test=64, reserve=124))
        seen_histories, seen_groups = set(), set()
        for name, rows in splits.items():
            with self.subTest(split=name):
                self.assertEqual(Counter(r['target'] for r in rows), {0: len(rows)//2, 1: len(rows)//2})
                groups = {r['group'] for r in rows}
                self.assertFalse(groups & seen_groups)
                seen_groups |= groups
                for r in rows:
                    h = r['history']
                    self.assertNotIn(h, seen_histories)
                    seen_histories.add(h)
                    self.assertEqual(Counter(h), {'A': 6, 'B': 6})
                    self.assertEqual((h[0], h[-1]), ('A', 'B'))
                    self.assertEqual(r['target'], int(sum(a != b for a, b in zip(h, h[1:])) >= 7))
                    self.assertEqual(r['group'], learning.group_key(h[::-1].translate(str.maketrans('AB', 'BA'))))
        self.assertEqual(len(seen_histories), 252)
        self.assertEqual(json.loads(campaign.PROTOCOL_PATH.read_text()), campaign.protocol())

    def test_default_four_event_circuit_preserves_original_model(self):
        for mode in learning.MODES:
            with self.subTest(mode=mode):
                current, _ = learning.build_request('AABB', mode, learning.Parameters())
                self.assertEqual(current['operations'], original.build_request('AABB', mode)[0]['operations'])
        for kwargs in (dict(outer_scale=3), dict(memory_scale=True), dict(readout_A=0),
                       dict(observer_step=16), dict(observer_step=2.0)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                learning.Parameters(**kwargs)

    def test_native_proposals_match_exact_replay_for_different_couplings_and_observers(self):
        evaluator = learning.ProposalEvaluator()
        # Six-event fixtures, outside the twelve-event learning/test family.
        for mode in learning.MODES:
            for params in (learning.Parameters(1, 2, 4, 2, 3), learning.Parameters(4, 4, 8, 1, 11)):
                for history in ('AABBAB', 'ABABAB'):
                    with self.subTest(mode=mode, params=params, history=history):
                        request, _ = learning.build_request(history, mode, params)
                        result = calculate(request)
                        self.assertEqual(result['status'], 'completed')
                        expected = float(result['answers'][0]['probabilities']['1']['decimal'])
                        actual = evaluator.probabilities([history], mode, params)[0]
                        self.assertAlmostEqual(actual, expected, delta=2e-10)

    @unittest.skipUnless(importlib.util.find_spec('qiskit'), 'optional Qiskit reference')
    def test_independent_statevector_checks_tuned_gate_encoding(self):
        for mode in ('M1', 'M3', 'E_CA'):
            with self.subTest(mode=mode):
                request, encoding = learning.build_request('ABABAB', mode, learning.Parameters(2, 4, 1, 8, 7))
                check = original.compare_qiskit(request, encoding, calculate(request))
                self.assertTrue(check['passed'], check)

    def test_binomial_arithmetic_matches_direct_rational_sum_including_endpoints(self):
        for p in (Fraction(0), Fraction(1, 7), Fraction(1, 2), Fraction(6, 7), Fraction(1)):
            for n in (1, 3, 8):
                for cutoff in range(n + 2):
                    direct = sum(Fraction(comb(n, k)) * p**k * (1-p)**(n-k) for k in range(cutoff, n+1))
                    self.assertEqual(learning.binomial_tail(p, n, cutoff), direct)
        display = dict(decimal_enclosure=dict(lower='0.25', upper='0.50'))
        for orientation in (1, -1):
            model = learning.freeze_model('M3', learning.Parameters(), orientation, 2, [], [], shots=3)
            for target in (0, 1):
                lo, hi = learning.success_bounds(display, target, model)
                correct = (Fraction(5, 32), Fraction(1, 2))
                if (orientation == -1) != (target == 0):
                    correct = (1-correct[1], 1-correct[0])
                self.assertEqual((lo, hi), correct)
                rounded = learning.rounded_bounds(lo, hi, places=4)
                self.assertLessEqual(Fraction(rounded['lower']), lo)
                self.assertGreaterEqual(Fraction(rounded['upper']), hi)
        negative = learning.rounded_bounds(Fraction(-1, 3), Fraction(-1, 7), places=4)
        self.assertEqual((negative['lower'], negative['upper']), ('-0.3334', '-0.1428'))

    def test_finite_readouts_cannot_treat_tiny_probability_gap_as_perfect_classification(self):
        indistinguishable = learning.decision_scores([0.2, 0.2], [0, 1])
        np.testing.assert_allclose(indistinguishable, 0.5, atol=1e-14)
        self.assertEqual(learning.decision_scores([0, 1], [0, 1]).max(), 1)
        scores = learning.decision_scores([0.5, 0.501], [0, 1])
        self.assertGreater(scores.max(), 0.5)
        self.assertLess(scores.max(), 0.51)
        model = learning.freeze_model('M3', learning.Parameters(), 1, 32, [], [])
        for index, target in enumerate((0, 1)):
            p = ('0.5', '0.501')[index]
            bounds = learning.success_bounds(dict(decimal_enclosure=dict(lower=p, upper=p)), target, model)
            self.assertEqual(bounds[0], bounds[1])
        exact = (1-learning.binomial_tail(Fraction(1, 2), 64, 32) + learning.binomial_tail(Fraction(501, 1000), 64, 32))/2
        self.assertAlmostEqual(scores[0, 0, 32], float(exact), places=13)

    def test_search_uses_only_supplied_training_validation_and_rejects_group_overlap(self):
        train = [row('AAAAAB', 0), row('ABABAB', 1)]
        validation = [row('AAABBB', 0), row('ABBABB', 1)]
        result = learning.fit(train, validation, 'M1')
        self.assertEqual(set(result['histories_evaluated']), {r['history'] for r in train + validation})
        self.assertEqual(len(result['candidates']), 1152)
        self.assertEqual(len(result['shortlist']), 4)
        self.assertEqual(len({(r['parameters']['outer_scale'], r['parameters']['memory_scale']) for r in result['shortlist']}), 4)
        learning.check_frozen(result['model'])
        bad = deepcopy(result['model'])
        bad['cutoff'] += 1
        with self.assertRaises(ValueError):
            learning.check_frozen(bad)
        with self.assertRaises(ValueError):
            learning.fit(train, [row('ABBBBB', 0), row('AAABBB', 1)], 'M1')

    def test_paired_bootstrap_retains_sign_and_exactly_zero_control(self):
        left = [dict(row(h, target), expected_correct_midpoint=0.7)
                for h, target in [('AAAAAB', 0), ('AAABBB', 0), ('ABABAB', 1), ('ABBABB', 1)]]
        right = [dict(r, expected_correct_midpoint=0.5) for r in left]
        same = campaign.grouped_bootstrap(left, left, repeats=20)
        self.assertEqual((same['lower'], same['upper']), (0, 0))
        better = campaign.grouped_bootstrap(left, right, repeats=20)
        self.assertAlmostEqual(better['lower'], 0.2)
        self.assertAlmostEqual(better['upper'], 0.2)

    def test_failed_exact_replay_is_retained_as_incomplete_not_a_success(self):
        train = [row('AAAAAB', 0), row('ABABAB', 1)]
        validation = [row('AAABBB', 0), row('ABBABB', 1)]
        plan = campaign.protocol()
        plan['dataset'] = dict(train=train, validation=validation,
                               test=[row('AABBAB', 0), row('ABAAAB', 1)], reserve=[])
        def fixed_fit(training, val, mode):
            return dict(model=learning.freeze_model(mode, learning.Parameters(), 1, 32, training, val),
                        selected_training_score=0.5, selected_validation_score=0.5,
                        histories_evaluated=[r['history'] for r in training + val], native_gate_applications=0)
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            path = Path(tmp) / 'audit'
            protocol_path = Path(tmp) / 'plan.json'
            campaign.write_json(protocol_path, plan)
            with patch.object(campaign, 'PROTOCOL_PATH', protocol_path), patch.object(campaign, 'protocol', return_value=plan), \
                 patch.object(campaign, 'fit', side_effect=fixed_fit), \
                 patch.object(campaign, 'run_calculation', return_value=dict(status='time_limit')):
                with self.assertRaisesRegex(RuntimeError, 'did not complete'):
                    campaign.audit(path, 'a'*40, workers=1)
            self.assertEqual(json.loads((path/'status.json').read_text())['status'], 'incomplete')
            self.assertTrue((path/'frozen_models.json').is_file())
            self.assertFalse((path/'summary.json').exists())
            self.assertTrue(list((path/'results').glob('*.json')))


if __name__ == '__main__':
    unittest.main()
