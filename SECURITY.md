# Security

What Desktop Organizer reads, writes and never does (version 1.0.0).

## Installation and rights

- The installer copies the program to `C:\Program Files\Desktop Organizer`. Windows asks once for permission (UAC) because Program Files is protected. The installed program always runs with normal user rights; the installer starts it without elevation.
- The portable ZIP needs no installation and no rights.
- Uninstalling removes the program, the Start menu entry, the desktop shortcut and the autostart entry. Your data in `%APPDATA%\DesktopOrganizer` is kept; remove it with Settings > Delete all data.

## What the app reads

- Folders you choose in the file tools (file cleaner, duplicate finder, folder sizes, text replacer, backup). Windows, Program Files, ProgramData and other users' profiles are refused; symbolic links are never followed.
- CPU, memory, disk, network, battery and process information (system monitor and status line, via `psutil`).
- The clipboard, only when you switch on clipboard recording.
- The name of the program in front when something is copied, only to skip excluded programs.

## What the app writes

- Its data folder: `%APPDATA%\DesktopOrganizer` (portable: `data\` next to the program) with `settings.json`, `organizer.db` (notes, tasks, reminders, time entries, clipboard history), logs, the file cleaner's undo journal, text replacer backups and backup logs.
- Files in folders you chose, only after a preview and your confirmation: moved files (file cleaner), files moved to the Recycle Bin or another folder (duplicate finder), changed text files (text replacer), copies at the backup destination.
- `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\DesktopOrganizer`, only when you turn on "Start with Windows", removed when you turn it off.
- Tinted icon files in `%TEMP%\DesktopOrganizer-ui` used by the style sheet.

## Deleting

- Nothing is deleted permanently by the tools. Duplicates and files removed by backup mirror mode go to the Windows Recycle Bin. On drives without a Recycle Bin (some network shares) the deletion fails and is reported.
- Settings > Delete all data removes the whole data folder after a confirmation.

## Clipboard history

- Off by default. When on, copied text is stored encrypted with Windows DPAPI, bound to your Windows account.
- Content marked by password managers (`ExcludeClipboardContentFromMonitorProcessing`, `CanIncludeInClipboardHistory = 0`) and content copied from excluded programs (KeePass, 1Password, Bitwarden and others, configurable) is not stored.
- Only text is stored; images and files are not.

## Passwords

Generated with Python's `secrets` module (the operating system's cryptographic random source). Generated passwords are never written to disk or logs. Copied passwords are removed from the clipboard after 30 seconds by default.

## What the app never does

- No network access, no telemetry, no account, no update check.
- No administrator rights at run time; no changes to system settings beyond the optional autostart entry.
- Logs contain no content of notes, tasks, clipboard entries or passwords.

## Unsigned executables

The executables are not code-signed. Windows SmartScreen shows "Windows protected your PC" on first start: choose "More info", then "Run anyway". Some antivirus products flag new, unsigned PyInstaller programs by mistake. Verify downloads with `SHA256SUMS.txt`:

```powershell
Get-FileHash .\DesktopOrganizer-1.0.0-setup.exe -Algorithm SHA256
```

## Dependencies

PySide6 (Qt), psutil and Send2Trash, pinned. CI checks them with `pip-audit` on every push.
