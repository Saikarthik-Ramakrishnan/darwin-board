"""Small-signal environmental twin. Parameters are synthetic until calibrated."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .model import Configuration, MVPDesign


@dataclass(frozen=True)
class OperatingPoint:
    name: str = "Reference"
    temperature_c: float = 25.0
    load_ohms: float = 1.0e7
    age: float = 0.0
    open_capacitors: tuple[int, ...] = ()
    resistor_scales: tuple[tuple[int, float], ...] = ()

    def __post_init__(self) -> None:
        if not np.isfinite(self.temperature_c) or not -40 <= self.temperature_c <= 125:
            raise ValueError("Temperature must be between -40 and 125 C")
        if not np.isfinite(self.load_ohms) or self.load_ohms <= 0:
            raise ValueError("Load must be finite and positive")
        if not np.isfinite(self.age) or not 0 <= self.age <= 1:
            raise ValueError("Age must be between zero and one")
        if len(set(self.open_capacitors)) != len(self.open_capacitors):
            raise ValueError("Duplicate capacitor faults")
        if len({i for i, _ in self.resistor_scales}) != len(self.resistor_scales):
            raise ValueError("Duplicate resistor faults")
        if any(not np.isfinite(s) or s <= 0 for _, s in self.resistor_scales):
            raise ValueError("Resistor fault scales must be finite and positive")


@dataclass(frozen=True)
class TwinProfile:
    resistor_scale: tuple[float, ...]
    capacitor_scale: tuple[float, ...]
    resistor_tc: tuple[float, ...]
    capacitor_tc: tuple[float, ...]
    capacitor_wear: tuple[float, ...]
    switch_ohms: float = 65.0
    branch_esr_ohms: float = 3.0
    parasitic_farads: float = 18e-12
    leakage_ohms: float = 2e7

    @classmethod
    def sample(cls, design: MVPDesign, seed: int) -> TwinProfile:
        rng = np.random.default_rng(seed)
        nr, nc = len(design.resistor_ohms), len(design.capacitor_farads)
        # Lognormal scales stay positive. A shared offset models batch correlation.
        batch = rng.normal(0, 0.025)
        return cls(
            tuple(np.exp(rng.normal(0, 0.025, nr))),
            tuple(np.exp(batch + rng.normal(0, 0.04, nc))),
            tuple(rng.uniform(40e-6, 220e-6, nr)),
            tuple(rng.uniform(-1600e-6, 600e-6, nc)),
            tuple(rng.uniform(0.02, 0.18, nc)),
        )


class EnvironmentalTwin:
    """The existing board measurement interface, with a loaded RC network."""

    def __init__(
        self,
        design: MVPDesign | None = None,
        *,
        seed: int = 7,
        point: OperatingPoint | None = None,
        profile: TwinProfile | None = None,
        measurement_noise_db: float = 0.015,
    ) -> None:
        self.design = design or MVPDesign()
        self.point = point or OperatingPoint()
        self.profile = profile or TwinProfile.sample(self.design, seed)
        if not np.isfinite(measurement_noise_db) or measurement_noise_db < 0:
            raise ValueError("Measurement noise must be finite and non-negative")
        self.measurement_noise_db = measurement_noise_db
        self._rng = np.random.default_rng(seed)
        self.measurement_count = 0
        nr, nc = len(self.design.resistor_ohms), len(self.design.capacitor_farads)
        for values, length in ((self.profile.resistor_scale, nr),
                               (self.profile.capacitor_scale, nc),
                               (self.profile.resistor_tc, nr),
                               (self.profile.capacitor_tc, nc),
                               (self.profile.capacitor_wear, nc)):
            if len(values) != length or not np.all(np.isfinite(values)):
                raise ValueError("Profile dimensions must match the component bank")
        if any(i < 0 or i >= nc for i in self.point.open_capacitors):
            raise ValueError("Unknown capacitor fault")
        if any(i < 0 or i >= nr for i, _ in self.point.resistor_scales):
            raise ValueError("Unknown resistor fault")
        if any(v <= 0 for v in self.profile.resistor_scale + self.profile.capacitor_scale):
            raise ValueError("Component scales must be positive")
        if any(not np.isfinite(v) or v < 0 for v in (
            self.profile.switch_ohms, self.profile.branch_esr_ohms,
            self.profile.parasitic_farads,
        )) or not np.isfinite(self.profile.leakage_ohms) or self.profile.leakage_ohms <= 0:
            raise ValueError("Invalid parasitic parameters")

    def response_db(self, configuration: Configuration, frequencies_hz: np.ndarray) -> np.ndarray:
        """Deterministic ground truth for scoring; controllers use measure_response_db."""
        self.design.genotype(configuration)
        frequencies = np.asarray(frequencies_hz, dtype=float)
        if frequencies.ndim != 1 or not len(frequencies) or np.any(~np.isfinite(frequencies)) or np.any(frequencies <= 0):
            raise ValueError("Frequencies must be a nonempty vector of positive values")
        p, env = self.profile, self.point
        delta = env.temperature_c - 25.0
        ri = configuration.resistor_index
        resistance = self.design.resistor_ohms[ri] * p.resistor_scale[ri]
        resistance *= max(0.1, 1 + p.resistor_tc[ri] * delta)
        resistance *= dict(env.resistor_scales).get(ri, 1.0)
        resistance += p.switch_ohms * max(0.2, 1 + 0.004 * delta)
        jw = 2j * np.pi * frequencies
        leakage = p.leakage_ohms / 2 ** (max(delta, 0) / 25)
        admittance = np.full(frequencies.shape, 1 / env.load_ohms + 1 / leakage, dtype=complex)
        admittance += jw * p.parasitic_farads
        for ci in configuration.active_capacitors(len(self.design.capacitor_farads)):
            if ci in env.open_capacitors:
                continue
            cap = self.design.capacitor_farads[ci] * p.capacitor_scale[ci]
            cap *= max(0.1, 1 + p.capacitor_tc[ci] * delta)
            cap *= max(0.1, 1 - p.capacitor_wear[ci] * env.age)
            branch_r = p.branch_esr_ohms + p.switch_ohms * max(0.2, 1 + 0.004 * delta)
            admittance += jw * cap / (1 + jw * cap * branch_r)
        transfer = 1 / (1 + resistance * admittance)
        return 20 * np.log10(np.maximum(np.abs(transfer), 1e-12))

    def measure_response_db(self, configuration: Configuration, frequencies_hz: np.ndarray) -> np.ndarray:
        response = self.response_db(configuration, frequencies_hz)
        self.measurement_count += 1
        return response + self._rng.normal(0, self.measurement_noise_db, len(response))
