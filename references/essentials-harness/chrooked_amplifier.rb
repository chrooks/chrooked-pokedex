# chrooked:amplifier
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "amplifier". Two effects:
#   1. The user's sound-based moves deal 30% more damage.
#   2. The user's single-target sound moves expand to hit ALL adjacent foes.
# Engine-neutral intent: ruleset/behaviors/amplifier.yaml.
#
# CROSS-ENGINE: the plugins are written for stock Essentials 16.2 but several
# targets (notably IF2) are a 16.x FORK with renamed battle methods. The two gate
# predicates differ by engine, so we pick the present one by respond_to? instead
# of hardcoding a name (matches references/essentials-harness/chrooked_compat.rb):
#   * sound flag   — 16.2 `isSoundBased?`        / IF2 `soundMove?`
#   * has ability  — 16.2 `hasWorkingAbility(:X)` / IF2 `hasActiveAbility?(:X)`
# (Before this, the boost gated on the 16.2 names only and rescued false on IF2,
# so the +30% silently never fired there.)
#
# EFFECT 1 — Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent),
# 16.2's final-damage multiplier hook (damagemult in 0x1000 units; present on IF2
# too). Scale by 1.3 when the attacker has Amplifier AND the move is sound-based.
#
# EFFECT 2 — Seam: PokeBattle_Move#pbTarget(user). On the IF2 fork this returns a
# GameData::Target (symbol-id API); a single adjacent-foe target (:NearFoe/:NearOther)
# is rewritten to :AllNearFoes when the user has Amplifier and the move is a damaging
# sound move. Installed ONLY where GameData::Target exists — stock 16.2 uses the old
# integer PBTargets module instead, which we can't verify on this machine, so the
# expansion stays a safe no-op there (matches the spec: never implemented in C either).
#
# HARNESS (Route B log oracle): pbModifyDamage logs BOOSTED/NORMAL; pbTarget logs
# EXPANDED when it widens a target. Lines tagged [chrooked:amplifier] OBS ...
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

# Cross-engine gate predicates (top-level so the aliased instance methods can call
# them). Each tries the engine's own method name and rescues to a safe false.
def chrooked_amplifier_sound?(move)
  return (move.soundMove? rescue false)    if move.respond_to?(:soundMove?)
  return (move.isSoundBased? rescue false) if move.respond_to?(:isSoundBased?)
  false
end

def chrooked_amplifier_user_has?(battler)
  return false unless battler
  return (battler.hasActiveAbility?(:AMPLIFIER) rescue false) if battler.respond_to?(:hasActiveAbility?)
  return (battler.hasWorkingAbility(:AMPLIFIER) rescue false) if battler.respond_to?(:hasWorkingAbility)
  false
end

def chrooked_amplifier_movename(move)
  (getConstantName(PBMoves, move.id) rescue (move.id.to_s rescue "?"))
end

def chrooked_install_amplifier
  return if $chrooked_amplifier_installed
  return unless defined?(PokeBattle_Move)
  method_names = PokeBattle_Move.instance_methods.map { |m| m.to_s }
  return unless method_names.include?("pbModifyDamage")

  PokeBattle_Move.class_eval do
    # --- EFFECT 1: +30% sound damage ---
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_amplifier_orig")
      alias_method :pbModifyDamage_chrooked_amplifier_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_amplifier_orig(damagemult, attacker, opponent)
        is_ab = chrooked_amplifier_user_has?(attacker)
        is_sound = chrooked_amplifier_sound?(self)
        movename = chrooked_amplifier_movename(self)
        if is_ab && is_sound
          mult = (mult * 1.3).round
          ($chrooked_log.call("[chrooked:amplifier] OBS move=#{movename} ability=#{is_ab} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:amplifier] OBS move=#{movename} ability=#{is_ab} result=NORMAL") rescue nil)
        end
        mult
      end
    end

    # --- EFFECT 2: single-foe sound move -> all adjacent foes (GameData::Target engines only) ---
    if defined?(GameData) && defined?(GameData::Target) &&
       !instance_methods(false).map { |m| m.to_s }.include?("pbTarget_chrooked_amplifier_orig")
      alias_method :pbTarget_chrooked_amplifier_orig, :pbTarget
      def pbTarget(user)
        t = pbTarget_chrooked_amplifier_orig(user)
        begin
          if user && chrooked_amplifier_user_has?(user) && chrooked_amplifier_sound?(self) &&
             (damagingMove? rescue true) && t && (t.id == :NearFoe || t.id == :NearOther)
            ($chrooked_log.call("[chrooked:amplifier] OBS move=#{chrooked_amplifier_movename(self)} target=#{t.id} result=EXPANDED->AllNearFoes") rescue nil)
            return GameData::Target.get(:AllNearFoes)
          end
        rescue Exception => e
          ($chrooked_log.call("[chrooked:amplifier] pbTarget ERROR: #{e.class}: #{e.message}") rescue nil)
        end
        t
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
