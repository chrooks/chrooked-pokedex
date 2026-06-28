# chrooked:sagepower
# ---------------------------------------------------------------------------
# Sage Power: the special-move counterpart of Gorilla Tactics.
#   (1) The user's SPECIAL moves deal 1.5x damage (flat boost, not pseudo-STAB).
#   (2) After its first move since being sent out, the user is locked into that
#       move until it switches out.
#
# Hook 1 (damage) — Seam (verified 16.2): PokeBattle_Move#pbModifyDamage(damagemult,
#   attacker, opponent). x1.5 when the move is special AND attacker has SAGEPOWER.
#
# Hook 2 (move-lock) — Seam (verified 16.2): PokeBattle_Battle#pbCanChooseMove?(
#   idxPokemon,idxMove,showMessages,sleeptalk=false) (line 883), the move-selection
#   gate. NOTE: the engine's ChoiceBand lock there ONLY fires for Choice-ITEM holders
#   (line 904 requires hasWorkingItem(:CHOICEBAND...)), so setting effects[ChoiceBand]
#   from an ability does NOT lock — that was the v1 bug (re-locked to each new move).
#   Correct approach: disallow choosing any move whose id != the holder's lastMoveUsed
#   once it has acted this stint. lastMoveUsed is -1 on switch-in (so the first choice
#   is free) and resets on switch-out, giving exactly the Gorilla-Tactics lock.
#
# HARNESS log:
#   damage: [chrooked:sagepower] OBS move=<NAME> sagepower=<bool> special=<bool> result=BOOSTED|NORMAL
#   lock:   [chrooked:sagepower] OBS event=movelock blocked=<MOVEID> locked=<MOVEID>
#
# RUBY 1.8: alias_method chaining; each hook its own flag; deferred install on
# Graphics.update; unique _chrooked_sagepower names; call _orig first.
# ---------------------------------------------------------------------------

unless defined?($chrooked_log) && $chrooked_log
  $chrooked_log = lambda do |msg|
    begin
      d = File.expand_path(File.dirname(__FILE__))
      File.open(File.join(d, "chrooked_load.log"), "a") { |f| f.puts(msg) }
    rescue Exception
    end
  end
end

# --- Hook 1: special-move x1.5 damage boost ---------------------------------
def chrooked_install_sagepower_damage
  return if $chrooked_sagepower_damage_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_sagepower_orig")
      alias_method :pbModifyDamage_chrooked_sagepower_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_sagepower_orig(damagemult, attacker, opponent)
        is_sage = (attacker.hasWorkingAbility(:SAGEPOWER) rescue false)
        movetype = (Chrooked.move_type(self, attacker, opponent) rescue nil)
        is_special = (Chrooked.move_special?(self, movetype) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_sage && is_special
          mult = (mult * 1.5).round
          ($chrooked_log.call("[chrooked:sagepower] OBS move=#{movename} sagepower=#{is_sage} special=#{is_special} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:sagepower] OBS move=#{movename} sagepower=#{is_sage} special=#{is_special} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_sagepower_damage_installed = true
  ($chrooked_log.call("[chrooked:sagepower] damage hook installed on PokeBattle_Move") rescue nil)
end

# --- Hook 2: Gorilla-Tactics move-lock via pbCanChooseMove? -----------------
def chrooked_install_sagepower_lock
  return if $chrooked_sagepower_lock_installed
  return unless defined?(PokeBattle_Battle)
  return unless PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbCanChooseMove?")
  PokeBattle_Battle.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbCanChooseMove_chrooked_sagepower_orig")
      alias_method :pbCanChooseMove_chrooked_sagepower_orig, :pbCanChooseMove?
      def pbCanChooseMove?(idxPokemon, idxMove, showMessages, sleeptalk = false)
        begin
          pkmn = @battlers[idxPokemon]
          mv = pkmn.moves[idxMove]
          last = (pkmn.lastMoveUsed rescue -1)
          if mv && (pkmn.hasWorkingAbility(:SAGEPOWER) rescue false) && last && last >= 0 && mv.id != last
            if showMessages
              (pbDisplayPaused(_INTL("¡{1} solo puede usar su primer movimiento!", pkmn.pbThis)) rescue nil)
            end
            ($chrooked_log.call("[chrooked:sagepower] OBS event=movelock blocked=#{mv.id} locked=#{last}") rescue nil)
            return false
          end
        rescue Exception
        end
        pbCanChooseMove_chrooked_sagepower_orig(idxPokemon, idxMove, showMessages, sleeptalk)
      end
    end
  end
  $chrooked_sagepower_lock_installed = true
  ($chrooked_log.call("[chrooked:sagepower] lock hook installed on PokeBattle_Battle") rescue nil)
end

# --- Deferred install arming (each hook tracked by its own flag) -------------
chrooked_install_sagepower_damage if defined?(PokeBattle_Move) &&
  PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
chrooked_install_sagepower_lock if defined?(PokeBattle_Battle) &&
  PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbCanChooseMove?")

if (defined?($chrooked_sagepower_damage_installed) && $chrooked_sagepower_damage_installed) &&
   (defined?($chrooked_sagepower_lock_installed) && $chrooked_sagepower_lock_installed)
  # both installed eagerly
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_sagepower_orig)
      alias_method :update_chrooked_sagepower_orig, :update
      def update
        chrooked_install_sagepower_damage if !$chrooked_sagepower_damage_installed && defined?(PokeBattle_Move)
        chrooked_install_sagepower_lock if !$chrooked_sagepower_lock_installed && defined?(PokeBattle_Battle)
        update_chrooked_sagepower_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:sagepower] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:sagepower] ERROR: PokeBattle classes/Graphics missing at load") rescue nil)
end
