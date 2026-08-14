import unittest

from darwin_board.board import SimulatedDarwinBoard
from darwin_board.controller import DarwinController
from darwin_board.resilience import avoids_component


class ResiliencePlannerTest(unittest.TestCase):
    def test_commissioning_prequalifies_escape_routes(self) -> None:
        board = SimulatedDarwinBoard(seed=7)
        controller = DarwinController(board, cutoff_hz=1_200.0)

        commissioned = controller.commission(budget=24)
        plan = controller.contingency_plan

        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.coverage, 1.0)
        self.assertEqual(controller.qualification_measurements, 6)
        self.assertLessEqual(plan.performance_tradeoff_db, 0.20)
        self.assertGreaterEqual(len(plan.fallbacks), 1)
        self.assertTrue(
            any(
                item.selection_method == "contingency qualification"
                for item in commissioned.evaluations
            )
        )
        for contingency in plan.contingencies:
            self.assertTrue(
                avoids_component(
                    contingency.fallback.configuration,
                    contingency.failed_component,
                )
            )

    def test_reflex_recovers_without_full_search(self) -> None:
        board = SimulatedDarwinBoard(seed=7)
        controller = DarwinController(board, cutoff_hz=1_200.0)
        commissioned = controller.commission(budget=24)
        active_capacitors = commissioned.best.configuration.active_capacitors(
            len(board.design.capacitor_farads)
        )
        failed = max(
            active_capacitors,
            key=lambda index: board.design.capacitor_farads[index],
        )
        board.inject_open_capacitor(failed)

        decision = controller.recover_resiliently(budget=24)

        self.assertEqual(decision.mode, "prequalified reflex")
        self.assertFalse(decision.full_search_used)
        self.assertGreater(decision.search_measurements_avoided, 0)
        self.assertLess(decision.result.best.response_error_db, 1.0)
        self.assertIsNone(controller.contingency_plan)

    def test_reflex_validates_error_limit(self) -> None:
        board = SimulatedDarwinBoard(seed=7)
        controller = DarwinController(board, cutoff_hz=1_200.0)
        controller.commission(budget=8)

        with self.assertRaises(ValueError):
            controller.recover_resiliently(maximum_error_db=0.0)


if __name__ == "__main__":
    unittest.main()
