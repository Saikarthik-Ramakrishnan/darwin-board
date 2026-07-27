import unittest

from darwin_board.evidence import seal_payload, verify_payload


class EvidenceTest(unittest.TestCase):
    def test_seals_payload_deterministically(self) -> None:
        first = seal_payload({"value": 12, "samples": [1.0, 2.0]})
        second = seal_payload({"samples": [1.0, 2.0], "value": 12})

        self.assertEqual(first["evidence"], second["evidence"])
        self.assertTrue(verify_payload(first))
        self.assertTrue(first["evidence"]["run_id"].startswith("DB-"))

    def test_detects_modified_payload(self) -> None:
        payload = seal_payload({"response_error_db": 0.12})
        payload["response_error_db"] = 0.01

        self.assertFalse(verify_payload(payload))

    def test_rejects_modified_algorithm_label(self) -> None:
        payload = seal_payload({"response_error_db": 0.12})
        payload["evidence"]["algorithm"] = "unknown"

        self.assertFalse(verify_payload(payload))


if __name__ == "__main__":
    unittest.main()
