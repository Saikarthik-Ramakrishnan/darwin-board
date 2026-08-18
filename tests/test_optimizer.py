import unittest

import numpy as np

from darwin_board.board import SimulatedDarwinBoard
from darwin_board.model import (
    frequency_grid,
    low_pass_response_db,
    target_response_db,
)
from darwin_board.optimizer import BayesianTuner


class BayesianTunerTest(unittest.TestCase):
    def test_regularized_ensemble_handles_repeated_observations(self) -> None:
        tuner = BayesianTuner()
        measured_x = np.array(
            [
                [0.2, 0.4, 0.0],
                [0.2, 0.4, 0.0],
                [0.8, 0.6, 0.1],
            ]
        )
        measured_y = np.array([0.12, 0.13, -0.04])
        candidate_x = np.array(
            [
                [0.2, 0.4, 0.0],
                [0.5, 0.5, 0.05],
                [0.9, 0.7, 0.1],
            ]
        )

        mean, uncertainty = tuner._predict(
            measured_x,
            measured_y,
            candidate_x,
        )

        self.assertTrue(np.all(np.isfinite(mean)))
        self.assertTrue(np.all(np.isfinite(uncertainty)))
        self.assertTrue(np.all(uncertainty > 0.0))

    def test_tuner_remains_close_to_oracle_across_tolerances(self) -> None:
        frequencies_hz = frequency_grid()
        regrets = []
        response_errors = []

        for target_hz in (700.0, 2_400.0):
            target = target_response_db(frequencies_hz, target_hz)
            for seed in (2, 7, 11):
                board = SimulatedDarwinBoard(
                    seed=seed,
                    measurement_noise_db=0.04,
                )
                tuner = BayesianTuner(seed=100 + seed)
                result = tuner.tune(
                    board,
                    frequencies_hz,
                    target_hz,
                    budget=24,
                )

                true_scores = {}
                true_errors = {}
                for configuration in board.design.configurations():
                    values = board.physical_values(configuration)
                    response = low_pass_response_db(
                        frequencies_hz,
                        values.resistance_ohms,
                        values.capacitance_farads,
                    )
                    error = float(
                        np.sqrt(np.mean((response - target) ** 2))
                    )
                    resistance, _ = board.design.nominal_values(configuration)
                    penalty = (
                        tuner.power_weight
                        * min(board.design.resistor_ohms)
                        / resistance
                    )
                    true_errors[configuration] = error
                    true_scores[configuration] = error + penalty

                selected = result.best.configuration
                response_errors.append(true_errors[selected])
                regrets.append(
                    true_scores[selected] - min(true_scores.values())
                )

        self.assertLess(max(response_errors), 0.20)
        self.assertLess(max(regrets), 0.10)

    def test_rejects_unsafe_hyperparameters(self) -> None:
        invalid_arguments = (
            {"length_scale": 0.0},
            {"exploration": -0.1},
            {"observation_noise": 0.0},
            {"topology_weight": -0.1},
            {"kernel_scale_factors": ()},
            {"kernel_scale_factors": (1.0, -0.5)},
        )
        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    BayesianTuner(**arguments)


if __name__ == "__main__":
    unittest.main()
