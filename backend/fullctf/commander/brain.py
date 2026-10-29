"""Cerveau LLM du Commander (greffé au-dessus du noyau code).

Le LLM *propose*, le code *valide*. Ici, le cerveau aide seulement sur une décision
floue : classer un challenge quand les règles n'y arrivent pas (catégorie MISC/UNKNOWN).

Le noyau code garde tous les garde-fous (budgets, transitions, sécurité). Si le LLM
répond n'importe quoi ou échoue, on retombe sur la décision par règles.
"""

from __future__ import annotations

from ..agents.base import AgentAdapter
from ..models.challenge import Category, Challenge

_KNOWN = [c for c in Category if c not in (Category.UNKNOWN,)]


class CommanderBrain:
    """Classification assistée par un agent LLM existant (pas de 4e abonnement)."""

    def __init__(self, adapter: AgentAdapter) -> None:
        self.adapter = adapter

    def _prompt(self, challenge: Challenge) -> str:
        cats = ", ".join(c.value for c in _KNOWN)
        return (
            "Classe ce challenge CTF dans UNE catégorie parmi : "
            f"{cats}. Réponds uniquement par le nom de la catégorie.\n\n"
            f"Titre: {challenge.title}\n"
            f"Description: {challenge.description}\n"
            f"Pièces jointes: {', '.join(challenge.attachments)}"
        )

    def classify(self, challenge: Challenge, fallback: Category) -> Category:
        """Demande au LLM de classer ; valide la réponse ; sinon repli sur fallback.

        Le code reste maître : toute réponse non reconnue est ignorée.
        """
        result = self.adapter.run_mission(self._prompt(challenge), "", 30)
        if not result.success:
            return fallback

        answer = result.output.strip().lower()
        for category in _KNOWN:
            if category.value in answer:
                return category
        return fallback  # réponse inexploitable => on garde la décision par règles
