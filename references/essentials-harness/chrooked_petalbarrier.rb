# chrooked:petalbarrier
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "petalbarrier" (ability :PETALBARRIER).
#
# HOOK 1 (special-damage reduction) — PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent)
#   16.2 Seam (Data/Scripts.rxdata). In pbModifyDamage, `opponent` is the DEFENDER
#   being hit, so this is a DEFENDER-side ability check (opponent.hasWorkingAbility).
#   If the defender has PETALBARRIER and the move's resolved type is SPECIAL
#   (pbIsSpecial?(movetype)), scale the final multiplier by 0.75. damagemult is in
#   0x1000 units; we round after scaling. The reduction is flat — it does NOT
#   require a super-effective hit. Vanilla aliased _orig runs first.
#
# NOT-PORTED — Shed Skin status cure (1/3 end-of-turn status cure):
#   The behavior spec's second effect (Shed Skin-style 1-in-3 end-of-turn cure of
#   the holder's non-volatile status) has NO verified end-of-round Seam in the
#   16.2 FACTS. We do NOT guess an unverified method. Only the damage half is
#   implemented here; the cure must be wired by hand once a verified end-of-round
#   Seam exists. needs_ingame.
#
# HARNESS (Route B log oracle):
#   damage:  [chrooked:petalbarrier] OBS move=<NAME> special=<BOOL> result=REDUCED|NORMAL
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

# --- HOOK 1: Special-damage reduction via pbModifyDamage --------------------
def chrooked_install_petalbarrier_reduction
  return if $chrooked_petalbarrier_reduction_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_petalbarrier_orig")
      alias_method :pbModifyDamage_chrooked_petalbarrier_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_petalbarrier_orig(damagemult, attacker, opponent)
        # opponent is the DEFENDER in pbModifyDamage.
        has_petalbarrier = (opponent.hasWorkingAbility(:PETALBARRIER) rescue false)
        movetype = (pbType(@type, attacker, opponent) rescue -1)
        is_special = (pbIsSpecial?(movetype) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if has_petalbarrier && is_special
          mult = (mult * 0.75).round
          ($chrooked_log.call("[chrooked:petalbarrier] OBS move=#{movename} special=true result=REDUCED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:petalbarrier] OBS move=#{movename} special=#{is_special} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_petalbarrier_reduction_installed = true
  ($chrooked_log.call("[chrooked:petalbarrier] reduction installed on PokeBattle_Move") rescue nil)
end

def chrooked_install_petalbarrier_all
  chrooked_install_petalbarrier_reduction
end

def chrooked_petalbarrier_all_installed?
  $chrooked_petalbarrier_reduction_installed
end

if defined?(PokeBattle_Move) &&
   PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_petalbarrier_all
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_petalbarrier_orig)
      alias_method :update_chrooked_petalbarrier_orig, :update
      def update
        chrooked_install_petalbarrier_all if !chrooked_petalbarrier_all_installed? && defined?(PokeBattle_Move)
        update_chrooked_petalbarrier_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:petalbarrier] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:petalbarrier] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
