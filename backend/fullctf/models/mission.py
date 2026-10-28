"""Modèle Mission : une tâche confiée à un agent sur un challenge."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from .policies import AutonomyPolicy, ToolAccessPolicy


class AgentProvider(str, Enum):
    """Les trois workers agentiques autorisés. Aucun 4e LLM permanent."""

    CODEX = "codex"
    CLAUDE = "claude"
    CURSOR = "cursor"


class MissionStatus(str, Enum):
    """Cycle de vie d'une mission.

    CREATED -> VALIDATED -> QUEUED -> RUNNING
    RUNNING -> WAITING_APPROVAL -> RUNNING
    RUNNING -> PAUSED -> RUNNING
    RUNNING -> COMPLETED / FAILED / CANCELLED / TIMED_OUT
    """

    CREATED = "created"
    VALIDATED = "validated"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class ResourceBudget(BaseModel):
    """Budget de ressources d'une mission (garde-fou du Commander)."""

    max_cpu: float = Field(default=2.0, description="vCPU alloués au conteneur.")
    max_memory_mb: int = Field(default=4096, description="RAM max en Mo.")
    max_disk_mb: int = Field(default=10240, description="Disque max en Mo.")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Mission(BaseModel):
    """Une mission : un agent + un profil + un objectif sur un challenge."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    challenge_id: str
    agent_provider: AgentProvider
    specialist_profile: str = Field(
        default="generalist",
        description="Profil endossé : web, pwn, crypto, reverse, forensic...",
    )
    objective: str = ""
    allowed_tools: list[str] = Field(default_factory=list)
    resource_budget: ResourceBudget = Field(default_factory=ResourceBudget)
    time_budget_seconds: int = Field(default=1800, description="Temps max en secondes.")
    workspace: str = Field(default="", description="Chemin du workspace isolé.")
    status: MissionStatus = MissionStatus.CREATED
    result: str | None = None

    autonomy_policy: AutonomyPolicy = Field(default_factory=AutonomyPolicy)
    tool_access_policy: ToolAccessPolicy = Field(default_factory=ToolAccessPolicy)

    created_at: datetime = Field(default_factory=_now)


# Transitions autorisées du cycle de vie. Toute transition hors de cette table
# est refusée par le Commander (noyau code = garde-fou).
ALLOWED_TRANSITIONS: dict[MissionStatus, set[MissionStatus]] = {
    MissionStatus.CREATED: {MissionStatus.VALIDATED, MissionStatus.CANCELLED},
    MissionStatus.VALIDATED: {MissionStatus.QUEUED, MissionStatus.CANCELLED},
    MissionStatus.QUEUED: {MissionStatus.RUNNING, MissionStatus.CANCELLED},
    MissionStatus.RUNNING: {
        MissionStatus.WAITING_APPROVAL,
        MissionStatus.PAUSED,
        MissionStatus.COMPLETED,
        MissionStatus.FAILED,
        MissionStatus.CANCELLED,
        MissionStatus.TIMED_OUT,
    },
    MissionStatus.WAITING_APPROVAL: {MissionStatus.RUNNING, MissionStatus.CANCELLED},
    MissionStatus.PAUSED: {MissionStatus.RUNNING, MissionStatus.CANCELLED},
    MissionStatus.COMPLETED: set(),
    MissionStatus.FAILED: set(),
    MissionStatus.CANCELLED: set(),
    MissionStatus.TIMED_OUT: set(),
}


def can_transition(current: MissionStatus, target: MissionStatus) -> bool:
    """Retourne True si la transition est autorisée."""
    return target in ALLOWED_TRANSITIONS.get(current, set())
