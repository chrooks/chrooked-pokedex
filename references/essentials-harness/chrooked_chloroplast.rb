# chrooked:chloroplast
# ---------------------------------------------------------------------------
# Chloroplast (ability :CHLOROPLAST): this Pokemon's MOVES act as if the sun is
# shining, regardless of real weather; Weather Ball is Fire-type for it. Scope is
# move-only — no passive sun effects (Solar Power, Dry Skin, Leaf Guard, etc.).
#
# No single "sun for moves" helper exists in this fork (unlike the pokeemerald
# source's IsBattlerSunAffectedForMoves) — each move reads @battle.pbWeather inline.
# So we override the specific sun-reading move subclasses (all verified in
# Data/Scripts.rxdata), forcing sun behavior when the user has CHLOROPLAST:
#
#   * Solar Beam  (PokeBattle_Move_0C4): pbTwoTurnAttack — fire same turn (no
#     charge); pbBaseDamageMultiplier — don't halve power in non-sun.
#   * Solar Blade (PokeBattle_Move_CF7): pbTwoTurnAttack — fire same turn.
#   * Weather Ball(PokeBattle_Move_087): pbModifyType → FIRE; pbBaseDamage → ×2
#     (the sun-doubling) regardless of real weather.
#
# Fire x1.5 / Water x0.5 sun damage gate — lives mid-method in the core damage calc
# (PokeBattle_Move pbCalcDamage ~line 1102, "case @battle.pbWeather"), not alias-
# injectable. We apply it via the pbModifyDamage final-multiplier hook. pbCalcDamage
# has ALREADY baked the REAL weather's Fire/Water mult into the damage, so to force
# "as if sun" over ANY weather we divide that engine mult back out and multiply in
# sun's (clear -> x1.5/x0.5, real sun -> no-op, rain -> x3.0/x0.333). This Pokemon's
# Fire/Water moves behave as in sun regardless of the field weather.
#
# Also ported (the rest of the sun-for-moves gate, per the spec):
#   * Synthesis/Morning Sun/Moonlight (Move_0D8): heal 2/3 max HP (the sun amount).
#   * Growth (Move_028): raise Atk+SpAtk by 2 (the sun amount).
#
# (chloroplast.yaml's note was reconciled 2026-06-22: an earlier draft wrongly said
# the Fire/Water multiplier was excluded, contradicting test 3 + the cited C.)
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

# --- Solar Beam (Move_0C4): skip charge + no power-halve under Chloroplast ----
def chrooked_install_chloroplast_solarbeam
  return if $chrooked_chloroplast_solarbeam_installed
  klass = (Object.const_get("PokeBattle_Move_0C4") rescue nil)
  return if klass.nil?
  # chrooked: IF2's fork renames these per-move seams; skip if absent or alias_method
  # raises NameError and crashes boot.
  return unless ["pbTwoTurnAttack", "pbBaseDamageMultiplier"].all? { |n|
    klass.instance_methods.map { |m| m.to_s }.include?(n) }
  klass.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbTwoTurnAttack_chrooked_chloroplast_orig")
      alias_method :pbTwoTurnAttack_chrooked_chloroplast_orig, :pbTwoTurnAttack
      def pbTwoTurnAttack(attacker)
        ret = pbTwoTurnAttack_chrooked_chloroplast_orig(attacker)
        if (attacker.hasWorkingAbility(:CHLOROPLAST) rescue false) && !@immediate &&
           attacker.effects[PBEffects::TwoTurnAttack] == 0
          @immediate = true; @sunny = true
          ($chrooked_log.call("[chrooked:chloroplast] OBS move=SOLARBEAM ability=true effect=nocharge") rescue nil)
          return false
        end
        ret
      end
    end
    unless instance_methods(false).map { |m| m.to_s }.include?("pbBaseDamageMultiplier_chrooked_chloroplast_orig")
      alias_method :pbBaseDamageMultiplier_chrooked_chloroplast_orig, :pbBaseDamageMultiplier
      def pbBaseDamageMultiplier(damagemult, attacker, opponent)
        return damagemult if (attacker.hasWorkingAbility(:CHLOROPLAST) rescue false)
        pbBaseDamageMultiplier_chrooked_chloroplast_orig(damagemult, attacker, opponent)
      end
    end
  end
  $chrooked_chloroplast_solarbeam_installed = true
  ($chrooked_log.call("[chrooked:chloroplast] solarbeam hooks installed on PokeBattle_Move_0C4") rescue nil)
