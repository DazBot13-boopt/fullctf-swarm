"""Tests de la persistance (SQLite store + repositories)."""

from fullctf.models.challenge import Category, Challenge, Difficulty
from fullctf.models.evidence import Evidence
from fullctf.models.mission import AgentProvider, Mission
from fullctf.persistence import (
    ChallengeRepository,
    EvidenceRepository,
    MissionRepository,
    SqliteDocStore,
)


# --- Doc store ---

def test_store_put_get():
    store = SqliteDocStore(":memory:")
    store.put("col", "1", {"a": 1})
    assert store.get("col", "1") == {"a": 1}


def test_store_upsert():
    store = SqliteDocStore(":memory:")
    store.put("col", "1", {"a": 1})
    store.put("col", "1", {"a": 2})  # écrase
    assert store.get("col", "1") == {"a": 2}
    assert len(store.list("col")) == 1


def test_store_list_and_delete():
    store = SqliteDocStore(":memory:")
    store.put("col", "1", {"x": 1})
    store.put("col", "2", {"x": 2})
    assert len(store.list("col")) == 2
    store.delete("col", "1")
    assert store.get("col", "1") is None
    assert len(store.list("col")) == 1


def test_store_missing_returns_none():
    store = SqliteDocStore(":memory:")
    assert store.get("col", "nope") is None


def test_store_persists_to_file(tmp_path):
    db = str(tmp_path / "t.db")
    store = SqliteDocStore(db)
    store.put("col", "1", {"keep": True})
    store.close()

    # Réouverture : la donnée est toujours là.
    store2 = SqliteDocStore(db)
    assert store2.get("col", "1") == {"keep": True}
    store2.close()


# --- Challenge repository ---

def test_challenge_repo_roundtrip():
    repo = ChallengeRepository(SqliteDocStore(":memory:"))
    c = Challenge(title="Baby RSA", category=Category.CRYPTO, difficulty=Difficulty.EASY)
    repo.save(c)

    loaded = repo.get(c.id)
    assert loaded is not None
    assert loaded.title == "Baby RSA"
    assert loaded.category == Category.CRYPTO  # enum reconstruit
    assert loaded.created_at == c.created_at  # datetime préservé


def test_challenge_repo_list():
    repo = ChallengeRepository(SqliteDocStore(":memory:"))
    repo.save(Challenge(title="a"))
    repo.save(Challenge(title="b"))
    assert len(repo.list()) == 2


# --- Mission repository ---

def test_mission_repo_roundtrip_with_policies():
    repo = MissionRepository(SqliteDocStore(":memory:"))
    m = Mission(challenge_id="c1", agent_provider=AgentProvider.CODEX)
    repo.save(m)

    loaded = repo.get(m.id)
    assert loaded is not None
    assert loaded.agent_provider == AgentProvider.CODEX
    # Les policies imbriquées survivent au round-trip.
    assert loaded.autonomy_policy.auto_submit_flag is False
    assert loaded.tool_access_policy.base_image == "fullctf-arsenal:latest"


def test_mission_repo_for_challenge():
    repo = MissionRepository(SqliteDocStore(":memory:"))
    repo.save(Mission(challenge_id="c1", agent_provider=AgentProvider.CODEX))
    repo.save(Mission(challenge_id="c2", agent_provider=AgentProvider.CLAUDE))
    assert len(repo.for_challenge("c1")) == 1


# --- Evidence repository ---

def test_evidence_repo():
    repo = EvidenceRepository(SqliteDocStore(":memory:"))
    e = Evidence(challenge_id="c1", mission_id="m1", source="codex", observation="obs")
    repo.save(e)
    assert repo.get(e.id).observation == "obs"
    assert len(repo.for_challenge("c1")) == 1
