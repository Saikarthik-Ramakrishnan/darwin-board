import unittest

from darwin_board.board import SimulatedDarwinBoard
from darwin_board.controller import DarwinController


class DarwinBoardRecoveryTest(unittest.TestCase):
    def test_tunes_detects_fault_and_recovers(self) -> None:
        board = SimulatedDarwinBoard(seed=7)
        controller = DarwinController(board, cutoff_hz=1_200.0)

        commissioned = controller.commission(budget=24)
        self.assertLess(commissioned.best.response_error_db, 0.40)

        active = commissioned.best.configuration.active_capacitors(
            len(board.design.capacitor_farads)
        )
        failed_capacitor = max(
            active,
            key=lambda index: board.design.capacitor_farads[index],
        )
        board.inject_open_capacitor(failed_capacitor)

        health = controller.check_health()
        self.assertTrue(health.fault_detected)

        recovered = controller.recover(budget=24)
        self.assertLess(recovered.best.response_error_db, 0.50)
        self.assertNotEqual(
            recovered.best.configuration,
            commissioned.best.configuration,
        )

    def test_healthy_board_does_not_raise_false_alarm(self) -> None:
        board = SimulatedDarwinBoard(seed=11)
        controller = DarwinController(board, cutoff_hz=2_000.0)
        controller.commission(budget=20)

        health = controller.check_health()
        self.assertFalse(health.fault_detected)
        self.assertLess(health.signature_error_db, health.threshold_db)


if __name__ == "__main__":
    unittest.main()

