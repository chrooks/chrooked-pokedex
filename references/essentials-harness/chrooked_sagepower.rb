# chrooked:sagepower
# ---------------------------------------------------------------------------
# Sage Power: the special-move counterpart of Gorilla Tactics.
#   (1) The user's SPECIAL moves deal 1.5x damage (flat boost, not pseudo-STAB).
#   (2) After its first move since being sent out, the user is locked into that
#       move until it switches out (same code path as a Choice item).
#
# Hook 1 (damage) — Seam (verified 16.2, Data/Scripts.rxdata):
#   PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — the
#   purpose-built final-damage multiplier hook (base impl returns damagemult;
#   damagemult is in 0x1000 units). movetype = pbType(@type,attacker,opponent);
#   category via pbIsSpecial?(movetype). We multiply by 1.5 ONLY when the move is
#   special AND the attacker has SAGEPOWER. This is a flat special-only boost
#   (Gorilla Tactics analogue), NOT a granted pseudo-STAB, so we deliberately do
#   NOT gate on pbHasType? — the boost stacks on top of any real STAB, matching
#   the spec ("special moves x1.5").
#
# Hook 2 (move-lock) — Seam (verified 16.2, Data/Scripts.rxdata):
#   PokeBattle_Battler#pbUseMove(choice, specialusage=false) — move-execution
#   entry; `self` is the user. We reuse the engine Choice-lock effect
#   PBEffects::ChoiceBand (==7): when currently <0 (unlocked) and the user has
#   already recorded a move this send-out (self.lastMoveUsed >= 0), set
#   self.effects[PBEffects::ChoiceBand] = self.lastMoveUsed. The engine then
#   enforces the lock exactly like a Choice item, and clears it on switch-out.
#
# HARNESS (Route B log oracle):
#   damage hook: [chrooked:sagepower] OBS move=<NAME> sagepower=<bool> special=<bool> result=BOOSTED|NORMAL
#   lock hook:   [chrooked:sagepower] OBS event=movelock ability=true locked=<MOVEID>
#
# RUBY 1.8: alias_method chaining (NO prepend/TracePoint); each method aliased
# separately with its own installed-flag; deferred install on Graphics.update;
# unique _chrooked_sagepower names; call _orig first.
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
        movetype = (pbType(@type, attacker, opponent) rescue -1)
        is_special = (pbIsSpecial?(movetype) rescue false)
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

# --- Hook 2: Gorilla-Tactics-style move-lock --------------------------------
def chrooked_install_sagepower_lock
  return if $chrooked_sagepower_lock_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbUseMove")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbUseMove_chrooked_sagepower_orig")
      alias_method :pbUseMove_chrooked_sagepower_orig, :pbUseMove
      def pbUseMove(choice, specialusage = false)
        ret = pbUseMove_chrooked_sagepower_orig(choice, specialusage)
        begin
          if (self.hasWorkingAbility(:SAGEPOWER) rescue false) &&
             self.effects[PBEffects::ChoiceBand] < 0 &&
             self.lastMoveUsed && self.lastMoveUsed >= 0
            self.effects[PBEffects::ChoiceBand] = self.lastMoveUsed
            ($chrooked_log.call("[chrooked:sagepower] OBS event=movelock ability=true locked=#{self.lastMoveUsed}") rescue nil)
          end
        rescue Exception
        end
        ret
      end
    end
  end
  $chrooked_sagepower_lock_installed = true
  ($chrooked_log.call("[chrooked:sagepower] lock hook installed on PokeBattle_Battler") rescue nil)
end

# --- Deferred install arming (each hook tracked by its own flag) -------------
chrooked_install_sagepower_damage if defined?(PokeBattle_Move) &&
  PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
chrooked_install_sagepower_lock if defined?(PokeBattle_Battler) &&
  PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbUseMove")

if (defined?($chrooked_sagepower_damage_installed) && $chrooked_sagepower_damage_installed) &&
   (defined?($chrooked_sagepower_lock_installed) && $chrooked_sagepower_lock_installed)
  # both installed eagerly; nothing deferred needed
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_sagepower_orig)
      alias_method :update_chrooked_sagepower_orig, :update
      def update
        chrooked_install_sagepower_damage if !$chrooked_sagepower_damage_installed && defined?(PokeBattle_Move)
        chrooked_install_sagepower_lock if !$chrooked_sagepower_lock_installed && defined?(PokeBattle_Battler)
        update_chrooked_sagepower_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:sagepower] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:sagepower] ERROR: PokeBattle classes/Graphics missing at load") rescue nil)
end
