# User guide

This guide covers version 0.1.0. Tools are added from version 0.2.0 on; until then they
appear in the overview as "Not available yet".

## Install

**Installer.** Run `DesktopOrganizer-<version>-setup.exe`. It installs for your user only and needs no administrator rights. A Start menu entry is created; a desktop shortcut is optional.

**Portable.** Unpack `DesktopOrganizer-<version>-portable.zip` anywhere, for example to a USB drive, and start `DesktopOrganizer.exe`. All data is stored in the `data` folder next to it.

Windows may show "Windows protected your PC" because the program is not code-signed yet. Choose "More info", then "Run anyway". See `SECURITY.md` for how to verify the download.

## Main window

- The sidebar shows all tools or one category at a time; the number next to each entry is the number of tools in it.
- Type in the search field to find tools by name or description. Ctrl+K (or Ctrl+F) jumps to the search field, Esc clears it, Down moves to the first tool, the arrow keys move between tools.
- Enter or a click opens a tool. Tools marked "Planned" are not available yet.
- The line at the bottom shows CPU load, memory use and, on laptops, the battery level. It updates every two seconds.

## Settings

Open with Settings at the bottom of the sidebar or Ctrl+,.

- **Language:** German, English, or the same as Windows (English if Windows is English, otherwise German). Changes apply immediately.
- **Theme:** light, dark, or the same as Windows. Changes apply immediately.
- **Data:** shows where your data is stored and opens the data or log folder.
- **Export data:** saves settings and the database as a ZIP file.
- **Delete all data:** removes all settings, tool data and logs after a confirmation, then closes the app. Files in your own folders are not affected.

## Uninstall

Windows Settings > Apps > Installed apps > Desktop Organizer > Uninstall. Your data stays in `%APPDATA%\DesktopOrganizer`; remove it with "Delete all data" before uninstalling if you want it gone.

## Problems

Settings > Open log folder shows `desktop-organizer.log`. If the app reports an unexpected error, it keeps running and writes the details there.
