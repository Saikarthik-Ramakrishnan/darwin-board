import unittest

import numpy as np

from darwin_board.model import Configuration
from darwin_board.serial_board import SerialDarwinBoard


class FakeTransport:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.commands: list[str] = []
        self.closed = False

    def request(self, command: str) -> str:
        self.commands.append(command)
        return self.responses[command]

    def close(self) -> None:
        self.closed = True


class SerialDarwinBoardTest(unittest.TestCase):
    def test_identifies_configures_and_measures(self) -> None:
        transport = FakeTransport(
            {
                "ID?": "ID DARWIN_ESP32_1 FW=0.3.0",
                "SET R=2 C=0x15": "OK",
                "SWEEP 100 10000 3": "SWEEP_DB -0.01,-3.02,-20.04",
            }
        )
        board = SerialDarwinBoard(transport)

        response = board.measure_response_db(
            Configuration(2, 0x15),
            np.geomspace(100.0, 10_000.0, 3),
        )

        np.testing.assert_allclose(response, [-0.01, -3.02, -20.04])
        self.assertEqual(board.board_id, "DARWIN_ESP32_1")
        self.assertEqual(board.measurement_count, 1)

    def test_parses_status(self) -> None:
        transport = FakeTransport(
            {
                "ID?": "ID DARWIN_ESP32_1 FW=0.3.0",
                "STATUS?": (
                    "STATUS MODE=STEP_MODEL VCC_MV=3294 TEMP_C=31.5 "
                    "FC_HZ=1198.4 FIT_R2=0.9972"
                ),
            }
        )
        board = SerialDarwinBoard(transport)

        status = board.status()

        self.assertEqual(status.mode, "STEP_MODEL")
        self.assertEqual(status.supply_mv, 3294)
        self.assertAlmostEqual(status.temperature_c, 31.5)
        self.assertAlmostEqual(status.cutoff_hz, 1198.4)
        self.assertAlmostEqual(status.fit_r2, 0.9972)

    def test_rejects_non_geometric_sweep(self) -> None:
        transport = FakeTransport(
            {"ID?": "ID DARWIN_ESP32_1 FW=0.3.0"}
        )
        board = SerialDarwinBoard(transport)

        with self.assertRaises(ValueError):
            board.measure_response_db(
                Configuration(0, 1),
                np.array([100.0, 200.0, 500.0]),
            )

    def test_surfaces_firmware_error(self) -> None:
        transport = FakeTransport(
            {
                "ID?": "ID DARWIN_ESP32_1 FW=0.3.0",
                "SET R=0 C=0x01": "ERR SWITCH_BANK_OFFLINE",
            }
        )
        board = SerialDarwinBoard(transport)

        with self.assertRaisesRegex(RuntimeError, "SWITCH_BANK_OFFLINE"):
            board.measure_response_db(
                Configuration(0, 1),
                np.geomspace(100.0, 10_000.0, 3),
            )


if __name__ == "__main__":
    unittest.main()
