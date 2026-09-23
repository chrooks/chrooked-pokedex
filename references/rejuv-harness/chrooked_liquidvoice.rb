# chrooked:liquidvoice
# Liquid Voice — vanilla (sound moves become Water-type) plus a Chrooked rider:
#   sound moves also deal 30% more damage.
#   damage-calc: sound move => x1.3
# The type conversion is native Rejuv and is left alone; only the boost is added,
# so every existing Liquid Voice holder (Ducklett, Swanna) gains it too.
# Test cases (drive in-game):
#   - Hyper Voice => resolves as Water AND hits 30% harder
#   - Boomburst   => same
#   - Surf (not a sound move) => unchanged
CHROOKED_DAMAGE_MODS[:LIQUIDVOICE] = lambda { |move, attacker, opponent|
  (move.respond_to?(:isSoundBased?) && move.isSoundBased?) ? 1.3 : 1.0
}
