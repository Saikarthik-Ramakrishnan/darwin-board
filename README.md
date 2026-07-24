# Darwin Board

Darwin Board is a self-tuning analog hardware platform. It measures a circuit,
learns which component configuration best matches a requested response, stores
a healthy signature, detects physical changes, and reroutes around degraded
components.

Milestone 0.2 models a reconfigurable RC low-pass filter with 378 possible
component paths. A Gaussian-process optimizer searches that space from measured
frequency-response data.

## Control loop

1. Request a target cutoff frequency.
2. Measure a small set of resistor and capacitor configurations.
3. Use a lower-confidence-bound policy to choose each next experiment.
4. Activate the lowest-score configuration and store its health signature.
5. Aggregate three health sweeps to detect a persistent response change.
6. Search the remaining hardware paths and recover the target response.

The simulator includes component tolerance, measurement noise, capacitor
opens, capacitor drift, and resistor drift. The same controller interface is
intended for a USB-connected physical board.

## Evidence

The checked-in benchmark covers 90 runs: three target cutoffs, ten tolerance
profiles, and three fault mechanisms.

| Metric | Result |
| --- | ---: |
| Faults detected | 100% |
| Recoveries below 1 dB RMS error | 100% |
| Commissioned error, median / p95 | 0.091 / 0.297 dB |
| Recovered error, median / p95 | 0.156 / 0.578 dB |
| Weakest fault evidence | 2.00× threshold |

Full run-level data is available in
[`benchmark-results.json`](benchmark-results.json).

## Run the lab

```bash
PYTHONPATH=src python3 -m darwin_board.visualizer_server
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). Choose a target, search
budget, and fault scenario, then step through tuning, injection, and recovery.
The lab supports light and dark themes and exports the complete experiment
trace as JSON.

Run the terminal demonstration:

```bash
PYTHONPATH=src python3 -m darwin_board.demo --trace demo-trace.json
```

Reproduce the benchmark:

```bash
PYTHONPATH=src python3 -m darwin_board.benchmark \
  --seeds 10 \
  --output benchmark-results.json
```

Run the test suite:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Project map

```text
src/darwin_board/
  model.py              Circuit model and component bank
  board.py              Simulator and hardware-facing protocol
  optimizer.py          Gaussian-process experimental search
  controller.py         Commissioning, health checks, and recovery
  visualizer_server.py  Local lab API and experiment assembly
  benchmark.py          Repeatable validation matrix
  demo.py               Terminal demonstration
visualizer/index.html   Interactive test bench
tests/                  Controller, lab, and benchmark tests
docs/                   Architecture and hardware plan
```

See [`docs/architecture.md`](docs/architecture.md) for the software loop and
[`docs/hardware-mvp.md`](docs/hardware-mvp.md) for the first physical build.

## Physical milestone

The next milestone connects the controller to a low-voltage RC network with a
waveform source, switch bank, buffered measurement path, and USB serial bridge.
Acceptance requires tuning at 500 Hz, 1 kHz, and 2 kHz, detection within two
health cycles, and recovery below 1 dB RMS error.

Operate the prototype at 3.3 V or 5 V. Keep it isolated from mains voltage,
high-power loads, and unprotected battery packs.