end

# --- Solar Blade (Move_CF7): skip charge under Chloroplast --------------------
def chrooked_install_chloroplast_solarblade
  return if $chrooked_chloroplast_solarblade_installed
  klass = (Object.const_get("PokeBattle_Move_CF7") rescue nil)
  return if klass.nil?
  # chrooked: skip if IF2's fork lacks this seam (alias_method would crash boot).
  return unless klass.instance_methods.map { |m| m.to_s }.include?("pbTwoTurnAttack")
  klass.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbTwoTurnAttack_chrooked_chloroplast_orig")
      alias_method :pbTwoTurnAttack_chrooked_chloroplast_orig, :pbTwoTurnAttack
      def pbTwoTurnAttack(attacker)
        ret = pbTwoTurnAttack_chrooked_chloroplast_orig(attacker)
        if (attacker.hasWorkingAbility(:CHLOROPLAST) rescue false) && !@immediate &&
           attacker.effects[PBEffects::TwoTurnAttack] == 0
          @immediate = true
          ($chrooked_log.call("[chrooked:chloroplast] OBS move=SOLARBLADE ability=true effect=nocharge") rescue nil)
          return false
        end
        ret
      end
    end
  end
  $chrooked_chloroplast_solarblade_installed = true
  ($chrooked_log.call("[chrooked:chloroplast] solarblade hook installed on PokeBattle_Move_CF7") rescue nil)
end

# --- Weather Ball (Move_087): Fire-type + ×2 power under Chloroplast -----------
def chrooked_install_chloroplast_weatherball
  return if $chrooked_chloroplast_weatherball_installed
  klass = (Object.const_get("PokeBattle_Move_087") rescue nil)
  return if klass.nil?
  # chrooked: IF2's fork renames pbModifyType (and may rename pbBaseDamage); skip if
  # absent or alias_method raises NameError and crashes boot.
  return unless ["pbModifyType", "pbBaseDamage"].all? { |n|
    klass.instance_methods.map { |m| m.to_s }.include?(n) }
  klass.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyType_chrooked_chloroplast_orig")
      alias_method :pbModifyType_chrooked_chloroplast_orig, :pbModifyType
      def pbModifyType(type, attacker, opponent)
        ret = pbModifyType_chrooked_chloroplast_orig(type, attacker, opponent)
        if (attacker.hasWorkingAbility(:CHLOROPLAST) rescue false) && hasConst?(PBTypes, :FIRE)
          ($chrooked_log.call("[chrooked:chloroplast] OBS move=WEATHERBALL ability=true type=FIRE") rescue nil)
          return getConst(PBTypes, :FIRE)
        end
        ret
      end
    end
    unless instance_methods(false).map { |m| m.to_s }.include?("pbBaseDamage_chrooked_chloroplast_orig")
      alias_method :pbBaseDamage_chrooked_chloroplast_orig, :pbBaseDamage
      def pbBaseDamage(basedmg, attacker, opponent)
        if (attacker.hasWorkingAbility(:CHLOROPLAST) rescue false)
          return basedmg * 2
        end
        pbBaseDamage_chrooked_chloroplast_orig(basedmg, attacker, opponent)
      end
    end
  end
  $chrooked_chloroplast_weatherball_installed = true
  ($chrooked_log.call("[chrooked:chloroplast] weatherball hooks installed on PokeBattle_Move_087") rescue nil)
