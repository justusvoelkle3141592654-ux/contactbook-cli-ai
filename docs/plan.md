# Plan and decisions

Decisions from the product interview (November 2026). Changing one of them is a product
decision and is recorded here.

## Decisions

| Area | Decision |
|---|---|
| Name | Desktop Organizer |
| Platform | Windows 10 (22H2) and Windows 11, 64-bit only |
| Delivery | System-wide installer into Program Files (one UAC prompt during setup, Start menu, desktop shortcut, uninstaller; changed on owner request for 1.0) and a portable ZIP |
| Tool windows | Every tool runs as its own process and top-level window (own taskbar button), with its own settings in the tool and on the main settings page (owner request for 1.0) |
| Tray and autostart | Available, both off by default, switchable in settings |
| Audience | Personal use first, built so it can be shared later without rework |
| Scope of 1.0 | All 12 tools |
| Build order | File tools, safety tools, everyday tools, system tools (milestones 3 to 6) |
| Global shortcuts | Yes, user-configurable, off by default |
| Data location | `%APPDATA%\DesktopOrganizer`; portable build stores data in `data\` next to the `.exe` |
| Clipboard history | Off by default; ignores content marked as sensitive by password managers; pause, clear and app exclusion list |
| Encryption | Clipboard history encrypted with Windows DPAPI (bound to the user account); notes and tasks stored unencrypted |
| Backup helper | Free choice of source and destination including external, network and cloud-synced folders; system and other users' folders blocked |
| Theme | Follows Windows, overridable |
| Accent | Own calm blue (`#1F5FBF` light, `#6CA6EE` dark) |
| Visual reference | Windows 11 built-in apps (Settings, File Explorer, PowerToys) |
| Language | English if Windows is English, otherwise German; switchable |
| Repository | This repository, to be renamed `desktop-organizer` and set to private by the owner |
| Branching | Work on the session branch, one pull request per milestone, owner merges |
| Code signing | Unsigned for now; SHA-256 checksums published with every release |
| Releases | Built by GitHub Actions on version tags |
| Update check | Not included in 1.0: the repository is private, so an unauthenticated check against GitHub Releases cannot work |

## Stack

Two options were evaluated.

**Python 3.12 + PySide6 (Qt 6.8) + PyInstaller** (chosen)

- Mature native widget toolkit with real Windows integration: native file dialogs, system tray, notifications, high-DPI, dark title bar, accessibility (UI Automation).
- Qt widgets render lists, tables and forms densely and fast, which matches the product better than a web view.
- All tool logic (hashing, copying, SQLite, `psutil`) is straightforward Python and testable without a window.
- Reliable packaging with PyInstaller; no runtime for the user to install.
- Cost: larger download than Tauri (0.1.0: installer 27.7 MB, portable ZIP 39.2 MB) and a cold start of a few seconds.

**Tauri 2 (Rust) + web front end**

- Smaller binary (under 15 MB) and fast start.
- UI would be HTML/CSS in WebView2: a "native feel" has to be rebuilt by hand, and dense tables, keyboard handling and accessibility need much more custom work.
- Two languages (Rust and TypeScript) for every tool; file system work, tray and global shortcuts depend on plugins of varying maturity.

PySide6 gives the more native, consistent result for a tool-heavy desktop app with less risk. The size is the trade-off and is accepted.

## Architecture

See `docs/architecture.md`.

## Milestones

Detailed progress: `docs/roadmap.md`.

1. Interview and plan: decisions, stack, design system. (This document.)
2. Foundation: app shell, overview, theming, i18n, storage, logging, settings, CI, release pipeline, first build.
3. File tools: file cleaner, duplicate finder, file size overview, text replacer.
4. Safety tools: backup helper, password generator.
5. Everyday tools: notes, task list, reminders, time tracker.
6. System tools: system monitor, clipboard history, global shortcuts, tray, autostart, update check.
7. Hardening and release: security review, accessibility pass, clean-machine test, documentation, 1.0.0.
