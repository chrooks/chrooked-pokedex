#!/usr/bin/env bash
# nova_apply.sh — project the Ruleset into Pokémon Nova and ship it to the places
# it is played: the PC's live copy (Sunshine stream) and thor (Kirin).
#
# Runs on the Windows PC in WSL. Nova is an Essentials 21.99 game that ships only
# compiled Data/*.dat, so the loop has a compile step Rejuvenation never needed:
#
#   1. git pull                     — the Ruleset (incl. ruleset/targets/nova/) is canon in git
#   2. apply  → LAB copy's PBS/     — the dex writes PBS text (essentials engine, v21 dialect)
#   3. compile in the LAB copy      — Game.exe in debug mode rebuilds Data/*.dat from PBS
#   4. deploy changed Data/*.dat    — to the LIVE PC copy and to thor over SSH
#
# Only the LAB copy ever runs in debug mode or carries lab-only scripts; the live
# copies receive nothing but .dat files. thor keeps its own Data/Scripts/998_ChrookedKirin
# controls shim untouched because only .dat files travel.
#
# Usage: scripts/nova_apply.sh [--no-pull] [--no-deploy] [--create-species]
#
# Config (defaults match mjolnir runbook 30):
#   NOVA_LAB   /mnt/d/Games/Pokemon FanGames/NovaV3.0-dexlab/Nova
#   NOVA_LIVE  /mnt/d/Games/Pokemon FanGames/NovaV3.0/Nova
#   NOVA_THOR  u0_a132@192.168.1.121 (port 8022), game at /storage/emulated/0/Pokemon Nova
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NOVA_LAB="${NOVA_LAB:-/mnt/d/Games/Pokemon FanGames/NovaV3.0-dexlab/Nova}"
NOVA_LIVE="${NOVA_LIVE:-/mnt/d/Games/Pokemon FanGames/NovaV3.0/Nova}"
NOVA_THOR_USER="${NOVA_THOR_USER:-u0_a132}"
NOVA_THOR_HOST="${NOVA_THOR_HOST:-192.168.1.121}"
NOVA_THOR_PORT="${NOVA_THOR_PORT:-8022}"
NOVA_THOR_GAME="${NOVA_THOR_GAME:-/storage/emulated/0/Pokemon Nova}"
# Windows' own OpenSSH: this PC's key has a passphrase that only the Windows
# ssh-agent holds (mjolnir runbook 21). Git Bash / WSL ssh cannot sign with it.
WIN_SSH="${WIN_SSH:-/mnt/c/Windows/System32/OpenSSH/ssh.exe}"
POWERSHELL="${POWERSHELL:-/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe}"
DAT_FILES=(abilities moves species types messages_game items berry_plants trainer_types trainers
           trainer_lists encounters phone ribbons regional_dexes species_metrics map_metadata
           metadata player_metadata town_map map_connections dungeon_parameters dungeon_tilesets)

PULL=true; DEPLOY=true; CREATE_SPECIES=false
for arg in "$@"; do
  case "$arg" in
    --no-pull) PULL=false ;;
    --no-deploy) DEPLOY=false ;;
    --create-species) CREATE_SPECIES=true ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

STAMP="$(date +%F)"
say() { printf '\n== %s\n' "$*"; }

[ -f "${NOVA_LAB}/Game.exe" ] || { echo "lab copy not found at ${NOVA_LAB}" >&2; exit 1; }
[ -d "${NOVA_LAB}/PBS" ] || { echo "lab copy has no PBS/ — run Game.exe once in debug mode to write it (runbook 30)" >&2; exit 1; }
grep -q '"debugMode": true' "${NOVA_LAB}/mkxp.json" || { echo "lab mkxp.json lacks \"debugMode\": true — refusing: the compile step needs it" >&2; exit 1; }
if grep -q '"debugMode": true' "${NOVA_LIVE}/mkxp.json" 2>/dev/null; then
  echo "LIVE copy has debugMode on — that is the lab's setting; fix before continuing" >&2; exit 1
fi

if $PULL; then
  say "git pull (Ruleset)"
  git -C "${REPO_ROOT}" pull --ff-only
fi

say "apply → ${NOVA_LAB}"
APPLY_ARGS=(--target "${NOVA_LAB}" --engine essentials --no-sync)
$CREATE_SPECIES || APPLY_ARGS+=(--no-create-species)
(cd "${REPO_ROOT}" && uv run chrooked-pokedex apply "${APPLY_ARGS[@]}") | grep -vE '^\s+ability [a-z]+ \([A-Z]+\)$'

say "compile (debug-mode Game.exe in the lab copy)"
"${POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w "${SCRIPT_DIR}/nova_compile.ps1")"

$DEPLOY || { say "deploy skipped (--no-deploy)"; exit 0; }

say "deploy changed Data/*.dat → live PC copy"
mkdir -p "${NOVA_LIVE}/Data.pre-apply-${STAMP}"
CHANGED=()
for f in "${DAT_FILES[@]}"; do
  src="${NOVA_LAB}/Data/${f}.dat"; dst="${NOVA_LIVE}/Data/${f}.dat"
  [ -f "$src" ] || continue
  if ! cmp -s "$src" "$dst"; then
    cp -p "$dst" "${NOVA_LIVE}/Data.pre-apply-${STAMP}/" 2>/dev/null || true
    cp -p "$src" "$dst"; CHANGED+=("${f}.dat"); echo "  ${f}.dat"
  fi
done
[ ${#CHANGED[@]} -gt 0 ] || { echo "  nothing changed — live copy already current"; }

say "deploy changed Data/*.dat → thor (${NOVA_THOR_HOST})"
if [ ${#CHANGED[@]} -gt 0 ]; then
  (cd "${NOVA_LAB}/Data" && tar -cf - "${CHANGED[@]}") | "${WIN_SSH}" -o BatchMode=yes -p "${NOVA_THOR_PORT}" "${NOVA_THOR_USER}@${NOVA_THOR_HOST}" \
    "mkdir -p \"${NOVA_THOR_GAME}/Data.pre-apply-${STAMP}\" && cd \"${NOVA_THOR_GAME}/Data\" && for f in ${CHANGED[*]}; do cp -p \"\$f\" \"../Data.pre-apply-${STAMP}/\" 2>/dev/null || true; done && tar -xf - && md5sum ${CHANGED[*]} | cut -c1-8,33-"
  echo "  (lab)"; (cd "${NOVA_LAB}/Data" && md5sum "${CHANGED[@]}" | cut -c1-8,33-)
else
  echo "  nothing to send"
fi

say "done — relaunch the game (Kirin: kill + relaunch; stream: quit + relaunch) to load the new data"
