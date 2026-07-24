from __future__ import annotations

import argparse
import json
from pathlib import Path

from .board import SimulatedDarwinBoard
from .controller import DarwinController


def describe_configuration(board: SimulatedDarwinBoard, configuration) -> dict:
    nominal_resistance, nominal_capacitance = board.design.nominal_values(configuration)
    physical = board.physical_values(configuration)
    return {
        "resistor_index": configuration.resistor_index,
        "capacitor_mask": configuration.capacitor_mask,
        "active_capacitors": list(
            configuration.active_capacitors(len(board.design.capacitor_farads))
        ),
        "nominal_resistance_ohms": nominal_resistance,
        "nominal_capacitance_nf": nominal_capacitance * 1.0e9,
        "physical_cutoff_hz": physical.cutoff_hz,
    }


def run_demo(trace_path: Path | None = None) -> dict:
    requested_cutoff_hz = 1_200.0
    board = SimulatedDarwinBoard(seed=7)
    controller = DarwinController(board, requested_cutoff_hz)

    print("DARWIN BOARD - MILESTONE 0.2")
    print(f"Requested response: first-order low-pass at {requested_cutoff_hz:.0f} Hz")
    print()

    commissioned = controller.commission(budget=24)
    original_configuration = commissioned.best.configuration
    original = describe_configuration(board, original_configuration)
    print(
        "Commissioned: "
        f"R={original['nominal_resistance_ohms'] / 1_000:.1f} kΩ, "
        f"C={original['nominal_capacitance_nf']:.1f} nF, "
        f"measured fc≈{original['physical_cutoff_hz']:.1f} Hz"
    )
    print(
        f"Response error={commissioned.best.response_error_db:.3f} dB "
        f"after {len(commissioned.evaluations)} experimental configurations"
    )

    active_capacitors = original_configuration.active_capacitors(
        len(board.design.capacitor_farads)
    )
    failed_capacitor = max(
        active_capacitors,
        key=lambda index: board.design.capacitor_farads[index],
    )
    board.inject_open_capacitor(failed_capacitor)
    failed_nf = board.design.capacitor_farads[failed_capacitor] * 1.0e9
    print()
    print(
        f"Injected fault: capacitor branch C{failed_capacitor} "
        f"({failed_nf:g} nF) opened"
    )

    health = controller.check_health(repeats=3)
    status = "FAULT DETECTED" if health.fault_detected else "healthy"
    print(
        f"Health monitor: {status}; signature changed by "
        f"{health.signature_error_db:.3f} dB RMS"
    )

    recovered = None
    recovered_description = None
    if health.fault_detected:
        recovered = controller.recover(budget=24)
        recovered_description = describe_configuration(
            board,
            recovered.best.configuration,
        )
        print(
            "Recovered: "
            f"R={recovered_description['nominal_resistance_ohms'] / 1_000:.1f} kΩ, "
            f"C={recovered_description['nominal_capacitance_nf']:.1f} nF, "
            f"measured fc≈{recovered_description['physical_cutoff_hz']:.1f} Hz"
        )
        print(
            f"Recovered response error={recovered.best.response_error_db:.3f} dB"
        )

    trace = {
        "schema_version": "0.2",
        "requested_cutoff_hz": requested_cutoff_hz,
        "commissioned": {
            **original,
            "response_error_db": commissioned.best.response_error_db,
            "measurements": len(commissioned.evaluations),
        },
        "fault": {
            "type": "open_capacitor",
            "capacitor_index": failed_capacitor,
            "nominal_capacitance_nf": failed_nf,
            "detected": health.fault_detected,
            "signature_error_db": health.signature_error_db,
            "health_sweeps": health.repeat_count,
            "sweep_errors_db": list(health.sweep_errors_db),
        },
        "recovered": (
            {
                **recovered_description,
                "response_error_db": recovered.best.response_error_db,
                "measurements": len(recovered.evaluations),
            }
            if recovered is not None and recovered_description is not None
            else None
        ),
        "total_board_measurements": board.measurement_count,
    }
    if trace_path is not None:
        trace_path.write_text(json.dumps(trace, indent=2) + "\n")
        print()
        print(f"Trace saved to {trace_path}")
    return trace


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Darwin Board milestone 0")
    parser.add_argument(
        "--trace",
        type=Path,
        help="Optional JSON path for the full demonstration trace",
    )
    arguments = parser.parse_args()
    run_demo(arguments.trace)


if __name__ == "__main__":
    main()
