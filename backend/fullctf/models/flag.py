"""Modèle FlagCandidate : un flag trouvé, avec son parcours de validation."""

from __future__ import annotations

from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class FlagStatus(str, Enum):
    """Parcours d'un flag. Un flag local n'est JAMAIS automatiquement accepté.

    candidate -> format_valid -> reproduced -> accepted / rejected
    """

    CANDIDATE = "candidate"  # Trouvé, non vérifié
    FORMAT_VALID = "format_valid"  # Respecte le format attendu
    REPRODUCED = "reproduced"  # Résultat reproduit (pas un faux positif)
    ACCEPTED = "accepted"  # Accepté par la plateforme
    REJECTED = "rejected"  # Rejeté


# Transitions autorisées pour un flag.
ALLOWED_FLAG_TRANSITIONS: dict[FlagStatus, set[FlagStatus]] = {
    FlagStatus.CANDIDATE: {FlagStatus.FORMAT_VALID, FlagStatus.REJECTED},
    FlagStatus.FORMAT_VALID: {FlagStatus.REPRODUCED, FlagStatus.REJECTED},
    FlagStatus.REPRODUCED: {FlagStatus.ACCEPTED, FlagStatus.REJECTED},
    FlagStatus.ACCEPTED: set(),
    FlagStatus.REJECTED: set(),
}


def can_flag_transition(current: FlagStatus, target: FlagStatus) -> bool:
    """Retourne True si la transition de statut du flag est autorisée."""
    return target in ALLOWED_FLAG_TRANSITIONS.get(current, set())


class FlagCandidate(BaseModel):
    """Un flag candidat et son état de validation."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    challenge_id: str
    value: str
    source_mission: str
    validation_status: FlagStatus = FlagStatus.CANDIDATE
    reproduction_reference: str | None = Field(
        default=None, description="Référence du script/méthode de reproduction."
    )
    platform_feedback: str | None = Field(
        default=None, description="Retour de la plateforme après soumission."
    )
