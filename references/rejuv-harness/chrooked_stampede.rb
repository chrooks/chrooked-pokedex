# chrooked:stampede
# Stampede — "Knocking out a target arms a one-time +1 priority for the next
#   contact move." Armed on KO; priority delta read by the core priorityCheck
#   hook (effects[:ChrookedStampede]); consumed when a contact move deals damage.
# Test cases:
#   - KO a foe, then use a contact move => it acts at +1 priority, flag clears
#   - non-contact move while armed => normal priority, flag stays
CHROOKED_ON_KO[:STAMPEDE] = lambda { |battler, targets, basemove, battle|
  battler.effects[:ChrookedStampede] = true
}
CHROOKED_ON_DEAL[:STAMPEDE] = lambda { |move, user, target, battle|
  user.effects[:ChrookedStampede] = nil if user.effects[:ChrookedStampede] && user.makesContact?(move)
}
