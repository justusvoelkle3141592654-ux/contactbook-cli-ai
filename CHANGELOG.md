# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [0.1.0] - Unreleased

Foundation release. No tools are available yet; they are listed in the overview as
"Not available yet".

### Added

- Overview window with tool search, grouped tool list and a status line for CPU, memory and battery.
- Settings: language (German, English, same as Windows), theme (light, dark, same as Windows), data location, open data and log folders, export data as ZIP, delete all data.
- Local storage: versioned JSON settings, SQLite database with per-tool schema migrations.
- Rotating log file and an error dialog for unexpected errors; the app keeps running.
- Single instance per data folder; a second start brings the running window to the front.
- Portable mode via a `data` folder next to the executable.
- Per-user installer without administrator rights, portable ZIP, SHA-256 checksums.
- CI on Windows: lint, type check, tests, dependency vulnerability check, packaged build with smoke tests of the executable and the installer.
