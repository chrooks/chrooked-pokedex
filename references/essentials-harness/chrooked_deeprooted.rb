# chrooked:deeprooted
# ---------------------------------------------------------------------------
# Deep-Rooted (ability :DEEPROOTED): HP recovered from draining effects is ×1.3
# (floored, min 1), stacking multiplicatively with Big Root.
#
# Seam (verified in Data/Scripts.rxdata): every drain heal in this fork ends in
#   <recoverer>.pbRecoverHP(hpgain, true)   # hpgain already Big-Root-scaled
# The damage-drain MOVE family is three subclasses with identical shape — each
# pbEffect calls super then heals the attacker:
#   PokeBattle_Move_0DD  (Absorb / Mega Drain / Giga Drain / Drain Punch / Leech Life)
#   PokeBattle_Move_0DE  (Dream Eater)
#   PokeBattle_Move_14F  (Draining Kiss / Oblivion Wing, 3/4)
#
# We bracket each subclass's pbEffect with a transient @chrooked_draining flag on
# the attacker (a drain move's pbEffect heals ONLY via drain, so the flag is
# precise), and wrap PokeBattle_Battler#pbRecoverHP (line 762) to multiply the
# amount by 1.3 when the recoverer has DEEPROOTED AND the flag is set. Applied
# after the site's Big Root ×1.3, so the two stack to ×1.69 as specced.
#
# The PASSIVE drains — Leech Seed receiver, Ingrain, Aqua Ring — live inside
# PokeBattle_Battle#pbEndOfRoundPhase (lines 3537/3548/3567), mid-method. Rather
# than intercept their pbRecoverHP (which can't be told apart from a co-occurring
# Leftovers / Black Sludge / Grassy Terrain tick — same amount, same window), we
# post-wrap pbEndOfRoundPhase and add the +0.3 as a SEPARATE top-up heal computed
# from the holder's active drain sources (Aqua Ring/Ingrain totalhp/16, Leech Seed
# seeder.totalhp/8, each ×1.3 if Big Root). Heal-Block-gated; Leech Seed skipped if
# the seeder has Liquid Ooze (no heal happened). Because the bonus is computed
# outside, no other end-of-round heal is ever scaled — the old Leftovers ceiling
# is gone. Approximation: the Leech Seed base uses seeder.totalhp/8 (the engine's
# nominal amount), which can slightly over-credit when the seeder is near death;
# pbRecoverHP still caps at the holder's max HP.
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

# --- Recover scaler: ×1.3 when a flagged DEEPROOTED battler heals ------------
def chrooked_install_deeprooted_recover
  return if $chrooked_deeprooted_recover_installed
  return unless defined?(PokeBattle_Battler)
  return unless PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbRecoverHP")
  PokeBattle_Battler.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbRecoverHP_chrooked_deeprooted_orig")
      alias_method :pbRecoverHP_chrooked_deeprooted_orig, :pbRecoverHP
      def pbRecoverHP(amt, anim = false)
        begin
          # Only the in-move drain path scales here, gated on the transient flag
          # set around the drain-move subclasses' pbEffect (precise — a drain move
          # heals ONLY via drain). Passive end-of-round drains are handled by the
          # replay-bonus below, NOT here, so a co-occurring Leftovers/Grassy-Terrain
          # tick is never scaled.
          if (@chrooked_draining rescue false) && (self.hasWorkingAbility(:DEEPROOTED) rescue false)
            scaled = (amt * 1.3).floor
            scaled = 1 if scaled < 1
            ($chrooked_log.call("[chrooked:deeprooted] OBS event=drain src=move ability=true before=#{amt} after=#{scaled}") rescue nil)
            amt = scaled
          end
        rescue Exception
        end
        pbRecoverHP_chrooked_deeprooted_orig(amt, anim)
      end
    end
  end
  $chrooked_deeprooted_recover_installed = true
  ($chrooked_log.call("[chrooked:deeprooted] recover scaler installed on PokeBattle_Battler") rescue nil)
end

# --- Bracket each drain-move subclass's pbEffect with the drain flag ---------
CHROOKED_DEEPROOTED_DRAIN_CLASSES = %w[PokeBattle_Move_0DD PokeBattle_Move_0DE PokeBattle_Move_14F]

def chrooked_install_deeprooted_drainmoves
  return if $chrooked_deeprooted_drainmoves_installed
  installed_all = true
  CHROOKED_DEEPROOTED_DRAIN_CLASSES.each do |cname|
    klass = (Object.const_get(cname) rescue nil)
    if klass.nil?
      installed_all = false
      next
    end
    klass.class_eval do
      unless instance_methods(false).map { |m| m.to_s }.include?("pbEffect_chrooked_deeprooted_orig")
        alias_method :pbEffect_chrooked_deeprooted_orig, :pbEffect
        def pbEffect(attacker, opponent, hitnum = 0, alltargets = nil, showanimation = true)
          attacker.instance_variable_set(:@chrooked_draining, true) rescue nil
          begin
            ret = pbEffect_chrooked_deeprooted_orig(attacker, opponent, hitnum, alltargets, showanimation)
          ensure
            attacker.instance_variable_set(:@chrooked_draining, false) rescue nil
          end
          ret
        end
      end
    end
    ($chrooked_log.call("[chrooked:deeprooted] drain flag installed on #{cname}") rescue nil)
  end
  $chrooked_deeprooted_drainmoves_installed = installed_all
