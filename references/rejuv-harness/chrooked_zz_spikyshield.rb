# chrooked:zz_spikyshield
# Spiky Shield buff — contact chip raised from 1/8 to 1/6 of the attacker's max HP.
#
# Rejuv resolves every protect-variant's on-contact rider in one `case hitflag`
# block inside moveFailureEffects. Rather than re-implement that branch, let
# vanilla apply its own 1/8 and then top up the difference, which is
# floor(hp/6) - floor(hp/8) and NOT a flat 1/24.
#
# The top-up only fires when vanilla's chip actually landed (HP moved), so every
# gate vanilla already applies — Magic Guard, a substitute, an already-fainted
# attacker — gates the extra too, with no second check to keep in sync.
#
# The Colosseum field already chips for 1/4, which is harsher than 1/6, so that
# field is left alone.
#
# Test cases:
#   - contact move into Spiky Shield, 120 max HP => 20 total chip (was 15)
#   - Magic Guard attacker => no chip at all, top-up skipped
#   - non-contact move => no chip, top-up skipped
#   - Colosseum field => still 1/4, untouched
module ChrookedSpikyShield
  def moveFailureEffects(user, basemove, target, hitflag)
    before = user.hp
    result = super
    if hitflag == :SpikyShield && @battle.FE != :COLOSSEUM &&
       user.hp < before && !user.isFainted?
      extra = (user.totalhp / 6.0).floor - (user.totalhp / 8.0).floor
      user.pbReduceHP(extra, true) if extra > 0
    end
    result
  end
end
PokeBattle_Battler.prepend(ChrookedSpikyShield)
