# chrooked:highnoon
# ---------------------------------------------------------------------------
# High Noon: the solar counterpart to Full Moon. This Pokemon's FIRE- and
# PSYCHIC-type moves get pseudo-STAB (a flat 1.5x), regardless of the user's
# own types. The Morning Sun 75%-heal branch is now ported too (see below).
#
# Seam: PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent) — 16.2's
# purpose-built final-damage multiplier hook (base impl just returns damagemult).
# damagemult is in 0x1000 units.
#
# DOUBLE-COUNT GUARD: vanilla STAB is applied INLINE in pbCalcDamage (x1.5 when
# attacker.pbHasType?(type)). To GRANT pseudo-STAB without double-counting, we
# multiply by 1.5 ONLY when the move type is FIRE or PSYCHIC AND the attacker
# does NOT already have that type (if they already have it, vanilla STAB already
# gave the 1.5). So a Fire/Normal High Noon user firing Flamethrower keeps the
# vanilla 1.5 and we add nothing; a pure-Normal High Noon user gets our 1.5.
#
# HARNESS (Route B log oracle): every pbModifyDamage call logs one line:
#     [chrooked:highnoon] OBS move=<NAME> highnoon=<true|false> gate=<true|false> result=<BOOSTED|NORMAL>
# Cases distinguished by move: Fire/Psychic move + highnoon + no own-type-match
# -> BOOSTED; otherwise -> NORMAL.
#
# SECOND EFFECT — Morning Sun heals 3/4 max HP (now ported). The recover handler
# is PokeBattle_Move_0D8#pbEffect (Moonlight/Morning Sun/Synthesis share this
# class; verified in Data/Scripts.rxdata). We wrap it: when the user has HIGHNOON
# and the move is Morning Sun and it is below full HP, heal (totalhp*3/4).floor and
# skip the original (weather branches never run). Full HP falls through to _orig.
# Mirror of chrooked_fullmoon's Moonlight heal.
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

def chrooked_install_highnoon
  return if $chrooked_highnoon_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_highnoon_orig")
      alias_method :pbModifyDamage_chrooked_highnoon_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_highnoon_orig(damagemult, attacker, opponent)
        is_highnoon = (attacker.hasWorkingAbility(:HIGHNOON) rescue false)
        movetype = (pbType(@type, attacker, opponent) rescue -1)
        is_fire = (isConst?(movetype, PBTypes, :FIRE) rescue false)
        is_psychic = (isConst?(movetype, PBTypes, :PSYCHIC) rescue false)
        # Vanilla STAB already gives 1.5 if the user already has the move's type;
        # only grant pseudo-STAB when they do NOT, to avoid double-counting.
        already_stab = (attacker.pbHasType?(movetype) rescue false)
        gate = is_highnoon && (is_fire || is_psychic) && !already_stab
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if gate
          mult = (mult * 1.5).round
          ($chrooked_log.call("[chrooked:highnoon] OBS move=#{movename} highnoon=#{is_highnoon} gate=true result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:highnoon] OBS move=#{movename} highnoon=#{is_highnoon} gate=false result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_highnoon_installed = true
  ($chrooked_log.call("[chrooked:highnoon] installed on PokeBattle_Move") rescue nil)
end

# --- Morning Sun heal: 3/4 max HP for a HIGHNOON user (Move_0D8) --------------
def chrooked_install_highnoon_heal
  return if $chrooked_highnoon_heal_installed
  klass = (Object.const_get("PokeBattle_Move_0D8") rescue nil)
  return if klass.nil?
  # chrooked: IF2's Infinite Fusion fork renames the per-move effect seam, so 0D8 has
  # no pbEffect to alias. Guard or alias_method raises NameError and crashes boot.
  return unless klass.instance_methods.map { |m| m.to_s }.include?("pbEffect")
  klass.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEffect_chrooked_highnoon_orig")
      alias_method :pbEffect_chrooked_highnoon_orig, :pbEffect
      def pbEffect(attacker, opponent, hitnum = 0, alltargets = nil, showanimation = true)
        if (attacker.hasWorkingAbility(:HIGHNOON) rescue false) &&
           (isConst?(@id, PBMoves, :MORNINGSUN) rescue false) &&
           attacker.hp != attacker.totalhp
          hpgain = (attacker.totalhp * 3 / 4).floor
          pbShowAnimation(@id, attacker, nil, hitnum, alltargets, showanimation)
          attacker.pbRecoverHP(hpgain, true)
          @battle.pbDisplay(_INTL("{1} recuperó salud.", attacker.pbThis))
          ($chrooked_log.call("[chrooked:highnoon] OBS move=MORNINGSUN highnoon=true heal=three_quarters") rescue nil)
          return 0
        end
        pbEffect_chrooked_highnoon_orig(attacker, opponent, hitnum, alltargets, showanimation)
      end
    end
  end
  $chrooked_highnoon_heal_installed = true
  ($chrooked_log.call("[chrooked:highnoon] heal hook installed on PokeBattle_Move_0D8") rescue nil)
end

def chrooked_highnoon_done?
  $chrooked_highnoon_installed && $chrooked_highnoon_heal_installed
end

chrooked_install_highnoon if defined?(PokeBattle_Move) &&
  PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
chrooked_install_highnoon_heal

unless chrooked_highnoon_done?
  if defined?(Graphics)
    class << Graphics
      unless method_defined?(:update_chrooked_highnoon_orig)
        alias_method :update_chrooked_highnoon_orig, :update
        def update
          chrooked_install_highnoon if !$chrooked_highnoon_installed && defined?(PokeBattle_Move)
          chrooked_install_highnoon_heal unless $chrooked_highnoon_heal_installed
          update_chrooked_highnoon_orig
        end
      end
    end
    ($chrooked_log.call("[chrooked:highnoon] deferred install armed on Graphics.update") rescue nil)
  else
    ($chrooked_log.call("[chrooked:highnoon] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
  end
end
