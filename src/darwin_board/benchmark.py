from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .visualizer_server import FAULT_KINDS, build_session


DEFAULT_TARGETS_HZ = (500.0, 1_000.0, 2_000.0)


def run_benchmark(
    *,
    targets_hz: Iterable[float] = DEFAULT_TARGETS_HZ,
    seeds: Iterable[int] = range(10),
    fault_kinds: Iterable[str] = tuple(sorted(FAULT_KINDS)),
    budget: int = 24,
    health_sweeps: int = 3,
) -> dict[str, Any]:
    targets_hz = tuple(float(value) for value in targets_hz)
    seeds = tuple(int(value) for value in seeds)
    fault_kinds = tuple(fault_kinds)
    if not targets_hz or not seeds or not fault_kinds:
        raise ValueError(
            "Benchmark targets, seeds, and fault kinds cannot be empty"
        )
    records: list[dict[str, Any]] = []
    for target_hz in targets_hz:
        for seed in seeds:
            for fault_kind in fault_kinds:
                session = build_session(
                    cutoff_hz=float(target_hz),
                    budget=budget,
                    seed=int(seed),
                    fault_kind=fault_kind,
                    health_sweeps=health_sweeps,
                )
                stages = session["stages"]
                records.append(
                    {
                        "target_hz": float(target_hz),
                        "seed": int(seed),
                        "fault_kind": fault_kind,
                        "fault_detected": stages["fault"]["detected"],
                        "commissioned_error_db": stages["commissioned"][
                            "response_error_db"
                        ],
                        "fault_error_db": stages["fault"]["response_error_db"],
                        "signature_ratio": stages["fault"]["signature_ratio"],
                        "recovered_error_db": stages["recovered"][
                            "response_error_db"
                        ],
                        "recovery_gain_db": stages["recovered"][
                            "recovery_gain_db"
                        ],
                        "total_measurements": session["meta"][
                            "total_measurements"
                        ],
                    }
                )

    commissioned_errors = np.array(
        [record["commissioned_error_db"] for record in records]
    )
    recovered_errors = np.array(
        [record["recovered_error_db"] for record in records]
    )
    signature_ratios = np.array(
        [record["signature_ratio"] for record in records]
    )
    recovery_gains = np.array(
        [record["recovery_gain_db"] for record in records]
    )
    detections = np.array(
        [record["fault_detected"] for record in records],
        dtype=bool,
    )
    recoveries = recovered_errors < 1.0

    return {
        "schema_version": "0.2",
        "parameters": {
            "targets_hz": list(targets_hz),
            "seeds": list(seeds),
            "fault_kinds": list(fault_kinds),
            "budget": budget,
            "health_sweeps": health_sweeps,
        },
        "summary": {
            "runs": len(records),
            "fault_detection_rate": float(detections.mean()),
            "recovery_success_rate": float(recoveries.mean()),
            "median_commissioned_error_db": float(
                np.median(commissioned_errors)
            ),
            "p95_commissioned_error_db": float(
                np.percentile(commissioned_errors, 95)
            ),
            "median_recovered_error_db": float(
                np.median(recovered_errors)
            ),
            "p95_recovered_error_db": float(
                np.percentile(recovered_errors, 95)
            ),
            "minimum_signature_ratio": float(signature_ratios.min()),
            "median_recovery_gain_db": float(np.median(recovery_gains)),
        },
        "records": records,
    }


def _print_summary(result: dict[str, Any]) -> None:
    summary = result["summary"]
    print("DARWIN BOARD BENCHMARK")
    print(f"Runs: {summary['runs']}")
    print(
        "Fault detection: "
        f"{summary['fault_detection_rate'] * 100.0:.1f}%"
    )
    print(
        "Recovery under 1 dB RMS: "
        f"{summary['recovery_success_rate'] * 100.0:.1f}%"
    )
    print(
        "Commissioned error, median / p95: "
        f"{summary['median_commissioned_error_db']:.3f} / "
        f"{summary['p95_commissioned_error_db']:.3f} dB"
    )
    print(
        "Recovered error, median / p95: "
        f"{summary['median_recovered_error_db']:.3f} / "
        f"{summary['p95_recovered_error_db']:.3f} dB"
    )
    print(
        "Weakest fault evidence: "
        f"{summary['minimum_signature_ratio']:.2f}× threshold"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark Darwin Board across targets, faults, and tolerances"
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=10,
        help="Number of tolerance profiles to test",
    )
    parser.add_argument("--budget", type=int, default=24)
    parser.add_argument("--health-sweeps", type=int, default=3)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the complete JSON report",
    )
    arguments = parser.parse_args()
    if not 1 <= arguments.seeds <= 100:
        parser.error("--seeds must be between 1 and 100")

    result = run_benchmark(
        seeds=range(arguments.seeds),
        budget=arguments.budget,
        health_sweeps=arguments.health_sweeps,
    )
    _print_summary(result)
    if arguments.output is not None:
        arguments.output.write_text(
            json.dumps(result, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Report saved to {arguments.output}")


if __name__ == "__main__":
    main()
