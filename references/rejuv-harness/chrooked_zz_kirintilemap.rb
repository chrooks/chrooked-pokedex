# chrooked:zz_kirintilemap — Kirin compatibility shim, hand-placed (not generated).
#
# Symptom: on some maps the overworld freezes on its last frame while logic,
# input and audio keep running. Cause: the map's tileset PNG is taller than the
# GPU max texture size (Adreno: 16384px; "GearenCity Real" is 17000px, and 28
# Rejuv tilesets exceed the limit). Desktop mkxp-z splits oversized tilesets;
# Kirin's build fails the upload silently and the tile layer never draws.
#
# Fix: route Spriteset_Map to Rejuv's pure-Ruby CustomTilemap, which blits
# tiles in small chunks and never builds a giant texture. Rejuv only loads it
# for JoiPlay (Bootstrap.rb: `$joiplay ? 'TilemapXP' : nil`) — Kirin postdates
# that line — so this shim loads the file itself first.
#
# ponytail: one const_set, not a rewrite. Ruby resolves a bare constant against
# the enclosing class before Object, and `Tilemap.new` appears in exactly ONE
# place (Spriteset_Map#initialize), so Spriteset_Map::Tilemap redirects only
# that call site. Global ::Tilemap is untouched.
#
# Revert: delete this file (apply never prunes mods).
if $kirin
  unless defined?(CustomTilemap)
    begin
      loadScript('Scripts/TilemapXP.rb')
    rescue StandardError
      eval(File.read('Scripts/TilemapXP.rb'), nil, 'Scripts/TilemapXP.rb') rescue nil
    end
  end
  if defined?(Spriteset_Map) && defined?(CustomTilemap) &&
     !Spriteset_Map.const_defined?(:Tilemap, false)
    Spriteset_Map.const_set(:Tilemap, CustomTilemap)
  end

  # Force the per-tile cached-bitmap path. CustomTilemap's fast path assigns
  # the WHOLE tileset bitmap to each priority-tile sprite (sprite.bitmap =
  # @tileset, src_rect picks the tile) — putting the >16384px mega texture
  # right back on the GPU. @diffsizes=true instead caches each tile id as its
  # own 32px Bitmap (stretch_blt at 1:1 = plain copy), so nothing oversized
  # ever reaches a sprite.
  if defined?(CustomTilemap)
    module ChrookedKirinDiffsizes
      def initialize(*a)
        super
        @diffsizes = true
      end
    end
    CustomTilemap.prepend(ChrookedKirinDiffsizes)
  end
end

# Load receipt — proves in chrooked-probe.log what actually happened.
begin
  routed = defined?(Spriteset_Map) && Spriteset_Map.const_defined?(:Tilemap, false)
  File.open("chrooked-probe.log", "a") { |f|
    f.puts("#{Time.now.strftime('%H:%M:%S')} MARK kirintilemap loaded kirin=#{!!$kirin} custom=#{defined?(CustomTilemap) ? 'yes' : 'NO'} routed=#{routed ? 'yes' : 'NO'}")
  }
rescue StandardError
  nil
end
