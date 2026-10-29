#!/usr/bin/env bash
#
# sprint0_audit.sh — Audit Sprint 0 (Phase A), LECTURE SEULE.
#
# Inspecte l'environnement du VPS pour FullCTF Swarm SANS rien installer,
# sans sudo, sans démarrer de service, sans lire de secret.
#
# Usage :
#   bash scripts/sprint0_audit.sh                 # affiche le rapport
#   bash scripts/sprint0_audit.sh > audit.txt     # sauvegarde le rapport
#
set -u

# --- helpers --------------------------------------------------------------

line() { printf '%s\n' "------------------------------------------------------------"; }

# Affiche la version d'un outil s'il est présent, sinon MANQUANT.
check() {
  local name="$1"; shift
  if command -v "$name" >/dev/null 2>&1; then
    local ver
    ver="$("$@" 2>&1 | head -n 1)"
    printf '  [OK]      %-16s %s\n' "$name" "$ver"
  else
    printf '  [MANQUANT] %-15s (non trouvé dans le PATH)\n' "$name"
  fi
}

header() { line; printf '%s\n' "$1"; line; }

# --- 0. Contexte ----------------------------------------------------------

header "FullCTF Swarm — Audit Sprint 0 (Phase A, lecture seule)"
printf 'Date      : %s\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
printf 'Utilisateur: %s\n' "$(whoami)"
printf 'Répertoire : %s\n' "$(pwd)"
if [ "$(id -u)" = "0" ]; then
  printf 'ATTENTION : exécuté en root. Préférer un compte dédié non-root.\n'
fi
echo

# --- 1. Système -----------------------------------------------------------

header "1. Système"
if [ -r /etc/os-release ]; then
  . /etc/os-release
  printf '  OS        : %s\n' "${PRETTY_NAME:-inconnu}"
fi
printf '  Noyau     : %s\n' "$(uname -sr)"
printf '  Arch      : %s\n' "$(uname -m)"
printf '  CPU       : %s vCPU\n' "$(nproc 2>/dev/null || echo '?')"
if command -v free >/dev/null 2>&1; then
  printf '  RAM       : %s\n' "$(free -h | awk '/^Mem:/{print $2" total, "$7" dispo"}')"
fi
printf '  Disque /  : %s\n' "$(df -h / | awk 'NR==2{print $2" total, "$4" dispo"}')"
echo

# --- 2. Dépendances de base ----------------------------------------------

header "2. Dépendances système"
check git        git --version
check python3    python3 --version
check pip3       pip3 --version
check uv         uv --version
check node       node --version
check npm        npm --version
check tmux       tmux -V
echo

# --- 3. Docker ------------------------------------------------------------

header "3. Docker (sans l'utiliser)"
check docker     docker --version
if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    printf '  [OK]      docker compose  %s\n' "$(docker compose version | head -n1)"
  elif command -v docker-compose >/dev/null 2>&1; then
    printf '  [OK]      docker-compose  %s\n' "$(docker-compose --version | head -n1)"
  else
    printf '  [MANQUANT] docker compose (plugin v2 recommandé)\n'
  fi
  # Accès au démon (sans lancer de conteneur).
  if docker info >/dev/null 2>&1; then
    printf '  [OK]      accès au démon Docker\n'
  else
    printf '  [INFO]    pas d accès au démon (droits/groupe docker ?)\n'
  fi
fi
echo

# --- 4. Les trois CLI agents ---------------------------------------------

header "4. Agents CLI (présence + version uniquement, pas de secret)"
check codex         codex --version
check claude        claude --version
check cursor-agent  cursor-agent --version
echo
printf '  Note : la présence ne garantit PAS le fonctionnement non-interactif.\n'
printf '         Le test réel (mode auto, headless) se fait en Phase D, après ton accord.\n'
echo

# --- 5. Synthèse ----------------------------------------------------------

header "5. Prochaines actions (Phase B/C/D — nécessitent ton accord)"
cat <<'EOF'
  - Installer ce qui est marqué [MANQUANT] (git, python3, docker, tmux...).
  - Phase B : auditer CAO (dépôt, licence Apache 2.0, API).
  - Phase C : auditer CAI (architecture + licences, sans exécuter son code).
  - Phase D : tester chaque CLI en mode non-interactif sur une tâche inoffensive,
              puis ajuster les commandes dans backend/fullctf/agents/providers.py.

  Ce script n'a RIEN installé ni modifié. Décision humaine requise pour la suite.
EOF
line
