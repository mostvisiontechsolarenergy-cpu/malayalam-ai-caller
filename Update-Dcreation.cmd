@echo off
title Dcreation - Update and Rebuild
cd /d "%~dp0"
echo Use this only after application dependencies or Docker configuration change.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Dcreation.ps1" -Rebuild
if errorlevel 1 (
  echo.
  echo Dcreation could not rebuild. Keep this window open and share the error shown above.
  pause
)

