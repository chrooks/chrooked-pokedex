# chrooked dex lab (mjolnir NV-5, 2026-10-22): keep the lab's saves out of the
# synced save folder. LAB-ONLY - never deploy to the live PC copy or thor.
#
# The lab and the live PC copy share Game.ini Title=Nova, so both resolve
# System.data_directory to %AppData%\Roaming\Nova, which is the nova-saves
# Syncthing folder. A save made in the lab would overwrite Chris's real save
# there and Syncthing would carry it to hestia and thor.
#
# SaveData::DIRECTORY is read at call time everywhere it is used (SaveData,
# Game.save's default argument, the load/save screens), so replacing the
# constant here, after 002_Save data defines it, moves every save and load.
module SaveData
  chrooked_lab_dir = File.expand_path("LabSaves") + "/"
  Dir.mkdir(chrooked_lab_dir) unless File.directory?(chrooked_lab_dir)
  remove_const(:DIRECTORY)
  const_set(:DIRECTORY, chrooked_lab_dir)
end

begin
  File.open("chrooked_load.log", "a") { |f| f.puts("[chrooked:lab] save dir #{SaveData::DIRECTORY}") }
rescue StandardError
end
