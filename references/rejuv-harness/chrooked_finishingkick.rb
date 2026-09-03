# encoding: utf-8
# chrooked:finishingkick
# Finishing Kick — "Speed rises each turn. Once it has risen, contact moves
#   hit 1.2x harder."
#
# Only the CONTACT clause lives here. The per-turn Speed rise is declared in
# the Ruleset as
#   behaviors: [finishingkick, speedboost]
# so chrooked_zz_zcompose.rb makes the holder a ChrookedAbilitySet of
# [:FINISHINGKICK, :SPEEDBOOST] and vanilla's own Speed Boost tick
# (Battle.rb ~7326, `ability == :SPEEDBOOST`) fires on it. Never copy that
# rule in here.
#
#   damage-calc: attacker's Speed STAGE >= +1 AND contact move => x1.2
#   Reads the stage counter, not computed Speed, so Simple/Contrary only change
#   how fast the threshold is reached. Stages reset on switch-out, so the
#   bonus is lost on a switch and rebuilt by Speed Boost.
# Test cases:
#   - stage 0, Quick Attack (contact)      => no boost
#   - stage +1, Wild Charge (contact)      => 1.2x
#   - stage +2, Thunderbolt (non-contact)  => no boost
#   - stage +6, Crunch (contact)           => 1.2x (still active at the cap)
CHROOKED_DAMAGE_MODS[:FINISHINGKICK] = lambda { |move, attacker, opponent|
  attacker.stages[PBStats::SPEED] >= 1 && move.contactMove? ? 1.2 : 1.0
}
