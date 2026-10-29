"""Registre de playbooks : sélection du meilleur playbook pour un challenge."""

from __future__ import annotations

from ..models.challenge import Category, Challenge
from .playbook import Playbook


class PlaybookRegistry:
    """Catalogue de playbooks, sélectionnable par catégorie + triggers."""

    def __init__(self) -> None:
        self._playbooks: dict[str, Playbook] = {}

    def register(self, playbook: Playbook) -> None:
        self._playbooks[playbook.id] = playbook

    def register_many(self, playbooks: list[Playbook]) -> None:
        for p in playbooks:
            self.register(p)

    def get(self, playbook_id: str) -> Playbook:
        if playbook_id not in self._playbooks:
            raise KeyError(f"Playbook inconnu : {playbook_id}")
        return self._playbooks[playbook_id]

    def for_category(self, category: Category) -> list[Playbook]:
        return [p for p in self._playbooks.values() if p.category == category]

    def select(self, challenge: Challenge) -> Playbook | None:
        """Choisit le meilleur playbook : même catégorie, puis score de triggers.

        Retourne None si aucun playbook ne correspond à la catégorie.
        """
        candidates = self.for_category(challenge.category)
        if not candidates:
            return None
        text = f"{challenge.title} {challenge.description} {' '.join(challenge.attachments)}"
        # Meilleur score de triggers ; à égalité, on garde le premier déclaré.
        return max(candidates, key=lambda p: p.matches(text))

    def all(self) -> list[Playbook]:
        return list(self._playbooks.values())
