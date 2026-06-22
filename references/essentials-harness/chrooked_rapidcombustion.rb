# chrooked:rapidcombustion
# ---------------------------------------------------------------------------
# Rapid Combustion (ability :RAPIDCOMBUSTION): Fire moves get +1 priority while
# the user is at full HP. Exact Gale Wings clone, Fire instead of Flying.
#
# Seam (verified in Data/Scripts.rxdata): turn order is NOT computed from
# PokeBattle_Move#pbPriority(attacker) (that method exists at line 180 but is
# unused for ordering). It is PokeBattle_Battle#pbPriority (line 1058), which
# reads each move's base priority as @choices[i][2].priority and adds the ability
# bonuses INLINE (Prankster/Gale Wings/Triage, lines 1104-1112):
#     pri+=1 if @battlers[i].hasWorkingAbility(:GALEWINGS) &&
#               isConst?(@choices[i][2].type,PBTypes,:FLYING)
# That inline block can't be alias-injected mid-method, so we wrap the whole
# pbPriority: before the orig sorts, bump @priority on each qualifying move
# (priority is attr_reader, so set the ivar directly), then restore it after the
# sort so the move's base priority never permanently changes. The orig caches the
# ordered list under @usepriority; when that flag is already set the orig returns
# the cache, so we must not double-bump — short-circuit on it.
#
# Matches Gale Wings on move.type (the move's own base type), not the resolved
# -ize/Normalize type — same as the vanilla line we are cloning.
#
# RUBY 1.8: alias_method chaining; deferred install on Graphics.update.
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

def chrooked_install_rapidcombustion
  return if $chrooked_rapidcombustion_installed
  return unless defined?(PokeBattle_Battle)
  return unless PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbPriority")
  PokeBattle_Battle.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbPriority_chrooked_rapidcombustion_orig")
      alias_method :pbPriority_chrooked_rapidcombustion_orig, :pbPriority
      def pbPriority(ignorequickclaw = false, log = false)
        return pbPriority_chrooked_rapidcombustion_orig(ignorequickclaw, log) if @usepriority
        bumped = []
        begin
          for i in 0...@choices.length
            next unless @choices[i] && @choices[i][0] == 1 && @choices[i][2]
            move = @choices[i][2]
            batt = @battlers[i]
            next unless batt
            next unless (batt.hasWorkingAbility(:RAPIDCOMBUSTION) rescue false)
            fullhp = (batt.hp == batt.totalhp)
            is_fire = (isConst?(move.type, PBTypes, :FIRE) rescue false)
            movename = (getConstantName(PBMoves, move.id) rescue "?")
            if fullhp && is_fire
              base = move.priority
              move.instance_variable_set(:@priority, base + 1)
              bumped.push([move, base])
              ($chrooked_log.call("[chrooked:rapidcombustion] OBS move=#{movename} fullhp=#{fullhp} type=FIRE result=BOOSTED") rescue nil)
            else
              ($chrooked_log.call("[chrooked:rapidcombustion] OBS move=#{movename} fullhp=#{fullhp} type=#{is_fire ? 'FIRE' : 'other'} result=NORMAL") rescue nil)
            end
          end
        rescue Exception
        end
        ret = pbPriority_chrooked_rapidcombustion_orig(ignorequickclaw, log)
        bumped.each { |m, base| (m.instance_variable_set(:@priority, base) rescue nil) }
        ret
      end
    end
  end
  $chrooked_rapidcombustion_installed = true
  ($chrooked_log.call("[chrooked:rapidcombustion] installed on PokeBattle_Battle") rescue nil)
end

if defined?(PokeBattle_Battle) && PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbPriority")
  chrooked_install_rapidcombustion
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_rapidcombustion_orig)
      alias_method :update_chrooked_rapidcombustion_orig, :update
      def update
        chrooked_install_rapidcombustion if !$chrooked_rapidcombustion_installed && defined?(PokeBattle_Battle)
        update_chrooked_rapidcombustion_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:rapidcombustion] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:rapidcombustion] ERROR: PokeBattle_Battle/Graphics missing at load") rescue nil)
end
