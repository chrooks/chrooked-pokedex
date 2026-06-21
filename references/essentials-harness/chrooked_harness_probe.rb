# chrooked:harness-probe  (M0 spike — Route A feasibility)
# ---------------------------------------------------------------------------
# Decides whether a headless PokeBattle_Battle (Route A) is cheap enough to
# build, or whether we stay on the proven log-oracle (Route B). It does NOT
# instantiate anything (that could crash the boot); it only reports, once the
# engine class exists, that PokeBattle_Battle is defined and how many arguments
# its constructor demands. A high-arity constructor (scene + parties + trainers)
# means a headless battle needs a full mock scene = Route A is not cheap.
#
# Safe to leave in place; it disarms after one report. RUBY 1.8-safe.
# ---------------------------------------------------------------------------

unless defined?($chrooked_log) && $chrooked_log
  $chrooked_log = lambda do |msg|
    begin
      d = File.expand_path(File.dirname(__FILE__))
      File.open(File.join(d, "chrooked_load.log"), "a") { |f| f.puts(msg) }
    rescue Exception
    end
  end
end

def chrooked_harness_probe_fire
  return if $chrooked_harness_probed
  return unless defined?(PokeBattle_Battle)
  $chrooked_harness_probed = true
  begin
    arity = PokeBattle_Battle.instance_method(:initialize).arity
    ($chrooked_log.call("[chrooked:harness] PokeBattle_Battle defined; #initialize arity=#{arity} (>=2 args => headless needs a mock scene+parties => Route B)") rescue nil)
  rescue Exception => e
    ($chrooked_log.call("[chrooked:harness] PokeBattle_Battle defined; arity probe failed: #{e.class}: #{e.message}") rescue nil)
  end
end

if defined?(PokeBattle_Battle)
  chrooked_harness_probe_fire
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_probe_orig)
      alias_method :update_chrooked_probe_orig, :update
      def update
        chrooked_harness_probe_fire unless $chrooked_harness_probed
        update_chrooked_probe_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:harness] probe armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:harness] ERROR: neither PokeBattle_Battle nor Graphics at load") rescue nil)
end
