"""Repositories typés au-dessus d'un DocStore.

Convertissent les modèles Pydantic en documents JSON et inversement. Le reste du
code manipule des objets typés, sans savoir si c'est stocké en SQLite ou Postgres.
"""

from __future__ import annotations

from ..models.challenge import Challenge
from ..models.evidence import Evidence
from ..models.mission import Mission
from .sqlite_store import DocStore

_CHALLENGES = "challenges"
_MISSIONS = "missions"
_EVIDENCE = "evidence"


class ChallengeRepository:
    def __init__(self, store: DocStore) -> None:
        self._store = store

    def save(self, challenge: Challenge) -> Challenge:
        self._store.put(_CHALLENGES, challenge.id, challenge.model_dump(mode="json"))
        return challenge

    def get(self, challenge_id: str) -> Challenge | None:
        data = self._store.get(_CHALLENGES, challenge_id)
        return Challenge.model_validate(data) if data else None

    def list(self) -> list[Challenge]:
        return [Challenge.model_validate(d) for d in self._store.list(_CHALLENGES)]


class MissionRepository:
    def __init__(self, store: DocStore) -> None:
        self._store = store

    def save(self, mission: Mission) -> Mission:
        self._store.put(_MISSIONS, mission.id, mission.model_dump(mode="json"))
        return mission

    def get(self, mission_id: str) -> Mission | None:
        data = self._store.get(_MISSIONS, mission_id)
        return Mission.model_validate(data) if data else None

    def list(self) -> list[Mission]:
        return [Mission.model_validate(d) for d in self._store.list(_MISSIONS)]

    def for_challenge(self, challenge_id: str) -> list[Mission]:
        return [m for m in self.list() if m.challenge_id == challenge_id]


class EvidenceRepository:
    def __init__(self, store: DocStore) -> None:
        self._store = store

    def save(self, evidence: Evidence) -> Evidence:
        self._store.put(_EVIDENCE, evidence.id, evidence.model_dump(mode="json"))
        return evidence

    def get(self, evidence_id: str) -> Evidence | None:
        data = self._store.get(_EVIDENCE, evidence_id)
        return Evidence.model_validate(data) if data else None

    def list(self) -> list[Evidence]:
        return [Evidence.model_validate(d) for d in self._store.list(_EVIDENCE)]

    def for_challenge(self, challenge_id: str) -> list[Evidence]:
        return [e for e in self.list() if e.challenge_id == challenge_id]
