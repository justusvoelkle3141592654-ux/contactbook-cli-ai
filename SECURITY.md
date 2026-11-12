# Security

This document lists what Desktop Organizer reads, writes and never does. It covers the
current version (0.1.0, foundation). It will be extended with each tool.

## What the app reads

- Its own data folder: `%APPDATA%\DesktopOrganizer`, or `data\` next to the executable in the portable build.
- CPU load, memory usage and battery state for the status line (through the `psutil` library).
- The Windows light/dark setting and display language.

## What the app writes

- `settings.json`, `organizer.db` and `logs\desktop-organizer.log` in its data folder.
- A tinted icon file in the temporary folder (`%TEMP%\DesktopOrganizer-ui`), used by the style sheet.
- A ZIP file at a location you choose, only when you use "Export data".

## What the app never does

- No network access. The app makes no connections to the internet. (A future update check against GitHub Releases is planned; it will be off by default.)
- No telemetry, no account, no analytics.
- No administrator rights. The installer installs per user to `%LOCALAPPDATA%\Programs\Desktop Organizer`.
- No changes to system settings. Autostart is not implemented yet and will be off by default.
- No files outside its data folder are read or changed. Tools that work on files (from milestone 3 on) only touch folders you choose and refuse Windows, Program Files, ProgramData and other users' profiles.

## Logs

The log file records start, exit, errors and the paths of exports. It does not contain the content of notes, tasks, clipboard entries or passwords.

## Deleting data

Settings > Delete all data removes the whole data folder after a confirmation and closes the app. Uninstalling the app keeps your data, so that a reinstall does not lose it; use "Delete all data" first if you want everything removed.

## Unsigned executables

The executables are not code-signed yet. Windows SmartScreen will show "Windows protected your PC" on first start; choose "More info" and "Run anyway". Some antivirus products flag new, unsigned PyInstaller builds by mistake. Every release publishes SHA-256 checksums (`SHA256SUMS.txt`) so you can verify that a download is unchanged:

```powershell
Get-FileHash .\DesktopOrganizer-0.1.0-setup.exe -Algorithm SHA256
```

## Dependencies

Runtime dependencies are PySide6 (Qt) and psutil, with pinned versions. CI checks them against known vulnerabilities with `pip-audit` on every push.

## Reporting a problem

Open an issue in the repository. Do not include personal data or files.
