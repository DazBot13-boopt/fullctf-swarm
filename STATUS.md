# STATUS — état courant (pour reprise rapide en nouvelle session)

> Objectif : **résoudre des CTF DURS** en pilotant 3 CLI agents (Codex, Claude, Cursor)
> dans des conteneurs jetables, sans clé API (auth montée en live depuis l'hôte).

## Branche de travail
`ctfd-live` (poussée sur `github.com/DazBot13-boopt/fullctf-swarm`). `main` = base mergée.

## Ce qui est FAIT (testé, ~181 tests)
- **Pipeline** : Commander (classe, easy→1 agent) → worker en **conteneur jetable** →
  anti-injection (`wrap_untrusted`) → Evidence → **Flag Verifier** (+ filtre placeholder
  `NOM{...}`) → rapport. Code : `backend/fullctf/runner/real_mission.py`.
- **CTFd live** : connecte (token + login session), liste, download, **submit**.
  Code : `backend/fullctf/ctfd/{http,client,connector}.py`.
- **3 modes** (`backend/fullctf/ctfd/`) :
  - séquentiel (`solve_ctf`), `--parallel` (`solve_ctf_parallel`),
  - **`--workstealing`** (`workstealing.py`) : agents jamais au repos + course
    (1er qui trouve gagne, autres **annulés** via `adapter.cancel()`).
- **Intelligence d'équipe** (`runner/persistence.py` + `workstealing.py`) :
  bump d'insights, retries, anti-boucle, **débat anti-blocage** (`--debate` : tous
  bloqués → mise en commun → UN agent continue ; `approval_gate` = bouton humain).
- **Worker image** : `fullctf-worker:latest` = arsenal CTF complet + Node + Codex +
  Claude + Cursor. Auth montée au runtime (`scripts/run_worker.sh`).
  Limites RAM/CPU par conteneur (spec §10).
- **Arsenal hard-CTF v2** : `infrastructure/Dockerfile.hardctf` → tag
  `fullctf-worker:hardctf` (SageMath, ropper, gef, libc-database, pwninit, flint,
  nuclei/httpx/dalfox, seccomp-tools). `scripts/build_hardctf.sh` (durable tmux).
- **Traçabilité** : traces par agent dans `<data>/ctfd-<id>/traces/<agent>.log`.
- **Mission Control** (supervision live) : `python -m fullctf.supervisor.cli <data> status`.

## Prouvé EN VRAI (sur ctf.bugpwn.com, compte baco)
- Web : **TicketVault** résolu + soumis.
- Pwn : **PWN#Delta** résolu + soumis (par Cursor).
- Faible sur pwn/vuln/ot (dur pour un agent) ; fort sur web.

## Modèle d'usage retenu
**Superviseur** : lancer SANS `--auto-submit` → les flags sont **proposés** (loggés 🚩) →
l'humain (ou l'assistant) **vérifie et soumet** les vrais. Évite les mauvaises soumissions.

## Lancer
```bash
cd /root/DAZ/fullctf-swarm && source .venv/bin/activate
python -m fullctf.ctfd.connector --url https://ctf.bugpwn.com \
  --username <mail> --password <pass> --token <token> \
  --workstealing --debate --agents claude,codex,cursor \
  --ids 29,21,22 --data-root /tmp/run   # ajouter --auto-submit pour soumission auto
```

## Reste à faire (idées)
- Prompts plus musclés pour forcer le raisonnement (méthodologie, no-guess, vérif).
- Benchmark (M8) : mesurer le taux de réussite par catégorie.
- Pause-sur-limite + swap de compte auto. Dashboard poli. Merger `ctfd-live`→`main`.