end

# --- Fire×1.5 / Water×0.5 sun gate (clear weather only) via pbModifyDamage -----
def chrooked_install_chloroplast_sungate
  return if $chrooked_chloroplast_sungate_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_chloroplast_orig")
      alias_method :pbModifyDamage_chrooked_chloroplast_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_chloroplast_orig(damagemult, attacker, opponent)
        begin
          if (attacker.hasWorkingAbility(:CHLOROPLAST) rescue false)
            movetype = (Chrooked.move_type(self, attacker, opponent) rescue nil)
            is_fire  = (isConst?(movetype, PBTypes, :FIRE) rescue false)
            is_water = (isConst?(movetype, PBTypes, :WATER) rescue false)
            if is_fire || is_water
              # pbCalcDamage already baked the REAL weather's Fire/Water mult into
              # damage (sun: Fire 1.5/Water 0.5; rain: Fire 0.5/Water 1.5; else 1).
              # We run after, on the multiplier, so divide that out and multiply in
              # sun's value — forcing "as if sun" over ANY weather, for this mon only.
              w = (@battle.pbWeather rescue 0)
              sun  = (w == PBWeather::SUNNYDAY || w == PBWeather::HARSHSUN)
              rain = (w == PBWeather::RAINDANCE || w == PBWeather::HEAVYRAIN)
              wtag = sun ? "sun" : (rain ? "rain" : "clear")
              mname = (getConstantName(PBMoves, @id) rescue @id)
              if is_fire
                engine = sun ? 1.5 : (rain ? 0.5 : 1.0)
                mult = (mult * (1.5 / engine)).round
                ($chrooked_log.call("[chrooked:chloroplast] OBS move=#{mname} ability=true type=FIRE weather=#{wtag} result=SUN_BOOSTED") rescue nil)
              else
                engine = sun ? 0.5 : (rain ? 1.5 : 1.0)
                mult = (mult * (0.5 / engine)).round
                ($chrooked_log.call("[chrooked:chloroplast] OBS move=#{mname} ability=true type=WATER weather=#{wtag} result=SUN_WEAKENED") rescue nil)
              end
            end
          end
        rescue Exception
        end
        mult
      end
    end
  end
  $chrooked_chloroplast_sungate_installed = true
  ($chrooked_log.call("[chrooked:chloroplast] sungate hook installed on PokeBattle_Move") rescue nil)
end

# --- Synthesis / Morning Sun / Moonlight (Move_0D8): heal the sun 2/3 amount ---
def chrooked_install_chloroplast_synthesis
  return if $chrooked_chloroplast_synthesis_installed
  klass = (Object.const_get("PokeBattle_Move_0D8") rescue nil)
  return if klass.nil?
  # chrooked: IF2's fork lacks pbEffect on this class; skip or alias_method crashes boot.
  return unless klass.instance_methods.map { |m| m.to_s }.include?("pbEffect")
  klass.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEffect_chrooked_chloroplast_orig")
      alias_method :pbEffect_chrooked_chloroplast_orig, :pbEffect
      def pbEffect(attacker, opponent, hitnum = 0, alltargets = nil, showanimation = true)
        if (attacker.hasWorkingAbility(:CHLOROPLAST) rescue false) && attacker.hp != attacker.totalhp
          hpgain = (attacker.totalhp * 2 / 3).floor   # sun amount, regardless of real weather
          pbShowAnimation(@id, attacker, nil, hitnum, alltargets, showanimation)
          attacker.pbRecoverHP(hpgain, true)
          @battle.pbDisplay(_INTL("{1} recuperó salud.", attacker.pbThis))
          ($chrooked_log.call("[chrooked:chloroplast] OBS move=SYNTHESIS ability=true heal=sun_2_3") rescue nil)
          return 0
        end
        pbEffect_chrooked_chloroplast_orig(attacker, opponent, hitnum, alltargets, showanimation)
      end
    end
  end
  $chrooked_chloroplast_synthesis_installed = true
  ($chrooked_log.call("[chrooked:chloroplast] synthesis hook installed on PokeBattle_Move_0D8") rescue nil)
