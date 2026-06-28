# chrooked:petalbarrier
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "petalbarrier" (ability :PETALBARRIER).
#
# HOOK 1 (special-damage reduction) — PokeBattle_Move#pbModifyDamage(damagemult, attacker, opponent)
#   16.2 Seam (Data/Scripts.rxdata). In pbModifyDamage, `opponent` is the DEFENDER
#   being hit, so this is a DEFENDER-side ability check (opponent.hasWorkingAbility).
#   If the defender has PETALBARRIER and the move's resolved type is SPECIAL
#   (Chrooked.move_special?(self, movetype)), scale the final multiplier by 0.75. damagemult is in
#   0x1000 units; we round after scaling. The reduction is flat — it does NOT
#   require a super-effective hit. Vanilla aliased _orig runs first.
#
# HOOK 2 (Shed-Skin-style 1/3 end-of-turn status cure) — now ported.
#   Native Shed Skin lives mid-method in PokeBattle_Battle#pbEndOfRoundPhase
#   (line ~3475: `if hasWorkingAbility(:SHEDSKIN) && pbRandom(10)<3 ... pbCureStatus`),
#   not alias-injectable in place. So we POST-WRAP pbEndOfRoundPhase: after _orig,
#   each living PETALBARRIER holder with a non-volatile status rolls pbRandom(10)<3
#   and, on success, pbCureStatus — exactly Shed Skin's odds, landing at end of round.
#
# HARNESS (Route B log oracle):
#   damage:  [chrooked:petalbarrier] OBS move=<NAME> special=<BOOL> result=REDUCED|NORMAL
#   cure:    [chrooked:petalbarrier] OBS event=eor_cure ability=true rolled=<bool> cured=<bool>
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

# --- HOOK 1: Special-damage reduction via pbModifyDamage --------------------
def chrooked_install_petalbarrier_reduction
  return if $chrooked_petalbarrier_reduction_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbModifyDamage")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbModifyDamage_chrooked_petalbarrier_orig")
      alias_method :pbModifyDamage_chrooked_petalbarrier_orig, :pbModifyDamage
      def pbModifyDamage(damagemult, attacker, opponent)
        mult = pbModifyDamage_chrooked_petalbarrier_orig(damagemult, attacker, opponent)
        # opponent is the DEFENDER in pbModifyDamage.
        has_petalbarrier = (opponent.hasWorkingAbility(:PETALBARRIER) rescue false)
        movetype = (Chrooked.move_type(self, attacker, opponent) rescue nil)
        is_special = (Chrooked.move_special?(self, movetype) rescue false)
        movename = (getConstantName(PBMoves, @id) rescue @id.to_s)
        if has_petalbarrier && is_special
          mult = (mult * 0.75).round
          ($chrooked_log.call("[chrooked:petalbarrier] OBS move=#{movename} ability=true special=true result=REDUCED") rescue nil)
        else
          ($chrooked_log.call("[chrooked:petalbarrier] OBS move=#{movename} ability=#{has_petalbarrier} special=#{is_special} result=NORMAL") rescue nil)
        end
        mult
      end
    end
  end
  $chrooked_petalbarrier_reduction_installed = true
  ($chrooked_log.call("[chrooked:petalbarrier] reduction installed on PokeBattle_Move") rescue nil)
end

# --- HOOK 2: 1/3 end-of-round status cure via pbEndOfRoundPhase post-wrap -----
def chrooked_install_petalbarrier_cure
  return if $chrooked_petalbarrier_cure_installed
  return unless defined?(PokeBattle_Battle)
  return unless PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbEndOfRoundPhase")
  PokeBattle_Battle.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEndOfRoundPhase_chrooked_petalbarrier_orig")
      alias_method :pbEndOfRoundPhase_chrooked_petalbarrier_orig, :pbEndOfRoundPhase
      def pbEndOfRoundPhase(*args)
        ret = pbEndOfRoundPhase_chrooked_petalbarrier_orig(*args)
        begin
          @battlers.each do |b|
            next unless b && !(b.isFainted? rescue true)
            next unless (b.hasWorkingAbility(:PETALBARRIER) rescue false)
            next unless (b.status rescue 0) > 0
            rolled = (pbRandom(10) < 3)
            if rolled
              b.pbCureStatus(false)
              @scene.pbRefresh rescue nil
            end
            ($chrooked_log.call("[chrooked:petalbarrier] OBS event=eor_cure ability=true rolled=#{rolled} cured=#{rolled}") rescue nil)
          end
        rescue Exception
        end
        ret
      end
    end
  end
  $chrooked_petalbarrier_cure_installed = true
  ($chrooked_log.call("[chrooked:petalbarrier] cure installed on PokeBattle_Battle") rescue nil)
end

def chrooked_install_petalbarrier_all
  chrooked_install_petalbarrier_reduction
  chrooked_install_petalbarrier_cure
end

def chrooked_petalbarrier_all_installed?
  $chrooked_petalbarrier_reduction_installed && $chrooked_petalbarrier_cure_installed
end

chrooked_install_petalbarrier_all

unless chrooked_petalbarrier_all_installed?
  if defined?(Graphics)
    class << Graphics
      unless method_defined?(:update_chrooked_petalbarrier_orig)
        alias_method :update_chrooked_petalbarrier_orig, :update
        def update
          chrooked_install_petalbarrier_all unless chrooked_petalbarrier_all_installed?
          update_chrooked_petalbarrier_orig
        end
      end
    end
    ($chrooked_log.call("[chrooked:petalbarrier] deferred install armed on Graphics.update") rescue nil)
  else
    ($chrooked_log.call("[chrooked:petalbarrier] ERROR: neither PokeBattle classes nor Graphics defined at load") rescue nil)
  end
end
