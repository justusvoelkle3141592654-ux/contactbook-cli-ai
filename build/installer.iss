; Inno Setup script for Desktop Organizer. Compiled by build/build.py, which passes
; AppVersion, AppPublisher, SourceDir, OutputDir and IconFile on the command line.
;
; Per-user installation: no administrator rights, installs to
; %LOCALAPPDATA%\Programs\Desktop Organizer and adds a Start menu entry.
; User data in %APPDATA%\DesktopOrganizer is left untouched on uninstall; it can be
; removed from the app with Settings > Delete all data.

#ifndef AppVersion
  #error AppVersion must be defined
#endif

[Setup]
AppId={{6F1E3B7C-6C55-4F0C-9A3E-2C7D6B0D9A41}
AppName=Desktop Organizer
AppVersion={#AppVersion}
AppVerName=Desktop Organizer {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\Desktop Organizer
DefaultGroupName=Desktop Organizer
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19045
OutputDir={#OutputDir}
OutputBaseFilename=DesktopOrganizer-{#AppVersion}-setup
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\DesktopOrganizer.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
VersionInfoVersion={#AppVersion}
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Desktop Organizer"; Filename: "{app}\DesktopOrganizer.exe"
Name: "{autodesktop}\Desktop Organizer"; Filename: "{app}\DesktopOrganizer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DesktopOrganizer.exe"; Description: "{cm:LaunchProgram,Desktop Organizer}"; Flags: nowait postinstall skipifsilent
