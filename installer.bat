@echo off
rem Installation de Thessalia (Windows) : double-cliquer. Lance installer.py avec le Python du PC.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 installer.py %*
) else (
  python installer.py %*
)
pause
