import importlib.util
from types import SimpleNamespace
import unittest

from native_relational_qc.grover_cloud import TARGETS, ideal, metadata, prepare, summarize


def sample(target, counts):
    register = SimpleNamespace(get_counts=lambda: counts)
    return SimpleNamespace(metadata={"circuit_metadata": metadata(target, 32)},
                           data=SimpleNamespace(c=register))


class GroverCloudTests(unittest.TestCase):
    def test_ideal_truth_table(self):
        result = ideal()
        self.assertIsNone(result["hardware_job_id"])
        for target, outcomes in result["probabilities"].items():
            for label in TARGETS:
                self.assertAlmostEqual(outcomes[label], float(label == target))

    def test_parity_constraints(self):
        for syndrome, outcomes in ideal(parity=True)["probabilities"].items():
            for bits, probability in outcomes.items():
                high, low = map(int, bits)
                consistent = f"{high ^ low}{low}" == syndrome
                self.assertAlmostEqual(probability, float(consistent))

    def test_noisy_counts_and_wrong_evidence(self):
        pubs = [sample(t, {"00": 16, "11": 16}) for t in TARGETS]
        rows = summarize(pubs)
        self.assertEqual(rows["00"]["target_frequency"], 0.5)
        self.assertFalse(any(row["unique_mode_is_target"] for row in rows.values()))
        with self.assertRaises(ValueError):
            summarize(pubs[::-1])
        for counts in ({"01": 31}, {"001": 32}, {"00": -1, "01": 33}):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                summarize([sample("00", counts), *pubs[1:]])

    @unittest.skipUnless(importlib.util.find_spec("qiskit"), "optional Qiskit adapter")
    def test_compiled_circuits_and_sampler_register_order(self):
        from qiskit.primitives import StatevectorSampler
        from qiskit.providers.fake_provider import GenericBackendV2

        backend = GenericBackendV2(3, seed=117)
        for parity in (False, True):
            circuits = prepare(backend, 32, parity)
            pubs = StatevectorSampler(seed=117).run(circuits, shots=32).result()
            rows = summarize(pubs, parity)
            for target, row in rows.items():
                self.assertEqual(row["counts"], {row["solution"]: 32})
                self.assertTrue(row["unique_mode_is_target"])
            if parity:
                self.assertEqual(rows["01"]["counts"], {"11": 32})
                with self.assertRaises(ValueError):
                    summarize(pubs, parity=False)

    @unittest.skipUnless(importlib.util.find_spec("qiskit_ibm_runtime"), "optional IBM SDK")
    def test_runtime_local_sampler_counts(self):
        from qiskit.providers.fake_provider import GenericBackendV2
        from qiskit_ibm_runtime import SamplerV2

        backend = GenericBackendV2(3, seed=117)
        job = SamplerV2(mode=backend).run(prepare(backend, 32), shots=32)
        for row in summarize(job.result()).values():
            self.assertEqual(sum(row["counts"].values()), 32)
