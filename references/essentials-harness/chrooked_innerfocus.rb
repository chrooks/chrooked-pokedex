# chrooked:innerfocus
# ---------------------------------------------------------------------------
# Custom mechanic delta for the Ruleset behavior "innerfocus": "the user's
# Focus Blast never misses." Vanilla Inner Focus no-flinch already exists in
# PokeBattle_Battler#pbFlinch (083) and is NOT touched here.
#
# Overrides PokeBattle_Move#pbAccuracyCheck to return true (always-hit, the
# engine's :NOGUARD convention) when the attacker has Inner Focus AND the move
# is Focus Blast; otherwise calls the original accuracy logic.
#
# HARNESS (Route B log oracle): on EVERY accuracy check this emits one uniform
# observation line the harness driver reads:
#     [chrooked:innerfocus] OBS move=<NAME> if=<true|false> result=<ALWAYS_HIT|NORMAL>
# `if` = attacker has Inner Focus; `result` = whether the custom always-hit
# fired. The three spec test_cases are distinguished by (move, if):
#   FOCUSBLAST + if=true  -> ALWAYS_HIT   (case 1)
#   HYDROPUMP  + if=true  -> NORMAL       (case 2: delta does not leak to other moves)
#   FOCUSBLAST + if=false -> NORMAL       (case 3: delta does not leak to other users)
#
# RUBY 1.8: no prepend / no TracePoint. Override via alias_method chaining;
# defer install via a one-shot on the native Graphics.update (preload runs
# BEFORE Scripts.rxdata defines PokeBattle_Move).
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

def chrooked_install_innerfocus
  return if $chrooked_innerfocus_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbAccuracyCheck")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbAccuracyCheck_chrooked_orig")
      alias_method :pbAccuracyCheck_chrooked_orig, :pbAccuracyCheck
      def pbAccuracyCheck(attacker, opponent)
        is_if = (attacker.hasWorkingAbility(:INNERFOCUS) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if isConst?(@id, PBMoves, :FOCUSBLAST) && is_if
          ($chrooked_log.call("[chrooked:innerfocus] OBS move=#{movename} if=#{is_if} result=ALWAYS_HIT") rescue nil)
          return true
        end
        ($chrooked_log.call("[chrooked:innerfocus] OBS move=#{movename} if=#{is_if} result=NORMAL") rescue nil)
        pbAccuracyCheck_chrooked_orig(attacker, opponent)
      end
    end
  end
  $chrooked_innerfocus_installed = true
  ($chrooked_log.call("[chrooked:innerfocus] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbAccuracyCheck")
  chrooked_install_innerfocus
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_innerfocus_orig)
      alias_method :update_chrooked_innerfocus_orig, :update
      def update
        chrooked_install_innerfocus if !$chrooked_innerfocus_installed && defined?(PokeBattle_Move)
        update_chrooked_innerfocus_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:innerfocus] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:innerfocus] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
