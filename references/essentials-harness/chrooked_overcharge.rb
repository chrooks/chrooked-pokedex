# chrooked:overcharge
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "overcharge": while at low HP, the
# user's Electric-type moves deal 50% more damage. HP-gated (like Blaze): the
# 1.5x applies ONLY when current HP <= (totalhp / 3).floor AND move type is
# Electric.
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# purpose-built final-damage multiplier hook (base impl just returns damagemult;
# verified in the extracted 084_PokeBattle_Move). damagemult is in 0x1000 units.
# We scale it by 1.5 when the attacker has Overcharge, the move's resolved type
# is Electric, AND the attacker is at or below 1/3 max HP. Same Seam as kindle,
# but with the pinch-ability HP threshold added back in.
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:overcharge] OBS move=<NAME> ability=<true|false> hp_low=<true|false> result=<BOOSTED|NORMAL>
# Cases distinguished by move + HP: Electric move + ability + low HP -> BOOSTED;
# non-Electric OR full HP -> NORMAL. hp_low lets the harness tell the at-1/4-HP
# case from the full-HP case (both use Thunderbolt, differ only by HP).
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

def chrooked_install_overcharge
  return if $chrooked_overcharge_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_overcharge_orig")
      alias_method :pbModifyDamage_chrooked_overcharge_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_overcharge_orig(damagemult, attacker, opponent)
        is_overcharge = (attacker.hasWorkingAbility(:OVERCHARGE) rescue false)
        movetype = (pbType(@type, attacker, opponent) rescue -1)
        is_electric = (isConst?(movetype, PBTypes, :ELECTRIC) rescue false)
        hp_low = (attacker.hp <= (attacker.totalhp / 3).floor rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_overcharge && is_electric && hp_low
          mult = (mult * 1.5).round
          ($chrooked_log.call("[chrooked:overcharge] OBS move=#{movename} ability=#{is_overcharge} hp_low=#{hp_low} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:overcharge] OBS move=#{movename} ability=#{is_overcharge} hp_low=#{hp_low} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_overcharge_installed = true
  ($chrooked_log.call("[chrooked:overcharge] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_overcharge
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_overcharge_orig)
      alias_method :update_chrooked_overcharge_orig, :update
      def update
        chrooked_install_overcharge if !$chrooked_overcharge_installed && defined?(PokeBattle_Move)
        update_chrooked_overcharge_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:overcharge] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:overcharge] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
