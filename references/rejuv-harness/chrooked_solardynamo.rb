# encoding: utf-8
# chrooked:solardynamo
# Solar Dynamo — "Summons harsh sunlight on entry. In sun, boosts the higher
#   attacking stat 1.5x with no HP drain."
#
# NO LAMBDAS HERE ON PURPOSE. This ability is declared in the Ruleset as
#   behaviors: [solarpower, drought]
# so chrooked_zz_zcompose.rb makes the holder a ChrookedAbilitySet of
# [:SOLARPOWER, :DROUGHT] at battler init. From there:
#   - vanilla's `ability == :DROUGHT` fires and sets the sun
#   - vanilla's `ability == :SOLARPOWER` fires and pays its sun boost
#   - chrooked_solarpower.rb's CORRECTING lambdas then apply on top, which is
#     what moves the boost onto the higher attacking stat and cancels the drain
#
# This file previously hand-copied Solar Power's damage rule, and drifted: it
# kept boosting Sp. Atk only after Solar Power was rebuilt to follow the higher
# attacking stat, and shipped wrong on Helioptile, Heliolisk, Sunkern and
# Sunflora. Composition is what makes that class of drift impossible — do not
# reintroduce a lambda here. Change the rule in chrooked_solarpower.rb instead
# and this follows automatically.
#
# Kept as a file (rather than deleted) because apply never prunes mods: a stale
# copy left in a target would still register the old lambdas.
