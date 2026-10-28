"""Policies de mission : autonomie des agents et accès aux outils.

Ces policies sont lues par le Commander pour adapter son comportement.
Rien n'est codé en dur : tout est configurable par mission (ou via un profil).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ExecutionMode(str, Enum):
    """Mode d'exécution d'une mission."""

    LOCAL_ONLY = "local_only"  # Travail hors-ligne sur les fichiers, juste trouver le flag
    CONNECTED = "connected"  # Accès à la plateforme / cible autorisée


class SandboxType(str, Enum):
    """Type d'isolation pour l'exécution des outils."""

    CONTAINER = "container"  # Conteneur Docker jetable (recommandé)
    NONE = "none"  # Aucune isolation (déconseillé, réservé aux tests)


class AutonomyPolicy(BaseModel):
    """Réglages d'autonomie, activables/désactivables par mission.

    Exemples de combinaisons :
      - local_only + auto_submit=False : propose le flag, l'humain soumet.
      - connected + auto_submit=True + human_checkpoints=False : autonomie complète.
      - connected + auto_submit=True + human_checkpoints=True : autonome mais
        demande avant les actions sensibles.
    """

    auto_submit_flag: bool = Field(
        default=False,
        description="Si True, l'agent soumet le flag lui-même. Sinon il le propose.",
    )
    human_checkpoints: bool = Field(
        default=True,
        description="Si True, l'agent demande l'avis humain aux points clés.",
    )
    mode: ExecutionMode = Field(
        default=ExecutionMode.LOCAL_ONLY,
        description="local_only (hors-ligne) ou connected (plateforme autorisée).",
    )


class ToolAccessPolicy(BaseModel):
    """Policy d'accès aux outils : liberté d'installation + performance.

    Liberté totale À L'INTÉRIEUR du conteneur jetable.
    L'hôte n'est jamais modifié par les agents.
    """

    can_install: bool = Field(
        default=True,
        description="Autorise pip/apt/git clone... dans le conteneur.",
    )
    sandbox: SandboxType = Field(
        default=SandboxType.CONTAINER,
        description="Tout se passe dans un conteneur jetable.",
    )
    persist_installs: bool = Field(
        default=True,
        description="Cache partagé : ne jamais réinstaller deux fois le même outil.",
    )
    network_for_install: bool = Field(
        default=True,
        description="Autorise le réseau pour télécharger les outils.",
    )
    base_image: str = Field(
        default="fullctf-arsenal:latest",
        description="Image Docker 'fat' pré-équipée de l'arsenal CTF.",
    )
