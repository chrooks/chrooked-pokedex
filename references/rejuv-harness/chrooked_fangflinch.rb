# chrooked:fangflinch
# Fang Flinch (move mechanic) — the chrooked stat-drop fangs carry their stat
# drop as a native function code; this adds their 10% flinch chance.
#   on-hit: Draconic/Lithic/Metallic/Tectonic Fang or Lovely Bite connects
#   => 10% flinch
# Test cases:
#   - stat-drop fang hit, roll succeeds => target flinches
#   - other moves => unaffected
FANGFLINCH_MOVES = [:DRACONICFANG, :LITHICFANG, :METALLICFANG,
                    :TECTONICFANG, :LOVELYBITE].freeze
FANGFLINCH_MOVES.each do |fang|
  CHROOKED_MOVE_ON_DEAL[fang] = lambda { |move, user, target, battle|
    next if target.isFainted? || battle.pbRandom(100) >= 10
    target.effects[:Flinch] = true
  }
end
