# chrooked:medium
# Medium — "Contact moves use Sp. Atk instead of Attack."
#   The body is the medium and the touch delivers it: gas, flame, venom,
#   current, cold carried by contact. Also the spiritualist's medium.
#   damage-calc: physical contact move => attacker's Sp. Atk replaces Attack.
#   The move stays physical otherwise (target's Defense, contact effects,
#   category checks). No power boost — contact is a broad set, unlike the
#   punch / slice gates of Magical Fists and Mystic Blades.
# Test cases:
#   - Lick from 120 SpA / 95 Atk => damage computed off 120
#   - Shadow Ball (non-contact) => vanilla, Sp. Atk as normal
#   - Ice Punch into a high-Defense foe => still checked against Defense
#   - Frost Body / Rocky Helmet contact effects => still fire (still contact)
CHROOKED_STAT_SWAP[:MEDIUM] = lambda { |move, attacker|
  move.contactMove? && move.pbIsPhysical?(attacker, move.pbType(attacker))
}
