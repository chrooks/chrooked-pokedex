# chrooked:imperialcleave
# Imperial Cleave (move mechanic) — the Protect half is native: function 0x0AD
# (Feint / Hyperspace Hole) clears effects[:Protect] and resets the side guards,
# and the bypassprotect flag gets the move through in the first place. This adds
# the screen half, which no single vanilla funccode combines with a Protect break.
#   on-hit: Imperial Cleave connects => Reflect / Light Screen / Aurora Veil fall
# ponytail: screens still reduce this hit before falling, exactly like Rejuv's own
# Brick Break (pbResolveMoveEffects calls pbEffectTarget after damage,
# Battler.rb:5990). Matching the engine beats a bespoke pre-damage hook.
# Test cases:
#   - target side has Reflect => Reflect reduces this hit, then is removed
#   - target side has Aurora Veil + Light Screen => both fall in one hit
#   - target behind Protect => move hits through (native), shield cleared
#   - move misses or hits a Substitute => no screens removed (seam is damage-gated)
CHROOKED_MOVE_ON_DEAL[:IMPERIALCLEAVE] = lambda { |move, user, target, battle|
  next if target.isFainted?
  battle.pbEndSideEffects(target.pbOwnSide, PBStuff::SCREENEFFECTS.values)
}
