"""Transport HTTP réel pour CTFd (httpx), implémentant l'interface HttpClient.

Gère les deux modes d'auth d'une instance CTFd :
- **Token API** : header `Authorization: Token <...>` (suffit souvent pour /challenges).
- **Session (login)** : certaines instances exigent une session cookie pour les
  DÉTAILS d'un challenge et les téléchargements. `login()` récupère le nonce CSRF
  et poste les identifiants ; les cookies persistent dans le client httpx.

Le token/mot de passe ne sont jamais loggés. On ne cible que des plateformes
explicitement autorisées.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx

from .client import HttpResponse

_NONCE_RE = re.compile(r"name=['\"]nonce['\"]\s+value=['\"]([a-f0-9]{16,})", re.I)
_NONCE_RE2 = re.compile(r"csrfNonce[\"'\s:=]+([a-f0-9]{16,})", re.I)


class HttpxClient:
    """Client HTTP réel basé sur httpx.Client (cookies persistants)."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        verify_tls: bool = True,
        timeout: float = 30.0,
        user_agent: str = "FullCTF-Swarm/1.0",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._client = httpx.Client(
            follow_redirects=True,
            verify=verify_tls,
            timeout=timeout,
            headers={"User-Agent": user_agent},
        )

    # --- interface HttpClient (get/post -> HttpResponse) ---
    def get(self, url: str, headers: dict) -> HttpResponse:
        r = self._client.get(url, headers=headers)
        return HttpResponse(status_code=r.status_code, json_body=_safe_json(r))

    def post(self, url: str, headers: dict, json: dict) -> HttpResponse:
        r = self._client.post(url, headers=headers, json=json)
        return HttpResponse(status_code=r.status_code, json_body=_safe_json(r))

    # --- auth session (login formulaire CTFd) ---
    def login(self, username: str, password: str) -> bool:
        """Authentifie via le formulaire /login (session cookie). True si OK."""
        page = self._client.get(f"{self.base_url}/login")
        nonce = _extract_nonce(page.text)
        if not nonce:
            return False
        self._client.post(
            f"{self.base_url}/login",
            data={"name": username, "password": password, "nonce": nonce},
        )
        # Vérifie l'accès authentifié (l'API challenges ne doit plus rediriger).
        check = self._client.get(
            f"{self.base_url}/api/v1/challenges",
            headers=self._auth_header(),
        )
        return check.status_code == 200

    def _auth_header(self) -> dict:
        if self._token:
            return {"Authorization": f"Token {self._token}"}
        return {}

    # --- téléchargement de fichiers (bytes bruts) ---
    def download(self, url: str, dest: str | Path) -> int:
        """Télécharge une pièce jointe vers `dest`. Retourne la taille en octets."""
        if url.startswith("/"):
            url = f"{self.base_url}{url}"
        r = self._client.get(url, headers=self._auth_header())
        r.raise_for_status()
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return len(r.content)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "HttpxClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def _extract_nonce(html: str) -> str | None:
    m = _NONCE_RE.search(html or "") or _NONCE_RE2.search(html or "")
    return m.group(1) if m else None


def _safe_json(r: httpx.Response) -> dict:
    try:
        body = r.json()
        return body if isinstance(body, dict) else {"data": body}
    except Exception:
        return {}
