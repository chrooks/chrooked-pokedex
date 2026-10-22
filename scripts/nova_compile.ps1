# nova_compile.ps1 — recompile Pokémon Nova's PBS into Data/*.dat in the dex LAB copy.
#
# The lab copy runs Essentials in debug mode (mkxp.json: "debugMode": true), which
# is the only mode that compiles PBS. The live copies never do. Launches Game.exe,
# waits until no .dat has changed for ~45 s, stops it, and prints which .dat files
# now differ from the live PC copy's Data/ (what a deploy would copy). Exit 1 when
# Essentials wrote errorlog.txt.
#
# The reference used to be the shipped set (Data.vanilla-2026-10-22), deleted on
# 2026-10-22; a missing reference is now reported, never skipped silently.
#
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File nova_compile.ps1
#        [-Lab 'D:\...\NovaV3.0-dexlab\Nova'] [-Reference 'D:\...\NovaV3.0\Nova\Data']
param(
  [string]$Lab = 'D:\Games\Pokemon FanGames\NovaV3.0-dexlab\Nova',
  [string]$Reference = 'D:\Games\Pokemon FanGames\NovaV3.0\Nova\Data',
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
if (-not (Test-Path $Reference)) {
  'reference folder missing: {0} (cannot list changed .dat files)' -f $Reference
  exit 0
}
'differs from the live copy (a deploy copies these):'
$n = 0
foreach ($f in Get-ChildItem (Join-Path $Lab 'Data') -Filter *.dat) {
  $ref = Join-Path $Reference $f.Name
  if (-not (Test-Path $ref)) { '  {0} (new: not in the live copy)' -f $f.Name; $n++; continue }
  if ((Get-FileHash $f.FullName -Algorithm MD5).Hash -ne (Get-FileHash $ref -Algorithm MD5).Hash) { '  ' + $f.Name; $n++ }
}
if ($n -eq 0) { '  none' }
exit 0
