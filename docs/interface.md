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

Each view starts with one action. The lab puts the response plot beside the
active circuit. The arena places a replay beneath its target control. Search
records, experiment settings, and benchmark methods stay in expandable sections.

The circuit map occupies its own view. It connects measured genotypes through
recorded parentage and confirmed deployment switches. Selecting a node reveals
components, training error, and connected circuits. No visual connection implies
a relationship that the experiment did not record.

## Review criteria

The graph must remain useful without dragging or relying on colour. The circuit
picker and relationship buttons provide keyboard navigation. Selected circuits
have an outline, deployed circuits use a larger node, and recovery edges use a
different stroke. Small screens stack the inspector below the graph. Reduced
motion preferences disable animated replay.

Keep the simulation label visible. Distinguish training fitness from deployment
error and preserve negative results in the comparison table.
