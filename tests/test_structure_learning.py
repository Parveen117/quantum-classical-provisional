import copy
import json
import math
import random
import subprocess
import sys
import unittest
from unittest.mock import patch

import numpy as np

from native_relational_qc.circuit import Circuit
from native_relational_qc.compact import ResourceLimit
from native_relational_qc.learning_tasks import curvature_splits, xor_examples
from native_relational_qc.phase_backend import PowerPhaseCircuit, prepare
from native_relational_qc.self_learning import (
    DEFAULT_ENTANGLERS, FIELD, Evaluator, _ry, assess, circuit, digest,
    fit, load_packet, packet,
)
from native_relational_qc.structure_learning import canonical_readout_model, fit_structure, topology_candidates


class PhaseAndTopologyTests(unittest.TestCase):
    def test_phase_fusion_keeps_both_exact_matrix_columns_at_wrap_boundaries(self):
        for a in range(64):
            for b in (0, 1, 32, 63):
                for column in (0, 1):
                    source = PowerPhaseCircuit(1, 64)
                    result = PowerPhaseCircuit(1, 64)
                    if column:
                        source.add("x", 0)
                        result.add("x", 0)
                    _ry(source, 0, a)
                    _ry(source, 0, b)
                    _ry(result, 0, (a + b) % 64)
                    self.assertEqual(prepare(source).amplitudes, prepare(result).amplitudes,
                                     (a, b, column))

    def test_fused_nonclifford_topologies_match_raw_and_independent_numpy(self):
        rng = random.Random(1211)
        for candidate in topology_candidates():
            edges = candidate["entanglers"]
            for _ in range(3):
                features = tuple(rng.randrange(64) for _ in range(2))
                params = tuple(rng.randrange(64) for _ in range(5))
                raw = circuit(features, params, entanglers=edges)
                fused = circuit(features, params, entanglers=edges, compiler="fused")
                self.assertEqual(prepare(raw).amplitudes, prepare(fused).amplitudes)
                reference = Circuit(4)
                for q, step in enumerate(features):
                    reference.add("ry", q, theta=step * math.pi / 32)
                for q, step in enumerate(params[:4]):
                    reference.add("ry", q, theta=step * math.pi / 32)
                for a, b in edges:
                    reference.add("cx", a, b)
                reference.add("ry", 3, theta=params[4] * math.pi / 32)
                probability = sum(abs(v) ** 2 for k, v in enumerate(reference.state().amplitudes)
                                  if k & 8)
                exact = Evaluator(entanglers=edges, compiler="fused").probability(features, params)
                self.assertAlmostEqual(complex(exact).real, probability, places=12)
        odd_phase = circuit((5, 17), (3, 41, 22, 9, 50), compiler="fused")
        self.assertTrue(any(name == "p64" for name, _ in odd_phase.operations))

    def test_legacy_and_topology_checkpoints_keep_their_own_configuration(self):
        old = packet((0,) * 5, training_digest="a" * 64, view="xor_bits")
        self.assertEqual(old["schema"], "native-learning-model-v1")
        self.assertNotIn("entanglers", old)
        new = packet((0,) * 5, training_digest="a" * 64, view="xor_bits",
                     entanglers=((0, 3), (1, 3)))
        self.assertEqual(load_packet(new), (0,) * 5)
        self.assertEqual(assess(new, xor_examples())["accuracy"], "1")
        with self.assertRaises(ValueError):
            assess(new, xor_examples(), evaluator=Evaluator())
        corrupted = copy.deepcopy(new)
        corrupted["entanglers"][0] = [1, 2]
        with self.assertRaises(ValueError):
            load_packet(corrupted)
        broken = copy.deepcopy(new)
        del broken["entanglers"]
        with self.assertRaises(ValueError):
            load_packet(broken)

    def test_configuration_is_fixed_for_each_prediction_cache(self):
        evaluator = Evaluator(compiler="fused", entanglers=((0, 3), (1, 3)))
        for name, value in (("compiler", "raw"), ("entanglers", DEFAULT_ENTANGLERS)):
            with self.assertRaises(AttributeError):
                setattr(evaluator, name, value)
        a = evaluator.probability((32, 0), (0,) * 5)
        b = Evaluator(entanglers=()).probability((32, 0), (0,) * 5)
        self.assertEqual((a, b), (FIELD(1), FIELD(0)))
        for kwargs in (dict(compiler="guess"), dict(entanglers=((0, 0),)),
                       dict(entanglers=((True, 3),)), dict(entanglers=((0, 3), (0, 3)))):
            with self.assertRaises(ValueError):
                Evaluator(**kwargs)


    def test_unobserved_phase_is_zeroed_with_its_readout_scope_retained(self):
        params = (3, 41, 40, 9, 50)
        source = packet(params, training_digest="a" * 64, view="first_layer",
                        entanglers=((0, 3), (1, 3)))
        original = copy.deepcopy(source)
        normalized, trace = canonical_readout_model(source)
        self.assertEqual(source, original)
        self.assertEqual(load_packet(normalized), (3, 41, 0, 9, 50))
        self.assertEqual(trace["zeroed_phase_coordinates"], [2])
        a = Evaluator(entanglers=source["entanglers"], compiler="fused")
        b = Evaluator(entanglers=source["entanglers"], compiler="fused")
        for features in ((5, 17), (0, 63), (32, 32), (63, 1)):
            self.assertEqual(a.probability(features, params), b.probability(features, load_packet(normalized)))
        self.assertLess(b.stats["total_executed_gates"], a.stats["total_executed_gates"])


