"""Dispatcher WORK-STEALING + coordination de course.

Objectif (demandé explicitement) :
- **Aucun agent au repos** tant qu'il reste du travail utile : dès qu'un agent se
  libère, il reprend un challenge non résolu qu'il n'a pas encore tenté (renfort).
- **Plusieurs agents sur un challenge dur** = course ; le **1er qui trouve gagne**,
  les autres sur CE challenge sont **annulés** (stop de leur conteneur, pas de
  calcul gâché).
- **Traçabilité totale** : qui prend quoi, qui gagne, qui est annulé — en direct et
  dans des fichiers de trace par agent.

Réutilise les briques FullCTF : worker en conteneur (ContainerAgentAdapter),
anti-injection + Flag Verifier, bump d'insights. Exécution injectable (exec_run)
pour être testable sans Docker.
"""

from __future__ import annotations

import threading
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
from ..swarm.debate import _interpret as interpret_verdict
from ..verifier.flag_verifier import FlagVerifier, extract_flags
from ..verifier.injection_guard import partition_candidates
from .client import CTFdChallenge, SubmissionResult


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
    debate: str = ""  # verdict de la vérification croisée (ex: "codex: AGREE")
    cancelled_providers: set[AgentProvider] = field(default_factory=set)
    tried_by: set[AgentProvider] = field(default_factory=set)
    findings: list[str] = field(default_factory=list)
    adapters: dict = field(default_factory=dict)  # provider -> adapter en cours (pour cancel)


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


