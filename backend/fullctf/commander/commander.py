"""Commander FullCTF (noyau code à règles explicites).

Responsabilités de ce noyau (Sprint 4) :
- Classifier un challenge.
- Décider du mode de swarm et du nombre d'agents (allocation initiale).
- Créer les missions avec budgets et policies.
- Piloter l'escalade quand la stagnation est détectée.
- Garantir que les transitions de mission sont valides (garde-fou).

Le "cerveau LLM" (décisions stratégiques fines) sera greffé plus tard, au-dessus
de ce noyau, qui gardera toujours la main sur les garde-fous.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..agents.registry import AgentRegistry
from ..models.challenge import Challenge
from ..models.mission import (
    Mission,
    MissionStatus,
    can_transition,
)
from ..models.policies import AutonomyPolicy, ToolAccessPolicy
from .allocation import SwarmMode, initial_agent_count, initial_mode, next_mode
from .classifier import infer_category
from .stagnation import StagnationDetector


@dataclass
class MissionPlan:
    """Plan d'attaque décidé par le Commander pour un challenge."""

    challenge_id: str
    category: str
    mode: SwarmMode
    agent_count: int
    missions: list[Mission] = field(default_factory=list)


class Commander:
    """Noyau de décision du Commander."""

    def __init__(
        self,
        registry: AgentRegistry,
        *,
        default_autonomy: AutonomyPolicy | None = None,
        default_tools: ToolAccessPolicy | None = None,
    ) -> None:
        self.registry = registry
        self.default_autonomy = default_autonomy or AutonomyPolicy()
        self.default_tools = default_tools or ToolAccessPolicy()

    # --- Planification -------------------------------------------------

    def plan(self, challenge: Challenge) -> MissionPlan:
        """Classe le challenge et décide de l'allocation initiale."""
        usable = self.registry.usable_providers()
        if not usable:
            raise RuntimeError("Aucun agent utilisable : impossible de planifier")

        category = infer_category(challenge)
        mode = initial_mode(challenge.difficulty, len(usable))
        count = initial_agent_count(mode, len(usable))

        missions = [
            Mission(
                challenge_id=challenge.id,
                agent_provider=usable[i],
                specialist_profile=category.value,
                objective=f"Résoudre le challenge {challenge.title}",
                autonomy_policy=self.default_autonomy,
                tool_access_policy=self.default_tools,
            )
            for i in range(count)
        ]
        return MissionPlan(
            challenge_id=challenge.id,
            category=category.value,
            mode=mode,
            agent_count=count,
            missions=missions,
        )

    # --- Escalade ------------------------------------------------------

    def should_escalate(self, detector: StagnationDetector) -> bool:
        """Décide s'il faut escalader (basé sur la stagnation)."""
        return detector.is_stagnating()

    def escalate(self, current_mode: SwarmMode) -> SwarmMode | None:
        """Passe au mode supérieur, ou None s'il n'y a plus d'escalade possible."""
        usable = self.registry.usable_count()
        return next_mode(current_mode, usable)

    # --- Garde-fou des transitions ------------------------------------

    def transition(self, mission: Mission, target: MissionStatus) -> Mission:
        """Applique une transition d'état en la validant d'abord.

        Lève ValueError si la transition n'est pas autorisée (garde-fou code).
        """
        if not can_transition(mission.status, target):
            raise ValueError(
                f"Transition interdite : {mission.status.value} -> {target.value}"
            )
        mission.status = target
        return mission
