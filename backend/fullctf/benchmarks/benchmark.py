"""Benchmarks systématiques (Sprint 11).

Compare des configurations (agent seul, parallèle, collaboratif, swarm adaptatif)
sur un lot de challenges, et calcule des métriques objectives.

Aucune supériorité n'est affirmée sans mesures comparables : ce module PRODUIT
les chiffres, il ne juge pas.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChallengeRun(BaseModel):
    """Résultat d'une tentative sur un challenge pour une configuration."""

    challenge_id: str
    config: str = Field(description="Nom de la config, ex. 'codex-solo', 'swarm-3'.")
    flag_accepted: bool
    duration_seconds: float
    cost_usd: float = 0.0
    human_interventions: int = 0
    reproduced: bool = False
    tool_failures: int = 0


class ConfigMetrics(BaseModel):
    """Métriques agrégées pour une configuration."""

    config: str
    runs: int
    flags_accepted: int
    acceptance_rate: float
    avg_duration_seconds: float
    total_cost_usd: float
    cost_per_accepted_flag: float | None  # None si aucun flag accepté
    avg_human_interventions: float
    reproducibility_rate: float
    total_tool_failures: int


def aggregate(config: str, runs: list[ChallengeRun]) -> ConfigMetrics:
    """Agrège les runs d'une configuration en métriques."""
    if not runs:
        return ConfigMetrics(
            config=config, runs=0, flags_accepted=0, acceptance_rate=0.0,
            avg_duration_seconds=0.0, total_cost_usd=0.0, cost_per_accepted_flag=None,
            avg_human_interventions=0.0, reproducibility_rate=0.0, total_tool_failures=0,
        )

    n = len(runs)
    accepted = sum(1 for r in runs if r.flag_accepted)
    total_cost = sum(r.cost_usd for r in runs)
    reproduced = sum(1 for r in runs if r.reproduced)

    return ConfigMetrics(
        config=config,
        runs=n,
        flags_accepted=accepted,
        acceptance_rate=round(accepted / n, 4),
        avg_duration_seconds=round(sum(r.duration_seconds for r in runs) / n, 2),
        total_cost_usd=round(total_cost, 4),
        cost_per_accepted_flag=round(total_cost / accepted, 4) if accepted else None,
        avg_human_interventions=round(sum(r.human_interventions for r in runs) / n, 2),
        reproducibility_rate=round(reproduced / n, 4),
        total_tool_failures=sum(r.tool_failures for r in runs),
    )


class Benchmark:
    """Collecte les runs par configuration et produit le comparatif."""

    def __init__(self) -> None:
        self._runs: dict[str, list[ChallengeRun]] = {}

    def record(self, run: ChallengeRun) -> None:
        self._runs.setdefault(run.config, []).append(run)

    def metrics(self) -> list[ConfigMetrics]:
        return [aggregate(cfg, runs) for cfg, runs in self._runs.items()]

    def best_by_acceptance(self) -> ConfigMetrics | None:
        """Config avec le meilleur taux de flags acceptés (None si vide)."""
        all_metrics = self.metrics()
        if not all_metrics:
            return None
        return max(all_metrics, key=lambda m: m.acceptance_rate)

    def to_markdown(self) -> str:
        """Tableau comparatif Markdown des configurations."""
        metrics = self.metrics()
        if not metrics:
            return "# Benchmark\n\n(aucune donnée)\n"
        lines = [
            "# Benchmark FullCTF Swarm",
            "",
            "| Config | Runs | Acceptés | Taux | Durée moy. (s) | Coût/flag | Reproductibilité |",
            "|---|---|---|---|---|---|---|",
        ]
        for m in metrics:
            cpf = f"${m.cost_per_accepted_flag}" if m.cost_per_accepted_flag is not None else "—"
            lines.append(
                f"| {m.config} | {m.runs} | {m.flags_accepted} | "
                f"{m.acceptance_rate:.0%} | {m.avg_duration_seconds} | {cpf} | "
                f"{m.reproducibility_rate:.0%} |"
            )
        return "\n".join(lines) + "\n"
