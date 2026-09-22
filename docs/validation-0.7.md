# Validation record

## Fresh-seed evaluation

After the initial 30-run experiment, selection settings were frozen and
evaluated on seeds 100 through 109 at 600, 1200, and 2400 Hz. Every run used
96 circuit candidates, eighteen training sweeps per candidate, and 36 unseen
static cases. All thirty runs are included.

| Static selection | Mean error | 95th percentile | Within 0.5 dB |
| --- | ---: | ---: | ---: |
| Stress-selected archive winner | 0.379 dB | 0.882 dB | 73.24% |
| Nominal selection from the same population | 0.712 dB | 2.111 dB | 46.94% |
| Equal-budget random search | 0.483 dB | 1.087 dB | 58.80% |
| Existing Bayesian tuner | 0.657 dB | 1.513 dB | 53.06% |

The existing tuner has a smaller, 24-sweep training budget. Its row provides
context and does not establish superiority under equal measurement cost.
Stress selection shares the nominal method's candidate population. Random
search has the same training sweep budget as the archive.

In the separate eight-step deployment trials, adaptation passed 87.92% of
steps, compared with 42.08% for the commissioned circuit held fixed. A
same-size score-ranked reserve also passed 87.92%. The archive's mean mission
error was 0.426 dB, compared with 0.475 dB for that reserve. Archive diversity
helps some runs; a large universal advantage over score-ranked reserves has
not been established.

Raw results: [fresh-seed reference](benchmarks/arena-reference-benchmark.json).
These seeds are now inspected validation data, not a reusable untouched test
set. Future algorithm changes need another predeclared evaluation set.

## A refinement we rejected

A prototype screened 48 offspring before measuring eight. It used an ideal
loaded-RC prior, corrected by the five closest measured training residuals
in log resistance/capacitance space. Residual weights had a 0.3 length scale
and a denominator regularizer of 3. Five slots favoured the prediction, two
sought unoccupied archive niches, and one was sampled without ranking.

On the same fresh seeds, its static mean error rose from 0.379 to 0.441 dB.
Its deployment pass rate fell from 87.92% to 83.33%. The prototype was
removed from the runtime. The measurements remain in the
[rejected prototype record](benchmarks/arena-guided-benchmark.json).
That file is a historical experiment export; the current CLI cannot recreate
the removed prototype. Its mission faults target its own commissioned route,
so mission differences also include changes in which components were stressed.

This rejection matters: a more selective search can find circuits that fit
the two training profiles more closely while transferring less reliably.
The shipped search preserves broad parent sampling and circuit-family
diversity. Evaluation cases never feed into its ranking or archive updates.

## Interface and evidence

The main views expose a single run action. Settings and detailed records are
expandable. The circuit map uses only measured genotypes, recorded parents,
and confirmed switches. Selecting a node reveals the associated components
and measurements. The circuit picker supports keyboard navigation.

Browser checks cover a full tune/fault/recovery cycle, arena generation,
replay scrubbing, graph ancestry and recovery navigation, both themes, and
a 390 px viewport. Backend tests cover analytic limits, compound faults,
repeatable runs, evidence digests, the measurement budget, confirmation of
improvements, graph provenance, and malformed requests.

The release check passed 47 tests and 13 subtests. JavaScript syntax and
whitespace checks passed.

All results are from the synthetic small-signal model. Hardware calibration,
switching transients, and repeatable ESP32 measurements remain separate
validation tasks. This release is a demonstrable research prototype.
