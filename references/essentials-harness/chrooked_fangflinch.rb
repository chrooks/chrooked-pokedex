# chrooked:fangflinch
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "fangflinch": the custom stat-drop fangs
# (DRACONICFANG, LITHICFANG, METALLICFANG, TECTONICFANG, LOVELYBITE) are biting moves
# that BOTH lower a stat AND may flinch. 16.2 has no bundled stat-drop+flinch funccode,
# so the data layer emits the stat-drop funccode (042/043/045/047 — the engine lowers
# the stat natively) and THIS plugin adds the 10% flinch half on top.
#
# Seam (verified in Data/Scripts.rxdata, 16.2): PokeBattle_Battler#
# pbEffectsOnDealingDamage(move, user, target, damage) — the same post-damage hook
# chrooked_venomous rides. It runs after the USER deals damage, for ANY move, so it is
# not subclass-specific (the fang funccodes 042/043/... each have their own move class,
# but this battler-level hook fires for all of them). Alias-chained on PokeBattle_Battler.
#
# Gate: damage dealt (damage && damage>0) AND move is one of the chrooked fang ids.
# Flinch: 10% roll @battle.pbRandom(100)<10, then target.pbFlinch(user) — the engine's
# own flinch helper, which enforces Inner Focus / substitute / already-moved gating.
#
# SEAM TO CONFIRM in the harness pass: pbFlinch's arity on this build. Vanilla flinch
# moves call it (innerfocus cites PokeBattle_Battler#pbFlinch, code 083); the call is
# wrapped in `rescue` so a signature mismatch no-ops (no crash) and shows up as a FAIL
# in the log oracle rather than a broken battle.
#
# HARNESS (Route B log oracle): on a damaging fang hit, logs one line:
#     [chrooked:fangflinch] OBS move=<NAME> fang=true result=<FLINCHED|FLINCH_ROLL_FAILED|FLINCH_BLOCKED>
# A non-fang damaging hit logs nothing (the gate filters it out).
#
# RUBY 1.8: alias_method chaining; deferred install on Graphics.update.
# ---------------------------------------------------------------------------

CHROOKED_FANGFLINCH_MOVES = [:DRACONICFANG, :LITHICFANG, :METALLICFANG, :TECTONICFANG, :LOVELYBITE]
CHROOKED_FANGFLINCH_CHANCE = 10

unless defined?($chrooked_log) && $chrooked_log
  $chrooked_log = lambda do |msg|
    begin
      d = File.expand_path(File.dirname(__FILE__))
      File.open(File.join(d, "chrooked_load.log"), "a") { |f| f.puts(msg) }
    rescue Exception
    end
  end
end

def chrooked_install_fangflinch
  return if $chrooked_fangflinch_installed
  return unless defined?(PokeBattle_Battler) && defined?(Chrooked)
  # The gate+flinch logic as a battler instance method (idempotent). The compat shim's
  # install_post_damage wires it to whichever post-damage seam this engine has (16.2
  # pbEffectsOnDealingDamage or IF2 pbEffectsOnMakingHit) and feeds it the damage dealt.
  unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("chrooked_fangflinch_apply")
    PokeBattle_Battler.class_eval do
      def chrooked_fangflinch_apply(move, user, target, damage)
        begin
          dealt = (damage && damage > 0)
          is_fang = CHROOKED_FANGFLINCH_MOVES.any? { |s| Chrooked.move_is?(move, s) }
          if dealt && is_fang && target && !target.fainted?
            movename = (getConstantName(PBMoves, move.id) rescue move.id.to_s)
            if @battle.pbRandom(100) < CHROOKED_FANGFLINCH_CHANCE
              before = (target.effects[PBEffects::Flinch] rescue false)
              (target.pbFlinch(user) rescue nil)
              after = (target.effects[PBEffects::Flinch] rescue false)
              result = (after && !before) ? "FLINCHED" : "FLINCH_BLOCKED"
              ($chrooked_log.call("[chrooked:fangflinch] OBS move=#{movename} fang=true result=#{result}") rescue nil)
            else
              ($chrooked_log.call("[chrooked:fangflinch] OBS move=#{movename} fang=true result=FLINCH_ROLL_FAILED") rescue nil)
            end
          end
        rescue Exception
        end
      end
    end
  end
  return unless Chrooked.install_post_damage("chrooked_fangflinch_apply", "pbOnDamage_chrooked_fangflinch_orig")
  $chrooked_fangflinch_installed = true
  ($chrooked_log.call("[chrooked:fangflinch] installed (post-damage seam)") rescue nil)
end

if defined?(PokeBattle_Battler) && defined?(Chrooked)
  chrooked_install_fangflinch
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_fangflinch_orig)
      alias_method :update_chrooked_fangflinch_orig, :update
      def update
        chrooked_install_fangflinch if !$chrooked_fangflinch_installed && defined?(PokeBattle_Battler)
        update_chrooked_fangflinch_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:fangflinch] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:fangflinch] ERROR: neither PokeBattle_Battler nor Graphics defined at load") rescue nil)
end
