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


def build_sprint0_catalog() -> ModelCatalog:
    """Catalogue rempli avec les modèles RÉELS constatés au Sprint 0 (VPS).

    Sources (interrogation des comptes) :
    - Cursor  : `cursor-agent --list-models` (opus-5, gpt-5.x-codex, grok, gemini…).
                `None` => mode `auto` du CLI (Cursor choisit).
    - Claude  : alias officiels du CLI (`--model haiku|sonnet|opus`), repli compte.
    - Codex   : modèle par défaut du compte (`None`) ; `-m` accepte un nom précis
                si besoin. Les noms exacts dépendent du compte, non devinés ici.

    Ces valeurs sont des points de départ ajustables, pas des constantes figées.
    """
    catalog = ModelCatalog()
    catalog.set(
        ProviderModels(
            provider=AgentProvider.CODEX,
            default_model=None,  # défaut du compte Codex
            fast_model=None,
            heavy_model=None,
        )
    )
    catalog.set(
        ProviderModels(
            provider=AgentProvider.CLAUDE,
            default_model=None,  # défaut du compte Claude
            fast_model="haiku",
            heavy_model="opus",
        )
    )
    catalog.set(
        ProviderModels(
            provider=AgentProvider.CURSOR,
            default_model=None,  # None => "auto" du CLI Cursor
            fast_model="gpt-5.3-codex-low",
            heavy_model="claude-opus-5-thinking-high",
        )
    )
    return catalog


def tier_for_difficulty(difficulty: Difficulty) -> ModelTier:
    """Associe une difficulté à un tier de modèle."""
    if difficulty in (Difficulty.EASY, Difficulty.MEDIUM):
        return ModelTier.FAST
    if difficulty in (Difficulty.HARD, Difficulty.INSANE):
        return ModelTier.HEAVY
    return ModelTier.AUTO
