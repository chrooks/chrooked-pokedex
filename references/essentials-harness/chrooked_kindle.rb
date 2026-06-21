# chrooked:kindle
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "kindle": the user's Fire-type moves
# deal 50% more damage. Unconditional (unlike Blaze, no HP threshold).
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# purpose-built final-damage multiplier hook (base impl just returns damagemult;
# verified in the extracted 084_PokeBattle_Move). damagemult is in 0x1000 units.
# We scale it by 1.5 when the attacker has Kindle and the move's resolved type is
# Fire. This is a DIFFERENT Seam than innerfocus (accuracy), which is the point:
# it proves the harness generalizes across battle hooks.
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:kindle] OBS move=<NAME> kindle=<true|false> result=<BOOSTED|NORMAL>
# Cases distinguished by move: Fire move + kindle -> BOOSTED; non-Fire -> NORMAL.
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

def chrooked_install_kindle
  return if $chrooked_kindle_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_orig")
      alias_method :pbModifyDamage_chrooked_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_orig(damagemult, attacker, opponent)
        is_kindle = (attacker.hasWorkingAbility(:KINDLE) rescue false)
        movetype = (pbType(@type, attacker, opponent) rescue -1)
        is_fire = (isConst?(movetype, PBTypes, :FIRE) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_kindle && is_fire
          mult = (mult * 1.5).round
          ($chrooked_log.call("[chrooked:kindle] OBS move=#{movename} kindle=#{is_kindle} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:kindle] OBS move=#{movename} kindle=#{is_kindle} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_kindle_installed = true
  ($chrooked_log.call("[chrooked:kindle] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_kindle
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_kindle_orig)
      alias_method :update_chrooked_kindle_orig, :update
      def update
        chrooked_install_kindle if !$chrooked_kindle_installed && defined?(PokeBattle_Move)
        update_chrooked_kindle_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:kindle] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:kindle] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
