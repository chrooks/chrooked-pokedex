# Runnable check for the multi-type immunity seam. No game needed:
#   docker run --rm -v "$PWD/references/rejuv-harness:/h:ro" ruby:3.2-slim ruby /h/airborne_check.rb
CHROOKED_TYPE_IMMUNITY = {}

module Chrooked
  def self.entries(table, ability) = [table[ability]].compact
  def self.immunities(table, ability)
    entries(table, ability).flat_map { |e| e.is_a?(Hash) ? [e] : e }
  end
end

require_relative "chrooked_airborne"
CHROOKED_TYPE_IMMUNITY[:WINGSPAN] = { type: :GROUND, flag: :Soundproof } # single-hash holdout

def check(label) = (yield ? puts("ok   #{label}") : abort("FAIL #{label}"))

air = Chrooked.immunities(CHROOKED_TYPE_IMMUNITY, :AIRBORNE)
check("Airborne blocks two types")      { air.size == 2 }
check("Airborne Flying uses Soundproof"){ air.any? { |i| i[:type] == :FLYING && i[:flag] == :Soundproof } }
check("Airborne Ground uses Levitate")  { air.any? { |i| i[:type] == :GROUND && i[:flag] == :Levitate } }

# The typemod reader only zeroes Soundproof blocks, so Ground must NOT zero it —
# it rides the vanilla :Levitate hitflag instead. This is the crash that shipped.
zeroed = ->(atype) { air.any? { |i| i[:flag] == :Soundproof && atype == i[:type] } }
check("Flying zeroes the typemod")      { zeroed.(:FLYING) }
check("Ground does not zero the typemod"){ !zeroed.(:GROUND) }

old = Chrooked.immunities(CHROOKED_TYPE_IMMUNITY, :WINGSPAN)
check("single-hash entries still work") { old == [{ type: :GROUND, flag: :Soundproof }] }
check("unknown ability returns empty")  { Chrooked.immunities(CHROOKED_TYPE_IMMUNITY, :NOPE) == [] }
puts "all checks passed"
