# nova_compile.ps1 — recompile Pokémon Nova's PBS into Data/*.dat in the dex LAB copy.
#
# The lab copy runs Essentials in debug mode (mkxp.json: "debugMode": true), which
# is the only mode that compiles PBS. The live copies never do. Launches Game.exe,
# waits until no .dat has changed for ~45 s, stops it, and prints which .dat files
# now differ from the shipped set. Exit 1 when Essentials wrote errorlog.txt.
#
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File nova_compile.ps1
#        [-Lab 'D:\...\NovaV3.0-dexlab\Nova'] [-Shipped 'D:\...\NovaV3.0\Nova\Data.vanilla-2026-10-22']
param(
  [string]$Lab = 'D:\Games\Pokemon FanGames\NovaV3.0-dexlab\Nova',
  [string]$Shipped = 'D:\Games\Pokemon FanGames\NovaV3.0\Nova\Data.vanilla-2026-10-22',
  [int]$TimeoutSeconds = 420
)
$ErrorActionPreference = 'Stop'
$errlog = Join-Path $Lab 'errorlog.txt'
Remove-Item $errlog -Force -ErrorAction SilentlyContinue
$p = Start-Process -FilePath (Join-Path $Lab 'Game.exe') -WorkingDirectory $Lab -PassThru
$t0 = Get-Date; $stable = 0
while (((Get-Date) - $t0).TotalSeconds -lt $TimeoutSeconds) {
  Start-Sleep -Seconds 5
  if ($p.HasExited) { break }
  $newest = (Get-ChildItem (Join-Path $Lab 'Data') -Filter *.dat | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
  $age = [int]((Get-Date) - $newest).TotalSeconds
  if ($age -gt 45 -and ((Get-Date) - $t0).TotalSeconds -gt 50) { $stable++ } else { $stable = 0 }
  if ($stable -ge 2) { break }
}
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
'compile run: {0}s' -f [int]((Get-Date) - $t0).TotalSeconds
if (Test-Path $errlog) {
  'COMPILE ERROR (errorlog.txt):'
  Get-Content $errlog | Select-Object -First 12
  exit 1
}
'changed vs shipped:'
foreach ($f in Get-ChildItem (Join-Path $Lab 'Data') -Filter *.dat) {
  $ship = Join-Path $Shipped $f.Name
  if (-not (Test-Path $ship)) { continue }
  if ((Get-FileHash $f.FullName -Algorithm MD5).Hash -ne (Get-FileHash $ship -Algorithm MD5).Hash) { '  ' + $f.Name }
}
exit 0
