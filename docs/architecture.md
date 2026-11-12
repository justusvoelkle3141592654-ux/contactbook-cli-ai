# Architecture

## Overview

```
src/desktop_organizer/
├─ __init__.py          version (single source of truth), app name
├─ __main__.py          python -m desktop_organizer
├─ app/                 Qt shell
│  ├─ application.py    start-up sequence, --smoke-test
│  ├─ context.py        AppContext: services handed to every window
│  ├─ overview.py       main window: sidebar, tools page, status line
│  ├─ settings_page.py  settings page (settings cards)
│  ├─ widgets.py        painted building blocks: sidebar entry, tool card, meter, cards
│  ├─ tool_window.py    base class for every tool window
│  ├─ dialogs.py        shared confirmation and message dialogs
│  ├─ theming.py        applies tokens to Qt, follows Windows light/dark, tinted icons
│  ├─ single_instance.py
│  ├─ launcher.py       start a tool as its own process
│  ├─ services.py       tray, reminders, clipboard recording, shortcuts, autostart
│  ├─ hotkeys.py        RegisterHotKey wrapper
│  ├─ settings_sync.py  reload settings changed by another process
│  ├─ components.py     info bar, progress panel, folder pickers, tables, settings form
│  └─ worker.py         background threads with progress and cancel
├─ core/                logic without UI, unit-tested
│  ├─ paths.py          data folder resolution (installed, portable, override)
│  ├─ settings.py       versioned JSON settings
│  ├─ storage.py        SQLite with per-module migrations
│  ├─ i18n.py           language files, language resolution
│  ├─ theme.py          design tokens and style sheet
│  ├─ safety.py         protected path classification
│  ├─ formatting.py     numbers, sizes, percentages per language
│  ├─ system_info.py    CPU, memory, battery readings
│  ├─ data_management.py export and delete all data
│  ├─ logging_setup.py  rotating log file
│  ├─ tool_settings.py  declarative per-tool settings
│  ├─ jobs.py           cancellation and progress for long work
│  ├─ dpapi.py          Windows DPAPI encryption (clipboard history)
│  ├─ autostart.py      HKCU Run key
│  └─ errors.py         unhandled exception hooks
├─ tools/
│  ├─ registry.py       ToolSpec, planned tools, discovery
│  └─ <tool>/           __init__.py (SPEC, settings), logic.py (no Qt), window.py, i18n.json
└─ resources/
   ├─ i18n/de.json, en.json
   ├─ icons/            Lucide SVGs (ISC)
   └─ app.ico
```

The repository layout differs from the brief in one point: the package lives in
`src/desktop_organizer/` (the standard Python "src layout") instead of `src/app`,
`src/core`, ... directly. This keeps imports unambiguous and makes packaging reliable.

## Processes

- `DesktopOrganizer.exe` starts the main window. It also runs the background services (`app/services.py`): notification area icon, reminder notifications, clipboard recording, global shortcuts, autostart.
- `DesktopOrganizer.exe --tool <id>` starts one tool in its own process and window. The main window launches tools this way (`app/launcher.py`). A second start of the same tool brings the running window to the front (`app/single_instance.py`, one local socket per tool).
- All processes share `settings.json` (watched with `QFileSystemWatcher`, `app/settings_sync.py`) and `organizer.db` (SQLite in WAL mode with a busy timeout, `core/storage.connect`).

## Start-up

1. Resolve the data folder (`DESKTOP_ORGANIZER_DATA_DIR` override, then portable `data\` next to the executable, then `%APPDATA%\DesktopOrganizer`).
2. Configure the rotating log file.
3. Create the Qt application; if another instance uses the same data folder, bring it to the front and exit.
4. Load settings (a damaged file is kept as `settings.json.broken-<time>`, defaults are used).
5. Choose the language, apply the theme, open the database and run migrations.
6. Install exception hooks, show the overview.

## Adding a tool

1. Create `tools/<tool_id>/__init__.py` with `SPEC = ToolSpec(<id>, <category>, <icon>, factory=<function returning a ToolWindow>)`.
2. Put the logic in plain Python modules inside the package and test it without Qt.
3. Subclass `ToolWindow` for the UI. Use `self.toolbar`, `self.content` and `self.footer` so every tool has the same layout.
4. If the tool stores data, define `Migration("<tool_id>", n, (...))` objects and register them at start-up.
5. Add the texts `tool.<id>.*` to both language files.

The registry finds the package automatically; no other tool changes. A planned tool with the same id is replaced by the implementation.

## Threads

Long-running work (scanning, hashing, copying) runs in worker threads (`QThreadPool` / `QRunnable`) with progress signals and a cancel flag. Workers open their own SQLite connections; the shared `Database` connection belongs to the UI thread.

## Data

| What | Where | Format |
|---|---|---|
| Settings | `<data>\settings.json` | JSON with `schema_version` |
| Tool data | `<data>\organizer.db` | SQLite, WAL mode, table `schema_migrations(module, version, applied_at)` |
| Logs | `<data>\logs\desktop-organizer.log` | Text, rotated at 1 MB, 5 files kept |

## Packaging

`python build/build.py` runs PyInstaller (one-folder, windowed, icon, version resource generated from `__version__`), packs the portable ZIP, compiles the Inno Setup installer and writes `SHA256SUMS.txt`. GitHub Actions runs the same script.
