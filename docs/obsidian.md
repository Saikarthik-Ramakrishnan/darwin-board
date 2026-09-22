# Obsidian

Each measured circuit becomes a Markdown note. Parent links describe ancestry;
recovery links record confirmed route changes. Obsidian's Graph view, Local
graph, and Backlinks work with these notes without a plugin.

## Export a run

1. Start the local dashboard and run an arena trial, or select **Build map**.
2. In **Circuit map**, select **Send to Obsidian**.
3. Select **Open run in Obsidian** to read the overview.

On macOS, Darwin Board detects a single open vault, or the only configured
vault. If the choice is ambiguous or no vault is found, it downloads a ZIP.
Extract the ZIP's `Darwin Board` folder into your vault.

Notes live under `Darwin Board/<run-id>/`. Existing notes and vault settings
are left untouched. Repeating an export adds missing notes only. Each run is
a snapshot; edits in Obsidian do not change the dashboard or its measurements.

## Read the graph

The overview includes a ready-to-copy Graph view filter for that run. For
example, replace `<run-id>` here with the exported identifier:

```text
path:"Darwin Board/<run-id>" -file:Overview
```

Open any circuit's **Local graph** to explore its neighbours. **Backlinks**
include its children and incoming recovery links. Notes contain component
values, generation, training stress score, deployment errors, and space for
lab observations. Tags identify deployed circuits; the `archived` property
identifies retained candidates.

In the dashboard, node size follows link count. Hover highlights connections,
**Local graph** shows direct neighbours, and the circuit picker works without
dragging. Dashed edges distinguish recovery from ancestry. Native Obsidian
renders both as ordinary links; the notes retain their meaning in separate
sections.

All exported measurements are simulated. A sealed record detects accidental
changes to the payload; it does not establish physical accuracy.

## Choose a vault explicitly

```bash
PYTHONPATH=src python3 -m darwin_board.arena --seed 7 --budget 96 --output arena-run.json
PYTHONPATH=src python3 -m darwin_board.obsidian arena-run.json --vault "/path/to/vault"
```

Obsidian references: [Graph view](https://obsidian.md/help/plugins/graph),
[internal links](https://obsidian.md/help/links), and [open-note URIs](https://obsidian.md/help/uri).
