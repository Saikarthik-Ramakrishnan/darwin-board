# Milestone 0.6: measured evolution

Version 0.6 gives Darwin Board an explicit evolutionary search policy and
expands the digital switch fabric from 378 to 2,040 routes.

## Hardware chromosomes

The component bank now has eight resistor alleles and eight capacitor genes.
Every valid combination receives one canonical genotype such as
`R010:C00101010`. The mapping is bijective and round-trip tested across all
2,040 routes.

## Evolution loop

1. Measure an initial population from memory, the RC prior, and exploration.
2. Keep the strongest measured routes as survivors.
3. Select parents through measured-fitness tournaments.
4. Cross their capacitor genes and inherit one resistor allele.
5. Mutate resistor and capacitor genes at bounded rates.
6. Inject random immigrants to preserve population diversity.
7. Use the regularized Bayesian ensemble to choose which children to measure.
8. Repeat until the physical measurement budget is exhausted.

Every generation records its parents, measured offspring, survivors, best
genotype, score improvement, diversity, crossover count, mutation count, and
immigrant count. These records are included in the sealed experiment export
and displayed in the lab.

## Expanded ESP32 fabric

The physical design uses a three-bit analog multiplexer for eight resistor
paths and an eight-output shift register for eight capacitor-switch controls.
This keeps the ESP32 control cost at six GPIOs while exposing the full 2,040
route catalog.

Physical measurements remain the next evidence boundary. The evolutionary
results currently come from the digital twin.
