"""Adaptateur mock : simule un agent sans appeler aucun CLI réel.

Sert à développer et tester toute la logique (Commander, escalade, swarm)
sans consommer de tokens ni dépendre d'un abonnement.
"""

from __future__ import annotations

from .base import AgentAdapter, AgentAvailability, MissionResult
from ..models.mission import AgentProvider


class MockAgentAdapter(AgentAdapter):
    """Agent factice entièrement contrôlable pour les tests."""

    def __init__(
        self,
        provider: AgentProvider,
        *,
        installed: bool = True,
        authenticated: bool = True,
        version: str = "mock-1.0",
        model: str = "mock-model",
        response: str = "mission simulée terminée",
        succeed: bool = True,
    ) -> None:
        self.provider = provider
        self._installed = installed
        self._authenticated = authenticated
        self._version = version
        self._model = model
        self._response = response
        self._succeed = succeed
        self.cancelled = False
        self.calls: list[str] = []

    def check_availability(self) -> AgentAvailability:
        return AgentAvailability(
            provider=self.provider,
            installed=self._installed,
            authenticated=self._authenticated,
            version=self._version if self._installed else None,
            model=self._model if self._authenticated else None,
        )

    def run_mission(self, prompt: str, workspace: str, timeout_seconds: int) -> MissionResult:
        self.calls.append(prompt)
        if not self._succeed:
            return MissionResult(
                success=False, output="", model_used=self._model, error="échec simulé"
            )
        return MissionResult(success=True, output=self._response, model_used=self._model)

    def cancel(self) -> None:
        self.cancelled = True
