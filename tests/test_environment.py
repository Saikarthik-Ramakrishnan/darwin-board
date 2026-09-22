import unittest

import numpy as np

from darwin_board.environment import EnvironmentalTwin, OperatingPoint, TwinProfile
from darwin_board.model import Configuration, MVPDesign, low_pass_response_db


class EnvironmentalTwinTests(unittest.TestCase):
    def setUp(self):
        self.design = MVPDesign(resistor_ohms=(1000.0, 2000.0), capacitor_farads=(1e-8, 2e-8))
        self.profile = TwinProfile((1, 1), (1, 1), (0, 0), (0, 0), (0, 0),
                                   switch_ohms=0, branch_esr_ohms=0, parasitic_farads=0, leakage_ohms=1e30)
        self.frequencies = np.geomspace(10, 100_000, 51)

    def test_ideal_limit_matches_existing_analytic_model(self):
        board = EnvironmentalTwin(self.design, profile=self.profile, point=OperatingPoint(load_ohms=1e30))
        config = Configuration(0, 3)
        expected = low_pass_response_db(self.frequencies, 1000, 3e-8)
        np.testing.assert_allclose(board.response_db(config, self.frequencies), expected, atol=1e-12)

    def test_loaded_response_matches_closed_form(self):
        board = EnvironmentalTwin(self.design, profile=self.profile, point=OperatingPoint(load_ohms=4000))
        expected = 20 * np.log10(np.abs(1 / (1 + 1000 / 4000 + 2j * np.pi * self.frequencies * 1000 * 1e-8)))
        np.testing.assert_allclose(board.response_db(Configuration(0, 1), self.frequencies), expected, atol=1e-12)

    def test_compound_faults_obey_network_equations(self):
        board = EnvironmentalTwin(self.design, profile=self.profile,
            point=OperatingPoint(load_ohms=1e30, open_capacitors=(0,), resistor_scales=((0, 2),)))
        expected = low_pass_response_db(self.frequencies, 2000, 2e-8)
        np.testing.assert_allclose(board.response_db(Configuration(0, 3), self.frequencies), expected, atol=1e-12)
        # A route that avoids both damaged components is unchanged.
        healthy = EnvironmentalTwin(self.design, profile=self.profile, point=OperatingPoint(load_ohms=1e30))
        np.testing.assert_allclose(board.response_db(Configuration(1, 2), self.frequencies),
                                   healthy.response_db(Configuration(1, 2), self.frequencies))

    def test_noise_is_reproducible_and_counted_separately(self):
        a, b = EnvironmentalTwin(seed=13), EnvironmentalTwin(seed=13)
        config = Configuration(2, 17)
        truth = a.response_db(config, self.frequencies)
        self.assertEqual(a.measurement_count, 0)
        np.testing.assert_array_equal(a.measure_response_db(config, self.frequencies), b.measure_response_db(config, self.frequencies))
        self.assertEqual(a.measurement_count, 1)
        self.assertFalse(np.array_equal(truth, a.measure_response_db(config, self.frequencies)))

    def test_inputs_reject_nonphysical_values(self):
        for kwargs in ({"load_ohms":0}, {"temperature_c":float("nan")}, {"age":2},
                       {"resistor_scales":((0, float("inf")),)}, {"open_capacitors":(0, 0)}):
            with self.assertRaises(ValueError):
                OperatingPoint(**kwargs)
        with self.assertRaises(ValueError):
            EnvironmentalTwin(self.design, point=OperatingPoint(open_capacitors=(2,)))
        with self.assertRaises(ValueError):
            EnvironmentalTwin().response_db(Configuration(0, 1), np.array([0, 10]))


if __name__ == "__main__":
    unittest.main()
