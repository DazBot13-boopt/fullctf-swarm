"""Moteur Attack/Defense (A/D).

En A/D, les flags des adversaires TOURNENT à chaque round et expirent vite. Il faut
donc : collecter les flags volés par les exploits, les dédupliquer, et les soumettre
RAPIDEMENT via le bot de soumission — avant expiration.

Périmètre : uniquement le range fourni par l'organisateur (autorisé par définition).
Le transport de soumission est injecté (ADSubmitter) => testable sans réseau.
"""

from __future__ import annotations

from collections import deque
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field


class ADSubmitResult(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"  # faux / déjà soumis côté plateforme
    EXPIRED = "expired"  # flag périmé (round passé)
    ERROR = "error"


class ADSubmitter(Protocol):
    """Soumet un flag A/D à la plateforme et renvoie le verdict."""

    def submit(self, flag: str) -> ADSubmitResult: ...


class ADFlag(BaseModel):
    """Un flag volé à un service adverse."""

    value: str
    target_service: str = ""
    round: int = 0


class ADStats(BaseModel):
    submitted: int = 0
    accepted: int = 0
    rejected: int = 0
    expired: int = 0
    errors: int = 0
    duplicates_skipped: int = 0


class AttackDefenseBot:
    """Collecte et soumet les flags A/D, sans doublon, le plus vite possible."""

    def __init__(self, submitter: ADSubmitter) -> None:
        self._submitter = submitter
        self._queue: deque[ADFlag] = deque()
        self._seen: set[str] = set()
        self.stats = ADStats()

    def enqueue(self, flag: ADFlag) -> bool:
        """Ajoute un flag à soumettre. Ignore les doublons déjà vus.

        Retourne True si mis en file, False si doublon.
        """
        if flag.value in self._seen:
            self.stats.duplicates_skipped += 1
            return False
        self._seen.add(flag.value)
        self._queue.append(flag)
        return True

    def pending(self) -> int:
        return len(self._queue)

    def flush(self) -> ADStats:
        """Soumet tous les flags en file et met à jour les statistiques."""
        while self._queue:
            flag = self._queue.popleft()
            result = self._submitter.submit(flag.value)
            self.stats.submitted += 1
            if result == ADSubmitResult.ACCEPTED:
                self.stats.accepted += 1
            elif result == ADSubmitResult.REJECTED:
                self.stats.rejected += 1
            elif result == ADSubmitResult.EXPIRED:
                self.stats.expired += 1
            else:
                self.stats.errors += 1
        return self.stats
