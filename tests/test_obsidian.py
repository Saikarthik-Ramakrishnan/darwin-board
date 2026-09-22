from io import BytesIO
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from darwin_board.arena import build_arena
from darwin_board.evidence import seal_payload, verify_payload
from darwin_board.obsidian import circuit_notes, find_vault, notes_zip, write_vault
from darwin_board.visualizer_server import VisualizerHandler


class ObsidianTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = build_arena(seed=7, budget=24)

    def test_every_wikilink_resolves_to_an_exported_note(self):
        notes = circuit_notes(self.payload)
        self.assertEqual(len(notes), 25)
        prefix = f"Darwin Board/{self.payload['evidence']['run_id']}/"
        for name, content in notes.items():
            self.assertNotIn(":", name)
            for link in re.findall(r"\[\[([^]|]+)(?:\|[^]]+)?\]\]", content):
                self.assertTrue(link.startswith(prefix))
                self.assertIn(link[len(prefix):] + ".md", notes)
        with ZipFile(BytesIO(notes_zip(self.payload))) as archive:
            self.assertEqual(set(archive.namelist()), {prefix + name for name in notes})

    def test_existing_notes_and_settings_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / ".obsidian").mkdir()
            settings = vault / ".obsidian" / "graph.json"
            settings.write_text('{"search":"my existing graph"}')
            result = write_vault(self.payload, vault)
            note = vault / "Darwin Board" / result["run_id"] / "Overview.md"
            note.write_text("Personal annotations")
            repeated = write_vault(self.payload, vault)
            self.assertTrue(result["created"])
            self.assertFalse(repeated["created"])
            self.assertEqual(note.read_text(), "Personal annotations")
            self.assertEqual(settings.read_text(), '{"search":"my existing graph"}')
            self.assertTrue(result["uri"].startswith("obsidian://open?path="))

    def test_rejects_tampering_and_path_injection(self):
        bad = json.loads(json.dumps(self.payload))
        bad["circuit_graph"]["nodes"][0]["id"] = "../../outside"
        with self.assertRaises(ValueError):
            circuit_notes(bad)
        with self.assertRaises(ValueError):
            circuit_notes(seal_payload(bad))
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / ".obsidian").mkdir()
            (vault / "Darwin Board").symlink_to(vault / ".obsidian", target_is_directory=True)
            with self.assertRaises(ValueError):
                write_vault(self.payload, vault)

    def test_incomplete_export_adds_only_missing_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / ".obsidian").mkdir()
            destination = vault / "Darwin Board" / self.payload["evidence"]["run_id"]
            destination.mkdir(parents=True)
            (destination / "Overview.md").write_text("My annotations")
            result = write_vault(self.payload, vault)
            self.assertTrue(result["created"])
            self.assertEqual(len(list(destination.glob("*.md"))), 25)
            self.assertEqual((destination / "Overview.md").read_text(), "My annotations")

    def test_existing_note_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / ".obsidian").mkdir()
            destination = vault / "Darwin Board" / self.payload["evidence"]["run_id"]
            destination.mkdir(parents=True)
            (destination / "Overview.md").symlink_to(vault / "private.md")
            with self.assertRaises(ValueError):
                write_vault(self.payload, vault)

    def test_registry_requires_one_unambiguous_vault(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / ".obsidian").mkdir()
            registry = vault / "registry.json"
            entry = {"path": str(vault), "open": True}
            registry.write_text(json.dumps({"vaults":{"a":entry}}))
            self.assertEqual(find_vault(registry), vault.resolve())
            registry.write_text(json.dumps({"vaults":{"a":entry, "b":entry}}))
            self.assertIsNone(find_vault(registry))
            registry.write_text('{"vaults": []}')
            self.assertIsNone(find_vault(registry))

    def handler(self, path, payload, origin="http://127.0.0.1:8766", content_type="application/json"):
        body = json.dumps(payload).encode()
        handler = VisualizerHandler.__new__(VisualizerHandler)
        handler.path = path
        handler.server = Mock(server_port=8766)
        handler.headers = {"Content-Length":str(len(body)), "Origin":origin, "Content-Type":content_type}
        handler.rfile = BytesIO(body)
        handler._send_json = Mock()
        handler._send_bytes = Mock()
        return handler

    def test_vault_endpoint_blocks_cross_origin_writes(self):
        for origin, kind in (("https://evil.example", "application/json"),
                             ("http://127.0.0.1:9999", "application/json"),
                             ("http://127.0.0.1:8766", "text/plain"), ("", "application/json")):
            handler = self.handler("/api/obsidian", {"run": self.payload}, origin, kind)
            with patch("darwin_board.visualizer_server.write_vault") as write:
                handler.do_POST()
                write.assert_not_called()
            self.assertEqual(handler._send_json.call_args.kwargs["status"], 403)

    def test_zip_fallback_when_no_vault_is_found(self):
        handler = self.handler("/api/obsidian", {"run":self.payload})
        with patch("darwin_board.visualizer_server.find_vault", return_value=None):
            handler.do_POST()
        data, kind = handler._send_bytes.call_args.args
        self.assertEqual(kind, "application/zip")
        with ZipFile(BytesIO(data)) as archive:
            self.assertEqual(len(archive.namelist()), 25)

    def test_tutorial_has_sealed_results_and_does_not_use_shared_memory(self):
        handler = self.handler("/api/tutorial", {})
        original = VisualizerHandler.experience_memory
        handler.do_POST()
        payload = handler._send_json.call_args.args[0]
        self.assertTrue(verify_payload(payload["lab"]))
        self.assertTrue(verify_payload(payload["arena"]))
        self.assertIs(VisualizerHandler.experience_memory, original)
        self.assertEqual(payload["lab"]["meta"]["memory_records_before"], 0)

    def test_logo_and_tutorial_assets_are_served(self):
        for path, kind in (("/docs/assets/darwin-board-logo-transparent.png", "image/png"),
                           ("/tutorial.js", "text/javascript"), ("/tutorial.css", "text/css")):
            handler = VisualizerHandler.__new__(VisualizerHandler)
            handler.path = path
            handler._send_bytes = Mock()
            handler.do_GET()
            self.assertTrue(handler._send_bytes.call_args.args[1].startswith(kind))


if __name__ == "__main__":
    unittest.main()
