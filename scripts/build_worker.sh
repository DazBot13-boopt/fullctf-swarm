#!/usr/bin/env bash
# Build DURABLE de l'image worker (arsenal + 3 CLI), survit à une coupure de session.
#
#   tmux new-session -d -s worker 'bash scripts/build_worker.sh'
#   tmux attach -t worker        # suivre (Ctrl-b d pour détacher)
#   cat infrastructure/worker_build.done   # code de sortie à la fin
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
LOG="$ROOT/infrastructure/worker_build.log"
DONE="$ROOT/infrastructure/worker_build.done"
IMAGE="fullctf-worker:latest"
rm -f "$DONE"
{
  echo "=== Build worker démarré : $(date -Is) ==="
  IPF="$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null || echo '?')"
  echo "net.ipv4.ip_forward = $IPF"
  [ "$IPF" = "0" ] && sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 && echo "ip_forward activé"
  # prérequis : l'image arsenal doit exister
  if ! docker image inspect fullctf-arsenal:latest >/dev/null 2>&1; then
    echo "ERREUR : fullctf-arsenal:latest manquante. Build l'arsenal d'abord."
    echo "255" > "$DONE"; exit 255
  fi
  echo "=== docker build -> $IMAGE ==="
  docker build -f infrastructure/Dockerfile.worker -t "$IMAGE" .
  rc=$?
  echo "=== docker build terminé (exit=$rc) : $(date -Is) ==="
  echo "$rc" > "$DONE"
  exit "$rc"
} >>"$LOG" 2>&1
