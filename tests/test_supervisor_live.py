"""Tests de la supervision live (Mission Control) branchée au work-stealing."""

from __future__ import annotations

import pytest

from fullctf.agents import container_adapter as ca
from fullctf.ctfd.client import HttpResponse
from fullctf.ctfd.connector import CTFdConnector
from fullctf.ctfd.workstealing import solve_ctf_workstealing
from fullctf.models.challenge import Difficulty
from fullctf.supervisor.mission_control import MissionControl


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    for p in (".codex/auth.json", ".claude/.credentials.json", ".config/cursor/auth.json"):
        f = tmp_path / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("{}")
    monkeypatch.setattr(ca, "_home", lambda: tmp_path)
    return tmp_path


class _Http:
    def __init__(self, n):
        self.n = n
        self.submitted = []

    def get(self, url, headers):
        if url.endswith("/api/v1/challenges"):
            return HttpResponse(status_code=200, json_body={"data": [
                {"id": i, "name": f"C{i}", "category": "web", "value": 10,
                 "solved_by_me": False, "solves": 5} for i in range(1, self.n + 1)
            ]})
        for i in range(1, self.n + 1):
            if url.endswith(f"/api/v1/challenges/{i}"):
                return HttpResponse(status_code=200, json_body={"data": {
                    "id": i, "name": f"C{i}", "category": "web", "value": 10,
                    "solved_by_me": False, "description": "x",
                    "connection_info": f"t:{i}", "files": [],
                }})
        return HttpResponse(status_code=404, json_body={})

    def post(self, url, headers, json):
        self.submitted.append(json)
        return HttpResponse(status_code=200, json_body={"data": {"status": "correct"}})


def test_mission_control_roundtrip(tmp_path):
    mc = MissionControl(tmp_path)
    mc.publish({"solved": 1, "total": 2, "challenges": []})
    assert mc.read_status()["solved"] == 1
    mc.set_order(paused=True); assert mc.paused() is True
    mc.set_order(paused=False); assert mc.paused() is False
    mc.add_force_debate(21); assert 21 in mc.force_debate_ids()
    mc.clear_force_debate(21); assert 21 not in mc.force_debate_ids()
    mc.set_order(stopped=True); assert mc.stopped() is True


def test_stop_order_halts_run(fake_home, tmp_path):
    http = _Http(2)
    connector = CTFdConnector("https://x", token="t", http=http)
    mc = MissionControl(tmp_path / "ctl")
    mc.set_order(stopped=True)  # STOP avant même de démarrer
    calls = {"n": 0}

    def exec_run(argv, timeout):
        calls["n"] += 1
        return (0, "rien")

    s = solve_ctf_workstealing(connector, data_root=tmp_path / "d",
                               difficulty=Difficulty.EASY, control=mc, exec_run=exec_run)
    assert calls["n"] == 0        # aucun agent n'a travaillé (stop respecté)
    assert s.solved == 0


def test_status_is_published(fake_home, tmp_path):
    http = _Http(1)
    connector = CTFdConnector("https://x", token="t", http=http)
    mc = MissionControl(tmp_path / "ctl")

    def exec_run(argv, timeout):
        return (0, "FLAG: CTF{published_ok120}")

    solve_ctf_workstealing(connector, data_root=tmp_path / "d",
                           difficulty=Difficulty.EASY, control=mc, auto_submit=True,
                           exec_run=exec_run)
    st = mc.read_status()
    assert st["total"] == 1 and st["solved"] == 1
    assert st["challenges"][0]["status"] == "résolu"
    assert st["challenges"][0]["flag"] == "CTF{published_ok120}"


def test_supervisor_can_force_debate(fake_home, tmp_path):
    """Le superviseur force un débat (même si debate=off) -> il se déclenche."""
    http = _Http(1)
    connector = CTFdConnector("https://x", token="t", http=http)
    mc = MissionControl(tmp_path / "ctl")
    mc.add_force_debate(1)  # ordre humain : débat sur le challenge id=1
    seen = {"debate": False}

    def exec_run(argv, timeout):
        p = argv[-1]
        if "CONCLUSION DU DÉBAT" in p:
            return (0, "FLAG: CTF{after_forced_deb0}")
        if "DÉBAT D'ÉQUIPE" in p:
            seen["debate"] = True
            return (0, "je propose l'approche X")
        return (0, "rien trouvé")  # essais normaux échouent

    s = solve_ctf_workstealing(connector, data_root=tmp_path / "d",
                               difficulty=Difficulty.EASY, control=mc, debate=False,
                               auto_submit=True, exec_run=exec_run)
    assert seen["debate"] is True     # débat forcé par le superviseur
    assert s.solved == 1
