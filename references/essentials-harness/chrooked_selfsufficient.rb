# chrooked:selfsufficient
# ---------------------------------------------------------------------------
# Self Sufficient (ability :SELFSUFFICIENT): "Leftovers as an ability." At the
# end of each round, the holder restores 1/16 of its max HP (floored, min 1),
# skipped at full HP. Stacks with an actual Leftovers item (separate heals).
#
# Seam (same as deeprooted's passive-drain top-up): post-wrap
#   PokeBattle_Battle#pbEndOfRoundPhase
# and, after the engine's own end-of-round heals run, give every living
# SELFSUFFICIENT holder its 1/16 recovery via pbRecoverHP(amt, true). Computing
# it outside the engine's item loop means it is independent of — and stacks
# with — the Leftovers item heal. Heal-Block-gated, matching the engine's
# passive-heal abilities (Rain Dish / Ice Body).
#
# RUBY 1.8: alias_method chaining (NO prepend / NO TracePoint); deferred install
# on the native Graphics.update (preload runs BEFORE Scripts.rxdata defines
# PokeBattle_Battle).
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

def chrooked_install_selfsufficient
  return if $chrooked_selfsufficient_installed
  return unless defined?(PokeBattle_Battle)
  return unless PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbEndOfRoundPhase")
  PokeBattle_Battle.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEndOfRoundPhase_chrooked_selfsufficient_orig")
      alias_method :pbEndOfRoundPhase_chrooked_selfsufficient_orig, :pbEndOfRoundPhase
      def pbEndOfRoundPhase(*args)
        ret = pbEndOfRoundPhase_chrooked_selfsufficient_orig(*args)
        begin
          @battlers.each do |b|
            next if b.nil? || (b.isFainted? rescue true)
            next unless (b.hasWorkingAbility(:SELFSUFFICIENT) rescue false)
            next if (b.hp >= b.totalhp rescue true)            # already full — no heal
            next unless (b.effects[PBEffects::HealBlock] rescue 0) == 0
            amt = (b.totalhp / 16).floor
            amt = 1 if amt < 1
            b.pbRecoverHP(amt, true)
            pbDisplay(_INTL("{1} restored a little HP using Self Sufficient!", b.pbThis)) rescue nil
            ($chrooked_log.call("[chrooked:selfsufficient] OBS event=endround ability=true heal=#{amt}") rescue nil)
          end
        rescue Exception
        end
        ret
      end
    end
  end
  $chrooked_selfsufficient_installed = true
  ($chrooked_log.call("[chrooked:selfsufficient] installed on PokeBattle_Battle") rescue nil)
end

if defined?(PokeBattle_Battle) && PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbEndOfRoundPhase")
  chrooked_install_selfsufficient
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_selfsufficient_orig)
      alias_method :update_chrooked_selfsufficient_orig, :update
      def update
        chrooked_install_selfsufficient if !$chrooked_selfsufficient_installed && defined?(PokeBattle_Battle)
        update_chrooked_selfsufficient_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:selfsufficient] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:selfsufficient] ERROR: PokeBattle_Battle/Graphics missing at load") rescue nil)
end
