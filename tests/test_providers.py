"""Sprint 0 — verrouille les commandes réelles des 3 CLI (non-interactif).

Les commandes ont été validées sur le VPS (codex/claude/cursor répondent "OK"
en mode non-interactif avec ces flags). Ce test empêche une régression silencieuse.
"""

from __future__ import annotations

from fullctf.agents.providers import (
    make_claude_adapter,
    make_codex_adapter,
    make_cursor_adapter,
)
from fullctf.models.mission import AgentProvider


def _cmd(adapter, prompt="PROMPT"):
    return adapter._build_run_command(prompt)


def test_codex_auto_vs_safe_and_model():
    assert _cmd(make_codex_adapter(auto=True)) == [
        "codex", "exec", "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox", "PROMPT",
    ]
    assert _cmd(make_codex_adapter(auto=False)) == [
        "codex", "exec", "--skip-git-repo-check", "-s", "read-only", "PROMPT",
    ]
    assert _cmd(make_codex_adapter(model="gpt-5", auto=False)) == [
        "codex", "exec", "--skip-git-repo-check", "-m", "gpt-5", "-s", "read-only", "PROMPT",
    ]
    assert make_codex_adapter().provider is AgentProvider.CODEX


def test_claude_auto_vs_safe_and_model():
    assert _cmd(make_claude_adapter(auto=True)) == [
        "claude", "-p", "--dangerously-skip-permissions", "PROMPT",
    ]
    assert _cmd(make_claude_adapter(auto=False)) == ["claude", "-p", "PROMPT"]
    assert _cmd(make_claude_adapter(model="sonnet", auto=False)) == [
        "claude", "-p", "--model", "sonnet", "PROMPT",
    ]
    assert make_claude_adapter().provider is AgentProvider.CLAUDE


def test_cursor_auto_vs_safe_and_model():
    assert _cmd(make_cursor_adapter(auto=True)) == [
        "cursor-agent", "-p", "--output-format", "text", "--force", "PROMPT",
    ]
    assert _cmd(make_cursor_adapter(auto=False)) == [
        "cursor-agent", "-p", "--output-format", "text", "PROMPT",
    ]
    assert _cmd(make_cursor_adapter(model="gpt-5", auto=False)) == [
        "cursor-agent", "-p", "--output-format", "text", "--model", "gpt-5", "PROMPT",
    ]
    assert make_cursor_adapter().provider is AgentProvider.CURSOR


def test_prompt_is_always_last_argument():
    for make in (make_codex_adapter, make_claude_adapter, make_cursor_adapter):
        for auto in (True, False):
            assert _cmd(make(auto=auto), "trouve le flag")[-1] == "trouve le flag"


def test_container_adapter_applies_resource_limits():
    """Spec §10 : chaque conteneur a une limite RAM + CPU (garde-fou OOM)."""
    from fullctf.agents.container_adapter import ContainerAgentAdapter
    from fullctf.models.mission import AgentProvider
    captured = {}
    ad = ContainerAgentAdapter(
        AgentProvider.CLAUDE, challenge_files_dir="/tmp", memory_mb=1500, cpus=1.0,
        exec_run=lambda argv, t: (captured.setdefault("argv", argv), (0, "ok"))[1],
    )
    ad.run_mission("x", "/ws", 30)
    argv = captured["argv"]
    assert "--memory" in argv and "1500m" in argv
    assert "--cpus" in argv and "1.0" in argv
