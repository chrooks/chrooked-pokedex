# chrooked:hammerfist
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "hammerfist": the user's punch,
# hammer, and slam moves deal 30% more damage. Unconditional (no HP threshold).
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# purpose-built final-damage multiplier hook (base impl just returns damagemult).
# damagemult is in 0x1000 units. We scale it by 1.3 when the attacker has
# Hammerfist AND the move matches the gate: isPunchingMove? OR a curated set of
# hammer-/slam-named move constants.
#
# GATE: isPunchingMove? OR move in {HAMMERARM, WOODHAMMER, SLAM, BODYSLAM,
#       HEAVYSLAM, IRONHEAD}. A missing constant just means that move isn't
#       boosted (graceful — the isConst? probe is rescued).
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:hammerfist] OBS move=<NAME> ability=<true|false> result=<BOOSTED|NORMAL>
# Cases distinguished by move: matching move + ability -> BOOSTED; else NORMAL.
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

# Curated hammer-/slam-named move set (real Essentials PBS constants, uppercase,
# no spaces). Missing constants degrade gracefully via the rescued isConst? probe.
CHROOKED_HAMMERFIST_MOVES = [:HAMMERARM, :WOODHAMMER, :SLAM, :BODYSLAM, :HEAVYSLAM, :IRONHEAD]

def chrooked_install_hammerfist
  return if $chrooked_hammerfist_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_hammerfist_orig")
      alias_method :pbModifyDamage_chrooked_hammerfist_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_hammerfist_orig(damagemult, attacker, opponent)
        is_ab = (attacker.hasWorkingAbility(:HAMMERFIST) rescue false)
        is_punch = (isPunchingMove? rescue false)
        is_named = CHROOKED_HAMMERFIST_MOVES.any? { |s| (isConst?(@id, PBMoves, s) rescue false) }
        gate = is_punch || is_named
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_ab && gate
          mult = (mult * 1.3).round
          ($chrooked_log.call("[chrooked:hammerfist] OBS move=#{movename} ability=#{is_ab} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:hammerfist] OBS move=#{movename} ability=#{is_ab} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_hammerfist_installed = true
  ($chrooked_log.call("[chrooked:hammerfist] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_hammerfist
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_hammerfist_orig)
      alias_method :update_chrooked_hammerfist_orig, :update
      def update
        chrooked_install_hammerfist if !$chrooked_hammerfist_installed && defined?(PokeBattle_Move)
        update_chrooked_hammerfist_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:hammerfist] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:hammerfist] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
