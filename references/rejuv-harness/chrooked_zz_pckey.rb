# chrooked:zz_pckey
# Static QoL mod (not a Ruleset behavior) — always installed by apply.
#
# Overworld hotkey: press F8 on the map to open the PC storage screen
# (organize mode), no Pokemon Center or Remote PC item needed. Same organize
# screen the party-menu "PC" option (chrooked_zz_pc.rb) opens, so the two
# stay consistent. F8 is also the party-screen level-cap key
# (chrooked_zz_levelcap.rb) — one QoL key, context decides.
#
# Uses the designed Seam: Scene_Map#checkKeyPresses/#handleKeyPresses
# ("to be overwritten per game", Scene_Map.rb:250). Rejuv's Blessings overlay
# already overwrites them (Rejuv/Xenpurgis/BlessingsOverlay.rb:318), and Mods
# load after all base scripts, so alias-and-chain keeps the Blessings hotkey
# working. Same calling-flag shape as call_blessing.
#
# Guards: not while an event runs (pbMapInterpreterRunning?), and not while
# playing as a story character (:NotPlayerCharacter) — opening your own box
# mid-story-segment would sequence-break.
class Game_Temp
  attr_accessor :chrooked_pc_calling
end

class Scene_Map
  unless method_defined?(:chrooked_pckey_checkKeyPresses)
    alias chrooked_pckey_checkKeyPresses checkKeyPresses
    alias chrooked_pckey_handleKeyPresses handleKeyPresses
  end

  def checkKeyPresses
    chrooked_pckey_checkKeyPresses
    if Input.triggerex?(:F8) && !pbMapInterpreterRunning? &&
       !$game_switches[:NotPlayerCharacter]
      $game_temp.chrooked_pc_calling = true
    end
  end

  def handleKeyPresses
    if $game_temp.chrooked_pc_calling
      $game_temp.chrooked_pc_calling = false
      $game_player.straighten
      pbFadeOutIn(99999) {
        PokemonStorageScreen.new(PokemonStorageScene.new, $PokemonStorage).pbStartScreen(0)
      }
    else
      chrooked_pckey_handleKeyPresses
    end
  end
end
