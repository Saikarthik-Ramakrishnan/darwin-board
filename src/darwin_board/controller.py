from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .board import DarwinBoard
from .memory import ExperienceMemory
from .model import Configuration, frequency_grid
from .optimizer import BayesianTuner, TuningResult


@dataclass(frozen=True)
class HealthReport:
    fault_detected: bool
    signature_error_db: float
    threshold_db: float
    measured_response_db: np.ndarray
    repeat_count: int
    sweep_errors_db: tuple[float, ...]


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
        memory: ExperienceMemory | None = None,
        board_id: str = "unknown",
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
        self.memory = memory
        self.board_id = board_id
        self.active_configuration: Configuration | None = None
        self.healthy_signature_db: np.ndarray | None = None
        self.latest_tuning: TuningResult | None = None

    def commission(self, *, budget: int = 24) -> TuningResult:
        preferred = (
            self.memory.recommend(self.cutoff_hz)
            if self.memory is not None
            else ()
        )
        result = self.tuner.tune(
            self.board,
            self.frequencies_hz,
            self.cutoff_hz,
            budget=budget,
            preferred_configurations=preferred,
        )
        self._activate(result)
        self._remember(result)
        return result

    def check_health(self, *, repeats: int = 1) -> HealthReport:
        if self.active_configuration is None or self.healthy_signature_db is None:
            raise RuntimeError("Board must be commissioned before health checks")
        if not 1 <= repeats <= 16:
            raise ValueError("Health-check repeats must be between 1 and 16")

        responses = np.array(
            [
                self.board.measure_response_db(
                    self.active_configuration,
                    self.frequencies_hz,
                )
                for _ in range(repeats)
            ]
        )
        sweep_errors = tuple(
            float(
                np.sqrt(
                    np.mean((response - self.healthy_signature_db) ** 2)
                )
            )
            for response in responses
        )
        signature_error = float(np.median(sweep_errors))
        response = np.median(responses, axis=0)
        return HealthReport(
            fault_detected=signature_error > self.health_threshold_db,
            signature_error_db=signature_error,
            threshold_db=self.health_threshold_db,
            measured_response_db=response,
            repeat_count=repeats,
            sweep_errors_db=sweep_errors,
        )

    def recover(self, *, budget: int = 24) -> TuningResult:
        excluded = (
            (self.active_configuration,)
            if self.active_configuration is not None
            else ()
        )
        preferred = (
            self.memory.recommend(
                self.cutoff_hz,
                exclude=excluded,
            )
            if self.memory is not None
            else ()
        )
        result = self.tuner.tune(
            self.board,
            self.frequencies_hz,
            self.cutoff_hz,
            budget=budget,
            preferred_configurations=preferred,
        )
        self._activate(result)
        self._remember(result)
        return result

    def _remember(self, result: TuningResult) -> None:
        if self.memory is None:
            return
        self.memory.record(
            cutoff_hz=self.cutoff_hz,
            configuration=result.best.configuration,
            response_error_db=result.best.response_error_db,
            board_id=self.board_id,
        )

    def _activate(self, result: TuningResult) -> None:
        self.latest_tuning = result
        self.active_configuration = result.best.configuration
        # Use a fresh measurement as the healthy runtime signature.
        self.healthy_signature_db = self.board.measure_response_db(
            result.best.configuration,
            self.frequencies_hz,
        )
