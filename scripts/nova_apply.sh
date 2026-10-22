#!/usr/bin/env bash
# nova_apply.sh — project the Ruleset into Pokémon Nova and ship it to the places
# it is played: the PC's live copy (Sunshine stream) and thor (Kirin).
#
# Runs on the Windows PC in WSL. Nova is an Essentials 21.99 game that ships only
# compiled Data/*.dat, so the loop has a compile step Rejuvenation never needed:
#
#   1. git pull                     — the Ruleset (incl. ruleset/targets/nova/) is canon in git
#   2. lab scripts → LAB            — references/essentials21-harness/lab/*.rb into the lab's
#                                     Data/Scripts/998_ChrookedDexLab/ (save redirect, self-test)
#   3. apply  → LAB copy            — the dex writes PBS text (essentials engine, v21 dialect)
#                                     and installs ported mechanics in Data/Scripts/998_ChrookedMods/
#   4. compile in the LAB copy      — Game.exe in debug mode rebuilds Data/*.dat from PBS
#   5. deploy                       — changed Data/*.dat, and the chrooked_*.rb files of
#                                     998_ChrookedMods/, to the LIVE PC copy and to thor over SSH
#
# Only the LAB copy ever runs in debug mode or carries lab-only scripts; the live
# copies receive the .dat files and the ported mechanics in 998_ChrookedMods/, which
# the dex owns and mirrors (a retired port is removed there too). Nothing else under
# Data/Scripts/ travels, so thor keeps its own 998_ChrookedKirin controls shim.
# Ported mechanics write their oracle log only while chrooked-oracle.on exists in a
# game folder, so the live copies stay silent unless a proof run sets it.
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

say "lab scripts → ${NOVA_LAB} (lab only, never deployed)"
LAB_SCRIPTS_DST="${NOVA_LAB}/Data/Scripts/998_ChrookedDexLab"
mkdir -p "${LAB_SCRIPTS_DST}"
LAB_SYNCED=0
for src in "${REPO_ROOT}/references/essentials21-harness/lab/"*.rb; do
  if ! cmp -s "${src}" "${LAB_SCRIPTS_DST}/$(basename "${src}")"; then
    cp "${src}" "${LAB_SCRIPTS_DST}/"; echo "  $(basename "${src}")"; LAB_SYNCED=1
  fi
done
[ ${LAB_SYNCED} -eq 1 ] || echo "  already current"

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

# Ported mechanics: mirror the chrooked_*.rb files of the dex-owned 998_ChrookedMods/
# folder. Only that folder, only those files — 998_ChrookedKirin and every other
# script folder on the live copies is never touched.
MODS_REL="Data/Scripts/998_ChrookedMods"
LAB_MODS="${NOVA_LAB}/${MODS_REL}"
PORTS=()
if [ -d "${LAB_MODS}" ]; then
  while IFS= read -r f; do PORTS+=("$f"); done < <(cd "${LAB_MODS}" && find . -maxdepth 1 -name 'chrooked_*.rb' -printf '%f\n' | sort)
fi

say "deploy ${MODS_REL}/chrooked_*.rb → live PC copy"
LIVE_MODS="${NOVA_LIVE}/${MODS_REL}"
MODS_CHANGED=0
[ ${#PORTS[@]} -eq 0 ] || mkdir -p "${LIVE_MODS}"
for f in "${PORTS[@]}"; do
  if ! cmp -s "${LAB_MODS}/${f}" "${LIVE_MODS}/${f}"; then
    cp -p "${LAB_MODS}/${f}" "${LIVE_MODS}/${f}"; echo "  ${f}"; MODS_CHANGED=1
  fi
done
if [ -d "${LIVE_MODS}" ]; then
  for path in "${LIVE_MODS}"/chrooked_*.rb; do
    [ -e "${path}" ] || continue
    f="$(basename "${path}")"
    [ -f "${LAB_MODS}/${f}" ] || { rm -f "${path}"; echo "  removed ${f}"; MODS_CHANGED=1; }
  done
fi
[ ${MODS_CHANGED} -eq 1 ] || echo "  nothing changed — live copy already current"

say "deploy ${MODS_REL}/chrooked_*.rb → thor (${NOVA_THOR_HOST})"
THOR_MODS="${NOVA_THOR_GAME}/${MODS_REL}"
if [ ${#PORTS[@]} -gt 0 ]; then
  (cd "${LAB_MODS}" && tar -cf - "${PORTS[@]}") | "${WIN_SSH}" -o BatchMode=yes -p "${NOVA_THOR_PORT}" "${NOVA_THOR_USER}@${NOVA_THOR_HOST}" \
    "mkdir -p \"${THOR_MODS}\" && cd \"${THOR_MODS}\" && rm -f chrooked_*.rb && tar -xf - && md5sum chrooked_*.rb | cut -c1-8,33-"
  echo "  (lab)"; (cd "${LAB_MODS}" && md5sum "${PORTS[@]}" | cut -c1-8,33-)
else
  "${WIN_SSH}" -o BatchMode=yes -p "${NOVA_THOR_PORT}" "${NOVA_THOR_USER}@${NOVA_THOR_HOST}" "rm -f \"${THOR_MODS}\"/chrooked_*.rb"
  echo "  no ported mechanics in the lab — any on thor removed"
fi

say "done — relaunch the game (Kirin: kill + relaunch; stream: quit + relaunch) to load the new data"
