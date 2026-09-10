# ESP32 breadboard build

## Decision

Build the measurement path on a breadboard before designing a PCB. The ADC
noise, switch resistance, grounding, and transient timing need physical
measurements before the layout is frozen.

The firmware targets a classic ESP32-WROOM-32 or ESP32 DevKitC. Check the chip
or module marking before wiring. ESP32-C3 and ESP32-S3 boards do not provide the
same GPIO25 DAC path assumed here.

## Why an AD9833 is optional for the first build

The classic ESP32 has two 8-bit DAC channels. DAC channel 1 is connected to
GPIO25. The first milestone uses that DAC to apply a voltage step to the RC
network.

The ADC cannot capture a fast transient with oscilloscope-like timing through
simple blocking reads. Darwin Board uses equivalent-time sampling instead:

1. Discharge the capacitor.
2. Apply the same step.
3. Read one ADC point after a controlled delay.
4. Repeat with a different delay.
5. Combine the points into one reconstructed transient.
6. Fit the exponential response and estimate the time constant.

For a first-order RC filter:

```text
cutoff frequency = 1 / (2 × pi × time constant)
```

This gives the ESP32 a self-characterization mode that needs no external signal
generator or oscilloscope. A direct sine sweep in the college lab will later
validate the model-derived response.

## First fixed-filter build

Use the configuration already present in the simulator:

- resistor: 10 kΩ
- capacitors in parallel: 1 nF + 2.2 nF + 10 nF
- total capacitance: 13.2 nF
- nominal cutoff: approximately 1.21 kHz

### Wiring

```text
ESP32 GPIO25
      |
    10 kΩ
      |
      +-------- ESP32 GPIO34
      |
   13.2 nF
      |
     GND
```

GPIO34 is an ADC1 input. ADC1 is preferred because ADC2 access can conflict
with Wi-Fi on the original ESP32.

### Minimum parts

| Quantity | Part |
| ---: | --- |
| 1 | Classic ESP32-WROOM-32 development board |
| 1 | Breadboard |
| 1 | 10 kΩ resistor |
| 1 each | 1 nF, 2.2 nF, and 10 nF capacitors |
| 1 | 100 nF ceramic decoupling capacitor |
| several | Jumper wires |
| 1 | Data-capable USB cable |

Keep all signals within the ESP32 supply range. Do not connect GPIO34 to a
voltage above 3.3 V.

## Firmware

The PlatformIO project is in `firmware/esp32`.

```bash
cd firmware/esp32
pio run
pio run --target upload
pio device monitor
```

Smoke-test commands:

```text
ID?
STEP?
SWEEP 100 10000 32
STATUS?
```

A good first transient should report:

- a cutoff reasonably close to 1.21 kHz;
- a fit R² above 0.90;
- stable results over five repeated `STEP?` commands.

## Reconfigurable stage

After the fixed filter is stable:

1. Add a 74HC4051-class analog multiplexer for eight resistor choices.
2. Add eight capacitor branches through two quad analog-switch ICs.
3. Drive their control inputs from an eight-output 74HC595-class shift register.
4. Connect the reserved switching GPIOs from the firmware.
5. Measure the effective resistance of every closed switch path.
6. Add that resistance to the digital twin.
7. Pre-qualify two escape routes for every component in the active path.
8. Open one capacitor branch and compare reflex latency with a fresh search.

The current firmware reserves:

| Function | GPIO |
| --- | --- |
| DAC step output | 25 |
| ADC response input | 34 |
| Resistor multiplexer address | 21, 22, 23 |
| Capacitor shift-register data | 13 |
| Capacitor shift-register clock | 14 |
| Capacitor shift-register latch | 16 |

## Lab validation in three weeks

Use the oscilloscope and waveform generator to:

1. Measure the true sine-sweep response.
2. Compare its cutoff with the ESP32 transient estimate.
3. Quantify ADC and switching errors.
4. Update the simulator with the measured residuals.
5. Repeat the 90-run benchmark against the physical board.

The important result will be the simulation-to-hardware gap, including the
parts of the circuit the digital twin failed to predict.

## Official ESP32 references

- [ESP32 DAC documentation](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/dac.html)
- [ESP32 ADC documentation](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/adc/index.html)
- [ESP32 ADC oneshot driver](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/peripherals/adc/adc_oneshot.html)
