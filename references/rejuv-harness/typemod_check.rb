# Standalone check of the Gastric Snare / Corrosion / Sky Uppercut typemod math.
# Reimplements Rejuv's Typemod#* and the Poison + Fighting rows of the chart,
# then runs the three lambdas verbatim from the mod files.
class Typemod
  attr_reader :numerator, :denominator
  def initialize(n = 1, d = 1); @numerator = n; @denominator = d; end
  def *(o)
    n = numerator * o.numerator; d = denominator * o.denominator
    d = 1 if n == 0
    if n > 1 && d > 1
      m = [n, d].min; n /= m; d /= m
    end
    Typemod.new(n, d)
  end
  def immune?; @numerator <= 0; end
  def multiplier; (@numerator == -1 ? 0 : @numerator) * 1.0 / @denominator; end
end

module PBTypes
  POISON_ROW = { BUG: [1,1], FLYING: [1,1], STEEL: [0,1], GROUND: [1,2],
                 NORMAL: [1,1], GRASS: [2,1], FAIRY: [2,1], POISON: [1,2] }
  FIGHTING_ROW = { FLYING: [1,2], NORMAL: [2,1], GHOST: [0,1], ROCK: [2,1],
                   FIGHTING: [1,1] }
  ROWS = { POISON: POISON_ROW, FIGHTING: FIGHTING_ROW }
  def self.oneTypeEff(atype, dtype)
    row = ROWS.fetch(atype) { raise "chart gap #{atype}/#{dtype}" }
    n, d = row.fetch(dtype)
    Typemod.new(n, d)
  end
end

Opp = Struct.new(:types)

GASTRIC = lambda { |move, atype, attacker, opponent, typemod|
  opponent.types.each do |opptype|
    next unless opptype == :BUG
    chart = PBTypes.oneTypeEff(atype, :BUG)
    next if chart.immune?
    typemod *= Typemod.new(2 * chart.denominator, chart.numerator)
  end
  typemod
}

SKYUPPER = lambda { |move, atype, attacker, opponent, typemod|
  opponent.types.each do |opptype|
    next unless opptype == :FLYING
    chart = PBTypes.oneTypeEff(atype, :FLYING)
    next if chart.immune?
    typemod *= Typemod.new(2 * chart.denominator, chart.numerator)
  end
  typemod
}

CORROSION = lambda { |move, atype, attacker, opponent, typemod|
  next typemod unless atype == :POISON
  next typemod unless opponent.types.include?(:STEEL)
  rebuilt = Typemod.new(1, 1)
  opponent.types.each do |opptype|
    rebuilt *= opptype == :STEEL ? Typemod.new(2, 1) : PBTypes.oneTypeEff(atype, opptype)
  end
  rebuilt
}

# Mirrors core pbTypeModifier: vanilla chart, then ABILITY pass, then MOVE pass.
def resolve(types, corrosion:, gastric:)
  tm = Typemod.new(1, 1)
  types.each { |t| tm *= PBTypes.oneTypeEff(:POISON, t) }
  opp = Opp.new(types)
  tm = CORROSION.call(nil, :POISON, nil, opp, tm) if corrosion
  tm = GASTRIC.call(nil, :POISON, nil, opp, tm) if gastric
  tm.multiplier
end

# Same shape for the Fighting row: vanilla chart, then Sky Uppercut's MOVE pass.
def resolve_fighting(types, skyupper:)
  tm = Typemod.new(1, 1)
  types.each { |t| tm *= PBTypes.oneTypeEff(:FIGHTING, t) }
  tm = SKYUPPER.call(nil, :FIGHTING, nil, Opp.new(types), tm) if skyupper
  tm.multiplier
end

def check(label, got, want)
  ok = (got - want).abs < 1e-9
  puts "#{ok ? 'ok  ' : 'FAIL'} #{label}: got #{got}, want #{want}"
  ok
end

results = []
# Gastric Snare's Bug override
results << check("Caterpie (Bug), snare",        resolve([:BUG], corrosion: false, gastric: true), 2.0)
results << check("Scyther (Bug/Flying), snare",  resolve([:BUG, :FLYING], corrosion: false, gastric: true), 2.0)
results << check("Kangaskhan (Normal), snare",   resolve([:NORMAL], corrosion: false, gastric: true), 1.0)
# Corrosion's Steel override
results << check("Registeel (Steel), corrosion", resolve([:STEEL], corrosion: true, gastric: false), 2.0)
results << check("Steelix (Steel/Ground), corr", resolve([:STEEL, :GROUND], corrosion: true, gastric: false), 1.0)
results << check("Registeel, NO corrosion",      resolve([:STEEL], corrosion: false, gastric: false), 0.0)
# The composition case — the ordering bug this test exists to catch
results << check("Scizor (Bug/Steel), both",     resolve([:BUG, :STEEL], corrosion: true, gastric: true), 4.0)
# Corrosion must not touch non-Steel targets
results << check("Caterpie, corrosion only",     resolve([:BUG], corrosion: true, gastric: false), 1.0)
# Sky Uppercut's Flying override — the resisted-chart case (0.5x corrected to 2x)
results << check("Tornadus (Flying), uppercut",  resolve_fighting([:FLYING], skyupper: true), 2.0)
results << check("Tornadus, NO uppercut",        resolve_fighting([:FLYING], skyupper: false), 0.5)
results << check("Pidgeot (Nrm/Fly), uppercut",  resolve_fighting([:NORMAL, :FLYING], skyupper: true), 4.0)
results << check("Drifblim (Gho/Fly), uppercut", resolve_fighting([:GHOST, :FLYING], skyupper: true), 0.0)

abort("\n#{results.count(false)} FAILED") unless results.all?
puts "\nall #{results.size} passed"
