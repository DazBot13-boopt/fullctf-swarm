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