end

# --- End-of-round window flag: marks the passive-drain heal window -----------
def chrooked_install_deeprooted_endround
  return if $chrooked_deeprooted_endround_installed
  return unless defined?(PokeBattle_Battle)
  return unless PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbEndOfRoundPhase")
  PokeBattle_Battle.class_eval do
    unless instance_methods(false).map { |m| m.to_s }.include?("pbEndOfRoundPhase_chrooked_deeprooted_orig")
      alias_method :pbEndOfRoundPhase_chrooked_deeprooted_orig, :pbEndOfRoundPhase

      # The deeprooted bonus for the +0.3 on a bigroot-adjusted base amount.
      def chrooked_deeprooted_bonus(base, bigroot)
        g = base
        g = (g * 1.3).floor if bigroot
        ((g * 1.3).floor - g)   # what deeprooted adds on top of what the engine gave
      end

      # PASSIVE-drain ×1.3 is applied here as a separate top-up heal AFTER the
      # round, computed from the holder's drain sources — NOT by intercepting
      # pbRecoverHP (which can't tell a drain tick from a co-occurring Leftovers /
      # Grassy Terrain / Black Sludge tick: same amount, same window). Computing it
      # outside means those other heals are never touched.
      def pbEndOfRoundPhase(*args)
        ret = pbEndOfRoundPhase_chrooked_deeprooted_orig(*args)
        begin
          @battlers.each do |b|
            next if b.nil? || (b.isFainted? rescue true)
            next unless (b.hasWorkingAbility(:DEEPROOTED) rescue false)
            next unless (b.effects[PBEffects::HealBlock] rescue 0) == 0
            bigroot = (b.hasWorkingItem(:BIGROOT) rescue false)
            bonus = 0
            bonus += chrooked_deeprooted_bonus((b.totalhp / 16).floor, bigroot) if (b.effects[PBEffects::AquaRing] rescue false)
            bonus += chrooked_deeprooted_bonus((b.totalhp / 16).floor, bigroot) if (b.effects[PBEffects::Ingrain] rescue false)
            @battlers.each do |seeder|
              next if seeder.nil?
              next unless (seeder.effects[PBEffects::LeechSeed] rescue -1) == b.index
              next if (seeder.isFainted? rescue true)
              next if (seeder.hasWorkingAbility(:LIQUIDOOZE) rescue false)  # heal flipped to damage
              bonus += chrooked_deeprooted_bonus((seeder.totalhp / 8).floor, bigroot)
            end
            if bonus > 0
              b.pbRecoverHP(bonus, true)
              ($chrooked_log.call("[chrooked:deeprooted] OBS event=drain src=passive ability=true bonus=#{bonus}") rescue nil)
            end
          end
        rescue Exception
        end
        ret
      end
    end
  end
  $chrooked_deeprooted_endround_installed = true
  ($chrooked_log.call("[chrooked:deeprooted] passive replay-bonus installed on PokeBattle_Battle") rescue nil)
end

chrooked_install_deeprooted_recover if defined?(PokeBattle_Battler) &&
  PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?("pbRecoverHP")
chrooked_install_deeprooted_drainmoves
chrooked_install_deeprooted_endround if defined?(PokeBattle_Battle) &&
  PokeBattle_Battle.instance_methods.map { |m| m.to_s }.include?("pbEndOfRoundPhase")

if (!$chrooked_deeprooted_recover_installed || !$chrooked_deeprooted_drainmoves_installed || !$chrooked_deeprooted_endround_installed) && defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_deeprooted_orig)
      alias_method :update_chrooked_deeprooted_orig, :update
      def update
        chrooked_install_deeprooted_recover if !$chrooked_deeprooted_recover_installed && defined?(PokeBattle_Battler)
        chrooked_install_deeprooted_drainmoves if !$chrooked_deeprooted_drainmoves_installed
        chrooked_install_deeprooted_endround if !$chrooked_deeprooted_endround_installed && defined?(PokeBattle_Battle)
        update_chrooked_deeprooted_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:deeprooted] deferred install armed on Graphics.update") rescue nil)
elsif !defined?(Graphics) && (!$chrooked_deeprooted_recover_installed || !$chrooked_deeprooted_drainmoves_installed || !$chrooked_deeprooted_endround_installed)
  ($chrooked_log.call("[chrooked:deeprooted] ERROR: classes/Graphics missing at load") rescue nil)
end
