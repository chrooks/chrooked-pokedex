# chrooked dex lab (mjolnir NV-4, 2026-10-22). LAB COPY ONLY — never ship.
# Nova's map 050 (Outskirts) stores weather :Black, which no Nova script registers.
# The game never validates it, but Essentials' PBS writer and compiler do, so the
# round trip Data -> PBS -> Data dies there. A placeholder entry lets both pass and
# leaves the compiled value exactly as shipped.
unless GameData::Weather.exists?(:Black)
  GameData::Weather.register({
    :id        => :Black,
    :id_number => 99,
    :category  => :None
  })
end

# Phion stripped Scene_DebugIntro's `load_custom_start`, so debug mode's title
# skip crashes right after the compile. Go to the normal title screen instead.
if defined?(Settings::SKIP_TITLE_SCREEN)
  Settings.send(:remove_const, :SKIP_TITLE_SCREEN)
  Settings.const_set(:SKIP_TITLE_SCREEN, false)
end
