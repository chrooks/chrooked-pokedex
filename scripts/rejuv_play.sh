#!/usr/bin/env bash
# rejuv_play.sh — one-command "play Rejuvenation with my latest Ruleset".
#
# Runs on both machines (macOS and the Windows PC via WSL). Always launch the
# game through this instead of double-clicking, and the three save-sync hazards
# stop being things you have to remember:
#
#   1. Stale patch/ under a newer save -> we `git pull` + `apply` before launch.
#   2. Playing on both machines at once -> a lock file inside the SYNCED save
#      folder; the other machine refuses to launch while it's held.
#   3. Losing a save to a bad overwrite  -> not this script's job. Turn on
#      Staggered File Versioning on the save folder in Syncthing.
#
# The lock is a forgetfulness guardrail, not a real mutex: launch both machines
# inside Syncthing's propagation window (a few seconds) and both can take it.
# Upgrade path if that ever actually bites: a real lease with timestamps, or
# just don't sync saves. A crash leaves the lock behind -- use --force-unlock.
#
# Usage: scripts/rejuv_play.sh [--no-apply] [--no-pull] [--force-unlock] [--apply-only]
#
# Config (override per machine; sane defaults below):
#   REJUV_SAVES   save folder (the one Syncthing shares)
#   REJUV_GAME    game data dir — overrides the targets.json lookup

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGETS_JSON="${REPO_ROOT}/targets.json"

PULL=true
APPLY=true
LAUNCH=true
FORCE_UNLOCK=false
for arg in "$@"; do
  case "$arg" in
    --no-pull)      PULL=false ;;
    --no-apply)     APPLY=false ;;
    --apply-only)   LAUNCH=false ;;
    --force-unlock) FORCE_UNLOCK=true ;;
    -h|--help)      grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

# --- platform ---------------------------------------------------------------
case "$(uname -s)" in
  Darwin) PLATFORM=mac ;;
  Linux)  grep -qi microsoft /proc/version 2>/dev/null && PLATFORM=wsl || PLATFORM=linux ;;
  *)      echo "ERROR: unsupported platform: $(uname -s)" >&2; exit 1 ;;
esac

# --- where the game lives ---------------------------------------------------
if [[ -z "${REJUV_GAME:-}" ]]; then
  [[ -f "${TARGETS_JSON}" ]] || {
    echo "ERROR: targets.json not found at ${TARGETS_JSON} (gitignored, per-machine)." >&2
    echo 'Add a rejuv target, or set REJUV_GAME=/path/to/game/dir' >&2
    exit 1
  }
  REJUV_GAME="$(TARGETS_JSON_PATH="${TARGETS_JSON}" python3 - <<'PYEOF'
import json, os, sys
targets = json.load(open(os.environ["TARGETS_JSON_PATH"]))
pick = next((t for t in targets if t.get("engine") == "rejuv"), None)
if not pick:
    print("ERROR: no rejuv target in targets.json", file=sys.stderr); sys.exit(1)
print(pick["path"])
PYEOF
)"
fi
[[ -d "${REJUV_GAME}" ]] || { echo "ERROR: game dir does not exist: ${REJUV_GAME}" >&2; exit 1; }

# --- where the saves live ---------------------------------------------------
if [[ -z "${REJUV_SAVES:-}" ]]; then
  case "${PLATFORM}" in
    mac) REJUV_SAVES="${HOME}/Library/Application Support/Rejuv" ;;
    # %USERPROFILE%, not %USERNAME% — the login name and the profile FOLDER name
    # differ on this box (Chris vs cdbro), and it's the folder we need.
    wsl) REJUV_SAVES="$(wslpath "$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r\n')")/Saved Games/Rejuv" ;;
    *)   echo "ERROR: set REJUV_SAVES for this platform." >&2; exit 1 ;;
  esac
fi
[[ -d "${REJUV_SAVES}" ]] || {
  echo "ERROR: save folder not found: ${REJUV_SAVES}" >&2
  echo "Launch the game once and save, then set REJUV_SAVES to wherever it wrote." >&2
  exit 1
}

echo "Game:  ${REJUV_GAME}"
echo "Saves: ${REJUV_SAVES}"

# --- guardrail 2: cross-machine play lock -----------------------------------
LOCK="${REJUV_SAVES}/.rejuv-playing"
ME="$(hostname)"

if [[ -f "${LOCK}" ]]; then
  HOLDER="$(cat "${LOCK}" 2>/dev/null || echo unknown)"
  if [[ "${HOLDER}" == "${ME}" ]]; then
    echo "NOTE: stale lock from this machine (${ME}) — previous run crashed. Reclaiming."
  elif [[ "${FORCE_UNLOCK}" == "true" ]]; then
    echo "WARNING: overriding lock held by '${HOLDER}'."
    echo "         If that machine is ACTUALLY playing, you will lose one side's progress."
  else
    echo "" >&2
    echo "BLOCKED: '${HOLDER}' holds the play lock." >&2
    echo "" >&2
    echo "Close Rejuvenation there and let Syncthing settle, then retry." >&2
    echo "If it crashed / is powered off, override with: $0 --force-unlock" >&2
    exit 1
  fi
fi

# --- guardrail 1: latest Ruleset before we touch a save ---------------------
cd "${REPO_ROOT}"
if [[ "${PULL}" == "true" ]]; then
  echo ""; echo "==> git pull ..."
  git pull --ff-only
fi

if [[ "${APPLY}" == "true" ]]; then
  echo ""; echo "==> Applying Ruleset (engine=rejuv) ..."
  if command -v uv &>/dev/null; then
    uv run chrooked-pokedex apply --engine rejuv --target "${REJUV_GAME}"
  else
    chrooked-pokedex apply --engine rejuv --target "${REJUV_GAME}"
  fi
  echo "Apply complete. Report: ${REJUV_GAME}/apply-report.md"
fi

[[ "${LAUNCH}" == "true" ]] || exit 0

# --- launch, holding the lock for the session -------------------------------
echo "${ME}" > "${LOCK}"
trap 'rm -f "${LOCK}"; echo "Lock released."' EXIT INT TERM

echo ""; echo "==> Launching Rejuvenation (lock held by ${ME}) ..."
case "${PLATFORM}" in
  mac)
    # REJUV_GAME is .../Rejuvenation.app/Contents/Game — walk up to the bundle.
    APP="$(cd "${REJUV_GAME}/../.." && pwd)"
    open -W "${APP}"   # -W: block until the game quits, so the lock outlives it
    ;;
  wsl)
    # WSL interop runs the .exe directly; cwd must be the game dir.
    ( cd "${REJUV_GAME}" && ./Rejuvenation.exe )
    ;;
esac
