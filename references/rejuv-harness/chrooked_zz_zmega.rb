# encoding: utf-8
# chrooked:zz_zmega
# Static mod (not a Ruleset behavior) — always installed by apply.
# A Mega keeps every ability it had before it Mega Evolved and gains the Mega
# form's ability on top. With "All Abilities" On that is the base species'
# whole list plus the Mega ability; with it Off, the one ability it had plus
# the Mega ability.
#
# Seam: pbMegaEvolve → pbUpdate(true) → changeAbility(@pokemon.ability), which
# throws away the ChrookedAbilitySet built at pbInitPokemon. We let that run
# (so the Mega ability's own entry effects fire), then union the old members
# back in and re-run composition so a composed Mega ability expands too.
#
# Sorts after chrooked_zz_zcompose.rb on purpose: Chrooked.composed_ability
# must exist before this hook is called.

if defined?(PokeBattle_Battler)
  class PokeBattle_Battler
    if method_defined?(:pbUpdate) && !method_defined?(:chrooked_zmega_update)
      alias_method :chrooked_zmega_update, :pbUpdate
      def pbUpdate(fullchange = false, noability: false, fakebattler: false)
        before = @ability
        chrooked_zmega_update(fullchange, noability: noability, fakebattler: fakebattler)
        return unless fullchange && !noability && @pokemon && (isMega? rescue false)
        return if before.nil? || @ability.nil?
        old_list = before.respond_to?(:list) ? before.list : [before]
        new_list = @ability.respond_to?(:list) ? @ability.list : [@ability]
        merged = (new_list + old_list).compact.uniq
        return if merged.length <= 1
        set = ChrookedAbilitySet.new(merged)
        set = Chrooked.composed_ability(set) if defined?(Chrooked) && Chrooked.respond_to?(:composed_ability)
        @ability = set
        @backupability = set
      end
    end
  end
end
