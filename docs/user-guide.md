# User guide

Version 1.0.0.

## Install

**Installer.** Run `DesktopOrganizer-1.0.0-setup.exe` and confirm the Windows prompt ("Do you want to allow this app to make changes?") with Yes. Desktop Organizer is installed to `C:\Program Files\Desktop Organizer` with a Start menu entry and, if you keep the option, a desktop shortcut. Uninstall in Windows Settings > Apps > Installed apps.

**Portable.** Unpack `DesktopOrganizer-1.0.0-portable.zip` and start `DesktopOrganizer.exe`. Data is stored in the `data` folder next to it.

Because the program is not code-signed, Windows may show "Windows protected your PC". Choose "More info", then "Run anyway".

## Main window

- The sidebar shows all tools or one category; Settings is at the bottom.
- The today strip shows open tasks, the next reminder, the running timer and the number of notes. Click a tile to open the tool.
- Search (Ctrl+K) finds tools and notes.
- A click on a tool opens it in its own window, which appears as a separate button in the taskbar. Opening a tool that is already open brings its window to the front.

## Settings

- Every tool has a Settings button in its window (Ctrl+,). The same settings are on the main settings page under Tools. Changes apply immediately in all windows.
- **Keep running in the background**: closing the main window keeps Desktop Organizer in the notification area, so reminders, clipboard recording and shortcuts keep working. Quit from the notification area menu.
- **Start with Windows**: starts in the notification area when you sign in.
- **Global shortcuts**: quick note (Ctrl+Alt+N), clipboard history (Ctrl+Alt+V), password generator (Ctrl+Alt+P) by default; each can be changed.
- **Record clipboard**: see Clipboard history below.
- Language, theme, data folder, logs, export and Delete all data.

## File tools

**File cleaner.** Choose a folder, create a preview, review and untick files, then move. Files go into subfolders such as Images, Documents and Videos (optionally per year and month). Nothing is overwritten. "Undo last run" puts every file back.

**Duplicate finder.** Add one or more folders, choose the comparison (content is safest) and minimum size, then search. Results are grouped; the default rule pre-selects all copies except one. Change the selection by hand, with Select automatically, or with the context menu ("Keep only this file", select by folder). Move the selection to the Recycle Bin or to another folder, or export a CSV report. At least one file per group is always kept.

**Folder sizes.** Choose a folder and analyze. Double-click a folder to open it, Up to go back. Tabs show the largest files and the space per file type.

**Text replacer.** Choose a folder, enter the search and replacement text, set options and create a preview. Select a file to see each changed line. Replace writes the changes; with backups on (default) "Undo last run" restores the originals. Files changed since the preview are skipped.

## Safety tools

**Backup helper.** Create a profile, add source folders and choose a destination (USB drive, network share, OneDrive folder). The preview shows new and changed files. Start backup copies them and verifies them. Mirror mode also moves files deleted in the source to the Recycle Bin at the destination. Log and history are kept per run.

**Password generator.** Set length and character groups, or switch to passphrase. Copy puts the password on the clipboard and clears it after 30 seconds. "Several at once" creates a list; double-click copies an entry.

## Everyday tools

**Notes.** New note (Ctrl+N), type; everything saves automatically. Tags separated by commas, search with Ctrl+F, pin important notes, export as Markdown.

**Tasks.** Type a task and press Enter. "With details" sets a due date, priority, list, notes and a reminder. Filters on the left: all open, due today, overdue, upcoming, completed, and your lists.

**Reminders.** New reminder or a template (breaks, drinking water, moving). Reminders appear as Windows notifications while Desktop Organizer is running; turn on "Keep running in the background" so they also come when the main window is closed. Missed reminders are reported at the next start.

**Time tracker.** Choose or type a project and press Start. The timer keeps running when you close the window. Today shows entries, Week shows totals per project and day, Projects lets you rename, archive or delete. Export a week as CSV.

## System tools

**System monitor.** Live CPU, memory and network charts, load per core, battery, processes (End process asks first) and drives. It only measures while the window is visible.

**Clipboard history.** Off by default. Switch it on in the tool or in Settings. Copied text is stored encrypted for your Windows account; content from password managers is skipped. Search, pin, delete, and copy entries again with a double-click.

## Data and problems

- Data folder: `%APPDATA%\DesktopOrganizer` (portable: `data` next to the program). Settings > Open folder.
- Logs: Settings > Logs > Open folder. If the app reports an unexpected error, it keeps running and writes details there.
