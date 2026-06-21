# chrooked:impale
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "impale": the user's piercing moves
# deal 30% more damage. Gates on the ability AND a curated piercing move-name set
# (horn / drill / needle / spear / peck-type moves), since 16.2 has no per-move
# piercingMove flag to key off — we substitute a constant-name set built from the
# spec + Pokemon knowledge.
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# purpose-built final-damage multiplier hook (base impl just returns damagemult).
# damagemult is in 0x1000 units. We scale it by 1.3 when the attacker has Impale
# AND the move is in the piercing set. Same Seam as kindle (proves generality).
#
# Gate: ability :IMPALE  +  move ∈ curated piercing constants. Each constant is
# probed with isConst?(@id, PBMoves, sym); a constant that doesn't exist in this
# install simply never matches (graceful — that move just isn't boosted).
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:impale] OBS move=<NAME> ability=<true|false> result=<BOOSTED|NORMAL>
# Cases: piercing move + Impale -> BOOSTED; non-piercing or no Impale -> NORMAL.
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

# Curated piercing move-name set — horn / drill / needle / spear / peck / sting
# moves. Real Essentials PBS constants (uppercase, no spaces). Constants absent
# from a given install just never match.
CHROOKED_IMPALE_PIERCING_MOVES = [
  :HORNATTACK,    # Horn Attack
  :HORNDRILL,     # Horn Drill
  :MEGAHORN,      # Megahorn
  :HORNLEECH,     # Horn Leech
  :DRILLPECK,     # Drill Peck
  :DRILLRUN,      # Drill Run
  :PECK,          # Peck
  :FURYATTACK,    # Fury Attack (multi-hit jabbing)
  :PINMISSILE,    # Pin Missile
  :TWINEEDLE,     # Twineedle
  :POISONSTING,   # Poison Sting
  :FELLSTINGER,   # Fell Stinger
  :PIERCINGCLAW,  # (variant naming) graceful no-op if absent
  :SKEWER         # Skewer — graceful no-op if absent
]

def chrooked_move_is_piercing_chrooked_impale
  CHROOKED_IMPALE_PIERCING_MOVES.any? { |s| (isConst?(@id, PBMoves, s) rescue false) }
end

def chrooked_install_impale
  return if $chrooked_impale_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_impale_orig")
      alias_method :pbModifyDamage_chrooked_impale_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_impale_orig(damagemult, attacker, opponent)
        is_ab = (attacker.hasWorkingAbility(:IMPALE) rescue false)
        is_pierce = chrooked_move_is_piercing_chrooked_impale
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if is_ab && is_pierce
          mult = (mult * 1.3).round
          ($chrooked_log.call("[chrooked:impale] OBS move=#{movename} ability=#{is_ab} result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:impale] OBS move=#{movename} ability=#{is_ab} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_impale_installed = true
  ($chrooked_log.call("[chrooked:impale] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_impale
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_impale_orig)
      alias_method :update_chrooked_impale_orig, :update
      def update
        chrooked_install_impale if !$chrooked_impale_installed && defined?(PokeBattle_Move)
        update_chrooked_impale_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:impale] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:impale] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
