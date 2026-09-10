import unittest

import numpy as np

from darwin_board.board import SimulatedDarwinBoard
from darwin_board.evolution import EvolutionEngine
from darwin_board.model import MVPDesign, frequency_grid
from darwin_board.optimizer import BayesianTuner


class GenotypeCatalogTest(unittest.TestCase):
    def test_every_route_has_a_unique_round_trip_genotype(self) -> None:
        design = MVPDesign()
        configurations = design.configurations()
        genotypes = design.genotype_catalog()

        self.assertEqual(len(design.resistor_ohms), 8)
        self.assertEqual(len(design.capacitor_farads), 8)
        self.assertEqual(len(configurations), 2_040)
        self.assertEqual(len(set(genotypes)), len(configurations))
        self.assertTrue(all(code.startswith("R") for code in genotypes))
        for configuration, genotype in zip(configurations, genotypes):
            self.assertEqual(
                design.configuration_from_genotype(genotype),
                configuration,
            )

    def test_rejects_invalid_or_empty_genotypes(self) -> None:
        design = MVPDesign()
        for genotype in (
            "R000:C00000000",
            "R1000:C00000001",
            "R000:C000001",
            "R0:C1",
        ):
            with self.subTest(genotype=genotype):
                with self.assertRaises(ValueError):
                    design.configuration_from_genotype(genotype)


class EvolutionEngineTest(unittest.TestCase):
    def test_breeds_valid_unseen_children_and_keeps_immigrants(self) -> None:
        design = MVPDesign()
        configurations = design.configurations()
        measured = {
            configuration: float(index)
            for index, configuration in enumerate(configurations[:12])
        }
        unseen = set(configurations[12:])
        engine = EvolutionEngine(
            np.random.default_rng(7),
            offspring_pool_size=40,
            immigrant_fraction=0.20,
        )

        batch = engine.breed(
            measured_scores=measured,
            unseen=unseen,
            resistor_count=len(design.resistor_ohms),
            capacitor_count=len(design.capacitor_farads),
        )

        self.assertEqual(len(batch.candidates), 40)
        self.assertTrue(any(item.is_immigrant for item in batch.candidates))
        self.assertTrue(any(not item.is_immigrant for item in batch.candidates))
        self.assertEqual(
            len({item.configuration for item in batch.candidates}),
            len(batch.candidates),
        )
        for item in batch.candidates:
            self.assertIn(item.configuration, unseen)
            self.assertNotEqual(item.configuration.capacitor_mask, 0)

    def test_tuner_records_measured_generations(self) -> None:
        board = SimulatedDarwinBoard(seed=7)
        tuner = BayesianTuner(seed=19)

        result = tuner.tune(
            board,
            frequency_grid(),
            cutoff_hz=1_200.0,
            budget=24,
        )

        self.assertEqual(len(result.evaluations), 24)
        self.assertGreaterEqual(len(result.generations), 2)
        self.assertEqual(
            sum(len(item.offspring) for item in result.generations),
            24,
        )
        self.assertTrue(
            any(
                item.selection_method == "evolutionary offspring"
                for item in result.evaluations
            )
        )
        for generation in result.generations:
            self.assertLessEqual(len(generation.survivors), 8)
            self.assertGreaterEqual(generation.diversity, 0.0)
            self.assertLessEqual(generation.diversity, 1.0)


if __name__ == "__main__":
    unittest.main()
