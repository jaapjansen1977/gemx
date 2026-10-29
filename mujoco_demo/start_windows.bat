@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv-mujoco\Scripts\python.exe" (
    echo Voer eerst mujoco_demo\install_windows.bat uit.
    pause
    exit /b 1
)
".venv-mujoco\Scripts\python.exe" -m mujoco_demo play
if errorlevel 1 (
    echo Starten mislukt. Bewaar de foutmelding hierboven.
    pause
    exit /b 1
)
