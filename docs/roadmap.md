# Roadmap

Progress per milestone. This file stands in for GitHub issues while issues are disabled
in the repository; each entry becomes one issue once they are enabled.

## Milestone 1: Interview and plan — done

- [x] Decisions recorded (`docs/plan.md`)
- [x] Stack chosen: Python 3.12, PySide6, PyInstaller, Inno Setup
- [x] Design system (`docs/design-system.md`)

## Milestone 2: Foundation — in review

- [x] App shell, overview window with search and status line
- [x] Theming (light, dark, follow Windows), German and English UI
- [x] Settings (JSON, versioned), SQLite storage with per-tool migrations, rotating log
- [x] Settings dialog: language, theme, data folder, log folder, export, delete all data
- [x] CI on Windows: lint, types, tests, pip-audit, packaged build, smoke tests
- [x] Release workflow on version tags with checksums
- [ ] First successful Windows build on GitHub Actions confirmed
- [ ] Owner sign-off on the design (overview, settings, file cleaner mockup)

## Milestone 3: File tools

- [ ] **File cleaner**: sort a chosen folder into subfolders by type; preview of every move; conflicts never overwrite; full undo of the last run; protected paths refused; progress and cancel
- [ ] **Duplicate finder**: size first, then hash; groups; delete only after confirmation and only to the Recycle Bin; no following links into protected areas
- [ ] **Folder sizes**: sorted list with bars; drill down; open in Explorer; inaccessible folders reported
- [ ] **Text replacer**: preview of every change; case and whole-word options; file filter; optional backup of originals; undo; encoding detection, binary files skipped

## Milestone 4: Safety tools

- [ ] **Backup helper**: chosen folders to a destination; only changed files; progress, log and verification; handles files changing during copy
- [ ] **Password generator**: length and character sets; passphrase mode; `secrets` as random source; strength indicator; copy; never written to disk or logs

## Milestone 5: Everyday tools

- [ ] **Notes**: quick capture, tags, full-text search (FTS5), searchable from the overview, global shortcut
- [ ] **Task list**: add, check off, edit, due dates, optional link to a reminder
- [ ] **Reminders**: one-off and recurring; native notifications respecting Focus Assist; missed reminders shown on next start
- [ ] **Time tracker**: start/stop per task or project; daily and weekly overview; CSV export; survives restarts

## Milestone 6: System tools

- [ ] **System monitor**: CPU, memory, battery, disk space; polling only while visible
- [ ] **Clipboard history**: off by default; visible when active; pause and clear; ignores content flagged as sensitive by password managers; app exclusion list; DPAPI-encrypted storage; search, copy again, pin, delete
- [ ] **Global shortcuts**: configurable, off by default, conflict detection
- [ ] **Tray and autostart**: both off by default, switchable and removable in settings
- [ ] **Update check**: GitHub Releases, off by default, notifies only

## Milestone 7: Hardening and release

- [ ] Security review of all file operations
- [ ] Accessibility pass: keyboard, screen reader names, contrast, focus
- [ ] Test on a clean Windows 10 and Windows 11 machine
- [ ] Complete user guide and screenshots
- [ ] v1.0.0 built and published by GitHub Actions
