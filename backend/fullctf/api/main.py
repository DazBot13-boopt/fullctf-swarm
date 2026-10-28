"""API minimale FullCTF Swarm (Sprint 1).

Pour l'instant : un stockage en mémoire, un health check, et l'import de challenges.
La persistance (PostgreSQL) et les agents viendront dans les sprints suivants.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ..models.challenge import Category, Challenge, Difficulty

app = FastAPI(
    title="FullCTF Swarm API",
    version="0.1.0",
    description="API de la plateforme de résolution de challenges CTF autorisés.",
)

# Stockage en mémoire (temporaire, remplacé par une base au Sprint 1+).
_CHALLENGES: dict[str, Challenge] = {}


class ChallengeCreate(BaseModel):
    """Payload d'import d'un challenge."""

    title: str
    category: Category = Category.UNKNOWN
    difficulty: Difficulty = Difficulty.UNKNOWN
    description: str = ""
    authorization_scope: str = ""


@app.get("/health")
def health() -> dict[str, str]:
    """Vérifie que l'API est vivante."""
    return {"status": "ok", "service": "fullctf-swarm"}


@app.post("/challenges", response_model=Challenge, status_code=201)
def create_challenge(payload: ChallengeCreate) -> Challenge:
    """Importe un challenge dans le système."""
    challenge = Challenge(**payload.model_dump())
    _CHALLENGES[challenge.id] = challenge
    return challenge


@app.get("/challenges", response_model=list[Challenge])
def list_challenges() -> list[Challenge]:
    """Liste tous les challenges importés."""
    return list(_CHALLENGES.values())


@app.get("/challenges/{challenge_id}", response_model=Challenge)
def get_challenge(challenge_id: str) -> Challenge:
    """Récupère un challenge par son identifiant."""
    challenge = _CHALLENGES.get(challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge introuvable")
    return challenge