def _usable_providers(exec_run: ExecRun | None) -> list[AgentProvider]:
    reg = AgentRegistry()
    for prov in DEFAULT_PROVIDER_ORDER:
        reg.register(ContainerAgentAdapter(prov, challenge_files_dir=".", exec_run=exec_run))
    return reg.usable_providers()


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
    image: str = "fullctf-worker:latest",
    time_budget_seconds: int = 1800,
    agents_md: str | Path | None = None,
    exec_run: ExecRun | None = None,
) -> WSSummary:
    if not connector.authenticate():
        raise RuntimeError("Authentification CTFd échouée.")
    providers = _usable_providers(exec_run)
    if not providers:
        raise RuntimeError("Aucun agent authentifié sur l'hôte.")

    listed = connector.list_unsolved(categories, only_ids=only_ids)
    if limit is not None:
        listed = listed[:limit]

    playbooks = build_default_playbook_registry()
    verifier = FlagVerifier()
    lock = threading.Lock()
    http_lock = threading.Lock()
    states: dict[int, _ChallState] = {}

    # Préparation (fetch + download + objectif) — sérialisée (HTTP).
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

    def pick(provider: AgentProvider) -> _ChallState | None:
        """Choisit un challenge non résolu non encore tenté par cet agent (fewest workers)."""
        with lock:
            cands = [
                st for st in states.values()
                if not st.solved and provider not in st.tried_by
            ]
            if not cands:
                return None
            # préférer le moins "chargé" (renfort réparti), puis le plus de solves (facile).
            cands.sort(key=lambda s: (len(s.adapters), -s.ch.solves))
            st = cands[0]
            st.tried_by.add(provider)
            return st

    def _review_flag(reviewer: AgentProvider, st: _ChallState, flag_val: str,
                     proposer: AgentProvider) -> bool:
        """Vérification croisée : un autre agent confirme (AGREE) ou réfute (DISAGREE)."""
        objective = (
            f"VÉRIFICATION CROISÉE (débat). L'agent {proposer.value} propose ce flag "
            f"pour le challenge « {st.ch.name} » : {flag_val}\n"
            "Vérifie de façon critique et INDÉPENDANTE si c'est bien le vrai flag "
            "(tu peux re-tester sur la cible / relire la source). "
            "Réponds AGREE si tu confirmes, DISAGREE sinon, suivi d'une courte justification."
        )
        ad = ContainerAgentAdapter(
            reviewer, challenge_files_dir=st.files_dir, target=st.target,
            description=st.ch.description,
            mode=ExecutionMode.CONNECTED if st.target else ExecutionMode.LOCAL_ONLY,
            image=image, agents_md=agents_md, exec_run=exec_run,
        )
        res = ad.run_mission(objective, "", time_budget_seconds)
        _write_trace(data_root, st, reviewer, res.success, f"[REVUE] {res.output or ''}")
        return interpret_verdict(res.output) if res.success else False

    def run_one(provider: AgentProvider, st: _ChallState) -> None:
        print(f"  → {provider.value} prend [{st.ch.category}] {st.ch.name} (id={st.ch.id})", flush=True)
        adapter = ContainerAgentAdapter(
            provider, challenge_files_dir=st.files_dir, target=st.target,
            description=st.ch.description,
            mode=ExecutionMode.CONNECTED if st.target else ExecutionMode.LOCAL_ONLY,
            image=image, agents_md=agents_md, exec_run=exec_run,
        )
        with lock:
            st.adapters[provider] = adapter
        # prompt = objectif + insights (bump) des essais précédents
        with lock:
            insights = build_insights_block(st.findings)
        objective = st.base_objective + (f"\n\n{insights}" if insights else "")

        # watcher : si le challenge est résolu par un autre -> on annule cet agent.
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
        _write_trace(data_root, st, provider, result.success, out)

        # annulé par la course ?
        if st.solved_event.is_set() and not result.success:
            with lock:
                st.cancelled_providers.add(provider)
            print(f"     ✗ {provider.value} annulé sur {st.ch.name} (déjà résolu)", flush=True)
            return

        # extraction + anti-leurre + format
        safe, suspicious = partition_candidates(extract_flags(out))
        flag_val = None
        for cand in safe:
            fc = verifier.check_format(FlagCandidate(challenge_id=st.ch.name, value=cand, source_mission=provider.value))
            if fc.validation_status == FlagStatus.FORMAT_VALID:
                flag_val = cand
                break

        if flag_val:
            with lock:
                if not st.solved:
                    st.solved = True
                    st.winner = provider
                    st.flag = flag_val
                    st.solved_event.set()  # annule les autres sur CE challenge
                    first = True
                else:
                    first = False
            if first:
                print(f"  🚩 {provider.value} trouve le flag de {st.ch.name} : {flag_val}", flush=True)
                # Débat : un AUTRE agent confirme/réfute AVANT la soumission.
                do_submit = auto_submit
                if auto_submit and debate:
                    reviewer = next((p for p in providers if p != provider), None)
                    if reviewer is not None:
                        agree = _review_flag(reviewer, st, flag_val, provider)
                        st.debate = f"{reviewer.value}: {'AGREE' if agree else 'DISAGREE'}"
                        do_submit = agree
                        print(f"     débat: {reviewer.value} → {'AGREE ✓' if agree else 'DISAGREE ✗'}", flush=True)
                if do_submit:
                    with http_lock:
                        st.submission = connector.submit(st.ch.id, flag_val)
                    print(f"     submit={st.submission.status}", flush=True)
                elif auto_submit and debate:
                    print(f"     non soumis (désaccord du débat) → proposé pour validation humaine", flush=True)
            return

        # échec : on garde les trouvailles pour les suivants (bump)
        with lock:
            st.findings.append(f"[{provider.value}] {summarize_attempt(out)}")

    def agent_loop(provider: AgentProvider) -> None:
        while True:
            st = pick(provider)
            if st is None:
                return  # plus rien d'utile pour cet agent -> repos
            run_one(provider, st)

    print(f"=== Work-stealing : {len(providers)} agents, {len(states)} challenges ===", flush=True)
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


def _map_category(ctfd_category: str) -> Category:
    from .connector import map_category
    return map_category(ctfd_category)


def _write_trace(data_root, st: _ChallState, provider: AgentProvider, success: bool, out: str) -> None:
    try:
        tdir = Path(data_root) / f"ctfd-{st.ch.id}" / "traces"
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / f"{provider.value}.log").write_text(
            f"challenge: {st.ch.name} (id={st.ch.id}, {st.ch.category})\n"
            f"agent: {provider.value}  succes_run: {success}\n"
            f"{'-' * 60}\n{out}\n",
            encoding="utf-8",
        )
    except Exception:
        pass
