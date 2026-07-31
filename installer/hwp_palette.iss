; ===== HwpPalette 설치 스크립트 (Inno Setup 6) =====
;
; 쓰는 법:  build_release.py 가 버전을 넣어 자동으로 부른다 —
;           ISCC.exe /DAppVersion=0.3.0 installer\hwp_palette.iss
; 손으로 빌드하면 AppVersion 이 0.0.0 으로 박히니 반드시 스크립트를 거칠 것.
;
; 설계 결정 (2026-07-31, 투 트랙 릴리즈):
;   · 사용자 폴더 설치(PrivilegesRequired=lowest) — 학교 PC 는 관리자 권한이
;     없는 경우가 많다. {userpf} = C:\Users\<이름>\AppData\Local\Programs.
;   · 데이터('내 물감' 폴더)는 exe 옆에 생기는 구조 그대로 둔다. 제거할 때도
;     지우지 않는다 — 프로그램을 지워도 팔레트·물감은 사용자의 것이다.
;   · 코드 서명이 없어 SmartScreen 경고는 남는다. "추가 정보 → 실행" 안내 필요.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; AppId 는 이 프로그램의 신분증 — 바꾸면 업데이트가 아니라 딴 프로그램 설치가 된다
AppId={{B7E3D3D8-4C1A-4E63-9D25-7A0C2E9A31B4}
AppName=HwpPalette
AppVersion={#AppVersion}
AppPublisher=박승연 | SOMC
DefaultDirName={userpf}\HwpPalette
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=HwpPalette-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\hwp_palette.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
; Korean.isl 은 Inno Setup 6 기본 설치에 들어 있다. 없다는 오류가 나면
; https://jrsoftware.org/files/istrans/ 에서 받아 Languages 폴더에 넣을 것.
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면 바로가기 만들기"; GroupDescription: "추가 작업:"

[Files]
Source: "..\dist\hwp_palette.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\HwpPalette"; Filename: "{app}\hwp_palette.exe"
Name: "{userdesktop}\HwpPalette"; Filename: "{app}\hwp_palette.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\hwp_palette.exe"; Description: "지금 실행"; Flags: nowait postinstall skipifsilent
