#!/usr/bin/env ruby
# nova_dat_patch.rb — project Nova's PBS text into its compiled Data/*.dat
# without Game.exe. Mirrors the Essentials v21 compiler for the fields the
# dex owns (species types/stats/abilities/moves/evolutions, abilities, moves)
# and leaves every other field byte-for-byte as compiled by the real thing.
#
# Why: Nova ships compiled .dat files and the only compiler is the game's
# debug mode on the Windows PC. This lets hestia build the .dat and push them
# to thor when the PC is out of reach.
#
# Usage: ruby scripts/nova_dat_patch.rb GAME_DIR OUT_DIR
#   reads  GAME_DIR/PBS/*.txt and GAME_DIR/Data/{species,abilities,moves}.dat
#   writes OUT_DIR/{species,abilities,moves}.dat and prints the changed keys.
#   Exit 0 when something changed, 3 when the .dat already match the PBS.
#
# ponytail: patches records that already exist; a brand-new species or form in
# PBS is reported and skipped (the real compiler fills ~40 fields we don't own).
# Add species creation when the Ruleset starts creating species for Nova.

module GameData; end

game_dir, out_dir = ARGV
abort "usage: nova_dat_patch.rb GAME_DIR OUT_DIR" unless game_dir && out_dir

# --- Marshal with stub classes -------------------------------------------
def load_dat(path)
  data = File.binread(path)
  begin
    Marshal.load(data)
  rescue ArgumentError => e
    missing = e.message[%r{undefined class/module (\S+)}, 1]
    raise unless missing
    missing.split("::").inject(Object) do |owner, name|
      owner.const_defined?(name, false) ? owner.const_get(name) : owner.const_set(name, Class.new)
    end
    retry
  end
end

def iv(obj, name) = obj.instance_variable_get("@#{name}")
def iv_set(obj, name, value) = obj.instance_variable_set("@#{name}", value)

# --- PBS parsing (INI-ish: [ID] sections, Key = value lines) ---------------
def parse_pbs(path)
  sections = {}
  current = nil
  File.foreach(path, encoding: "UTF-8") do |raw|
    line = raw.sub(/\A\xEF\xBB\xBF/, "").strip
    next if line.empty? || line.start_with?("#")
    if (m = line.match(/\A\[(.+)\]\z/))
      current = sections[m[1]] = {}
    elsif current && (m = line.match(/\A([^=]+?)\s*=\s*(.*)\z/))
      # A repeated key (Evolution = ... several times) accumulates as one CSV.
      current[m[1]] = [current[m[1]], m[2].strip].compact.join(",")
    end
  end
  sections
end

def csv(value) = value.to_s.split(",").map(&:strip).reject(&:empty?)
def syms(value) = csv(value).map(&:to_sym)

# --- evolution parameter types from the game's own table -------------------
def evolution_param_types(game_dir)
  src = Dir[File.join(game_dir, "Data/Scripts/010_Data/001_Hardcoded data/*Evolution*.rb")].first
  types = {}
  File.read(src, encoding: "UTF-8").split("GameData::Evolution.register(").drop(1).each do |block|
    id = block[/:id\s*=>\s*:(\w+)/, 1]
    type = block[/:parameter\s*=>\s*(\S+?),/, 1]
    next unless id
    types[id.to_sym] = case type
                       when "Integer" then :integer
                       when "String" then :string
                       when "nil", nil then nil
                       else :symbol
                       end
  end
  types
end

def cast_evo_param(param, type)
  case type
  when nil then nil
  when :integer then param.to_i
  when :string then param
  else param.to_sym
  end
end

# --- species -----------------------------------------------------------------
STAT_ORDER = { HP: 0, ATTACK: 1, DEFENSE: 2, SPECIAL_ATTACK: 4, SPECIAL_DEFENSE: 5, SPEED: 3 }.freeze

def species_fields(section, evo_types)
  fields = {}
  fields[:types] = syms(section["Types"]).uniq if section["Types"]
  if section["BaseStats"]
    nums = csv(section["BaseStats"]).map(&:to_i)
    fields[:base_stats] = STAT_ORDER.to_h { |stat, idx| [stat, nums[idx]] }
  end
  fields[:abilities] = syms(section["Abilities"]) if section["Abilities"]
  fields[:hidden_abilities] = syms(section["HiddenAbilities"]) if section["HiddenAbilities"]
  if section["Moves"]
    fields[:moves] = csv(section["Moves"]).each_slice(2).map { |lvl, mv| [lvl.to_i, mv.to_sym] }
  end
  if section["Evolution"]
    # species,method,param triples; a method without a parameter (None) may
    # omit its slot entirely or leave it blank.
    tokens = section["Evolution"].split(",", -1).map(&:strip)
    evos = []
    until tokens.empty?
      species, method = tokens.shift(2)
      method = method.to_sym
      type = evo_types[method]
      param = if type.nil?
                tokens.shift if tokens.first == ""
                nil
              else
                tokens.shift
              end
      evos << [species.to_sym, method, cast_evo_param(param, type), false]
    end
    fields[:evolutions] = evos
  end
  fields
end

