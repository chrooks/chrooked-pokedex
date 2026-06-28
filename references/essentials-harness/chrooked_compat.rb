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

  # The move's RESOLVED type in the engine's native representation (16.2 integer
  # id; IF2 symbol like :NORMAL), or nil if undeterminable. `move` is the
  # PokeBattle_Move (pass `self` from inside a move method); user/target battlers.
  # On 16.2 this is exactly the old `pbType(@type, attacker, opponent)`.
  def self.move_type(move, user, target)
    case engine
    when :ess162
      (move.pbType(move.type, user, target) rescue nil)
    when :if_fork
      ensure_pbtypes!
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
    when :ess162  then (move.Chrooked.move_physical?(self, movetype) rescue false)
    when :if_fork then (move.physicalMove? rescue false)
    else false
    end
  end

  def self.move_special?(move, movetype)
    case engine
    when :ess162  then (move.Chrooked.move_special?(self, movetype) rescue false)
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
end

($chrooked_log.call("[chrooked:compat] loaded") rescue nil)
