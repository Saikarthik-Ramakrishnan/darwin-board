# Darwin Board: prior art and development direction

Darwin Board 0.7 investigates whether a population of reconfigurable RC
circuits can remain useful as operating conditions change. It adds a
loaded-circuit model, selection across multiple environments, a repertoire of
different component routes, and a bounded adaptation experiment. The evidence
supports an improvement in this synthetic benchmark. It does not establish a
new optimization algorithm, a first demonstration of adaptive electronics,
or performance on physical hardware.

## Existing solutions

The review covers evolutionary electronics, programmable analog products,
analog optimization, quality-diversity search, simulation transfer, and
redundant circuit recovery. Sources were reviewed on 10 September 2026.
Searches included academic papers, manufacturer documentation, simulator
documentation, and published patent documents. Abstract-only evidence is
identified below; it supports broad method comparisons, not reproduction of
the authors' experimental results.

| Existing work | What it already establishes | Consequence for Darwin Board |
| --- | --- | --- |
| Raman and Wagner, *The evolvability of programmable hardware* (2011) | Digital circuit genotypes can form connected neutral networks; functionally equivalent circuits can differ substantially in robustness. | Genetic representation, mutation, and robustness are established ideas. Retaining alternatives deserves study, but requires measured comparisons. [1] |
| Anadigm AN231E04, datasheet Rev. 1.2 (2014 copyright) | Programmable analog blocks support filtering and dynamic reconfiguration through shadow configuration memory. Applications include calibration and aging compensation. | An analog circuit that changes configuration is not a new product category. This manufacturer document was read through a datasheet mirror because the current product page returned no text. [2] |
| Visan et al., *Automated Circuit Sizing with Multi-objective Optimization based on Differential Evolution and Bayesian Inference* (2022) | Evolutionary methods and Bayesian inference have already been combined for analog sizing. | The existing Darwin tuner should be described as an implementation of related ideas. Its hybrid optimizer alone is a weak novelty claim. Comparison based on the paper's abstract. [3] |
| Shi et al., *RobustAnalog* (2022) | Analog optimization can include manufacturing and operating variation through multitask learning. | Optimizing across operating conditions is established. A new contribution needs a specific circuit platform, protocol, or demonstrated tradeoff. Comparison based on the abstract. [4] |
| Kong et al., *PVTSizing* (DAC 2024) | PVT-robust analog synthesis combines batch optimization and learning methods. | Robust circuit sizing is an active research area. A small RC project should compete on transparency and accessible experimentation rather than breadth of analog synthesis. [5] |
| Mouret and Clune, *Illuminating search spaces by mapping elites* (2015) | MAP-Elites retains strong solutions in different user-defined niches. | The repertoire mechanism in 0.7 is MAP-Elites-inspired. It is not an invented evolutionary algorithm. [6] |
| Cully et al., *Robots that can adapt like animals* (2015) | Robots can prepare a behavior repertoire and use a few experiments to adapt after damage without identifying the damage first. | Preparing alternatives and probing them after failure has strong prior art outside electronics. The circuit embodiment must earn its value experimentally. [7] |
| Wang et al., *POET* (2019) | Environments and their solutions can develop together in an expanding curriculum. | Open-ended coevolution is established and substantially broader than the finite stress suite implemented here. Darwin Board 0.7 does not implement POET. [8] |
| Tobin et al., *Domain Randomization* (2017) | Variation in simulation can support transfer to real robotic tasks. | Randomized twins are a useful training strategy. This paper does not establish that an uncalibrated RC model transfers to an ESP32 board. [9] |
| ngspice documentation | Parameter sweeps, Monte Carlo analysis, and circuit simulation are available in mature tools. | A Python frequency-response model is convenient for interactive experiments. SPICE cross-checking remains a necessary next layer of validation. [10] |
| Texas Instruments, SCDA028A application brief | Switch on-resistance and capacitance affect signal accuracy. | Switches and loading must appear in the model if route quality is to mean more than matching an ideal RC product. [11] |
| *Self-repair of analog circuits using redundancy*, WO2025250332A1 (2025) | A published patent document describes redundant analog elements and error-driven recovery. | Broad descriptions of self-repair overlap existing disclosures. This is a technical prior-art observation, with no conclusion about legal claim scope or patentability. [12] |

## The gap worth testing

The existing project selected circuits mainly for one reference response. Its
simulated board had manufacturing tolerance and injectable component faults,
but the nominal transfer function remained an ideal single-pole RC network.
Two routes with the same RC product therefore had nearly the same behavior.
That hides an important engineering distinction: high-impedance and
low-impedance realizations can react differently to loading and parasitic
elements.

