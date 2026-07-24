# Architecture

Darwin Board separates experimental policy from physical measurement. The
optimizer asks for circuit responses through a small board protocol, so the
same control loop can run against the simulator or a USB-connected prototype.

## Runtime loop

```text
target response
      |
      v
Bayesian tuner ---- candidate configuration
      ^                        |
      |                        v
measured error <---- DarwinBoard interface
                               |
                     simulator or USB board
```

Commissioning evaluates a limited set of the 378 available component paths.
The first experiment follows the nominal RC model. Five space-filling probes
establish an initial data set. Later experiments minimize a lower confidence
bound:

```text
predicted score - exploration weight × predicted uncertainty
```

This balances promising configurations with uncertain regions of the hardware
space. Each evaluation records the selection method, predicted score,
uncertainty, measured response error, and power penalty.

## Health and recovery

After commissioning, the controller stores a fresh measured response as the
healthy signature. A health check performs three sweeps and uses the median
response and median signature error. This reduces sensitivity to isolated
measurement noise while keeping the detector simple enough to reproduce on a
microcontroller.

```text
healthy signature
       |
three measured sweeps
       |
median RMS signature error
       |
threshold gate
       |
reconfigure and retune
```

The lab currently exercises three physical mechanisms:

| Scenario | Injected change | Expected response |
| --- | ---: | --- |
| Open capacitor branch | −100% branch capacitance | Cutoff rises |
| Capacitor drift | −45% branch capacitance | Cutoff rises |
| Resistor drift | +50% active resistance | Cutoff falls |

Detection is evidence for a response change. The simulator also knows the
injected mechanism so the interface can compare the physical cause with the
measured cutoff shift.

## Module boundaries

- `model.py` defines the circuit space and ideal responses.
- `board.py` owns measurement behavior and injectable physical faults.
- `optimizer.py` chooses experiments and records decision evidence.
- `controller.py` manages commissioning, signature checks, and recovery.
- `visualizer_server.py` assembles a complete experiment for the local lab.
- `benchmark.py` validates the loop across targets, tolerances, and faults.

## Hardware boundary

The future serial adapter only needs to implement the `DarwinBoard`
measurement protocol:

```python
measure_response_db(configuration, frequencies_hz) -> response_db
```

Switch control, waveform generation, ADC sampling, and calibration stay behind
that boundary. The optimizer and recovery policy remain unchanged.

## Next technical milestone

1. Add a `SerialDarwinBoard` adapter with timeouts and protocol validation.
2. Calibrate the input and output measurement paths with a loopback fixture.
3. Store temperature and supply voltage with every response signature.
4. Compare simulated and physical response residuals on the same benchmark.
5. Move the health gate onto the microcontroller after the host loop is stable.
