# nova_selftest.ps1 - boot the Nova LAB copy once with the headless battle self-test.
#
# The lab-only script Data/Scripts/998_ChrookedDexLab/010_battle_selftest.rb runs a
# measured damage calc and one AI-vs-AI battle at boot when chrooked-selftest.on
# names a mechanic. Ported mechanics log their OBS lines only while
# chrooked-oracle.on exists. This sets both markers, boots Game.exe, waits for the
# self-test's DONE line, stops the game, removes the markers it created, and prints
# the log. Usually driven by nova_selftest.sh, which also scores the result.
#
# Exit 0 when the self-test logged DONE with no ERROR line; 1 otherwise; 2 when
# the lab is not ready.
#
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File nova_selftest.ps1 -Mechanic kindle
#        [-Lab 'D:\...\NovaV3.0-dexlab\Nova'] [-TimeoutSeconds 150]
param(
  [Parameter(Mandatory = $true)][string]$Mechanic,
  [string]$Lab = 'D:\Games\Pokemon FanGames\NovaV3.0-dexlab\Nova',
  [int]$TimeoutSeconds = 150
)
$ErrorActionPreference = 'Stop'
$exe      = Join-Path $Lab 'Game.exe'
$log      = Join-Path $Lab 'chrooked_load.log'
$selftest = Join-Path $Lab 'chrooked-selftest.on'
$oracle   = Join-Path $Lab 'chrooked-oracle.on'
$errlog   = Join-Path $Lab 'errorlog.txt'

if (-not (Test-Path (Join-Path $Lab 'Data\Scripts\998_ChrookedDexLab\010_battle_selftest.rb'))) {
  'self-test script missing from the lab (run nova_selftest.sh, which installs it)'; exit 2
}
$running = Get-Process -Name Game -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $exe }
if ($running) { 'the lab Game.exe is already running (pid {0}); close it first' -f $running[0].Id; exit 2 }

$hadOracle = Test-Path $oracle
Remove-Item $log, $errlog -Force -ErrorAction SilentlyContinue
Set-Content -Path $selftest -Value $Mechanic -Encoding ascii
if (-not $hadOracle) { Set-Content -Path $oracle -Value 'selftest' -Encoding ascii }
$p = $null
$t0 = Get-Date
try {
  $p = Start-Process -FilePath $exe -WorkingDirectory $Lab -PassThru
  while (((Get-Date) - $t0).TotalSeconds -lt $TimeoutSeconds) {
    Start-Sleep -Seconds 2
    if ($p.HasExited) { 'game exited by itself (code {0})' -f $p.ExitCode; break }
    if ((Test-Path $log) -and (Select-String -Path $log -Pattern 'selftest\] DONE' -Quiet)) { Start-Sleep -Seconds 1; break }
  }
} finally {
  if ($p -and -not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
  Remove-Item $selftest -Force -ErrorAction SilentlyContinue
  if (-not $hadOracle) { Remove-Item $oracle -Force -ErrorAction SilentlyContinue }
}
'self-test run: {0}s' -f [int]((Get-Date) - $t0).TotalSeconds
if (Test-Path $errlog) { '--- errorlog.txt'; Get-Content $errlog | Select-Object -First 20 }
if (-not (Test-Path $log)) { '(no chrooked_load.log written)'; exit 1 }
'--- chrooked_load.log (EST lines omitted)'
Get-Content $log | Where-Object { $_ -notmatch '\] EST ' }
$text = Get-Content $log -Raw
if ($text -match 'selftest\] DONE' -and $text -notmatch '\] ERROR') { exit 0 }
exit 1
