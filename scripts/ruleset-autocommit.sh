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
# Commit only after ruleset/ has been unchanged for this long. An agent session
# on this box edits, applies, reads back, then makes its own scoped commit
# within a few minutes; the quiet window lets that commit win instead of the
# poll grabbing half the change under a generic message.
QUIET="${RULESET_AUTOCOMMIT_QUIET:-900}"

last_state=""
quiet_since=0

while true; do
  # --porcelain is empty when nothing under ruleset/ changed.
  state="$(git status --porcelain -- ruleset/)"
  now="$(date +%s)"
  if [ "$state" != "$last_state" ]; then
    last_state="$state"
    quiet_since="$now"
  fi
  if [ -n "$state" ] && [ $((now - quiet_since)) -ge "$QUIET" ]; then
    git add -- ruleset/
    git commit -q -m "chore(ruleset): auto-commit editor changes"
    git push -q
    echo "[ruleset-autocommit] pushed at $(date -u +%FT%TZ)"
    last_state=""
  fi
  # Couch loop v2 (mjolnir CL-2): also pull each cycle so Mac-side pushes reach
  # this clone unattended. Rebase keeps a not-yet-pushed autocommit ahead of
  # upstream; a real conflict stops this cycle loudly (set -eu) and shows in
  # journalctl -u ruleset-autocommit — the correct failure mode.
  git pull --rebase -q || {
    echo "[ruleset-autocommit] pull failed at $(date -u +%FT%TZ)"
    git rebase --abort 2>/dev/null || true   # never leave the clone mid-rebase
  }
  sleep "$INTERVAL"
done
