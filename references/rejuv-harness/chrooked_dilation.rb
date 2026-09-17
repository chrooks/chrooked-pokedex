# chrooked:dilation
# Dilation — "Warps the field's time on entry."
#   switch-in: Trick Room inactive => start it for 5 turns (Drought shape, but
#     for the room). Trick Room active => end it instead.
#   Mirrors the Dimensional Field entry branch (Battler.rb:4255-4264) and the
#   move itself: @battle.state.effects[:TrickRoom] is the counter, ticked down
#   in pbEndOfRoundPhase (Battle.rb:6944), set via pbSetTrickRoom (Battle.rb:702).
# Test cases:
#   - switch in, no Trick Room       => "twisted the dimensions", slow mons move first for 5 turns
#   - switch in while Trick Room up  => "returned to normal", speed order restored
#   - Frozen Dimension field         => counter set but never decrements (vanilla field rule)
CHROOKED_SWITCH_IN[:DILATION] = lambda { |battler, battle|
  battle.pbShowAbilityBox(battler)
  battle.pbAnimation(:TRICKROOM, battler, nil)
  if battle.state.effects[:TrickRoom] == 0
    battle.pbDisplay(_INTL("{1} twisted the dimensions!", battler.pbThis))
    battle.pbSetTrickRoom(5)
  else
    battle.pbDisplay(_INTL("The twisted dimensions returned to normal!"))
    battle.state.effects[:TrickRoom] = 0
  end
  battle.pbHideAbilityBox(battler)
}
