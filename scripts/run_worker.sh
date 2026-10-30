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

case "$AGENT" in
  codex)  CMD=(codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox "$PROMPT") ;;
  claude) CMD=(claude -p --dangerously-skip-permissions "$PROMPT") ;;
  cursor) CMD=(cursor-agent -p --output-format text --force "$PROMPT") ;;
  *) echo "agent inconnu: $AGENT (codex|claude|cursor)"; exit 1 ;;
esac

# Montages d'auth (seulement ceux qui existent sur l'hôte)
AUTH=()
[ -f "$HOME/.codex/auth.json" ]              && AUTH+=( -v "$HOME/.codex/auth.json:/root/.codex/auth.json:ro" )
[ -f "$HOME/.claude/.credentials.json" ]     && AUTH+=( -v "$HOME/.claude/.credentials.json:/root/.claude/.credentials.json:ro" )
[ -f "$HOME/.config/cursor-agent/auth.json" ] && AUTH+=( -v "$HOME/.config/cursor-agent/auth.json:/root/.config/cursor-agent/auth.json:ro" )

exec docker run --rm \
  --cap-add=NET_RAW --cap-add=NET_ADMIN \
  -e IS_SANDBOX=1 \
  "${AUTH[@]}" \
  -v "$(realpath "$CHALL")/files:/work/files:ro" \
  fullctf-worker:latest \
  "${CMD[@]}"
