# chrooked:impenetrable
# ---------------------------------------------------------------------------
# Ruleset behavior "impenetrable": Magic Guard, plus no poison from Toxic Spikes. No
# entry-hazard damage, no weather or status chip, no Curse, binding, Leech Seed or
# Nightmare damage, no recoil, no Rough Skin or Liquid Ooze; Sticky Web still applies.
#
# HAND-WRITTEN (mjolnir NV-26). Nova routes every one of those through one
# question, Battle::Battler#takesIndirectDamage?, whose only exemption is Magic Guard;
# the holder answers no there too, with Magic Guard's message where Nova shows one.
# Toxic Spikes poison through pbCanPoison? instead, so Battle#pbEntryHazards hides
# them from the holder for its entry (a Poison-type holder still absorbs them).
#
# Install, load order, the marker-gated oracle and the self-test registration at the
# end: references/essentials21-harness/README.md. It logs no OBS line of its own: Nova
# asks takesIndirectDamage? many times a round, the AI included; its checks measure it.
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
  ChrookedLog.line("[chrooked:impenetrable] load prior_wrapper=" \
                   "#{Battle::Battler.method_defined?(:chrooked_impenetrable_takesIndirectDamage?)}")
  Battle::Battler.class_eval do
    unless method_defined?(:chrooked_impenetrable_takesIndirectDamage?)
      alias_method :chrooked_impenetrable_takesIndirectDamage?, :takesIndirectDamage?
      def takesIndirectDamage?(showMsg = false)
        return chrooked_impenetrable_takesIndirectDamage?(showMsg) if fainted? || !hasActiveAbility?(:IMPENETRABLE)
        if showMsg   # Magic Guard's own message
          @battle.pbShowAbilitySplash(self)
          if Battle::Scene::USE_ABILITY_SPLASH
            @battle.pbDisplay(_INTL("{1} is unaffected!", pbThis))
          else
            @battle.pbDisplay(_INTL("{1} is unaffected because of its {2}!", pbThis, abilityName))
          end
          @battle.pbHideAbilitySplash(self)
        end
        return false
      end
    end
  end
  Battle.class_eval do
    unless method_defined?(:chrooked_impenetrable_pbEntryHazards)
      alias_method :chrooked_impenetrable_pbEntryHazards, :pbEntryHazards
      def pbEntryHazards(battler)
        side = battler.pbOwnSide
        layers = side.effects[PBEffects::ToxicSpikes]
        hide = layers > 0 && battler.hasActiveAbility?(:IMPENETRABLE) && !battler.pbHasType?(:POISON)
        side.effects[PBEffects::ToxicSpikes] = 0 if hide
        chrooked_impenetrable_pbEntryHazards(battler)
      ensure
        side.effects[PBEffects::ToxicSpikes] = layers if hide
      end
    end
  end
  # The holder (or a Pokemon with no ability) entering a side with the hazards set.
  chrooked_impenetrable_entry = lambda do |t, spec, ability, hazards|
    b, holder, _foe = t.pair(spec, :TACKLE)
    holder.ability = ability
    hazards.each { |effect, value| holder.pbOwnSide.effects[effect] = value }
    hp = holder.hp
    b.pbEntryHazards(holder)
    [holder.hp - hp, holder.status, holder.stages[:SPEED]]
  end
  ($chrooked_selftest_cases ||= {})["impenetrable"] = {
    ability: :IMPENETRABLE, control: nil, user: :NUMEL, foe: :SNORLAX, neutral: true,
    calc: [],
    checks: [
      ["burn_sand", ->(t, spec) {
        burn = [spec[:ability], nil].map { |a| t.keep_measure(spec, :eor_status, {status: :BURN}, a) }
        sand = [spec[:ability], nil].map { |a| t.keep_measure(spec, :eor_weather, {weather: :Sandstorm}, a) }
        "burn_with=#{burn[0]} burn_none=#{burn[1]} sand_with=#{sand[0]} sand_none=#{sand[1]} " \
        "spared=#{burn[0] == 0 && sand[0] == 0 && burn[1] < 0 && sand[1] < 0}"
      }],
      ["stealth_rock", ->(t, spec) {
        with, none = [spec[:ability], nil].map do |a|
          chrooked_impenetrable_entry.call(t, spec, a, {PBEffects::StealthRock => true})[0]
        end
        "rock_with=#{with} rock_none=#{none} spared=#{with == 0 && none < 0}"
      }],
      ["head_smash", ->(t, spec) {
        with, none = [spec[:ability], nil].map do |a|
          b, user, target = t.pair(spec, :HEADSMASH)
          user.ability = a
          move = Battle::Move.from_pokemon_move(b, Pokemon::Move.new(:HEADSMASH))
          target.damageState.reset
          target.damageState.totalHPLost = 100
          hp = user.hp
          move.pbEffectAfterAllHits(user, target)
          user.hp - hp
        end
        "recoil_with=#{with} recoil_none=#{none} spared=#{with == 0 && none < 0}"
      }],
      # Beside the test cases: Toxic Spikes poison nothing; Sticky Web still slows.
      ["toxic_spikes_web", ->(t, spec) {
        with, none = [spec[:ability], nil].map do |a|
          chrooked_impenetrable_entry.call(t, spec, a, {PBEffects::ToxicSpikes => 1, PBEffects::StickyWeb => true})
        end
        "status_with=#{with[1]} status_none=#{none[1]} speed_with=#{with[2]} speed_none=#{none[2]}"
      }]
    ],
    without: [],
    fight: [:TACKLE]
  }
  ChrookedLog.line("[chrooked:impenetrable] installed on Battler#takesIndirectDamage? and Battle#pbEntryHazards")
rescue StandardError => e
  ChrookedLog.error("[chrooked:impenetrable] ERROR #{e.class}: #{e.message}")
end
