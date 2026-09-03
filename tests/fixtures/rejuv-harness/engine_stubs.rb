# Rejuv engine classes the chrooked mods reach for AT LOAD TIME.
#
# A mod that prepends or alias-chains onto an engine class touches it the
# moment the file is eval'd, before any test drives anything. In the real game
# those classes always exist, so the mods correctly guard on their OWN module
# being defined rather than on the target — which leaves the harness to supply
# the target. Miss one and every mod file after it fails to load, taking the
# whole harness red on a NameError far from the real cause.
#
# These are inert placeholders ONLY. Anything a test actually drives —
# PokeBattle_Move, PokeBattle_Battler — stays in that test's own fixture,
# because each one needs a different shape and sharing them would couple
# unrelated checks together.
#
# Loaded by lambda_checks.rb and event_checks.rb via require_relative, and read
# verbatim into the inline stub in tests/test_rejuv_applier.py. Add to this file
# when a new mod prepends onto a class Rejuv has and we do not.

def _INTL(s, *a); s; end

# Rejuv's party-menu registry — the zz_* QoL mods register handlers on it.
module MenuHandlers
  def self.add(*args, &blk); end
end

# Rejuv's overworld sprite class — chrooked_zz_kirincull alias-chains #update,
# so the method must exist before the shim is eval'd.
class Sprite_Character
  def update; end
end

# The party Pokemon class — chrooked_zz_darmanitan prepends onto it to stop the
# engine reverting a deliberately chosen Zen form.
class PokeBattle_Pokemon; end

# The battle object. Nothing prepends onto it today; the lambdas take one as an
# argument and only ever call methods the per-test stubs define.
class PokeBattle_Battle; end
