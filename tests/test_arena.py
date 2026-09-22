import json
from io import BytesIO
import unittest
from unittest.mock import Mock

import numpy as np

from darwin_board.arena import (ArenaEvaluation, CircuitArchive, build_arena, evolve_archive,
                                benchmark_arena, probe_archive, stress_score, training_environments)
from darwin_board.environment import OperatingPoint
from darwin_board.evidence import verify_payload
from darwin_board.model import Configuration, MVPDesign
from darwin_board.visualizer_server import VisualizerHandler


class ArenaTests(unittest.TestCase):
    def test_tail_risk_discourages_a_single_bad_habitat(self):
        consistent = stress_score(np.array([0.3] * 8))
        brittle = stress_score(np.array([0.1] * 7 + [1.6]))
        self.assertLess(consistent, brittle)
        with self.assertRaises(ValueError):
            stress_score(np.array([np.nan]))

    def test_niches_preserve_diversity_and_replace_only_with_improvement(self):
        archive = CircuitArchive()
        def entry(config, score):
            return ArenaEvaluation(config, (score,), score, 0, (), 0)
        self.assertTrue(archive.add(entry(Configuration(0, 1), 0.2)))
        self.assertFalse(archive.add(entry(Configuration(0, 2), 0.4)))
        self.assertTrue(archive.add(entry(Configuration(1, 1), 0.5)))
        self.assertTrue(archive.add(entry(Configuration(0, 2), 0.1)))
        self.assertEqual(len(archive.cells), 2)
        self.assertEqual(archive.cells[(0, 1)].configuration, Configuration(0, 2))

    def test_budget_and_parent_provenance(self):
        design = MVPDesign()
        archive, evaluations, history, boards, frequencies = evolve_archive(design, cutoff_hz=1200, seed=5, budget=48)
        self.assertEqual(len(evaluations), 48)
        self.assertEqual(len({e.configuration for e in evaluations}), 48)
        self.assertEqual(sum(b.measurement_count for b in boards), 48 * 18)
        seen = set()
        for gen in history:
            for child in gen["children"]:
                self.assertTrue(set(child["parents"]).issubset(seen))
            seen.update(c["genotype"] for c in gen["children"])
        scores = [g["best_score_db"] for g in history]
        self.assertTrue(all(b <= a for a, b in zip(scores, scores[1:])))
        self.assertEqual(len(frequencies), 32)
        self.assertGreater(len(archive.cells), 8)

    def test_probe_policy_cannot_read_hidden_truth_or_fault_identity(self):
        class MeasuredOnly:
            design = MVPDesign()
            point = OperatingPoint()
            measurement_noise_db = 0.01
            def __init__(self):
                self.count = 0
            def measure_response_db(self, config, frequencies):
                self.count += 1
                return np.full(len(frequencies), 1.0 if config.resistor_index == 0 else 0.1)
            def response_db(self, *args):
                raise AssertionError("Controller accessed scoring truth")
        b = MeasuredOnly()
        current, backup = Configuration(0, 1), Configuration(1, 2)
        archive = (ArenaEvaluation(backup, (0.1,) * 18, 0.1, 0, (), 0),)
        result = probe_archive(b, archive, current, np.array([10., 100.]), np.zeros(2), cutoff_hz=1200)
        self.assertEqual(result["configuration"], backup)
        self.assertEqual(b.count, 4)

    def test_lucky_probe_is_rejected_by_confirmation(self):
        class NoisyProbe:
            design = MVPDesign()
            point = OperatingPoint()
            measurement_noise_db = 0.01
            def __init__(self):
                self.samples = iter([1.0, 1.0, 0.1, 1.1])
            def measure_response_db(self, config, frequencies):
                return np.full(len(frequencies), next(self.samples))
        current, backup = Configuration(0, 1), Configuration(1, 2)
        archive = (ArenaEvaluation(backup, (0.1,) * 18, 0.1, 0, (), 0),)
        result = probe_archive(NoisyProbe(), archive, current, np.array([10.]), np.zeros(1), cutoff_hz=1200)
        self.assertEqual(result["configuration"], current)

    def test_sealed_reproducible_and_frozen_before_holdout(self):
        result = build_arena(seed=2, budget=24)
        self.assertTrue(verify_payload(result))
        json.dumps(result, allow_nan=False)
        self.assertEqual(result, build_arena(seed=2, budget=24))
        archive, _, _, _, _ = evolve_archive(MVPDesign(), cutoff_hz=1200, seed=2, budget=24)
        self.assertEqual({e.configuration for e in archive.elites()},
                         {Configuration(**e["configuration"]) for e in result["archive"]})
        self.assertEqual(result["meta"]["holdout_cases"], 36)
        for step in result["mission"]:
            self.assertLessEqual(len(step["probes"]), 6)
            self.assertTrue(np.isfinite(step["error_db"]))
        train = {(e.temperature_c, e.load_ohms, e.age) for e in training_environments()}
        self.assertTrue(all((e["temperature_c"], e["load_ohms"], e["age"]) not in train
                            for e in result["holdout_environments"]))

    def test_invalid_run_requests(self):
        for args in ({"budget":0}, {"budget":10000}, {"cutoff_hz":float("inf")}, {"seed":-1}):
            with self.assertRaises(ValueError):
                build_arena(**args)

    def test_graph_contains_only_measured_ancestry_and_confirmed_switches(self):
        result = build_arena(seed=7, budget=48)
        graph = result["circuit_graph"]
        nodes = {n["id"]: n for n in graph["nodes"]}
        self.assertEqual(len(nodes), 48)
        archive_ids = {n["genotype"] for n in result["archive"]}
        deployed_ids = {s["genotype"] for s in result["mission"]}
        for n in nodes.values():
            self.assertEqual(MVPDesign().genotype(Configuration(**n["configuration"])), n["id"])
            self.assertEqual(n["archived"], n["id"] in archive_ids)
            self.assertEqual(n["deployed"], n["id"] in deployed_ids)
        for edge in graph["edges"]:
            self.assertIn(edge["source"], nodes)
            self.assertIn(edge["target"], nodes)
            if edge["kind"] == "ancestry":
                self.assertIn(edge["source"], nodes[edge["target"]]["parents"])
                self.assertLess(nodes[edge["source"]]["generation"], nodes[edge["target"]]["generation"])
            else:
                step = result["mission"][edge["step"]]
                self.assertTrue(step["changed"])
                self.assertEqual((edge["source"], edge["target"]), (step["before_genotype"], step["genotype"]))
        self.assertEqual(sum(e["kind"] == "recovery" for e in graph["edges"]), result["mission_summary"]["switches"])

    def test_benchmark_seed_range_validation(self):
        for start in (-1, 2**31, 1.5):
            with self.assertRaises(ValueError):
                benchmark_arena(seed_start=start)

    def test_arena_endpoint_validates_and_returns_sealed_evidence(self):
        def post(body):
            handler = VisualizerHandler.__new__(VisualizerHandler)
            handler.path = "/api/arena"
            handler.headers = {"Content-Length": str(len(body))}
            handler.rfile = BytesIO(body)
            handler._send_json = Mock()
            handler.do_POST()
            return handler._send_json.call_args
        result = post(b'{"budget":16,"seed":3}')
        self.assertTrue(verify_payload(result.args[0]))
        for body in (b'[]', b'{"budget":99999}', b'{"cutoff_hz":null}', b'not-json',
                     b'{"seed":1.5}', b'{"seed":true}', b'{"budget":48.5}'):
            self.assertEqual(post(body).kwargs["status"], 400)

    def test_new_assets_are_served_with_correct_types(self):
        for asset, content_type in (("arena.js", "text/javascript"), ("arena.css", "text/css"),
                                    ("graph.js", "text/javascript"), ("graph.css", "text/css"),
                                    ("interface.css", "text/css")):
            handler = VisualizerHandler.__new__(VisualizerHandler)
            handler.path = "/" + asset
            handler._send_bytes = Mock()
            handler.do_GET()
            data, kind = handler._send_bytes.call_args.args
            self.assertGreater(len(data), 100)
            self.assertTrue(kind.startswith(content_type))


if __name__ == "__main__":
    unittest.main()
