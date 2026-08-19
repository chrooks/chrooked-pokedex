# chrooked:toxicboost
# Toxic Boost — the 1.5x physical boost while poisoned is vanilla Rejuv
#   (Battle_Move.rb:1288 basemult); this mod only adds the poison-chip immunity.
#   The spec's old "NATIVE" claim was wrong for the status residual: Rejuv only
#   exempts TOXICBOOST from FIELD poison (Battle_Field.rb:1156, corrosive at
#   Battle.rb:6594) — the plain end-of-round poison tick (Battle.rb:6496) still
#   hits the holder. Veto it the same way Flare Boost vetoes burn.
#   turn-end: the holder's own poison/toxic residual is vetoed via the core's
#   status-tick stamp (the tick's pbReduceHP is message-less).
# Test cases:
#   - poisoned holder at end of turn => "hurt by poison!" message, 0 HP lost
#   - badly poisoned holder => 0 HP lost, Toxic counter still climbs
#   - poisoned holder + Leech Seed => seed drain still applies
CHROOKED_HP_LOSS_VETO[:TOXICBOOST] = lambda { |battler, message|
  message.nil? && battler.chrooked_consume_status_tick == :POISON
}
