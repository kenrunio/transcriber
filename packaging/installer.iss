; Inno Setup script: wraps the PyInstaller folder into Transcriber-Setup-<version>.exe.
; Built by packaging\build.bat, which passes /DAppVersion, /DSourceDir and /DOutDir.
; Installs for the current user (no administrator rights needed).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6B0F3C2E-5D1A-4C84-9E3B-7A2F1D4C9B10}
AppName=Transcriber
AppVersion={#AppVersion}
AppVerName=Transcriber {#AppVersion}
AppPublisher=Kenny Green Ltd
AppPublisherURL=https://github.com/kenrunio/transcriber
; the app's update check requires ProductName "Transcriber" as well as the signature
VersionInfoProductName=Transcriber
VersionInfoCompany=Kenny Green Ltd
VersionInfoDescription=Transcriber Setup
VersionInfoVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\Transcriber
DefaultGroupName=Transcriber
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutDir}
OutputBaseFilename=Transcriber-Setup-{#AppVersion}
SetupIconFile={#SourcePath}\..\assets\transcriber.ico
UninstallDisplayIcon={app}\Transcriber.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
#ifdef Sign
; build.bat defines "signtool" as packaging\sign.bat; this signs Setup and the uninstaller
SignTool=signtool
SignedUninstaller=yes
#endif

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourcePath}\..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "{#SourcePath}\THIRD-PARTY-NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Transcriber"; Filename: "{app}\Transcriber.exe"
Name: "{userdesktop}\Transcriber"; Filename: "{app}\Transcriber.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Transcriber.exe"; Description: "Start Transcriber"; Flags: nowait postinstall skipifsilent
; an update the app installed itself (/UPDATE=1): start the new version again
Filename: "{app}\Transcriber.exe"; Flags: nowait; Check: IsAppUpdate

; Transcripts, jobs and downloaded models (in %LOCALAPPDATA%\Transcriber) are
; left in place on uninstall, so reinstalling keeps them.

[Code]
function IsAppUpdate: Boolean;
begin
  Result := ExpandConstant('{param:UPDATE|0}') = '1';
end;
