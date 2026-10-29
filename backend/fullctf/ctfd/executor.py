"""Local Executor & routage d'exécution (Sprint 10).

Une mission peut s'exécuter sur le serveur principal OU sur un exécuteur local
(ordinateur personnel) qui se connecte au Commander. On modélise ici le pool
d'exécuteurs et la logique de choix.

Le mode local_only (autonomy_policy) favorise un exécuteur local ; sinon, le serveur.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ..models.policies import ExecutionMode


class ExecutorKind(str, Enum):
    SERVER = "server"  # Serveur principal
    LOCAL_PC = "local_pc"  # Exécuteur sur machine personnelle


class ExecutorNode(BaseModel):
    """Un nœud d'exécution déclaré dans le pool."""

    id: str
    kind: ExecutorKind
    online: bool = True
    capabilities: list[str] = Field(
        default_factory=list, description="ex. 'docker', 'gpu', 'big-ram'."
    )


class NoExecutorAvailable(RuntimeError):
    """Aucun exécuteur utilisable pour la mission."""


class ExecutorPool:
    """Gère les exécuteurs disponibles et route les missions."""

    def __init__(self) -> None:
        self._nodes: dict[str, ExecutorNode] = {}

    def register(self, node: ExecutorNode) -> None:
        self._nodes[node.id] = node

    def online_nodes(self) -> list[ExecutorNode]:
        return [n for n in self._nodes.values() if n.online]

    def select(
        self, mode: ExecutionMode, required_capabilities: list[str] | None = None
    ) -> ExecutorNode:
        """Choisit un exécuteur selon le mode et les capacités requises.

        - local_only -> préférer un exécuteur local, sinon repli serveur.
        - connected  -> préférer le serveur, sinon un local.
        Lève NoExecutorAvailable si rien ne convient.
        """
        required = set(required_capabilities or [])
        candidates = [
            n for n in self.online_nodes() if required.issubset(set(n.capabilities))
        ]
        if not candidates:
            raise NoExecutorAvailable("Aucun exécuteur en ligne avec les capacités requises")

        if mode == ExecutionMode.LOCAL_ONLY:
            preferred_kind = ExecutorKind.LOCAL_PC
        else:
            preferred_kind = ExecutorKind.SERVER

        preferred = [n for n in candidates if n.kind == preferred_kind]
        return preferred[0] if preferred else candidates[0]
