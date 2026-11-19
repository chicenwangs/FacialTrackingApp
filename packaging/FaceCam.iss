#define MyAppName "FaceCam"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "chicenwangs"
#define MyAppURL "https://github.com/chicenwangs/FacialTrackingApp"
#define MyAppExe "FaceCam.exe"
#define MyCamera "softcam-facecam.dll"

[Setup]
AppId={{8F3C1A72-4B6D-4E15-9A2B-7C1D0E5F6A34}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=
OutputDir=..\installer
OutputBaseFilename=FaceCam-Setup-{#MyAppVersion}
SetupIconFile=..\Icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName} {#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Start FaceCam with Windows (in tray, low power)"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\dist\FaceCam\{#MyAppExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\FaceCam\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExe}"" --minimized"; Flags: uninsdeletevalue; Tasks: autostart

[Code]
var
  CameraDll: string;

function RunRegsvr32(const Params: string): Boolean;
var
  code: Integer;
begin
  Result := ShellExec('open', ExpandConstant('{sys}\regsvr32.exe'), Params, '',
                      SW_HIDE, ewWaitUntilTerminated, code) and (code = 0);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep <> ssPostInstall then
    Exit;
  CameraDll := ExpandConstant('{app}\_internal\native\softcam\bin\{#MyCamera}');
  if FileExists(CameraDll) then
  begin
    if RunRegsvr32('/s "' + CameraDll + '"') then
      Log('FaceCam Camera registered')
    else
      Log('FaceCam Camera registration failed; use the Register button in Settings');
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep <> usUninstall then
    Exit;
  { Read the registered path before files are removed. }
  if RegQueryStringValue(HKEY_CLASSES_ROOT,
       'CLSID\{B7E2A4C1-9D3F-4E6A-8B25-0C1D2E3F4A5B}\InprocServer32', '', CameraDll) then
    if FileExists(CameraDll) then
      RunRegsvr32('/s /u "' + CameraDll + '"');
end;
