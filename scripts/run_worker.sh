#!/usr/bin/env bash
# Lance un worker DANS un conteneur jetable fullctf-worker (conforme à la spec :
# liberté totale DANS le conteneur, l'hôte n'est jamais modifié).
#
#   bash scripts/run_worker.sh <agent> <challenge_dir> <prompt_file>
#     <agent>         : codex | claude | cursor
#     <challenge_dir> : dossier contenant files/ (monté en LECTURE SEULE)
#     <prompt_file>   : fichier texte de la mission (cadrage anti-injection)
#
# L'auth est montée EN LIVE depuis l'hôte (le compte actif du serveur est utilisé).
# Les fichiers du challenge sont montés en :ro (originaux immuables). Le worker
# travaille dans /work (couche éphémère du conteneur, jetée à la fin via --rm).
set -uo pipefail

AGENT="${1:?agent requis: codex|claude|cursor}"
CHALL="${2:?dossier challenge requis}"
PROMPT_FILE="${3:?fichier prompt requis}"

[ -d "$CHALL/files" ] || { echo "ERREUR: $CHALL/files introuvable"; exit 1; }
[ -f "$PROMPT_FILE" ] || { echo "ERREUR: $PROMPT_FILE introuvable"; exit 1; }
PROMPT="$(cat "$PROMPT_FILE")"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_MD="$SCRIPT_DIR/../infrastructure/ctf_agents.md"   # cadrage CTF (lu par codex/cursor)
# Codex : le modèle "sol" refuse l'offensif ; "terra" l'accepte -> défaut terra.
CODEX_MODEL="${CODEX_MODEL:-gpt-5.6-terra}"

case "$AGENT" in
  codex)  CMD=(codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox -m "$CODEX_MODEL" "$PROMPT") ;;
  claude) CMD=(claude -p --dangerously-skip-permissions "$PROMPT") ;;
  cursor) CMD=(cursor-agent -p --output-format text --force "$PROMPT") ;;
  *) echo "agent inconnu: $AGENT (codex|claude|cursor)"; exit 1 ;;
esac

# Montages d'auth (seulement ceux qui existent sur l'hôte)
AUTH=()
[ -f "$HOME/.codex/auth.json" ]              && AUTH+=( -v "$HOME/.codex/auth.json:/root/.codex/auth.json:ro" )
[ -f "$HOME/.claude/.credentials.json" ]     && AUTH+=( -v "$HOME/.claude/.credentials.json:/root/.claude/.credentials.json:ro" )
[ -f "$HOME/.config/cursor/auth.json" ]      && AUTH+=( -v "$HOME/.config/cursor/auth.json:/root/.config/cursor/auth.json:ro" )

# Cursor s'authentifie via CURSOR_API_KEY (son token n'est pas dans un fichier
# montable : keyring/store lié à la machine). On passe la clé si elle est dans
# l'env de l'hôte. Génère-la dans Cursor puis : export CURSOR_API_KEY=...
CURSOR_ENV=()
[ -n "${CURSOR_API_KEY:-}" ] && CURSOR_ENV=( -e "CURSOR_API_KEY=${CURSOR_API_KEY}" )

exec docker run --rm \
  --cap-add=NET_RAW --cap-add=NET_ADMIN \
  -e IS_SANDBOX=1 \
  "${CURSOR_ENV[@]}" \
  "${AUTH[@]}" \
  -v "$(realpath "$CHALL")/files:/work/files:ro" \
  $( [ -f "$AGENTS_MD" ] && echo -v "$(realpath "$AGENTS_MD")":/work/AGENTS.md:ro ) \
  fullctf-worker:latest \
  "${CMD[@]}"
