import tempfile
import unittest
from pathlib import Path

from darwin_board.board import SimulatedDarwinBoard
from darwin_board.controller import DarwinController
from darwin_board.memory import ExperienceMemory
from darwin_board.model import Configuration


class ExperienceMemoryTest(unittest.TestCase):
    def test_recommends_nearby_low_error_configurations(self) -> None:
        memory = ExperienceMemory()
        memory.record(
            cutoff_hz=1_000.0,
            configuration=Configuration(1, 3),
            response_error_db=0.20,
        )
        memory.record(
            cutoff_hz=2_000.0,
            configuration=Configuration(2, 7),
            response_error_db=0.10,
        )

        recommendations = memory.recommend(1_100.0)

        self.assertEqual(recommendations[0], Configuration(1, 3))

    def test_round_trips_json(self) -> None:
        memory = ExperienceMemory()
        memory.record(
            cutoff_hz=1_200.0,
            configuration=Configuration(0, 43),
            response_error_db=0.08,
            board_id="ESP32-TEST",
            temperature_c=29.5,
            supply_mv=3290,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memory.json"
            memory.save(path)
            restored = ExperienceMemory.load(path)

        self.assertEqual(restored.experiences, memory.experiences)

    def test_second_commissioning_uses_experience(self) -> None:
        memory = ExperienceMemory()
        first = DarwinController(
            SimulatedDarwinBoard(seed=7),
            cutoff_hz=1_200.0,
            memory=memory,
        )
        first.commission(budget=16)

        second = DarwinController(
            SimulatedDarwinBoard(seed=8),
            cutoff_hz=1_200.0,
            memory=memory,
        )
        result = second.commission(budget=16)

        self.assertEqual(
            result.evaluations[0].selection_method,
            "experience memory",
        )


if __name__ == "__main__":
    unittest.main()
