from __future__ import annotations

from dataclasses import dataclass
from math import pi
import re

import numpy as np


@dataclass(frozen=True, order=True)
class Configuration:
    """One resistor tap and one non-empty subset of switched capacitors."""

    resistor_index: int
    capacitor_mask: int

    def active_capacitors(self, count: int) -> tuple[int, ...]:
        return tuple(index for index in range(count) if self.capacitor_mask & (1 << index))

    def genotype(self, resistor_count: int, capacitor_count: int) -> str:
        """Return the canonical binary chromosome for this hardware route."""

        if not 0 <= self.resistor_index < resistor_count:
            raise ValueError("Resistor gene is outside the component bank")
        if not 0 < self.capacitor_mask < (1 << capacitor_count):
            raise ValueError("Capacitor genes are outside the component bank")
        resistor_width = max(1, (resistor_count - 1).bit_length())
        return (
            f"R{self.resistor_index:0{resistor_width}b}:"
            f"C{self.capacitor_mask:0{capacitor_count}b}"
        )


@dataclass(frozen=True)
class MVPDesign:
    """Nominal component bank used by both the simulator and real controller."""

    resistor_ohms: tuple[float, ...] = (
        1_000.0,
        2_200.0,
        4_700.0,
        10_000.0,
        22_000.0,
        47_000.0,
        100_000.0,
        220_000.0,
    )
    capacitor_farads: tuple[float, ...] = (
        470.0e-12,
        1.0e-9,
        2.2e-9,
        4.7e-9,
        10.0e-9,
        22.0e-9,
        47.0e-9,
        100.0e-9,
    )

    def configurations(self) -> tuple[Configuration, ...]:
        masks = range(1, 1 << len(self.capacitor_farads))
        return tuple(
            Configuration(resistor_index, capacitor_mask)
            for resistor_index in range(len(self.resistor_ohms))
            for capacitor_mask in masks
        )

    def nominal_values(self, configuration: Configuration) -> tuple[float, float]:
        resistance = self.resistor_ohms[configuration.resistor_index]
        capacitance = sum(
            self.capacitor_farads[index]
            for index in configuration.active_capacitors(len(self.capacitor_farads))
        )
        return resistance, capacitance

    def nominal_cutoff_hz(self, configuration: Configuration) -> float:
        resistance, capacitance = self.nominal_values(configuration)
        return 1.0 / (2.0 * pi * resistance * capacitance)

    def genotype(self, configuration: Configuration) -> str:
        return configuration.genotype(
            len(self.resistor_ohms),
            len(self.capacitor_farads),
        )

    def genotype_catalog(self) -> tuple[str, ...]:
        """Return one stable, unique chromosome for every possible route."""

        return tuple(self.genotype(item) for item in self.configurations())

    def configuration_from_genotype(self, genotype: str) -> Configuration:
        """Decode a canonical chromosome and validate it against this bank."""

        resistor_width = max(1, (len(self.resistor_ohms) - 1).bit_length())
        capacitor_width = len(self.capacitor_farads)
        match = re.fullmatch(
            rf"R([01]{{{resistor_width}}}):C([01]{{{capacitor_width}}})",
            genotype,
        )
        if match is None:
            raise ValueError("Invalid hardware genotype")
        configuration = Configuration(
            resistor_index=int(match.group(1), 2),
            capacitor_mask=int(match.group(2), 2),
        )
        self.genotype(configuration)
        return configuration


def frequency_grid(
    minimum_hz: float = 80.0,
    maximum_hz: float = 25_000.0,
    points: int = 32,
) -> np.ndarray:
    return np.geomspace(minimum_hz, maximum_hz, points)


def low_pass_response_db(
    frequencies_hz: np.ndarray,
    resistance_ohms: float,
    capacitance_farads: float,
) -> np.ndarray:
    angular_term = 2.0 * pi * frequencies_hz * resistance_ohms * capacitance_farads
    magnitude = 1.0 / np.sqrt(1.0 + angular_term**2)
    return 20.0 * np.log10(np.maximum(magnitude, 1.0e-12))


def target_response_db(frequencies_hz: np.ndarray, cutoff_hz: float) -> np.ndarray:
    normalized = frequencies_hz / cutoff_hz
    magnitude = 1.0 / np.sqrt(1.0 + normalized**2)
    return 20.0 * np.log10(np.maximum(magnitude, 1.0e-12))
