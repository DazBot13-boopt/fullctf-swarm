"""Playbooks : recettes réutilisables par catégorie (Sprint 7).

Un playbook transforme l'intelligence de l'agent en vitesse : au lieu de tâtonner,
l'agent suit une séquence d'étapes éprouvées, avec les bons outils dans le bon ordre.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..models.challenge import Category


class PlaybookStep(BaseModel):
    """Une étape d'un playbook."""

    description: str = Field(description="Ce que l'agent doit faire.")
    tool: str | None = Field(default=None, description="Outil recommandé (id du registre).")
    args_hint: list[str] = Field(
        default_factory=list, description="Indices d'arguments pour l'outil."
    )


class Playbook(BaseModel):
    """Recette ordonnée pour une catégorie (ou un service récurrent)."""

    id: str
    category: Category
    triggers: list[str] = Field(
        default_factory=list,
        description="Mots-clés qui indiquent que ce playbook s'applique.",
    )
    description: str = ""
    steps: list[PlaybookStep] = Field(default_factory=list)

    def matches(self, text: str) -> int:
        """Nombre de triggers présents dans le texte (score de pertinence)."""
        low = text.lower()
        return sum(1 for t in self.triggers if t.lower() in low)
