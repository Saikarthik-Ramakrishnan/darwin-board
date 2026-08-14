import unittest

from darwin_board.benchmark import run_benchmark
from darwin_board.evidence import verify_payload


class BenchmarkTest(unittest.TestCase):
    def test_benchmark_aggregates_runs(self) -> None:
        result = run_benchmark(
            targets_hz=(1_200.0,),
            seeds=(7,),
            fault_kinds=("open_capacitor", "resistor_drift"),
            budget=18,
        )

        self.assertEqual(result["summary"]["runs"], 2)
        self.assertEqual(result["summary"]["fault_detection_rate"], 1.0)
        self.assertEqual(result["summary"]["recovery_success_rate"], 1.0)
        self.assertEqual(result["summary"]["reflex_recovery_rate"], 1.0)
        self.assertEqual(
            result["summary"]["minimum_contingency_coverage_percent"],
            100.0,
        )
        self.assertEqual(len(result["records"]), 2)
        self.assertTrue(verify_payload(result))


if __name__ == "__main__":
    unittest.main()
