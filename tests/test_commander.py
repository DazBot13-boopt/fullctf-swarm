"""Tests du Commander : classification, allocation, escalade, garde-fous (Sprint 4)."""

import pytest

from fullctf.agents import AgentRegistry, MockAgentAdapter
from fullctf.commander import (
    Commander,
    StagnationDetector,
    SwarmMode,
    infer_category,
    initial_mode,
    next_mode,
)
from fullctf.models.challenge import Category, Challenge, Difficulty
from fullctf.models.mission import AgentProvider, MissionStatus


# --- Classification ---

def test_infer_category_keeps_known():
    c = Challenge(title="x", category=Category.PWN)
    assert infer_category(c) == Category.PWN


def test_infer_category_from_keywords():
    c = Challenge(title="Baby RSA", description="recover the private key and decrypt")
    assert infer_category(c) == Category.CRYPTO


def test_infer_category_from_extension():
    c = Challenge(title="mystery", attachments=["dump.pcap"])
    assert infer_category(c) == Category.FORENSIC


def test_infer_category_defaults_to_misc():
    c = Challenge(title="???", description="no hints at all")
    assert infer_category(c) == Category.MISC


# --- Allocation ---

def test_initial_mode_easy_is_single():
    assert initial_mode(Difficulty.EASY, 3) == SwarmMode.SINGLE


def test_initial_mode_hard_is_parallel():
    assert initial_mode(Difficulty.HARD, 3) == SwarmMode.PARALLEL_INDEPENDENT


def test_initial_mode_insane_is_collaborative():
    assert initial_mode(Difficulty.INSANE, 3) == SwarmMode.COLLABORATIVE


def test_one_agent_always_single():
    assert initial_mode(Difficulty.INSANE, 1) == SwarmMode.SINGLE


def test_next_mode_escalation():
    assert next_mode(SwarmMode.SINGLE, 3) == SwarmMode.PARALLEL_INDEPENDENT
    assert next_mode(SwarmMode.DEBATE, 3) is None


def test_no_escalation_with_single_agent():
    assert next_mode(SwarmMode.SINGLE, 1) is None


# --- Commander ---

def _registry(n: int) -> AgentRegistry:
    reg = AgentRegistry()
    providers = [AgentProvider.CODEX, AgentProvider.CLAUDE, AgentProvider.CURSOR]
    for p in providers[:n]:
        reg.register(MockAgentAdapter(p))
    return reg


def test_commander_plan_easy_single():
    cmd = Commander(_registry(3))
    c = Challenge(title="warmup", category=Category.WEB, difficulty=Difficulty.EASY)
    plan = cmd.plan(c)
    assert plan.mode == SwarmMode.SINGLE
    assert plan.agent_count == 1
    assert len(plan.missions) == 1
    assert plan.missions[0].specialist_profile == "web"


def test_commander_plan_insane_collaborative():
    cmd = Commander(_registry(3))
    c = Challenge(title="hardcore", category=Category.PWN, difficulty=Difficulty.INSANE)
    plan = cmd.plan(c)
    assert plan.mode == SwarmMode.COLLABORATIVE
    assert plan.agent_count == 3
    assert len(plan.missions) == 3


def test_commander_plan_fails_without_agents():
    cmd = Commander(_registry(0))
    with pytest.raises(RuntimeError):
        cmd.plan(Challenge(title="x"))


def test_commander_escalation_flow():
    cmd = Commander(_registry(3))
    detector = StagnationDetector(max_attempts_without_progress=2)

    detector.record(made_progress=False)
    assert cmd.should_escalate(detector) is False
    detector.record(made_progress=False)
    assert cmd.should_escalate(detector) is True

    assert cmd.escalate(SwarmMode.SINGLE) == SwarmMode.PARALLEL_INDEPENDENT


def test_commander_transition_guardrail():
    cmd = Commander(_registry(1))
    c = Challenge(title="x", difficulty=Difficulty.EASY)
    mission = cmd.plan(c).missions[0]

    # Transition valide.
    cmd.transition(mission, MissionStatus.VALIDATED)
    assert mission.status == MissionStatus.VALIDATED

    # Transition interdite (saut d'étape) -> bloquée par le garde-fou.
    with pytest.raises(ValueError):
        cmd.transition(mission, MissionStatus.COMPLETED)


def test_stagnation_resets_on_progress():
    d = StagnationDetector(max_attempts_without_progress=2)
    d.record(made_progress=False)
    d.record(made_progress=True)  # reset
    d.record(made_progress=False)
    assert d.is_stagnating() is False
