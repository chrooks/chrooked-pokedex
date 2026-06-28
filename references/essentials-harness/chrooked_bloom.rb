# chrooked:bloom
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "bloom": the user's Grass-type moves
# deal 50% more damage. Unconditional (unlike Overgrow, no HP threshold).
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# purpose-built final-damage multiplier hook (base impl just returns damagemult;
# verified in the extracted 084_PokeBattle_Move). damagemult is in 0x1000 units.
# We scale it by 1.5 when the attacker has Bloom and the move's resolved type is
# Grass. This is a DIFFERENT Seam than innerfocus (accuracy), which is the point:
# it proves the harness generalizes across battle hooks.
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:bloom] OBS move=<NAME> ability=<true|false> result=<BOOSTED|NORMAL>
# Cases distinguished by move: Grass move + bloom -> BOOSTED; non-Grass -> NORMAL.
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

def chrooked_install_bloom
  return if $chrooked_bloom_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_bloom_orig")
      alias_method :pbModifyDamage_chrooked_bloom_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_bloom_orig(damagemult, attacker, opponent)
        is_bloom = (attacker.hasWorkingAbility(:BLOOM) rescue false)
        movetype = (Chrooked.move_type(self, attacker, opponent) rescue nil)
        is_grass = (isConst?(movetype, PBTypes, :GRASS) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_bloom && is_grass
          mult = (mult * 1.5).round
          ($chrooked_log.call("[chrooked:bloom] OBS move=#{movename} ability=#{is_bloom} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:bloom] OBS move=#{movename} ability=#{is_bloom} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_bloom_installed = true
  ($chrooked_log.call("[chrooked:bloom] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_bloom
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_bloom_orig)
      alias_method :update_chrooked_bloom_orig, :update
      def update
        chrooked_install_bloom if !$chrooked_bloom_installed && defined?(PokeBattle_Move)
        update_chrooked_bloom_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:bloom] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:bloom] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
