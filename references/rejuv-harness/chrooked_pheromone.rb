# chrooked:pheromone
# Pheromone — "Its scent holds foes in place. Foes cannot switch out or flee.
#   Ghost types are unaffected." Shadow Tag without the mirror-holder exemption.
#   switch-check: after vanilla allows a switch/run, fail it when the opposing
#   side has a Pheromone holder. Ghost types and Shed Shell already returned
#   true out of vanilla's case; they are re-checked here so the trap never
#   overrides those escapes. Move-forced switches (U-turn) bypass pbCanSwitch?
#   exactly as they do for Shadow Tag.
# Test cases (drive in-game):
#   - foe tries to switch => "X's Pheromone prevents switching!"
#   - wild foe tries to run => "X prevents escaping with Pheromone!"
#   - Ghost foe / Shed Shell holder => switches
#   - foe U-turns => switches
module Chrooked
  module PheromoneTrap
    def pbCanSwitch?(idxPokemon, pkmnidxTo, showMessage: false, ai_phase: false)
      return false unless super
      thispkmn = @battlers[idxPokemon]
      return true if !thispkmn || thispkmn.hasType?(:GHOST) || thispkmn.hasWorkingItem(:SHEDSHELL)
      trapper = pbCheckSideAbility(:PHEROMONE, thispkmn.pbOpposing1).first
      return true unless trapper
      if showMessage
        running = pkmnidxTo == -1
        message = running ? _INTL("{1} prevents escaping with {2}!", trapper.pbThis, getAbilityName(trapper.ability)) :
                            _INTL("{1}'s {2} prevents switching!", trapper.pbThis, getAbilityName(trapper.ability))
        pbDisplayCommandPaused(message)
      end
      false
    end
  end
end
PokeBattle_Battle.prepend(Chrooked::PheromoneTrap)

# The AI scores trapping by these lists (Battle_AI.rb:4944/6021/6465/7006).
if defined?(PBStuff)
  PBStuff::TRAPPINGABILITIES << :PHEROMONE if defined?(PBStuff::TRAPPINGABILITIES) && !PBStuff::TRAPPINGABILITIES.include?(:PHEROMONE)
  PBStuff::TRAPPINGABILITIESAI << :PHEROMONE if defined?(PBStuff::TRAPPINGABILITIESAI) && !PBStuff::TRAPPINGABILITIESAI.include?(:PHEROMONE)
end
