#!/usr/bin/env bash
# nova_thor_selftest.sh — one-boot proof of a ported mechanic on thor (mjolnir runbook 31).
#
# thor runs a played copy of Pokémon Nova, which never carries lab scripts. This
# is the one deliberate, short exception: it puts the lab's headless self-test on
# thor in a folder of its own, sets the markers, scores the log, and takes it all
# off again. Driven 2026-10-22 for kindle (mjolnir NV-5): 3/3 on Kirin 0.3.5.
#
#   scripts/nova_thor_selftest.sh arm <mechanic>...   self-test + markers onto thor
#   # Chris: kill Kirin, launch Nova, stop at the title screen, do NOT load the save
#   scripts/nova_thor_selftest.sh read <mechanic>...  fetch thor's log, score each with the harness
#   scripts/nova_thor_selftest.sh disarm            remove self-test, markers, log, scratch folder
#   # Chris: kill and relaunch Kirin once more before playing
#
# The self-test never writes the real save: while it runs, SaveData points at
# chrooked-selftest-saves/, and every global it sets is restored afterwards.
# The port itself must already be deployed (scripts/nova_apply.sh).
#
# Config: NOVA_LAB (PBS for the harness's dialect check), NOVA_THOR_* and WIN_SSH
# as in nova_apply.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
NOVA_LAB="${NOVA_LAB:-/mnt/d/Games/Pokemon FanGames/NovaV3.0-dexlab/Nova}"
NOVA_THOR_USER="${NOVA_THOR_USER:-u0_a132}"
NOVA_THOR_HOST="${NOVA_THOR_HOST:-192.168.1.121}"
NOVA_THOR_PORT="${NOVA_THOR_PORT:-8022}"
NOVA_THOR_GAME="${NOVA_THOR_GAME:-/storage/emulated/0/Pokemon Nova}"
# Windows' own OpenSSH: this PC's key has a passphrase only the Windows agent holds.
WIN_SSH="${WIN_SSH:-/mnt/c/Windows/System32/OpenSSH/ssh.exe}"
SELFTEST="${REPO_ROOT}/references/essentials21-harness/lab/010_battle_selftest.rb"
TEST_DIR="Data/Scripts/998_ChrookedSelfTest"
MODS_DIR="Data/Scripts/998_ChrookedMods"

thor() { "${WIN_SSH}" -o BatchMode=yes -p "${NOVA_THOR_PORT}" "${NOVA_THOR_USER}@${NOVA_THOR_HOST}" "$@"; }
usage() { echo "usage: $0 arm <mechanic>... | read <mechanic>... | disarm" >&2; exit 2; }

case "${1:-}" in
  arm)
    shift; [ $# -gt 0 ] || usage
    for MECH in "$@"; do
      grep -q "\"${MECH}\" =>" "${SELFTEST}" || { echo "no CASES entry for '${MECH}' in ${SELFTEST}" >&2; exit 1; }
      thor "test -f \"${NOVA_THOR_GAME}/${MODS_DIR}/chrooked_${MECH}.rb\"" \
        || { echo "chrooked_${MECH}.rb is not deployed on thor — run scripts/nova_apply.sh first" >&2; exit 1; }
    done
    thor "cd \"${NOVA_THOR_GAME}\" && mkdir -p ${TEST_DIR} && cat > ${TEST_DIR}/010_battle_selftest.rb \
      && printf '%s\n' '$*' > chrooked-selftest.on && printf 'proof\n' > chrooked-oracle.on \
      && rm -f chrooked_load.log && md5sum ${TEST_DIR}/010_battle_selftest.rb | cut -c1-8,33-" < "${SELFTEST}"
    echo "  (repo) $(md5sum "${SELFTEST}" | cut -c1-8)"
    echo "Armed. Kill Kirin, launch Nova, stop at the title screen (do not load the save), then: $0 read $*"
    ;;
  read)
    shift; [ $# -gt 0 ] || usage
    tmp="$(mktemp -d)"
    ln -s "${NOVA_LAB}/PBS" "${tmp}/PBS"   # gives the harness the essentials21 dialect
    thor "cat \"${NOVA_THOR_GAME}/chrooked_load.log\"" > "${tmp}/chrooked_load.log" \
      || { echo "no chrooked_load.log on thor — was Kirin relaunched after arming?" >&2; exit 1; }
    echo "--- thor chrooked_load.log (OBS and EST lines omitted)"
    grep -v -E '\] (OBS|EST) ' "${tmp}/chrooked_load.log" || true
    echo
    status=0
    for MECH in "$@"; do
      (cd "${REPO_ROOT}" && uv run python -m chrooked_pokedex.behavior.harness verify "${MECH}" --target "${tmp}") || status=1
      echo
    done
    exit "${status}"
    ;;
  disarm)
    thor "cd \"${NOVA_THOR_GAME}\" && rm -rf ${TEST_DIR} chrooked-selftest-saves \
      && rm -f chrooked-selftest.on chrooked-oracle.on chrooked_load.log && ls -d Data/Scripts/998_*"
    echo "Disarmed. Kill and relaunch Kirin once more before playing."
    ;;
  *) usage ;;
esac
