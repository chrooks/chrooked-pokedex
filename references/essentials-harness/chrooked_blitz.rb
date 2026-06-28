# chrooked:blitz
# ---------------------------------------------------------------------------
# Blitz: on the turn the user is sent out (first turn on the field), its Speed
# is x1.5 and its physical moves deal x1.3 damage. Both are flat multipliers on
# the computed stat / damage modifier, NOT stat-stage changes, so they vanish
# once the Pokemon has been out for a full turn.
#
# "First turn out" gate: attacker.turncount is 0 or 1 on the send-out turn —
# mirrors 16.2's canonical first-turn move Fake Out, which fails when turncount>1
# (turncount is set 0 at switch-in, incremented at end-of-round, line 2978). NOT the
# modern isFirstTurn flag, which does not exist in 16.2. (per FACTS;
# in-game will confirm the 0-vs-1 boundary).
#
# Two independent Seams, each aliased separately with its own installed flag and
# its own deferred install on Graphics.update (Ruby 1.8: alias_method chaining,
# NO prepend/TracePoint; call _orig first):
#
#   1. SPEED — PokeBattle_Battler#pbSpeed() (verified line 677, Data/Scripts.rxdata).
#      Returns the computed speed (SlowStart already halves it when turncount<=5).
#      We multiply the _orig result by 1.5 (rounded) when self.hasWorkingAbility(:BLITZ)
#      and self.turncount == 0.
#
#   2. DAMAGE — PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent).
#      Returns the multiplier in 0x1000 units. We multiply by 1.3 when the attacker
#      has Blitz, attacker.turncount == 0, and the move's resolved type is physical
#      (Chrooked.move_physical?(self, movetype), movetype = pbType(@type, attacker, opponent)).
#
# HARNESS (Route B log oracle): each gate firing logs one OBS line:
#     [chrooked:blitz] OBS hook=speed blitz=<bool> turncount=<n> result=<BOOSTED|NORMAL>
#     [chrooked:blitz] OBS hook=damage move=<NAME> blitz=<bool> turncount=<n> phys=<bool> result=<BOOSTED|NORMAL>
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

# --- Hook 1: Speed x1.5 on the send-out turn -------------------------------

def chrooked_install_blitz_speed
  return if $chrooked_blitz_speed_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbSpeed")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbSpeed_chrooked_blitz_orig")
      alias_method :pbSpeed_chrooked_blitz_orig, :pbSpeed
      def pbSpeed
        spd = pbSpeed_chrooked_blitz_orig
        is_blitz = (self.hasWorkingAbility(:BLITZ) rescue false)
        tc = (self.turncount rescue -1)
        if is_blitz && (tc == 0 || tc == 1)
          spd = (spd * 1.5).round
          ($chrooked_log.call("[chrooked:blitz] OBS hook=speed blitz=#{is_blitz} turncount=#{tc} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:blitz] OBS hook=speed blitz=#{is_blitz} turncount=#{tc} result=NORMAL") rescue nil)
        end
        spd
      end
    end
  end
  $chrooked_blitz_speed_installed = true
  ($chrooked_log.call("[chrooked:blitz] installed pbSpeed on PokeBattle_Battler") rescue nil)
end

# --- Hook 2: physical damage x1.3 on the send-out turn ---------------------

def chrooked_install_blitz_damage
  return if $chrooked_blitz_damage_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_blitz_orig")
      alias_method :pbModifyDamage_chrooked_blitz_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_blitz_orig(damagemult, attacker, opponent)
        is_blitz = (attacker.hasWorkingAbility(:BLITZ) rescue false)
        tc = (attacker.turncount rescue -1)
        movetype = (Chrooked.move_type(self, attacker, opponent) rescue nil)
        is_phys = (Chrooked.move_physical?(self, movetype) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_blitz && (tc == 0 || tc == 1) && is_phys
          mult = (mult * 1.3).round
          ($chrooked_log.call("[chrooked:blitz] OBS hook=damage move=#{movename} blitz=#{is_blitz} turncount=#{tc} phys=#{is_phys} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:blitz] OBS hook=damage move=#{movename} blitz=#{is_blitz} turncount=#{tc} phys=#{is_phys} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_blitz_damage_installed = true
  ($chrooked_log.call("[chrooked:blitz] installed pbModifyDamage on PokeBattle_Move") rescue nil)
end

# --- Install / deferred-install for hook 1 (speed) -------------------------

if defined?(PokeBattle_Battler) && PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbSpeed")
  chrooked_install_blitz_speed
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_blitz_speed_orig)
      alias_method :update_chrooked_blitz_speed_orig, :update
      def update
        chrooked_install_blitz_speed if !$chrooked_blitz_speed_installed && defined?(PokeBattle_Battler)
        update_chrooked_blitz_speed_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:blitz] deferred install (speed) armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:blitz] ERROR: PokeBattle_Battler/Graphics missing at load (speed)") rescue nil)
end

# --- Install / deferred-install for hook 2 (damage) ------------------------

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_blitz_damage
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_blitz_damage_orig)
      alias_method :update_chrooked_blitz_damage_orig, :update
      def update
        chrooked_install_blitz_damage if !$chrooked_blitz_damage_installed && defined?(PokeBattle_Move)
        update_chrooked_blitz_damage_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:blitz] deferred install (damage) armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:blitz] ERROR: PokeBattle_Move/Graphics missing at load (damage)") rescue nil)
end
