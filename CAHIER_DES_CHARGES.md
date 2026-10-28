# FullCTF Swarm — Cahier des charges V1.8
## Version de référence pour le développement local incrémental

- **Statut** : spécification approuvée pour audit, implémentation non commencée.
- **Environnement initial** : VPS Ubuntu, développement dans le compte utilisateur.
- **Environnement cible** : serveur Linux principal + exécuteur local optionnel.
- **Changements V1.7** : ajout des *Autonomy Policy*, *Tool Installation & Performance Policy*,
  du format **Attack/Defense**, et de la notion de **Playbooks** réutilisables.
- **Changements V1.8** : ajout du **Supervisor Chat (Mission Control)** dans M7,
  et de la **logique d'escalade adaptative** dans M5.
- **Changements V1.9** : **Commander hybride** (noyau code + cerveau LLM),
  **Supervisor Chat hybride**, et **configuration flexible des agents** (1, 2 ou 3).

---

## 1. Vision

Construire une plateforme autonome mais supervisée de résolution de challenges CTF
explicitement autorisés — **Jeopardy** (Web, Pwn, Reverse, Crypto, Forensic, Misc)
**et Attack/Defense** — avec preuves reproductibles et rapports techniques.

Les performances doivent être **mesurées**, jamais présumées.

---

## 2. Architecture générale

Trois couches de responsabilité séparées :

- **CAO (CLI Agent Orchestrator)** — socle d'orchestration prioritaire (à auditer).
  Plomberie : sessions CLI, lancement/arrêt, communication inter-agents, délégation, API.
- **CAI (Cybersecurity AI)** — source d'**inspiration** uniquement (dépôt archivé,
  licences à vérifier avant tout réemploi de code).
- **FullCTF** — la couche qui nous distingue : Commander adaptatif, Evidence Store,
  Flag Verifier, mémoire/RAG, playbooks, dashboard, benchmarks.

**Règle clé** : le Commander est une *couche de décision au-dessus de CAO*,
jamais une seconde orchestration concurrente.

### Trois workers agentiques exclusivement
1. OpenAI **Codex CLI**
2. Anthropic **Claude Code CLI**
3. **Cursor Agent CLI** (sélection auto de modèle si disponible)

Aucun 4ᵉ LLM permanent. Les 3 agents **endossent des profils** d'experts
(Reverse, Pwn, Crypto, Web, Forensic…) selon le challenge.

### Configuration flexible des agents (NOUVEAU — 1, 2 ou 3)
Le tool **détecte au démarrage** quels CLI sont installés + authentifiés, construit
la liste des agents disponibles et **s'adapte**. Il ne dépend jamais d'un agent précis.

- **3 agents** (Codex + Claude + Cursor) → pleine puissance : tous les modes,
  débat à 3.
