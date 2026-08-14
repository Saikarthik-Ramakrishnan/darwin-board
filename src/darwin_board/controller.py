from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .board import DarwinBoard
from .memory import ExperienceMemory
from .model import Configuration, frequency_grid
from .optimizer import BayesianTuner, TuningResult
from .resilience import ResiliencePlan, ResiliencePlanner


@dataclass(frozen=True)
class HealthReport:
    fault_detected: bool
    signature_error_db: float
    threshold_db: float
    measured_response_db: np.ndarray
    repeat_count: int
    sweep_errors_db: tuple[float, ...]


@dataclass(frozen=True)
class RecoveryDecision:
    result: TuningResult
    mode: str
    attempted_fallbacks: int
    full_search_used: bool
    search_measurements_avoided: int


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
        resilience_planner: ResiliencePlanner | None = None,
        resilience_qualification_budget: int = 6,
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
        self.resilience_planner = resilience_planner or ResiliencePlanner()
        if resilience_qualification_budget < 0:
            raise ValueError(
                "Resilience qualification budget cannot be negative"
            )
        self.resilience_qualification_budget = resilience_qualification_budget
        self.qualification_measurements = 0
        self.active_configuration: Configuration | None = None
        self.healthy_signature_db: np.ndarray | None = None
        self.latest_tuning: TuningResult | None = None
        self.contingency_plan: ResiliencePlan | None = None

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
        first_plan = self.resilience_planner.plan(
            result,
            capacitor_count=len(self.board.design.capacitor_farads),
        )
        qualification_candidates = (
            self.resilience_planner.qualification_candidates(
                self.board.design,
                self.cutoff_hz,
                first_plan,
                evaluated_configurations=tuple(
                    item.configuration for item in result.evaluations
                ),
                limit=self.resilience_qualification_budget,
            )
        )
        qualified = tuple(
            self.tuner.evaluate(
                self.board,
                self.frequencies_hz,
                self.cutoff_hz,
                configuration,
                selection_method="contingency qualification",
            )
            for configuration in qualification_candidates
        )
        self.qualification_measurements = len(qualified)
        if qualified:
            evaluations = result.evaluations + qualified
            result = TuningResult(
                best=min(evaluations, key=lambda item: item.score),
                evaluations=evaluations,
            )
        self.contingency_plan = self.resilience_planner.plan(
            result,
            capacitor_count=len(self.board.design.capacitor_farads),
        )
        result = TuningResult(
            best=self.contingency_plan.primary,
            evaluations=result.evaluations,
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
        self.contingency_plan = None
        self._activate(result)
        self._remember(result)
        return result

    def recover_resiliently(
        self,
        *,
        budget: int = 24,
        maximum_error_db: float = 1.0,
    ) -> RecoveryDecision:
        """Probe pre-qualified routes before starting another search."""

        if maximum_error_db <= 0.0:
            raise ValueError("Maximum recovery error must be positive")
        plan = self.contingency_plan
        if plan is not None and plan.fallbacks:
            evaluations = tuple(
                self.tuner.evaluate(
                    self.board,
                    self.frequencies_hz,
                    self.cutoff_hz,
                    configuration,
                    selection_method="prequalified reflex",
                )
                for configuration in plan.fallbacks
            )
            best = min(evaluations, key=lambda item: item.score)
            if best.response_error_db <= maximum_error_db:
                result = TuningResult(
                    best=best,
                    evaluations=evaluations,
                )
                self.contingency_plan = None
                self._activate(result)
                self._remember(result)
                return RecoveryDecision(
                    result=result,
                    mode="prequalified reflex",
                    attempted_fallbacks=len(evaluations),
                    full_search_used=False,
                    search_measurements_avoided=max(
                        budget - len(evaluations),
                        0,
                    ),
                )

        attempted = len(plan.fallbacks) if plan is not None else 0
        result = self.recover(budget=budget)
        return RecoveryDecision(
            result=result,
            mode="adaptive search",
            attempted_fallbacks=attempted,
            full_search_used=True,
            search_measurements_avoided=0,
        )

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
