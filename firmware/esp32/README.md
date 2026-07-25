# ESP32 firmware

This firmware targets a classic ESP32 development board with the original
ESP32 chip. It uses GPIO25 as the internal DAC output and GPIO34 as an ADC1
measurement input.

The first breadboard does not require an AD9833. It repeatedly applies the same
voltage step and samples one delayed point from each response. Combining those
points reconstructs the transient at an effective resolution finer than a
single ADC conversion. A logarithmic fit estimates the RC time constant and
cutoff frequency.

## Build

Install PlatformIO, connect the ESP32, then run:

```bash
pio run
pio run --target upload
pio device monitor
```

## Smoke test

Wire a fixed RC low-pass filter:

```text
GPIO25 DAC ---- resistor ----+---- GPIO34 ADC
                             |
                          capacitor
                             |
                            GND
```

Send:

```text
ID?
STEP?
SWEEP 100 10000 32
STATUS?
```

The switching pins are already reserved in `src/main.cpp`. They can remain
unconnected during the fixed-filter measurement milestone.
