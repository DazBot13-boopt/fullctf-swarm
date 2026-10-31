"""Connecteur CTFd LIVE + orchestration « résous tout le CTF ».

Relie une instance CTFd autorisée au pipeline FullCTF :

  connexion (token et/ou login)
    -> liste des challenges (non résolus)
    -> pour chaque : détails + téléchargement des pièces jointes
       -> solve_challenge() : Commander -> worker en conteneur -> Evidence
          -> Flag Verifier -> rapport (escalade séquentielle)
    -> soumission selon autonomy_policy (jamais un leurre ; jamais sans accord
       si auto_submit est désactivé).

Tout est injectable (http transport, exec_run) pour rester testable sans réseau
ni Docker.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from pathlib import Path

from ..agents.container_adapter import ContainerAgentAdapter, ExecRun
from ..agents.registry import AgentRegistry
from ..models.challenge import Category, Challenge, Difficulty
from ..models.mission import AgentProvider
from ..models.policies import AutonomyPolicy, ExecutionMode
from ..runner.real_mission import DEFAULT_PROVIDER_ORDER, SolveResult, solve_challenge
from .client import CTFdChallenge, CTFdClient, HttpClient, SubmissionResult
from .http import HttpxClient

# Correspondance catégorie CTFd (texte libre) -> notre énumération.
_CATEGORY_MAP = {
    "web": Category.WEB, "web exploitation": Category.WEB,
    "pwn": Category.PWN, "binary": Category.PWN, "binary exploitation": Category.PWN,
    "rev": Category.REVERSE, "reverse": Category.REVERSE,
    "reversing": Category.REVERSE, "reverse engineering": Category.REVERSE,
    "crypto": Category.CRYPTO, "cryptography": Category.CRYPTO,
    "forensic": Category.FORENSIC, "forensics": Category.FORENSIC,
    "misc": Category.MISC, "stego": Category.MISC, "steganography": Category.MISC,
}


def map_category(ctfd_category: str) -> Category:
    return _CATEGORY_MAP.get((ctfd_category or "").strip().lower(), Category.UNKNOWN)


@dataclass
class CTFChallengeResult:
    ctfd_id: int
    name: str
    category: str
    solve: SolveResult
    submission: SubmissionResult | None = None


@dataclass
class CTFRunSummary:
    total: int
    solved: int
    submitted_accepted: int
    results: list[CTFChallengeResult] = field(default_factory=list)


class CTFdConnector:
    """Connecteur live vers une instance CTFd autorisée."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
        verify_tls: bool = True,
        http: HttpClient | None = None,  # injectable pour tests
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        # Transport réel par défaut (httpx) ; injectable pour les tests.
        self._httpx = http if http is not None else HttpxClient(base_url, token=token, verify_tls=verify_tls)
        self.client = CTFdClient(base_url, token or "", self._httpx)

    def authenticate(self) -> bool:
        """Login session si des identifiants sont fournis (sinon on s'appuie sur le token)."""
        if self._username and self._password and hasattr(self._httpx, "login"):
            return bool(self._httpx.login(self._username, self._password))
        return True

    def list_unsolved(
        self, categories: list[str] | None = None, only_ids: set[int] | None = None
    ) -> list[CTFdChallenge]:
        wanted = {c.lower() for c in categories} if categories else None
        out = []
        for c in self.client.list_challenges():
            if c.solved:
                continue
            if only_ids is not None and c.id not in only_ids:
                continue
            if wanted and c.category.lower() not in wanted:
                continue
            out.append(c)
        return out

    def fetch(self, challenge_id: int) -> CTFdChallenge | None:
        return self.client.get_challenge(challenge_id)

    def download_files(self, ch: CTFdChallenge, dest_dir: str | Path) -> Path:
        """Télécharge les pièces jointes dans <dest_dir>/files/. Retourne ce dossier."""
        files_dir = Path(dest_dir) / "files"
        files_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(self._httpx, "download"):
            for f in ch.files:
                name = Path(f.split("?")[0]).name or "attachment"
                try:
                    self._httpx.download(f, files_dir / name)
                except Exception:
                    pass  # pièce jointe indisponible : on continue (données non fiables)
        return files_dir

    def to_challenge(self, ch: CTFdChallenge, difficulty: Difficulty) -> Challenge:
        return Challenge(
            title=ch.name,
            category=map_category(ch.category),
            difficulty=difficulty,
            description=ch.description,
            source="ctfd",
            authorization_scope=f"{self.base_url} (compte autorisé)",
        )

    def submit(self, challenge_id: int, flag: str) -> SubmissionResult:
        return self.client.submit_flag(challenge_id, flag)


