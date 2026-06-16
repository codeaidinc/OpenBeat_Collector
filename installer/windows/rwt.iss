; Inno Setup script — OpenBeat Collector (collector UI) Windows installer
; Build: iscc /DMyAppVersion=1.0.2 installer\windows\rwt.iss
; Prerequisite: first build dist\OpenBeat_Collector.exe with PyInstaller.
; Note: the GitHub Actions build passes /DMyAppVersion from the git tag (e.g. v1.0.2),
; so this fallback only applies to local manual builds.
#define MyAppName "OpenBeat Collector"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.2"
#endif
#define MyAppPublisher "CodeAid Inc."
#define MyAppExeName "OpenBeat_Collector.exe"

[Setup]
AppId={{B2D9A3C1-7E4F-4F2A-9C2E-RWT0001OPEN}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Install into the user area (no admin rights needed, writable)
PrivilegesRequired=lowest
DefaultDirName={localappdata}\OpenBeat_Collector
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename=OpenBeat_Collector-Setup-{#MyAppVersion}
SetupIconFile=..\app.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional tasks:"; Flags: unchecked

[Files]
Source: "..\..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Keep collected data (data\). To remove everything, delete {app} manually.
Type: filesandordirs; Name: "{app}\_internal"
