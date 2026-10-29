"""Mémoire d'expérience + recherche (Sprint 8).

On indexe les résolutions passées (techniques, outcome, référence de rapport) pour
que les agents puissent retrouver "comment on a résolu un challenge similaire".

Recherche LEXICALE pour l'instant (robuste, zéro dépendance lourde). L'interface
`search` est pensée pour accueillir un backend vectoriel plus tard, SI son intérêt
est démontré (cf. cahier des charges : pas de dépendance lourde sans besoin).

Les entrées sont des DONNÉES, jamais des instructions : un agent qui les consulte
doit les traiter comme des indices non fiables à vérifier.
"""

from __future__ import annotations

import re
from uuid import uuid4

from pydantic import BaseModel, Field

from ..models.challenge import Category, Difficulty

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class MemoryEntry(BaseModel):
    """Une expérience passée indexée."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    challenge_title: str
    category: Category = Category.UNKNOWN
    difficulty: Difficulty = Difficulty.UNKNOWN
    techniques: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    outcome: str = Field(default="solved", description="solved / failed / partial")
    summary: str = ""
    report_reference: str | None = None

    def searchable_text(self) -> str:
        parts = [
            self.challenge_title,
            self.category.value,
            self.summary,
            " ".join(self.techniques),
            " ".join(self.tools_used),
        ]
        return " ".join(parts)


class SearchResult(BaseModel):
    entry: MemoryEntry
    score: float


class MemoryStore:
    """Dépôt d'expériences avec recherche lexicale pondérée."""

    def __init__(self) -> None:
        self._entries: dict[str, MemoryEntry] = {}

    def add(self, entry: MemoryEntry) -> MemoryEntry:
        self._entries[entry.id] = entry
        return entry

    def get(self, entry_id: str) -> MemoryEntry:
        if entry_id not in self._entries:
            raise KeyError(f"Entrée mémoire inconnue : {entry_id}")
        return self._entries[entry_id]

    def all(self) -> list[MemoryEntry]:
        return list(self._entries.values())

    def search(
        self, query: str, *, limit: int = 5, category: Category | None = None
    ) -> list[SearchResult]:
        """Recherche lexicale : score = recouvrement de tokens, bonus de catégorie.

        Les résultats citent toujours leur source (report_reference).
        """
        q_tokens = set(_tokenize(query))
        if not q_tokens:
            return []

        results: list[SearchResult] = []
        for entry in self._entries.values():
            if category is not None and entry.category != category:
                continue
            e_tokens = set(_tokenize(entry.searchable_text()))
            overlap = len(q_tokens & e_tokens)
            if overlap == 0:
                continue
            score = overlap / len(q_tokens)
            if category is not None and entry.category == category:
                score += 0.5  # bonus même catégorie
            results.append(SearchResult(entry=entry, score=round(score, 4)))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]
