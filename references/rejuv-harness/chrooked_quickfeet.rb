# chrooked:quickfeet
# Quick Feet — the 1.5x Speed on any status and the paralysis Speed-drop
#   exemption are vanilla Rejuv (Battle_Effects.rb:1461 quickFeetActive?).
#   This mod adds the Guts half: no damage penalty from burn or frostbite.
#   burn: the engine's burnmult (Battle_Move.rb:1190) only exempts Guts, inside
#     pbCalcDamage, so the refund is a x2 on the same physical moves it halved.
#   frostbite: chrooked_frostbite.rb exempts Quick Feet next to Guts.
# ponytail: x0.5 then x2 can land 1 HP off the unburned number from rounding;
#   prepend pbCalcDamage around burnmult if exact parity ever matters.
# Test cases:
#   - burned holder uses a physical move => full damage
#   - burned holder uses Facade => vanilla Facade (no refund; it was never halved)
#   - burned holder uses a special move => unchanged
#   - frostbitten holder uses a special move => full damage
CHROOKED_DAMAGE_MODS[:QUICKFEET] = lambda { |move, attacker, opponent|
  next 1.0 unless attacker.status == :BURN
  next 1.0 if move.move == :FACADE || attacker.crested == :SUICUNE
  move.pbIsPhysical?(attacker, move.pbType(attacker)) ? 2.0 : 1.0
}
