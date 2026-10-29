"""Exécution d'outils dans un sandbox (Sprint 5).

Deux backends :
- LocalToolRunner : exécute directement (pour les tests / machine de confiance).
- DockerToolRunner : exécute dans un conteneur jetable (production, isolation).

La sortie est TOUJOURS structurée (ToolRun) pour que l'agent l'exploite facilement.
"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod

from pydantic import BaseModel

from .manifest import ToolManifest


class ToolRun(BaseModel):
    """Résultat structuré d'une exécution d'outil."""

    tool_id: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def success(self) -> bool:
        return self.returncode == 0 and not self.timed_out


class ToolRunner(ABC):
    """Contrat commun des exécuteurs d'outils."""

    @abstractmethod
    def run(self, manifest: ToolManifest, args: list[str], workspace: str) -> ToolRun:
        raise NotImplementedError


class LocalToolRunner(ToolRunner):
    """Exécute l'outil directement sur l'hôte (tests / machine de confiance)."""

    def run(self, manifest: ToolManifest, args: list[str], workspace: str) -> ToolRun:
        cmd = [manifest.command, *args]
        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace or None,
                capture_output=True,
                text=True,
                timeout=manifest.timeout_seconds,
                check=False,
            )
        except FileNotFoundError:
            return ToolRun(
                tool_id=manifest.id, command=cmd, returncode=127,
                stdout="", stderr=f"outil introuvable: {manifest.command}",
            )
        except subprocess.TimeoutExpired as e:
            return ToolRun(
                tool_id=manifest.id, command=cmd, returncode=-1,
                stdout=e.stdout or "", stderr="timeout", timed_out=True,
            )
        return ToolRun(
            tool_id=manifest.id, command=cmd, returncode=proc.returncode,
            stdout=proc.stdout, stderr=proc.stderr,
        )


class DockerToolRunner(ToolRunner):
    """Exécute l'outil dans un conteneur Docker jetable (isolation).

    Liberté totale à l'intérieur ; l'hôte n'est jamais touché. Le conteneur est
    supprimé après exécution (--rm). Réseau coupé par défaut (--network none),
    sauf si l'outil en a besoin.
    """

    def __init__(self, image: str = "fullctf-arsenal:latest", docker_bin: str = "docker"):
        self.image = image
        self.docker_bin = docker_bin

    def _build_docker_command(
        self, manifest: ToolManifest, args: list[str], workspace: str
    ) -> list[str]:
        network = "bridge" if manifest.needs_network else "none"
        return [
            self.docker_bin, "run", "--rm",
            "--network", network,
            "--memory", "4g", "--cpus", "2",
            "-v", f"{workspace}:/work",
            "-w", "/work",
            self.image,
            manifest.command, *args,
        ]

    def run(self, manifest: ToolManifest, args: list[str], workspace: str) -> ToolRun:
        cmd = self._build_docker_command(manifest, args, workspace)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=manifest.timeout_seconds, check=False,
            )
        except FileNotFoundError:
            return ToolRun(
                tool_id=manifest.id, command=cmd, returncode=127,
                stdout="", stderr="docker introuvable",
            )
        except subprocess.TimeoutExpired as e:
            return ToolRun(
                tool_id=manifest.id, command=cmd, returncode=-1,
                stdout=e.stdout or "", stderr="timeout", timed_out=True,
            )
        return ToolRun(
            tool_id=manifest.id, command=cmd, returncode=proc.returncode,
            stdout=proc.stdout, stderr=proc.stderr,
        )
