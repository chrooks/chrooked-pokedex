# chrooked:catchrate — personal QoL, not Ruleset canon. Delete to restore
# normal catch rates. Forces the capture formula's x above the guaranteed
# threshold (x > 255 => 4 shakes) for every throwable ball.
# Harvested into the Ruleset 2026-09-03 — it had lived only in patch/ on hestia
# and thor, where any apply would delete it. Delete THIS file (not a target's
# patch/Mods copy) to remove it.
module ChrookedCatchRate
  def pbThrowPokeBall(idxPokemon, ball, rareness = nil, showplayer = false)
    super(idxPokemon, ball, 99_999, showplayer)
  end
end
PokeBattle_Battle.prepend(ChrookedCatchRate)
