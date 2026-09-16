@echo off
cd /d "%~dp0"
chcp 65001 >nul
title DinoDashboard儀表板
rem ^ Tab/window name. @TAB below is read by Server_Launcher only;
rem   this line covers double-clicking the bat directly.
if not exist .venv (
  echo .venv not found. Run install.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
start "" http://localhost:5050
python app.py
pause

REM ==== Server_Launcher metadata -- see system\Server_Launcher ====
REM @PORT=5050
REM @GROUP=core
REM @ORDER=20
REM @TAB=DinoDashboard儀表板
REM ==== end of metadata. The ASCII line above guards the CJK line: ====
REM ==== if cp950 parsing swallows that line break, only this line dies. ====
