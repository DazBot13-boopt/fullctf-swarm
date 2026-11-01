#!/usr/bin/env bash
# Build durable de l'arsenal hard-CTF v2 (tag :hardctf). Survit aux coupures.
#   tmux new-session -d -s hardctf 'bash scripts/build_hardctf.sh'
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"
LOG="$ROOT/infrastructure/hardctf_build.log"
DONE="$ROOT/infrastructure/hardctf_build.done"
rm -f "$DONE"
{
  echo "=== Build hard-CTF démarré : $(date -Is) ==="
  [ "$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null)" = "0" ] && sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1
  docker image inspect fullctf-worker:latest >/dev/null 2>&1 || { echo "ERREUR: fullctf-worker:latest absente"; echo 255 > "$DONE"; exit 255; }
  docker build -f infrastructure/Dockerfile.hardctf -t fullctf-worker:hardctf .
  rc=$?
  echo "=== Build hard-CTF terminé (exit=$rc) : $(date -Is) ==="
  echo "$rc" > "$DONE"
  exit "$rc"
} >>"$LOG" 2>&1
