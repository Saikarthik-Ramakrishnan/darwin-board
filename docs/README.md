# Darwin Board documentation

## How it works

1. Every one of the 2,040 component routes receives a binary genotype.
2. Measured survivors breed children through crossover and mutation.
3. A physics-informed Bayesian model ranks which children to measure.
4. Before activation, the controller measures backups that avoid each active
   component.
5. Three health sweeps confirm a persistent response change.
6. The controller probes its small backup reserve. It resumes the full search
   only if those routes miss the target.

Successful configurations seed later runs. The exported trace records every
measurement, choice, fault, and recovery.

## Current status

Version 0.6 is ready for breadboard validation. It includes:

- a bijective catalog of 2,040 hardware genotypes
- measured evolutionary generations with selection, crossover, and mutation
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
| Recovery probes, median | 3 |
| Search measurements avoided, median | 21 |
| Commissioned error, median / p95 | 0.131 / 0.226 dB |
| Recovered error, median / p95 | 0.028 / 0.122 dB |

These results come from simulation. Physical validation is the next milestone.
The full data is in [`benchmark-results.json`](../benchmark-results.json), under
reference run `DB-103989A4C74D`.

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
- [`milestone-0.6.md`](milestone-0.6.md): evolutionary search and expanded fabric
- [`hardware-mvp.md`](hardware-mvp.md): physical prototype scope
- [`linkedin-demo.md`](linkedin-demo.md): demonstration script
- [`hackathon-submission.md`](hackathon-submission.md): submission notes
