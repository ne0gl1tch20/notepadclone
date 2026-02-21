#define MyAppName "Notepad Clone"
#define MyAppPublisher "Notepad Clone"
#define MyAppExeName "run.exe"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif

[Setup]
AppId={{4E6E3EFA-6F45-4D8F-BF1E-7AFD4382202A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=NotepadClone-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible and x86compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "assoc_txt"; Description: "Associate .txt files with Notepad Clone"; GroupDescription: "File associations:"; Flags: unchecked
Name: "ctx_openwith"; Description: "Add 'Open with Notepad Clone' to file context menu"; GroupDescription: "File associations:"; Flags: unchecked

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Bundle example plugins so users get plugin templates immediately.
Source: "..\plugins\*"; DestDir: "{userappdata}\notepadclone\plugins"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__\*"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Registry]
; .txt association (optional)
Root: HKCU; Subkey: "Software\Classes\.txt"; ValueType: string; ValueName: ""; ValueData: "NotepadClone.txtfile"; Flags: uninsdeletevalue; Tasks: assoc_txt
Root: HKCU; Subkey: "Software\Classes\NotepadClone.txtfile"; ValueType: string; ValueName: ""; ValueData: "Text Document (Notepad Clone)"; Flags: uninsdeletekey; Tasks: assoc_txt
Root: HKCU; Subkey: "Software\Classes\NotepadClone.txtfile\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Flags: uninsdeletekey; Tasks: assoc_txt
Root: HKCU; Subkey: "Software\Classes\NotepadClone.txtfile\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: assoc_txt

; Context menu entry for all files (optional)
Root: HKCU; Subkey: "Software\Classes\*\shell\Open with Notepad Clone"; ValueType: string; ValueName: ""; ValueData: "Open with Notepad Clone"; Flags: uninsdeletekey; Tasks: ctx_openwith
Root: HKCU; Subkey: "Software\Classes\*\shell\Open with Notepad Clone"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\{#MyAppExeName},0"; Flags: uninsdeletekey; Tasks: ctx_openwith
Root: HKCU; Subkey: "Software\Classes\*\shell\Open with Notepad Clone\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey; Tasks: ctx_openwith
