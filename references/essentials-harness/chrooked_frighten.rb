# chrooked:frighten
# ---------------------------------------------------------------------------
# Frighten: on switch-in, lowers the Special Attack of all opposing active
# battlers by 1 (Intimidate clone — Intimidate lowers ATTACK; Frighten lowers
# SPATK).
#
# Seam (verified in Data/Scripts.rxdata): PokeBattle_Battler#pbAbilitiesOnSwitchIn(onactive)
# — vanilla INTIMIDATE lives here: "if self.hasWorkingAbility(:INTIMIDATE) && onactive ...
# for i in 0...4: if pbIsOpposing?(i) && !@battle.battlers[i].isFainted?:
# @battle.battlers[i].pbReduceAttackStatIntimidate(self)". We mirror the loop but call
# the generic pbReduceStatWithCause(PBStats::SPATK,1,self,name) (verified signature in
# PokeBattle_BattlerEffects). The "empty opposing side" case yields no targets, so no
# change occurs naturally; doubles hit both foes via the 0...4 loop.
#
# Ruby 1.8: alias_method chaining; deferred install on Graphics.update.
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

def chrooked_install_frighten
  return if $chrooked_frighten_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbAbilitiesOnSwitchIn")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbAbilitiesOnSwitchIn_chrooked_frighten_orig")
      alias_method :pbAbilitiesOnSwitchIn_chrooked_frighten_orig, :pbAbilitiesOnSwitchIn
      def pbAbilitiesOnSwitchIn(onactive)
        pbAbilitiesOnSwitchIn_chrooked_frighten_orig(onactive)
        if (self.hasWorkingAbility(:FRIGHTEN) rescue false) && onactive
          name = (PBAbilities.getName(self.ability) rescue "Frighten")
          for i in 0...4
            if (pbIsOpposing?(i) rescue false) && !@battle.battlers[i].isFainted?
              (@battle.battlers[i].pbReduceStatWithCause(PBStats::SPATK, 1, self, name) rescue nil)
            end
          end
          ($chrooked_log.call("[chrooked:frighten] OBS event=switchin ability=true lowered=SPATK") rescue nil)
        end
      end
    end
  end
  $chrooked_frighten_installed = true
  ($chrooked_log.call("[chrooked:frighten] installed on PokeBattle_Battler") rescue nil)
end

if defined?(PokeBattle_Battler) && PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbAbilitiesOnSwitchIn")
  chrooked_install_frighten
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_frighten_orig)
      alias_method :update_chrooked_frighten_orig, :update
      def update
        chrooked_install_frighten if !$chrooked_frighten_installed && defined?(PokeBattle_Battler)
        update_chrooked_frighten_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:frighten] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:frighten] ERROR: PokeBattle_Battler/Graphics missing at load") rescue nil)
end
