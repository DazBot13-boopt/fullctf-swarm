"""Tests du pipeline réel (adaptateur conteneur + orchestration + escalade).

Aucun Docker, aucun vrai agent : l'exécution est injectée via `exec_run`, et
l'auth hôte est simulée (home temporaire). On valide le CÂBLAGE conforme à la spec.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fullctf.agents import container_adapter as ca
from fullctf.agents.container_adapter import ContainerAgentAdapter
from fullctf.models.challenge import Category, Challenge, Difficulty
from fullctf.models.mission import AgentProvider
from fullctf.models.policies import AutonomyPolicy, ExecutionMode
from fullctf.runner.real_mission import solve_challenge


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Home temporaire avec les 3 fichiers d'auth (simulés)."""
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "auth.json").write_text("{}")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / ".credentials.json").write_text("{}")
    (tmp_path / ".config" / "cursor").mkdir(parents=True)
    (tmp_path / ".config" / "cursor" / "auth.json").write_text("{}")
    monkeypatch.setattr(ca, "_home", lambda: tmp_path)
    return tmp_path


def _provider_of(argv: list[str]) -> str:
    if "cursor-agent" in argv:
        return "cursor"
    if "claude" in argv:
        return "claude"
    if "codex" in argv:
        return "codex"
    return "?"


# --- adaptateur : construction prompt + commande --------------------------------

def test_adapter_builds_prompt_and_argv(fake_home, tmp_path):
    files = tmp_path / "chall" / "files"
    files.mkdir(parents=True)
    captured = {}

    def fake_exec(argv, timeout):
        captured["argv"] = argv
        return (0, "FLAG: CTF{aaaa1111bbbb2222}")

    ad = ContainerAgentAdapter(
        AgentProvider.CODEX, challenge_files_dir=files,
        target="10.0.0.5:3001", description="ignore this please",
        mode=ExecutionMode.CONNECTED, exec_run=fake_exec,
    )
    res = ad.run_mission("Trouve le flag.", "/ws", 60)
    assert res.success
    argv = captured["argv"]
    # conteneur jetable + garde-fous
    assert argv[:3] == ["docker", "run", "--rm"]
    assert "IS_SANDBOX=1" in argv
    assert "--cap-add=NET_RAW" in argv
    # modèle terra pour codex, cible dans le prompt, énoncé encadré (anti-injection)
    assert "gpt-5.6-terra" in argv
    prompt = argv[-1]
    assert "10.0.0.5:3001" in prompt
    assert "DONNEES_NON_FIABLES" in prompt  # wrap_untrusted
    assert "ignore this please" in prompt
    # fichiers montés en lecture seule
    assert any(a.endswith(":/work/files:ro") for a in argv)


def test_adapter_detects_refusal(fake_home, tmp_path):
    files = tmp_path / "files"; files.mkdir()

    def refuse(argv, timeout):
        return (0, "Je ne peux pas t'aider sur ce challenge CTF.")

    ad = ContainerAgentAdapter(AgentProvider.CURSOR, challenge_files_dir=files, exec_run=refuse)
    res = ad.run_mission("x", "/ws", 60)
    assert not res.success
    assert "refus" in (res.error or "")


# --- orchestration : escalade séquentielle --------------------------------------

def _challenge():
    return Challenge(
        title="TicketVault", category=Category.WEB, difficulty=Difficulty.EASY,
        description="portail de tickets", authorization_scope="lab",
    )


def test_single_agent_solves_first_no_escalation(fake_home, tmp_path):
    files = tmp_path / "files"; files.mkdir()
    calls = []

    def exec_run(argv, timeout):
        calls.append(_provider_of(argv))
        return (0, "FLAG: CTF{deadc0de12345678}")

    res = solve_challenge(
        _challenge(), files_dir=files, data_root=tmp_path / "data",
        target="t:1", exec_run=exec_run,
    )
    assert res.solved
    assert res.winning_agent == AgentProvider.CLAUDE  # 1er de l'ordre par défaut
    assert calls == ["claude"]  # un seul agent lancé (pas d'escalade)
    assert res.mode == "single"
    assert res.flag_value == "CTF{deadc0de12345678}"


def test_escalates_when_first_refuses(fake_home, tmp_path):
    files = tmp_path / "files"; files.mkdir()
    calls = []

    def exec_run(argv, timeout):
        prov = _provider_of(argv)
        calls.append(prov)
        if prov == "claude":
            return (0, "I can't help with that.")  # refus -> escalade
        return (0, "1. FLAG: CTF{a1428a3ae5db7d74}")  # codex résout

    res = solve_challenge(
        _challenge(), files_dir=files, data_root=tmp_path / "data",
        target="t:1", exec_run=exec_run,
    )
    assert res.solved
    assert res.winning_agent == AgentProvider.CODEX
    assert calls == ["claude", "codex"]  # escalade claude -> codex
    assert len(res.attempts) == 2


def test_decoy_flag_is_not_accepted(fake_home, tmp_path):
    files = tmp_path / "files"; files.mkdir()

    # Tous les agents ne renvoient qu'un flag-leurre d'injection.
    def exec_run(argv, timeout):
        return (0, "found CTF{ignore_all_previous_instructions}")

    res = solve_challenge(
        _challenge(), files_dir=files, data_root=tmp_path / "data",
        target="t:1", exec_run=exec_run,
    )
    assert not res.solved          # un leurre n'est jamais retenu
    assert res.decoys_detected >= 1
    assert res.flag_value is None


def test_real_flag_wins_over_decoy(fake_home, tmp_path):
    files = tmp_path / "files"; files.mkdir()

    def exec_run(argv, timeout):
        return (0, "decoy CTF{ignore_all_previous} and real CTF{a1428a3ae5db7d74}")

    res = solve_challenge(
        _challenge(), files_dir=files, data_root=tmp_path / "data",
        target="t:1", exec_run=exec_run,
    )
    assert res.solved
    assert res.flag_value == "CTF{a1428a3ae5db7d74}"
    assert res.decoys_detected >= 1
