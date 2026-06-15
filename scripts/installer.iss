[Setup]
; Базовые настройки приложения
AppName=Simple Messenger
AppVersion=1.1.0
AppPublisher=Simple Messenger
DefaultDirName={autopf}\Simple Messenger
DefaultGroupName=Simple Messenger

; Иконка для самого установщика (Setup.exe)
SetupIconFile=..\client\assets\icon.ico

; Куда положить готовый установщик и как его назвать
OutputDir=..\dist
OutputBaseFilename=SimpleMessenger_Setup

; Сжатие (делает файл установщика минимального размера)
Compression=lzma2
SolidCompression=yes

; Права администратора (чтобы установить в Program Files)
PrivilegesRequired=admin

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Берем наш скомпилированный exe и кладем в папку установки
Source: "..\dist\SimpleMessenger.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Создаем ярлыки в меню Пуск и на Рабочем столе
Name: "{group}\Simple Messenger"; Filename: "{app}\SimpleMessenger.exe"
Name: "{commondesktop}\Simple Messenger"; Filename: "{app}\SimpleMessenger.exe"; Tasks: desktopicon

[Run]
; Предлагаем запустить мессенджер после завершения установки
Filename: "{app}\SimpleMessenger.exe"; Description: "{cm:LaunchProgram,Simple Messenger}"; Flags: nowait postinstall skipifsilent