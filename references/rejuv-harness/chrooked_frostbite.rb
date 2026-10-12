# chrooked:frostbite
# Frostbite — freeze reskinned. The engine keeps its :FROZEN symbol; only the
# behavior and the player-facing text change.
#
# History: through 14.0.1x Rejuv shipped its own frostbite gated behind the
# Nevermelting Hail state (state.effects[:NeverMeltIce]) and this file ungated
# it by flipping the flag. 14.0.20 deleted that gated code outright — the
# freeze block in pbTryUseMove is unconditional again and pbCalcDamage /
# pbEndOfRoundPhase no longer know frostbite — so this file now implements
# all three effects itself:
#   special damage x0.5 (Guts exempt)  -> CHROOKED_STATUS_DAMAGE_MODS (core)
#   1/16 max HP chip each turn          -> CHROOKED_STATUS_TURN_END (core)
#   no turn skip, no random thaw        -> prepend on pbTryUseMove below
#
# Test cases:
#   - frostbitten mon takes its turn instead of losing it
#   - its special move deals half damage; its physical move is unaffected
#   - it loses 1/16 max HP at end of turn (Magic Guard exempt)
#   - a Fire move it uses cures the status
#   - Guts holder suffers no special damage penalty (mirrors burn)
#   - Ice-types cannot be frostbitten (vanilla pbCanFreeze? already blocks them)

# --- Special damage halved, unless Guts ------------------------------------
# Mirrors the burn line directly above the frozen one in pbCalcDamage, which
# reads `attacker.ability != :GUTS`. Guts already grants its own x1.5 Attack on
# any status (Battle_Move.rb ~1515), so only the penalty exemption is new.
CHROOKED_STATUS_DAMAGE_MODS[:FROZEN] = lambda { |move, attacker, opponent|
  next 1.0 if attacker.crested == :SUICUNE
  next 1.0 if attacker.ability == :GUTS
  next 1.0 unless move.pbIsSpecial?(attacker, move.pbType(attacker))
  0.5
}

# --- Chip damage, 1/16 to match burn ---------------------------------------
CHROOKED_STATUS_TURN_END[:FROZEN] = lambda { |battler, battle|
  next if battler.crested == :SUICUNE
  next if battle.magicGuardAbilities.include?(battler.ability)
  battler.pbContinueStatus
  battler.pbReduceHP((battler.totalhp / 16.0).floor)
  battler.pbFaint if battler.isFainted?
}

# --- No turn skip, but keep the Fire-move thaw -----------------------------
# The freeze block in pbTryUseMove (Battler.rb ~5723 on 14.0.20) is
# `if self.status == :FROZEN` with no gate, and it sits inside a 200-line
# method we must not redefine. So the prepend handles the Fire-move thaw
# itself, then hides the status from the vanilla body for the duration of
# that one call: @status is swapped to nil and restored in an ensure.
#
# The ivar is written directly on purpose — `status=` has Truant / Petrified
# side effects on nil. The only other status reads inside pbTryUseMove are
# SLEEP, PARALYSIS and PETRIFIED, all false for a frostbitten mon, so nothing
# else changes. Nothing in that method cures a status for a mon it thinks is
# healthy, so the restore cannot re-freeze a cured mon.
module ChrookedFrostbiteNoTurnSkip
  def pbTryUseMove(*args, **kwargs)
    return super unless @status == :FROZEN
    basemove = args[1]
    if basemove.respond_to?(:canThawUser?) && basemove.canThawUser? &&
       !(basemove.move == :BURNUP && !self.hasType?(:FIRE))
      self.pbCureStatus(false)
      @battle.pbDisplay(_INTL("{1}'s {2} melted the frost!", pbThis, basemove.name))
      return super
    end
    @status = nil
    begin
      super
    ensure
      @status = :FROZEN if @status.nil?
    end
  end
end
PokeBattle_Battler.prepend(ChrookedFrostbiteNoTurnSkip) if defined?(PokeBattle_Battler)

# --- Player-facing text -----------------------------------------------------
# Cosmetic, but the difference between the change reading as intentional and
# reading as a bug. Both methods are small and cleanly scoped, so a prepend that
# handles only :FROZEN and defers everything else to super is safe.
module ChrookedFrostbiteText
  def pbFreeze(message: nil)
    message = _INTL("{1} was frostbitten!", pbThis) if message.nil?
    super(message: message)
  end

  def pbContinueStatus(showAnim = true)
    return super unless self.status == :FROZEN
    @battle.pbCommonAnimation("Frozen", self, nil)
    @battle.pbDisplay(_INTL("{1} was hurt by frostbite!", pbThis))
  end
end
PokeBattle_Battler.prepend(ChrookedFrostbiteText) if defined?(PokeBattle_Battler)
