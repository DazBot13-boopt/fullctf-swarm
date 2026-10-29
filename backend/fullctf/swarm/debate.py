"""Débat & vérification croisée (Sprint 7).

Un agent propose une solution/flag ; d'autres agents la révisent indépendamment.
Le verdict du débat distingue l'accord du désaccord — on ne croit pas une solution
sur parole, on la fait réviser.

Avec un seul agent disponible, le débat devient de l'auto-révision (l'agent
critique sa propre proposition).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..agents.registry import AgentRegistry
from ..models.mission import AgentProvider

# Marqueurs attendus dans la réponse d'un réviseur.
AGREE_MARKERS = ("AGREE", "D'ACCORD", "VALID", "CONFIRM")
DISAGREE_MARKERS = ("DISAGREE", "PAS D'ACCORD", "INVALID", "REJECT")


@dataclass
class ReviewVerdict:
    """Verdict d'un réviseur sur une proposition."""

    reviewer: AgentProvider
    agree: bool
    rationale: str


@dataclass
class DebateOutcome:
    """Résultat global d'un débat."""

    agree_count: int
    disagree_count: int
    verdicts: list[ReviewVerdict]

    @property
    def consensus(self) -> bool:
        """Consensus = majorité stricte d'accords."""
        return self.agree_count > self.disagree_count


def _interpret(output: str) -> bool:
    """Interprète la réponse d'un réviseur en accord/désaccord.

    Un désaccord explicite prime (prudence : on ne valide pas un flag douteux).
    """
    up = output.upper()
    if any(m in up for m in DISAGREE_MARKERS):
        return False
    if any(m in up for m in AGREE_MARKERS):
        return True
    return False  # Par défaut : prudence, pas d'accord implicite.


class DebateEngine:
    """Fait réviser une proposition par un ou plusieurs agents."""

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry

    def _build_review_prompt(self, proposal: str) -> str:
        return (
            "Révise cette proposition de solution de façon critique et indépendante. "
            "Réponds par AGREE ou DISAGREE suivi d'une justification.\n\n"
            f"Proposition :\n{proposal}"
        )

    def review(
        self,
        proposal: str,
        reviewers: list[AgentProvider],
        workspace: str,
        timeout: int,
    ) -> DebateOutcome:
        """Fait réviser la proposition par chaque réviseur, puis agrège."""
        prompt = self._build_review_prompt(proposal)
        verdicts: list[ReviewVerdict] = []
        for provider in reviewers:
            adapter = self.registry.get(provider)
            result = adapter.run_mission(prompt, workspace, timeout)
            agree = _interpret(result.output) if result.success else False
            verdicts.append(
                ReviewVerdict(
                    reviewer=provider,
                    agree=agree,
                    rationale=result.output if result.success else (result.error or ""),
                )
            )
        agree_count = sum(1 for v in verdicts if v.agree)
        return DebateOutcome(
            agree_count=agree_count,
            disagree_count=len(verdicts) - agree_count,
            verdicts=verdicts,
        )
