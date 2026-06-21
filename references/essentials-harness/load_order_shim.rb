# [LOAD_ORDER_SHIM] — chrooked Essentials 16.2 preload shim
# ---------------------------------------------------------------------------
# Loaded by mkxp.json -> preloadScript, BEFORE Data/Scripts.rxdata defines the
# engine classes. Its jobs:
#   1. Provide $chrooked_log, a guarded file logger. STDERR is a bad file
#      descriptor under the console-suppressed build, so NEVER write there;
#      everything goes to Scripts/chrooked_load.log next to this file.
#   2. Auto-load every Scripts/chrooked_*.rb plugin (the generalization that
#      makes this a reusable harness, not a one-off — each plugin defers its own
#      install onto the engine class via Graphics.update, see the plugins).
#
# RUBY 1.8 (this engine bundles 1.8): no prepend, no TracePoint, no 1.9 hash
# syntax. Keep everything 1.8-safe.
# ---------------------------------------------------------------------------

$chrooked_dir = File.expand_path(File.dirname(__FILE__))

unless defined?($chrooked_log) && $chrooked_log
  $chrooked_log = lambda do |msg|
    begin
      File.open(File.join($chrooked_dir, "chrooked_load.log"), "a") { |f| f.puts(msg) }
    rescue Exception
    end
  end
end

$chrooked_log.call("[LOAD_ORDER_SHIM] active") rescue nil

# Load every chrooked_*.rb plugin in this directory (except this shim). Sorted
# for deterministic order; each load is isolated so one bad plugin can't stop
# the rest or block the boot.
begin
  this_file = File.expand_path(__FILE__)
  Dir.glob(File.join($chrooked_dir, "chrooked_*.rb")).sort.each do |path|
    next if File.expand_path(path) == this_file
    begin
      load path
      ($chrooked_log.call("[LOAD_ORDER_SHIM] loaded #{File.basename(path)}") rescue nil)
    rescue Exception => e
      ($chrooked_log.call("[LOAD_ORDER_SHIM] ERROR loading #{File.basename(path)}: #{e.class}: #{e.message}") rescue nil)
    end
  end
rescue Exception => e
  ($chrooked_log.call("[LOAD_ORDER_SHIM] ERROR globbing plugins: #{e.class}: #{e.message}") rescue nil)
end
