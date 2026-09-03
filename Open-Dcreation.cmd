@echo off
title Dcreation - Fast Start
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-Dcreation.ps1"
if errorlevel 1 (
  echo.
  echo Dcreation could not start. Keep this window open and share the error shown above.
  pause
)

