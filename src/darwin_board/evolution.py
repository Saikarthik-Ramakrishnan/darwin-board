from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Mapping

import numpy as np

from .model import Configuration


@dataclass(frozen=True)
class EvolutionCandidate:
    """One unmeasured child and the genetic operation that produced it."""

    configuration: Configuration
    parents: tuple[Configuration, ...]
    mutation_count: int

    @property
    def is_immigrant(self) -> bool:
        return not self.parents


@dataclass(frozen=True)
class EvolutionBatch:
    """Candidate children bred from the current measured survivors."""

    parents: tuple[Configuration, ...]
    candidates: tuple[EvolutionCandidate, ...]


@dataclass(frozen=True)
class EvolutionGeneration:
    """Measured evidence for one generation of hardware chromosomes."""

    index: int
    parents: tuple[Configuration, ...]
    offspring: tuple[Configuration, ...]
    survivors: tuple[Configuration, ...]
    best_configuration: Configuration
    best_score: float
    improvement: float
    diversity: float
    mutation_events: int
    crossover_events: int
    immigrant_count: int


def genetic_distance(left: Configuration, right: Configuration) -> int:
    capacitor_changes = (left.capacitor_mask ^ right.capacitor_mask).bit_count()
    return capacitor_changes + int(left.resistor_index != right.resistor_index)


def population_diversity(
    population: tuple[Configuration, ...],
    capacitor_count: int,
) -> float:
    """Mean pairwise chromosome distance, normalized to the range 0 to 1."""

    if len(population) < 2:
        return 0.0
    distances = [
        genetic_distance(left, right) / (capacitor_count + 1)
        for left_index, left in enumerate(population)
        for right in population[left_index + 1 :]
    ]
    return float(np.mean(distances))


class EvolutionEngine:
    """Breed hardware routes while retaining diversity and measured elites."""

    def __init__(
        self,
        rng: np.random.Generator,
        *,
        population_size: int = 8,
        offspring_pool_size: int = 48,
        resistor_mutation_rate: float = 0.18,
        capacitor_mutation_rate: float | None = None,
        immigrant_fraction: float = 0.15,
        tournament_size: int = 3,
    ) -> None:
        if population_size < 2:
            raise ValueError("Evolution population must contain at least two routes")
        if offspring_pool_size < 1:
            raise ValueError("Offspring pool size must be positive")
        if not 0.0 <= resistor_mutation_rate <= 1.0:
            raise ValueError("Resistor mutation rate must be between 0 and 1")
        if capacitor_mutation_rate is not None and not (
            0.0 <= capacitor_mutation_rate <= 1.0
        ):
            raise ValueError("Capacitor mutation rate must be between 0 and 1")
        if not 0.0 <= immigrant_fraction < 1.0:
            raise ValueError("Immigrant fraction must be between 0 and 1")
        if tournament_size < 1:
            raise ValueError("Tournament size must be positive")
        self.rng = rng
        self.population_size = population_size
        self.offspring_pool_size = offspring_pool_size
        self.resistor_mutation_rate = resistor_mutation_rate
        self.capacitor_mutation_rate = capacitor_mutation_rate
        self.immigrant_fraction = immigrant_fraction
        self.tournament_size = tournament_size

    def breed(
        self,
        *,
        measured_scores: Mapping[Configuration, float],
        unseen: set[Configuration],
        resistor_count: int,
        capacitor_count: int,
    ) -> EvolutionBatch:
        if not measured_scores or not unseen:
            return EvolutionBatch((), ())
        parents = tuple(
            configuration
            for configuration, _ in sorted(
                measured_scores.items(),
                key=lambda item: item[1],
            )[: self.population_size]
        )
        target_size = min(self.offspring_pool_size, len(unseen))
        immigrant_count = min(
            int(ceil(target_size * self.immigrant_fraction)),
            target_size,
        )
        children: dict[Configuration, EvolutionCandidate] = {}
        attempts = 0
        maximum_attempts = max(target_size * 40, 100)
        while (
            len(children) < target_size - immigrant_count
            and attempts < maximum_attempts
        ):
            attempts += 1
            first = self._tournament(parents, measured_scores)
            second = self._tournament(parents, measured_scores)
            configuration, mutation_count = self._crossover_and_mutate(
                first,
                second,
                resistor_count=resistor_count,
                capacitor_count=capacitor_count,
            )
            if configuration not in unseen or configuration in children:
                continue
            children[configuration] = EvolutionCandidate(
                configuration=configuration,
                parents=(first, second),
                mutation_count=mutation_count,
            )

        immigrant_options = tuple(
            configuration
            for configuration in sorted(unseen)
            if configuration not in children
        )
        remaining = target_size - len(children)
        if remaining > 0 and immigrant_options:
            chosen = self.rng.choice(
                np.array(immigrant_options, dtype=object),
                size=min(remaining, len(immigrant_options)),
                replace=False,
            )
            for configuration in chosen:
                children[configuration] = EvolutionCandidate(
                    configuration=configuration,
                    parents=(),
                    mutation_count=0,
                )
        return EvolutionBatch(parents, tuple(children.values()))

    def survivors(
        self,
        measured_scores: Mapping[Configuration, float],
    ) -> tuple[Configuration, ...]:
        return tuple(
            configuration
            for configuration, _ in sorted(
                measured_scores.items(),
                key=lambda item: item[1],
            )[: self.population_size]
        )

    def _tournament(
        self,
        parents: tuple[Configuration, ...],
        measured_scores: Mapping[Configuration, float],
    ) -> Configuration:
        count = min(self.tournament_size, len(parents))
        contenders = self.rng.choice(
            np.array(parents, dtype=object),
            size=count,
            replace=False,
        )
        return min(contenders, key=lambda item: measured_scores[item])

    def _crossover_and_mutate(
        self,
        first: Configuration,
        second: Configuration,
        *,
        resistor_count: int,
        capacitor_count: int,
    ) -> tuple[Configuration, int]:
        resistor_index = (
            first.resistor_index
            if self.rng.random() < 0.5
            else second.resistor_index
        )
        selector = int(self.rng.integers(0, 1 << capacitor_count))
        full_mask = (1 << capacitor_count) - 1
        capacitor_mask = (
            (first.capacitor_mask & selector)
            | (second.capacitor_mask & (~selector & full_mask))
        )

        mutation_count = 0
        if self.rng.random() < self.resistor_mutation_rate:
            direction = -1 if self.rng.random() < 0.5 else 1
            mutated = resistor_index + direction
            if not 0 <= mutated < resistor_count:
                mutated = resistor_index - direction
            if mutated != resistor_index:
                resistor_index = mutated
                mutation_count += 1

        capacitor_rate = (
            self.capacitor_mutation_rate
            if self.capacitor_mutation_rate is not None
            else 1.0 / capacitor_count
        )
        for index in range(capacitor_count):
            if self.rng.random() < capacitor_rate:
                capacitor_mask ^= 1 << index
                mutation_count += 1
        if capacitor_mask == 0:
            capacitor_mask = 1 << int(self.rng.integers(0, capacitor_count))
            mutation_count += 1
        return Configuration(resistor_index, capacitor_mask), mutation_count
