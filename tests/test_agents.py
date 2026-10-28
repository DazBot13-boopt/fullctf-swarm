"""Tests des adaptateurs d'agents et du registre (Sprint 3)."""

import sys

from fullctf.agents import (
    AgentRegistry,
    MockAgentAdapter,
    SubprocessAgentAdapter,
)
from fullctf.models.mission import AgentProvider


def test_mock_availability_and_run(tmp_path):
    a = MockAgentAdapter(AgentProvider.CODEX, response="trouvé")
    av = a.check_availability()
    assert av.usable is True
    assert av.provider == AgentProvider.CODEX

    r = a.run_mission("analyse", str(tmp_path), 10)
    assert r.success is True
    assert r.output == "trouvé"
    assert a.calls == ["analyse"]


def test_mock_not_authenticated_is_not_usable():
    a = MockAgentAdapter(AgentProvider.CLAUDE, authenticated=False)
    assert a.check_availability().usable is False


def test_mock_failure():
    a = MockAgentAdapter(AgentProvider.CURSOR, succeed=False)
    r = a.run_mission("x", "", 5)
    assert r.success is False
    assert r.error


def test_registry_flexible_configuration():
    reg = AgentRegistry()
    reg.register(MockAgentAdapter(AgentProvider.CODEX))
    reg.register(MockAgentAdapter(AgentProvider.CLAUDE, authenticated=False))
    reg.register(MockAgentAdapter(AgentProvider.CURSOR))

    usable = reg.usable_providers()
    assert AgentProvider.CODEX in usable
    assert AgentProvider.CURSOR in usable
    assert AgentProvider.CLAUDE not in usable  # pas authentifié
    assert reg.usable_count() == 2
    assert reg.has_any_usable() is True


def test_subprocess_adapter_runs_real_harmless_command(tmp_path):
    # On teste la machinerie subprocess avec une commande inoffensive (echo).
    adapter = SubprocessAgentAdapter(
        provider=AgentProvider.CODEX,
        version_cmd=[sys.executable, "--version"],
        build_run_command=lambda prompt: [sys.executable, "-c", f"print('écho: {prompt}')"],
    )
    av = adapter.check_availability()
    assert av.installed is True

    r = adapter.run_mission("salut", str(tmp_path), 15)
    assert r.success is True
    assert "écho: salut" in r.output


def test_subprocess_adapter_missing_cli():
    adapter = SubprocessAgentAdapter(
        provider=AgentProvider.CURSOR,
        version_cmd=["this-cli-does-not-exist-xyz", "--version"],
        build_run_command=lambda prompt: ["this-cli-does-not-exist-xyz", prompt],
    )
    assert adapter.check_availability().installed is False
