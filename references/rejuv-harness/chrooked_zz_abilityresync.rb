# encoding: utf-8
# chrooked:zz_abilityresync
# mod-group: convenience
# mod-summary: A Pokémon whose saved ability its species no longer has re-derives it from its species list.
# Static QoL mod (not a Ruleset behavior) — installed unless turned off for the Target.
# Rejuvenation port of references/essentials21-harness/chrooked_zz_abilityresync.rb.
#
# Rejuv stores a Pokémon's ability in @ability once (initAbility) and the save
# keeps it. A Ruleset apply that changes a species' abilities therefore leaves
# every mon the player already owns on its old one: a Butterfree kept Compound
# Eyes after the line moved to Levitate and took Ground damage. Whenever the
# stored ability is one the species no longer lists, this re-rolls it the way
# initAbility does (personalID over the current list) and keeps the result.
#
# ponytail: the old slot is unrecoverable once the old list is gone, so a hidden-
# ability mon may land on a regular slot; an ability a script set outside the
# species' lists (setAbility) is re-rolled too. Add a keep-list here if an event
# mon ever needs one. originalAbility (Mega) is left alone: it is restored by the
# Mega code, not read through this getter.
class PokeBattle_Pokemon
  alias chrooked_abilityresync_ability ability
  def ability
    current = chrooked_abilityresync_ability
    return current if current.nil?
    list = getAbilityList
    return current if !list.is_a?(Array) || list.empty? || list.include?(current)
    initAbility
    chrooked_abilityresync_ability
  end
end
