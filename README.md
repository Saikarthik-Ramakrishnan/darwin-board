# Darwin Board

![Darwin Board system](docs/assets/darwin-board-system.svg)

Darwin Board is a self-tuning RC filter with reconfigurable component paths.
Set a cutoff frequency and the controller finds a matching circuit, checks a
backup for each active component, and monitors the response. If a component
fails, it tries the prepared backups before starting a fresh search.

The current digital twin covers 378 resistor and capacitor combinations.

## How it works

1. A Bayesian optimizer chooses promising configurations to measure.
2. The best configuration becomes the primary route.
3. Before activation, the controller measures backups that avoid each active
   component.
4. Three health sweeps confirm a persistent response change.
5. The controller probes its small backup reserve. It resumes the full search
   only if those routes miss the target.

Successful configurations seed later runs. The exported trace records every
measurement, choice, fault, and recovery.

## Current status

Version 0.5 is ready for breadboard validation. It includes:

- a tested digital twin and interactive lab
- persistent configuration memory
- measured backups for single-component faults
- fast recovery through pre-qualified routes
- SHA-256 sealed experiment traces
- a USB serial adapter and ESP32 firmware

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

These results come from simulation. Physical validation is the next milestone.
The full data is in [`benchmark-results.json`](benchmark-results.json), under
reference run `DB-09CA6BA28199`.

```bash
darwin-board-verify benchmark-results.json
```

## Run the lab

```bash
python3 -m pip install -e .
PYTHONPATH=src python3 -m darwin_board.visualizer_server
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765) and select **Run autonomous
cycle**. A second run shows how saved experience guides the search.

Tests and benchmark:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m darwin_board.benchmark \
  --seeds 10 \
  --output benchmark-results.json
```

## ESP32 build

The first prototype targets an ESP32-WROOM-32 or ESP32 DevKitC. GPIO25 applies
a voltage step and GPIO34 samples the filter response. Repeating the step at
different delays reconstructs the transient, which lets the ESP32 estimate the
RC time constant and cutoff frequency without an oscilloscope or external
waveform generator.

```bash
cd firmware/esp32
pio run
pio run --target upload
pio device monitor
```

The build guide, wiring, and parts list are in
[`docs/esp32-build.md`](docs/esp32-build.md).

## Documentation

- [`docs/architecture.md`](docs/architecture.md): system design
- [`docs/esp32-build.md`](docs/esp32-build.md): parts, wiring, and validation
- [`docs/serial-protocol.md`](docs/serial-protocol.md): ESP32 commands
- [`docs/milestone-0.5.md`](docs/milestone-0.5.md): recovery method and proof plan
- [`docs/linkedin-demo.md`](docs/linkedin-demo.md): demonstration script
- [`docs/hackathon-submission.md`](docs/hackathon-submission.md): submission notes

Keep the prototype at 3.3 V and isolate it from mains voltage and high-power
loads.
