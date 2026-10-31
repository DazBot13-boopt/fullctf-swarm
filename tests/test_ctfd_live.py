"""Tests du CTFd live : transport httpx (MockTransport) + orchestration solve_ctf."""

from __future__ import annotations

import httpx
import pytest

from fullctf.agents import container_adapter as ca
from fullctf.ctfd.client import HttpResponse
from fullctf.ctfd.connector import CTFdConnector, map_category, solve_ctf
from fullctf.ctfd.http import HttpxClient
from fullctf.models.challenge import Category, Difficulty


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "auth.json").write_text("{}")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / ".credentials.json").write_text("{}")
    (tmp_path / ".config" / "cursor").mkdir(parents=True)
    (tmp_path / ".config" / "cursor" / "auth.json").write_text("{}")
    monkeypatch.setattr(ca, "_home", lambda: tmp_path)
    return tmp_path


# --- transport httpx réel, mocké (login + get + download) -----------------------

def test_httpx_login_and_download(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login" and request.method == "GET":
            return httpx.Response(200, text='<input name="nonce" value="abcdef0123456789abcdef">')
        if request.url.path == "/login" and request.method == "POST":
            return httpx.Response(302, headers={"location": "/challenges"})
        if request.url.path == "/api/v1/challenges":
            return httpx.Response(200, json={"success": True, "data": []})
        if request.url.path.startswith("/files/"):
            return httpx.Response(200, content=b"FLAGDATA")
        return httpx.Response(404)

    client = HttpxClient("https://ctf.example")
    client._client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)

    assert client.login("user", "pass") is True
    size = client.download("/files/x/payload.bin", tmp_path / "files" / "payload.bin")
    assert size == 8
    assert (tmp_path / "files" / "payload.bin").read_bytes() == b"FLAGDATA"


def test_map_category():
    assert map_category("Web Exploitation") == Category.WEB
    assert map_category("reversing") == Category.REVERSE
    assert map_category("Cryptography") == Category.CRYPTO
    assert map_category("osint") == Category.UNKNOWN  # non supporté -> inconnu


# --- orchestration complète avec un transport factice -------------------------

class FakeHttp:
    """HttpClient factice routant sur l'URL (pas de réseau)."""

    def __init__(self):
        self.submitted = []

    def get(self, url, headers):
        if url.endswith("/api/v1/challenges"):
            return HttpResponse(status_code=200, json_body={"data": [
                {"id": 1, "name": "TicketVault", "category": "web", "value": 30,
                 "solved_by_me": False},
                {"id": 2, "name": "DéjàFait", "category": "crypto", "value": 50,
                 "solved_by_me": True},
            ]})
        if url.endswith("/api/v1/challenges/1"):
            return HttpResponse(status_code=200, json_body={"data": {
                "id": 1, "name": "TicketVault", "category": "web", "value": 30,
                "solved_by_me": False, "description": "portail de tickets",
                "connection_info": "10.0.0.9:3001", "files": [],
            }})
        return HttpResponse(status_code=404, json_body={})

    def post(self, url, headers, json):
        self.submitted.append(json)
        return HttpResponse(status_code=200, json_body={"data": {"status": "correct"}})


def test_solve_ctf_end_to_end(fake_home, tmp_path):
    http = FakeHttp()
    connector = CTFdConnector("https://ctf.example", token="tok", http=http)

    def exec_run(argv, timeout):
        return (0, "1. FLAG: CTF{a1428a3ae5db7d74}")

    summary = solve_ctf(
        connector, data_root=tmp_path / "data", difficulty=Difficulty.EASY,
        auto_submit=True, exec_run=exec_run,
    )
    # seul le non-résolu (id 1) est traité
    assert summary.total == 1
    assert summary.solved == 1
    assert summary.submitted_accepted == 1
    r = summary.results[0]
    assert r.name == "TicketVault"
    assert r.solve.flag_value == "CTF{a1428a3ae5db7d74}"
    assert r.submission is not None and r.submission.accepted
    # le flag soumis est bien le bon
    assert http.submitted[0]["submission"] == "CTF{a1428a3ae5db7d74}"
    assert http.submitted[0]["challenge_id"] == 1


def test_solve_ctf_no_autosubmit_proposes_only(fake_home, tmp_path):
    http = FakeHttp()
    connector = CTFdConnector("https://ctf.example", token="tok", http=http)

    summary = solve_ctf(
        connector, data_root=tmp_path / "data", difficulty=Difficulty.EASY,
        auto_submit=False, exec_run=lambda a, t: (0, "FLAG: CTF{proposed12345678}"),
    )
    assert summary.solved == 1
    assert summary.submitted_accepted == 0
    assert http.submitted == []  # rien soumis sans auto_submit
    assert summary.results[0].submission is None


class FakeHttpMulti:
    """3 challenges non résolus, détails + submit OK (pour tester le parallèle)."""

    def __init__(self):
        self.submitted = []
        self._lock_ok = True

    def get(self, url, headers):
        if url.endswith("/api/v1/challenges"):
            return HttpResponse(status_code=200, json_body={"data": [
                {"id": i, "name": f"C{i}", "category": "web", "value": 10 * i,
                 "solved_by_me": False} for i in (1, 2, 3)
            ]})
        for i in (1, 2, 3):
            if url.endswith(f"/api/v1/challenges/{i}"):
                return HttpResponse(status_code=200, json_body={"data": {
                    "id": i, "name": f"C{i}", "category": "web", "value": 10 * i,
                    "solved_by_me": False, "description": "x",
                    "connection_info": f"t:{i}", "files": [],
                }})
        return HttpResponse(status_code=404, json_body={})

    def post(self, url, headers, json):
        self.submitted.append(json)
        return HttpResponse(status_code=200, json_body={"data": {"status": "correct"}})


def test_solve_ctf_parallel(fake_home, tmp_path):
    from fullctf.ctfd.connector import solve_ctf_parallel
    http = FakeHttpMulti()
    connector = CTFdConnector("https://ctf.example", token="tok", http=http)

    def exec_run(argv, timeout):
        # chaque challenge renvoie un flag distinct (dérivé de la cible t:N)
        prompt = argv[-1]
        n = "1"
        for c in ("t:1", "t:2", "t:3"):
            if c in prompt:
                n = c[-1]
        return (0, f"FLAG: CTF{{solved{n}0000000}}")

    summary = solve_ctf_parallel(
        connector, data_root=tmp_path / "data", difficulty=Difficulty.EASY,
        auto_submit=True, exec_run=exec_run,
    )
    assert summary.total == 3
    assert summary.solved == 3                 # les 3 résolus en parallèle
    assert summary.submitted_accepted == 3      # les 3 soumis + acceptés
    assert len(http.submitted) == 3
    # chaque challenge a bien un agent gagnant parmi les agents dispo
    agents = {r.solve.winning_agent for r in summary.results}
    assert all(a is not None for a in agents)
