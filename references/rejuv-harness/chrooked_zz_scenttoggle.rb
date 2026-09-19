# chrooked:zz_scenttoggle
# Static QoL mod (not a Ruleset behavior) — always installed by apply.
#
# Encounter toggle: press E (mnemonic: E for Encounters) on the overworld to
# flip the Spice Scent between 0 (no wild encounters) and 9000 (an encounter
# on the first grass step). Replaces the repel-spam / Pokegear round trip.
# Writes the same state the Pokegear Spice Scent screen writes
# (Pokegear.rb Scene_EncounterRate#main): the variable holds the dial / 100,
# FirstUse must be on or Encounters.rb ignores the variable, then re-setup.
# Any value other than 0 counts as "on", so a custom dial value flips to 0.
#
# Pad hotkey: L3 (left stick click — SDL calls it LEFTSTICK). Select is the PC
# (chrooked_zz_pckey.rb) and R3 is the level cap (chrooked_zz_levelcap.rb).
# Same keyboard/pad shape as chrooked_zz_pckey.rb, and the same Seam
# (Scene_Map#checkKeyPresses/#handleKeyPresses); loads after it
# (alphabetical), so the alias chain keeps the PC and Blessings hotkeys.
class Game_Temp
  attr_accessor :chrooked_scent_calling
end

module ChrookedScentToggle
  ON_DIAL = 9000

  def self.pressed?
    return true if Input.triggerex?(:E)
    return false unless defined?(Input::Controller)

    Input::Controller.triggerex?(:LEFTSTICK)
  end

  def self.toggle
    on = $game_switches[:FirstUse] && $game_variables[:EncounterRateModifier].to_f > 0
    dial = on ? 0 : ON_DIAL
    $game_variables[:EncounterRateModifier] = dial / 100.0
    $game_switches[:FirstUse] = true
    $PokemonEncounters.setup($game_map.map_id) if defined?($game_map.map_id)
    Kernel.pbMessage(_INTL("Spice Scent set to {1}. Wild encounters {2}.",
                           dial, on ? "OFF" : "ON"))
  end
end

class Scene_Map
  # Chain only when the base Seam exists — the stub-test harness loads this
  # file against bare stand-in classes with no key-press methods.
  if method_defined?(:checkKeyPresses) && !method_defined?(:chrooked_scent_checkKeyPresses)
    alias chrooked_scent_checkKeyPresses checkKeyPresses
    alias chrooked_scent_handleKeyPresses handleKeyPresses

    def checkKeyPresses
      chrooked_scent_checkKeyPresses
      if ChrookedScentToggle.pressed? && !pbMapInterpreterRunning? &&
         !$game_switches[:NotPlayerCharacter]
        $game_temp.chrooked_scent_calling = true
      end
    end

    def handleKeyPresses
      if $game_temp.chrooked_scent_calling
        $game_temp.chrooked_scent_calling = false
        ChrookedScentToggle.toggle
      else
        chrooked_scent_handleKeyPresses
      end
    end
  end
end
