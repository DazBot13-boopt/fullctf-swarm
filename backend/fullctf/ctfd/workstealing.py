"""Dispatcher WORK-STEALING + débat anti-blocage + coordination de course.

- **Agents jamais au repos** : dès qu'un agent se libère, il reprend un challenge
  non résolu qu'il n'a pas encore tenté (renfort réparti).
- **Course** : si plusieurs agents sont sur le même challenge, le 1er qui trouve le
  flag GAGNE ; les autres sur CE challenge sont **annulés** (stop du conteneur).
- **Débat anti-blocage** (le vrai sens voulu) : quand **TOUS** les agents ont tenté
  un challenge **sans trouver** le flag, on les **oblige à débattre** — ils mettent
  leurs trouvailles en commun et concluent la meilleure piste — puis **UN SEUL**
  agent continue avec cette conclusion (les autres restent libres pour le reste).
  Déclenché automatiquement par le code ; un point d'approbation (`approval_gate`)
  permet d'exiger l'accord humain avant (le "bouton").

Réutilise : worker en conteneur, anti-injection + Flag Verifier, bump d'insights.
Exécution injectable (exec_run) pour être testable sans Docker.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..agents.container_adapter import ContainerAgentAdapter, ExecRun
from ..agents.registry import AgentRegistry
from ..models.challenge import Category, Difficulty
from ..models.flag import FlagCandidate, FlagStatus
from ..models.mission import AgentProvider
from ..models.policies import ExecutionMode
from ..playbooks.catalog import build_default_playbook_registry
from ..playbooks.render import category_profile, render_playbook
from ..runner.persistence import build_insights_block, summarize_attempt
from ..runner.real_mission import DEFAULT_PROVIDER_ORDER
from ..verifier.flag_verifier import FlagVerifier, extract_flags
from ..verifier.injection_guard import partition_candidates
from .client import CTFdChallenge, SubmissionResult

# Point d'approbation : reçoit le nom du challenge, retourne True pour autoriser le débat.
ApprovalGate = Callable[[str], bool]


@dataclass
class _ChallState:
    ch: CTFdChallenge
    files_dir: Path
    target: str | None
    base_objective: str
    solved_event: threading.Event = field(default_factory=threading.Event)
    solved: bool = False
    winner: AgentProvider | None = None
    flag: str | None = None
    submission: SubmissionResult | None = None
    debate: str = ""          # résumé du débat (conclusion + qui continue)
    debate_done: bool = False  # un débat a déjà eu lieu pour ce challenge
    cancelled_providers: set[AgentProvider] = field(default_factory=set)
    tried_by: set[AgentProvider] = field(default_factory=set)
    findings: list[str] = field(default_factory=list)
    adapters: dict = field(default_factory=dict)


@dataclass
class WSResult:
    ctfd_id: int
    name: str
    category: str
    solved: bool
    winner: AgentProvider | None
    flag: str | None
    submission: SubmissionResult | None
    debate: str
    cancelled: list[str]
    attempts: int


@dataclass
class WSSummary:
    total: int
    solved: int
    submitted_accepted: int
    results: list[WSResult] = field(default_factory=list)


def _usable_providers(
    exec_run: ExecRun | None, allowed: set[AgentProvider] | None = None
) -> list[AgentProvider]:
    reg = AgentRegistry()
    for prov in DEFAULT_PROVIDER_ORDER:
        if allowed is not None and prov not in allowed:
            continue
        reg.register(ContainerAgentAdapter(prov, challenge_files_dir=".", exec_run=exec_run))
    return reg.usable_providers()


def _parse_agents(agents: list[str] | None) -> set[AgentProvider] | None:
    """Convertit ['claude','codex'] -> set de providers (None = tous)."""
    if not agents:
        return None
    out = set()
    for a in agents:
        a = a.strip().lower()
        for prov in AgentProvider:
            if prov.value == a:
                out.add(prov)
    return out or None


def _map_category(ctfd_category: str) -> Category:
    from .connector import map_category
    return map_category(ctfd_category)


def _write_trace(data_root, st: _ChallState, provider: AgentProvider, tag: str, out: str) -> None:
    try:
        tdir = Path(data_root) / f"ctfd-{st.ch.id}" / "traces"
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / f"{provider.value}_{tag}.log").write_text(
            f"challenge: {st.ch.name} (id={st.ch.id}, {st.ch.category})\n"
            f"agent: {provider.value}  [{tag}]\n{'-' * 60}\n{out}\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def solve_ctf_workstealing(
    connector,
    *,
    data_root: str | Path,
    difficulty: Difficulty = Difficulty.UNKNOWN,
    categories: list[str] | None = None,
    only_ids: set[int] | None = None,
    limit: int | None = None,
    auto_submit: bool = False,
    debate: bool = False,
    approval_gate: ApprovalGate | None = None,
    agents: list[str] | None = None,
    image: str = "fullctf-worker:latest",
    time_budget_seconds: int = 1800,
    agents_md: str | Path | None = None,
    exec_run: ExecRun | None = None,
) -> WSSummary:
    if not connector.authenticate():
        raise RuntimeError("Authentification CTFd échouée.")
    providers = _usable_providers(exec_run, _parse_agents(agents))
    if not providers:
        raise RuntimeError("Aucun agent utilisable (vérifie --agents et l'auth hôte).")
    print(f"agents actifs : {', '.join(p.value for p in providers)}", flush=True)

    listed = connector.list_unsolved(categories, only_ids=only_ids)
    if limit is not None:
        listed = listed[:limit]

    playbooks = build_default_playbook_registry()
    verifier = FlagVerifier()
    lock = threading.Lock()
    http_lock = threading.Lock()
    states: dict[int, _ChallState] = {}

    for lc in listed:
        with http_lock:
            detailed = connector.fetch(lc.id) or lc
            chall_root = Path(data_root) / f"ctfd-{lc.id}"
            files_dir = connector.download_files(detailed, chall_root)
        cat = _map_category(detailed.category)
        challenge = connector.to_challenge(detailed, difficulty)
        pb = playbooks.select(challenge.model_copy(update={"category": cat}))
        base_obj = "\n\n".join(
            s for s in (
                f"Résous le challenge « {detailed.name} » (catégorie {cat.value}).",
                category_profile(cat), render_playbook(pb),
            ) if s
        )
        states[lc.id] = _ChallState(
            ch=detailed, files_dir=files_dir,
            target=detailed.connection_info, base_objective=base_obj,
        )

    def _new_adapter(provider: AgentProvider, st: _ChallState) -> ContainerAgentAdapter:
        return ContainerAgentAdapter(
            provider, challenge_files_dir=st.files_dir, target=st.target,
            description=st.ch.description,
            mode=ExecutionMode.CONNECTED if st.target else ExecutionMode.LOCAL_ONLY,
            image=image, agents_md=agents_md, exec_run=exec_run,
        )

    def _extract_flag(out: str) -> str | None:
        safe, _ = partition_candidates(extract_flags(out))  # écarte les leurres d'injection
        for cand in safe:
            fc = verifier.check_format(
                FlagCandidate(challenge_id="ws", value=cand, source_mission="ws")
            )
            if fc.validation_status == FlagStatus.FORMAT_VALID:
                return cand
        return None

    def _claim_flag(provider: AgentProvider, st: _ChallState, flag_val: str) -> bool:
        """Marque le challenge résolu (1er gagnant), annule les autres, soumet."""
        with lock:
            if st.solved:
                return False
            st.solved = True
            st.winner = provider
            st.flag = flag_val
            st.solved_event.set()  # annule les autres sur CE challenge
        print(f"  🚩 {provider.value} trouve le flag de {st.ch.name} : {flag_val}", flush=True)
        if auto_submit:
            with http_lock:
                st.submission = connector.submit(st.ch.id, flag_val)
            print(f"     submit={st.submission.status}", flush=True)
        return True

    def _run_debate(trigger: AgentProvider, st: _ChallState) -> None:
        """Tous bloqués -> débat (mise en commun) -> conclusion -> UN agent continue."""
        # Point d'approbation (le "bouton") : si fourni et refuse, on n'escalade pas.
        if approval_gate is not None and not approval_gate(st.ch.name):
            st.debate = "débat non autorisé (humain)"
            print(f"  ⏸ débat sur {st.ch.name} refusé (approbation humaine)", flush=True)
            return
        print(f"  💬 DÉBAT sur {st.ch.name} : tous bloqués, mise en commun…", flush=True)
        pooled = "\n\n---\n\n".join(st.findings) or "(aucune trouvaille notable)"
        proposals: list[str] = []
        for p in providers:
            obj = (
                f"DÉBAT D'ÉQUIPE sur « {st.ch.name} ». Tous les agents ont tenté SANS "
                f"trouver le flag. Voici ce qui a été tenté :\n\n{pooled}\n\n"
                "Propose LA meilleure prochaine approche concrète (différente de ce qui a "
                "échoué). Sois bref et précis."
            )
            r = _new_adapter(p, st).run_mission(obj, "", time_budget_seconds)
            if r.output:
                proposals.append(f"[{p.value}] {summarize_attempt(r.output, 800)}")
            _write_trace(data_root, st, p, "debat", r.output or "")
        conclusion = "\n\n".join(proposals) or "(pas de conclusion)"
        # UN SEUL agent continue avec la conclusion du débat.
        continuer = providers[0]
        st.debate = f"débat ({len(providers)} agents) → continue: {continuer.value}"
        print(f"     conclusion prête → {continuer.value} continue seul", flush=True)
        obj = (
            f"{st.base_objective}\n\nCONCLUSION DU DÉBAT D'ÉQUIPE (suis cette piste) :\n{conclusion}"
        )
        r = _new_adapter(continuer, st).run_mission(obj, "", time_budget_seconds)
        _write_trace(data_root, st, continuer, "post_debat", r.output or "")
        flag_val = _extract_flag(r.output or "")
        if flag_val:
            _claim_flag(continuer, st, flag_val)

    def pick(provider: AgentProvider) -> _ChallState | None:
        with lock:
            cands = [s for s in states.values() if not s.solved and provider not in s.tried_by]
            if not cands:
                return None
            cands.sort(key=lambda s: (len(s.adapters), -s.ch.solves))
            st = cands[0]
            st.tried_by.add(provider)
            return st

    def run_one(provider: AgentProvider, st: _ChallState) -> None:
        print(f"  → {provider.value} prend [{st.ch.category}] {st.ch.name} (id={st.ch.id})", flush=True)
        adapter = _new_adapter(provider, st)
        with lock:
            st.adapters[provider] = adapter
            objective = st.base_objective
            ins = build_insights_block(st.findings)
        if ins:
            objective = f"{objective}\n\n{ins}"

        done = threading.Event()

        def watcher() -> None:
            while not done.wait(1.0):
                if st.solved_event.is_set():
                    adapter.cancel()
                    return

        wt = threading.Thread(target=watcher, daemon=True)
        wt.start()
        try:
            result = adapter.run_mission(objective, "", time_budget_seconds)
        finally:
            done.set()
            wt.join(timeout=2)
            with lock:
                st.adapters.pop(provider, None)

        out = result.output or ""
        _write_trace(data_root, st, provider, "essai", out)

        if st.solved_event.is_set() and not result.success:
            with lock:
                st.cancelled_providers.add(provider)
            print(f"     ✗ {provider.value} annulé sur {st.ch.name} (déjà résolu)", flush=True)
            return

        flag_val = _extract_flag(out)
        if flag_val:
            _claim_flag(provider, st, flag_val)
            return

        # échec : on garde les trouvailles (bump) ; si TOUS ont tenté -> débat.
        with lock:
            st.findings.append(f"[{provider.value}] {summarize_attempt(out)}")
            trigger_debate = (
                debate and not st.solved and not st.debate_done
                and st.tried_by.issuperset(set(providers))
            )
            if trigger_debate:
                st.debate_done = True
        if trigger_debate:
            _run_debate(provider, st)

    def agent_loop(provider: AgentProvider) -> None:
        while True:
            st = pick(provider)
            if st is None:
                return
            run_one(provider, st)

    print(f"=== Work-stealing : {len(providers)} agents, {len(states)} challenges "
          f"(débat={'on' if debate else 'off'}) ===", flush=True)
    threads = [threading.Thread(target=agent_loop, args=(p,), daemon=True) for p in providers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    results = [
        WSResult(
            ctfd_id=st.ch.id, name=st.ch.name, category=st.ch.category,
            solved=st.solved, winner=st.winner, flag=st.flag,
            submission=st.submission, debate=st.debate,
            cancelled=[p.value for p in st.cancelled_providers],
            attempts=len(st.tried_by),
        )
        for st in states.values()
    ]
    solved = sum(1 for r in results if r.solved)
    accepted = sum(1 for r in results if r.submission and r.submission.accepted)
    return WSSummary(total=len(results), solved=solved, submitted_accepted=accepted, results=results)
