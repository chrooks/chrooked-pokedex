# chrooked:seasonsend
# Season's End (move) — a status move that rotates Deerling/Sawsbuck to its next
# seasonal form in the fixed cycle Spring(0) -> Summer(1) -> Autumn(2) -> Winter(3) -> Spring.
# Form indices confirmed from Rejuv's petal items (PINKPETAL=0 Spring, GREENPETAL=1 Summer,
# ORANGEPETAL=2 Autumn, BLUEPETAL=3 Winter in Scripts/ItemEffects.rb).
#
# Wiring: the move data carries function 0x000 (no engine effect), so the rotation runs
# through the core's post-move seam CHROOKED_AFTER_MOVE, which fires on the move's USER with
# its lastMoveUsed. That seam is keyed by the user's active ability, so we register the same
# lambda under all three abilities this line can carry (Adaptability / Impale / Serene Grace);
# whichever slot is active, the hook fires. The lambda guards on move + species, so every
# other Pokemon with those abilities pays only a symbol comparison after each move.
#
# In-battle form refresh mirrors Rejuv's own sequence (Scripts/Battle.rb:2380-2381):
# set the underlying Pokemon's form, sync the battler, then pbUpdate(true) to recalc
# stats/types/sprite for the rest of the battle. The form persists after battle because it
# is stored on the Pokemon, not a battle-only volatile.
#
# Test cases:
#   - a Spring Sawsbuck uses Season's End => becomes Summer (Normal/Grass); stats/types update
#   - a Winter Sawsbuck uses Season's End => wraps to Spring (Normal/Fairy)
#   - a non-Deerling/Sawsbuck that somehow has Season's End => no form change

_chrooked_season_shift = lambda { |user, move_sym, battle|
  next unless move_sym == :SEASONSEND
  pkmn = user.pokemon
  next unless pkmn && [:DEERLING, :SAWSBUCK].include?(pkmn.species)
  new_form = (user.form + 1) % 4
  pkmn.changeForm(new_form)
  user.changeForm(new_form)
  user.pbUpdate(true)
  battle.pbDisplay(_INTL("The season shifts!"))
}

# ponytail: last-write-wins on these keys. Safe today — Adaptability/Serene Grace carry no
# other chrooked after-move hook, and Impale is typemod-only. Revisit if a future behavior
# registers CHROOKED_AFTER_MOVE for one of these abilities.
[:ADAPTABILITY, :IMPALE, :SERENEGRACE].each do |abil|
  CHROOKED_AFTER_MOVE[abil] = _chrooked_season_shift
end
