# chrooked:zz_abilityresync
# mod-group: convenience
# mod-summary: A Pokémon whose saved ability its species no longer has re-derives it from its ability slot.
# Static QoL mod (not a Ruleset behavior) — installed unless turned off for the Target.
#
# Essentials memoizes Pokemon#ability_id into @ability, and the save keeps it. A
# Ruleset apply that changes a species' abilities therefore leaves every mon the
# player already owns on its old one: a Butterfree kept Compound Eyes after the
# line moved to Levitate and took Ground damage; a Magmar kept Flame Body and took
# Fire damage. This drops the stale memo whenever it names an ability the species
# no longer lists, so ability_index re-derives it (slot 0/1 regular, 2 hidden),
# exactly as an evolution does.
#
# ponytail: an ability a script set outside the species' lists (Pokemon#ability=)
# is re-derived too; add a keep-list here if an event mon ever needs one.
# No Rejuv port: Rejuv reads the ability from its slot on every call, so a
# species change reaches owned mons there already.
class Pokemon
  alias chrooked_abilityresync_ability_id ability_id
  def ability_id
    if @ability
      sp = species_data
      @ability = nil unless sp.abilities.include?(@ability) || sp.hidden_abilities.include?(@ability)
    end
    chrooked_abilityresync_ability_id
  end
end
