import unittest

from darwin_board.visualizer_server import build_session


class VisualizerSessionTest(unittest.TestCase):
    def test_session_contains_tuning_fault_and_recovery(self) -> None:
        session = build_session(cutoff_hz=1_200.0, budget=24, seed=7)

        self.assertEqual(len(session["frequency_hz"]), 32)
        self.assertEqual(len(session["target_response_db"]), 32)
        self.assertEqual(
            len(session["stages"]["commissioned"]["response_db"]),
            32,
        )
        self.assertTrue(session["stages"]["fault"]["detected"])
        self.assertEqual(session["schema_version"], "0.2")
        self.assertEqual(session["stages"]["fault"]["health_sweeps"], 3)
        self.assertGreater(session["stages"]["fault"]["signature_ratio"], 1.0)
        self.assertGreater(
            session["stages"]["fault"]["response_error_db"],
            session["stages"]["commissioned"]["response_error_db"],
        )
        self.assertLess(
            session["stages"]["recovered"]["response_error_db"],
            1.0,
        )
        self.assertEqual(len(session["search"]["commissioned"]), 24)
        self.assertEqual(len(session["search"]["recovered"]), 24)

    def test_session_validates_controls(self) -> None:
        with self.assertRaises(ValueError):
            build_session(cutoff_hz=50.0)
        with self.assertRaises(ValueError):
            build_session(budget=3)
        with self.assertRaises(ValueError):
            build_session(fault_kind="unknown")
        with self.assertRaises(ValueError):
            build_session(health_sweeps=0)

    def test_session_supports_multiple_fault_scenarios(self) -> None:
        for fault_kind in (
            "open_capacitor",
            "capacitor_drift",
            "resistor_drift",
        ):
            with self.subTest(fault_kind=fault_kind):
                session = build_session(
                    cutoff_hz=1_200.0,
                    budget=24,
                    seed=7,
                    fault_kind=fault_kind,
                )
                fault = session["stages"]["fault"]
                self.assertEqual(fault["kind"], fault_kind)
                self.assertTrue(fault["detected"])
                self.assertGreater(fault["signature_ratio"], 1.0)
                self.assertLess(
                    session["stages"]["recovered"]["response_error_db"],
                    1.0,
                )


if __name__ == "__main__":
    unittest.main()
