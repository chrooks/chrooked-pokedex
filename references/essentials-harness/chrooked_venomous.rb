# chrooked:venomous
# ---------------------------------------------------------------------------
# Venomous: one ability that combines Poison Point + Poison Touch.
# On a contact move that deals damage:
#   (a) if the USER has VENOMOUS   -> 30% to poison the TARGET (Poison Touch half)
#   (b) if the TARGET has VENOMOUS -> 30% to poison the USER   (Poison Point half)
# Each direction is an independent 30% roll, gated by pbCanPoison? before pbPoison.
#
# Seam (verified in Data/Scripts.rxdata, 16.2): PokeBattle_Battler#
# pbEffectsOnDealingDamage(move,user,target,damage) (~line 1459) — runs after the
# USER deals damage. Vanilla POISONTOUCH and POISONPOINT both live here, so both
# halves belong on this one Seam. Alias-chained on PokeBattle_Battler.
#
# Gate: damage dealt (damage && damage>0) AND move.isContactMove?. Roll 30% with
# @battle.pbRandom(100)<30. Poison via:
#     if other.pbCanPoison?(source,false,move): other.pbPoison(source)
# (pbCanPoison?(attacker,showMessages,move=nil); pbPoison(attacker,msg=nil).)
#
# HARNESS (Route B log oracle): on a damaging contact hit, logs one line:
#     [chrooked:venomous] OBS event=hit ability=true effect=<what happened>
# effect ∈ { touch-poisoned-target, point-poisoned-user,
#            both-poisoned, touch-roll-failed, point-roll-failed,
#            target-immune, user-immune, no-venomous } etc.
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

def chrooked_install_venomous
  return if $chrooked_venomous_installed
  return unless defined?(PokeBattle_Battler)
  return unless defined?(Chrooked)
  unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("chrooked_venomous_apply")
    PokeBattle_Battler.class_eval do
      def chrooked_venomous_apply(move, user, target, damage)
        begin
          dealt    = (damage && damage > 0)
          contact  = Chrooked.contact_move?(move)
          userv    = (user && (user.hasWorkingAbility(:VENOMOUS) rescue false))
          targetv  = (target && (target.hasWorkingAbility(:VENOMOUS) rescue false))
          if dealt && contact && (userv || targetv)
            results = []
            # (a) Poison Touch half — USER has VENOMOUS, may poison the TARGET.
            if userv
              if @battle.pbRandom(100) < 30
                if (target.pbCanPoison?(user, false, move) rescue false)
                  (target.pbPoison(user) rescue nil)
                  results.push("touch-poisoned-target")
                else
                  results.push("touch-target-immune")
                end
              else
                results.push("touch-roll-failed")
              end
            end
            # (b) Poison Point half — TARGET has VENOMOUS, may poison the USER.
            if targetv
              if @battle.pbRandom(100) < 30
                if (user.pbCanPoison?(target, false, move) rescue false)
                  (user.pbPoison(target) rescue nil)
                  results.push("point-poisoned-user")
                else
                  results.push("point-user-immune")
                end
              else
                results.push("point-roll-failed")
              end
            end
            effect = results.empty? ? "no-op" : results.join("+")
            ($chrooked_log.call("[chrooked:venomous] OBS event=hit ability=true effect=#{effect}") rescue nil)
          end
        rescue Exception
        end
      end
    end
  end
  return unless Chrooked.install_post_damage("chrooked_venomous_apply", "pbOnDamage_chrooked_venomous_orig")
  $chrooked_venomous_installed = true
  ($chrooked_log.call("[chrooked:venomous] installed on PokeBattle_Battler") rescue nil)
end

if defined?(PokeBattle_Battler) && defined?(Chrooked)
  chrooked_install_venomous
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_venomous_orig)
      alias_method :update_chrooked_venomous_orig, :update
      def update
        chrooked_install_venomous if !$chrooked_venomous_installed && defined?(PokeBattle_Battler)
        update_chrooked_venomous_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:venomous] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:venomous] ERROR: PokeBattle_Battler/Graphics missing at load") rescue nil)
end
