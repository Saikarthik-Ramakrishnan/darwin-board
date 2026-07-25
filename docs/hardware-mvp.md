# Hardware MVP: ESP32 Self-Tuning RC Filter

## Chosen path

- Controller: original ESP32-WROOM-32 or ESP32 DevKitC
- Construction: breadboard first
- Measurement: equivalent-time step response
- Initial band: roughly 300 Hz to 3 kHz
- Lab equipment: optional for the first milestone

This route uses the ESP32's internal DAC and ADC. It removes the external
waveform-generator dependency and creates a useful intermediate result before
college lab access.

## Functional architecture

```text
USB host
   |
ESP32 serial protocol
   |------------------------------|
   |                              |
Bayesian search              switch control
                                  |
GPIO25 DAC -> selectable R -> switched C bank -> GPIO34 ADC
                                  |
                         fitted step response
                                  |
                     cutoff and model-derived sweep
```

## Build in two stages

### Stage 1: fixed filter

Wire one 10 kΩ resistor and a 13.2 nF capacitor combination. The expected
cutoff is about 1.21 kHz. Use the firmware's `STEP?` command to reconstruct the
transient and estimate the cutoff.

### Stage 2: reconfigurable filter

Add six resistor choices and six switched capacitor branches:

- resistor taps: 2.2 kΩ, 4.7 kΩ, 10 kΩ, 22 kΩ, 47 kΩ, 100 kΩ
- capacitor branches: 1 nF, 2.2 nF, 4.7 nF, 10 nF, 22 nF, 47 nF

The capacitor branches form 63 non-empty combinations. Six resistor choices
produce 378 available configurations.

The firmware reserves GPIO21, GPIO22, and GPIO23 for resistor addressing, and
GPIO13, GPIO14, GPIO16, GPIO17, GPIO18, and GPIO19 for capacitor controls.
Suitable analog switches or small-signal MOSFET stages are still required
between these control pins and the analog network.

## Measurement strategy

For one equivalent-time measurement:

1. drive GPIO25 to a low DAC level,
2. let the filter settle,
3. apply a high DAC level,
4. take one GPIO34 sample after a chosen delay,
5. repeat the transient at logarithmically spaced delays,
6. use median samples to reject outliers,
7. fit the exponential response and report cutoff plus fit quality.

The ADC input remains on ADC1, which keeps the future option of using Wi-Fi for
telemetry. Every analog voltage must stay within the board's safe input range.

## Serial protocol

```text
ID?
STATUS?
SET R=2 C=0x15
STEP?
SWEEP 80 25000 32
```

Example responses:

```text
ID DARWIN_ESP32_1
STATUS R=2 C=0x15 FC_HZ=1187.42 FIT_R2=0.99710 TEMP_C=31.2
OK
STEP TAU_US=134.04 FC_HZ=1187.42 FIT_R2=0.99710
SWEEP_DB -0.02,-0.10,...,-26.48
```

The host `SerialDarwinBoard` adapter validates identities, timeouts, numeric
values, point counts, and firmware errors before data enters the optimizer.
The detailed grammar is in [`serial-protocol.md`](serial-protocol.md).

## Fault injection

The first reliable physical demonstration can use a switch in series with one
capacitor branch. Opening that branch produces a cutoff shift that the health
gate should detect. The controller then searches the remaining configurations
and stores the recovered path in experience memory.

Later fault fixtures can add:

- a switched parallel capacitor for controlled drift,
- a switched resistor for resistance drift,
- a stuck control line,
- a small supply change,
- local heating for temperature sensitivity.

## Acceptance criteria

- Fixed-RC cutoff within 10% of the expected value on three repeated runs.
- Exponential fit quality above 0.95 for the clean fixed filter.
- Tune to requested cutoffs of 500 Hz, 1 kHz, and 2 kHz.
- Detect an opened branch within two health cycles.
- Recover below 1 dB RMS model error through a different path.
- Record measurements, selected parts, recovery latency, temperature, and fit
  quality.

## Lab validation in three weeks

1. Compare the reconstructed transient with an oscilloscope capture.
2. Apply a direct sine sweep from a lab generator.
3. Measure model residuals across the full frequency range.
4. Calibrate DAC and ADC nonlinearity.
5. Repeat the physical fault and recovery benchmark.

The complete wiring and bring-up sequence is in
[`esp32-build.md`](esp32-build.md).

Operate at 3.3 V and share a common ground. Keep the prototype isolated from
mains voltage, high-power loads, and unprotected batteries.
