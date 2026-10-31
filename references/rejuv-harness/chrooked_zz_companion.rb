# chrooked:zz_companion
# mod-group: convenience
# mod-summary: Pushes the party and the current battle to the dex so the companion screen follows the game.
# Static QoL mod (not a Ruleset behavior) — installed unless turned off for the Target.
#
# The dex's companion view (bottom screen on the handheld) polls
# GET /api/live/rejuv. This is the push side: one JSON blob at the start of
# every command phase (so the foe on screen is current), at the end of every
# battle, and on every map change (party after a heal, a catch, a PC visit on
# the way out). Nothing is read back; a dead dex costs one failed POST.
#
# Kirin's HTTPLite speaks plain http only (Updater.rb downgrades https on
# $kirin), so the default URL is the dex container over Tailscale. Drop a
# chrooked_companion.url file beside Game.exe to point it elsewhere; a blank
# file turns the push off.
#
# ponytail: a hand-rolled JSON writer — the stdlib json is not on Kirin's load
# path. Fire-and-forget on a Thread; if HTTPLite ever blocks the VM, the
# per-turn cost is one LAN POST.
# Nova port: references/essentials21-harness/chrooked_zz_companion.rb.
module ChrookedCompanion
  DEFAULT_URL = "http://100.69.82.20:8000/api/live/rejuv"
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
    (mon.moves || []).compact.map { |m| { "id" => m.move, "pp" => m.pp, "totalpp" => m.totalpp } }
  end

  # A party member: the Pokémon object.
  def self.party_mon(mon)
    return { "egg" => true, "name" => mon.name } if mon.isEgg?
    {
      "species" => mon.species, "form" => mon.getFormName, "form_index" => mon.form,
      "name" => mon.name, "level" => mon.level, "hp" => mon.hp, "totalhp" => mon.totalhp,
      "status" => mon.status, "ability" => mon.ability, "item" => mon.item,
      "moves" => moves(mon)
    }
  end

  # An active battler: live typing and ability (Aevian, transformed, Mega).
  def self.battler_mon(mon)
    row = party_mon(mon.pokemon)
    row.merge(
      "name" => mon.name, "level" => mon.level, "hp" => mon.hp, "totalhp" => mon.totalhp,
      "status" => mon.status, "ability" => mon.ability,
      "types" => [mon.type1, mon.type2].compact.uniq, "active" => true, "slot" => mon.index
    )
  end

  def self.snapshot(scene, battle)
    party = ($Trainer ? $Trainer.party : []).map { |mon| party_mon(mon) }
    out = { "game" => "rejuv", "scene" => scene, "map" => ($game_map ? $game_map.name : nil), "party" => party, "foes" => [] }
    if battle
      foes = []
      battle.battlers.each do |mon|
        next if mon.nil? || mon.pokemon.nil?
        if battle.pbIsOpposing?(mon.index)
          foes << battler_mon(mon)
        elsif (slot = party.index { |p| p["name"] == mon.name && p["level"] == mon.level })
          party[slot] = party[slot].merge(battler_mon(mon))
        end
      end
      opp = battle.opponent
      out["foes"] = foes
      out["wild"] = battle.pbIsWild?
      out["trainer"] = opp.is_a?(Array) ? opp.map { |t| t.name }.join(" & ") : (opp ? opp.name : nil)
    end
    out
  end

  def self.push(scene, battle = nil)
    return unless url
    body = json(snapshot(scene, battle))
    post(body)
  rescue StandardError => e
    Chrooked.log("companion: #{e.class}: #{e.message}") if defined?(Chrooked) && Chrooked.respond_to?(:log)
  end

  def self.post(body)
    unless defined?(HTTPLite) && HTTPLite.respond_to?(:post_body)
      unless @warned
        @warned = true
        Chrooked.log("companion: HTTPLite.post_body missing, push off") if defined?(Chrooked)
      end
      return
    end
    return if @thread && @thread.alive?   # one in flight at a time; a stale blob is replaced next event
    @thread = Thread.new do
      begin
        HTTPLite.post_body(url, body, "application/json", { "Content-Length" => body.bytesize.to_s })
      rescue StandardError
        nil
      end
    end
  end
end

if defined?(PokeBattle_Battle)
  class PokeBattle_Battle
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
end

if defined?(Game_Map)
  class Game_Map
    alias chrooked_companion_setup setup
    def setup(*args)
      chrooked_companion_setup(*args)
      ChrookedCompanion.push("overworld")
    end
  end
end
