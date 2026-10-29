"""Tests des nouveaux endpoints API (Sprint 9)."""

from fastapi.testclient import TestClient

from fullctf.api.main import app

client = TestClient(app)


def test_supervisor_snapshot_endpoint():
    r = client.get("/supervisor/snapshot")
    assert r.status_code == 200
    body = r.json()
    assert "total_missions" in body
    assert "missions" in body


def test_missions_endpoint():
    r = client.get("/missions")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_memory_search_endpoint_empty():
    r = client.get("/memory/search", params={"q": "nothing-will-match-xyz"})
    assert r.status_code == 200
    assert r.json() == []


def test_dashboard_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "FullCTF Swarm" in r.text
