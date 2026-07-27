from __future__ import annotations

import argparse
import errno
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np

from .board import SimulatedDarwinBoard
from .controller import DarwinController
from .evidence import seal_payload
from .memory import ExperienceMemory
from .model import Configuration, target_response_db
from .optimizer import Evaluation, TuningResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = PROJECT_ROOT / "visualizer" / "index.html"
FAULT_KINDS = {
    "open_capacitor",
    "capacitor_drift",
    "resistor_drift",
}


def _configuration_payload(
    board: SimulatedDarwinBoard,
    configuration: Configuration,
) -> dict[str, Any]:
    resistance, capacitance = board.design.nominal_values(configuration)
    physical = board.physical_values(configuration)
    return {
        "resistor_index": configuration.resistor_index,
        "capacitor_mask": configuration.capacitor_mask,
        "genotype": (
            f"R{configuration.resistor_index + 1}:"
            f"C{configuration.capacitor_mask:06b}"
        ),
        "active_capacitors": list(
            configuration.active_capacitors(len(board.design.capacitor_farads))
        ),
        "nominal_resistance_ohms": resistance,
        "nominal_capacitance_nf": capacitance * 1.0e9,
        "physical_cutoff_hz": physical.cutoff_hz,
    }


def _search_payload(
    board: SimulatedDarwinBoard,
    result: TuningResult,
) -> list[dict[str, float | int | str | None]]:
    return [
        {
            "measurement": index,
            "score": evaluation.score,
            "response_error_db": evaluation.response_error_db,
            "nominal_cutoff_hz": board.design.nominal_cutoff_hz(
                evaluation.configuration
            ),
            "selection_method": evaluation.selection_method,
            "predicted_score": evaluation.predicted_score,
            "predicted_uncertainty": evaluation.predicted_uncertainty,
        }
        for index, evaluation in enumerate(result.evaluations, start=1)
    ]


def _response_error(response: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(np.mean((response - target) ** 2)))


def _inject_fault(
    board: SimulatedDarwinBoard,
    configuration: Configuration,
    fault_kind: str,
) -> dict[str, Any]:
    if fault_kind not in FAULT_KINDS:
        choices = ", ".join(sorted(FAULT_KINDS))
        raise ValueError(f"fault_kind must be one of: {choices}")

    if fault_kind in {"open_capacitor", "capacitor_drift"}:
        active_capacitors = configuration.active_capacitors(
            len(board.design.capacitor_farads)
        )
        capacitor_index = max(
            active_capacitors,
            key=lambda index: board.design.capacitor_farads[index],
        )
        capacitance_nf = board.design.capacitor_farads[capacitor_index] * 1.0e9
        if fault_kind == "open_capacitor":
            board.inject_open_capacitor(capacitor_index)
            return {
                "kind": fault_kind,
                "label": "Open capacitor branch",
                "component": f"C{capacitor_index + 1}",
                "component_index": capacitor_index,
                "nominal_value": capacitance_nf,
                "nominal_unit": "nF",
                "change_percent": -100.0,
            }

        drift_scale = 0.55
        board.inject_capacitor_drift(capacitor_index, drift_scale)
        return {
            "kind": fault_kind,
            "label": "Capacitor drift",
            "component": f"C{capacitor_index + 1}",
            "component_index": capacitor_index,
            "nominal_value": capacitance_nf,
            "nominal_unit": "nF",
            "change_percent": (drift_scale - 1.0) * 100.0,
        }

    resistor_index = configuration.resistor_index
    drift_scale = 1.50
    board.inject_resistor_drift(resistor_index, drift_scale)
    return {
        "kind": fault_kind,
        "label": "Resistor drift",
        "component": f"R{resistor_index + 1}",
        "component_index": resistor_index,
        "nominal_value": board.design.resistor_ohms[resistor_index],
        "nominal_unit": "Ω",
        "change_percent": (drift_scale - 1.0) * 100.0,
    }


