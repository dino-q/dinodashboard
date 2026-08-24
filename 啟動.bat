@echo off
cd /d "%~dp0"
if not exist .venv (
  echo .venv not found. Run install.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
start "" http://localhost:5050
python app.py
pause
