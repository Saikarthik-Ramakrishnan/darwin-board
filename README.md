# Darwin Board

![Darwin Board system](docs/assets/darwin-board-system.svg)

Darwin Board is an experiment in adaptive analog hardware. Give it a target
cutoff frequency and it searches the available component paths, remembers what
worked, tests escape routes before activation, watches for response changes,
and reacts through a pre-qualified backup path.

The current circuit is a reconfigurable RC low-pass filter with 378 possible
resistor and capacitor combinations.

## How it works

1. Use Bayesian optimization to measure promising configurations.
2. Run a pre-mortem and qualify escape routes for every active component.
3. Activate a configuration with complete single-fault coverage.
4. Detect persistent changes using three health sweeps.
5. Probe the reserved routes and restore the target response.

Experience memory gives later searches a useful starting point. Every
measurement and decision is kept in the exported experiment trace.

## Current status

Milestone 0.5 includes:

- a tested digital twin
- an interactive tuning and recovery lab
- persistent configuration memory
- a measured single-fault contingency atlas
- pre-qualified reflex recovery before a new search
- SHA-256 sealed experiment exports
- a USB serial adapter
- compiled firmware for a classic ESP32

The simulation benchmark covers 90 runs across three targets, ten component
tolerance profiles, and three fault types.

| Metric | Result |
| --- | ---: |
| Faults detected | 100% |
| Recoveries below 1 dB RMS error | 100% |
| Recoveries completed by reserved reflex | 100% |
| Recovery probes, median | 4 |
| Search measurements avoided, median | 20 |
| Commissioned error, median / p95 | 0.092 / 0.263 dB |
| Recovered error, median / p95 | 0.048 / 0.302 dB |

These are simulation results. Physical validation is the next milestone. The
complete data is in [`benchmark-results.json`](benchmark-results.json).
Reference run: `DB-09CA6BA28199`.

```bash
darwin-board-verify benchmark-results.json
```

## Run the lab

```bash
python3 -m pip install -e .
PYTHONPATH=src python3 -m darwin_board.visualizer_server
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765) and select **Run
autonomous cycle**. Run it again to see the search use earlier experience.

Tests and benchmark:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m darwin_board.benchmark \
  --seeds 10 \
  --output benchmark-results.json
```

## ESP32 build

The first prototype targets an original ESP32-WROOM-32 or ESP32 DevKitC.
GPIO25 applies a DAC voltage step and GPIO34 samples the filter response. The
firmware repeats that step at different delays, reconstructs the transient, and
estimates the RC time constant and cutoff frequency.

This gives the breadboard a useful self-measurement mode before oscilloscope
and waveform-generator access.

```bash
cd firmware/esp32
pio run
pio run --target upload
pio device monitor
```

The build guide, wiring, and parts list are in
[`docs/esp32-build.md`](docs/esp32-build.md).

## Documentation

- [`docs/architecture.md`](docs/architecture.md): control loop and software
  boundaries
- [`docs/esp32-build.md`](docs/esp32-build.md): breadboard plan and lab
  validation
- [`docs/serial-protocol.md`](docs/serial-protocol.md): ESP32 command protocol
- [`docs/milestone-0.5.md`](docs/milestone-0.5.md): pre-mortem algorithm,
  evidence, and physical proof contract
- [`docs/linkedin-demo.md`](docs/linkedin-demo.md): short demonstration script
- [`docs/hackathon-submission.md`](docs/hackathon-submission.md): Devpost copy,
  demo plan, and judging checklist

Keep the prototype at 3.3 V and isolate it from mains voltage and high-power
loads.
