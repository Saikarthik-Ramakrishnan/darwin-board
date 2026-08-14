from __future__ import annotations

from dataclasses import dataclass
from math import inf, log
from typing import Literal

from .model import Configuration, MVPDesign
from .optimizer import Evaluation, TuningResult


@dataclass(frozen=True, order=True)
class ComponentRef:
    """One switched component that can become a single point of failure."""

    kind: Literal["resistor", "capacitor"]
    index: int

    @property
    def label(self) -> str:
        prefix = "R" if self.kind == "resistor" else "C"
        return f"{prefix}{self.index + 1}"


@dataclass(frozen=True)
class Contingency:
    """A measured fallback route reserved for one component failure."""

    failed_component: ComponentRef
    fallback: Evaluation
    mutation_distance: int


@dataclass(frozen=True)
class ResiliencePlan:
    """Pre-qualified routes that let the board react before a new search."""

    primary: Evaluation
    baseline_best: Evaluation
    contingencies: tuple[Contingency, ...]
    failure_points: tuple[ComponentRef, ...]
    fallback_error_limit_db: float

    @property
    def coverage(self) -> float:
        if not self.failure_points:
            return 1.0
        covered = {
            item.failed_component
            for item in self.contingencies
            if item.fallback.response_error_db
            <= self.fallback_error_limit_db
        }
        return len(covered) / len(self.failure_points)

    @property
    def performance_tradeoff_db(self) -> float:
        return max(
            self.primary.response_error_db
            - self.baseline_best.response_error_db,
            0.0,
        )

    @property
    def worst_fallback_error_db(self) -> float:
        if not self.contingencies:
            return inf
        best_by_component = [
            min(
                item.fallback.response_error_db
                for item in self.contingencies
                if item.failed_component == component
            )
            for component in self.failure_points
            if any(
                item.failed_component == component
                for item in self.contingencies
            )
        ]
        return max(best_by_component, default=inf)

    @property
    def fallbacks(self) -> tuple[Configuration, ...]:
        ordered: list[Configuration] = []
        for contingency in self.contingencies:
            configuration = contingency.fallback.configuration
            if configuration not in ordered:
                ordered.append(configuration)
        return tuple(ordered)


def active_components(
    configuration: Configuration,
    capacitor_count: int,
) -> tuple[ComponentRef, ...]:
    return (
        ComponentRef("resistor", configuration.resistor_index),
        *(
            ComponentRef("capacitor", index)
            for index in configuration.active_capacitors(capacitor_count)
        ),
    )


def avoids_component(
    configuration: Configuration,
    component: ComponentRef,
) -> bool:
    if component.kind == "resistor":
        return configuration.resistor_index != component.index
    return not configuration.capacitor_mask & (1 << component.index)


def mutation_distance(left: Configuration, right: Configuration) -> int:
    changed_capacitors = (
        left.capacitor_mask ^ right.capacitor_mask
    ).bit_count()
    resistor_changed = left.resistor_index != right.resistor_index
    return changed_capacitors + int(resistor_changed)


class ResiliencePlanner:
    """Choose a strong primary route with measured escape routes."""

    def __init__(
        self,
        *,
        primary_tradeoff_db: float = 0.20,
        fallbacks_per_fault: int = 2,
        fallback_error_limit_db: float = 1.0,
    ) -> None:
        if primary_tradeoff_db < 0.0:
            raise ValueError("Primary tradeoff must be non-negative")
        if fallbacks_per_fault < 1:
            raise ValueError("Fallbacks per fault must be positive")
        if fallback_error_limit_db <= 0.0:
            raise ValueError("Fallback error limit must be positive")
        self.primary_tradeoff_db = primary_tradeoff_db
        self.fallbacks_per_fault = fallbacks_per_fault
        self.fallback_error_limit_db = fallback_error_limit_db

    def plan(
        self,
        result: TuningResult,
        *,
        capacitor_count: int,
    ) -> ResiliencePlan:
        if capacitor_count < 1:
            raise ValueError("Capacitor count must be positive")
        if not result.evaluations:
            raise ValueError("A resilience plan needs measured evaluations")

        baseline = result.best
        eligible = tuple(
            item
            for item in result.evaluations
            if item.response_error_db
            <= baseline.response_error_db + self.primary_tradeoff_db
        )
        candidates = [
            self._plan_for_primary(
                primary,
                result.evaluations,
                capacitor_count,
                baseline,
            )
            for primary in eligible
        ]
        return min(candidates, key=self._plan_rank)

    def qualification_candidates(
        self,
        design: MVPDesign,
        cutoff_hz: float,
        plan: ResiliencePlan,
        *,
        evaluated_configurations: tuple[Configuration, ...],
        limit: int = 6,
    ) -> tuple[Configuration, ...]:
        """Choose unseen escape routes worth measuring before activation."""

        if limit < 1:
            return ()
        seen = set(evaluated_configurations)
        selected: list[Configuration] = []
        all_configurations = design.configurations()
        rounds = range(self.fallbacks_per_fault)
        for _ in rounds:
            for component in plan.failure_points:
                possible = sorted(
                    (
                        configuration
                        for configuration in all_configurations
                        if configuration not in seen
                        and configuration not in selected
                        and avoids_component(configuration, component)
                    ),
                    key=lambda configuration: (
                        abs(
                            log(
                                design.nominal_cutoff_hz(configuration)
                                / cutoff_hz
                            )
                        ),
                        mutation_distance(
                            plan.primary.configuration,
                            configuration,
                        ),
                    ),
                )
                if not possible:
                    continue
                selected.append(possible[0])
                if len(selected) == limit:
                    return tuple(selected)
        return tuple(selected)

    def _plan_for_primary(
        self,
        primary: Evaluation,
        evaluations: tuple[Evaluation, ...],
        capacitor_count: int,
        baseline: Evaluation,
    ) -> ResiliencePlan:
        failure_points = active_components(
            primary.configuration,
            capacitor_count,
        )
        contingencies: list[Contingency] = []
        for component in failure_points:
            possible = tuple(
                item
                for item in evaluations
                if item.configuration != primary.configuration
                and avoids_component(item.configuration, component)
            )
            if not possible:
                continue
            ranked = sorted(
                possible,
                key=lambda item: (
                    item.response_error_db,
                    item.score,
                    mutation_distance(
                        primary.configuration,
                        item.configuration,
                    ),
                ),
            )
            for fallback in ranked[: self.fallbacks_per_fault]:
                contingencies.append(
                    Contingency(
                        failed_component=component,
                        fallback=fallback,
                        mutation_distance=mutation_distance(
                            primary.configuration,
                            fallback.configuration,
                        ),
                    )
                )
        return ResiliencePlan(
            primary=primary,
            baseline_best=baseline,
            contingencies=tuple(contingencies),
            failure_points=failure_points,
            fallback_error_limit_db=self.fallback_error_limit_db,
        )

    @staticmethod
    def _plan_rank(plan: ResiliencePlan) -> tuple[float, ...]:
        mean_mutation = (
            sum(item.mutation_distance for item in plan.contingencies)
            / len(plan.contingencies)
            if plan.contingencies
            else inf
        )
        return (
            -plan.coverage,
            plan.worst_fallback_error_db,
            float(len(plan.failure_points)),
            plan.primary.response_error_db,
            mean_mutation,
        )
