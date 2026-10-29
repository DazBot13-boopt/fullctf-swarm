"""Adaptateurs concrets pour les trois CLI autorisés.

Commandes réelles ajustées au Sprint 0 (audit sur le VPS, CLI testés en
non-interactif). Aucun 4e agent. Ces trois-là uniquement.

Mode `auto` :
- True  -> plein accès (prévu pour tourner DANS le conteneur jetable arsenal,
           lui-même isolé : l'agent peut installer/compiler/exécuter librement).
- False -> sandbox sûr (utile pour un test sur l'hôte sans rien casser).

Comportement non-interactif observé au Sprint 0 :
- codex        : `codex exec` exige `--skip-git-repo-check` hors repo git ;
                 `--dangerously-bypass-approvals-and-sandbox` = plein auto
                 (prévu pour un environnement déjà sandboxé = notre conteneur),
                 sinon `-s read-only` pour un test inoffensif.
- claude       : `claude -p` marche direct ; `--dangerously-skip-permissions`
                 pour l'autonomie des outils.
- cursor-agent : `cursor-agent -p` exige `--force` (alias `--yolo`) pour ne pas
                 demander de confiance ; `--output-format text` pour une sortie nette.
"""

from __future__ import annotations

from .subprocess_adapter import SubprocessAgentAdapter
from ..models.mission import AgentProvider


def make_codex_adapter(
    model: str | None = None, *, auto: bool = True
) -> SubprocessAgentAdapter:
    """Adaptateur OpenAI Codex CLI."""

    def build(prompt: str) -> list[str]:
        cmd = ["codex", "exec", "--skip-git-repo-check"]
        if model:
            cmd += ["-m", model]
        cmd += (
            ["--dangerously-bypass-approvals-and-sandbox"] if auto else ["-s", "read-only"]
        )
        cmd.append(prompt)
        return cmd

    return SubprocessAgentAdapter(
        provider=AgentProvider.CODEX,
        version_cmd=["codex", "--version"],
        build_run_command=build,
        model=model,
    )


def make_claude_adapter(
    model: str | None = None, *, auto: bool = True
) -> SubprocessAgentAdapter:
    """Adaptateur Anthropic Claude Code CLI."""

    def build(prompt: str) -> list[str]:
        cmd = ["claude", "-p"]
        if model:
            cmd += ["--model", model]
        if auto:
            cmd.append("--dangerously-skip-permissions")
        cmd.append(prompt)
        return cmd

    return SubprocessAgentAdapter(
        provider=AgentProvider.CLAUDE,
        version_cmd=["claude", "--version"],
        build_run_command=build,
        model=model,
    )


def make_cursor_adapter(
    model: str | None = None, *, auto: bool = True
) -> SubprocessAgentAdapter:
    """Adaptateur Cursor Agent CLI (mode auto de sélection de modèle si dispo)."""

    def build(prompt: str) -> list[str]:
        cmd = ["cursor-agent", "-p", "--output-format", "text"]
        if model:
            cmd += ["--model", model]
        if auto:
            cmd.append("--force")
        cmd.append(prompt)
        return cmd

    return SubprocessAgentAdapter(
        provider=AgentProvider.CURSOR,
        version_cmd=["cursor-agent", "--version"],
        build_run_command=build,
        model=model,
    )
