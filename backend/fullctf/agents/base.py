"""Interface commune des adaptateurs d'agents (Module 1 - Multi-CLI Integration).

Chaque CLI (Codex, Claude Code, Cursor Agent) aura son adaptateur concret qui
implémente cette interface. Le Commander ne parle qu'à cette abstraction, jamais
directement à un CLI précis. Cela permet la configuration flexible 1/2/3 agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from ..models.mission import AgentProvider


class AgentAvailability(BaseModel):
    """État de disponibilité d'un agent, détecté au démarrage."""

    provider: AgentProvider
    installed: bool
    authenticated: bool
    version: str | None = None
    model: str | None = None  # Modèle réellement utilisé lorsqu'il est déterminable

    @property
    def usable(self) -> bool:
        """L'agent est utilisable s'il est installé ET authentifié."""
        return self.installed and self.authenticated


class MissionResult(BaseModel):
    """Résultat brut d'une exécution de mission par un agent."""

    success: bool
    output: str
    model_used: str | None = None
    error: str | None = None


class AgentAdapter(ABC):
    """Contrat que chaque adaptateur de CLI doit respecter."""

    provider: AgentProvider

    @abstractmethod
    def check_availability(self) -> AgentAvailability:
        """Détecte si le CLI est installé, authentifié, et sa version/modèle.

        NE DOIT JAMAIS lire ou afficher de secret : seulement l'état.
        """
        raise NotImplementedError

    @abstractmethod
    def run_mission(self, prompt: str, workspace: str, timeout_seconds: int) -> MissionResult:
        """Lance une mission bénigne et retourne le résultat structuré."""
        raise NotImplementedError

    @abstractmethod
    def cancel(self) -> None:
        """Annule la mission en cours."""
        raise NotImplementedError