The selected direction makes those differences observable. A circuit genotype
still maps directly to the eight-resistor, eight-capacitor switch fabric. Its
fitness is now measured across several operating conditions and manufacturing
profiles. Evolution retains alternatives in separate niches, and a deployment
policy tests whether those alternatives remain useful on an unseen board.

The research question is concrete: **does preserving physically distinct
routes improve adaptation under a limited measurement budget?** The
implementation also asks a simpler question: does selecting for stress
performance reduce error on unseen operating conditions? These questions have
separate controls because stress selection and archive diversity can produce
different effects.

## Implemented additions

### Environmental circuit model

The new twin evaluates a complex small-signal network containing the selected
resistor, switch resistance, parallel capacitor branches with series
resistance, an output load, leakage, and shunt parasitic capacitance. Each
synthetic manufacturing profile has correlated capacitor tolerance, resistor
tolerance, individual temperature coefficients, and capacitor wear rates.
Fault scenarios may open capacitor branches and drift a resistor at the same
time.

This model retains the existing measurement interface. Its component and
parasitic values are explicit assumptions, not measurements of the intended
ESP32 build. The equations reduce to the previous ideal RC response when the
additional effects are removed. Unit tests check that limit, finite output
loading, and compound faults against separate closed-form expressions.

### Stress-selected circuit repertoire

The initial population includes nominally promising routes for every resistor
allele and random routes. Subsequent generations use crossover, mutation, and
immigration from the existing evolutionary engine. Parents are sampled from
the archive so less common circuit families can reproduce.

Each route receives 18 training sweeps: nine habitats on each of two synthetic
boards. Fitness gives equal weight to the average RMS response error and the
mean error in the worst quarter of cases. This penalizes brittle solutions
while preserving the target frequency-response objective.

An 8-by-8 archive stores one elite for each resistor choice and active
capacitor count. These descriptors have a physical interpretation and remain
compatible with the current genotype. A populated cell records a measured
candidate; it does not certify that the candidate is within tolerance. The
lab shows its score, worst training error, generation, and parents.

### Frozen-archive adaptation trial

After training, the archive is frozen. Static comparisons use three fresh
manufacturing profiles and twelve previously unused operating points. No
test response updates fitness, ancestry, or the archive.

A separate eight-step deployment replay uses another unseen board. It changes
temperature, output load, and wear, then opens the largest active capacitor
and drifts the commissioned resistor. The intervention policy receives
operating-condition information and noisy response measurements. It uses the
nearest training habitat to rank reserve routes and does not read fault
identities or the noiseless scoring response.

Each step allows at most six sweeps. Two sweeps check the current path. When
needed, the policy probes up to three alternatives and confirms the most
promising replacement with another sweep. Both replacement measurements must
beat the incumbent by a noise margin before a switch is accepted. The export
records unsuccessful attempts and residual error as well as recoveries.

## Evaluation and controls

The reference benchmark uses targets of 600, 1200, and 2400 Hz and seeds 0
through 9, with 96 candidate routes per evolutionary run. All 30 runs are
included. Settings stayed fixed across the matrix.

| Static selection | Mean error | 95th-percentile error | Cases within 0.5 dB |
| --- | ---: | ---: | ---: |
| Nominal selection from the evolved candidates | 0.624 dB | 1.915 dB | 60.1% |
| Stress-selected elite | 0.368 dB | 0.817 dB | 77.4% |
| Random search using the stress objective | 0.393 dB | 0.883 dB | 73.6% |
| Existing Bayesian tuner at its reference habitat | 0.518 dB | 1.214 dB | 64.5% |

These are 1,080 synthetic static cases. Nominal and stress selection share the
same evolved candidates, isolating the selection criterion within that
population. Random search receives the same 1,728 training sweeps as the
evolutionary experiment. The existing tuner receives its usual 24 sweeps;
that comparison is contextual and does not imply equal computational cost.

| Deployment policy | Mean error across runs | Steps within 0.5 dB |
| --- | ---: | ---: |
| Keep the commissioned route fixed | 2.255 dB | 49.6% |
| Probe the diverse archive | 0.413 dB | 87.5% |
| Probe a same-size reserve chosen only by score | 0.459 dB | 86.3% |

