# chrooked:thornedsucculent
# ---------------------------------------------------------------------------
# Ruleset ability "thornedsucculent": its own sandstorm immunity, plus Water Absorb and
# Iron Barbs (the Ruleset composes it as thornedsucculent + waterabsorb + ironbarbs).
#
# HAND-WRITTEN WHOLE (mjolnir NV-26). An ability that lists itself among its parts
# cannot be a generated composition: its own port takes chrooked_<id>.rb. So this file
# is the whole ability, built as behavior/compose.py builds one:
#   - its own part: Battle::Battler#takesSandstormDamage? answers no for the holder;
#   - Water Absorb: Nova's MoveImmunity handler, copied to the ability (a Water move
#     fails and heals a quarter, through pbMoveImmunityHealingAbility);
#   - Iron Barbs: Nova's OnBeingHit handler, copied (a contact attacker loses 1/8);
#   - by name: the holder answers hasActiveAbility? for Water Absorb and Iron Barbs, as
#     a composed battler answers for its parts, so the AI sees them too.
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md. Its checks measure it; the copied
# handlers are Nova's own and log nothing.
# ---------------------------------------------------------------------------

unless defined?(ChrookedLog)
  module ChrookedLog
    # Resolved once, at load, while the working directory is the game folder.
    LOG     = File.expand_path("chrooked_load.log")
    ENABLED = File.exist?(File.expand_path("chrooked-oracle.on"))

    def self.line(msg)
      write(msg) if ENABLED
    end

    def self.error(msg)
      write(msg)
    end

    def self.write(msg)
      File.open(LOG, "a") { |f| f.puts(msg) }
    rescue StandardError
      nil
    end
  end
end

begin
  ChrookedLog.line("[chrooked:thornedsucculent] load prior_handler=" \
                   "#{!Battle::AbilityEffects::MoveImmunity[:THORNEDSUCCULENT].nil?}")
  Battle::AbilityEffects::MoveImmunity.copy(:WATERABSORB, :THORNEDSUCCULENT)
  Battle::AbilityEffects::OnBeingHit.copy(:IRONBARBS, :THORNEDSUCCULENT)
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_thornedsucculent_takesSandstormDamage?)
      alias_method :chrooked_thornedsucculent_takesSandstormDamage?, :takesSandstormDamage?
      def takesSandstormDamage?
        return false if hasActiveAbility?(:THORNEDSUCCULENT)
        chrooked_thornedsucculent_takesSandstormDamage?
      end
    end
    unless method_defined?(:chrooked_thornedsucculent_hasActiveAbility?)
      alias_method :chrooked_thornedsucculent_hasActiveAbility?, :hasActiveAbility?
      def hasActiveAbility?(check_ability, ignore_fainted = false)
        asked = check_ability.is_a?(Array) ? check_ability : [check_ability]
        if (asked & [:WATERABSORB, :IRONBARBS]).any? &&
           chrooked_thornedsucculent_hasActiveAbility?(:THORNEDSUCCULENT, ignore_fainted)
          return true
        end
        chrooked_thornedsucculent_hasActiveAbility?(check_ability, ignore_fainted)
      end
    end
  end
  ($chrooked_selftest_cases ||= {})["thornedsucculent"] = {
    ability: :THORNEDSUCCULENT, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["surf", ->(t, spec) {
        b, attacker, holder = t.pair(spec, :SURF)
        holder.ability = spec[:ability]
        holder.hp = holder.totalhp / 2
        hp, foe_hp = holder.hp, attacker.hp
        surf = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:SURF))
        surf.calcType = surf.pbCalcType(attacker)
        immune = !!surf.pbImmunityByAbility(attacker, holder, true)
        "immune=#{immune} healed=#{holder.hp - hp} quarter=#{holder.totalhp / 4} foe_change=#{attacker.hp - foe_hp}"
      }],
      ["poison_jab", ->(t, spec) {
        b, attacker, holder = t.pair(spec, :POISONJAB)
        holder.ability = spec[:ability]
        jab = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:POISONJAB))
        jab.calcType = jab.pbCalcType(attacker)
        holder.damageState.reset
        holder.damageState.hpLost = holder.damageState.calcDamage = 20
        hp = attacker.hp
        Battle::AbilityEffects.triggerOnBeingHit(holder.ability, attacker, holder, jab, b)
        "move=POISONJAB contact=#{jab.pbContactMove?(attacker)} foe_change=#{attacker.hp - hp} " \
        "eighth=#{attacker.hp - hp == -(attacker.totalhp / 8)}"
      }],
      ["sandstorm", ->(t, spec) {
        with, none = [spec[:ability], nil].map { |a| t.keep_measure(spec, :eor_weather, {weather: :Sandstorm}, a) }
        "sand_with=#{with} sand_none=#{none} spared=#{with == 0 && none < 0}"
      }],
      # Beside the test cases: the battle code and the AI ask for the parts by name.
      ["identity", ->(t, spec) {
        _b, holder, _foe = t.pair(spec, :TACKLE)
        holder.ability = spec[:ability]
        "water_absorb=#{holder.hasActiveAbility?(:WATERABSORB)} iron_barbs=#{holder.hasActiveAbility?(:IRONBARBS)} " \
        "levitate=#{holder.hasActiveAbility?(:LEVITATE)}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:thornedsucculent] installed: Water Absorb and Iron Barbs copied, sandstorm spared")
rescue StandardError => e
  ChrookedLog.error("[chrooked:thornedsucculent] ERROR #{e.class}: #{e.message}")
end
