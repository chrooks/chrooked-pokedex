#!/usr/bin/env bash
# Redeploy the dex service on hestia (dex.hestia.chrooks.com).
#
# What it does, in one SSH session: fast-forward the hestia clone to
# origin/main, rebuild the compose image (the Dockerfile builds the SPA
# in-stage), recreate the container, then prove health through the real
# front door from this machine.
#
# Scope guard: this script touches ONLY the chrooked-pokedex compose stack.
# Everything else on hestia stays hands-off (machine rule, ADR-0003).
#
# Prereqs: `ssh hestia` works with key auth (see ~/.ssh/config on the mac);
# changes must already be pushed to origin/main — the deploy pulls, it never
# pushes.
set -euo pipefail

CLONE=/home/chrooks/projects/chrooked-pokedex
HEALTH_URL=https://dex.hestia.chrooks.com/api/health
HEALTH_TRIES=12
HEALTH_WAIT_S=5

echo "==> hestia: pull + rebuild + recreate"
DEPLOYED=$(ssh -o BatchMode=yes hestia "
  set -euo pipefail
  cd $CLONE
  git pull --ff-only --quiet
  docker compose up -d --build --quiet-pull 2>&1 | tail -2
  git rev-parse --short HEAD
" | tail -1)

echo "==> health check: $HEALTH_URL"
for _ in $(seq "$HEALTH_TRIES"); do
  if curl -fsS --max-time 5 "$HEALTH_URL" > /dev/null; then
    # The deploy record the deploy-owed Stop hook reads (gitignored,
    # machine-local — same class as targets.json).
    echo "$DEPLOYED" > "$(dirname "$0")/../.deployed-commit"
    echo "deployed $DEPLOYED — healthy"
    exit 0
  fi
  sleep "$HEALTH_WAIT_S"
done

echo "deploy finished but $HEALTH_URL never came healthy — check 'ssh hestia docker logs chrooked-pokedex'" >&2
exit 1
