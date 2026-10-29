"""Tests du Supervisor Chat / Mission Control (Sprint 9)."""

from fullctf.agents import MockAgentAdapter
from fullctf.evidence import EvidenceStore
from fullctf.models.evidence import Evidence, VerificationStatus
from fullctf.models.mission import AgentProvider, Mission, MissionStatus
from fullctf.supervisor import SupervisorService


def _mission(status=MissionStatus.RUNNING, provider=AgentProvider.CODEX, cid="c1"):
    return Mission(challenge_id=cid, agent_provider=provider, specialist_profile="web", status=status)


def test_snapshot_counts():
    store = EvidenceStore()
    svc = SupervisorService(store)
    missions = [
        _mission(MissionStatus.RUNNING),
        _mission(MissionStatus.COMPLETED),
        _mission(MissionStatus.FAILED),
    ]
    snap = svc.snapshot(missions)
    assert snap.total_missions == 3
    assert snap.active_missions == 1
    assert snap.completed_missions == 1
    assert snap.failed_missions == 1


def test_snapshot_evidence_counts():
    store = EvidenceStore()
    svc = SupervisorService(store)
    m = _mission()
    e1 = store.add(Evidence(challenge_id="c1", mission_id=m.id, source="codex", observation="a"))
    store.add(Evidence(challenge_id="c1", mission_id=m.id, source="codex", observation="b"))
    store.mark(e1.id, VerificationStatus.VERIFIED)

    snap = svc.snapshot([m])
    ms = snap.missions[0]
    assert ms.evidence_count == 2
    assert ms.verified_evidence_count == 1


def test_blocked_missions_flagged():
    store = EvidenceStore()
    svc = SupervisorService(store)
    m1 = _mission()
    m2 = _mission()
    snap = svc.snapshot([m1, m2], blocked_ids={m2.id})
    blocked = svc.blocked(snap)
    assert len(blocked) == 1
    assert blocked[0].mission_id == m2.id


def test_summarize_without_llm_returns_facts():
    store = EvidenceStore()
    svc = SupervisorService(store)
    snap = svc.snapshot([_mission()])
    out = svc.summarize(snap, "où en est-on ?", adapter=None)
    assert "Missions:" in out


def test_summarize_with_llm_uses_agent():
    store = EvidenceStore()
    svc = SupervisorService(store)
    snap = svc.snapshot([_mission()])
    agent = MockAgentAdapter(AgentProvider.CLAUDE, response="Tout avance bien, 1 mission active.")
    out = svc.summarize(snap, "résume", adapter=agent)
    assert out == "Tout avance bien, 1 mission active."
    # Le LLM a bien reçu les faits dans son prompt.
    assert "Missions:" in agent.calls[0]


def test_summarize_falls_back_on_llm_failure():
    store = EvidenceStore()
    svc = SupervisorService(store)
    snap = svc.snapshot([_mission()])
    agent = MockAgentAdapter(AgentProvider.CLAUDE, succeed=False)
    out = svc.summarize(snap, "résume", adapter=agent)
    # Repli sur les faits bruts.
    assert "Missions:" in out
