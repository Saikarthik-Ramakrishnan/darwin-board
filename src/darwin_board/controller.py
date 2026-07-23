from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .board import DarwinBoard
from .model import Configuration, frequency_grid
from .optimizer import BayesianTuner, TuningResult


@dataclass(frozen=True)
class HealthReport:
    fault_detected: bool
    signature_error_db: float
    threshold_db: float
    measured_response_db: np.ndarray


class DarwinController:
    """Coordinates experimental tuning, health monitoring, and recovery."""

    def __init__(
        self,
        board: DarwinBoard,
        cutoff_hz: float,
        *,
        tuner: BayesianTuner | None = None,
        frequencies_hz: np.ndarray | None = None,
        health_threshold_db: float = 0.75,
    ) -> None:
        self.board = board
        self.cutoff_hz = cutoff_hz
        self.tuner = tuner or BayesianTuner()
        self.frequencies_hz = (
            np.array(frequencies_hz, dtype=float)
            if frequencies_hz is not None
            else frequency_grid()
        )
        self.health_threshold_db = health_threshold_db
        self.active_configuration: Configuration | None = None
        self.healthy_signature_db: np.ndarray | None = None
        self.latest_tuning: TuningResult | None = None

    def commission(self, *, budget: int = 24) -> TuningResult:
        result = self.tuner.tune(
            self.board,
            self.frequencies_hz,
            self.cutoff_hz,
            budget=budget,
        )
        self._activate(result)
        return result

    def check_health(self) -> HealthReport:
        if self.active_configuration is None or self.healthy_signature_db is None:
            raise RuntimeError("Board must be commissioned before health checks")
        response = self.board.measure_response_db(
            self.active_configuration,
            self.frequencies_hz,
        )
        signature_error = float(
            np.sqrt(np.mean((response - self.healthy_signature_db) ** 2))
        )
        return HealthReport(
            fault_detected=signature_error > self.health_threshold_db,
            signature_error_db=signature_error,
            threshold_db=self.health_threshold_db,
            measured_response_db=response,
        )

    def recover(self, *, budget: int = 24) -> TuningResult:
        result = self.tuner.tune(
            self.board,
            self.frequencies_hz,
            self.cutoff_hz,
            budget=budget,
        )
        self._activate(result)
        return result

    def _activate(self, result: TuningResult) -> None:
        self.latest_tuning = result
        self.active_configuration = result.best.configuration
        # Use a fresh measurement as the healthy runtime signature.
        self.healthy_signature_db = self.board.measure_response_db(
            result.best.configuration,
            self.frequencies_hz,
        )

