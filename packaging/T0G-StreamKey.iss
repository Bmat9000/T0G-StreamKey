#ifndef AppVersion
  #error Pass the project version with /DAppVersion
#endif

[Setup]
AppId=T0G.StreamKey.Windows
AppName=T0G StreamKey
AppVersion={#AppVersion}
AppPublisher=T0G
DefaultDirName={localappdata}\Programs\T0G StreamKey
DefaultGroupName=T0G StreamKey
PrivilegesRequired=lowest
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=T0G-StreamKey-Setup
SetupIconFile=..\build\streamkey.ico
UninstallDisplayIcon={app}\T0G-StreamKey.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\build\installed\T0G-StreamKey\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\T0G StreamKey"; Filename: "{app}\T0G-StreamKey.exe"
Name: "{autodesktop}\T0G StreamKey"; Filename: "{app}\T0G-StreamKey.exe"; Tasks: desktopicon
