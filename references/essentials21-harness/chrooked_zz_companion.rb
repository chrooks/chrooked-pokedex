# chrooked:zz_companion
# mod-group: convenience
# mod-summary: Pushes the party and the current battle to the dex so the companion screen follows the game.
# Static QoL mod (not a Ruleset behavior) — installed unless turned off for the Target.
#
# Essentials 21 port of references/rejuv-harness/chrooked_zz_companion.rb; see
# that header for the why. Posts to GET /api/live/essentials' push side at the
# start of every command phase, at the end of every battle, and on every map
# change. Plain http only (Kirin's HTTPLite). A chrooked_companion.url file in
# the game folder overrides the URL; a blank file turns the push off.
#
# ponytail: hand-rolled JSON writer, fire-and-forget Thread, one in flight.
module ChrookedCompanion
  DEFAULT_URL = "http://100.69.82.20:8000/api/live/essentials"
  URL_FILE    = "chrooked_companion.url"

  def self.url
    return @url if defined?(@url)
    @url = File.exist?(URL_FILE) ? File.read(URL_FILE).strip : DEFAULT_URL
    @url = nil if @url.empty?
    @url
  end

  def self.json(v)
    case v
    when nil then "null"
    when true, false, Numeric then v.to_s
    when Array then "[" + v.map { |x| json(x) }.join(",") + "]"
    when Hash then "{" + v.map { |k, x| json(k.to_s) + ":" + json(x) }.join(",") + "}"
    else
      s = v.to_s.gsub("\\") { "\\\\" }.gsub('"') { "\\\"" }.gsub(/[\x00-\x1f]/) { |c| format("\\u%04x", c.ord) }
      "\"#{s}\""
    end
  end

  def self.moves(mon)
    (mon.moves || []).compact.map { |m| { "id" => m.id, "pp" => m.pp, "totalpp" => m.total_pp } }
  end

  def self.party_mon(mon)
    return { "egg" => true, "name" => mon.name } if mon.egg?
    {
      "species" => mon.species, "form" => mon.species_data.form_name, "form_index" => mon.form,
      "name" => mon.name, "level" => mon.level, "hp" => mon.hp, "totalhp" => mon.totalhp,
      "status" => (mon.status == :NONE ? nil : mon.status), "ability" => mon.ability_id, "item" => mon.item_id,
      "moves" => moves(mon)
    }
  end

  def self.battler_mon(mon)
    row = party_mon(mon.pokemon)
    row.merge(
      "name" => mon.name, "level" => mon.level, "hp" => mon.hp, "totalhp" => mon.totalhp,
      "status" => (mon.status == :NONE ? nil : mon.status), "ability" => mon.ability_id,
      "types" => mon.types.compact.uniq, "active" => true, "slot" => mon.index
    )
  end

  def self.snapshot(scene, battle)
    party = ($player ? $player.party : []).map { |mon| party_mon(mon) }
    out = { "game" => "nova", "scene" => scene, "map" => ($game_map ? $game_map.name : nil), "party" => party, "foes" => [] }
    if battle
      foes = []
      battle.allBattlers.each do |mon|
        next if mon.pokemon.nil?
        if battle.opposes?(mon.index)
          foes << battler_mon(mon)
        elsif (slot = party.index { |p| p["name"] == mon.name && p["level"] == mon.level })
          party[slot] = party[slot].merge(battler_mon(mon))
        end
      end
      opp = battle.opponent
      out["foes"] = foes
      out["wild"] = battle.wildBattle?
      out["trainer"] = opp ? opp.map { |t| t.name }.join(" & ") : nil
    end
    out
  end

  def self.push(scene, battle = nil)
    return unless url
    post(json(snapshot(scene, battle)))
  rescue StandardError => e
    echoln("companion: #{e.class}: #{e.message}") if defined?(echoln)
  end

  def self.post(body)
    return unless defined?(HTTPLite) && HTTPLite.respond_to?(:post_body)
    return if @thread && @thread.alive?
    @thread = Thread.new do
      begin
        HTTPLite.post_body(url, body, "application/json", { "Content-Length" => body.bytesize.to_s })
      rescue StandardError
        nil
      end
    end
  end
end

class Battle
  alias chrooked_companion_pbCommandPhase pbCommandPhase
  def pbCommandPhase(*args)
    ChrookedCompanion.push("battle", self)
    chrooked_companion_pbCommandPhase(*args)
  end

  alias chrooked_companion_pbEndOfBattle pbEndOfBattle
  def pbEndOfBattle(*args)
    ret = chrooked_companion_pbEndOfBattle(*args)
    ChrookedCompanion.push("overworld")
    ret
  end
end

class Game_Map
  alias chrooked_companion_setup setup
  def setup(*args)
    chrooked_companion_setup(*args)
    ChrookedCompanion.push("overworld")
  end
end
