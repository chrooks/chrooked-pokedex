# chrooked:infernalmaw
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "infernalmaw" (ability :INFERNALMAW).
# TWO plugins-in-one, each on a DIFFERENT class:
#
#   1) DAMAGE  — PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent):
#      when the attacker has Infernal Maw and the move is a biting move
#      (isBitingMove?, verified flag), scale the final multiplier by 1.3.
#      damagemult is in 0x1000 units; base impl just returns damagemult.
#
#   2) BURN + FLINCH — after-hit seam (compat install_after_move): after a damaging
#      biting move connects, roll 30% to burn the target (if burnable) AND an
#      independent flat 30% to flinch it. Gated on hasWorkingAbility(:INFERNALMAW),
#      actual damage dealt, and the move's bitingMove flag.
#
# Both methods are aliased onto their own class, and BOTH installs are deferred
# onto Graphics.update so they arm regardless of script load order. Mirrors the
# alias/defer/guarded-logger structure of chrooked_kindle.rb.
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:infernalmaw] OBS move=<NAME> ability=<true|false> result=<BOOSTED|NORMAL>
# When the burn roll fires, that line also carries burn=<true|false>.
# Cases distinguished by move: biting move + ability -> BOOSTED; else -> NORMAL.
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

# --- Install 1: 1.3x biting-move damage on PokeBattle_Move ------------------
def chrooked_install_infernalmaw_damage
  return if $chrooked_infernalmaw_damage_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_infernalmaw_orig")
      alias_method :pbModifyDamage_chrooked_infernalmaw_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_infernalmaw_orig(damagemult, attacker, opponent)
        is_ab = (attacker.hasWorkingAbility(:INFERNALMAW) rescue false)
        is_biting = (isBitingMove? rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_ab && is_biting
          mult = (mult * 1.3).round
          ($chrooked_log.call("[chrooked:infernalmaw] OBS move=#{movename} ability=#{is_ab} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:infernalmaw] OBS move=#{movename} ability=#{is_ab} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_infernalmaw_damage_installed = true
  ($chrooked_log.call("[chrooked:infernalmaw] damage install on PokeBattle_Move") rescue nil)
end

# --- Install 2: 20% burn-after-hit on PokeBattle_Battler -------------------
# Via the compat shim's install_after_move (16.2 pbEffectsAfterHit / IF2
# pbEffectsAfterMove), normalized to one (user, target, move) call per target.
# Damage dealt read from target.damageState.hpLost (present on both engines) rather
# than turneffects, which IF2's per-move seam doesn't pass.
def chrooked_install_infernalmaw_burn
  return if $chrooked_infernalmaw_burn_installed
  return unless defined?(PokeBattle_Battler) && defined?(Chrooked)
  unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("chrooked_infernalmaw_burn_apply")
    PokeBattle_Battler.class_eval do
      def chrooked_infernalmaw_burn_apply(user, target, thismove)
        begin
          return unless user && target
          return unless (user.hasWorkingAbility(:INFERNALMAW) rescue false)
          dealt = (target.damageState.hpLost rescue 0)
          dealt = 0 if dealt.nil?
          return unless dealt > 0
          is_biting = (thismove.bitingMove? rescue (thismove.isBitingMove? rescue false))
          return unless is_biting
          movename = (thismove.name rescue thismove)
          # 30% burn (independent roll)
          if @battle.pbRandom(100) < 30
            can_burn = (target.pbCanBurn?(user, false, thismove) rescue false)
            target.pbBurn(user) if can_burn
            ($chrooked_log.call("[chrooked:infernalmaw] OBS move=#{movename} ability=true burn=#{can_burn}") rescue nil)
          end
          # flat 30% flinch (independent roll; engine's pbFlinch enforces Inner Focus/etc.)
          fainted = (target.fainted? rescue (target.isFainted? rescue false))
          if !fainted && @battle.pbRandom(100) < 30
            (target.pbFlinch(user) rescue nil)
            ($chrooked_log.call("[chrooked:infernalmaw] OBS move=#{movename} ability=true flinch=true") rescue nil)
          end
        rescue Exception
        end
      end
    end
  end
  return unless Chrooked.install_after_move("chrooked_infernalmaw_burn_apply", "pbAfterMove_chrooked_infernalmaw_orig")
  $chrooked_infernalmaw_burn_installed = true
  ($chrooked_log.call("[chrooked:infernalmaw] burn install (after-move seam)") rescue nil)
end

# --- Arm both installs (immediate if classes are ready, else deferred) ------
if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_infernalmaw_damage
end
if defined?(PokeBattle_Battler) && defined?(Chrooked)
  chrooked_install_infernalmaw_burn
end

if (!$chrooked_infernalmaw_damage_installed || !$chrooked_infernalmaw_burn_installed) && defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_infernalmaw_orig)
      alias_method :update_chrooked_infernalmaw_orig, :update
      def update
        if !$chrooked_infernalmaw_damage_installed && defined?(PokeBattle_Move)
          chrooked_install_infernalmaw_damage
        end
        if !$chrooked_infernalmaw_burn_installed && defined?(PokeBattle_Battler)
          chrooked_install_infernalmaw_burn
        end
        update_chrooked_infernalmaw_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:infernalmaw] deferred install armed on Graphics.update") rescue nil)
elsif !defined?(Graphics) && (!$chrooked_infernalmaw_damage_installed || !$chrooked_infernalmaw_burn_installed)
  ($chrooked_log.call("[chrooked:infernalmaw] ERROR: classes not defined and no Graphics to defer onto") rescue nil)
end