def solve_ctf(
    connector: CTFdConnector,
    *,
    data_root: str | Path,
    difficulty: Difficulty = Difficulty.UNKNOWN,
    categories: list[str] | None = None,
    limit: int | None = None,
    auto_submit: bool = False,
    image: str = "fullctf-worker:latest",
    time_budget_seconds: int = 1800,
    exec_run: ExecRun | None = None,
) -> CTFRunSummary:
    """Résout (et éventuellement soumet) les challenges non résolus d'un CTFd."""
    if not connector.authenticate():
        raise RuntimeError("Authentification CTFd échouée (token/identifiants).")

    challenges = connector.list_unsolved(categories)
    if limit is not None:
        challenges = challenges[:limit]

    results: list[CTFChallengeResult] = []
    for idx, listed in enumerate(challenges, 1):
        print(f"[{idx}/{len(challenges)}] {listed.category}/{listed.name} (id={listed.id})…", flush=True)
        detailed = connector.fetch(listed.id) or listed
        chall_root = Path(data_root) / f"ctfd-{listed.id}"
        files_dir = connector.download_files(detailed, chall_root)
        challenge = connector.to_challenge(detailed, difficulty)

        autonomy = AutonomyPolicy(
            mode=ExecutionMode.CONNECTED if detailed.connection_info else ExecutionMode.LOCAL_ONLY,
            auto_submit_flag=False,  # la soumission CTFd est gérée ici, après coup
            human_checkpoints=False,
        )
        solve = solve_challenge(
            challenge,
            files_dir=files_dir,
            data_root=chall_root / "work",
            target=detailed.connection_info,
            description=detailed.description,
            autonomy=autonomy,
            image=image,
            time_budget_seconds=time_budget_seconds,
            exec_run=exec_run,
        )

        submission: SubmissionResult | None = None
        # Soumission CTFd : jamais un leurre (solve_challenge écarte déjà les leurres),
        # uniquement un flag fiable, et seulement si auto_submit est activé.
        if auto_submit and solve.solved and solve.flag_value:
            submission = connector.submit(listed.id, solve.flag_value)

        results.append(
            CTFChallengeResult(
                ctfd_id=listed.id, name=listed.name, category=listed.category,
                solve=solve, submission=submission,
            )
        )
        _mark = "🚩" if solve.solved else "·"
        _sub = f" submit={submission.status}" if submission else ""
        print(f"      {_mark} flag={solve.flag_value or '—'} "
              f"agent={solve.winning_agent.value if solve.winning_agent else '—'}{_sub}", flush=True)

    solved = sum(1 for r in results if r.solve.solved)
    accepted = sum(1 for r in results if r.submission and r.submission.accepted)
    return CTFRunSummary(total=len(results), solved=solved,
                         submitted_accepted=accepted, results=results)


def _usable_providers(exec_run: ExecRun | None) -> list[AgentProvider]:
    """Agents réellement authentifiés sur l'hôte (ordre d'escalade par défaut)."""
    reg = AgentRegistry()
    for prov in DEFAULT_PROVIDER_ORDER:
        reg.register(ContainerAgentAdapter(prov, challenge_files_dir=".", exec_run=exec_run))
    return reg.usable_providers()


