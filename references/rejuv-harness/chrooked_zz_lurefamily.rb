# chrooked:zz_lurefamily
# Static QoL mod (not a Ruleset behavior) — always installed by apply.
#
# Magnetic Lure counts whole evolution families. Base Rejuv filters a wild
# species out only when that exact species is owned, so owning Raichu still
# lets the lure pull Pikachu before an uncaught Butterfree. Here a species is
# "known" when ANY member of its line is owned: walk back to the baby
# (pbGetBabySpecies), then forward through every evolution edge, and ask the
# base meaningful_owned? check of each member.
#
# ponytail: full-method override of pbFilterKnownPkmnFromEncounter — re-sync
# from Scripts/Encounters.rb if a Rejuv update changes it. Only the owned
# check differs. The family walk is an uncached BFS over a handful of nodes,
# run once per lure encounter.
module ChrookedLureFamily
  # [species, form] pairs in the line, pre-evos and every branch included.
  def self.members(species, form)
    queue = [pbGetBabySpecies(species, form)]
    seen = []
    until queue.empty?
      node = queue.shift
      next if seen.include?(node)

      seen << node
      (pbGetEvolvedFormData(*node) || []).each do |evo|
        # A non-numeric :form (e.g. :nature) resolves at evolution time; keep ours.
        queue << [evo[:species], evo[:form].is_a?(Numeric) ? evo[:form] : node[1]]
      end
    end
    seen
  end

  def self.owned?(species, form)
    return true if $Trainer.pokedex.meaningful_owned?(species, form) # base check first

    # Encounter tables can list a form Range; the evolution data wants one form.
    walk_form = form.is_a?(Numeric) ? form : Array(form).first || 0
    members(species, walk_form).any? { |s, f| $Trainer.pokedex.meaningful_owned?(s, f) }
  end
end

class PokemonEncounters
  def pbFilterKnownPkmnFromEncounter(chances, encounters)
    uncaptured = []
    for i in 0...encounters.length
      next if !chances[i] || chances[i] <= 0

      enc = encounters[i]
      next if !enc

      species = enc[0]
      if species.is_a?(Array)
        form = species[1].is_a?(Symbol) ? pbDetermineForm(species[1]) : species[1]
        species = species[0]
      else
        form = 0
      end
      next if ChrookedLureFamily.owned?(species, form)

      uncaptured.push(enc)
    end
    return nil if uncaptured.length <= 0

    return uncaptured[rand(uncaptured.length)]
  end
end
