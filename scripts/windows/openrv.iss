; Open RV installer for the derek-rein/OpenRV release workflow.
; Build with:
;   ISCC.exe /DSourceDir=C:\path\_install /DAppVersion=4.0.2 /DOutputDir=C:\path\dist scripts\windows\openrv.iss

#ifndef SourceDir
  #define SourceDir "..\..\_install"
#endif
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef OutputDir
  #define OutputDir "dist"
#endif
#ifndef OutputBaseFilename
  #define OutputBaseFilename "openrv-windows-x86_64-setup"
#endif

[Setup]
AppId={{A7E3C1D4-6B58-4F0A-9C21-8E5D2F7A1B34}
AppName=Open RV
AppVersion={#AppVersion}
AppPublisher=CompStart.pro
AppPublisherURL=https://compstart.pro
AppSupportURL=https://github.com/derek-rein/OpenRV
AppUpdatesURL=https://github.com/derek-rein/OpenRV/releases
DefaultDirName={autopf}\CompStart.pro\Open RV
DefaultGroupName=Open RV
DisableProgramGroupPage=no
LicenseFile=INSTALLER_LICENSE.txt
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
; RV.ico already contains 16, 24, 32, 48, 64, 96, 128, and 256 px images.
SetupIconFile=..\..\src\bin\apps\rv\RV.ico
UninstallDisplayIcon={app}\bin\rv.exe
UninstallDisplayName=Open RV
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; x64 (not x64compatible) so Inno Setup 6.0 through current 6.x all accept the script.
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
ChangesAssociations=yes
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked
Name: "fileassoc"; Description: "Associate Open RV with .exr, .dpx, .mov, .mp4, and .rv files"; GroupDescription: "File associations:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Open RV"; Filename: "{app}\bin\rv.exe"; WorkingDir: "{app}\bin"; IconFilename: "{app}\bin\rv.exe"
Name: "{group}\Uninstall Open RV"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Open RV"; Filename: "{app}\bin\rv.exe"; WorkingDir: "{app}\bin"; IconFilename: "{app}\bin\rv.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\.exr"; ValueType: string; ValueName: ""; ValueData: "OpenRV.exr"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.exr"; ValueType: string; ValueName: ""; ValueData: "OpenEXR image"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.exr\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\bin\rv.exe,0"; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.exr\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\bin\rv.exe"" ""%1"""; Tasks: fileassoc

Root: HKA; Subkey: "Software\Classes\.dpx"; ValueType: string; ValueName: ""; ValueData: "OpenRV.dpx"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.dpx"; ValueType: string; ValueName: ""; ValueData: "DPX image"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.dpx\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\bin\rv.exe,0"; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.dpx\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\bin\rv.exe"" ""%1"""; Tasks: fileassoc

Root: HKA; Subkey: "Software\Classes\.mov"; ValueType: string; ValueName: ""; ValueData: "OpenRV.mov"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.mov"; ValueType: string; ValueName: ""; ValueData: "QuickTime movie"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.mov\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\bin\rv.exe,0"; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.mov\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\bin\rv.exe"" ""%1"""; Tasks: fileassoc

Root: HKA; Subkey: "Software\Classes\.mp4"; ValueType: string; ValueName: ""; ValueData: "OpenRV.mp4"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.mp4"; ValueType: string; ValueName: ""; ValueData: "MPEG-4 movie"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.mp4\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\bin\rv.exe,0"; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.mp4\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\bin\rv.exe"" ""%1"""; Tasks: fileassoc

Root: HKA; Subkey: "Software\Classes\.rv"; ValueType: string; ValueName: ""; ValueData: "OpenRV.session"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.session"; ValueType: string; ValueName: ""; ValueData: "Open RV session"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.session\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\bin\rv.exe,0"; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\OpenRV.session\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\bin\rv.exe"" ""%1"""; Tasks: fileassoc

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
