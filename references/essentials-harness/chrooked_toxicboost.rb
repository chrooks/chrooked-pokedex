# chrooked:toxicboost
# ---------------------------------------------------------------------------
# Toxic Boost: while the user is poisoned, its physical moves deal x1.5 damage.
# (Mainline canon boosts the +50% Attack stat; this fork applies it as a flat
# 1.5x physical-damage modifier — same shape as the Flare Boost special clone.)
#
# Single verified Seam (Ruby 1.8: alias_method chaining, NO prepend/TracePoint;
# call _orig first; deferred install on Graphics.update):
#
#   DAMAGE — PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent).
#     `attacker` is the user; returns the multiplier in 0x1000 units. We multiply
#     the _orig result by 1.5 (rounded) when:
#       - attacker.hasWorkingAbility(:TOXICBOOST), AND
#       - attacker.status == PBStatuses::POISON (regular OR bad/toxic poison both
#         report PBStatuses::POISON), AND
#       - the move's resolved type is physical: movetype = pbType(@type, attacker,
#         opponent); pbIsPhysical?(movetype).
#
# NOT-PORTED: the end-of-turn self-poison immunity (skip the poison residual for
#   a Toxic Boost holder). There is NO verified end-of-round / residual-damage
#   Seam in FACTS, and we do not guess unverified methods. Per the spec, we drop
#   this half rather than port it blind. The holder still takes normal poison
#   chip in-game until a verified residual Seam is confirmed.
#
# No stateful per-battler ivar is used, so no pbAbilitiesOnSwitchIn reset is
# needed (the gate is a pure read of live status + ability + move type).
#
# HARNESS (Route B log oracle): each gate firing logs one OBS line:
#     [chrooked:toxicboost] OBS move=<NAME> toxicboost=<bool> poison=<bool> phys=<bool> result=<BOOSTED|NORMAL>
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

# --- Hook: physical damage x1.5 while poisoned -----------------------------

def chrooked_install_toxicboost_damage
  return if $chrooked_toxicboost_damage_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_toxicboost_orig")
      alias_method :pbModifyDamage_chrooked_toxicboost_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_toxicboost_orig(damagemult, attacker, opponent)
        is_tb = (attacker.hasWorkingAbility(:TOXICBOOST) rescue false)
        is_psn = (attacker.status == PBStatuses::POISON rescue false)
        movetype = (pbType(@type, attacker, opponent) rescue -1)
        is_phys = (pbIsPhysical?(movetype) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_tb && is_psn && is_phys
          mult = (mult * 1.5).round
          ($chrooked_log.call("[chrooked:toxicboost] OBS move=#{movename} toxicboost=#{is_tb} poison=#{is_psn} phys=#{is_phys} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:toxicboost] OBS move=#{movename} toxicboost=#{is_tb} poison=#{is_psn} phys=#{is_phys} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_toxicboost_damage_installed = true
  ($chrooked_log.call("[chrooked:toxicboost] installed pbModifyDamage on PokeBattle_Move") rescue nil)
end

# --- Install / deferred-install --------------------------------------------

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_toxicboost_damage
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_toxicboost_damage_orig)
      alias_method :update_chrooked_toxicboost_damage_orig, :update
      def update
        chrooked_install_toxicboost_damage if !$chrooked_toxicboost_damage_installed && defined?(PokeBattle_Move)
        update_chrooked_toxicboost_damage_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:toxicboost] deferred install (damage) armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:toxicboost] ERROR: PokeBattle_Move/Graphics missing at load (damage)") rescue nil)
end
