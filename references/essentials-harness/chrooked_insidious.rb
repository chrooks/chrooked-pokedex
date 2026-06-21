# chrooked:insidious
# ---------------------------------------------------------------------------
# Insidious: after the user uses a STATUS-category move, raise the user's Speed
# by 1 (engine caps at +6).
#
# Seam (verified in Data/Scripts.rxdata): PokeBattle_Battler#pbUseMove(choice,
# specialusage=false) (line 3394) is the move-execution entry. `self` is the user;
# `choice[2]` is the PokeBattle_Move being used (set at 3411/3419), and
# PokeBattle_Move#pbIsStatus? (line 154) reports the status category. There is NO
# pbEffectsAfterMove hook in 16.2, and pbEffectsOnDealingDamage never fires for a
# no-damage status move — so we alias pbUseMove and act after the original runs.
# Stat const PBStats::SPEED==3; helpers pbCanIncreaseStatStage? / pbIncreaseStatWithCause.
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

def chrooked_install_insidious
  return if $chrooked_insidious_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbUseMove")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbUseMove_chrooked_insidious_orig")
      alias_method :pbUseMove_chrooked_insidious_orig, :pbUseMove
      def pbUseMove(choice, specialusage = false)
        ret = pbUseMove_chrooked_insidious_orig(choice, specialusage)
        begin
          move = choice[2]
          if move && (move.pbIsStatus? rescue false) && (self.hasWorkingAbility(:INSIDIOUS) rescue false)
            if (pbCanIncreaseStatStage?(PBStats::SPEED, self) rescue false)
              pbIncreaseStatWithCause(PBStats::SPEED, 1, self, PBAbilities.getName(self.ability))
            end
            ($chrooked_log.call("[chrooked:insidious] OBS event=statusmove ability=true effect=+1SPEED") rescue nil)
          end
        rescue Exception
        end
        ret
      end
    end
  end
  $chrooked_insidious_installed = true
  ($chrooked_log.call("[chrooked:insidious] installed on PokeBattle_Battler") rescue nil)
end

if defined?(PokeBattle_Battler) && PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbUseMove")
  chrooked_install_insidious
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_insidious_orig)
      alias_method :update_chrooked_insidious_orig, :update
      def update
        chrooked_install_insidious if !$chrooked_insidious_installed && defined?(PokeBattle_Battler)
        update_chrooked_insidious_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:insidious] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:insidious] ERROR: PokeBattle_Battler/Graphics missing at load") rescue nil)
end