end

# --- Growth (Move_028): raise +2 (the sun amount) under Chloroplast -----------
def chrooked_install_chloroplast_growth
  return if $chrooked_chloroplast_growth_installed
  klass = (Object.const_get("PokeBattle_Move_028") rescue nil)
  return if klass.nil?
  # chrooked: IF2's fork lacks pbEffect on this class; skip or alias_method crashes boot.
  return unless klass.instance_methods.map { |m| m.to_s }.include?("pbEffect")
  klass.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEffect_chrooked_chloroplast_orig")
      alias_method :pbEffect_chrooked_chloroplast_orig, :pbEffect
      def pbEffect(attacker, opponent, hitnum = 0, alltargets = nil, showanimation = true)
        if (attacker.hasWorkingAbility(:CHLOROPLAST) rescue false)
          if !attacker.pbCanIncreaseStatStage?(PBStats::ATTACK, attacker, false, self) &&
             !attacker.pbCanIncreaseStatStage?(PBStats::SPATK, attacker, false, self)
            @battle.pbDisplay(_INTL("¡Las características de {1} no subirán más!", attacker.pbThis))
            return -1
          end
          pbShowAnimation(@id, attacker, opponent, hitnum, alltargets, showanimation)
          showanim = true
          increment = 2   # sun amount, regardless of real weather
          if attacker.pbCanIncreaseStatStage?(PBStats::ATTACK, attacker, false, self)
            attacker.pbIncreaseStat(PBStats::ATTACK, increment, attacker, false, self, showanim)
            showanim = false
          end
          if attacker.pbCanIncreaseStatStage?(PBStats::SPATK, attacker, false, self)
            attacker.pbIncreaseStat(PBStats::SPATK, increment, attacker, false, self, showanim)
            showanim = false
          end
          ($chrooked_log.call("[chrooked:chloroplast] OBS move=GROWTH ability=true increment=2") rescue nil)
          return 0
        end
        pbEffect_chrooked_chloroplast_orig(attacker, opponent, hitnum, alltargets, showanimation)
      end
    end
  end
  $chrooked_chloroplast_growth_installed = true
  ($chrooked_log.call("[chrooked:chloroplast] growth hook installed on PokeBattle_Move_028") rescue nil)
end

def chrooked_install_chloroplast_all
  chrooked_install_chloroplast_solarbeam
  chrooked_install_chloroplast_solarblade
  chrooked_install_chloroplast_weatherball
  chrooked_install_chloroplast_sungate
  chrooked_install_chloroplast_synthesis
  chrooked_install_chloroplast_growth
end

def chrooked_chloroplast_done?
  $chrooked_chloroplast_solarbeam_installed && $chrooked_chloroplast_solarblade_installed &&
    $chrooked_chloroplast_weatherball_installed && $chrooked_chloroplast_sungate_installed &&
    $chrooked_chloroplast_synthesis_installed && $chrooked_chloroplast_growth_installed
end

chrooked_install_chloroplast_all

unless chrooked_chloroplast_done?
  if defined?(Graphics)
    class << Graphics
      unless method_defined?(:update_chrooked_chloroplast_orig)
        alias_method :update_chrooked_chloroplast_orig, :update
        def update
          chrooked_install_chloroplast_all unless chrooked_chloroplast_done?
          update_chrooked_chloroplast_orig
        end
      end
    end
    ($chrooked_log.call("[chrooked:chloroplast] deferred install armed on Graphics.update") rescue nil)
  else
    ($chrooked_log.call("[chrooked:chloroplast] ERROR: classes/Graphics missing at load") rescue nil)
  end
end
