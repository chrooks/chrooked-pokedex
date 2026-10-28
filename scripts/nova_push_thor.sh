#!/usr/bin/env bash
# nova_push_thor.sh — ship Nova from hestia to thor (Kirin) without the PC.
#
#   1. patch   — scripts/nova_dat_patch.rb projects the hestia copy's PBS into
#                its compiled Data/{species,abilities,moves}.dat (Ruby via the
#                chrooked-pokedex docker image; hestia has no system Ruby)
#   2. deploy  — changed .dat files and the dex-owned 998_ChrookedMods/chrooked_*.rb
#                go to thor over SSH, with a Data.pre-apply-<date> backup there,
#                exactly the shape scripts/nova_apply.sh uses from the PC.
#
# The PC's nova_apply.sh stays the full compile (every PBS field). This covers
# the fields the dex owns so a redesign can land while the PC is unreachable.
#
# Usage: scripts/nova_push_thor.sh [--dry-run]
#   NOVA_GAME  hestia's Nova copy          (default ~/projects/nova-game)
#   NOVA_THOR  user@host for thor          (default u0_a132@100.69.35.54, Tailscale)
#   NOVA_THOR_PORT                         (default 8022)
#   NOVA_THOR_GAME                         (default "/storage/emulated/0/Pokemon Nova")
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOVA_GAME="${NOVA_GAME:-$HOME/projects/nova-game}"
NOVA_THOR="${NOVA_THOR:-u0_a132@100.69.35.54}"
NOVA_THOR_PORT="${NOVA_THOR_PORT:-8022}"
NOVA_THOR_GAME="${NOVA_THOR_GAME:-/storage/emulated/0/Pokemon Nova}"
MODS_REL="Data/Scripts/998_ChrookedMods"
DRY=false; [ "${1:-}" = "--dry-run" ] && DRY=true
STAMP="$(date +%F)"
say() { printf '\n== %s\n' "$*"; }
IDENT=(); [ -f "$HOME/.ssh/thor_ed25519" ] && IDENT=(-i "$HOME/.ssh/thor_ed25519")
thor_ssh() { ssh "${IDENT[@]}" -o BatchMode=yes -o ConnectTimeout=10 -p "${NOVA_THOR_PORT}" "${NOVA_THOR}" "$@"; }

say "patch PBS → Data/*.dat (${NOVA_GAME})"
OUT="$(mktemp -d)"
set +e
docker run --rm -v "${NOVA_GAME}:/g:ro" -v "${SCRIPT_DIR}:/s:ro" -v "${OUT}:/o" \
  --entrypoint ruby chrooked-pokedex /s/nova_dat_patch.rb /g /o
rc=$?
set -e
[ "$rc" -eq 0 ] || [ "$rc" -eq 3 ] || { echo "patch failed (rc=$rc)" >&2; exit "$rc"; }

CHANGED=()
for f in species abilities moves; do
  cmp -s "${OUT}/${f}.dat" "${NOVA_GAME}/Data/${f}.dat" || CHANGED+=("${f}.dat")
done
echo "  changed: ${CHANGED[*]:-none}"
$DRY && { echo "dry run — nothing sent"; exit 0; }

say "deploy to thor (${NOVA_THOR})"
thor_ssh "test -d \"${NOVA_THOR_GAME}/Data\"" || { echo "thor unreachable or game folder missing" >&2; exit 4; }
if [ ${#CHANGED[@]} -gt 0 ]; then
  (cd "${OUT}" && tar -cf - "${CHANGED[@]}") | thor_ssh \
    "mkdir -p \"${NOVA_THOR_GAME}/Data.pre-apply-${STAMP}\" && cd \"${NOVA_THOR_GAME}/Data\" && for f in ${CHANGED[*]}; do cp -p \"\$f\" \"../Data.pre-apply-${STAMP}/\" 2>/dev/null || true; done && tar -xf - && md5sum ${CHANGED[*]} | cut -c1-8,33-"
  echo "  (hestia)"; (cd "${OUT}" && md5sum "${CHANGED[@]}" | cut -c1-8,33-)
  for f in "${CHANGED[@]}"; do cp -p "${OUT}/${f}" "${NOVA_GAME}/Data/${f}"; done
fi

say "mirror ${MODS_REL}/chrooked_*.rb → thor"
PORTS="$(cd "${NOVA_GAME}/${MODS_REL}" && find . -maxdepth 1 -name 'chrooked_*.rb' -printf '%f\n' | sort)"
(cd "${NOVA_GAME}/${MODS_REL}" && tar -cf - ${PORTS}) | thor_ssh \
  "mkdir -p \"${NOVA_THOR_GAME}/${MODS_REL}\" && cd \"${NOVA_THOR_GAME}/${MODS_REL}\" && tar -xf - && for p in chrooked_*.rb; do case ' ${PORTS//$'\n'/ } ' in *\" \$p \"*) ;; *) rm -f \"\$p\" && echo \"  removed \$p\";; esac; done && ls chrooked_*.rb | wc -l"
echo "  (hestia) $(echo "${PORTS}" | wc -l) ports"
rm -rf "${OUT}"
say "done — restart Nova in Kirin to load the new data"
