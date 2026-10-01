@echo off
rem ================================================================
rem  start.bat - one-click installer: pz3d + ZombieBuddy for
rem  Project Zomboid Build 42. Just double-click this file.
rem  Tip: you can drag'n'drop the game folder onto start.bat.
rem ================================================================
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install.ps1" %*
set "RC=%ERRORLEVEL%"

if "%RC%"=="99" exit /b 0
if not "%RC%"=="0" (
  echo.
  echo  [start.bat] Something went wrong. Scroll up to read the error.
  pause
  exit /b %RC%
)

echo.
pause
exit /b 0
