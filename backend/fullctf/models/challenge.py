"""Modèle Challenge : un défi CTF importé dans le système."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class Category(str, Enum):
    """Catégorie d'un challenge CTF."""

    WEB = "web"
    PWN = "pwn"
    REVERSE = "reverse"
    CRYPTO = "crypto"
    FORENSIC = "forensic"
    MISC = "misc"
    ATTACK_DEFENSE = "attack_defense"
    UNKNOWN = "unknown"


class Difficulty(str, Enum):
    """Difficulté annoncée d'un challenge."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    INSANE = "insane"
    UNKNOWN = "unknown"


class ChallengeStatus(str, Enum):
    """État d'un challenge dans le système."""

    IMPORTED = "imported"
    IN_PROGRESS = "in_progress"
    SOLVED = "solved"
    FAILED = "failed"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Challenge(BaseModel):
    """Un challenge CTF autorisé, importé localement ou depuis une plateforme."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    category: Category = Category.UNKNOWN
    difficulty: Difficulty = Difficulty.UNKNOWN
    description: str = ""
    source: str = Field(
        default="local",
        description="Origine : 'local', 'ctfd', etc.",
    )
    attachments: list[str] = Field(
        default_factory=list,
        description="Chemins des pièces jointes (originaux immuables).",
    )
    authorization_scope: str = Field(
        default="",
        description="Périmètre explicitement autorisé pour ce challenge.",
    )
    status: ChallengeStatus = ChallengeStatus.IMPORTED
    created_at: datetime = Field(default_factory=_now)
