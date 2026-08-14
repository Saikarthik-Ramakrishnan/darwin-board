# Milestone 0.5: failure pre-mortem

Milestone 0.5 changes when recovery begins. Darwin Board now prepares for a
component failure before the circuit enters service.

## The loop

```text
Bayesian search
      |
candidate primary route
      |
failure pre-mortem
      |
measure routes that avoid each active component
      |
activate with a qualified reserve
      |
health change detected
      |
probe the reserve
      |
acceptable route? --> yes: activate it
      |
      no
      |
adaptive search
```

The pre-mortem can trade up to 0.20 dB of primary response accuracy for a route
with stronger measured escape options. Each active resistor or capacitor must
have a fallback below the 1 dB recovery limit before it counts as covered.

Fault recovery remains blind to the simulator's hidden fault label. The
controller measures the reserved routes after a health alert and chooses the
best response. This matches the intended hardware behavior because the ESP32
does not need component-level diagnosis.

## Digital-twin evidence

The benchmark covers 90 runs across three target cutoffs, ten component
tolerance profiles, and three fault mechanisms.

| Metric | Result |
| --- | ---: |
| Single-fault contingency coverage | 100% |
| Fault detection | 100% |
| Recovery below 1 dB RMS error | 100% |
| Recovery through the reserved reflex | 100% |
| Recovery probes, median | 4 |
| Search measurements avoided, median | 20 |
| Recovered error, median / p95 | 0.048 / 0.302 dB |

These are simulation results. The benchmark does not establish physical
reliability.

## Physical proof contract

The hardware milestone should reproduce the same sequence:

1. Measure the primary and reserved routes on the intact breadboard.
2. Open one active capacitor branch.
3. Detect the response change through repeated ESP32 measurements.
4. Probe only the reserved routes.
5. Activate a route below the 1 dB model-error limit.
6. Compare the reflex measurement count and latency with a new search.

The strongest result will be the gap between the digital-twin prediction and
the measured breadboard response, reported without hiding the mismatch.
