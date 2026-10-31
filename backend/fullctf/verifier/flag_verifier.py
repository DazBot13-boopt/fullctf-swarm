"""Flag Verifier (Sprint 6) : fait avancer un flag dans ses états de validation.

Principe clé : un flag local n'est JAMAIS accepté automatiquement. Il doit passer
par candidate -> format_valid -> reproduced avant de pouvoir être accepté.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from ..models.flag import FlagCandidate, FlagStatus, can_flag_transition

# Format de flag par défaut : FLAG{...} / CTF{...} / nom{...}. Configurable.
DEFAULT_FLAG_PATTERN = re.compile(r"^[A-Za-z0-9_]{2,15}\{[^\n}]{1,200}\}$")

# Version non ancrée, pour EXTRAIRE des flags au milieu d'un texte (sortie d'agent).
_FLAG_FINDALL = re.compile(r"[A-Za-z0-9_]{2,15}\{[^\n}]{1,200}\}")

def is_placeholder_flag(value: str) -> bool:
    """True si le candidat est manifestement un placeholder, pas un vrai flag.

    On se base sur le CONTENU (pas le préfixe : « flag{…} » / « ctf{…} » sont de
    vrais préfixes courants). Un vrai flag ne contient jamais « ... »/« … », et un
    contenu vide ou d'exemple (XXX) trahit un gabarit de prompt (ex. NOM{...}).
    """
    if "..." in value or "…" in value:
        return True
    inside = value[value.find("{") + 1: value.rfind("}")].strip()
    return not inside or inside.lower() in {"x", "xx", "xxx", "xxxx", "flag", "placeholder"}


def extract_flags(text: str) -> list[str]:
    """Extrait les flags candidats d'un texte libre (sortie d'agent/outil).

    Retourne les occurrences uniques, dans l'ordre d'apparition. Les placeholders
    de format (NOM{...}, FLAG{...}, ...) sont écartés : jamais de faux flag.
    """
    seen: dict[str, None] = {}
    for match in _FLAG_FINDALL.findall(text or ""):
        if is_placeholder_flag(match):
            continue
        seen.setdefault(match, None)
    return list(seen.keys())


class FlagVerifier:
    """Vérifie et fait progresser un flag candidat, états contrôlés."""

    def __init__(self, pattern: re.Pattern[str] = DEFAULT_FLAG_PATTERN):
        self.pattern = pattern

    def _advance(self, flag: FlagCandidate, target: FlagStatus) -> FlagCandidate:
        """Applique une transition d'état en la validant (garde-fou)."""
        if not can_flag_transition(flag.validation_status, target):
            raise ValueError(
                f"Transition de flag interdite : "
                f"{flag.validation_status.value} -> {target.value}"
            )
        return flag.model_copy(update={"validation_status": target})

    def check_format(self, flag: FlagCandidate) -> FlagCandidate:
        """candidate -> format_valid si le format colle, sinon rejected."""
        if self.pattern.match(flag.value):
            return self._advance(flag, FlagStatus.FORMAT_VALID)
        return self._advance(flag, FlagStatus.REJECTED)

    def reproduce(
        self, flag: FlagCandidate, reproducer: Callable[[], bool], reference: str
    ) -> FlagCandidate:
        """format_valid -> reproduced si la reproduction réussit.

        `reproducer` rejoue la résolution et retourne True si elle redonne le flag.
        C'est ce qui distingue un vrai flag d'un faux positif.
        """
        if reproducer():
            advanced = self._advance(flag, FlagStatus.REPRODUCED)
            return advanced.model_copy(update={"reproduction_reference": reference})
        return self._advance(flag, FlagStatus.REJECTED)

    def accept(self, flag: FlagCandidate, platform_feedback: str = "") -> FlagCandidate:
        """reproduced -> accepted (après soumission réussie à la plateforme)."""
        advanced = self._advance(flag, FlagStatus.ACCEPTED)
        return advanced.model_copy(update={"platform_feedback": platform_feedback})

    def reject(self, flag: FlagCandidate, platform_feedback: str = "") -> FlagCandidate:
        """Rejette explicitement un flag (depuis n'importe quel état non terminal)."""
        advanced = self._advance(flag, FlagStatus.REJECTED)
        return advanced.model_copy(update={"platform_feedback": platform_feedback})
