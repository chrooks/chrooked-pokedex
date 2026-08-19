# chrooked:flareboost
# Flare Boost — the 1.5x special boost while burned is vanilla Rejuv
#   (Battle_Move.rb:1286 basemult, :374 calcspatk, AI twin Battle_AI.rb:13716);
#   this mod only adds the burn-chip immunity.
#   turn-end: the holder's own burn residual (Battle.rb:6555) is vetoed.
#   The tick is message-less, so the veto keys on the core's status-tick stamp
#   set by pbContinueStatus immediately before it.
#   External fire damage (Fire moves, Burning field, wildfire) is untouched;
#   field-side immunities are already native (Battle_Field.rb:1133, Battle.rb:6059).
# ponytail: the AI's residual model still docks burn chip from the holder's
#   projected HP — trainers under-rate it slightly. Refund it if it matters.
# Test cases:
#   - burned holder at end of turn => "hurt by its burn!" message, 0 HP lost
#   - burned holder hit by Ember => normal damage
#   - burned holder + sandstorm => sandstorm chip still applies
CHROOKED_HP_LOSS_VETO[:FLAREBOOST] = lambda { |battler, message|
  message.nil? && battler.chrooked_consume_status_tick == :BURN
}
