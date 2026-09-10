# chrooked:impenetrable
# Impenetrable — Magic Guard clone: only direct attacks damage the holder.
#   Direct move damage routes through pbReduceHPDamage and is untouched. Every
#   other source — hazards, residual ticks, Life Orb, own-move recoil — is gated
#   by vanilla on magicGuardAbilities, so the holder joins that list (below).
#   Weather chip does NOT route through pbReduceHP at all — the sand/hail tick
#   subtracts HP directly in pbReduceBattlersHP (Battle.rb:7877) — so it is
#   covered by CHROOKED_WEATHER_IMMUNE via the core's takesWeatherDamage? wrapper.
# ponytail: message-less pbReduceHP ticks slip through (e.g. Battle.rb:5930) and
#   Toxic Spikes can still poison on entry (status, not damage; its gate at
#   Battle.rb:3243 is mid-method) — extend if either shows up in play.
# ponytail: the AI's residual model doesn't know this ability — trainers
#   under-rate the holder's survivability. Teach Battle_AI if it ever matters.
# Test cases:
#   - burn + sandstorm at end of turn => 0 chip from both
#   - Head Smash / Double-Edge => 0 recoil taken
#   - switch-in on Stealth Rock => 0 damage
#   - Leech Seed => no HP sapped, seeder heals nothing
# Rejuv gates 62 damage sources on magicGuardAbilities (Battle.rb:893) — hazards,
# every residual tick, Life Orb, and getRecoil (Battle_Move.rb:2271). Registering
# here covers all of them, including own-move recoil: vanilla Magic Guard blocks
# Head Smash / Double-Edge recoil in this engine, and so does this.
CHROOKED_MAGIC_GUARD << :IMPENETRABLE
# Belt-and-braces for message-carrying pbReduceHP ticks that vanilla forgot to
# gate on magicGuardAbilities. The recoil exception is gone: getRecoil now
# returns 0 first, so no recoil message is ever raised for a holder.
CHROOKED_HP_LOSS_VETO[:IMPENETRABLE] = lambda { |battler, message|
  !message.to_s.empty?
}
CHROOKED_WEATHER_IMMUNE[:IMPENETRABLE] = [:SANDSTORM, :HAIL, :SHADOWSKY]
