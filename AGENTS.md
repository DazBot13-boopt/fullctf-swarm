# AGENTS.md — Instructions pour les agents de développement

À lire AVANT toute modification, avec `CAHIER_DES_CHARGES.md`.
Ce fichier dit comment travailler sur ce dépôt et où en est le projet.

## État actuel du projet

Backend **Sprints 1–12 + persistance codés et testés** : **136 tests passent** (`pytest`).
Tout est développé avec des **mocks** pour les parties externes (agents, réseau).
Il reste le **Sprint 0** (à faire ICI, sur le VPS) : audit réel + branchement des
vrais CLI. Voir `SPRINT_0.md` et `scripts/sprint0_audit.sh`.

### Modules présents
| Zone | Paquet | Fait |
|---|---|---|
| Modèles + policies + états | `models/` | ✅ |
| Local Solver | `challenges/` | ✅ |
| Adaptateurs agents (1/2/3) | `agents/` | ✅ |
| Model tiering (fast/heavy) | `agents/model_config.py` | ✅ |
| Commander (règles + escalade + garde-fous) | `commander/` | ✅ |
| Cerveau LLM du Commander (optionnel) | `commander/brain.py` | ✅ |
| Expert Tool Engine + sandbox | `tools/` | ✅ |
| Image fat (arsenal complet) | `infrastructure/Dockerfile.arsenal` | ✅ |
| Evidence Store | `evidence/` | ✅ |
| Flag Verifier + extraction | `verifier/` | ✅ |
| Rapports | `reports/` | ✅ |
| Collaboration + débat | `swarm/` | ✅ |
| Playbooks | `playbooks/` | ✅ |
| Mémoire / RAG lexical | `memory/` | ✅ |
| Supervisor Chat (hybride) | `supervisor/` | ✅ |
| Dashboard | `frontend/index.html` | ✅ |
| CTFd + Local Executor | `ctfd/` | ✅ |
| Attack/Defense bot | `attackdefense/` | ✅ |
| Benchmarks | `benchmarks/` | ✅ |
| **Mission Runner (intégration bout-en-bout)** | `runner/` | ✅ |
| **Persistance (SQLite, PostgreSQL-ready)** | `persistence/` | ✅ |

### Ce qui reste (à finir ici)
- **Sprint 0** : lancer `scripts/sprint0_audit.sh`, installer les CLI manquants,
  tester chaque CLI en mode non-interactif, puis ajuster les commandes réelles
  dans `backend/fullctf/agents/providers.py`.
- Remplacer les mocks par les vrais adaptateurs dans un point d'entrée d'exécution.
- Brancher le `ModelCatalog` avec les noms de modèles réels (interroger les comptes).
- Persistance : SQLite en place (`FULLCTF_DB_PATH`). Pour PostgreSQL, implémenter
  un `DocStore` Postgres derrière la même interface (repositories inchangés).
- Evidence/Memory : persistés en write-through via DocStore (fait). L'API leur
  passe le store SQLite partagé.
- CAO : auditer et décider s'il devient une dépendance (sinon garder notre impl).

## Décisions d'architecture (ne pas casser)
- **Exactement 3 workers** : Codex CLI, Claude Code, Cursor Agent CLI. Jamais de 4e LLM.
- Le **Commander est logiciel** (noyau code = garde-fous). Le cerveau LLM ne fait
  que *proposer* ; le code *valide et exécute*.
- **CAO/CAI** : réimplémentation des concepts, PAS de copie de leur code. Tout
  réemploi de code tiers exige une vérification de licence d'abord.
- **Sécurité** : cibles autorisées uniquement, conteneurs jetables, pas de privilège
  hôte, flag non reproduit jamais soumis, données (challenges/RAG) = non fiables.

## Règles de travail
- Un sprint à la fois. Tests réels, jamais de résultat inventé.
- Ajouter des tests à toute nouvelle fonctionnalité ; lancer `pytest` après chaque
  changement.
- Ne pas committer de secrets (`.gitignore` protège `.env`).
- Mocks quand un CLI/service n'est pas disponible.
- Dépendances injectées (submitter, reproducer, approval_gate, http) pour rester
  testable sans réseau.

## Commandes
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                                   # 136 tests
uvicorn fullctf.api.main:app --app-dir backend  # API + dashboard sur /
bash scripts/sprint0_audit.sh            # audit environnement (lecture seule)
```
