@echo off
rem Lance Thessalia (Windows) : double-cliquer. Le navigateur s'ouvre ; fermer cette fenêtre arrête Thessalia.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Thessalia n'est pas encore installe : double-cliquer d'abord sur installer.bat
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m thessalia app
if errorlevel 1 pause
