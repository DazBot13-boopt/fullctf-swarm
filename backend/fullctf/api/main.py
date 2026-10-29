"""API minimale FullCTF Swarm (Sprint 1).

Pour l'instant : un stockage en mémoire, un health check, et l'import de challenges.
La persistance (PostgreSQL) et les agents viendront dans les sprints suivants.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..evidence.store import EvidenceStore
from ..memory.store import MemoryStore
from ..models.challenge import Category, Challenge, Difficulty
from ..models.mission import Mission
from ..persistence import ChallengeRepository, MissionRepository, SqliteDocStore
from ..supervisor.service import SupervisorService, SupervisorSnapshot

app = FastAPI(
    title="FullCTF Swarm API",
    version="0.1.0",
    description="API de la plateforme de résolution de challenges CTF autorisés.",
)

# Persistance : fichier SQLite par défaut (FULLCTF_DB_PATH pour le configurer,
# ":memory:" pour un store éphémère, ex. en tests).
_DB_PATH = os.environ.get("FULLCTF_DB_PATH", "data/fullctf.db")
if _DB_PATH != ":memory:":
    Path(_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
_STORE = SqliteDocStore(_DB_PATH)

_CHALLENGE_REPO = ChallengeRepository(_STORE)
_MISSION_REPO = MissionRepository(_STORE)
_EVIDENCE = EvidenceStore()
_MEMORY = MemoryStore()
_SUPERVISOR = SupervisorService(_EVIDENCE)

_FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"


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
    """Importe un challenge dans le système (persisté)."""
    challenge = Challenge(**payload.model_dump())
    _CHALLENGE_REPO.save(challenge)
    return challenge


@app.get("/challenges", response_model=list[Challenge])
def list_challenges() -> list[Challenge]:
    """Liste tous les challenges importés."""
    return _CHALLENGE_REPO.list()


@app.get("/challenges/{challenge_id}", response_model=Challenge)
def get_challenge(challenge_id: str) -> Challenge:
    """Récupère un challenge par son identifiant."""
    challenge = _CHALLENGE_REPO.get(challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge introuvable")
    return challenge


@app.get("/missions", response_model=list[Mission])
def list_missions() -> list[Mission]:
    """Liste les missions enregistrées."""
    return _MISSION_REPO.list()


@app.get("/supervisor/snapshot", response_model=SupervisorSnapshot)
def supervisor_snapshot() -> SupervisorSnapshot:
    """Vue d'ensemble fiable de l'état (noyau code, lecture seule)."""
    return _SUPERVISOR.snapshot(_MISSION_REPO.list())


class MemorySearchResult(BaseModel):
    title: str
    category: str
    score: float
    reference: str | None


@app.get("/memory/search", response_model=list[MemorySearchResult])
def memory_search(q: str, limit: int = 5) -> list[MemorySearchResult]:
    """Recherche dans la mémoire d'expérience (lexicale)."""
    return [
        MemorySearchResult(
            title=r.entry.challenge_title,
            category=r.entry.category.value,
            score=r.score,
            reference=r.entry.report_reference,
        )
        for r in _MEMORY.search(q, limit=limit)
    ]


@app.get("/")
def dashboard() -> FileResponse:
    """Sert le dashboard (page unique)."""
    index = _FRONTEND_DIR / "index.html"
    if not index.is_file():
        raise HTTPException(status_code=404, detail="Dashboard introuvable")
    return FileResponse(index)
