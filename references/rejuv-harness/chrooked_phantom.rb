# chrooked:phantom
# Phantom — "Adds the Ghost type on entry, like Trick-or-Treat."
#   On switch-in (the battle-start lead included) the holder gains Ghost as an
#   extra type on top of its own two, exactly as if Trick-or-Treat hit it.
#
# The whole mechanic is the core's generic CHROOKED_ADDED_TYPE registry (see
# chrooked_00_core.rb): the pbAbilitiesOnSwitchIn wrapper writes the type into
# effects[:TemporaryType], the slot Trick-or-Treat itself writes
# (Battle_MoveEffects.rb:7424). Everything else is vanilla, for free:
#   - Battler#types appends the slot (Battler.rb:226), so hasType?, type
#     effectiveness (pbTypeModifier, Battle_Move.rb:431), STAB (Battle_Move.rb
#     :1163) and the AI (pbCalcTypeMod via pbTypeModNoMessages, Battle_AI.rb
#     :9488; STAB at :13601) all see Ghost.
#   - It goes on switch-out: pbInitEffects clears the slot (Battler.rb:655).
#   - Already Ghost, or cannot change type (Multitype, RKS System, crested
#     Silvally, Terastallized) => nothing, no ability box (Trick-or-Treat's own
#     gate, Battle_MoveEffects.rb:7416).
#   - A later Forest's Curse replaces Ghost with Grass (one slot); a later
#     Trick-or-Treat fails (already Ghost). Both vanilla.
#   - The battle inspect screen lists it as "Added: Ghost" (Battle_Inspect.rb:160).
# AI switch scoring: the core prepends getTypesOnEntry so a Phantom candidate is
# scored as part Ghost before it comes in.
#
# Test cases (drive in-game — the harness can't run a battle):
#   - Rotom-Heat leads          => ability box, "Ghost type was added to ...!";
#                                  Normal and Fighting moves now miss it.
#   - Rotom-Heat uses Shadow Ball => 1.5x STAB.
#   - Switch out and back in     => Ghost again (re-added on entry).
#   - Foe uses Forest's Curse    => Grass replaces Ghost.
CHROOKED_ADDED_TYPE[:PHANTOM] = :GHOST
