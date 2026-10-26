; ---------------------------------------------------------------------------
; Vizier installer (Inno Setup 6)
;
; Build the application first:
;   python -m PyInstaller --noconfirm --clean packaging\windows\Vizier.spec
; Then compile this script:
;   ISCC.exe /DMyAppVersion=1.0.0 packaging\windows\Vizier.iss
;
; The installer is per-user by default (no administrator prompt), installs
; into %LOCALAPPDATA%\Programs\Vizier, and can be changed to an all-users
; install from the elevation dialog.
; ---------------------------------------------------------------------------

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

#ifndef MyAppVersion4
  #define MyAppVersion4 "1.0.0.0"
#endif

#define MyAppName "Vizier"
#define MyAppPublisher "Vizier Project"
#define MyAppExeName "Vizier.exe"
#define MyAppId "{{8F1C6B42-7D3E-4A0B-9C55-2E7A51D9C4E1}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
VersionInfoVersion={#MyAppVersion4}
VersionInfoProductName={#MyAppName} (Royal Advisor)
VersionInfoDescription={#MyAppName} local AI agent installer
VersionInfoCompany={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\..\dist\installer
OutputBaseFilename=Vizier-Setup-{#MyAppVersion}-x64
SetupIconFile=..\..\assets\vizier.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
WizardStyle=modern
WizardImageFile=..\..\assets\wizard-large.bmp
WizardSmallImageFile=..\..\assets\wizard-small.bmp
WizardImageStretch=yes
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
CloseApplications=yes
RestartApplications=no
AllowNoIcons=yes
SetupLogging=yes
LicenseFile=..\..\LICENSE
DisableWelcomePage=no
AppComments=Vizier is a 100 percent local AI agent. No cloud, no telemetry.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\Vizier\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "..\..\RELEASE_NOTES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Vizier CLI"; Filename: "{app}\VizierCLI.exe"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Temporary files created by the updater/build process are safe to remove.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"

[Code]
const
  VizierDataDir = '{localappdata}\Vizier';

function InitializeSetup(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);
  if (Version.Major < 10) then
  begin
    MsgBox('Vizier requires Windows 10 or newer.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant(VizierDataDir);
    if DirExists(DataDir) then
    begin
      if SuppressibleMsgBox('Also delete your Vizier settings, sessions, and downloaded models?' + #13#10 + #13#10 +
                'This frees the data directory:' + #13#10 + DataDir + #13#10 + #13#10 +
                'Choose No to keep your data for a future reinstall.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
