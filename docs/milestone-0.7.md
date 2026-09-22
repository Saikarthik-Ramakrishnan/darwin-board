# Milestone 0.7: adaptation arena

The arena evolves an archive of RC circuit genotypes under environmental
stress, freezes it, and tests adaptation on a fresh simulated board. Open the
**Arena** tab in the lab, choose a target, and select **Run trial**. The seed,
route budget, and JSON export are under **Options**.
The header's **Walkthrough** explains the lab, replay, arena, and map through
a separate simulation. Your previous run returns when you finish or close it.

## What to inspect

- The replay shows the active circuit and response. Scrub to a failure or
  play through all eight conditions.
- **Experiment record** contains the archive, generation history, and
  unseen-board comparison, including cases where another method wins.
- **Circuit map** is an Obsidian-style graph of every measured genotype.
  Select a node to inspect its components, parents, children, and deployment
  error. Dashed edges show confirmed recovery switches. **View in replay**
  opens the selected circuit's first deployment step.
- **Export run** saves a sealed JSON record, including every graph edge.
- **Send to Obsidian** exports linked circuit notes into a dedicated vault
  folder, or downloads them when no vault is found. See the [Obsidian guide](obsidian.md).

The graph has no invented similarity links. A coloured archive node means
the circuit won its resistor/capacitor-count niche; it does not guarantee
acceptable error. Training stress scores and deployment error are separate.

## Run from the terminal

```bash
PYTHONPATH=src python3 -m darwin_board.arena --seed 7 --budget 96 --output arena-run.json
PYTHONPATH=src python3 -m darwin_board.evidence arena-run.json
PYTHONPATH=src python3 -m darwin_board.arena --benchmark --seeds 10 --output arena-benchmark.json
PYTHONPATH=src python3 -m darwin_board.arena --benchmark --seeds 10 --seed-start 100 --output arena-fresh.json
```

## Twin assumptions

The small-signal model uses a series resistor and switch feeding parallel
capacitor branches. Each branch has series resistance. A finite load,
leakage resistance, and shunt parasitic capacitor share the output node.

For angular frequency `w`, the output admittance is:

```text
Y = 1/Rload + 1/Rleak + jw*Cparasitic + sum(jw*Ci / (1 + jw*Ci*Rbranch))
H = 1 / (1 + Rseries*Y)
```

The synthetic defaults are 65 ohms switch resistance, 3 ohms additional
branch resistance, 18 pF shunt capacitance, and 20 Mohms leakage at 25 C.
Resistor scales are lognormal with a 0.025 log standard deviation. Capacitor
scales combine a shared 0.025 batch term and a 0.04 individual term.
Resistor temperature coefficients span 40–220 ppm/C; capacitor coefficients
span -1600–600 ppm/C. Capacitor wear reduces capacitance by an assigned
2–18% at age 1. Switch resistance changes by 0.4% per C in this model;
leakage conductance doubles every 25 C above reference temperature.

These are explicit stress-test assumptions. They are not specifications for
the user's components. Age is a normalized stress parameter, not elapsed
time or a remaining-life estimate. Thermal noise, ADC quantization, harmonic
distortion, voltage dependence, dielectric absorption, and switching
transients are outside the model. The generated response is settled AC
magnitude; it does not certify the old ESP32 transient fit for this richer
network.

## Selection and evaluation boundaries

Training uses two component profiles and nine habitats: one reference case
and the combinations of -10/65 C, 47 kohm/1 Mohm load, and age 0/0.6. Each
candidate is measured on all eighteen cases. Its score averages the mean
error and the mean of the five largest errors. Frequencies cover one decade
on either side of the requested cutoff with 32 logarithmic points.

Initial selection includes the closest ideal-RC route for each resistor.
Random candidates complete the 16-route initial population. Eight offspring
follow per generation, using uniform archive-parent selection, the existing
crossover and mutation operators, and 25% requested immigration. If breeding
cannot fill the batch, further immigrants complete it. Each genotype is
evaluated at most once per training method.

The holdout uses twelve random habitats spanning -20–80 C, 30 kohm–10 Mohm,
and age 0–0.9, across three unseen manufacturing profiles. These cases
include modest extrapolation beyond the training corners. They are generated
after selection and never used for reselection. A fresh seed samples both
the training and testing profiles again; repeated experimentation on a seed
still makes it development data rather than an untouched final test.

The mission uses another unseen component profile. The open capacitor is the
largest nominal capacitor in the commissioned route. The second fault changes
that route's resistor to 1.8 times its previous resistance. Faults persist
through the final step. This is a scripted stress trial, not a random sample
of all possible failures.

The adaptation policy gets noisy response measurements and ambient
temperature, load, and age information. Hardware currently does not supply
all of these inputs. The simulator's hidden fault labels and noiseless
response are used only by the trial runner and final scorer.

Two measurements gate the current path. Up to three reserve routes are
probed, and one extra measurement confirms a proposed replacement. Both
replacement errors must beat both incumbent errors by three times the
per-frequency noise standard deviation. This is a conservative heuristic,
not a calibrated confidence interval. Failed recovery is reported directly;
the arena does not silently restart a full search after exhausting its six
probes.

## Controls

The static comparison includes nominal selection on the evolved population,
the stress-selected winner, uniform random search with the same training
budget, and the original Bayesian tuner with 24 reference sweeps. Nominal
selection shares the evolved population's cost; it is an objective ablation,
not a standalone nominal-search benchmark.

The mission compares the adaptive archive with the same commissioned circuit
held fixed and an equally sized reserve of the lowest-scoring measured
routes. Both adaptive methods use the same ranking rule, probe limit, test
board, and scripted faults. The score-ranked reserve may preserve several
routes from one niche; the archive preserves one per niche. This control
tests the archive descriptor's value separately from having a reserve at all.

Full protocol, results, prior art, and research limits are in
[`prior-art-and-direction.md`](prior-art-and-direction.md). These experiments
do not guarantee freedom from overfitting or physical reliability.

The [validation record](validation-0.7.md) includes a rejected search
refinement, the fresh-seed comparison, and the interface checks.
