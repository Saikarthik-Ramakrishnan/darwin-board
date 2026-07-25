from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .model import Configuration


@dataclass(frozen=True)
class Experience:
    cutoff_hz: float
    configuration: Configuration
    response_error_db: float
    board_id: str = "unknown"
    temperature_c: float | None = None
    supply_mv: int | None = None

    def to_payload(self) -> dict:
        payload = asdict(self)
        payload["configuration"] = asdict(self.configuration)
        return payload

    @classmethod
    def from_payload(cls, payload: dict) -> Experience:
        configuration = Configuration(**payload["configuration"])
        return cls(
            cutoff_hz=float(payload["cutoff_hz"]),
            configuration=configuration,
            response_error_db=float(payload["response_error_db"]),
            board_id=str(payload.get("board_id", "unknown")),
            temperature_c=(
                float(payload["temperature_c"])
                if payload.get("temperature_c") is not None
                else None
            ),
            supply_mv=(
                int(payload["supply_mv"])
                if payload.get("supply_mv") is not None
                else None
            ),
        )


class ExperienceMemory:
    """Small persistent memory of configurations that worked on real boards."""

    def __init__(
        self,
        experiences: Iterable[Experience] = (),
        *,
        max_records: int = 128,
    ) -> None:
        if max_records < 1:
            raise ValueError("max_records must be positive")
        self.max_records = max_records
        self._experiences = list(experiences)[-max_records:]

    def __len__(self) -> int:
        return len(self._experiences)

    @property
    def experiences(self) -> tuple[Experience, ...]:
        return tuple(self._experiences)

    def record(
        self,
        *,
        cutoff_hz: float,
        configuration: Configuration,
        response_error_db: float,
        board_id: str = "unknown",
        temperature_c: float | None = None,
        supply_mv: int | None = None,
    ) -> None:
        experience = Experience(
            cutoff_hz=cutoff_hz,
            configuration=configuration,
            response_error_db=response_error_db,
            board_id=board_id,
            temperature_c=temperature_c,
            supply_mv=supply_mv,
        )
        self._experiences.append(experience)
        if len(self._experiences) > self.max_records:
            del self._experiences[: len(self._experiences) - self.max_records]

    def recommend(
        self,
        cutoff_hz: float,
        *,
        limit: int = 3,
        exclude: Iterable[Configuration] = (),
    ) -> tuple[Configuration, ...]:
        if limit < 1:
            return ()
        excluded = set(exclude)
        ranked = sorted(
            self._experiences,
            key=lambda item: (
                abs(item.cutoff_hz - cutoff_hz) / max(cutoff_hz, 1.0),
                item.response_error_db,
            ),
        )
        recommendations: list[Configuration] = []
        for experience in ranked:
            configuration = experience.configuration
            if configuration in excluded or configuration in recommendations:
                continue
            recommendations.append(configuration)
            if len(recommendations) == limit:
                break
        return tuple(recommendations)

    def save(self, path: Path) -> None:
        payload = {
            "schema_version": "0.3",
            "experiences": [
                experience.to_payload()
                for experience in self._experiences
            ],
        }
        path.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        max_records: int = 128,
    ) -> ExperienceMemory:
        if not path.exists():
            return cls(max_records=max_records)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "0.3":
            raise ValueError("Unsupported experience-memory schema")
        return cls(
            (
                Experience.from_payload(item)
                for item in payload.get("experiences", [])
            ),
            max_records=max_records,
        )
