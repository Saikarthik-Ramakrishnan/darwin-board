# ESP32 firmware

Firmware for an original ESP32 development board. GPIO25 supplies the internal
DAC output and GPIO34 reads the filter through ADC1.

The ESP32 repeats a voltage step and samples the response at a different delay
each time. Those samples reconstruct the RC transient. A logarithmic fit then
estimates the time constant and cutoff frequency. The first breadboard needs no
AD9833 or oscilloscope.

## Build

Install PlatformIO and connect the board:

```bash
pio run
pio run --target upload
pio device monitor
```

## Fixed-filter test

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

The switching pins are reserved in `src/main.cpp`. Leave them unconnected for
this fixed-filter test.
