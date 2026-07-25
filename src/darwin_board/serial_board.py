from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .model import Configuration, MVPDesign


class LineTransport(Protocol):
    def request(self, command: str) -> str:
        ...

    def close(self) -> None:
        ...


class PySerialTransport:
    def __init__(
        self,
        port: str,
        *,
        baudrate: int = 115_200,
        timeout: float = 4.0,
    ) -> None:
        try:
            import serial
        except ImportError as error:
            raise RuntimeError(
                "Install hardware support with: pip install -e '.[hardware]'"
            ) from error
        self._serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            write_timeout=timeout,
        )

    def request(self, command: str) -> str:
        self._serial.reset_input_buffer()
        self._serial.write((command.strip() + "\n").encode("ascii"))
        self._serial.flush()
        response = self._serial.readline()
        if not response:
            raise TimeoutError(f"ESP32 did not answer: {command}")
        return response.decode("ascii", errors="strict").strip()

    def close(self) -> None:
        self._serial.close()


@dataclass(frozen=True)
class BoardStatus:
    mode: str
    supply_mv: int | None
    temperature_c: float | None
    cutoff_hz: float | None
    fit_r2: float | None


class SerialDarwinBoard:
    """DarwinBoard adapter for the ESP32 line protocol."""

    def __init__(
        self,
        transport: LineTransport,
        design: MVPDesign | None = None,
        *,
        verify_identity: bool = True,
    ) -> None:
        self.transport = transport
        self.design = design or MVPDesign()
        self.measurement_count = 0
        self.board_id = "unknown"
        if verify_identity:
            self.board_id = self.identify()

    def identify(self) -> str:
        response = self._request("ID?")
        if not response.startswith("ID "):
            raise RuntimeError(f"Unexpected identity response: {response}")
        identity = response.removeprefix("ID ").split()[0]
        if not identity.startswith("DARWIN_"):
            raise RuntimeError(f"Unsupported board identity: {identity}")
        return identity

    def status(self) -> BoardStatus:
        response = self._request("STATUS?")
        if not response.startswith("STATUS "):
            raise RuntimeError(f"Unexpected status response: {response}")
        values = _parse_key_values(response.removeprefix("STATUS "))
        return BoardStatus(
            mode=values.get("MODE", "UNKNOWN"),
            supply_mv=_optional_int(values.get("VCC_MV")),
            temperature_c=_optional_float(values.get("TEMP_C")),
            cutoff_hz=_optional_float(values.get("FC_HZ")),
            fit_r2=_optional_float(values.get("FIT_R2")),
        )

    def measure_response_db(
        self,
        configuration: Configuration,
        frequencies_hz: np.ndarray,
    ) -> np.ndarray:
        frequencies = np.asarray(frequencies_hz, dtype=float)
        if frequencies.ndim != 1 or len(frequencies) < 2:
            raise ValueError("A sweep requires at least two frequencies")
        if not np.all(np.isfinite(frequencies)) or np.any(frequencies <= 0.0):
            raise ValueError("Sweep frequencies must be finite and positive")
        expected = np.geomspace(
            frequencies[0],
            frequencies[-1],
            len(frequencies),
        )
        if not np.allclose(frequencies, expected, rtol=1.0e-6, atol=1.0e-9):
            raise ValueError("ESP32 sweeps require a geometric frequency grid")

        mask_limit = 1 << len(self.design.capacitor_farads)
        if not 0 <= configuration.resistor_index < len(
            self.design.resistor_ohms
        ):
            raise ValueError("Unknown resistor index")
        if not 1 <= configuration.capacitor_mask < mask_limit:
            raise ValueError("Capacitor mask must select at least one branch")

        set_response = self._request(
            f"SET R={configuration.resistor_index} "
            f"C=0x{configuration.capacitor_mask:02X}"
        )
        if set_response != "OK":
            raise RuntimeError(f"Configuration was rejected: {set_response}")

        sweep_response = self._request(
            "SWEEP "
            f"{frequencies[0]:.9g} "
            f"{frequencies[-1]:.9g} "
            f"{len(frequencies)}"
        )
        if not sweep_response.startswith("SWEEP_DB "):
            raise RuntimeError(f"Unexpected sweep response: {sweep_response}")
        values_text = sweep_response.removeprefix("SWEEP_DB ")
        try:
            response = np.array(
                [float(value) for value in values_text.split(",")],
                dtype=float,
            )
        except ValueError as error:
            raise RuntimeError("ESP32 returned a malformed sweep") from error
        if len(response) != len(frequencies):
            raise RuntimeError(
                f"ESP32 returned {len(response)} points; "
                f"expected {len(frequencies)}"
            )
        if not np.all(np.isfinite(response)):
            raise RuntimeError("ESP32 returned non-finite measurements")
        self.measurement_count += 1
        return response

    def close(self) -> None:
        self.transport.close()

    def _request(self, command: str) -> str:
        response = self.transport.request(command).strip()
        if response.startswith("ERR"):
            raise RuntimeError(response)
        return response


def _parse_key_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in text.split():
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        values[key] = value
    return values


def _optional_float(value: str | None) -> float | None:
    return float(value) if value is not None else None


def _optional_int(value: str | None) -> int | None:
    return int(value) if value is not None else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe a Darwin Board ESP32 over USB serial"
    )
    parser.add_argument("port", help="Serial port such as /dev/cu.usbserial-0001")
    parser.add_argument("--baudrate", type=int, default=115_200)
    arguments = parser.parse_args()

    transport = PySerialTransport(
        arguments.port,
        baudrate=arguments.baudrate,
    )
    try:
        board = SerialDarwinBoard(transport)
        status = board.status()
        print(f"Board: {board.board_id}")
        print(f"Mode: {status.mode}")
        print(
            "Supply: "
            f"{status.supply_mv} mV"
            if status.supply_mv is not None
            else "Supply: unavailable"
        )
        print(
            "Last cutoff: "
            f"{status.cutoff_hz:.1f} Hz"
            if status.cutoff_hz is not None
            else "Last cutoff: unavailable"
        )
        print(
            "Transient fit: "
            f"R² {status.fit_r2:.4f}"
            if status.fit_r2 is not None
            else "Transient fit: unavailable"
        )
    finally:
        transport.close()


if __name__ == "__main__":
    main()
