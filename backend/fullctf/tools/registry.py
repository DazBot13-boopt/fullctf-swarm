"""Registre d'outils : catalogue versionné + sélection par catégorie (Sprint 5)."""

from __future__ import annotations

import shutil

from .manifest import ToolCategory, ToolManifest


class ToolRegistry:
    """Catalogue des outils déclarés, consultable par le Commander/agents."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolManifest] = {}

    def register(self, manifest: ToolManifest) -> None:
        self._tools[manifest.id] = manifest

    def register_many(self, manifests: list[ToolManifest]) -> None:
        for m in manifests:
            self.register(m)

    def get(self, tool_id: str) -> ToolManifest:
        if tool_id not in self._tools:
            raise KeyError(f"Outil inconnu : {tool_id}")
        return self._tools[tool_id]

    def all(self) -> list[ToolManifest]:
        return list(self._tools.values())

    def by_category(self, category: ToolCategory) -> list[ToolManifest]:
        """Outils d'une catégorie (pour un profil de spécialiste)."""
        return [t for t in self._tools.values() if t.category == category]

    def is_installed(self, tool_id: str) -> bool:
        """Vérifie que le binaire de base de l'outil est disponible (PATH)."""
        manifest = self.get(tool_id)
        return shutil.which(manifest.command) is not None

    def installed_tools(self) -> list[ToolManifest]:
        """Outils réellement installés sur le système courant."""
        return [t for t in self._tools.values() if shutil.which(t.command) is not None]
