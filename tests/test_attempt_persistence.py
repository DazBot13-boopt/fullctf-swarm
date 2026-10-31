"""Tests des briques de persistance d'essais : bump (insights), never-give-up, anti-boucle."""

from __future__ import annotations

import pytest

from fullctf.agents import container_adapter as ca
from fullctf.models.challenge import Category, Challenge, Difficulty
from fullctf.models.mission import AgentProvider
from fullctf.runner.persistence import (
    build_insights_block,
    no_progress,
    summarize_attempt,
)
from fullctf.runner.real_mission import solve_challenge


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "auth.json").write_text("{}")
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / ".credentials.json").write_text("{}")
    (tmp_path / ".config" / "cursor").mkdir(parents=True)
    (tmp_path / ".config" / "cursor" / "auth.json").write_text("{}")
    monkeypatch.setattr(ca, "_home", lambda: tmp_path)
    return tmp_path


def _chall():
    return Challenge(title="C", category=Category.WEB, difficulty=Difficulty.EASY)


# --- helpers ---------------------------------------------------------------

def test_summarize_tail():
    assert summarize_attempt("abc") == "abc"
    long = "x" * 5000
    s = summarize_attempt(long, max_chars=100)
    assert s.startswith("…") and len(s) == 101


def test_no_progress():
    assert no_progress("same output", "same output") is True
    assert no_progress("totally different aaaa", "zzzz nothing alike bbbb") is False
    assert no_progress("", "x") is False


def test_insights_block_wraps_untrusted():
    block = build_insights_block(["[claude essai 1] j'ai tenté X"])
    assert "DONNEES_NON_FIABLES" in block
    assert "j'ai tenté X" in block
    assert build_insights_block([]) == ""


# --- bump : les trouvailles passent à l'agent suivant ----------------------

def test_bump_passes_insights_to_next_agent(fake_home, tmp_path):
    files = tmp_path / "files"; files.mkdir()
    prompts = {}

    def exec_run(argv, timeout):
        prov = "claude" if "claude" in argv else ("codex" if "codex" in argv else "cursor")
        prompts[prov] = argv[-1]
        if prov == "claude":
            return (0, "J'AI TENTÉ l'injection SQL, sans succès.")  # pas de flag
        return (0, "FLAG: CTF{found_by_codex00}")  # codex résout

    res = solve_challenge(_chall(), files_dir=files, data_root=tmp_path / "d",
                          target="t:1", exec_run=exec_run)
    assert res.solved and res.winning_agent == AgentProvider.CODEX
    # le prompt de codex contient les trouvailles de claude (bump)
    assert "tentatives précédentes" in prompts["codex"]
    assert "injection SQL" in prompts["codex"]


# --- never give up : retries sur le même agent -----------------------------

def test_retries_same_provider_until_flag(fake_home, tmp_path):
    files = tmp_path / "files"; files.mkdir()
    calls = {"n": 0}

    def exec_run(argv, timeout):
        calls["n"] += 1
        if calls["n"] == 1:
            return (0, "exploration initiale du binaire")  # progresse, pas de flag
        return (0, "FLAG: CTF{second_try_000}")  # flag au 2e essai

    res = solve_challenge(_chall(), files_dir=files, data_root=tmp_path / "d",
                          target="t:1", provider_order=[AgentProvider.CLAUDE],
                          max_attempts_per_provider=3, exec_run=exec_run)
    assert res.solved
    assert calls["n"] == 2  # a réessayé, trouvé au 2e essai


# --- anti-boucle : on arrête un agent qui ne progresse plus ----------------

def test_anti_loop_stops_stuck_provider(fake_home, tmp_path):
    files = tmp_path / "files"; files.mkdir()
    calls = {"n": 0}

    def exec_run(argv, timeout):
        calls["n"] += 1
        return (0, "sortie identique à chaque fois")  # aucun progrès, jamais de flag

    res = solve_challenge(_chall(), files_dir=files, data_root=tmp_path / "d",
                          target="t:1", provider_order=[AgentProvider.CLAUDE],
                          max_attempts_per_provider=5, exec_run=exec_run)
    assert not res.solved
    assert calls["n"] == 2  # 1er essai + 1 retry identique -> stop (pas 5)
