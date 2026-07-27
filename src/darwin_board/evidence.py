from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


def canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    """Return one stable byte representation for an experiment payload."""

    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def seal_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Attach a deterministic run ID and SHA-256 digest to an experiment."""

    body = deepcopy(dict(payload))
    body.pop("evidence", None)
    digest = hashlib.sha256(canonical_bytes(body)).hexdigest()
    body["evidence"] = {
        "run_id": f"DB-{digest[:12].upper()}",
        "payload_sha256": digest,
        "algorithm": "SHA-256",
    }
    return body


def verify_payload(payload: Mapping[str, Any]) -> bool:
    """Check that a sealed experiment still matches its recorded digest."""

    evidence = payload.get("evidence")
    if not isinstance(evidence, Mapping):
        return False
    if evidence.get("algorithm") != "SHA-256":
        return False
    expected_digest = evidence.get("payload_sha256")
    run_id = evidence.get("run_id")
    if not isinstance(expected_digest, str) or not isinstance(run_id, str):
        return False

    body = deepcopy(dict(payload))
    body.pop("evidence", None)
    actual_digest = hashlib.sha256(canonical_bytes(body)).hexdigest()
    return (
        actual_digest == expected_digest
        and run_id == f"DB-{actual_digest[:12].upper()}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify a Darwin Board experiment or benchmark export"
    )
    parser.add_argument("path", type=Path)
    arguments = parser.parse_args()
    try:
        payload = json.loads(arguments.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        parser.error(str(error))

    if not verify_payload(payload):
        print(f"FAILED: {arguments.path}")
        raise SystemExit(1)
    print(
        f"VERIFIED: {payload['evidence']['run_id']} "
        f"({arguments.path})"
    )


if __name__ == "__main__":
    main()
