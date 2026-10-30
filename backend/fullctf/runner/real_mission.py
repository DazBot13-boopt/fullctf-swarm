"""Orchestration d'une VRAIE mission (Sprint 0 — sortie des mocks).

Assemble les briques FullCTF conformément au cahier des charges :

  Commander (classe + alloue : easy -> Single, 1 agent)
    -> Mission (autonomy_policy)
    -> MissionRunner : worker DANS le conteneur jetable (ContainerAgentAdapter)
       -> wrap_untrusted (anti-injection) + Evidence Store
       -> Flag Verifier (candidate -> format_valid -> reproduced)
       -> soumission selon autonomy_policy (jamais un flag non reproduit)
    -> ESCALADE SÉQUENTIELLE : un seul agent à la fois ; si refus/filtre/échec,
       on passe à l'agent suivant (exactement le comportement observé :
       Codex filtré -> bascule Claude).

Le tout est injectable (`exec_run`) pour être testable sans Docker ni vrais agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..agents.base import MissionResult  # noqa: F401 (type documenté)
from ..agents.container_adapter import ContainerAgentAdapter, ExecRun
from ..agents.registry import AgentRegistry
from ..challenges.solver import LocalSolver
from ..commander.commander import Commander
from ..evidence.store import EvidenceStore
from ..models.challenge import Category, Challenge, Difficulty
from ..models.flag import FlagStatus
from ..models.mission import AgentProvider, Mission, MissionStatus
from ..models.policies import AutonomyPolicy, ExecutionMode
from ..reports.report import build_markdown_report
from ..runner.mission_runner import (
    ApprovalGate,
    FlagSubmitter,
    MissionRunner,
    Reproducer,
)

# Cadrage CTF monté dans le conteneur (réduit les refus de politique).
DEFAULT_AGENTS_MD = Path(__file__).resolve().parents[3] / "infrastructure" / "ctf_agents.md"

# Ordre d'escalade par défaut : Claude accepte le plus fiablement l'offensif.
DEFAULT_PROVIDER_ORDER = [AgentProvider.CLAUDE, AgentProvider.CODEX, AgentProvider.CURSOR]


@dataclass
class Attempt:
    provider: AgentProvider
    status: MissionStatus
    notes: str
    decoys_detected: int


@dataclass
class SolveResult:
    challenge_id: str
    title: str
    category: str
    mode: str
    solved: bool
    flag_value: str | None
    flag_status: str | None
    winning_agent: AgentProvider | None
    submitted: bool
    accepted: bool
    decoys_detected: int
    attempts: list[Attempt] = field(default_factory=list)
    report_markdown: str = ""


def solve_challenge(
    challenge: Challenge,
    *,
    files_dir: str | Path,
    data_root: str | Path,
    target: str | None = None,
    description: str = "",
    autonomy: AutonomyPolicy | None = None,
    image: str = "fullctf-worker:latest",
    agents_md: str | Path | None = None,
    provider_order: list[AgentProvider] | None = None,
    reproducer: Reproducer | None = None,
    submitter: FlagSubmitter | None = None,
    approval_gate: ApprovalGate | None = None,
    time_budget_seconds: int = 1800,
    exec_run: ExecRun | None = None,
) -> SolveResult:
    """Résout un challenge de bout en bout, conforme à la spec."""
    description = description or challenge.description
    autonomy = autonomy or AutonomyPolicy(
        mode=ExecutionMode.CONNECTED if target else ExecutionMode.LOCAL_ONLY,
        auto_submit_flag=False,
        human_checkpoints=False,
    )
    order = provider_order or DEFAULT_PROVIDER_ORDER
    agents_md = Path(agents_md) if agents_md else (
        DEFAULT_AGENTS_MD if DEFAULT_AGENTS_MD.is_file() else None
    )

    # Registre : un adaptateur CONTENEUR par fournisseur (worker isolé).
    registry = AgentRegistry()
    for prov in order:
        registry.register(
            ContainerAgentAdapter(
                prov,
                challenge_files_dir=files_dir,
                target=target,
                description=description,
                mode=autonomy.mode,
                image=image,
                agents_md=agents_md,
                exec_run=exec_run,
            )
        )

    # Commander : classification + allocation (easy -> Single).
    commander = Commander(registry, default_autonomy=autonomy)
    plan = commander.plan(challenge)

    usable = registry.usable_providers()
    if not usable:
        raise RuntimeError(
            "Aucun agent authentifié sur l'hôte (codex/claude/cursor). "
            "Connecte au moins un compte avant de lancer une mission."
        )

    solver = LocalSolver(data_root)
    evidence_store = EvidenceStore()
    runner = MissionRunner(
        solver, registry, evidence_store,
        reproducer=reproducer, submitter=submitter, approval_gate=approval_gate,
    )

    attempts: list[Attempt] = []
    all_evidences = []
    winning: AgentProvider | None = None
    final_flag = None
    submitted = accepted = False
    decoys_total = 0

    # Escalade séquentielle : un seul agent à la fois (pas les 3 en parallèle).
    for prov in usable:
        mission = Mission(
            challenge_id=challenge.id,
            agent_provider=prov,
            specialist_profile=plan.category,
            objective=f"Résous le challenge « {challenge.title} » (catégorie {plan.category}).",
            autonomy_policy=autonomy,
            time_budget_seconds=time_budget_seconds,
        )
        outcome = runner.run(challenge, mission)
        attempts.append(Attempt(prov, outcome.status, outcome.notes, outcome.decoys_detected))
        all_evidences.extend(outcome.evidences)
        decoys_total += outcome.decoys_detected

        got_flag = (
            outcome.flag is not None
            and outcome.flag.validation_status != FlagStatus.REJECTED
        )
        if got_flag:
            winning = prov
            final_flag = outcome.flag
            submitted = outcome.submitted
            accepted = outcome.accepted
            break
        # sinon : refus/filtre/échec/aucun flag -> on escalade vers l'agent suivant

    agents_line = [
        f"{a.provider.value}: {a.status.value} — {a.notes}" for a in attempts
    ]
    report = build_markdown_report(
        challenge,
        all_evidences,
        final_flag,
        agents=agents_line,
        strategies=[f"Mode {plan.mode.value} ; escalade séquentielle sur {len(attempts)} agent(s)."],
        uncertainties=(
            "" if winning else
            "Aucun agent n'a produit de flag fiable (refus/filtre ou échec). "
            "Escalade épuisée sur les agents disponibles."
        ),
    )

    return SolveResult(
        challenge_id=challenge.id,
        title=challenge.title,
        category=plan.category,
        mode=plan.mode.value,
        solved=winning is not None,
        flag_value=final_flag.value if final_flag else None,
        flag_status=final_flag.validation_status.value if final_flag else None,
        winning_agent=winning,
        submitted=submitted,
        accepted=accepted,
        decoys_detected=decoys_total,
        attempts=attempts,
        report_markdown=report,
    )


# --------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Résout un challenge CTF autorisé via FullCTF (worker en conteneur)."
    )
    p.add_argument("--files", required=True, help="Dossier contenant les fichiers du challenge (monté :ro).")
    p.add_argument("--title", required=True)
    p.add_argument("--category", default="unknown",
                   choices=[c.value for c in Category])
    p.add_argument("--difficulty", default="easy",
                   choices=[d.value for d in Difficulty])
    p.add_argument("--target", default=None, help="URL/connexion de la cible live (mode connected).")
    p.add_argument("--description", default="")
    p.add_argument("--scope", default="", help="authorization_scope du challenge.")
    p.add_argument("--data-root", default="/tmp/fullctf-data")
    p.add_argument("--image", default="fullctf-worker:latest")
    p.add_argument("--auto-submit", action="store_true", help="Active la soumission auto (nécessite reproducer).")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--report-out", default=None, help="Chemin où écrire le rapport Markdown.")
    args = p.parse_args(argv)

    challenge = Challenge(
        title=args.title,
        category=Category(args.category),
        difficulty=Difficulty(args.difficulty),
        description=args.description,
        source="local" if not args.target else "ctfd",
        authorization_scope=args.scope,
    )
    autonomy = AutonomyPolicy(
        mode=ExecutionMode.CONNECTED if args.target else ExecutionMode.LOCAL_ONLY,
        auto_submit_flag=args.auto_submit,
        human_checkpoints=False,
    )

    result = solve_challenge(
        challenge,
        files_dir=args.files,
        data_root=args.data_root,
        target=args.target,
        description=args.description,
        autonomy=autonomy,
        image=args.image,
        time_budget_seconds=args.timeout,
    )

    print(f"\n=== Résultat : {result.title} ({result.category}, mode {result.mode}) ===")
    for a in result.attempts:
        print(f"  - {a.provider.value:7} : {a.status.value:10} — {a.notes}")
    if result.solved:
        print(f"\n🚩 FLAG : {result.flag_value}  (statut: {result.flag_status}, agent: {result.winning_agent.value})")
        print(f"   soumis={result.submitted} accepté={result.accepted} leurres_écartés={result.decoys_detected}")
    else:
        print(f"\n❌ Pas de flag fiable (leurres écartés: {result.decoys_detected}).")

    if args.report_out:
        Path(args.report_out).write_text(result.report_markdown, encoding="utf-8")
        print(f"\nRapport écrit : {args.report_out}")

    return 0 if result.solved else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
