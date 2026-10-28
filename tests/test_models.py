"""Tests des modèles de données et des machines à états."""

from fullctf.models import (
    AutonomyPolicy,
    Challenge,
    Difficulty,
    ExecutionMode,
    FlagStatus,
    Mission,
    MissionStatus,
    ToolAccessPolicy,
    can_flag_transition,
    can_transition,
)
from fullctf.models.mission import AgentProvider


def test_challenge_defaults():
    c = Challenge(title="Baby Web")
    assert c.id
    assert c.difficulty == Difficulty.UNKNOWN
    assert c.attachments == []


def test_mission_has_default_policies():
    m = Mission(challenge_id="abc", agent_provider=AgentProvider.CODEX)
    # Par défaut : prudent (pas de soumission auto, demande l'humain, local only).
    assert m.autonomy_policy.auto_submit_flag is False
    assert m.autonomy_policy.human_checkpoints is True
    assert m.autonomy_policy.mode == ExecutionMode.LOCAL_ONLY
    # Par défaut : liberté d'installer dans un conteneur.
    assert m.tool_access_policy.can_install is True


def test_autonomy_policy_full_autonomy():
    p = AutonomyPolicy(
        auto_submit_flag=True,
        human_checkpoints=False,
        mode=ExecutionMode.CONNECTED,
    )
    assert p.auto_submit_flag is True
    assert p.mode == ExecutionMode.CONNECTED


def test_tool_access_policy_defaults():
    p = ToolAccessPolicy()
    assert p.base_image == "fullctf-arsenal:latest"
    assert p.persist_installs is True


def test_mission_transitions_allowed():
    assert can_transition(MissionStatus.CREATED, MissionStatus.VALIDATED)
    assert can_transition(MissionStatus.RUNNING, MissionStatus.COMPLETED)
    assert can_transition(MissionStatus.RUNNING, MissionStatus.PAUSED)


def test_mission_transitions_forbidden():
    # On ne peut pas sauter de CREATED directement à RUNNING.
    assert not can_transition(MissionStatus.CREATED, MissionStatus.RUNNING)
    # Un état terminal ne mène nulle part.
    assert not can_transition(MissionStatus.COMPLETED, MissionStatus.RUNNING)


def test_flag_transitions():
    assert can_flag_transition(FlagStatus.CANDIDATE, FlagStatus.FORMAT_VALID)
    assert can_flag_transition(FlagStatus.REPRODUCED, FlagStatus.ACCEPTED)
    # Un flag local ne peut pas être "accepted" directement.
    assert not can_flag_transition(FlagStatus.CANDIDATE, FlagStatus.ACCEPTED)
