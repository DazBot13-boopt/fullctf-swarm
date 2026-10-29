"""Tests de l'Expert Tool Engine (Sprint 5)."""

import sys

from fullctf.tools import (
    DEFAULT_ARSENAL,
    DockerToolRunner,
    LocalToolRunner,
    ToolCategory,
    ToolManifest,
    ToolRegistry,
    build_default_registry,
)


def test_registry_register_and_get():
    reg = ToolRegistry()
    m = ToolManifest(id="ffuf", category=ToolCategory.WEB, command="ffuf")
    reg.register(m)
    assert reg.get("ffuf").id == "ffuf"


def test_registry_by_category():
    reg = build_default_registry()
    web = reg.by_category(ToolCategory.WEB)
    assert any(t.id == "ffuf" for t in web)
    assert all(t.category == ToolCategory.WEB for t in web)


def test_default_arsenal_is_well_formed():
    assert len(DEFAULT_ARSENAL) >= 10
    ids = [t.id for t in DEFAULT_ARSENAL]
    assert len(ids) == len(set(ids))  # pas de doublon


def test_registry_is_installed_detects_python():
    reg = ToolRegistry()
    reg.register(ToolManifest(id="py", category=ToolCategory.MISC, command="python3"))
    reg.register(ToolManifest(id="nope", category=ToolCategory.MISC, command="totally-missing-xyz"))
    assert reg.is_installed("py") is True
    assert reg.is_installed("nope") is False


def test_local_runner_executes(tmp_path):
    runner = LocalToolRunner()
    manifest = ToolManifest(
        id="echo-py", category=ToolCategory.MISC, command=sys.executable,
    )
    run = runner.run(manifest, ["-c", "print('hello tool')"], str(tmp_path))
    assert run.success is True
    assert "hello tool" in run.stdout


def test_local_runner_missing_tool(tmp_path):
    runner = LocalToolRunner()
    manifest = ToolManifest(id="x", category=ToolCategory.MISC, command="missing-bin-xyz")
    run = runner.run(manifest, [], str(tmp_path))
    assert run.success is False
    assert run.returncode == 127


def test_docker_runner_builds_isolated_command():
    runner = DockerToolRunner(image="fullctf-arsenal:latest")
    manifest = ToolManifest(id="binwalk", category=ToolCategory.FORENSIC, command="binwalk")
    cmd = runner._build_docker_command(manifest, ["-e", "file.bin"], "/tmp/ws")
    # Réseau coupé par défaut, image correcte, workspace monté, --rm.
    assert "--rm" in cmd
    assert "--network" in cmd and "none" in cmd
    assert "fullctf-arsenal:latest" in cmd
    assert "/tmp/ws:/work" in cmd


def test_docker_runner_enables_network_when_needed():
    runner = DockerToolRunner()
    manifest = ToolManifest(
        id="ffuf", category=ToolCategory.WEB, command="ffuf", needs_network=True,
    )
    cmd = runner._build_docker_command(manifest, ["-u", "http://x"], "/tmp/ws")
    assert "bridge" in cmd
