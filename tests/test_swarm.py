"""Tests collaboration + débat (Sprint 7)."""

from fullctf.agents import AgentRegistry, MockAgentAdapter
from fullctf.evidence import EvidenceStore
from fullctf.models.evidence import VerificationStatus
from fullctf.models.mission import AgentProvider
from fullctf.swarm import AgentTask, CollaborationEngine, DebateEngine


def _registry(responses: dict[AgentProvider, str] | None = None) -> AgentRegistry:
    reg = AgentRegistry()
    responses = responses or {}
    for p in (AgentProvider.CODEX, AgentProvider.CLAUDE, AgentProvider.CURSOR):
        reg.register(MockAgentAdapter(p, response=responses.get(p, "ok")))
    return reg


# --- Collaboration ---

def test_collaboration_creates_shared_evidence():
    store = EvidenceStore()
    engine = CollaborationEngine(_registry(), store)
    tasks = [
        AgentTask(AgentProvider.CODEX, "web", "fuzz endpoints", "m1"),
        AgentTask(AgentProvider.CLAUDE, "web", "test auth", "m2"),
    ]
    created = engine.run_round("c1", tasks, workspace="/tmp", timeout=10)
    assert len(created) == 2
    assert len(store.for_challenge("c1")) == 2
    assert {e.source for e in created} == {"codex/web", "claude/web"}


def test_collaboration_shared_context_only_verified():
    store = EvidenceStore()
    engine = CollaborationEngine(_registry(), store)
    tasks = [AgentTask(AgentProvider.CODEX, "pwn", "find offset", "m1")]
    created = engine.run_round("c1", tasks, "/tmp", 10)
    # Rien de vérifié au départ.
    assert engine.shared_context("c1") == []
    # Après vérification, la preuve devient partageable.
    store.mark(created[0].id, VerificationStatus.VERIFIED)
    assert len(engine.shared_context("c1")) == 1


# --- Débat ---

def test_debate_consensus_agree():
    reg = _registry({
        AgentProvider.CLAUDE: "AGREE, la solution est correcte",
        AgentProvider.CURSOR: "AGREE, confirmé",
    })
    engine = DebateEngine(reg)
    outcome = engine.review(
        "flag = FLAG{x}", [AgentProvider.CLAUDE, AgentProvider.CURSOR], "/tmp", 10
    )
    assert outcome.agree_count == 2
    assert outcome.consensus is True


def test_debate_disagreement_blocks_consensus():
    reg = _registry({
        AgentProvider.CLAUDE: "DISAGREE, l'exploit ne tient pas",
        AgentProvider.CURSOR: "AGREE",
    })
    engine = DebateEngine(reg)
    outcome = engine.review("proposition", [AgentProvider.CLAUDE, AgentProvider.CURSOR], "/tmp", 10)
    assert outcome.agree_count == 1
    assert outcome.disagree_count == 1
    assert outcome.consensus is False  # pas de majorité stricte


def test_debate_ambiguous_defaults_to_no_agreement():
    reg = _registry({AgentProvider.CLAUDE: "hmm je ne suis pas sûr"})
    engine = DebateEngine(reg)
    outcome = engine.review("x", [AgentProvider.CLAUDE], "/tmp", 10)
    assert outcome.agree_count == 0
    assert outcome.consensus is False


def test_debate_self_review_single_agent():
    # Un seul réviseur (auto-révision) qui valide.
    reg = _registry({AgentProvider.CODEX: "AGREE after re-checking my own work"})
    engine = DebateEngine(reg)
    outcome = engine.review("ma solution", [AgentProvider.CODEX], "/tmp", 10)
    assert outcome.consensus is True
