# chrooked:martialartist
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "martialartist": the user's punching
# moves AND kicking moves deal 30% more damage (1.3x). A move that is both still
# gets a single 1.3x.
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# final-damage multiplier hook (base impl just returns damagemult). damagemult is
# in 0x1000 units. We scale it by 1.3 when the attacker has Martial Artist AND the
# gate matches.
#
# GATE: isPunchingMove?  OR  a curated KICK move-name set.
#   16.2 has the engine-standard punch flag (isPunchingMove?), but no kick flag.
#   We synthesize "kicking move" with a curated set of real Essentials PBS move
#   constants checked via isConst?(@id, PBMoves, SYM). A missing constant just
#   means that move isn't boosted (graceful).
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:martialartist] OBS move=<NAME> ability=<true|false> result=<BOOSTED|NORMAL>
# Cases distinguished by move: punch/kick move + ability -> BOOSTED; other -> NORMAL.
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

# Curated set of kicking-move PBS constants (no engine kick flag exists in 16.2).
# Real, well-known Essentials move constants — a missing one is simply not boosted.
CHROOKED_MARTIALARTIST_KICKS = [
  :DOUBLEKICK, :HIJUMPKICK, :JUMPKICK, :LOWKICK, :MEGAKICK,
  :ROLLINGKICK, :TRIPLEKICK, :BLAZEKICK, :LOWSWEEP, :TROPKICK,
  :HIGHHORSEPOWER, :STOMP, :TRIPLEAXEL
]

def chrooked_install_martialartist
  return if $chrooked_martialartist_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_martialartist_orig")
      alias_method :pbModifyDamage_chrooked_martialartist_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_martialartist_orig(damagemult, attacker, opponent)
        is_ab = (attacker.hasWorkingAbility(:MARTIALARTIST) rescue false)
        is_punch = (isPunchingMove? rescue false)
        is_kick = CHROOKED_MARTIALARTIST_KICKS.any? { |s| (isConst?(@id, PBMoves, s) rescue false) }
        gate = is_punch || is_kick
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_ab && gate
          mult = (mult * 1.3).round
          ($chrooked_log.call("[chrooked:martialartist] OBS move=#{movename} ability=#{is_ab} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:martialartist] OBS move=#{movename} ability=#{is_ab} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_martialartist_installed = true
  ($chrooked_log.call("[chrooked:martialartist] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_martialartist
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_martialartist_orig)
      alias_method :update_chrooked_martialartist_orig, :update
      def update
        chrooked_install_martialartist if !$chrooked_martialartist_installed && defined?(PokeBattle_Move)
        update_chrooked_martialartist_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:martialartist] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:martialartist] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