def solve_ctf_parallel(
    connector: CTFdConnector,
    *,
    data_root: str | Path,
    difficulty: Difficulty = Difficulty.UNKNOWN,
    categories: list[str] | None = None,
    limit: int | None = None,
    auto_submit: bool = False,
    image: str = "fullctf-worker:latest",
    time_budget_seconds: int = 1800,
    escalate_unsolved: bool = True,
    only_ids: set[int] | None = None,
    exec_run: ExecRun | None = None,
) -> CTFRunSummary:
    """Résout les challenges EN PARALLÈLE : chaque agent prend un challenge différent.

    - Phase « étalement » : N agents disponibles = N challenges traités en même temps
      (1 agent par challenge, chacun pioche le suivant dès qu'il se libère).
    - Phase « renfort » : les challenges que personne n'a résolus sont réessayés avec
      l'escalade complète (tous les agents) — couvre aussi le cas d'un seul challenge.

    Les appels HTTP (CTFd) sont sérialisés ; seule l'exécution des workers (Docker)
    tourne en parallèle.
    """
    if not connector.authenticate():
        raise RuntimeError("Authentification CTFd échouée (token/identifiants).")

    providers = _usable_providers(exec_run)
    if not providers:
        raise RuntimeError("Aucun agent authentifié sur l'hôte.")

    challenges = connector.list_unsolved(categories, only_ids=only_ids)
    if limit is not None:
        challenges = challenges[:limit]

    http_lock = threading.Lock()
    results: dict[int, CTFChallengeResult] = {}
    results_lock = threading.Lock()

    def process(listed: CTFdChallenge, provider_order: list[AgentProvider]) -> None:
        with http_lock:
            detailed = connector.fetch(listed.id) or listed
            chall_root = Path(data_root) / f"ctfd-{listed.id}"
            files_dir = connector.download_files(detailed, chall_root)
        autonomy = AutonomyPolicy(
            mode=ExecutionMode.CONNECTED if detailed.connection_info else ExecutionMode.LOCAL_ONLY,
            auto_submit_flag=False, human_checkpoints=False,
        )
        solve = solve_challenge(
            connector.to_challenge(detailed, difficulty),
            files_dir=files_dir, data_root=chall_root / "work",
            target=detailed.connection_info, description=detailed.description,
            autonomy=autonomy, image=image, provider_order=provider_order,
            time_budget_seconds=time_budget_seconds, exec_run=exec_run,
        )
        submission: SubmissionResult | None = None
        if auto_submit and solve.solved and solve.flag_value:
            with http_lock:
                submission = connector.submit(listed.id, solve.flag_value)
        with results_lock:
            results[listed.id] = CTFChallengeResult(
                ctfd_id=listed.id, name=listed.name, category=listed.category,
                solve=solve, submission=submission,
            )
        mark = "🚩" if solve.solved else "·"
        sub = f" submit={submission.status}" if submission else ""
        print(f"  {mark} [{listed.category}] {listed.name} "
              f"agent={solve.winning_agent.value if solve.winning_agent else '—'} "
              f"flag={solve.flag_value or '—'}{sub}", flush=True)

    # --- Phase étalement : un agent par challenge, en parallèle ---
    q: queue.Queue[CTFdChallenge] = queue.Queue()
    for c in challenges:
        q.put(c)

    def agent_worker(provider: AgentProvider) -> None:
        while True:
            try:
                listed = q.get_nowait()
            except queue.Empty:
                return
            print(f"  → {provider.value} prend [{listed.category}] {listed.name} (id={listed.id})",
                  flush=True)
            try:
                process(listed, [provider])  # un seul agent sur ce challenge
            finally:
                q.task_done()

    print(f"=== Étalement : {len(providers)} agents sur {len(challenges)} challenges ===",
          flush=True)
    threads = [threading.Thread(target=agent_worker, args=(p,), daemon=True) for p in providers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # --- Phase renfort : escalade complète sur ce qui reste non résolu ---
    if escalate_unsolved:
        unsolved = [c for c in challenges if not results[c.id].solve.solved]
        if unsolved:
            print(f"=== Renfort : escalade complète sur {len(unsolved)} challenge(s) non résolu(s) ===",
                  flush=True)
            for listed in unsolved:
                process(listed, list(providers))  # tous les agents (escalade)

    ordered = [results[c.id] for c in challenges]
    solved = sum(1 for r in ordered if r.solve.solved)
    accepted = sum(1 for r in ordered if r.submission and r.submission.accepted)
    return CTFRunSummary(total=len(ordered), solved=solved,
                         submitted_accepted=accepted, results=ordered)


# --------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:  # pragma: no cover
    import argparse
    import os

    p = argparse.ArgumentParser(description="Résout les challenges d'un CTFd autorisé.")
    p.add_argument("--url", required=True, help="URL de l'instance CTFd.")
    p.add_argument("--token", default=os.environ.get("CTFD_TOKEN"), help="Token API (ou $CTFD_TOKEN).")
    p.add_argument("--username", default=None)
    p.add_argument("--password", default=os.environ.get("CTFD_PASSWORD"))
    p.add_argument("--categories", default=None, help="Filtre, ex: web,crypto")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--difficulty", default="unknown", choices=[d.value for d in Difficulty])
    p.add_argument("--auto-submit", action="store_true")
    p.add_argument("--parallel", action="store_true",
                   help="Les agents traitent des challenges différents en parallèle.")
    p.add_argument("--workstealing", action="store_true",
                   help="Agents jamais au repos + course (1er qui trouve gagne, autres annulés).")
    p.add_argument("--debate", action="store_true",
                   help="Un autre agent confirme/réfute le flag avant toute soumission.")
    p.add_argument("--ids", default=None, help="Cibler des challenges précis, ex: 21,18,22")
    p.add_argument("--agents", default=None,
                   help="Limiter les agents, ex: claude,codex (défaut: tous ceux authentifiés)")
    p.add_argument("--no-verify-tls", action="store_true")
    p.add_argument("--data-root", default="/tmp/fullctf-ctfd")
    p.add_argument("--image", default="fullctf-worker:latest")
    p.add_argument("--timeout", type=int, default=1800)
    args = p.parse_args(argv)

    connector = CTFdConnector(
        args.url, token=args.token, username=args.username, password=args.password,
        verify_tls=not args.no_verify_tls,
    )
    cats = [c.strip() for c in args.categories.split(",")] if args.categories else None
    ids = {int(x) for x in args.ids.split(",")} if args.ids else None

    if args.workstealing:
        from .workstealing import solve_ctf_workstealing
        agents = [a.strip() for a in args.agents.split(",")] if args.agents else None
        ws = solve_ctf_workstealing(
            connector, data_root=args.data_root, difficulty=Difficulty(args.difficulty),
            categories=cats, only_ids=ids, limit=args.limit, auto_submit=args.auto_submit,
            debate=args.debate, agents=agents, image=args.image,
            time_budget_seconds=args.timeout,
        )
        print(f"\n=== CTF (work-stealing) : {ws.solved}/{ws.total} résolus, "
              f"{ws.submitted_accepted} acceptés ===")
        for r in ws.results:
            mark = "🚩" if r.solved else "❌"
            canc = f" | annulés: {','.join(r.cancelled)}" if r.cancelled else ""
            sub = f" | soumis: {r.submission.status}" if r.submission else ""
            deb = f" | débat: {r.debate}" if r.debate else ""
            print(f"  {mark} [{r.category}] {r.name} (gagnant: "
                  f"{r.winner.value if r.winner else '—'}, essais: {r.attempts}) "
                  f"flag: {r.flag or '—'}{sub}{deb}{canc}")
        return 0

    if args.parallel:
        summary = solve_ctf_parallel(
            connector, data_root=args.data_root, difficulty=Difficulty(args.difficulty),
            categories=cats, only_ids=ids, limit=args.limit, auto_submit=args.auto_submit,
            image=args.image, time_budget_seconds=args.timeout,
        )
    else:
        summary = solve_ctf(
            connector, data_root=args.data_root, difficulty=Difficulty(args.difficulty),
            categories=cats, limit=args.limit, auto_submit=args.auto_submit,
            image=args.image, time_budget_seconds=args.timeout,
        )

    print(f"\n=== CTF : {summary.solved}/{summary.total} résolus, "
          f"{summary.submitted_accepted} acceptés ===")
    for r in summary.results:
        flag = r.solve.flag_value or "—"
        sub = f" | soumis: {r.submission.status}" if r.submission else ""
        mark = "🚩" if r.solve.solved else "❌"
        print(f"  {mark} [{r.category}] {r.name} (agent: "
              f"{r.solve.winning_agent.value if r.solve.winning_agent else '—'}) "
              f"flag: {flag}{sub}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
