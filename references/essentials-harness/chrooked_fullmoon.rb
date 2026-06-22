# chrooked:fullmoon
# ---------------------------------------------------------------------------
# Full Moon: the user's Dark- and Fairy-type moves get the Same-Type Attack
# Bonus (x1.5) regardless of the user's own types ("pseudo-STAB").
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# final-damage multiplier hook (base impl returns damagemult unchanged; same Seam
# kindle uses). damagemult is in 0x1000 units. movetype = pbType(@type, attacker,
# opponent); type check via isConst?(movetype, PBTypes, :DARK/:FAIRY).
#
# DOUBLE-COUNT GUARD: vanilla STAB is INLINE in pbCalcDamage (if the attacker
# pbHasType?(type) it already multiplied by 1.5). So Full Moon must grant the
# 1.5x ONLY when the gate matches AND the attacker does NOT already have that
# type — otherwise a Dark-type with Full Moon using a Dark move would get 2.25x.
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:fullmoon] OBS move=<NAME> fullmoon=<true|false> type=<NAME> result=<BOOSTED|NORMAL>
# Dark/Fairy move + fullmoon + type-not-already-owned -> BOOSTED; else NORMAL.
#
# SECOND EFFECT — Moonlight heals 3/4 max HP (now ported). The recover handler is
# PokeBattle_Move_0D8#pbEffect (Moonlight/Morning Sun/Synthesis share this class;
# verified in Data/Scripts.rxdata — it branches the heal on weather: sun 2/3, clear
# 1/2, other 1/4). We wrap it: when the user has FULLMOON and the move is Moonlight
# and it is below full HP, heal (totalhp*3/4).floor and skip the original (so the
# weather branches never run). Full HP falls through to _orig (Moonlight fails as
# usual). Same Seam chrooked_chloroplast uses for its Synthesis heal.
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

def chrooked_install_fullmoon
  return if $chrooked_fullmoon_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_fullmoon_orig")
      alias_method :pbModifyDamage_chrooked_fullmoon_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_fullmoon_orig(damagemult, attacker, opponent)
        is_fullmoon = (attacker.hasWorkingAbility(:FULLMOON) rescue false)
        movetype = (pbType(@type, attacker, opponent) rescue -1)
        is_dark = (isConst?(movetype, PBTypes, :DARK) rescue false)
        is_fairy = (isConst?(movetype, PBTypes, :FAIRY) rescue false)
        already_has = (attacker.pbHasType?(movetype) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        typename = (getConstantName(PBTypes, movetype) rescue movetype.to_s)
        if is_fullmoon && (is_dark || is_fairy) && !already_has
          mult = (mult * 1.5).round
          ($chrooked_log.call("[chrooked:fullmoon] OBS move=#{movename} fullmoon=#{is_fullmoon} type=#{typename} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:fullmoon] OBS move=#{movename} fullmoon=#{is_fullmoon} type=#{typename} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_fullmoon_installed = true
  ($chrooked_log.call("[chrooked:fullmoon] installed on PokeBattle_Move") rescue nil)
end

# --- Moonlight heal: 3/4 max HP for a FULLMOON user (Move_0D8) ----------------
def chrooked_install_fullmoon_heal
  return if $chrooked_fullmoon_heal_installed
  klass = (Object.const_get("PokeBattle_Move_0D8") rescue nil)
  return if klass.nil?
  klass.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEffect_chrooked_fullmoon_orig")
      alias_method :pbEffect_chrooked_fullmoon_orig, :pbEffect
      def pbEffect(attacker, opponent, hitnum = 0, alltargets = nil, showanimation = true)
        if (attacker.hasWorkingAbility(:FULLMOON) rescue false) &&
           (isConst?(@id, PBMoves, :MOONLIGHT) rescue false) &&
           attacker.hp != attacker.totalhp
          hpgain = (attacker.totalhp * 3 / 4).floor
          pbShowAnimation(@id, attacker, nil, hitnum, alltargets, showanimation)
          attacker.pbRecoverHP(hpgain, true)
          @battle.pbDisplay(_INTL("{1} recuperó salud.", attacker.pbThis))
          ($chrooked_log.call("[chrooked:fullmoon] OBS move=MOONLIGHT fullmoon=true heal=three_quarters") rescue nil)
          return 0
        end
        pbEffect_chrooked_fullmoon_orig(attacker, opponent, hitnum, alltargets, showanimation)
      end
    end
  end
  $chrooked_fullmoon_heal_installed = true
  ($chrooked_log.call("[chrooked:fullmoon] heal hook installed on PokeBattle_Move_0D8") rescue nil)
end

def chrooked_fullmoon_done?
  $chrooked_fullmoon_installed && $chrooked_fullmoon_heal_installed
end

chrooked_install_fullmoon if defined?(PokeBattle_Move) &&
  PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
chrooked_install_fullmoon_heal

unless chrooked_fullmoon_done?
  if defined?(Graphics)
    class << Graphics
      unless method_defined?(:update_chrooked_fullmoon_orig)
        alias_method :update_chrooked_fullmoon_orig, :update
        def update
          chrooked_install_fullmoon if !$chrooked_fullmoon_installed && defined?(PokeBattle_Move)
          chrooked_install_fullmoon_heal unless $chrooked_fullmoon_heal_installed
          update_chrooked_fullmoon_orig
        end
      end
    end
    ($chrooked_log.call("[chrooked:fullmoon] deferred install armed on Graphics.update") rescue nil)
  else
    ($chrooked_log.call("[chrooked:fullmoon] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
  end
end
