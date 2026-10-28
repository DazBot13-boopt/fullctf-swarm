"""Allocation des agents et modes du swarm (règles explicites)."""

from __future__ import annotations

from enum import Enum

from ..models.challenge import Difficulty


class SwarmMode(str, Enum):
    """Modes de fonctionnement du swarm."""

    SINGLE = "single"  # 1 agent travaille seul
    PARALLEL_INDEPENDENT = "parallel_independent"  # plusieurs agents, approches séparées
    COLLABORATIVE = "collaborative"  # agents partagent les preuves
    DEBATE = "debate"  # confrontation + vérification croisée


def initial_mode(difficulty: Difficulty, usable_agents: int) -> SwarmMode:
    """Choisit le mode de départ : commencer léger, selon difficulté et agents dispo.

    - easy/medium -> Single
    - hard        -> Parallel Independent (si >=2 agents)
    - insane      -> Collaborative (si >=2 agents)
    Avec 1 seul agent, tout retombe sur Single (escalade séquentielle ensuite).
    """
    if usable_agents <= 0:
        raise ValueError("Aucun agent utilisable")
    if usable_agents == 1:
        return SwarmMode.SINGLE

    if difficulty in (Difficulty.EASY, Difficulty.MEDIUM):
        return SwarmMode.SINGLE
    if difficulty == Difficulty.HARD:
        return SwarmMode.PARALLEL_INDEPENDENT
    if difficulty == Difficulty.INSANE:
        return SwarmMode.COLLABORATIVE
    # Difficulté inconnue : prudence, on démarre en Single.
    return SwarmMode.SINGLE


def initial_agent_count(mode: SwarmMode, usable_agents: int) -> int:
    """Combien d'agents mobiliser au démarrage pour un mode donné."""
    if mode == SwarmMode.SINGLE:
        return 1
    return min(usable_agents, 3)


# Chaîne d'escalade : chaque étape mobilise plus de force.
_ESCALATION_ORDER = [
    SwarmMode.SINGLE,
    SwarmMode.PARALLEL_INDEPENDENT,
    SwarmMode.COLLABORATIVE,
    SwarmMode.DEBATE,
]


def next_mode(current: SwarmMode, usable_agents: int) -> SwarmMode | None:
    """Mode suivant dans l'escalade, ou None si on est déjà au maximum.

    Avec 1 seul agent, pas d'escalade de mode (l'escalade devient séquentielle :
    changement de profil/stratégie, géré ailleurs).
    """
    if usable_agents == 1:
        return None
    idx = _ESCALATION_ORDER.index(current)
    if idx + 1 < len(_ESCALATION_ORDER):
        return _ESCALATION_ORDER[idx + 1]
    return None
