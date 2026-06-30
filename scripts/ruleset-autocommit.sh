#!/bin/sh
# Auto-commit + push ruleset/ edits made on the always-on editor box (hestia).
# Polls for changes instead of hooking the web app — so it also catches hand
# edits and harvest, and never slows down an HTTP save.
#
# ponytail: poll loop, not inotify. Batches whatever changed in one INTERVAL into
# one commit (so the message is generic, not per-logical-change). Upgrade to a
# watchfiles/inotify watcher only if sub-minute sync ever matters — for an
# edit-here / apply-on-the-gaming-PC-later flow, it doesn't.
#
# Setup on hestia (one time):
#   - git identity:  git config user.name / user.email
#   - push auth:     an SSH deploy key with write access (remote is git@github.com)
#   - run it:        scripts/ruleset-autocommit.sh   (or as a compose sidecar)
set -eu

cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"

INTERVAL="${RULESET_AUTOCOMMIT_INTERVAL:-120}"

while true; do
  # --porcelain is empty when nothing under ruleset/ changed.
  if [ -n "$(git status --porcelain -- ruleset/)" ]; then
    git add -- ruleset/
    git commit -q -m "chore(ruleset): auto-commit editor changes"
    git push -q
    echo "[ruleset-autocommit] pushed at $(date -u +%FT%TZ)"
  fi
  sleep "$INTERVAL"
done