class StructureSearchTests(unittest.TestCase):
    def test_candidate_family_uses_exact_ordered_readout_conditions(self):
        candidates = topology_candidates()
        edges = [tuple(map(tuple, c["entanglers"])) for c in candidates]
        self.assertEqual(len(candidates), 5)
        self.assertIn(DEFAULT_ENTANGLERS, edges)
        self.assertIn(((0, 3), (1, 3)), edges)
        self.assertTrue(all(c["input_support_mask"] & 3 == 3 for c in candidates))
        with self.assertRaises(ValueError):
            topology_candidates(((2, 3), (0, 2), (1, 2)))
        with self.assertRaises(ResourceLimit):
            topology_candidates(max_candidates=1)

    def fake_fit(self, examples, *, view, evaluator, seeds, sweeps):
        self.calls.append(dict(ids=[e.name for e in examples], edges=evaluator.entanglers,
                               seeds=tuple(seeds), sweeps=sweeps,
                               circuits_left=evaluator.max_circuits))
        evaluator.stats["circuit_executions"] = 1
        evaluator.stats["engine_work"] = 7
        evaluator.stats["peak_support"] = 2
        loss = FIELD(1) / 4 if evaluator.entanglers == self.worse else FIELD(0)
        return dict(model=packet((0,) * 5, training_digest=digest([e.record() for e in examples]),
                                 view=view, entanglers=evaluator.entanglers),
                    loss=dict(exact=loss.to_dict()))

    def test_selection_has_training_only_inputs_and_prefers_smaller_equal_loss(self):
        splits, _ = curvature_splits()
        self.calls, self.worse = [], None
        with patch("native_relational_qc.structure_learning.fit", side_effect=self.fake_fit):
            result = fit_structure(splits["train"], view="first_layer", seeds=(17,), sweeps=1)
        self.assertEqual(result["model"]["entanglers"], [[0, 3], [1, 3]])
        self.assertEqual(result["resources"]["circuit_executions"], 5)
        self.assertEqual(result["resources"]["engine_work"], 35)
        self.assertEqual(result["resources"]["peak_support"], 2)
        self.assertEqual([c["circuits_left"] for c in self.calls], list(range(60000, 59995, -1)))
        for c in self.calls:
            self.assertEqual(c["ids"], [e.name for e in splits["train"]])
            self.assertEqual((c["seeds"], c["sweeps"]), ((17,), 1))

    def test_loss_priority_prevents_accepting_a_cheaper_worse_model(self):
        self.calls, self.worse = [], ((0, 3), (1, 3))
        with patch("native_relational_qc.structure_learning.fit", side_effect=self.fake_fit):
            result = fit_structure(xor_examples(), view="xor_bits", seeds=(17,), sweeps=1)
        self.assertEqual(result["model"]["schema"], "native-learning-model-v1")
        self.assertEqual(result["selected_candidate"], result["baseline_candidate"])

    def test_search_budget_applies_across_topologies_and_returns_no_partial_model(self):
        self.calls, self.worse = [], None
        with patch("native_relational_qc.structure_learning.fit", side_effect=self.fake_fit):
            with self.assertRaises(ResourceLimit):
                fit_structure(xor_examples(), view="xor_bits", max_circuits=2)
        self.assertEqual(len(self.calls), 2)
        with self.assertRaises(ResourceLimit):
            fit_structure(xor_examples(), view="xor_bits", max_work=1, seeds=(17,), sweeps=1)

    def test_real_phase_fit_and_assessment_roundtrip_the_selected_topology(self):
        evaluator = Evaluator(compiler="fused", entanglers=((0, 3), (1, 3)))
        result = fit(xor_examples(), view="xor_bits", evaluator=evaluator,
                     seeds=(17,), sweeps=1, initial_parameters=(0,) * 5)
        self.assertEqual(result["model"]["entanglers"], [[0, 3], [1, 3]])
        self.assertEqual(assess(result["model"], xor_examples())["accuracy"], "1")

    def test_normal_cli_entrypoint_reports_whole_search_budget_failure(self):
        process = subprocess.run([sys.executable, "-m", "native_relational_qc", "learn-structure",
                                  "--task", "xor", "--max-work", "1"],
                                 text=True, capture_output=True)
        self.assertEqual(process.returncode, 1, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report["status"], "incomplete")
        self.assertNotIn("model", report)


if __name__ == "__main__":
    unittest.main()