The static stress-selected winner improves aggregate mean error by about 41%
relative to nominal selection, but improves the per-run mean in only 16 of 30
runs. Archive adaptation improves mean error over the score-ranked reserve in
only 3 runs, with 27 ties and no worse run in this matrix. Its aggregate advantage
over that reserve is small. The strongest
current evidence supports stress selection and measured adaptation; a large,
general benefit from this particular diversity descriptor remains unproven.

These observations are descriptive. Cases share profiles, targets, and
operating points, so they should not be treated as 1,080 independent physical
experiments. The benchmark does not compare against all-route exhaustive
search, modern analog synthesis tools, or a full online retuner at an equal
total budget.

Reproducible results and every included run appear in
[`arena-benchmark.json`](benchmarks/arena-benchmark.json). The run export includes
individual static errors, mission probes, selected genotypes, and provenance.
SHA-256 verifies the integrity of an export; it does not authenticate the
origin of the measurements.

## What can be claimed

Darwin Board now provides an inspectable experiment linking hardware
genotypes, environmental selection, diversity, and bounded recovery on a
small reconfigurable analog fabric. The project-specific contribution is the
integrated implementation and its evaluation protocol. The search found
strong conceptual precedents for every main technique. It did not establish
that this exact implementation has appeared elsewhere, and it cannot support
a claim of worldwide novelty.

A useful public description is: “Darwin Board evolves a population of RC
circuits in a digital twin, then tests how that population adapts to unseen
environments and component failures.” Quantitative claims should name the
synthetic benchmark and report the comparison method and budget.

## Directions deferred

Automatic environment generation is a plausible extension, informed by POET,
but a finite RC bank and a hand-built model provide weak grounds for an
open-ended-evolution claim. A better next experiment would vary the stress
curriculum while reserving an independent final test set.

Active circuit identification could select measurement frequencies that
distinguish competing explanations for drift. It would become useful after
the twin is calibrated and measurement error is characterized. Adding a
diagnosis label before establishing identifiability would exaggerate what a
single response sweep can reveal.

Safe transition planning is another candidate. Current experiments measure
settled responses only. They cannot establish glitch-free switching, charge
injection behavior, or transient safety. A transient model and physical
measurements should precede any such claim.

The next evidence step is to measure switch resistance, load impedance,
branch parasitics, and temperature response on the actual board, then
cross-check the network in SPICE. The final transfer trial should freeze
algorithm settings before acquiring new hardware measurements.

## Sources

1. Raman and Wagner. [The evolvability of programmable hardware](https://pmc.ncbi.nlm.nih.gov/articles/PMC3033018/), 2011.
2. Anadigm. [AN231E04 Datasheet, Rev. 1.2](https://datasheet.ciiva.com/18032/getdatasheetpartid-416090-18032060.pdf), manufacturer document, 2014 copyright; pp. 1–3, hosted by a datasheet mirror.
3. Visan et al. [Automated Circuit Sizing with Multi-objective Optimization based on Differential Evolution and Bayesian Inference](https://arxiv.org/abs/2206.02391), 2022, abstract.
4. Shi et al. [RobustAnalog: Fast Variation-Aware Analog Circuit Design Via Multi-task RL](https://arxiv.org/abs/2207.06412), 2022, abstract.
5. Kong et al. [PVTSizing: A TuRBO-RL-Based Batch-Sampling Optimization Framework for PVT-Robust Analog Circuit Synthesis](https://yibolin.com/publications/papers/ANALOG_DAC2024_Kong.pdf), DAC 2024.
6. Mouret and Clune. [Illuminating search spaces by mapping elites](https://arxiv.org/abs/1504.04909), 2015.
7. Cully, Clune, Tarapore, and Mouret. [Robots that can adapt like animals](https://www.nature.com/articles/nature14422), Nature, 27 May 2015, abstract and available figure descriptions.
8. Wang et al. [Paired Open-Ended Trailblazer (POET)](https://arxiv.org/abs/1901.01753), 2019, abstract.
9. Tobin et al. [Domain Randomization for Transferring Deep Neural Networks from Simulation to the Real World](https://arxiv.org/abs/1703.06907), 2017, abstract.
10. ngspice project. [Special features](https://ngspice.sourceforge.io/extras.html), current documentation, accessed 10 September 2026.
11. Texas Instruments. [SCDA028A application brief](https://www.ti.com/document-viewer/lit/html/SCDA028A/GUID-A72BBECD-A462-479F-9EA0-E59A51A2CFF9), accessed 10 September 2026.
12. [WO2025250332A1: Self-repair of analog circuits using redundancy](https://patents.google.com/patent/WO2025250332A1/en), published patent application, 2025.
