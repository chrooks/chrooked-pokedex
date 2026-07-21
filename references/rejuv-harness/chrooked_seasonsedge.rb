# chrooked:seasonsedge
# Season's Edge (move) — "This move's type matches the user's seasonal form."
#   damage-calc: resolve the move's type from the user's Deerling/Sawsbuck form
#   BEFORE anything downstream reads it: Spring(0) -> Fairy, Summer(1) -> Grass,
#   Autumn(2) -> Ground, Winter(3) -> Ice. Form indices match Season's End
#   (chrooked_seasonsend.rb) and Rejuv's petal items.
#
# Wiring: everything that cares about a move's type in this engine — STAB, type
# effectiveness, immunities, Lightning Rod/Storm Drain redirection, absorbing
# abilities, weather fizzle — resolves it through PokeBattle_Move#pbType
# (Battle_Move.rb:256; e.g. Battler.rb pbOnStartUse / redirection both call it).
# So one prepended pbType is the whole mechanic. prepend, NOT alias: the core's
# ChrookedTypeMods already prepends pbType, and an alias would capture that
# wrapper and recurse through its super. The swap applies after `super`, the
# same shape as the core's CHROOKED_TYPE_MODS hook.
# ponytail: a swapped Season's Edge ignores Electrify's retype — acceptable;
# rework to pre-super threading if that interaction ever matters.
#
# ponytail: the four-entry table is hardcoded (the spec allows it) — keep it in
# sync with the secondary types in ruleset/species/sawsbuck*.yaml.
#
# Test cases (from ruleset/behaviors/seasonsedge.yaml):
#   - Spring Sawsbuck: resolves Fairy; Adaptability gives 2.0x STAB, not 1.5x
#   - Winter Sawsbuck vs Ground target: resolves Ice, 2x, not resisted as Normal
#   - Summer Sawsbuck vs Sap Sipper: absorbed as a Grass move (+1 Atk, no damage)
#   - Autumn Sawsbuck vs Flying target: resolves Ground, immune
#   - a non-Deerling/Sawsbuck user: declared Normal type, no swap

CHROOKED_SEASONSEDGE_TYPES = [:FAIRY, :GRASS, :GROUND, :ICE]

module ChrookedSeasonsEdge
  def pbType(attacker, type = @type)
    t = super
    if @move == :SEASONSEDGE && attacker
      pkmn = attacker.respond_to?(:pokemon) ? attacker.pokemon : nil
      if pkmn && [:DEERLING, :SAWSBUCK].include?(pkmn.species)
        t = CHROOKED_SEASONSEDGE_TYPES[attacker.form % 4]
      end
    end
    t
  end
end
PokeBattle_Move.prepend(ChrookedSeasonsEdge)
