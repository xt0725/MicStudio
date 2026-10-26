#define AppName "MicStudio"
#define AppVersion "0.2.0"
[Setup]
AppId={{D7791729-8ABD-4B7C-AE5A-31239A7DD22C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=WFCQ
DefaultDirName={localappdata}\Programs\MicStudio
DefaultGroupName=MicStudio
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=MicStudio-Setup-0.2.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\assets\micstudio.ico
WizardImageFile=..\assets\setup.png
WizardSmallImageFile=..\assets\setup-small.png
DisableWelcomePage=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardSizePercent=115
UninstallDisplayIcon={app}\MicStudio.exe
[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
[Tasks]
Name: "desktopicon"; Description: "Créer un raccourci sur le Bureau"; Flags: unchecked
[Files]
Source: "..\dist\MicStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\MicStudio"; Filename: "{app}\MicStudio.exe"
Name: "{autodesktop}\MicStudio"; Filename: "{app}\MicStudio.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\MicStudio.exe"; Description: "Ouvrir MicStudio"; Flags: nowait postinstall skipifsilent
[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel1.Caption := 'Bienvenue dans votre studio vocal';
  WizardForm.WelcomeLabel2.Caption := 'MicStudio installe votre studio vocal : mixeur 4 sources, écoute au casque, réduction neuronale RNNoise, égaliseur 8 bandes et traitement dynamique.' + #13#10 + #13#10 + 'Un câble audio virtuel externe est nécessaire pour envoyer le résultat dans Discord ou un jeu. Aucun pilote n''est installé par cet assistant.';
end;
