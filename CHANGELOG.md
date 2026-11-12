# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [1.0.0] - 2026-11-12

First complete release. All twelve tools are available; each opens as its own program
window with its own settings.

### Added

- **File cleaner**: sorts a folder into subfolders by type (optionally by year and month), preview with filter, never overwrites, journal and full undo of the last run.
- **Duplicate finder**: several folders, three comparison methods (full content hash, fast, name and size), size and type filters, excluded folder names, automatic selection rules, keep-one protection, Recycle Bin or move, CSV report, context actions.
- **Folder sizes**: drill-down folder table with share bars, largest files, file types, drive usage.
- **Text replacer**: preview of every changed line, case, whole word and regular expressions, keeps encoding and line endings, skips files changed since the preview, backups and undo.
- **Backup helper**: profiles, incremental copy of new and changed files, mirror mode (to the Recycle Bin), verification by size or hash, log and history.
- **Password generator**: secure random source, password and passphrase modes (German and English word lists), strength and entropy, batch generation, clipboard cleared automatically.
- **Notes**: full-text search, tags, pinning, autosave, Markdown export; found from the overview search.
- **Tasks**: quick entry, due dates, priorities, lists, filters (today, overdue, upcoming, completed), linked reminders.
- **Reminders**: one-off and recurring (minutes, daily, weekdays, weekly, monthly) as Windows notifications, templates, missed reminders reported.
- **Time tracker**: start/stop per project, survives restarts, today and week views, manual entries, projects, CSV export.
- **System monitor**: live CPU, memory and network charts, load per core, battery, drives, processes.
- **Clipboard history**: off by default, encrypted with Windows DPAPI, skips password managers and confidential content, search, pin, copy again.
- Main window with sidebar, today strip, tool search and a settings page with per-tool settings, background mode, autostart, global shortcuts and clipboard recording.
- Notification area icon with quick actions.
- System-wide installer (Program Files, UAC prompt once, Start menu, desktop shortcut, uninstaller) and portable ZIP.

## [0.1.0] - 2026-11-12

Foundation: application shell, settings, storage, theming, German and English UI, build and release pipeline.
