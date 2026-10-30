"""Tests du model tiering (fast/heavy)."""

from fullctf.agents.model_config import (
    ModelCatalog,
    ModelTier,
    ProviderModels,
    tier_for_difficulty,
)
from fullctf.models.challenge import Difficulty
from fullctf.models.mission import AgentProvider


def test_provider_pick_tiers():
    pm = ProviderModels(
        provider=AgentProvider.CLAUDE,
        default_model="d", fast_model="f", heavy_model="h",
    )
    assert pm.pick(ModelTier.FAST) == "f"
    assert pm.pick(ModelTier.HEAVY) == "h"
    assert pm.pick(ModelTier.AUTO) == "d"


def test_provider_pick_fallback_to_default():
    pm = ProviderModels(provider=AgentProvider.CODEX, default_model="d")
    assert pm.pick(ModelTier.FAST) == "d"  # pas de fast défini -> default
    assert pm.pick(ModelTier.HEAVY) == "d"


def test_catalog_select():
    cat = ModelCatalog()
    cat.set(ProviderModels(provider=AgentProvider.CURSOR, default_model=None))
    # Cursor en auto (pas de modèle forcé).
    assert cat.select(AgentProvider.CURSOR, ModelTier.AUTO) is None
    # Fournisseur inconnu du catalogue.
    assert cat.select(AgentProvider.CODEX, ModelTier.FAST) is None


def test_tier_for_difficulty():
    assert tier_for_difficulty(Difficulty.EASY) == ModelTier.FAST
    assert tier_for_difficulty(Difficulty.INSANE) == ModelTier.HEAVY
    assert tier_for_difficulty(Difficulty.UNKNOWN) == ModelTier.AUTO


# --- Sprint 0 : catalogue rempli avec les modèles réels du VPS ---
from fullctf.agents.model_config import build_sprint0_catalog  # noqa: E402


def test_sprint0_catalog_has_three_providers_with_real_models():
    cat = build_sprint0_catalog()
    assert cat.select(AgentProvider.CLAUDE, ModelTier.FAST) == "haiku"
    assert cat.select(AgentProvider.CLAUDE, ModelTier.HEAVY) == "opus"
    assert cat.select(AgentProvider.CURSOR, ModelTier.HEAVY) == "claude-opus-5-thinking-high"
    # Cursor en FAST a un modèle réel (issu de --list-models)
    assert cat.select(AgentProvider.CURSOR, ModelTier.FAST) == "gpt-5.3-codex-low"
    # Codex : défaut du compte -> None (non deviné), repli propre
    assert cat.select(AgentProvider.CODEX, ModelTier.HEAVY) is None
