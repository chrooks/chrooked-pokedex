# chrooked:zz_settime
# Static QoL mod (not a Ruleset behavior) — always installed by apply.
#
# Adds "Set Time" to the debug menu (needs chrooked_zz_debug). Pick an hour
# and a minute; the game clock jumps there and keeps running from it.
#
# Rejuv has no settable clock of its own. Its only moveable clock is Unreal
# Time ($game_screen.gameTimeCurrent, Scripts/Time.rb), which is gated on
# switch :Unreal_Time (1667, normally a password unlock) and the Unreal Time
# option. Set Time turns both on and clears the Forced_* time-of-day switches,
# which would otherwise pin the hour and bypass Unreal Time. The clock then
# advances at the Unreal Time Scale option (default 30x; set 1x for real speed).
# gameTimeCurrent lives on Game_Screen, so it is saved with the game.

module ChrookedSetTime
  def add(key, value, callback = nil)
    super("chrooked_settime", _INTL("Set Time")) if key == "debugTrainer"
    super
  end

  # pbDebugMenu never calls executeCommand; it resolves the pick through
  # getCommand, then falls through its elsif chain on an unknown key.
  def getCommand(index)
    key = super
    pbChrookedSetTime if key == "chrooked_settime"
    key
  end
end
CommandList.prepend(ChrookedSetTime)

def pbChrookedSetTime
  now = pbGetTimeNow
  params = ChooseNumberParams.new
  params.setRange(0, 23)
  params.setDefaultValue(now.hour)
  hour = Kernel.pbMessageChooseNumber(_INTL("Set the hour (0-23)."), params)
  params = ChooseNumberParams.new
  params.setRange(0, 59)
  params.setDefaultValue(now.min)
  min = Kernel.pbMessageChooseNumber(_INTL("Set the minute."), params)

  $game_switches[:Forced_Time_of_Day] = false
  $game_switches[:Forced_Daytime] = false
  $game_switches[:Forced_Evening] = false
  $game_switches[:Forced_Night] = false
  $game_switches[:Unreal_Time] = true
  $Settings.unrealTimeDiverge = 1
  $game_screen.gameTimeCurrent = Time.new(now.year, now.month, now.day, hour, min, 0)
  $game_map.need_refresh = true
  Kernel.pbMessage(_INTL("The time is now {1}.", format("%02d:%02d", hour, min)))
end
