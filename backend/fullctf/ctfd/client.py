"""Connecteur CTFd (Sprint 10).

Parle à l'API d'une plateforme CTFd AUTORISÉE : lister les challenges, lire les
métadonnées, télécharger les pièces jointes, et (optionnellement) soumettre un flag.

Règles :
- Soumission MANUELLE par défaut : submit_flag n'est appelé que si l'autonomie
  l'autorise (auto_submit_flag), décision prise par le Commander, pas ici.
- Le token n'est jamais loggé.
- On ne cible que des plateformes explicitement autorisées.

Le transport HTTP est injectable (HttpClient) pour rester testable sans réseau.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel


class HttpResponse(BaseModel):
    status_code: int
    json_body: dict


class HttpClient(Protocol):
    """Interface HTTP minimale (injectable, testable)."""

    def get(self, url: str, headers: dict) -> HttpResponse: ...
    def post(self, url: str, headers: dict, json: dict) -> HttpResponse: ...


class CTFdChallenge(BaseModel):
    """Challenge tel que renvoyé par CTFd."""

    id: int
    name: str
    category: str
    value: int
    solved: bool = False


class SubmissionResult(BaseModel):
    """Résultat d'une soumission de flag."""

    status: str  # "correct" / "incorrect" / "already_solved" / "error"
    message: str = ""

    @property
    def accepted(self) -> bool:
        return self.status == "correct"


class CTFdClient:
    """Client CTFd pour une instance autorisée."""

    def __init__(self, base_url: str, token: str, http: HttpClient) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._http = http

    def _headers(self) -> dict:
        # Token transmis mais jamais loggé par ce client.
        return {"Authorization": f"Token {self._token}", "Content-Type": "application/json"}

    def list_challenges(self) -> list[CTFdChallenge]:
        resp = self._http.get(f"{self.base_url}/api/v1/challenges", self._headers())
        if resp.status_code != 200:
            return []
        data = resp.json_body.get("data", [])
        return [
            CTFdChallenge(
                id=c["id"], name=c.get("name", ""), category=c.get("category", ""),
                value=c.get("value", 0), solved=c.get("solved_by_me", False),
            )
            for c in data
        ]

    def get_challenge(self, challenge_id: int) -> CTFdChallenge | None:
        resp = self._http.get(
            f"{self.base_url}/api/v1/challenges/{challenge_id}", self._headers()
        )
        if resp.status_code != 200:
            return None
        c = resp.json_body.get("data", {})
        if not c:
            return None
        return CTFdChallenge(
            id=c["id"], name=c.get("name", ""), category=c.get("category", ""),
            value=c.get("value", 0), solved=c.get("solved_by_me", False),
        )

    def submit_flag(self, challenge_id: int, flag: str) -> SubmissionResult:
        """Soumet un flag. À N'APPELER que si l'autonomie l'autorise (Commander)."""
        resp = self._http.post(
            f"{self.base_url}/api/v1/challenges/attempt",
            self._headers(),
            {"challenge_id": challenge_id, "submission": flag},
        )
        if resp.status_code not in (200, 201):
            return SubmissionResult(status="error", message=f"HTTP {resp.status_code}")
        data = resp.json_body.get("data", {})
        status = data.get("status", "error")
        return SubmissionResult(status=status, message=data.get("message", ""))
