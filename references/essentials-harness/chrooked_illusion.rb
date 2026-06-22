# chrooked:illusion
# ---------------------------------------------------------------------------
# Illusion (ability :ILLUSION): disguise as the last conscious party member on
# entry, break on direct damage, AND deal ×1.2 outgoing damage while disguised.
#
# The disguise + break-on-damage are ALREADY native in this fork (verified in
# Data/Scripts.rxdata): PBEffects::Illusion (slot 39) holds the disguise mon,
# set up in PokeBattle_Battler at switch-in (~line 423: "if self.hasWorkingAbility
# (:ILLUSION) ... @effects[PBEffects::Illusion]=@battle.pbParty(@index)[lastpoke]")
# and cleared to nil when the holder takes a hit (~line 3122-3125). So only the
# custom ×1.2 boost is missing.
#
# Seam: PokeBattle_Move#pbModifyDamage. The disguise being active-and-unbroken is
# exactly "@effects[PBEffects::Illusion] is non-nil" (the engine nils it on break),
# so the boost gate is: attacker.hasWorkingAbility(:ILLUSION) && that effect set.
# Once the engine breaks the disguise the effect is nil and the ×1.2 stops — the
# spec's "boost no longer applies after the break" falls out for free.
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

def chrooked_install_illusion
  return if $chrooked_illusion_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_illusion_orig")
      alias_method :pbModifyDamage_chrooked_illusion_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_illusion_orig(damagemult, attacker, opponent)
        begin
          is_ab = (attacker.hasWorkingAbility(:ILLUSION) rescue false)
          disguised = is_ab && !(attacker.effects[PBEffects::Illusion].nil? rescue true)
          movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
          if disguised
            mult = (mult * 1.2).round
            ($chrooked_log.call("[chrooked:illusion] OBS move=#{movename} ability=true disguised=true result=BOOSTED") rescue nil)
          else
            ($chrooked_log.call("[chrooked:illusion] OBS move=#{movename} ability=#{is_ab} disguised=false result=NORMAL") rescue nil)
          end
        rescue Exception
        end
        mult
      end
    end
  end
  $chrooked_illusion_installed = true
  ($chrooked_log.call("[chrooked:illusion] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_illusion
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_illusion_orig)
      alias_method :update_chrooked_illusion_orig, :update
      def update
        chrooked_install_illusion if !$chrooked_illusion_installed && defined?(PokeBattle_Move)
        update_chrooked_illusion_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:illusion] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:illusion] ERROR: PokeBattle_Move/Graphics missing at load") rescue nil)
end
