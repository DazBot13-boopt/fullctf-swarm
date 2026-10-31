"""Persistance : ne pas abandonner, ne pas boucler, partager les trouvailles.

Trois briques inspirées des solveurs qui surpassent les humains :
- **bump / insights** : on passe à l'agent suivant ce que les précédents ont tenté,
  pour qu'il fasse AUTRE CHOSE au lieu de répéter.
- **never give up** : on peut relancer un agent (retries) avec ce contexte.
- **anti-boucle** : si un nouvel essai n'apporte aucun progrès, on arrête d'insister.

Les trouvailles d'un agent (sa sortie) sont des DONNÉES non fiables : on les encadre
avec wrap_untrusted avant de les redonner à un autre agent.
"""

from __future__ import annotations

import difflib

from ..verifier.injection_guard import wrap_untrusted


def summarize_attempt(output: str, max_chars: int = 1500) -> str:
    """Résumé compact d'un essai : la fin de la sortie (là où sont les conclusions)."""
    text = (output or "").strip()
    if len(text) <= max_chars:
        return text
    return "…" + text[-max_chars:]


def no_progress(prev_output: str, cur_output: str, threshold: float = 0.95) -> bool:
    """True si deux essais sont quasi identiques (agent coincé, aucun progrès)."""
    a = (prev_output or "").strip()
    b = (cur_output or "").strip()
    if not a or not b:
        return False
    if a == b:
        return True
    ratio = difflib.SequenceMatcher(None, a[-4000:], b[-4000:]).ratio()
    return ratio >= threshold


def build_insights_block(prior_findings: list[str]) -> str:
    """Bloc de prompt listant les tentatives précédentes (à NE PAS répéter)."""
    if not prior_findings:
        return ""
    joined = "\n\n---\n\n".join(prior_findings[-4:])
    body = (
        "Les agents précédents n'ont PAS trouvé le flag. Voici ce qui a déjà été "
        "tenté — n'y reviens pas, essaie une approche DIFFÉRENTE :\n\n" + joined
    )
    return wrap_untrusted("tentatives précédentes", body)
