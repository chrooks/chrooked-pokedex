# chrooked:deluge
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "deluge": the user's Water-type moves
# deal 50% more damage. Unconditional (unlike Torrent, no HP threshold).
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# purpose-built final-damage multiplier hook (base impl just returns damagemult;
# verified in the extracted 084_PokeBattle_Move). damagemult is in 0x1000 units.
# We scale it by 1.5 when the attacker has Deluge and the move's resolved type is
# Water. This is a DIFFERENT Seam than innerfocus (accuracy), which is the point:
# it proves the harness generalizes across battle hooks.
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:deluge] OBS move=<NAME> ability=<true|false> result=<BOOSTED|NORMAL>
# Cases distinguished by move: Water move + deluge -> BOOSTED; non-Water -> NORMAL.
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

def chrooked_install_deluge
  return if $chrooked_deluge_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_deluge_orig")
      alias_method :pbModifyDamage_chrooked_deluge_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_deluge_orig(damagemult, attacker, opponent)
        is_deluge = (attacker.hasWorkingAbility(:DELUGE) rescue false)
        movetype = (Chrooked.move_type(self, attacker, opponent) rescue nil)
        is_water = (isConst?(movetype, PBTypes, :WATER) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_deluge && is_water
          mult = (mult * 1.5).round
          ($chrooked_log.call("[chrooked:deluge] OBS move=#{movename} ability=#{is_deluge} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:deluge] OBS move=#{movename} ability=#{is_deluge} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_deluge_installed = true
  ($chrooked_log.call("[chrooked:deluge] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_deluge
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_deluge_orig)
      alias_method :update_chrooked_deluge_orig, :update
      def update
        chrooked_install_deluge if !$chrooked_deluge_installed && defined?(PokeBattle_Move)
        update_chrooked_deluge_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:deluge] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:deluge] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
