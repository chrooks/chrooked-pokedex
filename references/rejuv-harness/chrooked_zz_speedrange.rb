# encoding: utf-8
# chrooked:zz_speedrange
# Static UI mod (not a Ruleset behavior) — always installed by apply.
#
# The R key on the fight menu already opens DemICE's Battle Stats screen for the
# opposing mon: typing, base stats, stages. It prints "Base Spe: 102" and nothing
# about the real number. This mod appends a POSSIBLE-SPEED RANGE to that line and
# narrows it turn by turn from what the player could infer by watching:
#
#   start   : the raw stat range at this level (IV 0/EV 0/-nature .. IV 31/EV 252/+nature)
#   each turn: for every (opponent, player mon) pair that both used a move at equal
#             priority, the one that moved first was at least as fast:
#               opponent first  => lo = max(lo, my effective speed)
#               player first    => hi = min(hi, my effective speed)
#             Trick Room flips the reading. Ties are random, so bounds stay inclusive.
#   reset   : when a new Pokemon fills the opposing slot (checked lazily by owner).
#
# ponytail: bounds are on the opponent's EFFECTIVE speed (stages, item, weather
# included) while the starting range is the RAW stat; a Choice Scarf or +2 can push
# the truth above the raw ceiling, in which case the range clamps to what was seen.
# Upgrade path: reset the bounds when the opponent's Speed stage or item changes.
module ChrookedSpeedRange
  IV_MAX = 31
  EV_MAX_QUARTER = 63   # 252 EVs / 4

  def self.raw_range(battler)
    base = battler.pokemon.baseStats[PBStats::SPEED]
    lv = battler.level
    lo = (((2 * base) * lv / 100).floor + 5)
    hi = (((2 * base + IV_MAX + EV_MAX_QUARTER) * lv / 100).floor + 5)
    [(lo * 0.9).floor, (hi * 1.1).floor]
  end

  def self.range(battler)
    # A new Pokemon in the slot resets the bounds (Battler objects are reused per slot).
    owner = battler.pokemon.object_id
    if battler.chrooked_spd_owner != owner
      battler.chrooked_spd_owner = owner
      battler.chrooked_spd_lo = nil
      battler.chrooked_spd_hi = nil
    end
    lo, hi = raw_range(battler)
    lo = battler.chrooked_spd_lo if battler.chrooked_spd_lo
    hi = battler.chrooked_spd_hi if battler.chrooked_spd_hi
    hi = lo if hi < lo   # clamp when the truth left the raw range
    [lo, hi]
  end

  def self.observe(battle, order)
    trick_room = battle.state.effects[:TrickRoom] > 0
    order.each_with_index do |opp, oi|
      next unless battle.pbIsOpposing?(opp.index)
      next unless battle.choices[opp.index][0] == :move
      order.each_with_index do |mine, mi|
        next unless battle.pbOwnedByPlayer?(mine.index)
        next unless battle.choices[mine.index][0] == :move
        so, sm = battle.speedData[opp.index], battle.speedData[mine.index]
        next unless [:actPriority, :movePriority, :subPriority].all? { |k| so[k] == sm[k] }
        my_speed = mine.pbSpeed
        lo, hi = range(opp)
        opp_faster = (oi < mi) ^ trick_room
        if opp_faster
          lo = [lo, my_speed].max
        else
          hi = [hi, my_speed].min
        end
        opp.chrooked_spd_lo = lo
        opp.chrooked_spd_hi = hi
      end
    end
  end

  module BattlerHooks
    attr_accessor :chrooked_spd_lo, :chrooked_spd_hi

    # ponytail: no pbInitPokemon hook — chrooked_zz_zcompose aliases that method
    # and a prepend in front of it loops the alias back into itself (stack overflow,
    # 2026-09-06). Ownership is checked lazily instead: see ChrookedSpeedRange.range.
    attr_accessor :chrooked_spd_owner

    # Battle Stats screen: "Base Spe: 102" -> "Base Spe: 102  [200-300]" for foes.
    def pbGetBaseStatInspect(stat)
      value = super
      return value unless stat == PBStats::SPEED && @battle.pbIsOpposing?(@index)
      lo, hi = ChrookedSpeedRange.range(self)
      "#{value}  [#{lo}-#{hi}]"
    end
  end

  module BattleHooks   # battle already exposes speedData / choices / state

    def setMoveOrder
      order = super
      ChrookedSpeedRange.observe(self, order)
      order
    end
  end
end

PokeBattle_Battler.prepend(ChrookedSpeedRange::BattlerHooks)
PokeBattle_Battle.prepend(ChrookedSpeedRange::BattleHooks)
