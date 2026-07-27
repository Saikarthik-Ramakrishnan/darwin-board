# Hack The Limit submission

## Positioning

**Project:** Darwin Board
**Tagline:** A circuit that learns, remembers, and reroutes itself.

Primary award targets:

1. Boldest Idea Award
2. Limit Breaker Award
3. Real Impact Award

## Problem statement

Analog circuits are usually designed around fixed component paths. Component
tolerance, drift, and failure can move the response away from its intended
behavior. Diagnosing the change often requires lab equipment and manual
reconfiguration.

## Solution

Darwin Board treats circuit configuration as an experimental search problem.
It measures candidate resistor and capacitor paths, uses Bayesian optimization
to choose each next test, stores the best measured response, and monitors that
response over time. When the behavior changes, it searches the remaining paths
and restores the requested cutoff.

Each configuration has a compact hardware genotype such as
`R3:C010101`. Recovery is recorded as a mutation from the original genotype.
Every exported run also carries a deterministic run ID and SHA-256 digest so
the evidence can be checked after export.

## Key features

- Search across 378 hardware configurations
- Experience memory for later tuning runs
- Median-aggregated health checks
- Recovery around capacitor and resistor faults
- Hardware genotype and recovery mutation distance
- SHA-256 sealed experiment exports
- Interactive light and dark lab
- ESP32 firmware and validated serial protocol
- Equivalent-time step measurement without an external waveform generator

## Target users

- engineers prototyping resilient sensors and edge devices
- embedded-systems students studying adaptive hardware
- maintainers of low-cost electronics where manual calibration is difficult

## Technologies

Python, NumPy, Gaussian-process search, HTML, CSS, JavaScript, ESP32 Arduino,
PlatformIO, USB serial, ADC sampling, DAC step generation, and JSON evidence
exports.

## Current evidence

- 90 simulated runs
- three requested cutoff frequencies
- ten component-tolerance profiles
- three physical fault models
- 100% fault detection
- 100% recovery below 1 dB RMS response error
- 19 automated tests
- ESP32 firmware compiled for `esp32dev`

The benchmark is simulation evidence. Physical measurements should be labeled
separately.

## 90-second demo

### 0 to 12 seconds

Show the empty lab and set a 1.2 kHz target.

> Most analog circuits keep one fixed component path. Darwin Board can search
> 378 paths and learn which one best matches the response I ask for.

### 12 to 30 seconds

Select **Run autonomous cycle** and pause on the tuned response.

> A Bayesian tuner chooses which hardware configuration to measure next. It
> stores the best response and remembers the successful hardware genotype.

### 30 to 48 seconds

Show the injected fault and threshold evidence.

> I can open a capacitor branch or drift a resistor. Three health sweeps confirm
> that the response change is persistent.

### 48 to 66 seconds

Show the recovered curve, new genotype, and mutation count.

> The controller searches the remaining paths, mutates the switching
> configuration, and restores the requested response.

### 66 to 78 seconds

Export the proof file and show its run ID.

> The complete run is exported with a SHA-256 digest, so the measurements and
> decisions can be checked later.

### 78 to 90 seconds

Show the ESP32 firmware and fixed-RC breadboard if available.

> The physical version uses an ESP32 DAC step and delayed ADC samples to
> estimate the filter cutoff before I have access to an oscilloscope.

## Judging checklist

| Criterion | Current proof | Highest-value addition |
| --- | --- | --- |
| Execution, 30% | Tests, benchmark, compiled firmware, CI | Record one real ESP32 transient |
| Originality, 25% | Adaptive circuit, memory, genotype recovery | Show the same target on two component paths |
| Impact, 20% | Resilient low-cost electronics use case | Name one concrete sensor or edge-device scenario |
| UX, 15% | One-click lab, dark mode, proof export | Capture a clean 1080p demo |
| Presentation, 10% | Diagram, concise README, evidence data | Add three annotated screenshots |

## Submission assets

- repository: `https://github.com/Saikarthik-Ramakrishnan/darwin-board`
- one tuning screenshot
- one fault-detection screenshot
- one recovery screenshot showing the genotype change
- one 60 to 90 second video
- physical breadboard photo and serial output when available

Make the repository public before judging if the rules require judges to open
the link.

## Claims

Safe now:

- hardware-ready digital twin
- simulated autonomous recovery
- compiled ESP32 firmware
- sealed and reproducible experiment exports

After breadboard validation:

- measured ESP32 cutoff
- physical fault detection
- physical recovery

## Deadline check

The Devpost overview currently displays **August 29, 2026 at 11:45 PM PDT**.
The rules page still lists **July 29, 2026 at 9:00 PM PDT**. Use the earlier
deadline until the organizer confirms that the rules page is stale.
