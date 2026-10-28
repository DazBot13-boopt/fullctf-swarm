"""Adaptateur subprocess générique : pilote un CLI réel via la ligne de commande.

C'est la base des adaptateurs Codex / Claude Code / Cursor. On ne dépend d'aucun
code tiers : on lance le CLI comme un utilisateur le ferait, dans le workspace isolé.

NE LIT JAMAIS de secret : la détection ne regarde que la version.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable

from .base import AgentAdapter, AgentAvailability, MissionResult
from ..models.mission import AgentProvider


class SubprocessAgentAdapter(AgentAdapter):
    """Pilote un CLI externe via subprocess.

    Args:
        provider: le fournisseur (codex/claude/cursor).
        version_cmd: commande qui affiche la version (ex. ["codex", "--version"]).
        build_run_command: fonction (prompt) -> liste d'arguments à exécuter.
        model: modèle configuré (optionnel ; le vrai modèle est loggé si détectable).
    """

    def __init__(
        self,
        provider: AgentProvider,
        version_cmd: list[str],
        build_run_command: Callable[[str], list[str]],
        model: str | None = None,
    ) -> None:
        self.provider = provider
        self._version_cmd = version_cmd
        self._build_run_command = build_run_command
        self._model = model
        self._process: subprocess.Popen[str] | None = None

    def check_availability(self) -> AgentAvailability:
        try:
            proc = subprocess.run(
                self._version_cmd,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return AgentAvailability(
                provider=self.provider, installed=False, authenticated=False
            )

        installed = proc.returncode == 0
        version = proc.stdout.strip() or proc.stderr.strip() if installed else None
        # On considère "authentifié" comme à confirmer par run réel : par défaut
        # True si installé (l'adaptateur concret peut affiner).
        return AgentAvailability(
            provider=self.provider,
            installed=installed,
            authenticated=installed,
            version=version,
            model=self._model,
        )

    def run_mission(self, prompt: str, workspace: str, timeout_seconds: int) -> MissionResult:
        cmd = self._build_run_command(prompt)
        try:
            self._process = subprocess.Popen(
                cmd,
                cwd=workspace or None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            out, err = self._process.communicate(timeout=timeout_seconds)
            rc = self._process.returncode
        except FileNotFoundError:
            return MissionResult(success=False, output="", error="CLI introuvable")
        except subprocess.TimeoutExpired:
            self.cancel()
            return MissionResult(success=False, output="", error="timeout")
        finally:
            self._process = None

        if rc != 0:
            return MissionResult(
                success=False, output=out, model_used=self._model, error=err.strip()
            )
        return MissionResult(success=True, output=out, model_used=self._model)

    def cancel(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
