# chrooked:mountaineer
# ---------------------------------------------------------------------------
# Custom mechanic for the Ruleset behavior "mountaineer": a Pokemon with this
# ability is IMMUNE to Rock-type moves — the move is blocked and deals no
# damage. PURE immunity (Levitate/Soundproof-style): NO stat bonus, NO heal,
# just absorb the move. Only Rock is blocked; every other type lands normally.
#
# Seam: PokeBattle_Move#pbTypeImmunityByAbility(type, attacker, opponent)
# (verified 16.2 Data/Scripts.rxdata, line 324). The method returns TRUE to make
# the incoming move INEFFECTIVE — that is the absorb. 'opponent' is the holder
# being hit, so absorb-with-bonus abilities (SAPSIPPER/MOTORDRIVE/VOLTABSORB)
# apply their bonus to 'opponent' before returning true. Mountaineer is the
# LEVITATE-style variant: we just return true, no bonus.
#
# Override strategy (alias_method chaining):
#   1. Call the original _orig first. If it already returned true (some other
#      ability/type already absorbs), return true and do nothing else.
#   2. Otherwise, if 'opponent' has Mountaineer AND the incoming 'type' is Rock,
#      return true (pure block, no bonus).
#   3. Otherwise return the _orig result (false / whatever it was).
# Type match uses isConst?(type, PBTypes, :ROCK) (verified 16.2 helper).
#
# SECOND HOOK (Stealth Rock entry-hazard guard) — *** NOT PORTED ***
# The Ruleset also wants Stealth Rock entry damage waived on switch-in (alongside
# Magic Guard). That is a SEPARATE Seam in the entry-hazard routine, and no
# verified 16.2 method name/signature for that routine was supplied. Porting it
# would mean guessing the hazard method — which the harness forbids ("do not
# guess; cite the C/Seam"). So this file ports ONLY the Rock-move immunity. The
# Stealth Rock exemption is left UNPORTED and noted here for a follow-up once the
# hazard Seam is verified in Data/Scripts.rxdata. (If/when added, alias that
# method too — separate _orig name + separate installed-flag, both deferred.)
#
# HARNESS (Route B log oracle): every pbTypeImmunityByAbility call logs one line:
#     [chrooked:mountaineer] OBS type=<TYPE> ability=<true|false> result=<ABSORBED|PASS>
# Cases distinguished by type: Rock move + ability -> ABSORBED; else PASS.
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

def chrooked_install_mountaineer
  return if $chrooked_mountaineer_installed
  return unless defined?(PokeBattle_Move)
  return unless PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbTypeImmunityByAbility")
  PokeBattle_Move.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbTypeImmunityByAbility_chrooked_mountaineer_orig")
      alias_method :pbTypeImmunityByAbility_chrooked_mountaineer_orig, :pbTypeImmunityByAbility
      def pbTypeImmunityByAbility(type, attacker, opponent)
        # 1. Original first — respect any vanilla/other-ability absorb.
        orig = pbTypeImmunityByAbility_chrooked_mountaineer_orig(type, attacker, opponent)
        return true if orig
        # 2. Our ability + Rock type -> pure block (no bonus).
        is_ab = (opponent.hasWorkingAbility(:MOUNTAINEER) rescue false)
        is_rock = (isConst?(type, PBTypes, :ROCK) rescue false)
        typename = (getConstantName(PBTypes, type) rescue type.to_s)
        if is_ab && is_rock
          ($chrooked_log.call("[chrooked:mountaineer] OBS type=#{typename} ability=true result=ABSORBED") rescue nil)
          return true
        end
        ($chrooked_log.call("[chrooked:mountaineer] OBS type=#{typename} ability=#{is_ab} result=PASS") rescue nil)
        # 3. Fall through to the original result (false / whatever it was).
        orig
      end
    end
  end
  $chrooked_mountaineer_installed = true
  ($chrooked_log.call("[chrooked:mountaineer] installed on PokeBattle_Move") rescue nil)
end

if defined?(PokeBattle_Move) && PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?("pbTypeImmunityByAbility")
  chrooked_install_mountaineer
elsif defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_mountaineer_orig)
      alias_method :update_chrooked_mountaineer_orig, :update
      def update
        chrooked_install_mountaineer if !$chrooked_mountaineer_installed && defined?(PokeBattle_Move)
        update_chrooked_mountaineer_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:mountaineer] deferred install armed on Graphics.update") rescue nil)
else
  ($chrooked_log.call("[chrooked:mountaineer] ERROR: neither PokeBattle_Move nor Graphics defined at load") rescue nil)
end
