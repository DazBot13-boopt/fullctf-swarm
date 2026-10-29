"""Collaboration (Sprint 7) : plusieurs agents, preuves partagées.

Chaque agent produit un résultat qui devient une Evidence dans le store commun.
Les autres agents peuvent ensuite s'appuyer sur les preuves VÉRIFIÉES.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..agents.registry import AgentRegistry
from ..evidence.store import EvidenceStore
from ..models.evidence import ConfidenceLevel, Evidence
from ..models.mission import AgentProvider


@dataclass
class AgentTask:
    """Une tâche confiée à un agent précis pendant une collaboration."""

    provider: AgentProvider
    profile: str
    prompt: str
    mission_id: str


class CollaborationEngine:
    """Orchestre un tour de collaboration entre agents, via le store de preuves."""

    def __init__(self, registry: AgentRegistry, evidence_store: EvidenceStore) -> None:
        self.registry = registry
        self.evidence_store = evidence_store

    def run_round(
        self, challenge_id: str, tasks: list[AgentTask], workspace: str, timeout: int
    ) -> list[Evidence]:
        """Exécute chaque tâche et enregistre les résultats comme preuves.

        Retourne les preuves créées pendant ce tour.
        """
        created: list[Evidence] = []
        for task in tasks:
            adapter = self.registry.get(task.provider)
            result = adapter.run_mission(task.prompt, workspace, timeout)

            observation = result.output if result.success else (result.error or "échec")
            confidence = ConfidenceLevel.MEDIUM if result.success else ConfidenceLevel.LOW
            evidence = Evidence(
                challenge_id=challenge_id,
                mission_id=task.mission_id,
                source=f"{task.provider.value}/{task.profile}",
                observation=observation,
                confidence=confidence,
            )
            self.evidence_store.add(evidence)
            created.append(evidence)
        return created

    def shared_context(self, challenge_id: str) -> list[Evidence]:
        """Preuves vérifiées disponibles pour nourrir les agents suivants."""
        return self.evidence_store.verified(challenge_id)
