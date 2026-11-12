# Install silently into a temporary per-user folder, smoke-test the installed app, uninstall.
param(
    [Parameter(Mandatory = $true)][string]$Setup
)
$ErrorActionPreference = "Stop"

$target = Join-Path $env:RUNNER_TEMP ("do-install-" + [guid]::NewGuid())
$install = Start-Process -FilePath $Setup -PassThru -Wait -ArgumentList @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/DIR=`"$target`""
)
if ($install.ExitCode -ne 0) { throw "Installer failed with exit code $($install.ExitCode)" }

$exe = Join-Path $target "DesktopOrganizer.exe"
if (-not (Test-Path $exe)) { throw "Installed executable not found at $exe" }
& "$PSScriptRoot/smoke_test.ps1" -Exe $exe

$uninstaller = Get-ChildItem $target -Filter "unins*.exe" | Select-Object -First 1
$uninstall = Start-Process -FilePath $uninstaller.FullName -PassThru -Wait -ArgumentList @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"
)
if ($uninstall.ExitCode -ne 0) { throw "Uninstaller failed with exit code $($uninstall.ExitCode)" }
if (Test-Path $exe) { throw "Uninstall left the executable behind" }
Write-Host "Installer smoke test passed"
