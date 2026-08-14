from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .board import DarwinBoard
from .model import Configuration, target_response_db


@dataclass(frozen=True)
class Evaluation:
    configuration: Configuration
    score: float
    response_error_db: float
    power_penalty: float
    response_db: np.ndarray
    selection_method: str
    predicted_score: float | None
    predicted_uncertainty: float | None


@dataclass(frozen=True)
class TuningResult:
    best: Evaluation
    evaluations: tuple[Evaluation, ...]


class BayesianTuner:
    """Small Gaussian-process tuner for the discrete MVP component bank."""

    def __init__(
        self,
        *,
        seed: int = 19,
        power_weight: float = 0.10,
        length_scale: float = 0.23,
        exploration: float = 1.5,
    ) -> None:
        self._rng = np.random.default_rng(seed)
        self.power_weight = power_weight
        self.length_scale = length_scale
        self.exploration = exploration

    def tune(
        self,
        board: DarwinBoard,
        frequencies_hz: np.ndarray,
        cutoff_hz: float,
        *,
        budget: int = 24,
        initial_samples: int = 6,
        preferred_configurations: Iterable[Configuration] = (),
    ) -> TuningResult:
        candidates = board.design.configurations()
        candidate_indices_by_configuration = {
            configuration: index
            for index, configuration in enumerate(candidates)
        }
        if not 1 <= budget <= len(candidates):
            raise ValueError("Budget must fit within the candidate set")
        initial_samples = min(initial_samples, budget)
        target = target_response_db(frequencies_hz, cutoff_hz)
        features = self._features(board, candidates)
        evaluated: list[Evaluation] = []
        unseen = set(range(len(candidates)))

        # Include one nominally promising point, then spread random initial probes.
        nominal_errors = np.array(
            [
                abs(np.log(board.design.nominal_cutoff_hz(candidate) / cutoff_hz))
                for candidate in candidates
            ]
        )
        first_index = int(np.argmin(nominal_errors))
        initial_plan: list[tuple[int, str]] = []
        for configuration in preferred_configurations:
            index = candidate_indices_by_configuration.get(configuration)
            if index is None or index not in unseen:
                continue
            initial_plan.append((index, "experience memory"))
            unseen.remove(index)
            if len(initial_plan) == initial_samples:
                break

        if first_index in unseen and len(initial_plan) < initial_samples:
            initial_plan.append((first_index, "nominal prior"))
            unseen.remove(first_index)

        remaining_initial_samples = initial_samples - len(initial_plan)
        if remaining_initial_samples > 0:
            random_indices = self._rng.choice(
                np.array(sorted(unseen)),
                size=remaining_initial_samples,
                replace=False,
            )
            for index in random_indices:
                initial_plan.append((int(index), "exploration seed"))
                unseen.remove(int(index))

        for index, selection_method in initial_plan:
            evaluated.append(
                self._evaluate(
                    board,
                    candidates[index],
                    frequencies_hz,
                    target,
                    selection_method=selection_method,
                )
            )

        while len(evaluated) < budget:
            measured_indices = np.array(
                [
                    candidate_indices_by_configuration[item.configuration]
                    for item in evaluated
                ],
                dtype=int,
            )
            measured_scores = np.array([item.score for item in evaluated])
            candidate_indices = np.array(sorted(unseen), dtype=int)
            mean, standard_deviation = self._predict(
                features[measured_indices],
                measured_scores,
                features[candidate_indices],
            )
            acquisition = mean - self.exploration * standard_deviation
            selected_position = int(np.argmin(acquisition))
            next_index = int(candidate_indices[selected_position])
            unseen.remove(next_index)
            evaluated.append(
                self._evaluate(
                    board,
                    candidates[next_index],
                    frequencies_hz,
                    target,
                    selection_method="lower confidence bound",
                    predicted_score=float(mean[selected_position]),
                    predicted_uncertainty=float(
                        standard_deviation[selected_position]
                    ),
                )
            )

        best = min(evaluated, key=lambda item: item.score)
        return TuningResult(best=best, evaluations=tuple(evaluated))

    def evaluate(
        self,
        board: DarwinBoard,
        frequencies_hz: np.ndarray,
        cutoff_hz: float,
        configuration: Configuration,
        *,
        selection_method: str,
    ) -> Evaluation:
        """Measure one chosen route using the same score as the tuner."""

        target = target_response_db(frequencies_hz, cutoff_hz)
        return self._evaluate(
            board,
            configuration,
            frequencies_hz,
            target,
            selection_method=selection_method,
        )

    def _features(
        self,
        board: DarwinBoard,
        configurations: tuple[Configuration, ...],
    ) -> np.ndarray:
        raw = np.array(
            [
                np.log10(board.design.nominal_values(configuration))
                for configuration in configurations
            ]
        )
        minimum = raw.min(axis=0)
        span = np.maximum(raw.max(axis=0) - minimum, 1.0e-12)
        return (raw - minimum) / span

    def _evaluate(
        self,
        board: DarwinBoard,
        configuration: Configuration,
        frequencies_hz: np.ndarray,
        target: np.ndarray,
        *,
        selection_method: str,
        predicted_score: float | None = None,
        predicted_uncertainty: float | None = None,
    ) -> Evaluation:
        response = board.measure_response_db(configuration, frequencies_hz)
        response_error = float(np.sqrt(np.mean((response - target) ** 2)))
        resistance, _ = board.design.nominal_values(configuration)
        minimum_resistance = min(board.design.resistor_ohms)
        power_penalty = self.power_weight * minimum_resistance / resistance
        return Evaluation(
            configuration=configuration,
            score=response_error + power_penalty,
            response_error_db=response_error,
            power_penalty=power_penalty,
            response_db=response,
            selection_method=selection_method,
            predicted_score=predicted_score,
            predicted_uncertainty=predicted_uncertainty,
        )

    def _predict(
        self,
        measured_x: np.ndarray,
        measured_y: np.ndarray,
        candidate_x: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        y_mean = float(measured_y.mean())
        y_scale = float(measured_y.std())
        if y_scale < 1.0e-9:
            y_scale = 1.0
        normalized_y = (measured_y - y_mean) / y_scale

        kernel = self._rbf(measured_x, measured_x)
        kernel += np.eye(len(measured_x)) * 1.0e-5
        cross_kernel = self._rbf(measured_x, candidate_x)

        try:
            factor = np.linalg.cholesky(kernel)
            alpha = np.linalg.solve(factor.T, np.linalg.solve(factor, normalized_y))
            normalized_mean = cross_kernel.T @ alpha
            projected = np.linalg.solve(factor, cross_kernel)
            normalized_variance = np.maximum(
                1.0 - np.sum(projected**2, axis=0),
                1.0e-9,
            )
        except np.linalg.LinAlgError:
            inverse = np.linalg.pinv(kernel)
            normalized_mean = cross_kernel.T @ inverse @ normalized_y
            normalized_variance = np.maximum(
                1.0 - np.sum(cross_kernel * (inverse @ cross_kernel), axis=0),
                1.0e-9,
            )

        mean = normalized_mean * y_scale + y_mean
        standard_deviation = np.sqrt(normalized_variance) * y_scale
        return mean, standard_deviation

    def _rbf(self, left: np.ndarray, right: np.ndarray) -> np.ndarray:
        squared_distance = np.sum(
            (left[:, None, :] - right[None, :, :]) ** 2,
            axis=2,
        )
        return np.exp(-0.5 * squared_distance / self.length_scale**2)
