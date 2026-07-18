# chrooked:zz_relearn
# Static UI/mechanic mod (not a Ruleset behavior) — always installed by apply.
#
# Rejuv gates the party "Learn" -> "Natural moves" page behind a per-mon
# "can't remember its moves on its own yet..." flag (canRelearnAll?), which only
# flips true after a relearner NPC. Forcing it true lets every Pokemon SEE and
# relearn its previously-known level-up moves anywhere, no NPC/item needed.
class PokeBattle_Pokemon
  def canRelearnAll?
    return true
  end
end
