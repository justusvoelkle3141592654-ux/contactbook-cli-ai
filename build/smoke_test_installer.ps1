# Install silently (system-wide, as on a real PC after the UAC prompt), check the Start
# menu entry and uninstall registration, smoke-test the installed app, then uninstall.
# GitHub's Windows runners run elevated, so no UAC prompt appears here.
param(
    [Parameter(Mandatory = $true)][string]$Setup
)
$ErrorActionPreference = "Stop"

$target = Join-Path $env:ProgramFiles "Desktop Organizer"
$install = Start-Process -FilePath $Setup -PassThru -Wait -ArgumentList @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/ALLUSERS", "/TASKS=desktopicon"
)
if ($install.ExitCode -ne 0) { throw "Installer failed with exit code $($install.ExitCode)" }

$exe = Join-Path $target "DesktopOrganizer.exe"
if (-not (Test-Path $exe)) { throw "Installed executable not found at $exe" }

$shortcut = Join-Path $env:ProgramData "Microsoft\Windows\Start Menu\Programs\Desktop Organizer.lnk"
if (-not (Test-Path $shortcut)) { throw "Start menu entry missing: $shortcut" }

$uninstallKey = Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" |
    Where-Object { $_.PSChildName -like "*6F1E3B7C-6C55-4F0C-9A3E-2C7D6B0D9A41*" }
if (-not $uninstallKey) { throw "Not registered under Installed apps" }
Write-Host "Installed to $target, Start menu entry and uninstall registration present"

& "$PSScriptRoot/smoke_test.ps1" -Exe $exe

$uninstaller = Get-ChildItem $target -Filter "unins*.exe" | Select-Object -First 1
$uninstall = Start-Process -FilePath $uninstaller.FullName -PassThru -Wait -ArgumentList @(
    "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"
)
if ($uninstall.ExitCode -ne 0) { throw "Uninstaller failed with exit code $($uninstall.ExitCode)" }
Start-Sleep -Seconds 2
if (Test-Path $exe) { throw "Uninstall left the executable behind" }
if (Test-Path $shortcut) { throw "Uninstall left the Start menu entry behind" }
Write-Host "Installer smoke test passed"
