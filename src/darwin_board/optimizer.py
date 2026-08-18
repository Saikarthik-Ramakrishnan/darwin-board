from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .board import DarwinBoard
from .model import Configuration, low_pass_response_db, target_response_db


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
        observation_noise: float = 0.08,
        topology_weight: float = 0.12,
        kernel_scale_factors: tuple[float, ...] = (0.65, 1.0, 1.8),
    ) -> None:
        if power_weight < 0.0:
            raise ValueError("Power weight cannot be negative")
        if length_scale <= 0.0:
            raise ValueError("Length scale must be positive")
        if exploration < 0.0:
            raise ValueError("Exploration cannot be negative")
        if observation_noise <= 0.0:
            raise ValueError("Observation noise must be positive")
        if topology_weight < 0.0:
            raise ValueError("Topology weight cannot be negative")
        if not kernel_scale_factors or any(
            factor <= 0.0 for factor in kernel_scale_factors
        ):
            raise ValueError("Kernel scale factors must be positive")
        self._rng = np.random.default_rng(seed)
        self.power_weight = power_weight
        self.length_scale = length_scale
        self.exploration = exploration
        self.observation_noise = observation_noise
        self.topology_weight = topology_weight
        self.kernel_scale_factors = tuple(kernel_scale_factors)

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
        nominal_scores = self._nominal_scores(
            board,
            candidates,
            frequencies_hz,
            target,
        )
        evaluated: list[Evaluation] = []
        unseen = set(range(len(candidates)))

        # Start from experience and the best physics-model prediction, then
        # add reproducible exploratory probes.
        first_index = int(np.argmin(nominal_scores))
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
            measured_residuals = (
                measured_scores - nominal_scores[measured_indices]
            )
            residual_mean, standard_deviation = self._predict(
                features[measured_indices],
                measured_residuals,
                features[candidate_indices],
            )
            mean = nominal_scores[candidate_indices] + residual_mean
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
        electrical = (raw - minimum) / span
        capacitor_routes = np.array(
            [
                [
                    float(configuration.capacitor_mask & (1 << index) != 0)
                    for index in range(len(board.design.capacitor_farads))
                ]
                for configuration in configurations
            ]
        )
        return np.concatenate(
            (electrical, capacitor_routes * self.topology_weight),
            axis=1,
        )

    def _nominal_scores(
        self,
        board: DarwinBoard,
        configurations: tuple[Configuration, ...],
        frequencies_hz: np.ndarray,
        target: np.ndarray,
    ) -> np.ndarray:
        """Score the ideal RC model before spending physical measurements."""

        scores: list[float] = []
        for configuration in configurations:
            resistance, capacitance = board.design.nominal_values(configuration)
            response = low_pass_response_db(
                frequencies_hz,
                resistance,
                capacitance,
            )
            response_error, power_penalty = self._score_response(
                board,
                configuration,
                response,
                target,
            )
            scores.append(response_error + power_penalty)
        return np.array(scores)

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
        response_error, power_penalty = self._score_response(
            board,
            configuration,
            response,
            target,
        )
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

    def _score_response(
        self,
        board: DarwinBoard,
        configuration: Configuration,
        response: np.ndarray,
        target: np.ndarray,
    ) -> tuple[float, float]:
        response_error = float(np.sqrt(np.mean((response - target) ** 2)))
        resistance, _ = board.design.nominal_values(configuration)
        minimum_resistance = min(board.design.resistor_ohms)
        power_penalty = self.power_weight * minimum_resistance / resistance
        return response_error, power_penalty

    def _predict(
        self,
        measured_x: np.ndarray,
        measured_y: np.ndarray,
        candidate_x: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Average conservative GP predictions across several kernel scales."""

        means: list[np.ndarray] = []
        variances: list[np.ndarray] = []
        for factor in self.kernel_scale_factors:
            mean, standard_deviation = self._predict_single_scale(
                measured_x,
                measured_y,
                candidate_x,
                length_scale=self.length_scale * factor,
            )
            means.append(mean)
            variances.append(standard_deviation**2)

        stacked_means = np.array(means)
        ensemble_mean = np.mean(stacked_means, axis=0)
        # Total variance includes each model's posterior uncertainty and the
        # disagreement between length scales.
        second_moment = np.mean(
            np.array(variances) + stacked_means**2,
            axis=0,
        )
        ensemble_variance = np.maximum(
            second_moment - ensemble_mean**2,
            1.0e-9,
        )
        return ensemble_mean, np.sqrt(ensemble_variance)

    def _predict_single_scale(
        self,
        measured_x: np.ndarray,
        measured_y: np.ndarray,
        candidate_x: np.ndarray,
        *,
        length_scale: float,
    ) -> tuple[np.ndarray, np.ndarray]:
        y_mean = float(measured_y.mean())
        standard_scale = float(measured_y.std())
        median = float(np.median(measured_y))
        robust_scale = float(
            1.4826 * np.median(np.abs(measured_y - median))
        )
        y_scale = max(standard_scale, robust_scale, 0.03)
        normalized_y = (measured_y - y_mean) / y_scale

        kernel = self._rbf(
            measured_x,
            measured_x,
            length_scale=length_scale,
        )
        regularization = self.observation_noise**2 + 1.0e-8
        kernel += np.eye(len(measured_x)) * regularization
        cross_kernel = self._rbf(
            measured_x,
            candidate_x,
            length_scale=length_scale,
        )

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

    def _rbf(
        self,
        left: np.ndarray,
        right: np.ndarray,
        *,
        length_scale: float | None = None,
    ) -> np.ndarray:
        scale = self.length_scale if length_scale is None else length_scale
        squared_distance = np.sum(
            (left[:, None, :] - right[None, :, :]) ** 2,
            axis=2,
        )
        return np.exp(-0.5 * squared_distance / scale**2)
