@echo off
rem Installation de Thessalia (Windows) : double-cliquer. Lance installer.ps1 sans changer la politique du PC.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer.ps1" %*
pause
