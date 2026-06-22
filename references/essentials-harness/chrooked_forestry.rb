# chrooked:forestry
# ---------------------------------------------------------------------------
# Forestry: the user's moves deal 1.3x while Grassy Terrain is up and the user
# is grounded (a terrain-gated power boost).
#
# Seam (verified 16.2, Data/Scripts.rxdata): PokeBattle_Move#pbModifyDamage(
# damagemult, attacker, opponent) — the 0x1000-unit final-damage multiplier hook.
# Grassy Terrain is @battle.field.effects[PBEffects::GrassyTerrain]>0 (same check
# the engine's own Grassy Terrain damage code uses). Grounded = !attacker.isAirborne?
# (PokeBattle_Battler#isAirborne?, line 664).
#
# RUBY 1.8: alias_method chaining; deferred install on Graphics.update; guarded
# $chrooked_log; unique _chrooked_forestry names; calls _orig first.
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

def chrooked_install_forestry
  return if $chrooked_forestry_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_forestry_orig")
      alias_method :pbModifyDamage_chrooked_forestry_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_forestry_orig(damagemult, attacker, opponent)
        is_for = (attacker.hasWorkingAbility(:FORESTRY) rescue false)
        terrain = ((@battle.field.effects[PBEffects::GrassyTerrain] > 0) rescue false)
        grounded = (!attacker.isAirborne? rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_for && terrain && grounded
          mult = (mult * 1.3).round
          ($chrooked_log.call("[chrooked:forestry] OBS move=#{movename} ability=true terrain=true grounded=true result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:forestry] OBS move=#{movename} ability=#{is_for} terrain=#{terrain} grounded=#{grounded} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_forestry_installed = true
  ($chrooked_log.call("[chrooked:forestry] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_forestry
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_forestry_orig)
      alias_method :update_chrooked_forestry_orig, :update
      def update
        chrooked_install_forestry if !$chrooked_forestry_installed && defined?(PokeBattle_Move)
        update_chrooked_forestry_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:forestry] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:forestry] ERROR: PokeBattle_Move/Graphics missing at load") rescue nil)
end
