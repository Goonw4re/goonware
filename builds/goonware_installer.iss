;
; Goonware Installer Script
; Created using Inno Setup
;

#define MyAppName "GOONWARE"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Goonw4re"
#define MyAppURL "https://goonw4re.github.io"
#define MyAppExe "assets\start.bat"
#define MyAppAssocName "Goonware Model File"
#define MyAppAssocExt ".gmodel"
#define MyAppAssocKey StringChange(MyAppAssocName, " ", "") + MyAppAssocExt

[Setup]
; Application information
AppId={{7D8AB7E1-0DD6-4E9B-8D63-A84D518A9E3F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Default installation directory and allow user to change it
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
ChangesAssociations=yes

; Output directory and file name
OutputDir=.\
OutputBaseFilename=GoonwareSetup_v{#MyAppVersion}

; Compression settings
Compression=lzma
SolidCompression=yes

; User interface settings
SetupIconFile=..\assets\icon.ico
WizardStyle=modern

; Other settings
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UsePreviousAppDir=yes
UsePreviousGroup=yes
UninstallDisplayIcon={app}\assets\icon.ico
UninstallDisplayName=Uninstall {#MyAppName}
AppendDefaultDirName=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "fileassoc"; Description: "Associate .gmodel files with Goonware"; GroupDescription: "File associations:"; Flags: checkedonce
Name: "installgoonconverter"; Description: "Install GoonConverter (ZIP to GMODEL converter)"; GroupDescription: "Additional components:"; Flags: unchecked

[Files]
; Main application files - Using parent directory as source
Source: "..\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "builds\*,venv\*,*.lnk,GoonConverter\*,*.git\*,models\*,assets\logs\*,assets\config.json,assets\first_run.flag,README.md,uninstall.bat,assets\instance.lock"
; Icon files
Source: "..\assets\icon.ico"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "..\assets\icon.png"; DestDir: "{app}\assets"; Flags: ignoreversion
; GoonConverter files (optional component)
Source: "..\GoonConverter\*"; DestDir: "{app}\GoonConverter"; Flags: ignoreversion recursesubdirs createallsubdirs; Tasks: installgoonconverter
; Create GoonConverter shortcut
Source: "..\GOON CONVERTER.lnk"; DestDir: "{app}"; Flags: ignoreversion; Tasks: installgoonconverter
; Create a shortcut in the installation root directory
Source: "..\assets\start.bat"; DestDir: "{app}\assets"; Flags: ignoreversion; AfterInstall: CreateStartShortcut

[Dirs]
; Create empty models directory
Name: "{app}\models"
; Create empty logs directory
Name: "{app}\assets\logs"
; Only create GoonConverter directory when task is selected
Name: "{app}\GoonConverter"; Tasks: installgoonconverter

[Registry]
; Register file associations
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocExt}"; ValueType: string; ValueName: ""; ValueData: "{#MyAppAssocKey}"; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}"; ValueType: string; ValueName: ""; ValueData: "{#MyAppAssocName}"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\assets\icon.ico"; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExe}"" ""%1"""; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExe}\SupportedTypes"; ValueType: string; ValueName: ".gmodel"; ValueData: ""; Tasks: fileassoc

[Icons]
; Create program menu shortcuts
Name: "{group}\{#MyAppName}"; Filename: "{app}\assets\start.bat"; IconFilename: "{app}\assets\icon.ico"
Name: "{group}\GoonConverter"; Filename: "{app}\GoonConverter\src\converter.py"; IconFilename: "{app}\assets\icon.ico"; Tasks: installgoonconverter
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
; Desktop icon (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\assets\start.bat"; IconFilename: "{app}\assets\icon.ico"; Tasks: desktopicon

[Run]
; Option to launch app after installation
Filename: "{app}\assets\start.bat"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
; Hide the uninstaller data files
Filename: "cmd.exe"; Parameters: "/c attrib +h ""{app}\unins000.dat"""; Flags: runhidden

[UninstallDelete]
Type: files; Name: "{app}\GOONWARE.lnk"
Type: filesandordirs; Name: "{app}\models\*"
Type: filesandordirs; Name: "{app}\venv\*"
Type: filesandordirs; Name: "{app}\assets\*"
Type: dirifempty; Name: "{app}\models"
Type: dirifempty; Name: "{app}\venv"
Type: dirifempty; Name: "{app}\assets"
Type: dirifempty; Name: "{app}"

[UninstallRun]
; Close the running application before uninstalling
Filename: "taskkill.exe"; Parameters: "/f /im python.exe"; Flags: runhidden
Filename: "taskkill.exe"; Parameters: "/f /im pythonw.exe"; Flags: runhidden
; Explicitly remove registry entries
Filename: "cmd.exe"; Parameters: "/c reg delete ""HKCU\Software\Classes\.gmodel"" /f"; Flags: runhidden
Filename: "cmd.exe"; Parameters: "/c reg delete ""HKCU\Software\Classes\GoonwareModel"" /f"; Flags: runhidden
Filename: "cmd.exe"; Parameters: "/c reg delete ""HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.gmodel"" /f"; Flags: runhidden
Filename: "cmd.exe"; Parameters: "/c reg delete ""HKLM\SOFTWARE\Classes\.gmodel"" /f"; Flags: runhidden; Check: IsAdminLoggedOn
; Refresh file associations
Filename: "cmd.exe"; Parameters: "/c ie4uinit.exe -show"; Flags: runhidden

[Code]
// Additional script code can be added here if needed

// Function to check if Python is installed
function IsPythonInstalled: Boolean;
var
  PythonInstalled: Boolean;
  ResultCode: Integer;
begin
  PythonInstalled := False;
  // Try to run Python to check if it's installed
  if Exec('python', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
      PythonInstalled := True;
  end;
  Result := PythonInstalled;
end;

// Create shortcut in the root directory
procedure CreateStartShortcut;
var
  ShortcutFile: String;
begin
  ShortcutFile := ExpandConstant('{app}\GOONWARE.lnk');
  if FileExists(ShortcutFile) = False then
    CreateShellLink(
      ShortcutFile,
      'GOONWARE Application',
      ExpandConstant('{app}\assets\start.bat'),
      '',
      ExpandConstant('{app}'),
      ExpandConstant('{app}\assets\icon.ico'),
      0,
      SW_SHOWNORMAL
    );
end;

// Function to close the application before uninstall
function InitializeUninstall: Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  try
    // Try to close the app gracefully first
    Exec('taskkill.exe', '/im pythonw.exe /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Exec('taskkill.exe', '/im python.exe /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  except
    // Ignore errors, we'll try again in the UninstallRun section
  end;
end;

// Initialize setup
function InitializeSetup: Boolean;
begin
  // Check if Python is installed
  if not IsPythonInstalled then
  begin
    MsgBox('Python is required but not detected on your system.' + #13#10 +
           'Please install Python 3.8 or later before installing Goonware.', mbInformation, MB_OK);
    Result := False;
  end
  else
    Result := True;
end; 