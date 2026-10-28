"""Détecteur de stagnation : décide quand escalader."""

from __future__ import annotations


class StagnationDetector:
    """Détecte l'absence de progrès pour déclencher une escalade.

    On compte les tentatives consécutives sans progrès. On peut aussi borner
    le temps écoulé (fourni par l'appelant pour rester testable sans horloge).
    """

    def __init__(self, max_attempts_without_progress: int = 3, max_seconds: int | None = None):
        if max_attempts_without_progress < 1:
            raise ValueError("max_attempts_without_progress doit être >= 1")
        self.max_attempts_without_progress = max_attempts_without_progress
        self.max_seconds = max_seconds
        self._attempts_without_progress = 0
        self._elapsed_seconds = 0

    def record(self, *, made_progress: bool, elapsed_seconds: int = 0) -> None:
        """Enregistre le résultat d'une tentative."""
        self._elapsed_seconds = elapsed_seconds
        if made_progress:
            self._attempts_without_progress = 0
        else:
            self._attempts_without_progress += 1

    def is_stagnating(self) -> bool:
        """True si on doit considérer la mission comme bloquée."""
        if self._attempts_without_progress >= self.max_attempts_without_progress:
            return True
        if self.max_seconds is not None and self._elapsed_seconds >= self.max_seconds:
            return True
        return False

    def reset(self) -> None:
        self._attempts_without_progress = 0
        self._elapsed_seconds = 0
