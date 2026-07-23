# Hardware MVP: Self-Tuning RC Filter

## Goal

Construct a safe, low-voltage board that can select a resistance, select a
parallel combination of capacitors, inject a known sine wave, measure the
output amplitude, and expose those operations over USB serial.

The host controller will request a configuration and a list of frequencies.
The board will return measured gain values. It does not need to understand the
optimizer.

## Functional architecture

```text
USB host
   |
MCU or FPGA controller
   |-----------------------|
   |                       |
frequency source      switch control
   |                       |
input buffer -> programmable R -> switched C bank -> output buffer
                                                   |
                                                  ADC
```

## Recommended first implementation

- Raspberry Pi Pico/Pico 2 or a classic ESP32 development board
- AD9833 waveform-generator module for repeatable sine sweeps
- MCP41010 digital potentiometer, or a resistor bank selected through an
  analog multiplexer
- Six film/C0G capacitor branches controlled through low-leakage analog
  switches
- Rail-to-rail dual op-amp such as MCP6002 for input/output buffering
- MCU ADC for synchronous amplitude measurement
- Breadboard, decoupling capacitors, resistors, and USB cable

An FPGA can replace the MCU later, but a microcontroller shortens the first
measurement milestone. The optimizer remains on the host computer initially.

## Component-bank values

The simulator currently assumes:

- resistor taps: 2.2 kΩ, 4.7 kΩ, 10 kΩ, 22 kΩ, 47 kΩ, 100 kΩ
- capacitor branches: 1 nF, 2.2 nF, 4.7 nF, 10 nF, 22 nF, 47 nF

Capacitors are connected in parallel, giving 63 non-empty combinations. With
six resistor choices, the MVP has 378 possible configurations.

## Minimal serial protocol

Human-readable commands are sufficient for the first board:

```text
ID?
SET R=2 C=0x15
MEASURE 1000
SWEEP 80 25000 32
STATUS?
```

Example responses:

```text
ID DARWIN_MVP_1
OK
GAIN_DB -2.91
SWEEP_DB 0.00,-0.01,...,-26.40
STATUS VCC_MV=3298 TEMP_C=31.2
```

The future `SerialDarwinBoard` class will translate the existing Python board
interface into these commands.

## Measurement strategy

For every frequency:

1. program the AD9833,
2. wait for the filter to settle,
3. sample several waveform periods,
4. remove ADC offset,
5. estimate amplitude using sine/cosine correlation,
6. divide by a separately measured input amplitude,
7. return gain in dB.

Synchronous correlation is more robust than using peak-to-peak ADC readings.

## Built-in fault injection

Add a transistor or spare analog switch in series with at least one capacitor
branch. A button or command can force that branch open. This creates a
repeatable demonstration without physically pulling wires from a live
breadboard.

Later versions can simulate:

- capacitor drift by adding a second switched capacitor,
- resistor drift by switching a parallel resistor,
- ADC bias,
- stuck switch control,
- supply-voltage variation.

## First acceptance criteria

- Tune to requested cutoffs of 500 Hz, 1 kHz, and 2 kHz.
- Achieve less than 1 dB RMS response error over the measured frequency grid.
- Detect an opened active capacitor branch with no more than two health sweeps.
- Restore less than 1 dB RMS error through a different configuration.
- Report total measurements, recovery latency, and selected components.

## Decisions needed before hardware integration

1. Which controller is available: ESP32, Raspberry Pi Pico, or FPGA board?
2. Is an oscilloscope or USB logic analyzer available for validation?
3. Should the first board be breadboarded or designed immediately as a PCB?
4. What frequency range matters for the first demonstration?

Keep the prototype at 3.3 V or 5 V. Do not connect it to mains or high-power
loads.

