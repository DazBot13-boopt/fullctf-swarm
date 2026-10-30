#!/usr/bin/env bash
# Build DURABLE de l'image arsenal, pensé pour survivre à une coupure de session.
#
# Usage recommandé (détaché, survit à la fermeture du terminal/session) :
#   tmux new-session -d -s arsenal 'bash scripts/build_arsenal.sh'
#   tmux attach -t arsenal          # pour suivre en direct (Ctrl-b d pour détacher)
#
# Ou simplement :
#   bash scripts/build_arsenal.sh   # en avant-plan
#
# Le log complet + un marqueur de fin sont écrits dans infrastructure/.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
LOG="$ROOT/infrastructure/arsenal_build.log"
DONE="$ROOT/infrastructure/arsenal_build.done"   # contient le code de sortie final
IMAGE="fullctf-arsenal:latest"

rm -f "$DONE"
{
  echo "=== Build arsenal démarré : $(date -Is) ==="

  # Prérequis réseau conteneur : sans ip_forward, apt/pip échouent dans le build.
  IPF="$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null || echo '?')"
  echo "net.ipv4.ip_forward = $IPF"
  if [ "$IPF" = "0" ]; then
    if sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1; then
      echo "ip_forward activé pour ce build."
    else
      echo "AVERTISSEMENT : ip_forward=0 et activation impossible (pas root ?)."
    fi
  fi

  echo "=== docker build -> $IMAGE ==="
  docker build -f infrastructure/Dockerfile.arsenal -t "$IMAGE" .
  rc=$?
  echo "=== docker build terminé (exit=$rc) : $(date -Is) ==="
  echo "$rc" > "$DONE"
  exit "$rc"
} >>"$LOG" 2>&1
