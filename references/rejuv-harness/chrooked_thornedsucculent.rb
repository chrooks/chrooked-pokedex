# chrooked:thornedsucculent
# Thorned Succulent — Water Absorb + Iron Barbs + sandstorm immunity, for cacti.
# A COMPOSED ability: ruleset/abilities/thornedsucculent.yaml declares
# behaviors [thornedsucculent, waterabsorb, ironbarbs], so chrooked_zz_zcompose.rb
# makes the battler's ability a set that answers == :WATERABSORB and == :IRONBARBS
# to every vanilla branch. Those two parts need no code here.
#   turn-end: no sandstorm residual (CHROOKED_WEATHER_IMMUNE, core takesWeatherDamage? wrapper)
# Test cases:
#   - Surf at 50% HP      => absorbed, +1/4 HP (vanilla Water Absorb)
#   - Poison Jab (contact) => attacker loses 1/8 (vanilla Iron Barbs)
#   - sand end of turn     => 0 chip
CHROOKED_WEATHER_IMMUNE[:THORNEDSUCCULENT] = [:SANDSTORM]
