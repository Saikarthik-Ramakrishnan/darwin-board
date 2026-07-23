from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .model import Configuration, MVPDesign, low_pass_response_db


class DarwinBoard(Protocol):
    """Measurement interface to be implemented by simulator and USB hardware."""

    design: MVPDesign

    def measure_response_db(
        self,
        configuration: Configuration,
        frequencies_hz: np.ndarray,
    ) -> np.ndarray:
        ...


@dataclass(frozen=True)
class PhysicalValues:
    resistance_ohms: float
    capacitance_farads: float

    @property
    def cutoff_hz(self) -> float:
        if self.resistance_ohms <= 0.0 or self.capacitance_farads <= 0.0:
            return float("inf")
        return 1.0 / (2.0 * np.pi * self.resistance_ohms * self.capacitance_farads)


class SimulatedDarwinBoard:
    """A repeatable imperfect board with tolerance, noise, and injectable faults."""

    def __init__(
        self,
        design: MVPDesign | None = None,
        *,
        seed: int = 7,
        resistor_tolerance: float = 0.03,
        capacitor_tolerance: float = 0.06,
        measurement_noise_db: float = 0.025,
    ) -> None:
        self.design = design or MVPDesign()
        self._rng = np.random.default_rng(seed)
        self._resistor_scale = self._rng.normal(
            1.0, resistor_tolerance, len(self.design.resistor_ohms)
        )
        self._capacitor_scale = self._rng.normal(
            1.0, capacitor_tolerance, len(self.design.capacitor_farads)
        )
        self._resistor_fault_scale = np.ones(len(self.design.resistor_ohms))
        self._capacitor_fault_scale = np.ones(len(self.design.capacitor_farads))
        self.measurement_noise_db = measurement_noise_db
        self.measurement_count = 0

    def physical_values(self, configuration: Configuration) -> PhysicalValues:
        resistor_index = configuration.resistor_index
        resistance = (
            self.design.resistor_ohms[resistor_index]
            * self._resistor_scale[resistor_index]
            * self._resistor_fault_scale[resistor_index]
        )
        capacitance = sum(
            self.design.capacitor_farads[index]
            * self._capacitor_scale[index]
            * self._capacitor_fault_scale[index]
            for index in configuration.active_capacitors(
                len(self.design.capacitor_farads)
            )
        )
        return PhysicalValues(resistance, capacitance)

    def measure_response_db(
        self,
        configuration: Configuration,
        frequencies_hz: np.ndarray,
    ) -> np.ndarray:
        values = self.physical_values(configuration)
        response = low_pass_response_db(
            frequencies_hz,
            values.resistance_ohms,
            values.capacitance_farads,
        )
        noise = self._rng.normal(0.0, self.measurement_noise_db, len(frequencies_hz))
        self.measurement_count += 1
        return response + noise

    def inject_open_capacitor(self, capacitor_index: int) -> None:
        self._validate_capacitor_index(capacitor_index)
        self._capacitor_fault_scale[capacitor_index] = 0.0

    def inject_capacitor_drift(self, capacitor_index: int, scale: float) -> None:
        self._validate_capacitor_index(capacitor_index)
        if scale < 0.0:
            raise ValueError("Capacitor scale cannot be negative")
        self._capacitor_fault_scale[capacitor_index] = scale

    def inject_resistor_drift(self, resistor_index: int, scale: float) -> None:
        if not 0 <= resistor_index < len(self.design.resistor_ohms):
            raise IndexError("Unknown resistor index")
        if scale <= 0.0:
            raise ValueError("Resistor scale must be positive")
        self._resistor_fault_scale[resistor_index] = scale

    def _validate_capacitor_index(self, capacitor_index: int) -> None:
        if not 0 <= capacitor_index < len(self.design.capacitor_farads):
            raise IndexError("Unknown capacitor index")

