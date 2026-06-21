# chrooked:sledgehammer
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "sledgehammer": the user's
# hammer/slam moves deal 30% more damage. Conditional on a curated move-name
# set (the hammer/slam grouping), NOT a punch flag — Sledgehammer is the
# hammer/slam subset of Hammerfist and deliberately excludes punching moves.
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# final-damage multiplier hook (base impl just returns damagemult). damagemult
# is in 0x1000 units. We scale it by 1.3 when the attacker has Sledgehammer AND
# the move is in the curated hammer/slam set.
#
# GATE: a curated HAMMER/SLAM move-name set (no punch half). Matched against
# real Essentials PBS move constants via isConst?(@id, PBMoves, sym), guarded so
# a missing constant just means that move isn't boosted (graceful).
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:sledgehammer] OBS move=<NAME> ability=<true|false> result=<BOOSTED|NORMAL>
# Cases distinguished by move: hammer/slam move + ability -> BOOSTED; else NORMAL.
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

# Curated hammer/slam set from the behavior spec — hammer- and slam-named moves
# only, no punching moves. Real Essentials PBS move constants (uppercase).
$chrooked_sledgehammer_moves = [
  :SLAM, :BODYSLAM, :HAMMERARM, :IRONHEAD,
  :WOODHAMMER, :HEAVYSLAM, :ICEHAMMER, :GIGATONHAMMER
]

def chrooked_install_sledgehammer
  return if $chrooked_sledgehammer_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_sledgehammer_orig")
      alias_method :pbModifyDamage_chrooked_sledgehammer_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_sledgehammer_orig(damagemult, attacker, opponent)
        is_ab = (attacker.hasWorkingAbility(:SLEDGEHAMMER) rescue false)
        is_hammer = $chrooked_sledgehammer_moves.any? { |s| (isConst?(@id, PBMoves, s) rescue false) }
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_ab && is_hammer
          mult = (mult * 1.3).round
          ($chrooked_log.call("[chrooked:sledgehammer] OBS move=#{movename} ability=#{is_ab} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:sledgehammer] OBS move=#{movename} ability=#{is_ab} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_sledgehammer_installed = true
  ($chrooked_log.call("[chrooked:sledgehammer] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_sledgehammer
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_sledgehammer_orig)
      alias_method :update_chrooked_sledgehammer_orig, :update
      def update
        chrooked_install_sledgehammer if !$chrooked_sledgehammer_installed && defined?(PokeBattle_Move)
        update_chrooked_sledgehammer_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:sledgehammer] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:sledgehammer] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
