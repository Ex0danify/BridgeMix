; Inno Setup script for the Windows installer.
; Build:  iscc /DAppVersion=1.2.3 /DSourceDir=dist\BridgeMix /DOutputDir=out packaging\windows\bridgemix.iss
; Installs once, per user and without admin rights, then BridgeMix runs from the install folder.
; Running a newer installer upgrades in place (same AppId); settings and plugins live outside it.

#ifndef AppVersion
  #error Pass /DAppVersion=X.Y.Z
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\BridgeMix"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{10A66505-8E3B-4F5E-A36B-6C861C4492B8}
AppName=BridgeMix
AppVersion={#AppVersion}
AppPublisher=Ex0danify
AppPublisherURL=https://github.com/Ex0danify/BridgeMix
AppSupportURL=https://github.com/Ex0danify/BridgeMix/issues
DefaultDirName={autopf}\BridgeMix
DefaultGroupName=BridgeMix
UninstallDisplayIcon={app}\BridgeMix.exe
SetupIconFile=..\..\assets\icon.ico
LicenseFile=..\..\LICENSE
OutputDir={#OutputDir}
OutputBaseFilename=BridgeMix-{#AppVersion}-windows-x64-setup
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BridgeMix"; Filename: "{app}\BridgeMix.exe"
Name: "{autodesktop}\BridgeMix"; Filename: "{app}\BridgeMix.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\BridgeMix.exe"; Description: "Launch BridgeMix"; Flags: nowait postinstall skipifsilent
