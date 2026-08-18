# Darwin Board documentation

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
The full data is in [`benchmark-results.json`](../benchmark-results.json), under
reference run `DB-09CA6BA28199`.

```bash
darwin-board-verify benchmark-results.json
```

## Tests and benchmark

Run these commands from the project root:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m darwin_board.benchmark \
  --seeds 10 \
  --output benchmark-results.json
```

## ESP32 prototype

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

Keep the prototype at 3.3 V and isolate it from mains voltage and high-power
loads.

## Reference

- [`architecture.md`](architecture.md): system design
- [`esp32-build.md`](esp32-build.md): parts, wiring, and validation
- [`serial-protocol.md`](serial-protocol.md): ESP32 commands
- [`milestone-0.5.md`](milestone-0.5.md): recovery method and proof plan
- [`hardware-mvp.md`](hardware-mvp.md): physical prototype scope
- [`linkedin-demo.md`](linkedin-demo.md): demonstration script
- [`hackathon-submission.md`](hackathon-submission.md): submission notes
