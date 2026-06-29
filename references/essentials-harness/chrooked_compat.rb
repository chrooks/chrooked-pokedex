# [CHROOKED_COMPAT] — engine-compatibility layer for the chrooked_* plugins
# ---------------------------------------------------------------------------
# Loaded by load_order_shim.rb BEFORE any chrooked_*.rb plugin. The plugins were
# written against stock Pokemon Essentials 16.2, but some targets (notably
# Infinite Fusion 2 = "IF2") are a FORK of 16.x: same class/constant names
# (PokeBattle_Move, PBTypes, isConst?) but renamed/restructured battle internals.
#
# This module lets a plugin ask for the right seam on whatever engine it is on,
# instead of hardcoding the 16.2 name. Detection is by CAPABILITY PROBE (does the
# method exist?), never a version string — IF2 exposes no usable version constant.
#
# RUBY 1.8 (this engine bundles 1.8): no 1.9 hash syntax, no prepend. Keep 1.8-safe.
# Load-time safety: the engine classes (PokeBattle_*, GameData) do NOT exist yet
# when this file loads, so everything here is lazy — nothing touches them until a
# plugin calls a helper at battle time.
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

module Chrooked
  @engine = nil
  @pbtypes_ready = false
  @pbmoves_ready = false

  # :ess162 (stock 16.2, has pbType) | :if_fork (IF2, has pbCalcType not pbType) |
  # :unknown. Memoized on first call. Safe to call before classes exist (returns
  # :unknown until PokeBattle_Move is defined, then sticks once it resolves).
  def self.engine
    return @engine if @engine && @engine != :unknown
    return :unknown unless defined?(PokeBattle_Move)
    names = PokeBattle_Move.instance_methods.map { |m| m.to_s }
    @engine =
      if names.include?("pbType")        then :ess162
      elsif names.include?("pbCalcType") then :if_fork
      else :unknown
      end
    ($chrooked_log.call("[chrooked:compat] engine detected = #{@engine}") rescue nil)
    @engine
  end

  # IF2's PBTypes compat class is a STUB with no type constants, so the plugins'
  # isConst?(type, PBTypes, :DARK) always returned false (const_defined?(:DARK) is
  # false there). Populate PBTypes constants from GameData::Type (:DARK => :DARK)
  # so the existing symbol-based type checks resolve. Stock 16.2 already defines
  # these (as integers) — NEVER touch it there. Idempotent + lazy (needs GameData).
  def self.ensure_pbtypes!
    return if @pbtypes_ready
    return unless engine == :if_fork
    return unless defined?(GameData) && defined?(GameData::Type) && defined?(PBTypes)
    begin
      GameData::Type.each do |t|
        sym = t.id
        PBTypes.const_set(sym, sym) unless PBTypes.const_defined?(sym)
      end
      @pbtypes_ready = true
      ($chrooked_log.call("[chrooked:compat] PBTypes constants populated (if_fork)") rescue nil)
    rescue Exception => e
      ($chrooked_log.call("[chrooked:compat] PBTypes populate ERROR: #{e.class}: #{e.message}") rescue nil)
    end
  end

  # IF2's PBMoves compat module lists only IF2's OWN moves as constants, so a custom
  # move (EXCALIBUR, DRACONICFANG, ...) makes isConst?(@id, PBMoves, :CUSTOM) false
  # (const_defined? fails) — breaking every move-id gate (fangflinch, excalibur, the
  # Moonlight/Synthesis checks). Populate PBMoves from GameData::Move (:ID => :ID) so
  # all moves resolve. @id is a Symbol on this fork, so isConst? then compares
  # symbol==symbol. 16.2 already has full PBMoves (integers) — never touched there.
  def self.ensure_pbmoves!
    return if @pbmoves_ready
    return unless engine == :if_fork
    return unless defined?(GameData) && defined?(GameData::Move) && defined?(PBMoves)
    begin
      GameData::Move.each do |m|
        sym = m.id
        PBMoves.const_set(sym, sym) unless PBMoves.const_defined?(sym)
      end
      @pbmoves_ready = true
      ($chrooked_log.call("[chrooked:compat] PBMoves constants populated (if_fork)") rescue nil)
    rescue Exception => e
      ($chrooked_log.call("[chrooked:compat] PBMoves populate ERROR: #{e.class}: #{e.message}") rescue nil)
    end
  end

  # Populate both compat constant tables once GameData is up. Plugins call
  # isConst?(.., PBTypes/PBMoves, ..) DIRECTLY (not via a helper), so these must be
  # filled eagerly before any battle — armed on Graphics.update at the file bottom.
  def self.ensure_pb_constants!
    ensure_pbtypes!
    ensure_pbmoves!
  end

  # True if `move` makes contact. Bridges 16.2 isContactMove? and IF2's contactMove?.
  def self.contact_move?(move)
    return false unless move
    (move.isContactMove? rescue (move.contactMove? rescue false))
  end

  # The move's RESOLVED type in the engine's native representation (16.2 integer
  # id; IF2 symbol like :NORMAL), or nil if undeterminable. `move` is the
  # PokeBattle_Move (pass `self` from inside a move method); user/target battlers.
  # On 16.2 this is exactly the old `pbType(@type, attacker, opponent)`.
  def self.move_type(move, user, target)
    case engine
    when :ess162
      (move.pbType(move.type, user, target) rescue nil)
    when :if_fork
      ensure_pb_constants!
      (move.pbCalcType(user) rescue nil)
    else
      (move.type rescue nil)
    end
  end

  # Is the move physical? `movetype` is the resolved type (from move_type), used by
  # the old gen3-5 type-based split on 16.2; IF2 (gen6) uses per-move category, so
  # the type arg is ignored there. Returns false on an engine lacking both.
  def self.move_physical?(move, movetype)
    case engine
    when :ess162  then (move.pbIsPhysical?(movetype) rescue false)
    when :if_fork then (move.physicalMove? rescue false)
    else false
    end
  end

  def self.move_special?(move, movetype)
    case engine
    when :ess162  then (move.pbIsSpecial?(movetype) rescue false)
    when :if_fork then (move.specialMove? rescue false)
    else false
    end
  end

  # First seam name present on `klass` from `candidates` (engine-renamed methods),
  # or nil. Used at install time to alias whichever name this engine actually has.
  def self.seam(klass, candidates)
    names = klass.instance_methods.map { |m| m.to_s }
    candidates.find { |c| names.include?(c) }
  end

  # Install a post-damage hook on PokeBattle_Battler that calls the battler instance
  # method named `apply_method` with (move, user, target, damage) AFTER the engine's
  # own handler. Bridges the engine rename: 16.2's pbEffectsOnDealingDamage(move,user,
  # target,damage) (damage passed) and IF2's pbEffectsOnMakingHit(move,user,target)
  # (damage read from target.damageState.hpLost). `orig` is this plugin's unique backup
  # name so multiple plugins chain on the same seam. Idempotent; returns true if the
  # seam exists (installed or already), false if neither seam is present.
  def self.install_post_damage(apply_method, orig)
    return false unless defined?(PokeBattle_Battler)
    s = seam(PokeBattle_Battler, ["pbEffectsOnDealingDamage", "pbEffectsOnMakingHit"])
    return false unless s
    return true if PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?(orig)
    PokeBattle_Battler.class_eval do
      alias_method orig.to_sym, s.to_sym
      if s == "pbEffectsOnDealingDamage"
        define_method(s) do |move, user, target, damage|
          send(orig, move, user, target, damage)
          send(apply_method, move, user, target, damage)
        end
      else
        define_method(s) do |move, user, target|
          send(orig, move, user, target)
          dmg = (target.damageState.hpLost rescue 0)
          send(apply_method, move, user, target, dmg)
        end
      end
    end
    true
  end

  # Install a type-effectiveness hook on PokeBattle_Move. Bridges 16.2's
  # pbTypeModifier(type,attacker,opponent) and IF2's pbCalcTypeMod(moveType,user,
  # target) — same 3-arg shape and same 8-base scale (neutral 8, super 16). The
  # battler/move instance method `apply_method`(result, type, attacker, opponent)
  # receives the engine's computed effectiveness and RETURNS the (possibly modified)
  # value. `orig` is this plugin's unique backup name. Idempotent; returns true if a
  # seam exists.
  def self.install_typemod(apply_method, orig)
    return false unless defined?(PokeBattle_Move)
    s = seam(PokeBattle_Move, ["pbTypeModifier", "pbCalcTypeMod"])
    return false unless s
    return true if PokeBattle_Move.instance_methods.map { |m| m.to_s }.include?(orig)
    PokeBattle_Move.class_eval do
      alias_method orig.to_sym, s.to_sym
      define_method(s) do |type, attacker, opponent|
        r = send(orig, type, attacker, opponent)
        send(apply_method, r, type, attacker, opponent)
      end
    end
    true
  end

  # Neutral stat key -> [16.2 PBStats const name, IF2 GameData::Stat id symbol].
  STAT_TOKENS = {
    :attack   => ["ATTACK",   :ATTACK],
    :defense  => ["DEFENSE",  :DEFENSE],
    :spatk    => ["SPATK",    :SPECIAL_ATTACK],
    :spdef    => ["SPDEF",    :SPECIAL_DEFENSE],
    :speed    => ["SPEED",    :SPEED],
    :accuracy => ["ACCURACY", :ACCURACY],
    :evasion  => ["EVASION",  :EVASION],
  }

  # Lower `target`'s stat by `stages`, attributed to `user`. Bridges 16.2's
  # pbReduceStatWithCause(PBStats::X int, stages, user, cause) and IF2's
  # pbLowerStatStage(:GAMEDATA_STAT_ID sym, stages, user). `stat_key` is a neutral
  # symbol from STAT_TOKENS (:spatk/:accuracy/...). Returns true if it attempted the drop.
  def self.lower_stat(target, stat_key, stages, user)
    pair = STAT_TOKENS[stat_key]
    return false unless pair && target
    case engine
    when :ess162
      const = (PBStats.const_get(pair[0]) rescue nil)
      return false if const.nil?
      cause = (PBAbilities.getName(user.ability) rescue "")
      (target.pbReduceStatWithCause(const, stages, user, cause) rescue nil)
      true
    when :if_fork
      (target.pbLowerStatStage(pair[1], stages, user) rescue nil)
      true
    else
      false
    end
  end

  # Non-fainted battlers opposing `battler`. Bridges 16.2's pbIsOpposing?/isFainted?
  # and IF2's opposes?/fainted?. Returns [] if the battle context is unavailable.
  def self.opposing_battlers(battler)
    return [] unless battler
    battle = (battler.instance_variable_get(:@battle) rescue nil)
    return [] unless battle
    list = (battle.battlers rescue [])
    out = []
    list.each_with_index do |b, i|
      next unless b
      opp = (battler.opposes?(i) rescue (battler.pbIsOpposing?(i) rescue false))
      next unless opp
      fnt = (b.fainted? rescue (b.isFainted? rescue true))
      next if fnt
      out.push(b)
    end
    out
  end

  # Install a switch-in hook on PokeBattle_Battler. Bridges 16.2's
  # pbAbilitiesOnSwitchIn(onactive) and IF2's pbEffectsOnSwitchIn(switchIn=false).
  # Calls the battler instance method `apply_method`(switched_in_bool) AFTER the
  # engine's own. `orig` is this plugin's unique backup name. Idempotent.
  def self.install_switch_in(apply_method, orig)
    return false unless defined?(PokeBattle_Battler)
    s = seam(PokeBattle_Battler, ["pbAbilitiesOnSwitchIn", "pbEffectsOnSwitchIn"])
    return false unless s
    return true if PokeBattle_Battler.instance_methods.map { |m| m.to_s }.include?(orig)
    PokeBattle_Battler.class_eval do
      alias_method orig.to_sym, s.to_sym
      define_method(s) do |*args|
        send(orig, *args)
        send(apply_method, args[0])
      end
    end
    true
  end
end

($chrooked_log.call("[chrooked:compat] loaded") rescue nil)

# Eagerly populate PBTypes/PBMoves once GameData is up — plugins call isConst? against
# them DIRECTLY, so the tables must be filled before the first battle, not lazily on a
# helper call. Armed on Graphics.update; self-disarms after both populate.
if defined?(Graphics)
  class << Graphics
    unless method_defined?(:update_chrooked_compat_orig)
      alias_method :update_chrooked_compat_orig, :update
      def update
        (Chrooked.ensure_pb_constants! rescue nil) if defined?(GameData)
        update_chrooked_compat_orig
      end
    end
  end
  ($chrooked_log.call("[chrooked:compat] PB-constant populate armed on Graphics.update") rescue nil)
end
