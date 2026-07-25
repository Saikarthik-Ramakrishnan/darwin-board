# Darwin Board

![Darwin Board system](docs/assets/darwin-board-system.svg)

Darwin Board is a self-tuning analog circuit. It learns which component path
best matches a requested response, remembers useful configurations, detects
physical changes, and reroutes itself around degraded parts.

Milestone 0.3 includes a tested digital twin, an interactive experiment lab,
experience-guided tuning, a hardware serial adapter, and firmware for a classic
ESP32 development board.

## What makes it interesting

- **Closed-loop hardware search:** the software chooses each physical
  experiment from real response measurements.
- **Experience memory:** successful configurations become starting points for
  later searches.
- **Self-characterization without lab instruments:** the ESP32 repeatedly
  applies a voltage step and samples a different point on each response. Those
  points reconstruct the filter transient and estimate its cutoff.
- **Autonomous recovery:** a persistent response change triggers a search for a
  healthy alternate component path.
- **Traceable decisions:** every measurement, uncertainty estimate, health
  decision, and recovery step can be exported.

## Current evidence

The checked-in benchmark covers 90 simulated boards: three target cutoffs, ten
tolerance profiles, and three physical fault mechanisms.

| Metric | Result |
| --- | ---: |
| Faults detected | 100% |
| Recoveries below 1 dB RMS error | 100% |
| Commissioned error, median / p95 | 0.091 / 0.297 dB |
| Recovered error, median / p95 | 0.156 / 0.578 dB |
| Weakest fault evidence | 2.00× threshold |

Full run-level evidence is stored in
[`benchmark-results.json`](benchmark-results.json). These results validate the
algorithm in simulation. Physical measurements are the next evidence
milestone.

## Run the interactive lab

```bash
python3 -m pip install -e .
PYTHONPATH=src python3 -m darwin_board.visualizer_server
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765) and select **Run
autonomous cycle**. Run a second cycle to see experience memory guide the
search. The lab supports light and dark themes and exports the experiment as
JSON.

Run the tests and reproduce the benchmark:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m darwin_board.benchmark \
  --seeds 10 \
  --output benchmark-results.json
```

## ESP32 prototype

The first physical build targets the original ESP32-WROOM-32 or ESP32 DevKitC.
It uses:

- GPIO25 as the internal 8-bit DAC output
- GPIO34 as the ADC1 measurement input
- equivalent-time step sampling to estimate the RC time constant
- a breadboarded fixed RC filter before the full switch bank

No oscilloscope or external waveform generator is required for the first
measurement milestone. See [`docs/esp32-build.md`](docs/esp32-build.md) for the
wiring, bill of materials, and three-week validation path.

Firmware:

```bash
cd firmware/esp32
pio run
pio run --target upload
pio device monitor
```

Host probe:

```bash
python3 -m pip install -e '.[hardware]'
darwin-board-probe /dev/cu.usbserial-0001
```

## Project map

```text
src/darwin_board/
  model.py              Circuit model and component bank
  board.py              Simulator and hardware-facing protocol
  optimizer.py          Gaussian-process experimental search
  memory.py             Persistent configuration experience
  controller.py         Commissioning, health checks, and recovery
  serial_board.py       Validated USB serial hardware adapter
  visualizer_server.py  Local lab API and experiment assembly
  benchmark.py          Repeatable validation matrix
firmware/esp32/          ESP32 measurement and switch-control firmware
visualizer/index.html   Interactive experiment lab
tests/                  Controller, memory, serial, and lab tests
docs/                   Architecture, build guide, protocol, and demo script
```

Start with [`docs/architecture.md`](docs/architecture.md) for the complete
loop, [`docs/esp32-build.md`](docs/esp32-build.md) for the prototype, and
[`docs/linkedin-demo.md`](docs/linkedin-demo.md) for a clear public demo.

Operate the prototype at 3.3 V. Keep every signal within the ESP32 input range
and isolate it from mains voltage, high-power loads, and unprotected batteries.
