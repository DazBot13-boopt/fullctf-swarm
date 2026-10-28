# FullCTF Swarm

Plateforme supervisée de résolution de challenges **CTF autorisés** (Jeopardy et
Attack/Defense), orchestrant trois agents CLI (Codex, Claude Code, Cursor Agent)
avec preuves vérifiables et rapports reproductibles.

> ⚠️ Usage strictement limité aux challenges et infrastructures **explicitement
> autorisés** (CTF, labs, ranges possédés). Supervision humaine disponible à tout
> moment. Voir `CAHIER_DES_CHARGES.md`.

## État du projet

**Sprint 1 — Structure & API minimale** (en cours)

Déjà en place :
- Modèles de données : `Challenge`, `Mission`, `Evidence`, `FlagCandidate`
- Policies : `AutonomyPolicy` (auto-submit, checkpoints, mode local/connecté),
  `ToolAccessPolicy` (install libre + image fat)
- Machines à états (mission + flag) avec transitions contrôlées
- Interface `AgentAdapter` (Multi-CLI, config flexible 1/2/3 agents)
- API FastAPI minimale (health + import de challenges)
- Tests unitaires

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
