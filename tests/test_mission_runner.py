"""Tests du Mission Runner : cycle complet + application de l'autonomy_policy."""

import pytest

from fullctf.agents import AgentRegistry, MockAgentAdapter
from fullctf.challenges import LocalSolver
from fullctf.evidence import EvidenceStore
from fullctf.models.challenge import Challenge
from fullctf.models.mission import AgentProvider, Mission, MissionStatus
from fullctf.models.policies import AutonomyPolicy, ExecutionMode
from fullctf.runner import MissionRunner


@pytest.fixture
def challenge():
    return Challenge(title="demo")


def _runner(tmp_path, response, *, reproducer=None, submitter=None, approval=None):
    reg = AgentRegistry()
    reg.register(MockAgentAdapter(AgentProvider.CODEX, response=response))
    return MissionRunner(
        solver=LocalSolver(tmp_path / "data"),
        registry=reg,
        evidence_store=EvidenceStore(),
        reproducer=reproducer,
        submitter=submitter,
        approval_gate=approval,
    ), reg


def _mission(cid, **autonomy):
    return Mission(
        challenge_id=cid, agent_provider=AgentProvider.CODEX,
        specialist_profile="web",
        autonomy_policy=AutonomyPolicy(**autonomy) if autonomy else AutonomyPolicy(),
    )


class _Submitter:
    def __init__(self, accept=True):
        self.accept = accept
        self.calls = []

    def submit(self, challenge, flag_value):
        self.calls.append(flag_value)
        return self.accept


class _Gate:
    def __init__(self, approve):
        self.approve = approve
        self.asked = []

    def request(self, context):
        self.asked.append(context)
        return self.approve


def test_no_flag_completes(tmp_path, challenge):
    runner, _ = _runner(tmp_path, "je n'ai rien trouvé")
    out = runner.run(challenge, _mission(challenge.id))
    assert out.status == MissionStatus.COMPLETED
    assert out.flag is None
    assert out.notes == "aucun flag trouvé"


def test_agent_failure_marks_failed(tmp_path, challenge):
    reg = AgentRegistry()
    reg.register(MockAgentAdapter(AgentProvider.CODEX, succeed=False))
    runner = MissionRunner(LocalSolver(tmp_path / "d"), reg, EvidenceStore())
    out = runner.run(challenge, _mission(challenge.id))
    assert out.status == MissionStatus.FAILED
    assert len(out.evidences) == 1  # la preuve de l'échec est tracée


def test_flag_found_but_not_reproduced_is_proposed(tmp_path, challenge):
    # Pas de reproducteur -> flag reste format_valid, proposé (pas soumis).
    runner, _ = _runner(tmp_path, "le flag est FLAG{found_it}")
    out = runner.run(challenge, _mission(challenge.id, auto_submit_flag=True))
    assert out.flag.value == "FLAG{found_it}"
    assert out.submitted is False
    assert out.status == MissionStatus.COMPLETED
    assert "manuelle" in out.notes


def test_flag_shaped_token_is_format_valid(tmp_path, challenge):
    # Le format par défaut est permissif sur le CONTENU entre accolades
    # (espaces autorisés) : un jeton NOM{...} est donc extrait et format_valid.
    runner, _ = _runner(tmp_path, "trouvé : ctf{some content here}")
    out = runner.run(challenge, _mission(challenge.id))
    assert out.flag.value == "ctf{some content here}"
    assert out.flag.validation_status.value == "format_valid"


def test_auto_submit_accepted(tmp_path, challenge):
    submitter = _Submitter(accept=True)
    runner, _ = _runner(
        tmp_path, "FLAG{win}", reproducer=lambda f, ws: True, submitter=submitter
    )
    m = _mission(challenge.id, auto_submit_flag=True, human_checkpoints=False,
                 mode=ExecutionMode.CONNECTED)
    out = runner.run(challenge, m)
    assert out.submitted is True
    assert out.accepted is True
    assert out.flag.validation_status.value == "accepted"
    assert submitter.calls == ["FLAG{win}"]


def test_auto_submit_rejected_by_platform(tmp_path, challenge):
    submitter = _Submitter(accept=False)
    runner, _ = _runner(
        tmp_path, "FLAG{nope}", reproducer=lambda f, ws: True, submitter=submitter
    )
    m = _mission(challenge.id, auto_submit_flag=True, human_checkpoints=False)
    out = runner.run(challenge, m)
    assert out.submitted is True
    assert out.accepted is False
    assert out.flag.validation_status.value == "rejected"


def test_human_checkpoint_blocks_until_approval(tmp_path, challenge):
    submitter = _Submitter(accept=True)
    gate = _Gate(approve=False)  # l'humain n'approuve pas
    runner, _ = _runner(
        tmp_path, "FLAG{x}", reproducer=lambda f, ws: True,
        submitter=submitter, approval=gate,
    )
    m = _mission(challenge.id, auto_submit_flag=True, human_checkpoints=True)
    out = runner.run(challenge, m)
    assert out.needs_human_approval is True
    assert out.status == MissionStatus.WAITING_APPROVAL
    assert submitter.calls == []  # rien soumis sans approbation
    assert gate.asked  # l'approbation a bien été demandée


def test_human_checkpoint_approved_submits(tmp_path, challenge):
    submitter = _Submitter(accept=True)
    gate = _Gate(approve=True)
    runner, _ = _runner(
        tmp_path, "FLAG{ok}", reproducer=lambda f, ws: True,
        submitter=submitter, approval=gate,
    )
    m = _mission(challenge.id, auto_submit_flag=True, human_checkpoints=True)
    out = runner.run(challenge, m)
    assert out.submitted is True
    assert out.accepted is True


def test_reproduction_failure_not_submitted(tmp_path, challenge):
    submitter = _Submitter(accept=True)
    runner, _ = _runner(
        tmp_path, "FLAG{fake}", reproducer=lambda f, ws: False, submitter=submitter
    )
    m = _mission(challenge.id, auto_submit_flag=True, human_checkpoints=False)
    out = runner.run(challenge, m)
    assert out.submitted is False
    assert out.flag.validation_status.value == "rejected"
    assert "faux positif" in out.notes
