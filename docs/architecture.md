# Architecture

Darwin Board separates experimental policy from physical measurement. The same
control loop can operate a simulated circuit or a USB-connected ESP32
prototype.

## Complete loop

```text
requested cutoff
       |
       v
experience memory --> Bayesian tuner --> candidate component path
                            ^                       |
                            |                       v
                     measured error <------ pre-mortem qualification
                                                    |
                                      measured escape-route reserve
                                                    |
                                      simulator or ESP32 hardware
                                                    |
                                  response signature and health gate
                                                    |
                                  fault detected --> reserved reflex
```

The component bank contains six resistor choices and 63 non-empty parallel
capacitor combinations, giving 378 possible paths.

## Learning a configuration

Experience memory first offers configurations that performed well near the
requested cutoff. A nominal RC estimate and space-filling probes complete the
initial sample set. Later experiments minimize a lower confidence bound:

```text
predicted score - exploration weight × predicted uncertainty
```

This lets the tuner investigate both promising paths and uncertain regions.
Each evaluation records the selection method, prediction, uncertainty,
measured response error, and power penalty.

The selected configuration and its measured score are added to bounded
experience memory, which can be saved as JSON. A repeated request can therefore
begin with prior physical experience while still verifying the result on the
current board.

## Planning before failure

After the normal search, the controller performs a pre-mortem. It lists every
component used by the proposed primary route, then measures alternative routes
that avoid each one. The controller can accept up to 0.20 dB of primary-response
tradeoff when that produces stronger escape routes.

The resulting contingency atlas records:

- every active component that could interrupt the route,
- two measured fallback candidates for each failure point,
- the switching mutation required to reach each fallback,
- the worst preflight response error,
- single-fault coverage before activation.

The board therefore enters service with measured options already in reserve.
This planning uses real response measurements and does not require knowing
which component will fail.

## Genotype and evidence

Each switching state is represented as a compact hardware genotype. For
example, `R3:C010101` selects resistor path 3 and a six-bit capacitor mask.
Recovery records the Hamming distance between the commissioned and recovered
genotypes, the changed capacitor branches, and whether the failed path was
bypassed.

Experiment and benchmark exports use canonical JSON ordering and a SHA-256
digest. The digest produces a short run ID and can be checked with:

```bash
darwin-board-verify benchmark-results.json
```

## Measuring without an oscilloscope

The ESP32 firmware uses equivalent-time step sampling:

1. hold the DAC at a low level and let the RC network settle,
2. apply the same voltage step,
3. wait for one selected delay and take an ADC sample,
4. reset the circuit and repeat at another delay,
5. combine the delayed samples into one reconstructed transient,
6. fit the transient to estimate the RC time constant and cutoff.

For a first-order low-pass filter:

```text
V(t) = Vfinal - (Vfinal - Vinitial) × exp(-t / tau)
cutoff = 1 / (2 × pi × tau)
```

The reconstructed cutoff produces a model-derived response curve for the host
optimizer. This is suitable for the breadboard milestone. A direct sine sweep
in the college lab will later measure model mismatch and establish physical
accuracy.

## Health and recovery

After commissioning, the controller stores a fresh response as the healthy
signature. A health check performs three sweeps and compares their median
response with that signature. Requiring persistent evidence reduces false
alarms from individual noisy samples.

```text
healthy signature
       |
three measured sweeps
       |
median RMS signature error
       |
threshold gate
       |
probe reserved routes
       |
acceptable route? ---- no ----> adaptive search
       |
      yes
       |
new signature and memory record
```

The current lab covers three physical mechanisms:

| Scenario | Injected change | Expected response |
| --- | ---: | --- |
| Open capacitor branch | 100% loss of branch capacitance | Cutoff rises |
| Capacitor drift | 45% loss of branch capacitance | Cutoff rises |
| Resistor drift | 50% increase in active resistance | Cutoff falls |

The detector only uses measured response change. Fault labels exist in the
simulator so test results can compare the hidden cause with the observed
effect.

The first recovery action is a blind reflex. The controller probes the small
set of pre-qualified routes and selects the best measured response. A full
Bayesian search remains available when no reserved route meets the recovery
limit. In the current 90-run digital-twin benchmark, every tested fault was
handled by the reserve with a median of four probes, avoiding a median of 20
search measurements.

## Module boundaries

- `model.py` defines the circuit space and ideal responses.
- `board.py` provides the simulator and common board contract.
- `optimizer.py` selects experiments and records decision evidence.
- `memory.py` stores and ranks prior successful configurations.
- `evidence.py` seals and verifies exported experiment data.
- `resilience.py` builds the contingency atlas and ranks safe primary routes.
- `controller.py` manages commissioning, health checks, and recovery.
- `serial_board.py` validates the line protocol used by physical hardware.
- `visualizer_server.py` assembles complete experiments for the local lab.
- `benchmark.py` validates targets, tolerances, and faults.
- `firmware/esp32` measures transients and controls component selections.

## Hardware boundary

Both backends implement:

```python
measure_response_db(configuration, frequencies_hz) -> response_db
```

Switch control, ADC sampling, transient fitting, and calibration remain behind
that boundary. This keeps the optimizer and recovery policy independent of the
measurement electronics.

## Evidence ladder

1. **Complete:** deterministic tests of search, memory, fault detection, serial
   validation, and lab data.
2. **Complete:** 90-run digital-twin benchmark.
3. **Complete:** pre-mortem qualification and reserved-reflex benchmark.
4. **Next:** fixed-RC ESP32 step measurement on a breadboard.
5. **Then:** six-resistor and six-capacitor switch fabric.
6. **College lab:** direct frequency sweep and oscilloscope comparison.
7. **Final:** physical fault benchmark and compact PCB.