def patch_species(dat, pbs_dir, evo_types)
  base = parse_pbs(File.join(pbs_dir, "pokemon.txt"))
  forms = parse_pbs(File.join(pbs_dir, "pokemon_forms.txt"))
  wanted = {}   # key => fields
  skipped = []
  base.each { |id, section| wanted[id.to_sym] = species_fields(section, evo_types) }
  forms.each do |id, section|
    species, form = id.split(",")
    key = :"#{species}_#{form}"
    own = species_fields(section, evo_types)
    inherited = wanted.fetch(species.to_sym)
    # compile_pokemon_forms: nil list → base's; empty moves/evolutions → base's
    merged = inherited.merge(own)
    merged[:moves] = inherited[:moves] if own[:moves].nil? || own[:moves].empty?
    merged[:evolutions] = inherited[:evolutions] if own[:evolutions].nil? || own[:evolutions].empty?
    wanted[key] = merged
  end
  # Forward evolutions first, then the prevolution pass exactly as
  # validate_all_compiled_pokemon_forms does it (true-flagged entries rebuilt).
  forward = wanted.transform_values { |f| (f[:evolutions] || []).map(&:dup) }
  all_evos = {}
  forward.each do |key, evos|
    record = dat[key]
    next unless record
    species, form = iv(record, :species), iv(record, :form)
    evos.each do |evo|
      all_evos[evo[0]] ||= [species, evo[1], evo[2], true]
      all_evos[[evo[0], form]] ||= [species, evo[1], evo[2], true] if form > 0
    end
  end
  final = forward.transform_values { |evos| evos.map(&:dup) }
  forward.each_key do |key|
    record = dat[key]
    next unless record
    species = iv(record, :species)
    # Species#base_form: a DefaultForm_N flag, else the record's own form.
    default = (iv(record, :flags) || []).filter_map { |f| f[/\ADefaultForm_(\d+)\z/i, 1] }.first
    base_form = default ? default.to_i : iv(record, :form)
    prevo = all_evos[[species, base_form]] || all_evos[species]
    next unless prevo
    final[key].push(prevo.dup)
    prevo_key = prevo[0]
    if final[prevo_key] && final[prevo_key].none? { |evo| !evo[3] && evo[0] == species }
      final[prevo_key].push([species, :None, nil])
    end
  end
  changed = []
  wanted.each do |key, fields|
    record = dat[key]
    unless record
      skipped << key
      next
    end
    fields = fields.merge(evolutions: final[key])
    before = Marshal.dump(record)
    fields.each { |name, value| iv_set(record, name, value) }
    changed << key if Marshal.dump(record) != before
  end
  [changed, skipped]
end

# --- abilities and moves -----------------------------------------------------
def new_record(klass, template)
  obj = klass.allocate
  template.instance_variables.each { |name| obj.instance_variable_set(name, nil) }
  obj
end

def patch_abilities(dat, pbs_dir)
  template = dat.values.first
  changed = []
  parse_pbs(File.join(pbs_dir, "abilities.txt")).each do |id, section|
    key = id.to_sym
    record = dat[key] ||= new_record(template.class, template).tap do |r|
      iv_set(r, :id, key)
      iv_set(r, :pbs_file_suffix, "")
    end
    before = Marshal.dump(record)
    iv_set(record, :real_name, section["Name"] || key.to_s)
    iv_set(record, :real_description, section["Description"] || "???")
    iv_set(record, :flags, csv(section["Flags"]))
    changed << key if Marshal.dump(record) != before
  end
  changed
end

MOVE_CATEGORY = { "Physical" => 0, "Special" => 1, "Status" => 2 }.freeze

def patch_moves(dat, pbs_dir)
  template = dat.values.first
  changed = []
  parse_pbs(File.join(pbs_dir, "moves.txt")).each do |id, section|
    key = id.to_sym
    record = dat[key] ||= new_record(template.class, template).tap do |r|
      iv_set(r, :id, key)
      iv_set(r, :pbs_file_suffix, "")
    end
    before = Marshal.dump(record)
    iv_set(record, :real_name, section["Name"] || key.to_s)
    iv_set(record, :type, (section["Type"] || "NONE").to_sym)
    iv_set(record, :category, MOVE_CATEGORY.fetch(section["Category"] || "Status"))
    iv_set(record, :power, (section["Power"] || 0).to_i)
    iv_set(record, :accuracy, (section["Accuracy"] || 100).to_i)
    iv_set(record, :total_pp, (section["TotalPP"] || 5).to_i)
    iv_set(record, :target, (section["Target"] || "None").to_sym)
    iv_set(record, :priority, (section["Priority"] || 0).to_i)
    iv_set(record, :function_code, section["FunctionCode"] || "None")
    iv_set(record, :flags, csv(section["Flags"]))
    iv_set(record, :effect_chance, (section["EffectChance"] || 0).to_i)
    iv_set(record, :real_description, section["Description"] || "???")
    changed << key if Marshal.dump(record) != before
  end
  changed
end

# --- main --------------------------------------------------------------------
pbs_dir = File.join(game_dir, "PBS")
data_dir = File.join(game_dir, "Data")
evo_types = evolution_param_types(game_dir)

species = load_dat(File.join(data_dir, "species.dat"))
abilities = load_dat(File.join(data_dir, "abilities.dat"))
moves = load_dat(File.join(data_dir, "moves.dat"))

species_changed, species_skipped = patch_species(species, pbs_dir, evo_types)
abilities_changed = patch_abilities(abilities, pbs_dir)
moves_changed = patch_moves(moves, pbs_dir)

Dir.mkdir(out_dir) unless Dir.exist?(out_dir)
{ "species" => species, "abilities" => abilities, "moves" => moves }.each do |name, dat|
  File.binwrite(File.join(out_dir, "#{name}.dat"), Marshal.dump(dat))
end

puts "species changed (#{species_changed.size}): #{species_changed.join(' ')}"
puts "species skipped, not in .dat (#{species_skipped.size}): #{species_skipped.join(' ')}" unless species_skipped.empty?
puts "abilities changed (#{abilities_changed.size}): #{abilities_changed.join(' ')}"
puts "moves changed (#{moves_changed.size}): #{moves_changed.join(' ')}"
exit 3 if species_changed.empty? && abilities_changed.empty? && moves_changed.empty?
