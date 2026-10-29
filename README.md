# FullCTF Swarm

Plateforme supervisée de résolution de challenges **CTF autorisés** (Jeopardy et
Attack/Defense), orchestrant trois agents CLI (Codex, Claude Code, Cursor Agent)
avec preuves vérifiables et rapports reproductibles.

> ⚠️ Usage strictement limité aux challenges et infrastructures **explicitement
> autorisés** (CTF, labs, ranges possédés). Supervision humaine disponible à tout
> moment. Voir `CAHIER_DES_CHARGES.md`.

## État du projet

**Backend complet (Sprints 1–11)** — 101 tests passent. Le squelette produit est
codé et testé avec des mocks. Reste le **Sprint 0** (sur VPS) : audit CAO/CAI +
branchement des vrais CLI.

| Sprint | Module | État |
|---|---|---|
| 1 | Modèles, policies, API, machines à états | ✅ |
| 2 | Local Solver (import, workspaces isolés) | ✅ |
| 3 | Adaptateurs agents + registre flexible 1/2/3 | ✅ |
| 4 | Commander (classification, allocation, escalade, garde-fous) | ✅ |
| 5 | Expert Tool Engine + sandbox + image fat (Dockerfile) | ✅ |
| 6 | Evidence Store + Flag Verifier + Reports | ✅ |
| 7 | Collaboration + débat + playbooks | ✅ |
| 8 | Mémoire / RAG lexical | ✅ |
| 9 | Dashboard + Supervisor Chat (hybride) | ✅ |
| 10 | Connecteur CTFd + Local Executor | ✅ |
| 11 | Benchmarks systématiques | ✅ |
| 0 | Audit CAO/CAI + vrais CLI (**à faire sur VPS**) | ⏳ |

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Lancer l'API

```bash
uvicorn fullctf.api.main:app --reload --app-dir backend
```

Puis : http://127.0.0.1:8000/health et la doc auto sur http://127.0.0.1:8000/docs

## Lancer les tests

```bash
pytest
```

## Structure

```
backend/fullctf/
  api/          API FastAPI
  models/       Contrats de données + machines à états
  agents/       Interface des adaptateurs CLI
  commander/    Commander (squelette, Sprint 4)
tests/          Tests unitaires
```

## Feuille de route

Développement incrémental, un sprint à la fois, validation humaine entre chaque.
Voir `CAHIER_DES_CHARGES.md` (section Plan de développement).
