# chrooked:pyre
# ---------------------------------------------------------------------------
# Pyre (ability :PYRE): knocking out a target fuels the user's Fire and Ghost
# moves for 3 turns. ATTACKER-side, timed window.
#
# Three hooks across two classes, each aliased separately with its own
# installed-flag, all deferred onto Graphics.update (Ruby 1.8 alias_method
# chaining; unique _chrooked_pyre names; _orig called first):
#
#   (a) KO  — PokeBattle_Battler#pbEffectsAfterHit(user,target,thismove,
#       turneffects). Seam: vanilla MOXIE/MAGICIAN-style after-hit hook; KO is
#       detected via target.isFainted?. When the user has PYRE and the target
#       fainted, set the per-battler ivar @chrooked_pyre_until = @battle.turncount
#       + 3 (the move that scored the KO is the user's; @battle is the battler's
#       battle reference here).
#
#   (b) DAMAGE — PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent).
#       Seam: 0x1000-unit damage multiplier; attacker = the user. Gate on
#       attacker.hasWorkingAbility(:PYRE) AND @battle.turncount <= the user's
#       stored @chrooked_pyre_until (default -1 so it never fires unset) AND the
#       resolved move type is FIRE or GHOST. When all hold, mult = (mult*1.3).round.
#       @battle inside pbModifyDamage is the move's own battle reference. The
#       attacker's ivar is read with instance_variable_get since it lives on a
#       different object than self (the move).
#
#   (c) RESET — PokeBattle_Battler#pbAbilitiesOnSwitchIn(onactive). Custom
#       per-battler state has no spare PBEffects slot, so the timer is a plain
#       ivar; it MUST be cleared on switch-in so it does not leak to the next
#       Pokemon occupying that slot. Reset @chrooked_pyre_until = -1.
#
# HARNESS (Route B log oracle): each gate firing logs one line:
#   ko:     [chrooked:pyre] OBS event=ko ability=true until=<turn>
#   damage: [chrooked:pyre] OBS move=<NAME> ability=<bool> type=<FIRE|GHOST|other> active=<bool> result=<BOOSTED|NORMAL>
#   reset:  [chrooked:pyre] OBS event=switchin reset=until
#
# NOT-PORTED: none. The yaml's "decrement each turn end" framing is realized
# here as an absolute turncount window (set until=turncount+3, gate
# turncount<=until) per the verified Seam guidance — behaviorally identical to a
# 3-turn countdown, no separate end-of-round Seam needed.
#
# RUBY 1.8: alias_method chaining; deferred install on Graphics.update.
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

# --- Hook (a): KO sets the 3-turn timer on PokeBattle_Battler ---------------
def chrooked_install_pyre_ko
  return if $chrooked_pyre_ko_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbEffectsAfterHit")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEffectsAfterHit_chrooked_pyre_orig")
      alias_method :pbEffectsAfterHit_chrooked_pyre_orig, :pbEffectsAfterHit
      def pbEffectsAfterHit(user, target, thismove, turneffects)
        pbEffectsAfterHit_chrooked_pyre_orig(user, target, thismove, turneffects)
        begin
          if user && target && (user.hasWorkingAbility(:PYRE) rescue false) && (target.isFainted? rescue false)
            until_turn = (@battle.turncount rescue 0) + 3
            user.instance_variable_set(:@chrooked_pyre_until, until_turn)
            ($chrooked_log.call("[chrooked:pyre] OBS event=ko ability=true until=#{until_turn}") rescue nil)
          end
        rescue Exception
        end
      end
    end
  end
  $chrooked_pyre_ko_installed = true
  ($chrooked_log.call("[chrooked:pyre] ko hook installed on PokeBattle_Battler") rescue nil)
end

# --- Hook (b): 1.3x FIRE/GHOST damage while the window is open --------------
def chrooked_install_pyre_damage
  return if $chrooked_pyre_damage_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_pyre_orig")
      alias_method :pbModifyDamage_chrooked_pyre_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_pyre_orig(damagemult, attacker, opponent)
        begin
          is_ab = (attacker.hasWorkingAbility(:PYRE) rescue false)
          movetype = (pbType(@type, attacker, opponent) rescue -1)
          is_fire = (isConst?(movetype, PBTypes, :FIRE) rescue false)
          is_ghost = (isConst?(movetype, PBTypes, :GHOST) rescue false)
          right_type = is_fire || is_ghost
          until_turn = (attacker.instance_variable_get(:@chrooked_pyre_until) rescue nil)
          until_turn = -1 if until_turn.nil?
          now = (@battle.turncount rescue -1)
          active = (now <= until_turn)
          movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
          typetag = is_fire ? "FIRE" : (is_ghost ? "GHOST" : "other")
          if is_ab && active && right_type
            mult = (mult * 1.3).round
            ($chrooked_log.call("[chrooked:pyre] OBS move=#{movename} ability=#{is_ab} type=#{typetag} active=#{active} result=BOOSTED") rescue nil)
          else
            ($chrooked_log.call("[chrooked:pyre] OBS move=#{movename} ability=#{is_ab} type=#{typetag} active=#{active} result=NORMAL") rescue nil)
          end
        rescue Exception
        end
        mult
      end
    end
  end
  $chrooked_pyre_damage_installed = true
  ($chrooked_log.call("[chrooked:pyre] damage hook installed on PokeBattle_Move") rescue nil)
end

# --- Hook (c): clear the timer on switch-in so it never leaks slots ---------
def chrooked_install_pyre_reset
  return if $chrooked_pyre_reset_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbAbilitiesOnSwitchIn")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbAbilitiesOnSwitchIn_chrooked_pyre_orig")
      alias_method :pbAbilitiesOnSwitchIn_chrooked_pyre_orig, :pbAbilitiesOnSwitchIn
      def pbAbilitiesOnSwitchIn(onactive)
        @chrooked_pyre_until = -1
        ($chrooked_log.call("[chrooked:pyre] OBS event=switchin reset=until") rescue nil)
        pbAbilitiesOnSwitchIn_chrooked_pyre_orig(onactive)
      end
    end
  end
  $chrooked_pyre_reset_installed = true
  ($chrooked_log.call("[chrooked:pyre] reset hook installed on PokeBattle_Battler") rescue nil)
end

# --- Arm all three installs (immediate if classes are ready, else deferred) -
chrooked_install_pyre_ko if defined?(PokeBattle_Battler) &&
  PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbEffectsAfterHit")
chrooked_install_pyre_damage if defined?(PokeBattle_Move) &&
  PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
chrooked_install_pyre_reset if defined?(PokeBattle_Battler) &&
  PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbAbilitiesOnSwitchIn")

if (!$chrooked_pyre_ko_installed || !$chrooked_pyre_damage_installed || !$chrooked_pyre_reset_installed) && defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_pyre_orig)
      alias_method :update_chrooked_pyre_orig, :update
      def update
        chrooked_install_pyre_ko if !$chrooked_pyre_ko_installed && defined?(PokeBattle_Battler)
        chrooked_install_pyre_damage if !$chrooked_pyre_damage_installed && defined?(PokeBattle_Move)
        chrooked_install_pyre_reset if !$chrooked_pyre_reset_installed && defined?(PokeBattle_Battler)
        update_chrooked_pyre_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:pyre] deferred install armed on Graphics.update") rescue nil)
elsif !defined?(Graphics) && (!$chrooked_pyre_ko_installed || !$chrooked_pyre_damage_installed || !$chrooked_pyre_reset_installed)
  ($chrooked_log.call("[chrooked:pyre] ERROR: PokeBattle classes/Graphics missing at load") rescue nil)
end