def build_session(
    cutoff_hz: float = 1_200.0,
    budget: int = 24,
    seed: int = 7,
    fault_kind: str = "open_capacitor",
    health_sweeps: int = 3,
    memory: ExperienceMemory | None = None,
) -> dict[str, Any]:
    if not 100.0 <= cutoff_hz <= 10_000.0:
        raise ValueError("cutoff_hz must be between 100 and 10000")
    if not 8 <= budget <= 60:
        raise ValueError("budget must be between 8 and 60")
    if not 0 <= seed <= 1_000_000:
        raise ValueError("seed must be between 0 and 1000000")
    if fault_kind not in FAULT_KINDS:
        choices = ", ".join(sorted(FAULT_KINDS))
        raise ValueError(f"fault_kind must be one of: {choices}")
    if not 1 <= health_sweeps <= 8:
        raise ValueError("health_sweeps must be between 1 and 8")

    board = SimulatedDarwinBoard(seed=seed)
    memory_records_before = len(memory) if memory is not None else 0
    controller = DarwinController(
        board,
        cutoff_hz=cutoff_hz,
        memory=memory,
        board_id=f"SIM-{seed:06d}",
    )
    frequencies = controller.frequencies_hz
    target = target_response_db(frequencies, cutoff_hz)

    commissioned = controller.commission(budget=budget)
    commissioned_configuration = commissioned.best.configuration
    commissioned_response = np.array(controller.healthy_signature_db, copy=True)
    commissioned_details = _configuration_payload(
        board,
        commissioned_configuration,
    )

    fault = _inject_fault(board, commissioned_configuration, fault_kind)
    health = controller.check_health(repeats=health_sweeps)
    faulty_details = _configuration_payload(
        board,
        commissioned_configuration,
    )

    recovered = controller.recover(budget=budget)
    recovered_configuration = recovered.best.configuration
    recovered_response = np.array(controller.healthy_signature_db, copy=True)
    recovered_details = _configuration_payload(
        board,
        recovered_configuration,
    )
    commissioned_error = _response_error(commissioned_response, target)
    fault_error = _response_error(health.measured_response_db, target)
    recovered_error = _response_error(recovered_response, target)
    cutoff_shift_percent = (
        faulty_details["physical_cutoff_hz"]
        / commissioned_details["physical_cutoff_hz"]
        - 1.0
    ) * 100.0
    recovery_gain_db = fault_error - recovered_error
    changed_capacitors = [
        index
        for index in range(len(board.design.capacitor_farads))
        if (
            commissioned_configuration.capacitor_mask
            ^ recovered_configuration.capacitor_mask
        )
        & (1 << index)
    ]
    resistor_changed = (
        commissioned_configuration.resistor_index
        != recovered_configuration.resistor_index
    )
    mutation_distance = len(changed_capacitors) + int(resistor_changed)
    if fault_kind in {"open_capacitor", "capacitor_drift"}:
        fault_bypassed = not (
            recovered_configuration.capacitor_mask
            & (1 << int(fault["component_index"]))
        )
    else:
        fault_bypassed = (
            recovered_configuration.resistor_index
            != int(fault["component_index"])
        )
    fault["cutoff_shift_percent"] = cutoff_shift_percent
    memory_records_after = len(memory) if memory is not None else 0
    warm_started = any(
        evaluation.selection_method == "experience memory"
        for evaluation in commissioned.evaluations
    )

    session = {
        "schema_version": "0.4",
        "meta": {
            "backend": "digital_twin",
            "engine_version": "0.4.0",
            "cutoff_hz": cutoff_hz,
            "budget": budget,
            "seed": seed,
            "health_threshold_db": controller.health_threshold_db,
            "health_sweeps": health_sweeps,
            "total_measurements": board.measurement_count,
            "candidate_count": len(board.design.configurations()),
            "memory_records_before": memory_records_before,
            "memory_records_after": memory_records_after,
            "warm_started": warm_started,
        },
        "frequency_hz": frequencies.tolist(),
        "target_response_db": target.tolist(),
        "component_bank": {
            "resistor_ohms": list(board.design.resistor_ohms),
            "capacitor_nf": [
                capacitance * 1.0e9
                for capacitance in board.design.capacitor_farads
            ],
        },
        "stages": {
            "commissioned": {
                "configuration": commissioned_details,
                "response_db": commissioned_response.tolist(),
                "response_error_db": commissioned_error,
                "measurements": len(commissioned.evaluations),
            },
            "fault": {
                "configuration": faulty_details,
                "response_db": health.measured_response_db.tolist(),
                "response_error_db": fault_error,
                "signature_error_db": health.signature_error_db,
                "signature_ratio": (
                    health.signature_error_db / health.threshold_db
                ),
                "sweep_errors_db": list(health.sweep_errors_db),
                "health_sweeps": health.repeat_count,
                "detected": health.fault_detected,
                **fault,
            },
            "recovered": {
                "configuration": recovered_details,
                "response_db": recovered_response.tolist(),
                "response_error_db": recovered_error,
                "measurements": len(recovered.evaluations),
                "recovery_gain_db": recovery_gain_db,
                "mutation_distance": mutation_distance,
                "resistor_changed": resistor_changed,
                "changed_capacitors": changed_capacitors,
                "fault_bypassed": fault_bypassed,
            },
        },
        "search": {
            "commissioned": _search_payload(board, commissioned),
            "recovered": _search_payload(board, recovered),
        },
    }
    return seal_payload(session)


class VisualizerHandler(BaseHTTPRequestHandler):
    server_version = "DarwinBoard/0.4"
    experience_memory = ExperienceMemory()

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self._send_bytes(
                INDEX_PATH.read_bytes(),
                "text/html; charset=utf-8",
            )
            return
        if self.path == "/health":
            self._send_json({"status": "ok"})
            return
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:
        if self.path != "/api/session":
            self._send_json({"error": "not found"}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length) or b"{}")
            payload = build_session(
                cutoff_hz=float(request.get("cutoff_hz", 1_200.0)),
                budget=int(request.get("budget", 24)),
                seed=int(request.get("seed", 7)),
                fault_kind=str(
                    request.get("fault_kind", "open_capacitor")
                ),
                health_sweeps=int(request.get("health_sweeps", 3)),
                memory=self.experience_memory,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            self._send_json({"error": str(error)}, status=400)
            return
        self._send_json(payload)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self._send_bytes(body, "application/json; charset=utf-8", status)

    def _send_bytes(
        self,
        body: bytes,
        content_type: str,
        status: int = 200,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Darwin Board visualizer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    arguments = parser.parse_args()
    try:
        server = ThreadingHTTPServer(
            (arguments.host, arguments.port),
            VisualizerHandler,
        )
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            print(
                f"Port {arguments.port} is already in use. "
                f"Darwin Board may already be running at "
                f"http://{arguments.host}:{arguments.port}"
            )
            raise SystemExit(2) from None
        raise
    print(f"Darwin Board visualizer: http://{arguments.host}:{arguments.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
