# chrooked:impenetrable
# Impenetrable — Magic Guard clone: only direct attacks damage the holder.
#   Direct move damage routes through pbReduceHPDamage and is untouched; every
#   passive/residual tick (status, weather, hazards, Leech Seed, binding, curse,
#   Life Orb, crash damage) routes through pbReduceHP WITH a message — veto those.
#   Own-move recoil keeps its damage (spec: self-inflicted), keyed on Rejuv's
#   "was damaged by the recoil!" message (Battle_Move.rb:2277).
# ponytail: message-less pbReduceHP ticks slip through (e.g. Battle.rb:5930) and
#   Toxic Spikes can still poison on entry (status, not damage; its gate at
#   Battle.rb:3243 is mid-method) — extend if either shows up in play.
# ponytail: the AI's residual model doesn't know this ability — trainers
#   under-rate the holder's survivability. Teach Battle_AI if it ever matters.
# Test cases:
#   - burn + sandstorm at end of turn => 0 chip from both
#   - Double-Edge => normal recoil still taken
#   - switch-in on Stealth Rock => 0 damage
#   - Leech Seed => no HP sapped, seeder heals nothing
CHROOKED_HP_LOSS_VETO[:IMPENETRABLE] = lambda { |battler, message|
  msg = message.to_s
  !msg.empty? && !msg.include?("recoil")
}
