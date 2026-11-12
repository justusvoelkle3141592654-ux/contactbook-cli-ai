; Inno Setup script for Desktop Organizer. Compiled by build/build.py, which passes
; AppVersion, AppPublisher, SourceDir, OutputDir and IconFile on the command line.
;
; System-wide installation into Program Files. Windows asks for permission (UAC) once
; during setup; the installed app itself always runs with normal user rights.
; User data in %APPDATA%\DesktopOrganizer is kept on uninstall so a reinstall does not
; lose it; it can be removed in the app with Settings > Delete all data.

#ifndef AppVersion
  #error AppVersion must be defined
#endif

[Setup]
AppId={{6F1E3B7C-6C55-4F0C-9A3E-2C7D6B0D9A41}
AppName=Desktop Organizer
AppVersion={#AppVersion}
AppVerName=Desktop Organizer {#AppVersion}
AppPublisher={#AppPublisher}
AppCopyright=Copyright (c) 2026 {#AppPublisher}
DefaultDirName={autopf}\Desktop Organizer
DefaultGroupName=Desktop Organizer
DisableProgramGroupPage=yes
UsePreviousAppDir=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19045
OutputDir={#OutputDir}
OutputBaseFilename=DesktopOrganizer-{#AppVersion}-setup
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\DesktopOrganizer.exe
UninstallDisplayName=Desktop Organizer
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}
VersionInfoProductName=Desktop Organizer
VersionInfoProductVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Desktop Organizer Setup

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Desktop Organizer"; Filename: "{app}\DesktopOrganizer.exe"; Comment: "Desktop Organizer"
Name: "{autodesktop}\Desktop Organizer"; Filename: "{app}\DesktopOrganizer.exe"; Tasks: desktopicon

[Run]
; runasoriginaluser: start the app with normal rights, not with the installer's elevation.
Filename: "{app}\DesktopOrganizer.exe"; Description: "{cm:LaunchProgram,Desktop Organizer}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM DesktopOrganizer.exe"; Flags: runhidden; RunOnceId: "StopApp"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    // Remove "start with Windows" if the user had turned it on.
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'DesktopOrganizer');
end;
