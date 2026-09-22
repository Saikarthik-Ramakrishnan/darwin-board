"""Plain Markdown export for Obsidian. Existing notes are never overwritten."""

from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote, urlencode
from zipfile import ZipFile, ZIP_DEFLATED

from .evidence import verify_payload
from .model import MVPDesign


def find_vault(registry: Path | None = None) -> Path | None:
    if registry is None:
        if sys.platform != "darwin":
            return None
        registry = Path.home() / "Library/Application Support/obsidian/obsidian.json"
    try:
        vaults = list(json.loads(registry.read_text())["vaults"].values())
        opened = [v for v in vaults if v.get("open")]
        choices = opened if opened else vaults
        if len(choices) != 1:
            return None
        path = Path(choices[0]["path"]).expanduser().resolve()
        return path if (path / ".obsidian").is_dir() else None
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def circuit_notes(run: dict) -> dict[str, str]:
    """Use scoped filenames and real wikilinks so native backlinks work."""
    if not isinstance(run, dict) or not verify_payload(run):
        raise ValueError("A verified arena run is required")
    if run.get("meta", {}).get("kind") != "adaptation-arena":
        raise ValueError("Only arena runs can be exported")
    run_id = run["evidence"]["run_id"]
    if not re.fullmatch(r"DB-[A-F0-9]{12}", run_id):
        raise ValueError("Invalid run identifier")
    nodes = run["circuit_graph"]["nodes"]
    if not 1 <= len(nodes) <= 256:
        raise ValueError("Invalid circuit count")
    design = MVPDesign()
    ids = {n["id"] for n in nodes}
    if len(ids) != len(nodes):
        raise ValueError("Duplicate circuit identifier")
    for value in ids:
        design.configuration_from_genotype(value)
    for n in nodes:
        if not set(n["parents"]).issubset(ids):
            raise ValueError("Unknown parent circuit")
    for edge in run["circuit_graph"]["edges"]:
        if edge["source"] not in ids or edge["target"] not in ids:
            raise ValueError("Unknown graph endpoint")

    prefix = f"Darwin Board/{run_id}"
    def link(identifier: str) -> str:
        return f"[[{prefix}/{identifier.replace(':', '-')}|{identifier}]]"

    notes = {}
    for n in nodes:
        identifier = n["id"]
        config = design.configuration_from_genotype(identifier)
        resistance, capacitance = design.nominal_values(config)
        properties = {
            "tags": ["darwin-board/circuit"] + (["darwin-board/deployed"] if n["deployed"] else []),
            "darwin_run": run_id, "genotype": identifier,
            "generation": int(n["generation"]), "stress_score_db": float(n["score_db"]),
            "archived": bool(n["archived"]), "deployed": bool(n["deployed"]),
        }
        # JSON is valid YAML and is natively supported in Obsidian properties.
        lines = ["---", json.dumps(properties, indent=2, allow_nan=False), "---", "",
                 f"# {identifier}", "", "Synthetic circuit measurement. Physical validation is pending.", "",
                 f"Resistance: {resistance:g} ohms. Capacitance: {capacitance * 1e9:g} nF.", "",
                 "Active branches: " + ", ".join(f"C{i + 1}" for i in config.active_capacitors(8)) + ".", "",
                 f"Training stress score: {float(n['score_db']):.3f} dB.", "", "## Parents", ""]
        lines += [f"- {link(p)}" for p in dict.fromkeys(n["parents"])] or ["Initial candidate or independent immigrant."]
        # Children are backlinks to this note, preserving directional parent links.
        children = [c["id"] for c in nodes if identifier in c["parents"]]
        lines += ["", "## Children", "", f"{len(children)} measured children. Open Backlinks to follow them."]
        recoveries = [e for e in run["circuit_graph"]["edges"] if e["kind"] == "recovery" and e["source"] == identifier]
        if recoveries:
            lines += ["", "## Recovery", ""]
            lines += [f"- Step {int(e['step']) + 1}: changed to {link(e['target'])}." for e in recoveries]
        deployed = [s for s in run["mission"] if s["genotype"] == identifier]
        if deployed:
            lines += ["", "## Deployment", "", "| Step | Error | Sweeps |", "| --- | ---: | ---: |"]
            lines += [f"| {int(s['step']) + 1} | {float(s['error_db']):.3f} dB | {len(s['probes'])} |" for s in deployed]
        lines += ["", "## Lab notes", "", ""]
        notes[f"{identifier.replace(':', '-')}.md"] = "\n".join(lines)
    summary = ["---", "tags: [darwin-board/run]", f"darwin_run: {run_id}", "---", "",
               f"# Darwin Board {run_id}", "", f"Target cutoff: {float(run['meta']['cutoff_hz']):g} Hz.", "",
               "This export contains simulated circuit measurements, parent links, and confirmed recovery paths.", "",
               "## Open the graph", "",
               "Open Graph view and use this search filter to isolate the circuit notes:", "",
               f'`path:"{prefix}" -file:Overview`', "",
               "For a focused view, open a circuit and run **Open local graph**. Backlinks show its children.", "",
               "Suggested colour groups: `tag:darwin-board/deployed` and `[archived:true]`.", "",
               "## Deployed circuits", ""]
    summary += [f"- {link(n['id'])}" for n in nodes if n["deployed"]]
    summary += ["", "## Evidence", "", f"SHA-256: `{run['evidence']['payload_sha256']}`", "",
                "Training fitness is separate from deployment error. No hardware reliability claim is implied.", ""]
    notes["Overview.md"] = "\n".join(summary)
    return notes


def notes_zip(run: dict) -> bytes:
    notes = circuit_notes(run)
    data = BytesIO()
    with ZipFile(data, "w", ZIP_DEFLATED) as archive:
        for name, content in notes.items():
            archive.writestr(f"Darwin Board/{run['evidence']['run_id']}/{name}", content)
    return data.getvalue()


def write_vault(run: dict, vault: Path) -> dict:
    notes = circuit_notes(run)
    vault = vault.resolve()
    if not (vault / ".obsidian").is_dir():
        raise ValueError("The selected folder is not an Obsidian vault")
    root = vault / "Darwin Board"
    destination = root / run["evidence"]["run_id"]
    if root.is_symlink() or destination.is_symlink():
        raise ValueError("Export folders cannot be symbolic links")
    root.mkdir(exist_ok=True)
    destination.mkdir(exist_ok=True)
    # Check the whole set before writing; never follow links inside an export.
    for name in notes:
        note = destination / name
        if note.is_symlink() or (note.exists() and not note.is_file()):
            raise ValueError("An export note is occupied by a link or directory")
    created = False
    # Complete interrupted exports while preserving every existing annotation.
    for name, content in notes.items():
        try:
            with (destination / name).open("x", encoding="utf-8") as handle:
                handle.write(content)
            created = True
        except FileExistsError:
            continue
    return {"created": created, "note_count": len(notes), "vault": vault.name,
            "run_id": run["evidence"]["run_id"],
            "uri": "obsidian://open?" + urlencode({"path": str(destination / "Overview.md"), "paneType": "tab"}, quote_via=quote)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export an arena run as linked Obsidian notes")
    parser.add_argument("run", type=Path)
    parser.add_argument("--vault", type=Path)
    args = parser.parse_args()
    vault = args.vault or find_vault()
    if vault is None:
        parser.error("No unambiguous local vault found. Supply --vault PATH.")
    print(json.dumps(write_vault(json.loads(args.run.read_text()), vault), indent=2))


if __name__ == "__main__":
    main()
