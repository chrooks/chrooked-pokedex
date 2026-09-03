# chrooked:zz_debug
# Static mod (not a Ruleset behavior) — always installed by apply.
#
# Unlocks the Debug entry in the pause menu, bag, party, and storage screens.
# Harvested into the Ruleset 2026-09-03: it had been a hand-placed file living
# only inside patch/ on two machines, which meant any clean apply deleted it —
# and one did. patch/ is generated, so a file that exists only there is not
# stored, it is stranded (runbook 23's harvest rule).
#
# To turn debug mode off, delete THIS file from references/rejuv-harness/ and
# re-apply. Deleting it from a target's patch/Mods only lasts until next apply.
$DEBUG = true
