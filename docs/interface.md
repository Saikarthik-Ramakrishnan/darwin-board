# Interface

The circuit and its response take precedence. A visitor should be able to run
an experiment, see a recovery, and inspect the circuit responsible without
reading the methodology first.

## Design

- Light canvas `#f8fafb`, white plotting surface, ink `#20242a`.
- Muted text `#64717b`, measured paths `#19776b`, dividers `#dfe5e7`.
- Avenir Next with native sans-serif fallbacks and tabular numerals.
- Dark surfaces retain the same hierarchy and use brighter trace colours.
- Sentence-case labels, restrained borders, no decorative metric cards.
- Centred project title with the repository logo and a compact walkthrough control.

Each view starts with one action. The lab puts the response plot beside the
active circuit. The arena places a replay beneath its target control. Search
records, experiment settings, and benchmark methods stay in expandable sections.

The circuit map occupies its own view. It connects measured genotypes through
recorded parentage and confirmed deployment switches. Selecting a node reveals
components, training error, and connected circuits. No visual connection implies
a relationship that the experiment did not record. Node size reflects link count.
Hovering highlights neighbours; **Local graph** isolates the selected circuit
and its direct connections. The same circuits export as native Obsidian notes.

## Walkthrough

Twelve steps follow commissioning, failure, recovery, replay, arena trials,
and the circuit map. The demo uses real simulation results and isolated
experience memory. Closing it restores the previous run, tab, controls,
expanded records, graph selection, and scroll position. It never exports notes
automatically.

## Review criteria

The graph must remain useful without dragging or relying on colour. The circuit
picker and relationship buttons provide keyboard navigation. Selected circuits
have an outline, deployed circuits have a distinct fill, and recovery edges use a
different stroke. Small screens stack the inspector below the graph. Reduced
motion preferences disable animated replay.

Keep the simulation label visible. Distinguish training fitness from deployment
error and preserve negative results in the comparison table.
