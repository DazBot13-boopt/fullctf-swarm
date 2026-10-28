"""Registre d'agents : détection et configuration flexible (1, 2 ou 3 agents).

Au démarrage, on enregistre les adaptateurs disponibles. Le registre détecte
lesquels sont réellement utilisables (installés + authentifiés) et expose cette
liste au Commander. Le tool ne dépend jamais d'un agent précis.
"""

from __future__ import annotations

from .base import AgentAdapter, AgentAvailability
from ..models.mission import AgentProvider


class AgentRegistry:
    """Garde la trace des adaptateurs enregistrés et de leur disponibilité."""

    def __init__(self) -> None:
        self._adapters: dict[AgentProvider, AgentAdapter] = {}

    def register(self, adapter: AgentAdapter) -> None:
        self._adapters[adapter.provider] = adapter

    def get(self, provider: AgentProvider) -> AgentAdapter:
        if provider not in self._adapters:
            raise KeyError(f"Aucun adaptateur enregistré pour {provider}")
        return self._adapters[provider]

    def availabilities(self) -> list[AgentAvailability]:
        """État de tous les adaptateurs enregistrés."""
        return [a.check_availability() for a in self._adapters.values()]

    def usable_providers(self) -> list[AgentProvider]:
        """Fournisseurs réellement utilisables (installés + authentifiés)."""
        return [av.provider for av in self.availabilities() if av.usable]

    def usable_count(self) -> int:
        return len(self.usable_providers())

    def has_any_usable(self) -> bool:
        return self.usable_count() > 0
