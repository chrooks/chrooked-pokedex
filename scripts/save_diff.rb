# save_diff.rb — what changed between two Essentials save files, without the game.
#
# An Essentials save (Game.rxdata) is a Ruby Marshal dump of game objects. Marshal
# only needs each class to exist, so unknown classes are stubbed as they are met
# (plain instance variables, or _load for RGSS user dumps), and both saves are
# flattened to field paths and compared. Written for mjolnir NV-10, to tell an
# in-game save from anything a proof boot could have done (runbook 31).
#
# Usage: ruby scripts/save_diff.rb BEFORE.rxdata AFTER.rxdata [--events]
#   Map events' per-frame timers change on every save; they are hidden unless
#   --events is given. Look first at [:game_system].save_count and
#   [:game_player].x / .y.
class StubBase
  def self._load(str) = new.tap { |o| o.instance_variable_set(:@_raw, str) }
end

def stub_const(path)
  parent = Object
  path.split("::").each do |name|
    parent = if parent.const_defined?(name, false)
               parent.const_get(name, false)
             else
               parent.const_set(name, Class.new(StubBase))
             end
  end
end

def load_save(file)
  data = File.binread(file)
  begin
    Marshal.load(data)
  rescue ArgumentError, TypeError => e
    raise unless e.message =~ /undefined class\/module (\S+)/
    stub_const(Regexp.last_match(1))
    retry
  end
end

def flat(obj, path = "", out = {}, depth = 0)
  return out if depth > 6
  case obj
  when Hash
    obj.each { |k, v| flat(v, "#{path}[#{k.inspect}]", out, depth + 1) }
  when Array
    if obj.length <= 40
      obj.each_with_index { |v, i| flat(v, "#{path}[#{i}]", out, depth + 1) }
    else
      out[path] = "Array(#{obj.length}) #{obj.hash}"
    end
  when Numeric, String, Symbol, TrueClass, FalseClass, NilClass
    out[path] = obj.inspect[0, 80]
  else
    ivars = obj.instance_variables
    out[path + "<#{obj.class}>"] = "" if ivars.empty?
    ivars.each { |iv| flat(obj.instance_variable_get(iv), "#{path}.#{iv.to_s.delete('@')}", out, depth + 1) }
  end
  out
end

files = ARGV.reject { |a| a.start_with?("--") }
abort("usage: ruby save_diff.rb BEFORE AFTER [--events]") unless files.size == 2
a, b = files.map { |f| flat(load_save(f)) }
diff = (a.keys | b.keys).reject { |k| a[k] == b[k] }
shown = ARGV.include?("--events") ? diff : diff.reject { |k| k.include?("].events[") }
puts "#{a.size} fields before, #{b.size} after, #{diff.size} differ (#{diff.size - shown.size} event timers hidden)"
shown.each { |k| puts "  #{k}: #{a[k].inspect} -> #{b[k].inspect}" }
