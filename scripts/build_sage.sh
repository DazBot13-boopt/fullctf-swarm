#!/usr/bin/env bash
# Build durable + AUTO-PROMOTE : SageMath par-dessus hard-CTF. Survit aux coupures.
# Si le build réussit ET que sage marche -> promeut fullctf-worker:latest tout seul.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
ROOT="$(pwd)"; LOG="$ROOT/infrastructure/sage_build.log"; DONE="$ROOT/infrastructure/sage_build.done"
rm -f "$DONE"
{
  echo "=== Build SageMath démarré : $(date -Is) ==="
  [ "$(cat /proc/sys/net/ipv4/ip_forward 2>/dev/null)" = "0" ] && sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1
  docker image inspect fullctf-worker:hardctf >/dev/null 2>&1 || { echo "ERREUR: :hardctf absente"; echo 255 > "$DONE"; exit 255; }
  docker build -f infrastructure/Dockerfile.sage -t fullctf-worker:sage .
  rc=$?
  if [ "$rc" = "0" ]; then
    if docker run --rm fullctf-worker:sage bash -c 'command -v sage >/dev/null && sage --version' >/dev/null 2>&1; then
      docker tag fullctf-worker:sage fullctf-worker:latest
      echo "AUTO-PROMOTE : fullctf-worker:latest = arsenal + SageMath ✅"
    else
      echo "SageMath non fonctionnel -> PAS de promote (on garde :latest = hard-CTF)"
    fi
  fi
  echo "=== Build SageMath terminé (exit=$rc) : $(date -Is) ==="
  echo "$rc" > "$DONE"
  exit "$rc"
} >>"$LOG" 2>&1
