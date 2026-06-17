#!/usr/bin/env bash
# africanvs_devloop.sh — one-command Africanvs dev loop (macOS / Apple Silicon).
#
#   1. Resolve the Essentials Target from targets.json (label ~= "africanvs").
#   2. Apply the Ruleset to that Target (engine auto-detects the 16.2 dialect).
#   3. Launch the game in Wine DEBUG via `open` on the copy's .command launcher.
#
# Why `open` and not `wine Game.exe debug` directly: launching from an interactive
# terminal leaves the Wine window without keyboard focus, AND `debug` spawns an
# mkxp-z console window that steals focus. The copy's `Play Copy (Wine Debug).command`
# sets MKXPZ_WINDOWS_CONSOLE=0 and, opened via LaunchServices (like a Finder
# double-click), boots in a fresh Terminal where the game gets keyboard focus.
#
# IMPORTANT: this game runs under **Wine Game.exe** (bundled Ruby 1.8, which the
# Essentials 16.2 scripts need). The native Z-universal binary uses modern Ruby and
# crashes on the 16.2 scripts — do NOT use it. See docs/africanvs-dev-loop.md.
#
# Usage: scripts/africanvs_devloop.sh [--apply-only] [--no-apply]
#   --apply-only   Run the applier only; do not launch.
#   --no-apply     Launch only; skip the applier.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGETS_JSON="${REPO_ROOT}/targets.json"

APPLY=true
LAUNCH=true
for arg in "$@"; do
  case "$arg" in
    --apply-only) LAUNCH=false ;;
    --no-apply)   APPLY=false ;;
    -h|--help)    grep '^#' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
done

if [[ ! -f "${TARGETS_JSON}" ]]; then
  echo "ERROR: targets.json not found at ${TARGETS_JSON} (it is gitignored)." >&2
  echo 'Add: [{"engine":"essentials","label":"Africanvs","path":"/path/to/copy","id":"..."}]' >&2
  exit 1
fi

GAME_PATH="$(TARGETS_JSON_PATH="${TARGETS_JSON}" python3 - <<'PYEOF'
import json, os, sys
targets = json.load(open(os.environ["TARGETS_JSON_PATH"]))
pick = next((t for t in targets if t.get("engine") == "essentials" and "africanvs" in t.get("label","").lower()), None) \
    or next((t for t in targets if t.get("engine") == "essentials"), None)
if not pick:
    print("ERROR: no essentials target in targets.json", file=sys.stderr); sys.exit(1)
print(pick["path"])
PYEOF
)"
echo "Target: ${GAME_PATH}"
[[ -d "${GAME_PATH}" ]] || { echo "ERROR: target path does not exist: ${GAME_PATH}" >&2; exit 1; }

if [[ "${APPLY}" == "true" ]]; then
  echo ""; echo "==> Applying Ruleset (engine=essentials, dialect auto-detected) ..."
  cd "${REPO_ROOT}"
  if command -v uv &>/dev/null; then
    uv run chrooked-pokedex apply --engine essentials --target "${GAME_PATH}"
  else
    chrooked-pokedex apply --engine essentials --target "${GAME_PATH}"
  fi
  echo "Apply complete. Report: ${GAME_PATH}/apply-report.md"
fi

if [[ "${LAUNCH}" == "true" ]]; then
  LAUNCHER="${GAME_PATH}/Play Copy (Wine Debug).command"
  if [[ ! -f "${LAUNCHER}" ]]; then
    echo "ERROR: launcher not found: ${LAUNCHER}" >&2
    echo "Create the copy's Finder launchers (see docs/africanvs-dev-loop.md)." >&2
    exit 1
  fi
  echo ""; echo "==> Launching (Wine debug, keyboard-safe) via: ${LAUNCHER}"
  open "${LAUNCHER}"
fi
