# chrooked:amplifier
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "amplifier": the user's sound-based
# moves deal 30% more damage. Engine-neutral intent (ruleset/behaviors/amplifier.yaml):
# "Sound moves deal 30% more damage." The second intended effect (target-set
# expansion to all adjacent foes) is intent-only and NOT implemented here — it is
# a target override, not a damage calc, and most sound moves already spread.
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# purpose-built final-damage multiplier hook (base impl just returns damagemult).
# damagemult is in 0x1000 units. We scale it by 1.3 when the attacker has
# Amplifier AND the move is sound-based.
#
# GATE: isSoundBased? (the verified Essentials 16.2 sound flag). We use the
# move's own predicate so the boost tracks exactly the engine's notion of a
# sound move (Hyper Voice, Boomburst, etc.); no hand-maintained move list.
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:amplifier] OBS move=<NAME> ability=<true|false> result=<BOOSTED|NORMAL>
# Cases distinguished by move: sound move + amplifier -> BOOSTED; non-sound -> NORMAL.
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

def chrooked_install_amplifier
  return if $chrooked_amplifier_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_amplifier_orig")
      alias_method :pbModifyDamage_chrooked_amplifier_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_amplifier_orig(damagemult, attacker, opponent)
        is_ab = (attacker.hasWorkingAbility(:AMPLIFIER) rescue false)
        is_sound = (isSoundBased? rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_ab && is_sound
          mult = (mult * 1.3).round
          ($chrooked_log.call("[chrooked:amplifier] OBS move=#{movename} ability=#{is_ab} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:amplifier] OBS move=#{movename} ability=#{is_ab} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_amplifier_installed = true
  ($chrooked_log.call("[chrooked:amplifier] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_amplifier
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_amplifier_orig)
      alias_method :update_chrooked_amplifier_orig, :update
      def update
        chrooked_install_amplifier if !$chrooked_amplifier_installed && defined?(PokeBattle_Move)
        update_chrooked_amplifier_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:amplifier] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:amplifier] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
