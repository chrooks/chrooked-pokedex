# chrooked:sacredtoll
# ---------------------------------------------------------------------------
# Sacred Toll (ability :SACREDTOLL): this Pokemon's SOUND moves become Psychic-type
# and gain a ×1.2 damage boost. Structural twin of the -ize converters (psyonize),
# but gated on isSoundBased? instead of Normal-type.
#
# Seam (same as psyonize/amplifier): PokeBattle_Move#pbModifyType swaps the type to
# PSYCHIC and sets @powerboost; #pbModifyDamage applies the ×1.2 (vanilla applies its
# 1.2 only to the stock -ate abilities, so a custom ability must add its own). The
# conversion gate keys off the move's own isSoundBased? predicate, so the boost
# tracks exactly the engine's notion of a sound move — no hand-maintained list.
#
# @powerboost needs no reset: a move's sound flag is fixed per move instance (Hyper
# Voice always sound, Tackle never), so a converted move stays converted and the
# boost can't leak to a non-sound move — same invariant psyonize relies on.
#
# NOT-PORTED (intentional, per spec): the in-game description says "Cures team on
# entry", but the seed source C implements NO team-cure switch-in effect — it is
# description text only. Only the sound→Psychic conversion + ×1.2 are real.
#
# Psychic typing then follows normal effectiveness (0× into Dark) for free.
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

def chrooked_install_sacredtoll
  return if $chrooked_sacredtoll_installed
  return unless defined?(PokeBattle_Move)
  im = PokeBattle_Move.instance_methods.map { |m| m.to_s }
  return unless im.include?("pbModifyType") && im.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyType_chrooked_sacredtoll_orig")
      alias_method :pbModifyType_chrooked_sacredtoll_orig, :pbModifyType
      def pbModifyType(type, attacker, opponent)
        type = pbModifyType_chrooked_sacredtoll_orig(type, attacker, opponent)
        if type >= 0 && (isSoundBased? rescue false) &&
           (attacker.hasWorkingAbility(:SACREDTOLL) rescue false) && hasConst?(PBTypes, :PSYCHIC)
          type = getConst(PBTypes, :PSYCHIC)
          @powerboost = true
        end
        type
      end
    end
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_sacredtoll_orig")
      alias_method :pbModifyDamage_chrooked_sacredtoll_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        m = pbModifyDamage_chrooked_sacredtoll_orig(damagemult, attacker, opponent)
        is_ab = (attacker.hasWorkingAbility(:SACREDTOLL) rescue false)
        is_sound = (isSoundBased? rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_ab && is_sound && @powerboost
          m = (m * 1.2).round
          ($chrooked_log.call("[chrooked:sacredtoll] OBS move=#{movename} ability=true sound=true converted=PSYCHIC result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:sacredtoll] OBS move=#{movename} ability=#{is_ab} sound=#{is_sound} converted=none result=NORMAL") rescue nil)
        end
        m
      end
    end
  end
  $chrooked_sacredtoll_installed = true
  ($chrooked_log.call("[chrooked:sacredtoll] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyType")
  chrooked_install_sacredtoll
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_sacredtoll_orig)
      alias_method :update_chrooked_sacredtoll_orig, :update
      def update
        chrooked_install_sacredtoll if !$chrooked_sacredtoll_installed && defined?(PokeBattle_Move)
        update_chrooked_sacredtoll_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:sacredtoll] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:sacredtoll] ERROR: PokeBattle_Move/Graphics missing at load") rescue nil)
end
