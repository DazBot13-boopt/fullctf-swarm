"""Tests des benchmarks (Sprint 11)."""

from fullctf.benchmarks import Benchmark, ChallengeRun, aggregate


def _run(config, accepted, duration=10.0, cost=0.5, reproduced=None, interventions=0, failures=0):
    return ChallengeRun(
        challenge_id="c", config=config, flag_accepted=accepted,
        duration_seconds=duration, cost_usd=cost,
        reproduced=accepted if reproduced is None else reproduced,
        human_interventions=interventions, tool_failures=failures,
    )


def test_aggregate_empty():
    m = aggregate("solo", [])
    assert m.runs == 0
    assert m.cost_per_accepted_flag is None


def test_aggregate_metrics():
    runs = [
        _run("solo", True, duration=20, cost=1.0),
        _run("solo", False, duration=10, cost=0.5),
    ]
    m = aggregate("solo", runs)
    assert m.runs == 2
    assert m.flags_accepted == 1
    assert m.acceptance_rate == 0.5
    assert m.avg_duration_seconds == 15.0
    assert m.total_cost_usd == 1.5
    assert m.cost_per_accepted_flag == 1.5  # 1.5$ total / 1 flag


def test_cost_per_flag_none_when_no_success():
    m = aggregate("solo", [_run("solo", False), _run("solo", False)])
    assert m.flags_accepted == 0
    assert m.cost_per_accepted_flag is None


def test_benchmark_records_and_compares():
    b = Benchmark()
    b.record(_run("codex-solo", True, cost=2.0))
    b.record(_run("codex-solo", False, cost=2.0))
    b.record(_run("swarm-3", True, cost=1.0))
    b.record(_run("swarm-3", True, cost=1.0))

    metrics = {m.config: m for m in b.metrics()}
    assert metrics["codex-solo"].acceptance_rate == 0.5
    assert metrics["swarm-3"].acceptance_rate == 1.0

    best = b.best_by_acceptance()
    assert best.config == "swarm-3"


def test_benchmark_markdown():
    b = Benchmark()
    b.record(_run("swarm-3", True))
    md = b.to_markdown()
    assert "Benchmark FullCTF Swarm" in md
    assert "swarm-3" in md
    assert "| Config |" in md


def test_benchmark_empty_markdown():
    assert "aucune donnée" in Benchmark().to_markdown()
