"""Adaptateur qui exécute un worker DANS le conteneur jetable (fullctf-worker).

Conforme au cahier des charges :
- liberté totale DANS le conteneur, l'hôte n'est JAMAIS modifié ;
- auth montée EN LIVE depuis l'hôte (le compte actif du serveur est utilisé :
  un logout/login d'un compte sur l'hôte suffit à changer de compte) ;
- fichiers du challenge montés en lecture seule (originaux immuables) ;
- entrée non fiable (énoncé) encadrée par wrap_untrusted (anti-injection) ;
- un refus/filtre fournisseur est signalé comme un échec -> le Commander escalade.

L'exécution Docker est injectable (`exec_run`) pour rester testable sans Docker
ni vrais agents.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from .base import AgentAdapter, AgentAvailability, MissionResult
from ..models.mission import AgentProvider
from ..models.policies import ExecutionMode
from ..verifier.injection_guard import wrap_untrusted

# Fichier d'auth hôte (source) -> point de montage dans le conteneur (dest), par agent.
HOST_AUTH: dict[AgentProvider, tuple[str, str]] = {
    AgentProvider.CODEX: (".codex/auth.json", "/root/.codex/auth.json"),
    AgentProvider.CLAUDE: (".claude/.credentials.json", "/root/.claude/.credentials.json"),
    AgentProvider.CURSOR: (".config/cursor/auth.json", "/root/.config/cursor/auth.json"),
}

# Marqueurs de refus/filtre d'un fournisseur => échec de l'agent, à escalader.
REFUSAL_MARKERS: tuple[str, ...] = (
    "flagged for possible cybersecurity risk",
    "je ne peux pas t'aider",
    "je ne fournis pas",
    "i can't help",
    "i cannot help",
    "i won't help",
    "i can't assist",
    "cannot assist with",
    "not able to assist",
    "i'm not able to help",
)

# Type de la fonction d'exécution injectable : (argv, timeout) -> (returncode, output)
ExecRun = Callable[[list[str], int], "tuple[int, str]"]


def _home() -> Path:
    return Path(os.path.expanduser("~"))


class ContainerAgentAdapter(AgentAdapter):
    """Pilote un worker (codex|claude|cursor) dans un conteneur jetable."""

    def __init__(
        self,
        provider: AgentProvider,
        *,
        challenge_files_dir: str | Path,
        target: str | None = None,
        description: str = "",
        mode: ExecutionMode = ExecutionMode.CONNECTED,
        image: str = "fullctf-worker:latest",
        codex_model: str = "gpt-5.6-terra",
        agents_md: str | Path | None = None,
        exec_run: ExecRun | None = None,
    ) -> None:
        self.provider = provider
        self.files_dir = Path(challenge_files_dir)
        self.target = target
        self.description = description
        self.mode = mode
        self.image = image
        self.codex_model = codex_model
        self.agents_md = Path(agents_md) if agents_md else None
        self._exec = exec_run or self._docker_exec
        self._proc: subprocess.Popen[str] | None = None

    # --- disponibilité : auth présente sur l'hôte (jamais le secret lui-même) ---
    def check_availability(self) -> AgentAvailability:
        rel, _ = HOST_AUTH[self.provider]
        auth_file = _home() / rel
        authed = auth_file.is_file()
        if self.provider == AgentProvider.CURSOR and not authed:
            authed = bool(os.environ.get("CURSOR_API_KEY"))
        return AgentAvailability(
            provider=self.provider, installed=True, authenticated=authed
        )

    # --- construction de la commande CLI dans le conteneur ---
    def _cli_command(self, prompt: str) -> list[str]:
        if self.provider == AgentProvider.CODEX:
            return [
                "codex", "exec", "--skip-git-repo-check",
                "--dangerously-bypass-approvals-and-sandbox",
                "-m", self.codex_model, prompt,
            ]
        if self.provider == AgentProvider.CLAUDE:
            return ["claude", "-p", "--dangerously-skip-permissions", prompt]
        if self.provider == AgentProvider.CURSOR:
            return ["cursor-agent", "-p", "--output-format", "text", "--force", prompt]
        raise ValueError(f"fournisseur inconnu : {self.provider}")

    def _full_prompt(self, objective: str) -> str:
        parts = [objective.strip() or "Résous ce challenge CTF autorisé et trouve le flag."]
        if self.mode == ExecutionMode.CONNECTED and self.target:
            parts.append(f"CIBLE LIVE AUTORISÉE (reste strictement dessus) : {self.target}")
        else:
            parts.append(
                "MODE LOCAL : travaille uniquement sur les fichiers de ./files, "
                "pas de cible réseau."
            )
        parts.append("SOURCE : ./files/ (monté en lecture seule).")
        if self.description:
            parts.append(wrap_untrusted("énoncé du challenge", self.description))
        parts.append(
            "LIVRABLE : 1) FLAG exact (format NOM{...}) ; 2) VULNÉRABILITÉ (1-2 phrases) ; "
            "3) REPRODUCTION (commandes exactes). Ne soumets rien toi-même. "
            "Ne prétends pas avoir réussi sans avoir obtenu le flag depuis la cible."
        )
        return "\n\n".join(parts)

    def _docker_run_argv(self, prompt: str) -> list[str]:
        home = _home()
        argv = [
            "docker", "run", "--rm",
            "--cap-add=NET_RAW", "--cap-add=NET_ADMIN",
            "-e", "IS_SANDBOX=1",
        ]
        if os.environ.get("CURSOR_API_KEY"):
            argv += ["-e", f"CURSOR_API_KEY={os.environ['CURSOR_API_KEY']}"]
        # auth montée en live (tous les comptes présents sur l'hôte)
        for _prov, (rel, dst) in HOST_AUTH.items():
            src = home / rel
            if src.is_file():
                argv += ["-v", f"{src}:{dst}:ro"]
        # fichiers du challenge en lecture seule
        argv += ["-v", f"{self.files_dir.resolve()}:/work/files:ro"]
        # cadrage CTF (lu par codex/cursor)
        if self.agents_md and self.agents_md.is_file():
            argv += ["-v", f"{self.agents_md.resolve()}:/work/AGENTS.md:ro"]
        argv.append(self.image)
        argv += self._cli_command(prompt)
        return argv

    def _docker_exec(self, argv: list[str], timeout: int) -> tuple[int, str]:
        self._proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        try:
            out, _ = self._proc.communicate(timeout=timeout)
            rc = self._proc.returncode
        except subprocess.TimeoutExpired:
            self.cancel()
            return (124, "timeout")
        finally:
            self._proc = None
        return (rc, out or "")

    def run_mission(self, prompt: str, workspace: str, timeout_seconds: int) -> MissionResult:
        full = self._full_prompt(prompt)
        argv = self._docker_run_argv(full)
        rc, out = self._exec(argv, timeout_seconds)
        out = out or ""
        refused = any(m in out.lower() for m in REFUSAL_MARKERS)
        if rc != 0 or refused:
            return MissionResult(
                success=False,
                output=out,
                error="refus/filtre fournisseur" if refused else f"exit={rc}",
            )
        return MissionResult(success=True, output=out, model_used=self._model_label())

    def _model_label(self) -> str | None:
        if self.provider == AgentProvider.CODEX:
            return self.codex_model
        return None

    def cancel(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
