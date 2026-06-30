# chrooked:excalibur
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "excalibur": the MOVE :EXCALIBUR is
# always at least super effective (2x) against Dragon-type targets. This is a
# MOVE behavior gated on the move id, NOT an ability.
#
# Seam (verified 16.2, Data/Scripts.rxdata): PokeBattle_Move#pbTypeModifier(
# type, attacker, opponent) returns effectiveness on a base-8 scale (8 = 1x
# neutral, 0 = immune, 16 = 2x super effective, 4 = 0.5x). We alias it, call the
# original first, and when the move is EXCALIBUR and the opponent has the Dragon
# type, return [_orig, 16].max so effectiveness is at least 2x. The max() keeps
# the chart's own multiplier whenever it is already higher (e.g. a Dragon/Flying
# target where another type pushes it past 2x).
#
# Gate: isConst?(@id, PBMoves, :EXCALIBUR) AND opponent.pbHasType?(:DRAGON).
# No ability check (this gates on the move id). No custom Move subclass needed.
#
# HARNESS (Route B log oracle): each gate firing logs one line:
#     [chrooked:excalibur] OBS move=<NAME> dragon=<true|false> result=<FORCED_SE|NORMAL>
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

def chrooked_install_excalibur
  return if $chrooked_excalibur_installed
  return unless defined?(PokeBattle_Move) && defined?(Chrooked)
  unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("chrooked_excalibur_typemod_apply")
    PokeBattle_Move.class_eval do
      def chrooked_excalibur_typemod_apply(mod, type, attacker, opponent)
        is_excalibur = Chrooked.move_is?(self, :EXCALIBUR)
        is_dragon = (opponent && opponent.pbHasType?(:DRAGON) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_excalibur && is_dragon
          mod = [mod, 16].max   # super-effective on both engines' 8-base scale
          ($chrooked_log.call("[chrooked:excalibur] OBS move=#{movename} dragon=#{is_dragon} result=FORCED_SE") rescue nil)
        else
          ($chrooked_log.call("[chrooked:excalibur] OBS move=#{movename} dragon=#{is_dragon} result=NORMAL") rescue nil)
        end
        mod
      end
    end
  end
  return unless Chrooked.install_typemod("chrooked_excalibur_typemod_apply", "pbTypeMod_chrooked_excalibur_orig")
  $chrooked_excalibur_installed = true
  ($chrooked_log.call("[chrooked:excalibur] installed type-mod (seam)") rescue nil)
end

if defined?(PokeBattle_Move) && defined?(Chrooked)
  chrooked_install_excalibur
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_excalibur_orig)
      alias_method :update_chrooked_excalibur_orig, :update
      def update
        chrooked_install_excalibur if !$chrooked_excalibur_installed && defined?(PokeBattle_Move)
        update_chrooked_excalibur_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:excalibur] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:excalibur] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
