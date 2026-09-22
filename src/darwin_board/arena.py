"""Repertoire evolution and a frozen, independently scored adaptation trial."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from math import ceil
from pathlib import Path

import numpy as np

from .environment import EnvironmentalTwin, OperatingPoint, TwinProfile
from .evidence import seal_payload
from .evolution import EvolutionEngine, genetic_distance
from .model import Configuration, MVPDesign, target_response_db
from .optimizer import BayesianTuner


def training_environments() -> tuple[OperatingPoint, ...]:
    return (OperatingPoint(),) + tuple(
        OperatingPoint(f"{temp} C / {load / 1000:g} kohm", temp, load, age)
        for temp in (-10, 65)
        for load in (47_000, 1_000_000)
        for age in (0.0, 0.6)
    )


def stress_score(errors: np.ndarray) -> float:
    """Equal weight on the mean and the worst quarter of training cases."""
    values = np.asarray(errors, dtype=float)
    if values.ndim != 1 or not len(values) or not np.all(np.isfinite(values)) or np.any(values < 0):
        raise ValueError("Errors must be a nonempty finite non-negative vector")
    tail = np.sort(values)[-max(1, ceil(len(values) / 4)):]
    return float(0.5 * values.mean() + 0.5 * tail.mean())


def rms_error(response: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(np.mean((response - target) ** 2)))


@dataclass(frozen=True)
class ArenaEvaluation:
    configuration: Configuration
    errors: tuple[float, ...]
    score: float
    generation: int
    parents: tuple[str, ...]
    mutations: int


class CircuitArchive:
    """One stress-tested elite per resistor allele and capacitor-count niche."""

    def __init__(self) -> None:
        self.cells: dict[tuple[int, int], ArenaEvaluation] = {}

    def add(self, evaluation: ArenaEvaluation) -> bool:
        config = evaluation.configuration
        key = (config.resistor_index, config.capacitor_mask.bit_count())
        old = self.cells.get(key)
        if old is None or (evaluation.score, config) < (old.score, old.configuration):
            self.cells[key] = evaluation
            return True
        return False

    def elites(self) -> tuple[ArenaEvaluation, ...]:
        return tuple(self.cells[key] for key in sorted(self.cells))


def evolve_archive(design: MVPDesign, *, cutoff_hz: float, seed: int, budget: int):
    """All selection happens here, before any evaluation environments exist."""
    candidates = design.configurations()
    if type(budget) is not int or not 16 <= budget <= min(256, len(candidates)):
        raise ValueError("Arena budget must be between 16 and 256 and fit the bank")
    if not np.isfinite(cutoff_hz) or not 100 <= cutoff_hz <= 10_000:
        raise ValueError("Cutoff must be between 100 and 10000 Hz")
    if type(seed) is not int or not 0 <= seed <= 2**31 - 1:
        raise ValueError("Seed must be an integer between 0 and 2147483647")
    rng = np.random.default_rng(seed)
    frequencies = np.geomspace(cutoff_hz / 10, cutoff_hz * 10, 32)
    target = target_response_db(frequencies, cutoff_hz)
    environments = training_environments()
    # The optimizer sees two independently manufactured synthetic boards.
    boards = tuple(
        EnvironmentalTwin(design, profile=TwinProfile.sample(design, seed + offset),
                          point=env, seed=seed + 1000 + offset + i)
        for offset in (0, 101)
        for i, env in enumerate(environments)
    )
    archive = CircuitArchive()
    history: list[dict] = []
    evaluated: list[ArenaEvaluation] = []
    unseen = set(candidates)
    # Stratify the initial population by resistor, then add random immigrants.
    initial = []
    for ri in range(len(design.resistor_ohms)):
        options = [c for c in candidates if c.resistor_index == ri]
        initial.append(min(options, key=lambda c: abs(np.log(design.nominal_cutoff_hz(c) / cutoff_hz))))
    for index in rng.permutation(len(candidates)):
        if len(initial) >= min(16, budget):
            break
        if candidates[index] not in initial:
            initial.append(candidates[index])
    engine = EvolutionEngine(rng, population_size=64, offspring_pool_size=8,
                             tournament_size=1, immigrant_fraction=0.25)
    generation = 0
    batch = [(config, (), 0) for config in initial]
    while len(evaluated) < budget:
        replacements = 0
        children = []
        for config, parents, mutations in batch[:budget - len(evaluated)]:
            errors = tuple(rms_error(b.measure_response_db(config, frequencies), target) for b in boards)
            evaluation = ArenaEvaluation(config, errors, stress_score(np.array(errors)), generation, parents, mutations)
            replacements += int(archive.add(evaluation))
            evaluated.append(evaluation)
            unseen.remove(config)
            children.append({"genotype": design.genotype(config), "parents": list(parents),
                             "mutations": mutations, "score_db": evaluation.score})
        best = min(evaluated, key=lambda e: e.score)
        history.append({"generation": generation, "evaluated_routes": len(evaluated),
                        "occupied_cells": len(archive.cells), "archive_updates": replacements,
                        "best_score_db": best.score, "best_genotype": design.genotype(best.configuration),
                        "children": children})
        if len(evaluated) >= budget:
            break
        offspring = engine.breed(
            measured_scores={e.configuration: e.score for e in archive.elites()},
            unseen=unseen, resistor_count=len(design.resistor_ohms),
            capacitor_count=len(design.capacitor_farads),
        )
        batch = [(c.configuration, tuple(design.genotype(p) for p in c.parents), c.mutation_count)
                 for c in offspring.candidates]
        generation += 1
    return archive, tuple(evaluated), history, boards, frequencies


def probe_archive(
    board: EnvironmentalTwin, archive: tuple[ArenaEvaluation, ...],
    current: Configuration, frequencies: np.ndarray, target: np.ndarray,
    *, cutoff_hz: float, probe_budget: int = 6, limit_db: float = 0.5,
) -> dict:
    """Bounded interventions, with a second measurement before switching.

    Fault identities and noiseless response are never available to this policy.
    The environment sensor supplies temperature/load/age only for ranking.
    """
    if probe_budget < 3:
        raise ValueError("At least three probes are required")
    probes = []

    def measure(config: Configuration) -> float:
        error = rms_error(board.measure_response_db(config, frequencies), target)
        probes.append({"genotype": board.design.genotype(config), "error_db": error})
        return error

    current_errors = [measure(current), measure(current)]
    current_score = float(np.mean(current_errors))
    if max(current_errors) <= limit_db:
        return {"configuration": current, "probes": probes, "reason": "Current path meets tolerance"}
    # Use the nearest training habitat; the two board profiles occupy equal blocks.
    def distance(point: OperatingPoint) -> float:
        env = board.point
        return ((point.temperature_c - env.temperature_c) / 75) ** 2 + (
            np.log10(point.load_ohms / env.load_ohms)
        ) ** 2 + (point.age - env.age) ** 2
    habitats = training_environments()
    nearest = min(range(len(habitats)), key=lambda i: distance(habitats[i]))
    ranked = sorted(archive, key=lambda e: (
        np.mean([e.errors[nearest], e.errors[nearest + len(habitats)]])
        + 0.005 * genetic_distance(current, e.configuration), e.configuration,
    ))
    best, best_score = current, current_score
    for elite in ranked:
        if len(probes) >= probe_budget - 1:
            break
        if elite.configuration == current:
            continue
        score = measure(elite.configuration)
        if score < best_score:
            best, best_score = elite.configuration, score
    if best != current:
        confirmation = measure(best)
        # Both observations must improve on the incumbent by a noise margin.
        if max(best_score, confirmation) + 3 * board.measurement_noise_db < min(current_errors):
            return {"configuration": best, "probes": probes, "reason": "Replacement confirmed by a second sweep"}
    return {"configuration": current, "probes": probes, "reason": "No confirmed improvement within the probe budget"}


def _metrics(errors: list[float], limit: float) -> dict:
    return {"mean_error_db": float(np.mean(errors)), "p95_error_db": float(np.percentile(errors, 95)),
            "worst_error_db": float(max(errors)), "pass_percent": float(100 * np.mean(np.array(errors) <= limit))}


def build_arena(*, cutoff_hz: float = 1200, seed: int = 7, budget: int = 96) -> dict:
    design = MVPDesign()
    archive, evaluations, history, training_boards, frequencies = evolve_archive(
        design, cutoff_hz=cutoff_hz, seed=seed, budget=budget,
    )
    target = target_response_db(frequencies, cutoff_hz)
    robust = min(evaluations, key=lambda e: (e.score, e.configuration))
    # Same candidates, reference-only selection: isolates the stress objective.
    nominal = min(evaluations, key=lambda e: (e.errors[0], e.configuration))
    rng = np.random.default_rng(seed + 202)
    all_routes = design.configurations()
    random_routes = [all_routes[i] for i in rng.choice(len(all_routes), size=budget, replace=False)]
    random_scores = []
    for config in random_routes:
        errors = np.array([rms_error(board.measure_response_db(config, frequencies), target) for board in training_boards])
        random_scores.append(stress_score(errors))
    random_best = random_routes[int(np.argmin(random_scores))]
    baseline_board = EnvironmentalTwin(design, seed=seed)
    bayesian_budget = min(24, budget)
    bayesian = BayesianTuner(seed=seed).tune(baseline_board, frequencies, cutoff_hz, budget=bayesian_budget).best.configuration
    frozen = archive.elites()
    selections = {"nominal": nominal.configuration, "robust": robust.configuration,
                  "random": random_best, "bayesian": bayesian}
    # These profiles and operating points are created only after selection ends.
    holdout_rng = np.random.default_rng(seed + 303)
    test_points = tuple(OperatingPoint(
        f"Unseen habitat {i + 1}", float(holdout_rng.uniform(-20, 80)),
        float(10 ** holdout_rng.uniform(np.log10(30_000), 7)),
        float(holdout_rng.uniform(0, 0.9)),
    ) for i in range(12))
    limits = 0.5
    holdout_errors = {key: [] for key in selections}
    for profile_id in (seed + 10_001, seed + 20_003, seed + 30_007):
        for point in test_points:
            board = EnvironmentalTwin(design, seed=profile_id, point=point)
            for key, config in selections.items():
                holdout_errors[key].append(rms_error(board.response_db(config, frequencies), target))
    # A separate sequential deployment trial. Environmental changes and faults
    # are scripted relative to the commissioned route, never to a test winner.
    caps = robust.configuration.active_capacitors(len(design.capacitor_farads))
    largest = max(caps, key=lambda i: design.capacitor_farads[i])
    resistor = robust.configuration.resistor_index
    mission = (
        OperatingPoint("Arrival", 28, 2e6, 0.1),
        OperatingPoint("Hot enclosure", 78, 180_000, 0.2),
        OperatingPoint("Sensor load changes", 48, 32_000, 0.3),
        OperatingPoint("Cold start", -18, 330_000, 0.4),
        OperatingPoint("Component wear", 55, 95_000, 0.85),
        OperatingPoint("Capacitor opens", 60, 95_000, 0.85, (largest,)),
        OperatingPoint("Second component drifts", 60, 95_000, 0.85, (largest,), ((resistor, 1.8),)),
        OperatingPoint("Load eases, faults remain", 32, 680_000, 0.85, (largest,), ((resistor, 1.8),)),
    )
    current = robust.configuration
    top_current = current
    top_population = tuple(sorted(evaluations, key=lambda e: (e.score, e.configuration))[:len(frozen)])
    steps = []
    for index, point in enumerate(mission):
        board = EnvironmentalTwin(design, seed=seed + 40_009 + index,
                                  profile=TwinProfile.sample(design, seed + 40_009), point=point)
        before = current
        decision = probe_archive(board, frozen, current, frequencies, target, cutoff_hz=cutoff_hz)
        current = decision["configuration"]
        top_board = EnvironmentalTwin(design, seed=seed + 40_009 + index,
                                      profile=board.profile, point=point)
        top_decision = probe_archive(top_board, top_population, top_current, frequencies, target, cutoff_hz=cutoff_hz)
        top_current = top_decision["configuration"]
        adaptive_response = board.response_db(current, frequencies)
        fixed_response = board.response_db(robust.configuration, frequencies)
        steps.append({"step": index, "environment": asdict(point),
                      "before_genotype": design.genotype(before), "genotype": design.genotype(current),
                      "configuration": asdict(current), "changed": current != before,
                      "reason": decision["reason"], "probes": decision["probes"],
                      "error_db": rms_error(adaptive_response, target),
                      "fixed_error_db": rms_error(fixed_response, target),
                      "topk_error_db": rms_error(top_board.response_db(top_current, frequencies), target),
                      "topk_genotype": design.genotype(top_current), "topk_probes": top_decision["probes"],
                      "response_db": adaptive_response.tolist(), "fixed_response_db": fixed_response.tolist()})
    cells = []
    for elite in frozen:
        cells.append({"resistor_index": elite.configuration.resistor_index,
                      "capacitor_count": elite.configuration.capacitor_mask.bit_count(),
                      "genotype": design.genotype(elite.configuration),
                      "score_db": elite.score, "worst_training_error_db": max(elite.errors),
                      "generation": elite.generation, "parents": list(elite.parents),
                      "configuration": asdict(elite.configuration)})
    deployed = {step["genotype"] for step in steps}
    archived = {entry["genotype"] for entry in cells}
    graph_nodes = [{"id": design.genotype(e.configuration), "configuration": asdict(e.configuration),
                    "generation": e.generation, "score_db": e.score, "parents": list(e.parents),
                    "mutations": e.mutations, "archived": design.genotype(e.configuration) in archived,
                    "deployed": design.genotype(e.configuration) in deployed} for e in evaluations]
    graph_edges = [{"source": parent, "target": child["id"], "kind": "ancestry"}
                   for child in graph_nodes for parent in dict.fromkeys(child["parents"])]
    graph_edges.extend({"source": step["before_genotype"], "target": step["genotype"],
                        "kind": "recovery", "step": step["step"], "reason": step["environment"]["name"]}
                       for step in steps if step["changed"])
    payload = {
        "meta": {"version": "0.7.0", "kind": "adaptation-arena", "seed": seed,
                 "cutoff_hz": cutoff_hz, "route_budget": budget, "limit_db": limits,
                 "search": "diversity-preserving evolution",
                 "training_sweeps_per_method": budget * len(training_boards),
                 "bayesian_training_sweeps": bayesian_budget,
                 "training_cases": len(training_boards), "holdout_cases": len(test_points) * 3,
                 "probe_budget_per_step": 6, "evidence": "Synthetic small-signal simulation; no hardware validation",
                 "objective": "0.5 mean error + 0.5 worst-quarter mean error",
                 "selection_boundary": "Archive and static choices frozen before holdout and mission creation"},
        "design": {"resistor_ohms": list(design.resistor_ohms), "capacitor_nf": [c * 1e9 for c in design.capacitor_farads]},
        "training_environments": [asdict(e) for e in training_environments()],
        "holdout_environments": [asdict(e) for e in test_points],
        "frequencies_hz": frequencies.tolist(), "target_response_db": target.tolist(),
        "archive": cells, "generations": history,
        "circuit_graph": {"nodes": graph_nodes, "edges": graph_edges},
        "static_comparison": {key: {"genotype": design.genotype(selections[key]), **_metrics(values, limits), "errors_db": values}
                              for key, values in holdout_errors.items()},
        "mission": steps,
        "mission_summary": {"adaptive": _metrics([s["error_db"] for s in steps], limits),
                            "fixed": _metrics([s["fixed_error_db"] for s in steps], limits),
                            "topk": _metrics([s["topk_error_db"] for s in steps], limits),
                            "switches": sum(s["changed"] for s in steps),
                            "probes": sum(len(s["probes"]) for s in steps)},
    }
    return seal_payload(payload)


def benchmark_arena(*, seeds: int = 10, budget: int = 96, seed_start: int = 0) -> dict:
    if type(seeds) is not int or not 1 <= seeds <= 100:
        raise ValueError("Seed count must be between 1 and 100")
    if type(seed_start) is not int or not 0 <= seed_start <= 2**31 - seeds:
        raise ValueError("Seed range must fit non-negative 32-bit signed integers")
    rows = []
    for cutoff in (600, 1200, 2400):
        for seed in range(seed_start, seed_start + seeds):
            result = build_arena(cutoff_hz=cutoff, seed=seed, budget=budget)
            rows.append({"cutoff_hz": cutoff, "seed": seed, "run_id": result["evidence"]["run_id"],
                         "archive_cells": len(result["archive"]),
                         "static_comparison": result["static_comparison"],
                         "mission_summary": result["mission_summary"]})
    summary = {
        "static": {name: _metrics([error for row in rows for error in row["static_comparison"][name]["errors_db"]], 0.5)
                   for name in ("nominal", "robust", "random", "bayesian")},
        "mission": {name: {"mean_run_error_db": float(np.mean([r["mission_summary"][name]["mean_error_db"] for r in rows])),
                           "mean_pass_percent": float(np.mean([r["mission_summary"][name]["pass_percent"] for r in rows]))}
                    for name in ("adaptive", "fixed", "topk")},
        "robust_beats_nominal_mean_error_runs": sum(r["static_comparison"]["robust"]["mean_error_db"] < r["static_comparison"]["nominal"]["mean_error_db"] for r in rows),
        "archive_beats_topk_mean_error_runs": sum(r["mission_summary"]["adaptive"]["mean_error_db"] < r["mission_summary"]["topk"]["mean_error_db"] for r in rows),
    }
    return seal_payload({"kind": "arena-benchmark", "route_budget": budget, "run_count": len(rows),
                         "seed_start": seed_start,
                         "protocol": "Fixed settings across three targets and consecutive seeds. No run excluded.",
                         "summary": summary, "runs": rows})


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Darwin Board's environmental adaptation trial")
    parser.add_argument("--cutoff", type=float, default=1200)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--budget", type=int, default=96)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--benchmark", action="store_true")
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--seed-start", type=int, default=0)
    args = parser.parse_args()
    result = (benchmark_arena(seeds=args.seeds, budget=args.budget, seed_start=args.seed_start) if args.benchmark else
              build_arena(cutoff_hz=args.cutoff, seed=args.seed, budget=args.budget))
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(result["summary"] if args.benchmark else {
        "static_comparison": result["static_comparison"], "mission_summary": result["mission_summary"]}, indent=2))


if __name__ == "__main__":
    main()
