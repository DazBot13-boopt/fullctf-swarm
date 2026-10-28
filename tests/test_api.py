"""Tests de l'API minimale (Sprint 1)."""

from fastapi.testclient import TestClient

from fullctf.api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_and_get_challenge():
    payload = {
        "title": "Baby RSA",
        "category": "crypto",
        "difficulty": "easy",
        "authorization_scope": "local-training",
    }
    r = client.post("/challenges", json=payload)
    assert r.status_code == 201
    created = r.json()
    assert created["title"] == "Baby RSA"
    assert created["category"] == "crypto"
    assert created["id"]

    # On peut le relire.
    r2 = client.get(f"/challenges/{created['id']}")
    assert r2.status_code == 200
    assert r2.json()["title"] == "Baby RSA"


def test_get_unknown_challenge_returns_404():
    r = client.get("/challenges/does-not-exist")
    assert r.status_code == 404


def test_list_challenges():
    r = client.get("/challenges")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
