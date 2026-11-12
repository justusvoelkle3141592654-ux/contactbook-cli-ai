# Start the packaged executable with an empty data folder and --smoke-test.
# The app opens the overview and the settings window, then exits with code 0.
param(
    [Parameter(Mandatory = $true)][string]$Exe,
    [int]$TimeoutSeconds = 60
)
$ErrorActionPreference = "Stop"

$data = Join-Path $env:RUNNER_TEMP ("do-smoke-" + [guid]::NewGuid())
$env:DESKTOP_ORGANIZER_DATA_DIR = $data

$process = Start-Process -FilePath $Exe -ArgumentList "--smoke-test" -PassThru
$null = $process.Handle  # needed so ExitCode is available after the process ends
if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
    $process.Kill()
    throw "Smoke test timed out after $TimeoutSeconds s"
}
$log = Join-Path $data "logs\desktop-organizer.log"
if (Test-Path $log) { Get-Content $log }
if ($process.ExitCode -ne 0) { throw "Smoke test failed with exit code $($process.ExitCode)" }
if (-not (Select-String -Path $log -Pattern "SMOKE TEST OK" -Quiet)) { throw "Smoke test marker missing" }
Write-Host "Smoke test passed"