- **2 agents** (n'importe quelle paire) → parallèle, collaboration, débat à 2.
  Quasi aussi puissant que 3.
- **1 agent** (n'importe lequel seul) → mode Single. L'escalade devient
  **séquentielle** (le même agent change de profil/stratégie) et le débat devient
  de l'**auto-révision** (il critique sa propre solution avant de valider).

Note : avec 1 seul agent, ce même compte sert aussi de cerveau LLM du Commander
et de LLM du Supervisor Chat → plus de tokens sur un compte, exécution séquentielle.
Mode escalade + budgets d'autant plus utiles pour contrôler la dépense.

### Schéma logique

```
FullCTF Control Center (Dashboard)
          |
     FullCTF API
          |
   FullCTF Commander  (décisions, budgets, parallélisme, autonomie)
          |
   CAO Orchestration Layer
          |
   +------+------+------+
 Codex      Claude    Cursor
   |          |         |
   +------+------+------+
          |
   FullCTF Shared Services
   | Expert Tool Engine | Knowledge/RAG + Playbooks |
   | Evidence Store | Debate Engine | Stagnation Detector |
   | Flag Verifier | Benchmark Engine |
          |
   Sandboxed Executors (conteneurs jetables)
          |
   Challenges locaux / CTFd autorisés / range A/D
          |
   Flag Delivery + Technical Reports
```

---

## 3. Autonomy Policy (NOUVEAU — par mission)

Chaque mission possède des réglages d'autonomie **activables/désactivables**,
soit par défi, soit via un profil global (ex. "mode compétition" vs "mode entraînement").

```yaml
autonomy_policy:
  auto_submit_flag: bool        # ON = l'agent soumet le flag lui-même
                                # OFF = il propose, l'humain soumet
  human_checkpoints: bool       # ON = demande l'avis humain aux points clés
                                # OFF = décide seul et avance
  mode: "local_only" | "connected"
                                # local_only = travail hors-ligne sur fichiers,
                                #              juste trouver le flag
                                # connected  = accès à la plateforme/cible autorisée
```

Exemples de combinaisons :
- `local_only` + `auto_submit=OFF` → fouille un binaire, propose le flag, l'humain vérifie.
- `connected` + `auto_submit=ON` + `human_checkpoints=OFF` → autonomie complète (mode compétition).
- `connected` + `auto_submit=ON` + `human_checkpoints=ON` → autonome mais demande avant les actions sensibles.

Le **Commander** lit cette policy et adapte son comportement. Rien n'est codé en dur.

---

## 4. Tool Installation & Performance Policy (NOUVEAU)

Objectif : **liberté totale** d'outillage pour les agents **+ vitesse maximale**,
sans risque pour l'hôte.

### Stratégie d'installation (optimisée vitesse)
- **Image Docker "fat" pré-équipée** : tout l'arsenal CTF installé une seule fois,
  disponible instantanément au démarrage de chaque mission (gros gain de vitesse).
- **Volume de cache partagé** : les installs supplémentaires sont conservées et
  réutilisées (jamais réinstallées deux fois).
- **Install libre à la volée** : l'agent peut installer tout outil manquant dans
  son conteneur, sans blocage.

### Policy d'accès outils (par mission)
```yaml
tool_access_policy:
  can_install: true                     # liberté totale d'installer
  sandbox: "container"                  # tout dans un conteneur jetable
  persist_installs: true                # cache partagé pour la vitesse
  network_for_install: true             # réseau autorisé pour télécharger
  base_image: "fullctf-arsenal:latest"  # image fat pré-équipée
```

### Périmètre (le seul garde-fou)
- Liberté **totale à l'intérieur** du conteneur : install, compile, download, casse.
- L'**hôte (VPS) n'est jamais modifié** par les agents → il reste propre et stable,
  ce qui garantit la performance sur la durée.
- Dégâts confinés au conteneur, effacés instantanément (jeter + relancer).
- Un conteneur tourne à la **même vitesse** que l'hôte : l'isolation ne coûte rien
  en performance, elle protège la performance dans le temps.

---

## 5. Les huit modules fondamentaux

- **M1 — Multi-CLI Integration** : adaptateurs unifiés (version, capacités, auth état,
  lancement, sorties, annulation, erreurs, coût/modèle si dispo).
- **M2 — Hybrid Swarm** : modes Single / Parallel Independent / Collaborative /
  Debate & Review. Distinction stricte fait observé / hypothèse / résultat reproduit.
- **M3 — Expert Arsenal** : registre versionné d'outils + manifestes + wrappers
  (voir §7). Image fat + install libre (voir §4).
- **M4 — Advanced Memory** : historique, preuves, stratégies, erreurs, recherche
  hybride lexicale+vectorielle, RAG. Données RAG = **non fiables**, citées.
- **M5 — Adaptive Commander** : classification, profils, budgets, parallélisme,
  stagnation, pause/reprise/arrêt, lecture de l'`autonomy_policy`. Règles explicites d'abord.
  Inclut la **logique d'escalade adaptative** (voir §5bis).
- **M6 — CTFd Integration** : auth autorisée, liste challenges, pièces jointes,
  statuts. Soumission selon `autonomy_policy` (manuelle par défaut).
- **M7 — Real-Time Dashboard** : challenges, agents, missions, logs, preuves,
  coûts/temps, contrôles pause/arrêt, flags, rapports. Accès distant sécurisé.
  Inclut le **Supervisor Chat / Mission Control** (voir §7bis).
- **M8 — Systematic Benchmarks** : comparaison agents seuls / indépendants /
  collaboratifs / swarm adaptatif. Mesures : taux de flags acceptés, temps, coût,
  interventions humaines, reproductibilité, taux d'échec outils, ressources.

---

## 5bis. Commander hybride & logique d'escalade adaptative (NOUVEAU — M5)

### Commander hybride (noyau code + cerveau LLM)
Le Commander n'est pas un simple script rigide, ni un LLM pur. C'est une
**combinaison** :

- **Noyau CODE (règles explicites)** — gère les décisions mécaniques et critiques :
  budgets, timeouts, états des missions, sécurité, détection de stagnation,
  validation des transitions. → fiable, gratuit, instantané, **auditable**.
- **Cerveau LLM (optionnel, greffé plus tard)** — gère les décisions stratégiques
  et floues : classification fine, choix du mode, quel agent sur quel challenge.
  → intelligent, adaptatif.

**Règle d'or de l'hybride : le LLM *propose*, le code *valide et exécute*.**
Les gardes-fous (budget, sécurité, autorisations) restent toujours dans le code.
Si le LLM déraille ou est indisponible, le noyau code reprend la main.
Le LLM utilisé est **un des agents existants** (pas de 4ᵉ abonnement).

Ordre de construction : noyau code pur d'abord (Sprint 4), cerveau LLM greffé
ensuite (Sprint 7+), une fois la base stable.

### Logique d'escalade adaptative
Principe : **commencer léger, monter en puissance seulement si ça coince.**
Évite de gaspiller 3 agents sur un challenge facile, mais mobilise toute la
force sur un challenge dur.

### Allocation initiale (par règles explicites)
Le Commander classe le challenge puis choisit un mode de départ :
- Difficulté *easy/medium* → **Single** (1 agent, le mieux adapté au profil).
- Difficulté *hard* → **Parallel Independent** (plusieurs agents, approches distinctes).
- Difficulté *insane* → **Collaborative / Debate** possible d'emblée.

Facteurs pris en compte : difficulté annoncée, budget temps/coût autorisé,
disponibilité des agents, progrès mesurés.

### Boucle d'escalade
```
1. Lancer 1 agent (économe)
2. Stagnation Detector : bloqué depuis X min / Y tentatives sans progrès ?
3. OUI → renfort : ajouter un 2e agent (approche différente)
4. Toujours bloqué ? → passer les agents en mode Collaborative / Debate
5. Flag trouvé → vérification (candidate → reproduced) → livraison
6. Budget épuisé sans flag → stop + rapport d'échec documenté
```

### Cas d'un seul challenge (ex. 1 seul challenge Web sur le site)
- classé Web → profil + playbook Web chargés ;
- démarre avec 1 agent → escalade vers 2 puis 3 uniquement si blocage ;
- l'humain peut **forcer** le mode via le Supervisor Chat
  ("mets les 3 dessus" / "garde-en 1, pas urgent").

Les agents non mobilisés restent disponibles pour d'autres challenges/sites.

---

## 6. Playbooks réutilisables (NOUVEAU — intégré à M3/M4)

Un **playbook** = une recette éprouvée par catégorie (ou par service récurrent)
qui transforme l'intelligence de l'agent en **vitesse concrète**.

- Déclencheur (comment l'agent reconnaît le cas).
- Étapes ordonnées (quoi tester, dans quel ordre, avec quel outil).
- Ressources associées (wordlists dédiées, wrappers de sortie structurée).

Exemples : `pwn/basic-bof`, `crypto/rsa`, `web/media-service`, `forensic/memory-dump`.

**Dépendance** : un playbook n'est testable qu'une fois l'**image fat** et un
**agent branché** disponibles → donc écrit *après* la base (Sprints 5–7),
pas au tout début.

---

## 7. Sous-systèmes transversaux

### Local Solver
- Import : ZIP, ELF, Python, sources, PCAP, images, archives, dumps mémoire, textes.
- Originaux **immuables** conservés. Workspace isolé par agent.

### Evidence Store
- Chaque preuve : id, challenge, agent+outil, horodatage, commande/procédure,
  artefact, empreinte, niveau de confiance, statut de vérification.

### Flag Delivery
- États : `candidate → format_valid → reproduced → accepted / rejected`.
- Un flag local ≠ flag accepté.
- Soumission auto **uniquement si** `autonomy_policy.auto_submit_flag = true`.

### Technical Report
- Résumé, classification, stratégies, agents, outils, étapes, commandes/scripts,
  preuves, flag candidat, méthode de reproduction, incertitudes, temps et coûts.

### 7bis. Supervisor Chat / Mission Control (NOUVEAU — M7)
Interface conversationnelle pour superviser pendant que les agents travaillent.
Permet à l'humain d'interroger l'état en temps réel et d'intervenir.

Fonctions :
- **Requêtes temps réel** : "Où en est Codex ?", "Qui est bloqué ?", "Ça avance ?"
  → réponses basées sur l'état réel (missions, budgets, temps, dernières preuves).
- **Blocages exposés** : le Stagnation Detector remonte directement dans le chat.
- **Résumé en langage naturel** : un agent LLM résume l'état en **lecture seule**.
- **Architecture hybride (comme le Commander)** : le **noyau code** fournit les
  faits bruts fiables (budgets, %, preuves — jamais faux), le **cerveau LLM** les
  traduit en langage naturel. Si le LLM est indisponible, l'état brut reste affiché.
  Le LLM réutilise un des agents disponibles (pas de 4ᵉ abonnement).
- **Relais d'ordres** vers le Commander (pause / stop / redirect / forcer le mode)
  avec confirmation humaine.
- **Aide à la vérification** : comprendre pourquoi un flag est `candidate` et pas
  encore `reproduced`, relire les preuves, décider de valider.

Architecture :
```
Humain (chat)
   → Supervisor Chat  --lit-->  Evidence Store + Mission status + Logs
   ← résumé langage naturel
   → relais d'ordres  -------->  Commander (avec confirmation)
```

Garde-fou : le chat **lit l'état réel, il ne l'invente jamais**. Toute action
modifiante passe par le Commander et respecte l'`autonomy_policy`.

---

## 8. Arsenal cible (image fat, par catégorie)

- **Pwn** : pwntools, GDB + pwndbg/GEF, one_gadget, ropper, ROPgadget, angr, QEMU.
- **Reverse** : Ghidra (headless scriptable), angr, Triton, Qiling.
- **Crypto** : SageMath, Z3, RsaCtfTool, fpylll.
- **Web** : ffuf/feroxbuster, sqlmap, Playwright, mitmproxy.
- **Forensic** : Volatility 3, binwalk, foremost, Sleuth Kit/Autopsy, exiftool, zsteg.
- **Réseau** : tshark, Scapy, Zeek.
- **Attack/Defense** : capture+replay de trafic (Scapy/tcpdump), bots de soumission
  de flags (flags A/D expirent vite), outils de patching auto des services défendus.
  → Périmètre = **range fourni par l'organisateur** (autorisé par définition).

Chaque outil a un **manifeste** : id, version, catégorie, prérequis, paramètres,
sorties attendues, timeout, permissions, limites ressources, méthode de vérification.

**Accélérateurs clés** : image fat + scripting *headless* (Ghidra/angr) +
wrappers à sortie structurée (Expert Tool Engine).

---

## 9. Attack/Defense (NOUVEAU — précision de périmètre)

Format de **compétition fermée** : tous les participants dans le même range.
- Outillage orienté rapidité : vol/replay d'exploits, soumission rapide, patching.
- Cibles = **uniquement** le range de la compétition (le périmètre autorisé par nature).
- Jamais de C2/red-team hors d'un lab explicitement possédé/autorisé, et toujours
  avec supervision humaine disponible.

---

## 10. Sécurité (principes maintenus)

- Uniquement des challenges/cibles **explicitement autorisés**.
- Isolation des exécutions, limitation ressources (CPU/RAM/disque/temps).
- Aucun privilège administrateur sur l'hôte pour les workers.
- Aucune exposition publique des interfaces de contrôle (tunnel SSH/VPN).
- Secrets hors du dépôt et hors des logs.
- Pause et arrêt d'urgence à tout moment.
- Fichiers de challenge, sorties d'outils et RAG = **données non fiables**,
  jamais exécutées comme des instructions prioritaires.

---

## 11. Stack technique (à valider au Sprint 0)

- Python 3.12+ / FastAPI / Pydantic / pytest / Ruff
- PostgreSQL (persistance), Redis (file de tâches si justifié)
- Docker + Docker Compose (isolation + déploiement)
- React / TypeScript (dashboard)
- CAO si audit concluant

Ne pas introduire de dépendance lourde sans besoin démontré.

---

## 12. Contrats de données minimaux

```
Challenge  : id, title, category, difficulty, description, source,
             attachments, authorization_scope, status, created_at
Mission    : id, challenge_id, agent_provider, specialist_profile, objective,
             allowed_tools, resource_budget, time_budget, workspace, status,
             result, autonomy_policy, tool_access_policy
Evidence   : id, challenge_id, mission_id, source, observation, artifact_path,
             checksum, verification_status, created_at
FlagCandidate : id, challenge_id, value, source_mission, validation_status,
                reproduction_reference, platform_feedback
```

Cycle de vie Mission :
```
CREATED → VALIDATED → QUEUED → RUNNING
RUNNING → WAITING_APPROVAL → RUNNING
RUNNING → PAUSED → RUNNING
RUNNING → COMPLETED / FAILED / CANCELLED / TIMED_OUT
```
Chaque transition : contrôlée, horodatée, traçable. Pas de duplication silencieuse
d'une action sensible lors d'une reprise.

---

## 13. Plan de développement (sprints)

- **Sprint 0** : audit environnement, CAO, CAI, CLI, licences. *(autorisé)*
- **Sprint 1** : dépôt, backend minimal (FastAPI), modèles, tests.
- **Sprint 2** : Local Solver + import de challenges.
- **Sprint 3** : intégration d'un premier CLI.
- **Sprint 4** : trois CLI + Commander minimal (règles) + `autonomy_policy`.
- **Sprint 5** : Expert Tool Engine + sandbox + **image fat**.
- **Sprint 6** : Evidence Store + Flag Verifier + rapports.
- **Sprint 7** : collaboration, débat, stagnation + **premiers playbooks**.
- **Sprint 8** : mémoire + RAG.
- **Sprint 9** : dashboard.
- **Sprint 10** : Local Executor + CTFd.
- **Sprint 11** : benchmarks, durcissement, déploiement.

---

## 14. Règles de livraison

- Un seul sprint actif. Pas d'anticipation des sprints futurs.
- Tests réels ou statut explicite "non testé". Jamais de résultat inventé.
- Mocks quand un CLI/service n'est pas disponible.
- Changements documentés et reproductibles.
- Aucune nouvelle dépendance majeure sans justification.
- Jamais de 4ᵉ worker LLM. Aucun code CAI sans vérification de licence.
- Validation humaine obligatoire entre chaque sprint.

---

## 15. Sprint actuellement autorisé

**SPRINT 0 UNIQUEMENT.** Aucun développement des modules FullCTF avant
validation du rapport d'audit et du plan de Sprint 1.
