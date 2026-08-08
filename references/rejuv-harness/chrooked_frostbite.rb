# chrooked:frostbite
# Frostbite — freeze reskinned. The engine keeps its :FROZEN symbol; only the
# behavior and the player-facing text change.
#
# Rejuv already implements frostbite, gated behind the Nevermelting Hail/Snow
# weather state (state.effects[:NeverMeltIce]). Three sites read that flag:
#   Battler.rb ~5719   (pbTryUseMove)      flag on => the turn-skip block is skipped
#   Battle_Move.rb ~1179 (pbCalcDamage)    flag on => special attacks deal x0.5
#   Battle.rb ~6404    (pbEndOfRoundPhase) flag on => 1/8 max HP chip each turn
# This file ungates all three permanently, and drops the chip to 1/16 so it
# matches burn (Battle.rb ~6544) exactly.
#
# Every handler no-ops when the flag is genuinely on, so real Nevermelting Hail
# keeps vanilla behavior and nothing is applied twice.
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
  # Vanilla already applied its own x0.5 when the flag is really on.
  next 1.0 if move.battle.state.effects[:NeverMeltIce]
  next 1.0 unless move.pbIsSpecial?(attacker, move.pbType(attacker))
  0.5
}

# --- Chip damage, 1/16 to match burn ---------------------------------------
CHROOKED_STATUS_TURN_END[:FROZEN] = lambda { |battler, battle|
  next if battler.crested == :SUICUNE
  next if battle.magicGuardAbilities.include?(battler.ability)
  # Vanilla already chipped (at its own 1/8) when the flag is really on.
  next if battle.state.effects[:NeverMeltIce]
  battler.pbContinueStatus
  battler.pbReduceHP((battler.totalhp / 16.0).floor)
  battler.pbFaint if battler.isFainted?
}

# --- No turn skip, but keep the Fire-move thaw -----------------------------
# The turn-skip block in pbTryUseMove is guarded by `!NeverMeltIce`, so flipping
# the flag on for the duration of that one call skips the block wholesale. The
# flip is scoped to the call and restored in an ensure, so nothing outside sees
# it — that is what keeps this off the weather display and the NeverMeltIce item,
# which the always-on-flag approach would have changed.
#
# Skipping the block also discards its Fire-move thaw branch, so that branch is
# re-done here first, minus the random thaw roll and the turn cancellation.
module ChrookedFrostbiteNoTurnSkip
  def pbTryUseMove(*args, **kwargs)
    basemove = args[1]
    if self.status == :FROZEN && basemove.respond_to?(:canThawUser?) &&
       basemove.canThawUser? && !(basemove.move == :BURNUP && !self.hasType?(:FIRE))
      self.pbCureStatus(false)
      @battle.pbDisplay(_INTL("{1}'s {2} melted the frost!", pbThis, basemove.name))
    end
    state = @battle.state.effects
    was = state[:NeverMeltIce]
    state[:NeverMeltIce] = true
    begin
      super
    ensure
      state[:NeverMeltIce] = was
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
