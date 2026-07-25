@echo off
title JARVIS
cd /d "%~dp0"

rem Use the project venv if it exists, otherwise whatever python is on PATH.
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

rem Open the HUD in the default browser once the server has had time to boot.
start "" cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8765"

echo Starting JARVIS...
"%PY%" -m jarvis_hud

echo.
echo JARVIS stopped. Press any key to close.
pause >nul
