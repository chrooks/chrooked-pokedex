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
# TEAM-CURE ON ENTRY (now ported, per Chris — match the in-game description "Cures
# team on entry"). Not in the seed source C (description text only), but wanted as
# real behavior. On a real switch-in, cure the holder's whole team's non-volatile
# status — mirrors Heal Bell / Aromatherapy (Move_019): active allies via
# pbCureStatus, benched party via status=0/statusCount=0. Hooked on
# PokeBattle_Battler#pbAbilitiesOnSwitchIn, gated on `onactive` (fires every turn
# with onactive=false otherwise).
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

# --- Team-cure on entry (PokeBattle_Battler#pbAbilitiesOnSwitchIn) ------------
def chrooked_install_sacredtoll_cure
  return if $chrooked_sacredtoll_cure_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbAbilitiesOnSwitchIn")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbAbilitiesOnSwitchIn_chrooked_sacredtoll_orig")
      alias_method :pbAbilitiesOnSwitchIn_chrooked_sacredtoll_orig, :pbAbilitiesOnSwitchIn
      def pbAbilitiesOnSwitchIn(onactive)
        begin
          if onactive && (self.hasWorkingAbility(:SACREDTOLL) rescue false)
            cured = 0
            activeidx = []
            @battle.battlers.each do |b|
              next if b.nil? || (self.pbIsOpposing?(b.index) rescue true) || (b.isFainted? rescue true)
              activeidx.push(b.pokemonIndex)
              if (b.status rescue 0) > 0
                b.pbCureStatus(false)
                cured += 1
              end
            end
            party = (@battle.pbParty(self.index) rescue [])
            for i in 0...party.length
              next if activeidx.include?(i)
              next if !party[i] || (party[i].isEgg? rescue false) || party[i].hp <= 0
              if party[i].status > 0
                party[i].status = 0
                party[i].statusCount = 0
                cured += 1
              end
            end
            @battle.pbDisplay(_INTL("¡Una campana sagrada curó al equipo!")) if cured > 0
            ($chrooked_log.call("[chrooked:sacredtoll] OBS event=switchin cure=team cured=#{cured}") rescue nil)
          end
        rescue Exception
        end
        pbAbilitiesOnSwitchIn_chrooked_sacredtoll_orig(onactive)
      end
    end
  end
  $chrooked_sacredtoll_cure_installed = true
  ($chrooked_log.call("[chrooked:sacredtoll] team-cure installed on PokeBattle_Battler") rescue nil)
end

def chrooked_sacredtoll_done?
  $chrooked_sacredtoll_installed && $chrooked_sacredtoll_cure_installed
end

chrooked_install_sacredtoll if defined?(PokeBattle_Move) &&
  PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyType")
chrooked_install_sacredtoll_cure if defined?(PokeBattle_Battler) &&
  PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbAbilitiesOnSwitchIn")

unless chrooked_sacredtoll_done?
  if defined?(Graphics)
    class << Graphics
      unless method_defined?(:update_chrooked_sacredtoll_orig)
        alias_method :update_chrooked_sacredtoll_orig, :update
        def update
          chrooked_install_sacredtoll if !$chrooked_sacredtoll_installed && defined?(PokeBattle_Move)
          chrooked_install_sacredtoll_cure if !$chrooked_sacredtoll_cure_installed && defined?(PokeBattle_Battler)
          update_chrooked_sacredtoll_orig
        end
      end
    end
    ($chrooked_log.call("[chrooked:sacredtoll] deferred install armed on Graphics.update") rescue nil)
  else
    ($chrooked_log.call("[chrooked:sacredtoll] ERROR: PokeBattle classes/Graphics missing at load") rescue nil)
  end
end
