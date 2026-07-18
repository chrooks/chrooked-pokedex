# chrooked:spitefulblock
# Spiteful Block — "Taking a damaging hit arms a one-time 30% boost for the
#   next Dark-type move." Armed WHEN_HIT; damage rider reads the flag;
#   consumed after a Dark move deals damage.
#   ponytail: flag persists across switch-out — one-time semantics still hold.
# Test cases:
#   - get hit, then use a Dark move => 1.3x damage, flag clears
#   - Dark move without being hit first => normal damage
CHROOKED_WHEN_HIT[:SPITEFULBLOCK] = lambda { |move, user, target, battle|
  target.effects[:ChrookedSpiteful] = true
}
CHROOKED_DAMAGE_MODS[:SPITEFULBLOCK] = lambda { |move, attacker, opponent|
  attacker.effects[:ChrookedSpiteful] && move.pbType(attacker) == :DARK ? 1.3 : 1.0
}
CHROOKED_ON_DEAL[:SPITEFULBLOCK] = lambda { |move, user, target, battle|
  user.effects[:ChrookedSpiteful] = nil if user.effects[:ChrookedSpiteful] && move.pbType(user) == :DARK
}
