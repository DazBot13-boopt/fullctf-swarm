"""Manifeste d'outil : décrit un outil CTF de façon structurée (Sprint 5).

Un manifeste permet au Commander et aux agents de savoir quel outil utiliser,
avec quels paramètres, quelles limites, et comment interpréter sa sortie.
Rien n'est exécuté ici : c'est de la description.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ToolCategory(str, Enum):
    """Catégorie d'un outil (aligne avec les catégories de challenges)."""

    WEB = "web"
    PWN = "pwn"
    REVERSE = "reverse"
    CRYPTO = "crypto"
    FORENSIC = "forensic"
    NETWORK = "network"
    MISC = "misc"


class ToolManifest(BaseModel):
    """Description complète d'un outil de l'arsenal."""

    id: str = Field(description="Identifiant unique, ex. 'pwntools'.")
    version: str = Field(default="unknown", description="Version installée.")
    category: ToolCategory
    command: str = Field(description="Exécutable de base, ex. 'ffuf'.")
    description: str = ""
    required_binaries: list[str] = Field(
        default_factory=list, description="Binaires requis sur le système."
    )
    parameters: list[str] = Field(
        default_factory=list, description="Paramètres/flags principaux."
    )
    timeout_seconds: int = Field(default=300, description="Timeout par défaut.")
    needs_network: bool = Field(
        default=False, description="L'outil a-t-il besoin du réseau ?"
    )
    produces_artifacts: bool = Field(
        default=False, description="Produit-il des fichiers (dumps, sorties) ?"
    )
    verification: str = Field(
        default="",
        description="Comment vérifier que la sortie est exploitable.",
    )
