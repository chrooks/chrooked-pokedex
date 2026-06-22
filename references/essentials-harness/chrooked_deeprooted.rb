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
# PokeBattle_Battle#pbEndOfRoundPhase (lines 3537/3548/3567), mid-method, alongside
# non-drain end-of-round heals (Leftovers/Rain Dish). They are not alias-injectable
# per-site, so we wrap the whole pbEndOfRoundPhase to raise an end-round flag, and
# in pbRecoverHP scale a DEEPROOTED heal during that window ONLY when the recoverer
# currently has an active drain source: effects[AquaRing], effects[Ingrain], or it
# is some battler's Leech Seed recipient. That gate excludes Leftovers/Rain Dish.
#
# ponytail: ceiling — if a DEEPROOTED mon holds Leftovers AND simultaneously has
# Aqua Ring / Ingrain / is seeded, its Leftovers tick is also scaled ×1.3 (the
# effect-gate can't tell two same-window heals apart). Niche; the drain portion is
# correct. Upgrade path: only a per-site edit to pbEndOfRoundPhase would split them.
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
          if (self.hasWorkingAbility(:DEEPROOTED) rescue false)
            is_move_drain = (@chrooked_draining rescue false)
            in_endround = (@battle.instance_variable_get(:@chrooked_dr_endround) rescue false)
            passive_drain = false
            if in_endround
              passive_drain = (self.effects[PBEffects::AquaRing] rescue false) ||
                              (self.effects[PBEffects::Ingrain] rescue false)
              if !passive_drain
                others = (@battle.battlers rescue [])
                others.each do |b|
                  next unless b
                  if (b.effects[PBEffects::LeechSeed] rescue -1) == self.index
                    passive_drain = true
                    break
                  end
                end
              end
            end
            if is_move_drain || passive_drain
              scaled = (amt * 1.3).floor
              scaled = 1 if scaled < 1
              src = is_move_drain ? "move" : "passive"
              ($chrooked_log.call("[chrooked:deeprooted] OBS event=drain src=#{src} ability=true before=#{amt} after=#{scaled}") rescue nil)
              amt = scaled
            end
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
      def pbEndOfRoundPhase(*args)
        @chrooked_dr_endround = true
        begin
          ret = pbEndOfRoundPhase_chrooked_deeprooted_orig(*args)
        ensure
          @chrooked_dr_endround = false
        end
        ret
      end
    end
  end
  $chrooked_deeprooted_endround_installed = true
  ($chrooked_log.call("[chrooked:deeprooted] endround flag installed on PokeBattle_Battle") rescue nil)
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
