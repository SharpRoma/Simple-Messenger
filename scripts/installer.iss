[Setup]
; Уникальный ID приложения, чтобы Windows правильно его обновлял
AppId=SimpleMessenger
AppName=Simple Messenger

; Версия подтягивается из скрипта сборки
AppVersion={#AppVersion}
AppPublisher=Simple Messenger
DefaultDirName={autopf}\Simple Messenger
DefaultGroupName=Simple Messenger

SetupIconFile=..\client\assets\icon.ico
; OutputDir=..\dist

; Установщик будет с версией: SimpleMessenger_Setup_v1.1.0.exe
OutputBaseFilename=SimpleMessenger_Setup_v{#AppVersion}

Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "SimpleMessenger_Setup_*.exe"

[Icons]
Name: "{group}\Simple Messenger"; Filename: "{app}\SimpleMessenger.exe"
Name: "{commondesktop}\Simple Messenger"; Filename: "{app}\SimpleMessenger.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SimpleMessenger.exe"; Description: "{cm:LaunchProgram,Simple Messenger}"; Flags: nowait postinstall skipifsilent

[Code]
// Функция вызывается ДО появления первого окна установщика
function InitializeSetup(): Boolean;
var
  OldVersion: String;
begin
  Result := True;

  // Ищем в реестре Windows прошлую установленную версию
  if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\SimpleMessenger_is1', 'DisplayVersion', OldVersion) then
  begin
    // Сравниваем старую версию с той, которую пытаемся установить
    if CompareStr(OldVersion, '{#AppVersion}') > 0 then
    begin
      MsgBox('На вашем компьютере уже установлена более новая версия (' + OldVersion + ').' + #13#10 + 'Установка устаревшей версии (' + '{#AppVersion}' + ') отменена.', mbError, MB_OK);
      Result := False; // Прерываем установку
    end;
  end;
end;