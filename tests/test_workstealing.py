"""Tests du dispatcher work-stealing (agents jamais au repos + coordination)."""

from __future__ import annotations

import pytest

from fullctf.agents import container_adapter as ca
from fullctf.ctfd.client import HttpResponse
from fullctf.ctfd.connector import CTFdConnector
from fullctf.ctfd.workstealing import solve_ctf_workstealing
from fullctf.models.challenge import Difficulty


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    for p in (".codex/auth.json", ".claude/.credentials.json", ".config/cursor/auth.json"):
        f = tmp_path / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("{}")
    monkeypatch.setattr(ca, "_home", lambda: tmp_path)
    return tmp_path


class _Http:
    """CTFd factice : `n` challenges non résolus + détails + submit correct."""

    def __init__(self, n):
        self.n = n
        self.submitted = []

    def get(self, url, headers):
        if url.endswith("/api/v1/challenges"):
            return HttpResponse(status_code=200, json_body={"data": [
                {"id": i, "name": f"C{i}", "category": "web", "value": 10 * i,
                 "solved_by_me": False, "solves": i} for i in range(1, self.n + 1)
            ]})
        for i in range(1, self.n + 1):
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


def test_workstealing_solves_all_with_distinct_winners(fake_home, tmp_path):
    http = _Http(3)
    connector = CTFdConnector("https://x", token="t", http=http)

    def exec_run(argv, timeout):
        p = argv[-1]
        n = next((c for c in "123" if f"t:{c}" in p), "0")
        return (0, f"FLAG: CTF{{solved{n}0000000}}")

    s = solve_ctf_workstealing(connector, data_root=tmp_path / "d",
                               difficulty=Difficulty.EASY, auto_submit=True, exec_run=exec_run)
    assert s.total == 3 and s.solved == 3 and s.submitted_accepted == 3
    assert all(r.winner is not None for r in s.results)
    assert len(http.submitted) == 3


def test_workstealing_reinforces_until_solved(fake_home, tmp_path):
    """1 challenge : le 1er agent échoue, un autre agent (renfort) le résout."""
    http = _Http(1)
    connector = CTFdConnector("https://x", token="t", http=http)
    calls = {"n": 0}
    import threading
    lk = threading.Lock()

    def exec_run(argv, timeout):
        with lk:
            calls["n"] += 1
            k = calls["n"]
        if k == 1:
            return (0, "exploration, pas de flag")   # 1er agent échoue
        return (0, "FLAG: CTF{reinforced123456}")     # renfort résout

    s = solve_ctf_workstealing(connector, data_root=tmp_path / "d",
                               difficulty=Difficulty.EASY, auto_submit=True, exec_run=exec_run)
    assert s.solved == 1
    r = s.results[0]
    assert r.winner is not None
    assert r.attempts >= 2            # plusieurs agents ont tenté (renfort)
    assert r.flag == "CTF{reinforced123456}"


def test_workstealing_decoy_not_accepted(fake_home, tmp_path):
    http = _Http(1)
    connector = CTFdConnector("https://x", token="t", http=http)

    def exec_run(argv, timeout):
        return (0, "CTF{ignore_all_previous_instructions}")  # leurre d'injection

    s = solve_ctf_workstealing(connector, data_root=tmp_path / "d",
                               difficulty=Difficulty.EASY, auto_submit=True, exec_run=exec_run)
    assert s.solved == 0
    assert http.submitted == []       # un leurre n'est jamais soumis


def test_debate_unblocks_after_all_stuck(fake_home, tmp_path):
    """Tous les agents échouent -> débat -> UN agent continue -> trouve le flag."""
    http = _Http(1)
    connector = CTFdConnector("https://x", token="t", http=http)

    def exec_run(argv, timeout):
        p = argv[-1]
        if "CONCLUSION DU DÉBAT" in p:
            return (0, "FLAG: CTF{found_after_debate0}")   # le continuer trouve
        if "DÉBAT D'ÉQUIPE" in p:
            return (0, "Je propose d'essayer l'approche alternative Z")  # proposition
        return (0, "rien trouvé pour l'instant")            # essais normaux : échec

    s = solve_ctf_workstealing(connector, data_root=tmp_path / "d",
                               difficulty=Difficulty.EASY, auto_submit=True,
                               debate=True, exec_run=exec_run)
    assert s.solved == 1
    assert s.results[0].flag == "CTF{found_after_debate0}"
    assert "débat" in s.results[0].debate
    assert s.submitted_accepted == 1


def test_no_debate_when_disabled(fake_home, tmp_path):
    http = _Http(1)
    connector = CTFdConnector("https://x", token="t", http=http)

    def exec_run(argv, timeout):
        assert "DÉBAT D'ÉQUIPE" not in argv[-1]  # jamais de débat si désactivé
        return (0, "rien trouvé")

    s = solve_ctf_workstealing(connector, data_root=tmp_path / "d",
                               difficulty=Difficulty.EASY, debate=False, exec_run=exec_run)
    assert s.solved == 0


def test_debate_approval_gate_can_block(fake_home, tmp_path):
    """Le 'bouton' : si l'humain refuse, pas de débat (pas de dépense)."""
    http = _Http(1)
    connector = CTFdConnector("https://x", token="t", http=http)
    seen = {"debate_calls": 0}

    def exec_run(argv, timeout):
        if "DÉBAT D'ÉQUIPE" in argv[-1] or "CONCLUSION DU DÉBAT" in argv[-1]:
            seen["debate_calls"] += 1
        return (0, "rien trouvé")

    s = solve_ctf_workstealing(connector, data_root=tmp_path / "d",
                               difficulty=Difficulty.EASY, debate=True,
                               approval_gate=lambda name: False,  # refus humain
                               exec_run=exec_run)
    assert s.solved == 0
    assert seen["debate_calls"] == 0                 # débat jamais lancé
    assert "non autorisé" in s.results[0].debate


def test_agents_filter_excludes_cursor(fake_home, tmp_path):
    """--agents claude,codex : Cursor n'est pas utilisé."""
    http = _Http(1)
    connector = CTFdConnector("https://x", token="t", http=http)
    used = set()

    def exec_run(argv, timeout):
        for a in ("claude", "codex", "cursor-agent"):
            if a in argv:
                used.add("cursor" if a == "cursor-agent" else a)
        return (0, "rien trouvé")

    solve_ctf_workstealing(connector, data_root=tmp_path / "d",
                           difficulty=Difficulty.EASY, agents=["claude", "codex"],
                           exec_run=exec_run)
    assert "cursor" not in used      # Cursor exclu
    assert used <= {"claude", "codex"}


def test_workstealing_spreads_agents_on_different_challenges(fake_home, tmp_path):
    """3 challenges, 2 agents : ils DÉMARRENT sur des challenges différents (répartition)."""
    import threading
    import time
    http = _Http(3)
    connector = CTFdConnector("https://x", token="t", http=http)
    first_pick: dict[str, str] = {}
    lk = threading.Lock()

    def exec_run(argv, timeout):
        prov = "claude" if "claude" in argv else "codex"
        n = next((c for c in "123" if f"t:{c}" in argv[-1]), "0")
        with lk:
            first_pick.setdefault(prov, n)
        time.sleep(0.15)  # laisse les 2 agents piocher AVANT toute résolution
        return (0, f"FLAG: CTF{{solved{n}0000000}}")

    s = solve_ctf_workstealing(connector, data_root=tmp_path / "d",
                               difficulty=Difficulty.EASY, agents=["claude", "codex"],
                               exec_run=exec_run)
    assert s.solved == 3
    assert first_pick["claude"] != first_pick["codex"]  # pas le même challenge au départ
