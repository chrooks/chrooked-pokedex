# chrooked:zz_kirinprobe
# Kirin DIAGNOSTIC probe — NOT a Ruleset behavior, NOT a permanent shim.
# Hand-placed while hunting the weather-transition spike (2026-08-26).
#
# What it does: times the prime suspects for the transition hitch and appends
# one line to <game folder>/probe-kirin.log whenever a call is slow. Also logs
# FRAME_GAP whenever a whole frame takes over 100 ms, so a spike from code we
# did NOT wrap (e.g. a compiled common event) still leaves a fingerprint by
# its absence: FRAME_GAP lines with no suspect line beside them.
#
# Read the log over SSH (runbook 21): it lives beside Game.exe.
# Revert: delete this file. Zero cost when nothing is slow.
if $kirin
  CHROOKED_PROBE_LOG      = "probe-kirin.log"
  CHROOKED_PROBE_SLOW_MS  = 20.0
  CHROOKED_PROBE_FRAME_MS = 100.0

  def chrooked_probe(tag)
    t0 = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    result = yield
    dt = (Process.clock_gettime(Process::CLOCK_MONOTONIC) - t0) * 1000.0
    if dt >= CHROOKED_PROBE_SLOW_MS
      File.open(CHROOKED_PROBE_LOG, "a") { |f| f.puts("#{Time.now.strftime('%H:%M:%S')} #{tag} #{dt.round(1)}ms") }
    end
    result
  end

  if defined?(RPG) && defined?(RPG::Weather)
    module ChrookedProbeWeather
      def setWeatherType(type, variant, double_size)
        chrooked_probe("Weather#setWeatherType(#{type})") { super }
      end

      def max=(value)
        chrooked_probe("Weather#max=") { super }
      end
    end
    RPG::Weather.prepend(ChrookedProbeWeather)
  end

  if defined?(Game_Map)
    module ChrookedProbeMapRefresh
      def refresh
        chrooked_probe("Game_Map#refresh(#{@map_id})") { super }
      end
    end
    Game_Map.prepend(ChrookedProbeMapRefresh)
  end

  if defined?(Spriteset_Map)
    module ChrookedProbeSpriteset
      def initialize(*args)
        chrooked_probe("Spriteset_Map#new") { super }
      end
    end
    Spriteset_Map.prepend(ChrookedProbeSpriteset)
  end

  if defined?(RPG) && defined?(RPG::Cache)
    module ChrookedProbeCache
      def clear
        chrooked_probe("RPG::Cache.clear") { super }
      end
    end
    class << RPG::Cache
      prepend ChrookedProbeCache
    end
  end

  if private_method_defined = Object.private_method_defined?(:pbBGSPlay) || Object.method_defined?(:pbBGSPlay)
    module ChrookedProbeBGS
      def pbBGSPlay(*args)
        chrooked_probe("pbBGSPlay(#{args[0].is_a?(String) ? args[0] : args[0].class})") { super }
      end
    end
    Object.prepend(ChrookedProbeBGS)
  end

  # Whole-frame watchdog: catches spikes none of the wraps above explain.
  module ChrookedProbeGraphics
    def update
      now = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      if @chrooked_last_frame
        gap = (now - @chrooked_last_frame) * 1000.0
        if gap >= CHROOKED_PROBE_FRAME_MS
          File.open(CHROOKED_PROBE_LOG, "a") { |f| f.puts("#{Time.now.strftime('%H:%M:%S')} FRAME_GAP #{gap.round(1)}ms") }
        end
      end
      super
      @chrooked_last_frame = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    end
  end
  class << Graphics
    prepend ChrookedProbeGraphics
  end
end
