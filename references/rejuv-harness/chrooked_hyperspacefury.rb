# chrooked:hyperspacefury
# Hyperspace Fury unlock (move) — Umbreon may use it; Hoopa-only gate bypassed.
#   move-use: attacker is Umbreon => skip the species check in
#   PokeBattle_Move_159#pbOnStartUse; everyone else falls through to vanilla
#   (Hoopa Unbound and Rejuv's Angel of Death Gardevoir keep their access).
# Test cases:
#   - Umbreon uses Hyperspace Fury => executes (pierces protection, -1 Def self)
#   - Hoopa (Confined) => vanilla failure message
#   - any other species => vanilla failure message
if defined?(PokeBattle_Move_159)
  module ChrookedHyperspaceFuryUnlock
    def pbOnStartUse(attacker, targets)
      return true if attacker.species == :UMBREON
      super
    end
  end
  PokeBattle_Move_159.prepend(ChrookedHyperspaceFuryUnlock)
end
