"""Génération de rapports techniques reproductibles (Sprint 6)."""

from __future__ import annotations

from ..models.challenge import Challenge
from ..models.evidence import Evidence
from ..models.flag import FlagCandidate, FlagStatus


def _flag_line(flag: FlagCandidate | None) -> str:
    if flag is None:
        return "- Aucun flag candidat."
    status = flag.validation_status.value
    reproduced = flag.validation_status in (FlagStatus.REPRODUCED, FlagStatus.ACCEPTED)
    mark = "✅" if reproduced else "⚠️"
    return f"- `{flag.value}` — statut : **{status}** {mark}"


def build_markdown_report(
    challenge: Challenge,
    evidences: list[Evidence],
    flag: FlagCandidate | None,
    *,
    strategies: list[str] | None = None,
    agents: list[str] | None = None,
    tools: list[str] | None = None,
    uncertainties: str = "",
) -> str:
    """Construit un rapport Markdown reproductible pour un challenge."""
    strategies = strategies or []
    agents = agents or []
    tools = tools or []

    lines: list[str] = []
    lines.append(f"# Rapport — {challenge.title}")
    lines.append("")
    lines.append("## Résumé")
    lines.append(f"- **Catégorie** : {challenge.category.value}")
    lines.append(f"- **Difficulté** : {challenge.difficulty.value}")
    lines.append(f"- **Source** : {challenge.source}")
    if challenge.description:
        lines.append(f"- **Énoncé** : {challenge.description}")
    lines.append("")

    lines.append("## Flag")
    lines.append(_flag_line(flag))
    if flag and flag.reproduction_reference:
        lines.append(f"- **Reproduction** : {flag.reproduction_reference}")
    lines.append("")

    lines.append("## Stratégies tentées")
    lines.extend(f"- {s}" for s in strategies) if strategies else lines.append("- (aucune renseignée)")
    lines.append("")

    lines.append("## Agents impliqués")
    lines.extend(f"- {a}" for a in agents) if agents else lines.append("- (aucun renseigné)")
    lines.append("")

    lines.append("## Outils utilisés")
    lines.extend(f"- {t}" for t in tools) if tools else lines.append("- (aucun renseigné)")
    lines.append("")

    lines.append("## Preuves")
    if evidences:
        for e in evidences:
            lines.append(f"- [{e.verification_status.value}] {e.observation} "
                         f"(source: {e.source})")
            if e.checksum:
                lines.append(f"  - checksum: `{e.checksum}`")
    else:
        lines.append("- (aucune preuve enregistrée)")
    lines.append("")

    lines.append("## Incertitudes")
    lines.append(uncertainties or "- (aucune renseignée)")
    lines.append("")

    return "\n".join(lines)
