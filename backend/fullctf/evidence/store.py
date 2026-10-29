"""Evidence Store (Sprint 6) : conserve les preuves de façon traçable.

Persistance optionnelle : si un DocStore est fourni, les preuves sont écrites
(write-through) et rechargées au démarrage. Sans store, fonctionnement en mémoire
(comme avant) — utile pour les tests.
"""

from __future__ import annotations

from ..models.evidence import Evidence, VerificationStatus
from ..persistence.sqlite_store import DocStore


class EvidenceStore:
    """Dépôt de preuves, interrogeable par challenge/mission."""

    def __init__(self, store: DocStore | None = None, collection: str = "evidence") -> None:
        self._store = store
        self._collection = collection
        self._items: dict[str, Evidence] = {}
        # Recharge l'existant depuis la persistance.
        if store is not None:
            for data in store.list(collection):
                e = Evidence.model_validate(data)
                self._items[e.id] = e

    def _persist(self, evidence: Evidence) -> None:
        if self._store is not None:
            self._store.put(self._collection, evidence.id, evidence.model_dump(mode="json"))

    def add(self, evidence: Evidence) -> Evidence:
        self._items[evidence.id] = evidence
        self._persist(evidence)
        return evidence

    def get(self, evidence_id: str) -> Evidence:
        if evidence_id not in self._items:
            raise KeyError(f"Preuve inconnue : {evidence_id}")
        return self._items[evidence_id]

    def for_challenge(self, challenge_id: str) -> list[Evidence]:
        return [e for e in self._items.values() if e.challenge_id == challenge_id]

    def for_mission(self, mission_id: str) -> list[Evidence]:
        return [e for e in self._items.values() if e.mission_id == mission_id]

    def verified(self, challenge_id: str) -> list[Evidence]:
        """Preuves vérifiées d'un challenge (celles qu'on peut partager/croire)."""
        return [
            e for e in self.for_challenge(challenge_id)
            if e.verification_status == VerificationStatus.VERIFIED
        ]

    def mark(self, evidence_id: str, status: VerificationStatus) -> Evidence:
        evidence = self.get(evidence_id)
        updated = evidence.model_copy(update={"verification_status": status})
        self._items[evidence_id] = updated
        self._persist(updated)
        return updated

    def all(self) -> list[Evidence]:
        return list(self._items.values())
