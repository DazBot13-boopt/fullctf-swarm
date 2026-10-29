"""Tests du câblage playbooks + outils dans le Commander (Sprint 12)."""

from fullctf.agents import AgentRegistry, MockAgentAdapter
from fullctf.commander import Commander
from fullctf.models.challenge import Category, Challenge, Difficulty
from fullctf.models.mission import AgentProvider
from fullctf.playbooks import build_default_playbook_registry
from fullctf.tools import build_default_registry


def _agents(n=1):
    reg = AgentRegistry()
    for p in [AgentProvider.CODEX, AgentProvider.CLAUDE, AgentProvider.CURSOR][:n]:
        reg.register(MockAgentAdapter(p))
    return reg


def test_commander_without_registries_leaves_defaults():
    cmd = Commander(_agents())
    c = Challenge(title="x", category=Category.WEB, difficulty=Difficulty.EASY)
    m = cmd.plan(c).missions[0]
    assert m.playbook_id is None
    assert m.allowed_tools == []


def test_commander_wires_playbook_and_tools():
    cmd = Commander(
        _agents(),
        playbook_registry=build_default_playbook_registry(),
        tool_registry=build_default_registry(),
    )
    c = Challenge(
        title="Baby RSA", category=Category.CRYPTO, difficulty=Difficulty.EASY,
        description="public key n = ... e = ...",
    )
    m = cmd.plan(c).missions[0]
    assert m.playbook_id == "crypto/rsa"
    # Les outils crypto sont branchés.
    assert "sagemath" in m.allowed_tools
    assert "rsactftool" in m.allowed_tools


def test_commander_wiring_infers_category_for_playbook():
    cmd = Commander(
        _agents(),
        playbook_registry=build_default_playbook_registry(),
        tool_registry=build_default_registry(),
    )
    # Catégorie inconnue mais indices forensic -> playbook forensic.
    c = Challenge(
        title="RAM capture", difficulty=Difficulty.HARD,
        description="analyze this volatility memory dump", attachments=["cap.raw"],
    )
    m = cmd.plan(c).missions[0]
    assert m.specialist_profile == "forensic"
    assert m.playbook_id in ("forensic/memory", "forensic/stego-image")
