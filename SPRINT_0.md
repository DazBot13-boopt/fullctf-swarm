# Sprint 0 — Audit & branchement des vrais CLI (à faire sur le VPS)

Statut : NON COMMENCÉ. C'est le seul sprint qui a besoin du VPS réel et des
abonnements. Les Sprints 1–12 sont déjà codés et testés (mocks).

## Objectif
Valider que l'environnement et les 3 CLI fonctionnent réellement, puis brancher
nos adaptateurs (déjà prêts) à la place des mocks.

## Phase A — Inspection (lecture seule)
```bash
bash scripts/sprint0_audit.sh
```
Note : OS, CPU, RAM, disque, dépendances, Docker, présence des CLI.
Le script n'installe rien et ne lit aucun secret.

## Phase B — Audit CAO
- Dépôt officiel, révision, licence (Apache 2.0), API, modes de délégation.
- Décision : CAO comme dépendance OU on garde notre implémentation (par défaut).

## Phase C — Audit CAI
- Architecture + licences par composant (certaines restreintes à la recherche).
- Ne PAS exécuter son code. S'en inspirer seulement.

## Phase D — Test réel des 3 CLI (le point critique)
Pour chaque CLI (codex, claude, cursor-agent) :
1. version + authentification (sans afficher de secret).
2. tâche INOFFENSIVE non-interactive, ex. :
   « Lis math_demo.py et explique la fonction add. Ne modifie aucun fichier. »
3. vérifier : fonctionne sans GUI, mode auto autorisé, sortie récupérable.
4. ajuster la commande réelle dans `backend/fullctf/agents/providers.py`
   (`build_run_command`) selon le comportement observé.

## Critère de sortie
- Prérequis installés, 3 CLI testés en mode non-interactif.
- Commandes réelles ajustées dans providers.py.
- `ModelCatalog` rempli avec les modèles réellement disponibles.
- Un petit script d'exemple qui lance une vraie mission via le MissionRunner
  (en remplaçant MockAgentAdapter par les vrais adaptateurs).

## Interdictions
- Aucune activité offensive hors cible autorisée.
- Pas de 4e agent. Pas de copie de code CAO/CAI sans licence vérifiée.
- Pas de soumission automatique de flag sans autonomy_policy explicite.
- Ne jamais prétendre qu'un test a réussi sans l'avoir exécuté.

---

## Résultats Sprint 0 (exécuté sur le VPS — 2026-10-29)

### Phase A — Environnement (vérifié)
- Python 3.12.3, Docker 29.1.3 (démon OK), uv 0.13.5, node 24, tmux 3.4 : OK.
- Manquant : plugin `docker compose` v2 (non bloquant pour le build `docker build`).

### Phase D — 3 CLI testés en non-interactif (tâche inoffensive, lecture seule)
Commandes réelles constatées et branchées dans `agents/providers.py` :
- **codex** : `codex exec --skip-git-repo-check [-m MODEL] (--dangerously-bypass-approvals-and-sandbox | -s read-only) PROMPT`
- **claude** : `claude -p [--model MODEL] [--dangerously-skip-permissions] PROMPT`
- **cursor** : `cursor-agent -p --output-format text [--model MODEL] [--force] PROMPT`

Flag `auto` : True = plein accès (prévu pour tourner DANS le conteneur arsenal
isolé), False = sandbox sûr (test sur l'hôte). Verrouillé par `tests/test_providers.py`.

### Modèles réels (ModelCatalog)
`build_sprint0_catalog()` rempli depuis `cursor-agent --list-models` et les alias
Claude. Codex = défaut du compte (non deviné). Voir `tests/test_model_config.py`.

### Correctif infra critique : réseau des conteneurs Docker
Symptôme : le build de l'image arsenal échouait (`apt-get` ne trouvait aucun
paquet) et tout accès réseau depuis un conteneur restait bloqué.
Cause : `net.ipv4.ip_forward = 0` sur l'hôte → pas de NAT/forwarding pour le
bridge Docker. Correctif appliqué et **persisté** :
```
/etc/sysctl.d/99-fullctf-docker.conf : net.ipv4.ip_forward=1
```
Après correctif : DNS + TCP OK depuis le conteneur, build arsenal relancé.

### Reste à faire
- Vérifier l'image `fullctf-arsenal:latest` après build (pwn/angr/z3/ffuf/gdb/ghidra).
- Script d'exemple : vraie mission bout-en-bout via `MissionRunner` + vrai adaptateur.
