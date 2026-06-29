# chrooked:exhaust
# ---------------------------------------------------------------------------
# Exhaust: on dealing damage with a CONTACT move, unconditionally lower the
# target's ACCURACY by 1 stage. No random roll. The engine handles the -6 floor
# (pbReduceStatWithCause returns false / no-ops when already at minimum).
#
# Seam (verified in Data/Scripts.rxdata): PokeBattle_Battler#pbEffectsOnDealingDamage
# (move,user,target,damage) — runs after USER deals damage. Vanilla POISONTOUCH and
# POISONPOINT both live here. We alias it and, for an :EXHAUST user landing a
# damaging contact hit, reduce the target's ACCURACY by 1 (PBStats::ACCURACY == 6).
#
# Gates: damage && damage>0 (target actually took damage) and move.isContactMove?
# (contact only). No RandomPercentage roll — guaranteed every damaging contact hit.
#
# Ruby 1.8: alias_method chaining; deferred install on Graphics.update (the shim
# preloads before PokeBattle_Battler is defined). Guarded $chrooked_log.
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

def chrooked_install_exhaust
  return if $chrooked_exhaust_installed
  return unless defined?(PokeBattle_Battler)
  return unless defined?(Chrooked)
  unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("chrooked_exhaust_apply")
    PokeBattle_Battler.class_eval do
      def chrooked_exhaust_apply(move, user, target, damage)
        dealt = (damage && damage > 0) rescue false
        contact = (move && move.isContactMove?) rescue false
        if user && target && dealt && contact && (user.hasWorkingAbility(:EXHAUST) rescue false)
          (Chrooked.lower_stat(target, :accuracy, 1, user) rescue nil)
          ($chrooked_log.call("[chrooked:exhaust] OBS event=hit ability=true effect=lowered target ACCURACY by 1 (contact, no roll)") rescue nil)
        end
      end
    end
  end
  return unless Chrooked.install_post_damage("chrooked_exhaust_apply", "pbOnDamage_chrooked_exhaust_orig")
  $chrooked_exhaust_installed = true
  ($chrooked_log.call("[chrooked:exhaust] installed on PokeBattle_Battler") rescue nil)
end

if defined?(PokeBattle_Battler) && defined?(Chrooked)
  chrooked_install_exhaust
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_exhaust_orig)
      alias_method :update_chrooked_exhaust_orig, :update
      def update
        chrooked_install_exhaust if !$chrooked_exhaust_installed && defined?(PokeBattle_Battler)
        update_chrooked_exhaust_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:exhaust] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:exhaust] ERROR: PokeBattle_Battler/Graphics missing at load") rescue nil)
end
