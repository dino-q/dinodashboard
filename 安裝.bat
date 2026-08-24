@echo off
cd /d "%~dp0"
if not exist .venv (
  py -3.13 -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt
echo.
echo Install done.
pause
