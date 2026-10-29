"""Model tiering : choisir le bon modèle selon la tâche (sans hardcode).

Chaque fournisseur déclare un modèle rapide (fast) et un modèle puissant (heavy).
Le Commander choisit le tier selon la difficulté : on ne brûle pas le modèle le
plus cher pour une tâche triviale.

Les noms de modèles ne sont PAS codés en dur ici : ils se remplissent au Sprint 0
en interrogeant les comptes réels. On fournit juste la structure et la logique.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ..models.challenge import Difficulty
from ..models.mission import AgentProvider


class ModelTier(str, Enum):
    FAST = "fast"  # rapide / économique (tâches simples)
    HEAVY = "heavy"  # puissant (raisonnement dur)
    AUTO = "auto"  # laisser le fournisseur choisir (ex. Cursor)


class ProviderModels(BaseModel):
    """Modèles déclarés pour un fournisseur."""

    provider: AgentProvider
    default_model: str | None = None  # None => mode auto du CLI
    fast_model: str | None = None
    heavy_model: str | None = None

    def pick(self, tier: ModelTier) -> str | None:
        """Retourne le modèle pour un tier, avec repli sur default."""
        if tier == ModelTier.FAST and self.fast_model:
            return self.fast_model
        if tier == ModelTier.HEAVY and self.heavy_model:
            return self.heavy_model
        return self.default_model


class ModelCatalog:
    """Catalogue des modèles par fournisseur + sélection par tier."""

    def __init__(self) -> None:
        self._by_provider: dict[AgentProvider, ProviderModels] = {}

    def set(self, config: ProviderModels) -> None:
        self._by_provider[config.provider] = config

    def select(self, provider: AgentProvider, tier: ModelTier) -> str | None:
        config = self._by_provider.get(provider)
        if config is None:
            return None
        return config.pick(tier)


def tier_for_difficulty(difficulty: Difficulty) -> ModelTier:
    """Associe une difficulté à un tier de modèle."""
    if difficulty in (Difficulty.EASY, Difficulty.MEDIUM):
        return ModelTier.FAST
    if difficulty in (Difficulty.HARD, Difficulty.INSANE):
        return ModelTier.HEAVY
    return ModelTier.AUTO
