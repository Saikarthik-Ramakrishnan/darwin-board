# Darwin Board

Darwin Board is an experimental platform for self-tuning analog hardware.
Milestone 0 controls a reconfigurable RC low-pass filter and adapts it from
measured frequency-response data.

## How it works

1. Set a target cutoff frequency.
2. Measure candidate resistor and capacitor configurations.
3. Use a Gaussian-process surrogate to select the next experiment.
4. Activate the configuration with the lowest response error.
5. Store its measured response as a health signature.
6. Detect component changes and run a new search when required.

The simulator includes component tolerance, measurement noise, capacitor
faults, and resistor drift. Its interface is designed for a later USB-connected
breadboard.

## Results

Thirty simulations covered ten component-tolerance profiles and target cutoffs
of 500 Hz, 1 kHz, and 2 kHz.

| Metric | Result |
| --- | ---: |
| Open-capacitor faults detected | 30 / 30 |
| Worst initial response error | 0.331 dB RMS |
| Worst recovered response error | 0.753 dB RMS |
| MVP error limit | 1.000 dB RMS |

## Run

```bash
PYTHONPATH=src python3 -m darwin_board.demo
```

The demo tunes a 1.2 kHz filter, opens an active capacitor branch, detects the
response change, and recovers with a new configuration. Add `--trace` to save
the run:

```bash
PYTHONPATH=src python3 -m darwin_board.demo --trace demo-trace.json
```

Run the tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Layout

```text
src/darwin_board/
  model.py       Circuit configurations and target response
  board.py       Simulator and future hardware interface
  optimizer.py   Surrogate-guided experimental search
  controller.py  Commissioning, monitoring, and recovery
  demo.py        End-to-end fault-and-recovery demonstration
tests/
  test_recovery.py
docs/
  hardware-mvp.md
```

## Next milestone

Build the low-voltage RC network, waveform source, switching bank, and
measurement path described in
[`docs/hardware-mvp.md`](docs/hardware-mvp.md). A serial adapter will connect
the existing controller to the physical board.

## Safety

Operate the prototype at 3.3 V or 5 V. Keep it isolated from mains voltage,
high-power loads, and unprotected battery packs.
