# chrooked:zz_run
# Static QoL mod (not a Ruleset behavior) — always installed by apply.
# Overrides ONE method (pbCommandMenuEx) per Rejuv's patch/Mods method-override
# modding (see Modding.txt): pressing B in a wild battle picks Run.
# ponytail: full-method override — re-sync from Scripts/Battle_Scene.rb if a
# Rejuv update changes pbCommandMenuEx.
class PokeBattle_Scene
  def pbCommandMenuEx(index, texts, mode = 0)
    pbShowWindow(COMMANDBOX)
    cw = @sprites["commandwindow"]
    cw.setTexts(texts)
    cw.index = 0 if @lastcmd[index] == 2 || $Settings.remember_commands == 0
    cw.mode = mode
    fieldnotes = readableFieldNotes()
    bossnotes = readableBossNotes(@battle)
    @sprites["defaultballdisplay"].pbSet(index)
    pbSelectBattler(index)
    pbRefresh
    update_menu = true
    holdZ = false
    $chrooked_quickrun = false # chrooked: cleared each time the command menu opens
    tts(texts[0].gsub("\n", " "))
    loop do
      pbFrameUpdate(cw, update_menu)
      pbGraphicsUpdate
      Input.update
      update_menu = false

      if Input.triggerex?(Input::F2)
        scene = DefaultControlsScene.new(2)
        pbFadeOutIn(99999) { scene.pbRender }
      elsif Input.shiftKeyTriggered? && !Rejuv
        pbToggleStatsBoostsVisibility
        pbPlayCursorSE()
      elsif Input.trigger?(Input::LEFT)
        if (cw.index & 1) == 1 && mode != 5
          pbPlayCursorSE()
          cw.index -= 1
          update_menu = true
        end
      elsif Input.trigger?(Input::RIGHT)
        if (cw.index & 1) == 0 && mode != 5
          pbPlayCursorSE()
          cw.index += 1
          update_menu = true
        end
      elsif Input.trigger?(Input::UP)
        if (cw.index & 2) == 2 && mode != 5
          pbPlayCursorSE()
          cw.index -= 2
          update_menu = true
        end
      elsif Input.trigger?(Input::DOWN)
        if (cw.index & 2) == 0 && mode != 5
          pbPlayCursorSE()
          cw.index += 2
          update_menu = true
        end
      elsif Input.trigger?(Input::L) # Show Battle Stats feature made by DemICE, Trainer Pokemon
        pbShowBattleStats(index) unless pbInSafari?
      elsif Input.trigger?(Input::R) # Show Battle Stats feature made by DemICE, Opponent Pokemon
        pbShowBattleStats(index ^ 1) unless pbInSafari?
      elsif Input.trigger?(Input::Y) # Battle log
        showBattleLog
      elsif Input.trigger?(Input::A) && @sprites["defaultballdisplay"].canthrow # Default Poke Ball
        ballchosen = @sprites["defaultballdisplay"].pbSelect
        return :ball if ballchosen
      elsif Input.trigger?(Input::C) # Confirm choice
        pbPlayDecisionSE()
        ret = cw.index
        @lastcmd[index] = ret
        return ret
      elsif Input.trigger?(Input::B) # Cancel
        if index == 2 # && @lastcmd[0]!=2 # Commented out for cancelling switches in doubles
          pbPlayDecisionSE()
          return -1
        end
        if @battle.specialchoices[index] != [nil]
          pbPlayDecisionSE()
          return -1
        end
        # chrooked: B runs from a wild battle (returns the Run command index,
        # which pbCommandMenu maps to Run/Call). Trainer battles fall through
        # to the base no-op; pbRun still gates escape.
        if @battle.pbIsWild?
          pbPlayDecisionSE()
          $chrooked_quickrun = true
          return 3
        end
      else
        checkKeyPressesCommand()
      end

      showFieldNotes, showBossNotes = false, false
      holdZ = false if Input.time?(Input::Z) == 0.0 && !Input.release?(Input::Z)
      if Input.time?(Input::Z) >= 0.5
        if $game_switches[:Blindstep]
          holdZ = true
        else
          showBossNotes = true
        end
      elsif Input.release?(Input::Z) && !Input.press?(Input::Z)
        if holdZ
          holdZ = false
          showBossNotes = true
        else
          showFieldNotes = true
        end
      end
      if showFieldNotes && canCheckFieldApp?(fieldnotes)
        pbPlayCursorSE()
        infoscene = Scene_FieldNotes_Battle.new
        pbCheckPokegearScene(infoscene, fieldnotes)
      end
      if showBossNotes && canCheckBossDex?(bossnotes)
        pbPlayCursorSE()
        infoscene = Scene_BossDex_Battle.new
        pbCheckPokegearScene(infoscene, bossnotes)
      end

      tts(texts[cw.index + 1], true) if update_menu
    end
  end
end

# chrooked: a B-triggered run shouldn't make you press A again to leave.
# Full-method override of PokeBattle_Battle#pbDisplayAutoPaused (Battle.rb) —
# unpaused only for the one message that follows a B-run.
class PokeBattle_Battle
  def pbDisplayAutoPaused(msg)
    if @controlPlayer || $game_switches[:SpeedSkip_Password] || $chrooked_quickrun
      @scene.pbDisplayMessage(msg)
    else
      @scene.pbDisplayPausedMessage(msg)
    end
  end
end
