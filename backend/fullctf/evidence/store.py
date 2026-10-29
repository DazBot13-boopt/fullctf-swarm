"""Evidence Store (Sprint 6) : conserve les preuves de façon traçable.

Stockage en mémoire pour l'instant (remplacé par une base plus tard). Chaque preuve
garde sa provenance, son empreinte et son statut de vérification.
"""

from __future__ import annotations

from ..models.evidence import Evidence, VerificationStatus


class EvidenceStore:
    """Dépôt de preuves, interrogeable par challenge/mission."""

    def __init__(self) -> None:
        self._items: dict[str, Evidence] = {}

    def add(self, evidence: Evidence) -> Evidence:
        self._items[evidence.id] = evidence
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
        return updated

    def all(self) -> list[Evidence]:
        return list(self._items.values())
