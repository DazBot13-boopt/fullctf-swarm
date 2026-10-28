"""Modèle Evidence : une preuve produite pendant une mission."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    """Statut de vérification d'une preuve."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ConfidenceLevel(str, Enum):
    """Niveau de confiance dans une observation."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Evidence(BaseModel):
    """Une preuve : observation + artefact + provenance traçable.

    On distingue toujours fait observé / hypothèse / résultat reproduit.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    challenge_id: str
    mission_id: str
    source: str = Field(description="Agent et outil d'origine.")
    observation: str = Field(description="Ce qui a été observé (fait, pas hypothèse).")
    artifact_path: str | None = Field(
        default=None, description="Chemin de l'artefact produit."
    )
    checksum: str | None = Field(
        default=None, description="Empreinte du fichier lorsque pertinent."
    )
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    created_at: datetime = Field(default_factory=_now)
