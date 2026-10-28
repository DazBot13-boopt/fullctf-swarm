"""Adaptateurs concrets pour les trois CLI autorisés.

Les commandes réelles seront ajustées au Sprint 0 (audit sur le VPS) en fonction
du comportement non-interactif réel de chaque CLI. Ici on fixe une base propre.

Aucun 4e agent. Ces trois-là uniquement.
"""

from __future__ import annotations

from .subprocess_adapter import SubprocessAgentAdapter
from ..models.mission import AgentProvider


def make_codex_adapter(model: str | None = None) -> SubprocessAgentAdapter:
    """Adaptateur OpenAI Codex CLI."""
    return SubprocessAgentAdapter(
        provider=AgentProvider.CODEX,
        version_cmd=["codex", "--version"],
        build_run_command=lambda prompt: ["codex", "exec", prompt],
        model=model,
    )


def make_claude_adapter(model: str | None = None) -> SubprocessAgentAdapter:
    """Adaptateur Anthropic Claude Code CLI."""
    return SubprocessAgentAdapter(
        provider=AgentProvider.CLAUDE,
        version_cmd=["claude", "--version"],
        build_run_command=lambda prompt: ["claude", "-p", prompt],
        model=model,
    )


def make_cursor_adapter(model: str | None = None) -> SubprocessAgentAdapter:
    """Adaptateur Cursor Agent CLI (mode auto de sélection de modèle si dispo)."""
    return SubprocessAgentAdapter(
        provider=AgentProvider.CURSOR,
        version_cmd=["cursor-agent", "--version"],
        build_run_command=lambda prompt: ["cursor-agent", "-p", prompt],
        model=model,
    )
