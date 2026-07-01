; Script de Inno Setup para "Grabador de Pantalla PRO".
;
; Genera un instalador (Setup.exe) que funciona en cualquier PC con Windows:
; copia el .exe (con FFmpeg ya incrustado) a Archivos de Programa, crea
; accesos directos en el Menú Inicio y (opcional) en el Escritorio, y
; registra un desinstalador estándar en "Aplicaciones y características".
;
; Compilar con:  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; (o hacer doble clic en build_installer.bat)

#define MyAppName "Grabador de Pantalla PRO"
#define MyAppVersion "1.0"
#define MyAppPublisher "PharmaJava"
#define MyAppURL "https://github.com/PharmaJava/AplicacionGrabarPantalla"
#define MyAppExeName "GrabadorPantallaPRO.exe"

[Setup]
AppId={{8F3B6C2E-4B9A-4E4E-9E9A-4D6C1B7A2F10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Instalador para cualquier usuario del equipo (pide permisos de administrador,
; comportamiento estándar de un "Setup" de Windows).
PrivilegesRequired=admin
OutputDir=installer_output
OutputBaseFilename=GrabadorPantallaPRO_Setup
SetupIconFile=icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
