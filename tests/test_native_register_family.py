"""The 2056 design as one point of a parametric register family."""
from fractions import Fraction
import unittest

from native_relational_qc import large_register
from native_relational_qc.exact import ONE, INV_SQRT2
from native_relational_qc.register_family import (
    DESIGN_2056, carrier_scaling, cost_laws, family_predictions, qualify_ghz, register_plan,
)


class PlanTests(unittest.TestCase):
    def test_design_2056_is_reproduced(self):
        plan = register_plan(**DESIGN_2056)
        self.assertEqual(plan['sites'], 2056)
        self.assertEqual(plan['data_sites'], 2048)
        self.assertEqual((plan['chain_edges'], plan['edges_within_banks'], plan['edges_between_banks'],
                          plan['edges_within_workspace'], plan['edges_data_to_workspace']), (2055, 1984, 63, 7, 1))

    def test_edges_always_sites_minus_one(self):
        for banks, width, workspace in ((1, 1, 0), (3, 5, 2), (128, 32, 8), (1000, 1000, 16)):
            plan = register_plan(banks, width, workspace)
            self.assertEqual(plan['chain_edges'], plan['sites'] - 1)

    def test_guards(self):
        with self.assertRaises(ValueError):
            register_plan(0, 32, 8)
        with self.assertRaises(ValueError):
            register_plan(1 << 21, 4, 0)
        with self.assertRaises(ValueError):
            register_plan(True, 1, 0)


class CostTests(unittest.TestCase):
    def test_tableau_bits_match_design_note(self):
        c = cost_laws(2056, chi_max=256)
        self.assertEqual(c['tableau_bits'], 16_912_656)
        self.assertEqual(c['mps_coefficient_bound'], 269_484_032)
        self.assertEqual(cost_laws(2056, chi_max=2)['mps_coefficient_bound'], 16_448)

    def test_costs_are_polynomial_in_sites(self):
        self.assertEqual(cost_laws(4112)['tableau_bits'], 2 * 4112 * (2 * 4112 + 1))
        self.assertEqual(cost_laws(1)['tableau_bits'], 6)


class CarrierTests(unittest.TestCase):
    def test_single_photon_path_is_exponential(self):
        c = carrier_scaling(4, 'single_photon_path')
        self.assertEqual((c['photons'], c['paths']), (1, 16))
        big = carrier_scaling(2056, 'single_photon_path')
        self.assertEqual(big['paths_log2'], 2056)
        self.assertIsNone(big['paths'])
        self.assertFalse(big['scalable'])

    def test_dual_rail_is_linear(self):
        c = carrier_scaling(2056, 'dual_rail')
        self.assertEqual((c['photons'], c['modes']), (2056, 4112))
        self.assertTrue(c['scalable'])

    def test_banked_path(self):
        c = carrier_scaling(2056, 'banked_path', bank_width=32)
        self.assertEqual((c['photons'], c['paths_per_bank']), (65, 1 << 32))
        self.assertFalse(c['scalable'])
        self.assertTrue(carrier_scaling(8, 'banked_path', bank_width=4)['scalable'])
        with self.assertRaises(ValueError):
            carrier_scaling(8, 'unknown')


class BoundTests(unittest.TestCase):
    def test_default_bound_is_2056_and_restorable(self):
        self.assertEqual(large_register.register_bound(), 2056)
        previous = large_register.declare_register_bound(5000)
        try:
            self.assertEqual(previous, 2056)
            self.assertEqual(large_register.LargeCircuit(5000).n_qubits, 5000)
            with self.assertRaises(ValueError):
                large_register.LargeCircuit(5001)
        finally:
            large_register.declare_register_bound(previous)
        with self.assertRaises(ValueError):
            large_register.LargeCircuit(2057)
        with self.assertRaises(ValueError):
            large_register.declare_register_bound(large_register.REGISTER_BOUND_CEILING + 1)

    def test_predictions(self):
        p = family_predictions(777)
        self.assertEqual(p['A']['all_x_expectation'], ONE)
        self.assertEqual(p['B']['all_x_expectation'], INV_SQRT2)

    def test_families_pass_beyond_2056(self):
        for n in (1, 2, 2056, 4112):
            r = qualify_ghz(n)
            self.assertTrue(r['family_a_passed'], n)
            self.assertTrue(r['family_b_passed'], n)
        self.assertEqual(large_register.register_bound(), 2056)


if __name__ == '__main__':
    unittest.main()
