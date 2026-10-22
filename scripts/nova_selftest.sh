#!/usr/bin/env bash
# nova_selftest.sh — prove a ported mechanic in Pokémon Nova's LAB copy with no one playing.
#
# Runs on the Windows PC in WSL, against the debug-mode lab copy only (mjolnir
# runbook 30). Four steps:
#
#   1. lab scripts → LAB  — references/essentials21-harness/lab/*.rb into
#                           Data/Scripts/998_ChrookedDexLab/ (save redirect, self-test)
#   2. install the port   — apply --category behaviors, only when the lab's copy of
#                           this mechanic's port differs from references/
#   3. headless battle    — nova_selftest.ps1 boots Game.exe once; the self-test
#                           measures the damage A/B and runs one AI-vs-AI battle
#   4. score              — behavior harness verify: PASS/FAIL per spec test_case
#
# Usage: scripts/nova_selftest.sh <mechanic>      e.g. scripts/nova_selftest.sh kindle
#
# Config: NOVA_LAB (default /mnt/d/Games/Pokemon FanGames/NovaV3.0-dexlab/Nova)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NOVA_LAB="${NOVA_LAB:-/mnt/d/Games/Pokemon FanGames/NovaV3.0-dexlab/Nova}"
POWERSHELL="${POWERSHELL:-/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe}"
LAB_SCRIPTS_SRC="${REPO_ROOT}/references/essentials21-harness/lab"
MECH="${1:?usage: nova_selftest.sh <mechanic>}"

say() { printf '\n== %s\n' "$*"; }

[ -f "${NOVA_LAB}/Game.exe" ] || { echo "lab copy not found at ${NOVA_LAB}" >&2; exit 1; }
grep -q '"debugMode": true' "${NOVA_LAB}/mkxp.json" || { echo "${NOVA_LAB} is not the lab (no debugMode) — refusing" >&2; exit 1; }
[ -f "${REPO_ROOT}/references/essentials21-harness/chrooked_${MECH}.rb" ] || { echo "no Essentials 21 port for '${MECH}' in references/essentials21-harness/" >&2; exit 1; }

say "lab scripts → ${NOVA_LAB} (lab only)"
dst="${NOVA_LAB}/Data/Scripts/998_ChrookedDexLab"
mkdir -p "${dst}"
for src in "${LAB_SCRIPTS_SRC}"/*.rb; do
  cmp -s "${src}" "${dst}/$(basename "${src}")" || { cp "${src}" "${dst}/"; echo "  $(basename "${src}")"; }
done

port_rel="Data/Scripts/998_ChrookedMods/chrooked_${MECH}.rb"
if ! cmp -s "${REPO_ROOT}/references/essentials21-harness/chrooked_${MECH}.rb" "${NOVA_LAB}/${port_rel}"; then
  say "install ported mechanics → lab (apply --category behaviors)"
  (cd "${REPO_ROOT}" && uv run chrooked-pokedex apply --target "${NOVA_LAB}" --engine essentials --category behaviors --no-sync)
fi

say "headless battle (lab Game.exe)"
status=0
"${POWERSHELL}" -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w "${SCRIPT_DIR}/nova_selftest.ps1")" -Mechanic "${MECH}" || status=$?

say "score against the spec"
(cd "${REPO_ROOT}" && uv run python -m chrooked_pokedex.behavior.harness verify "${MECH}" --target "${NOVA_LAB}") || status=$?
exit "${status}"
