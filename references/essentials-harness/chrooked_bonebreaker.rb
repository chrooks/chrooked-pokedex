# chrooked:bonebreaker
# ---------------------------------------------------------------------------
# Bone Breaker: the user's bone-flagged moves (1) ignore type immunities and
# (2) deal 20% more damage. Both effects fire only when the attacker has the
# BONEBREAKER ability AND the move is one of the bone moves.
#
# Bone moves in this fork: Bone Club, Bonemerang, Bone Rush, Bone Torch,
# Shadow Bone — matched via isConst?(@id, PBMoves, sym).
#
# Two Seams, both on PokeBattle_Move (each aliased separately, own installed
# flag, both deferred on Graphics.update):
#
# (1) IMMUNITY BYPASS — PokeBattle_Move#pbTypeModifier(type, attacker, opponent)
#     returns effectiveness on a base-8 scale (8 = 1x neutral, 0 = immune,
#     16 = 2x, 4 = 0.5x). We call _orig first; if the gate matches and _orig
#     returned 0 (immune — Ground-vs-ungrounded/Levitate/type-absorb all fold
#     into a 0 here), we return 8 (neutral) so the move connects. We do NOT
#     touch non-zero results, so resisted/super-effective matchups keep their
#     vanilla multiplier.
#
# (2) DAMAGE MULTIPLIER — PokeBattle_Move#pbModifyDamage(damagemult, attacker,
#     opponent) returns the multiplier in 0x1000 units. We call _orig first,
#     then scale by 1.2 when the gate matches (same bone set + ability).
#
# HARNESS (Route B log oracle): each gate firing logs one line:
#     [chrooked:bonebreaker] OBS hook=typemod move=<NAME> bonebreaker=<bool> orig=<n> result=<NEUTRALIZED|UNCHANGED>
#     [chrooked:bonebreaker] OBS hook=modifydamage move=<NAME> bonebreaker=<bool> result=<BOOSTED|NORMAL>
#
# RUBY 1.8: alias_method chaining (NO prepend/TracePoint); deferred install on
# Graphics.update; guarded $chrooked_log; unique _chrooked_bonebreaker names.
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

# Shared gate: true when the attacker has BONEBREAKER and @id is a bone move.
unless defined?($chrooked_bonebreaker_gate) && $chrooked_bonebreaker_gate
  $chrooked_bonebreaker_gate = lambda do |move, attacker|
    begin
      next false unless attacker
      next false unless (attacker.hasWorkingAbility(:BONEBREAKER) rescue false)
      bone = [:BONECLUB, :BONEMERANG, :BONERUSH, :BONETORCH, :SHADOWBONE]
      bone.any? { |s| (isConst?(move.id, PBMoves, s) rescue false) }
    rescue Exception
      false
    end
  end
end

# --- Hook 1: immunity bypass via pbTypeModifier ----------------------------
def chrooked_install_bonebreaker_typemod
  return if $chrooked_bonebreaker_typemod_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbTypeModifier")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbTypeModifier_chrooked_bonebreaker_orig")
      alias_method :pbTypeModifier_chrooked_bonebreaker_orig, :pbTypeModifier
      def pbTypeModifier(type, attacker, opponent)
        result = pbTypeModifier_chrooked_bonebreaker_orig(type, attacker, opponent)
        gate = ($chrooked_bonebreaker_gate.call(self, attacker) rescue false)
        if gate
          movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
          if result == 0
            ($chrooked_log.call("[chrooked:bonebreaker] OBS hook=typemod move=#{movename} bonebreaker=true orig=#{result} result=NEUTRALIZED") rescue nil)
            result = 8
          else
            ($chrooked_log.call("[chrooked:bonebreaker] OBS hook=typemod move=#{movename} bonebreaker=true orig=#{result} result=UNCHANGED") rescue nil)
          end
        end
        result
      end
    end
  end
  $chrooked_bonebreaker_typemod_installed = true
  ($chrooked_log.call("[chrooked:bonebreaker] installed pbTypeModifier on PokeBattle_Move") rescue nil)
end

# --- Hook 2: 1.2x damage via pbModifyDamage --------------------------------
def chrooked_install_bonebreaker_modifydamage
  return if $chrooked_bonebreaker_modifydamage_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_bonebreaker_orig")
      alias_method :pbModifyDamage_chrooked_bonebreaker_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_bonebreaker_orig(damagemult, attacker, opponent)
        gate = ($chrooked_bonebreaker_gate.call(self, attacker) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if gate
          mult = (mult * 1.2).round
          ($chrooked_log.call("[chrooked:bonebreaker] OBS hook=modifydamage move=#{movename} bonebreaker=true result=BOOSTED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:bonebreaker] OBS hook=modifydamage move=#{movename} bonebreaker=false result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_bonebreaker_modifydamage_installed = true
  ($chrooked_log.call("[chrooked:bonebreaker] installed pbModifyDamage on PokeBattle_Move") rescue nil)
end

# --- Install both: immediate if class is ready, else defer on Graphics.update
def chrooked_install_bonebreaker_all
  chrooked_install_bonebreaker_typemod
  chrooked_install_bonebreaker_modifydamage
end

if defined?(PokeBattle_Move) &&
   PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbTypeModifier") &&
   PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  chrooked_install_bonebreaker_all
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_bonebreaker_orig)
      alias_method :update_chrooked_bonebreaker_orig, :update
      def update
        if (!$chrooked_bonebreaker_typemod_installed || !$chrooked_bonebreaker_modifydamage_installed) && defined?(PokeBattle_Move)
          chrooked_install_bonebreaker_all
        end
        update_chrooked_bonebreaker_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:bonebreaker] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:bonebreaker] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
