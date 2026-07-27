# Darwin Board

![Darwin Board system](docs/assets/darwin-board-system.svg)

Darwin Board is an experiment in adaptive analog hardware. Give it a target
cutoff frequency and it searches the available component paths, remembers what
worked, watches for response changes, and reroutes around a degraded part.

The current circuit is a reconfigurable RC low-pass filter with 378 possible
resistor and capacitor combinations.

## How it works

1. Measure a small set of component configurations.
2. Use Bayesian optimization to choose the next useful experiment.
3. Activate the best measured configuration and store its response.
4. Detect persistent changes using three health sweeps.
5. Search for another healthy path and restore the target response.

Experience memory gives later searches a useful starting point. Every
measurement and decision is kept in the exported experiment trace.

## Current status

Milestone 0.3 includes:

- a tested digital twin
- an interactive tuning and recovery lab
- persistent configuration memory
- a USB serial adapter
- compiled firmware for a classic ESP32

The simulation benchmark covers 90 runs across three targets, ten component
tolerance profiles, and three fault types.

| Metric | Result |
| --- | ---: |
| Faults detected | 100% |
| Recoveries below 1 dB RMS error | 100% |
| Commissioned error, median / p95 | 0.091 / 0.297 dB |
| Recovered error, median / p95 | 0.156 / 0.578 dB |

These are simulation results. Physical validation is the next milestone. The
complete data is in [`benchmark-results.json`](benchmark-results.json).

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
- [`docs/linkedin-demo.md`](docs/linkedin-demo.md): short demonstration script

Keep the prototype at 3.3 V and isolate it from mains voltage and high-power
loads.
