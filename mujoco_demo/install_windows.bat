@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv-mujoco\Scripts\python.exe" (
    py -3.12 -m venv .venv-mujoco
    if errorlevel 1 (
        echo Installeer eerst Python 3.12 voor Windows via python.org.
        pause
        exit /b 1
    )
)
".venv-mujoco\Scripts\python.exe" -m pip install -r mujoco_demo\requirements.txt
if errorlevel 1 (
    echo Installatie mislukt. Bewaar de foutmelding hierboven.
    pause
    exit /b 1
)
".venv-mujoco\Scripts\python.exe" -m mujoco_demo validate
if errorlevel 1 (
    echo De demo-validatie is mislukt.
    pause
    exit /b 1
)
echo Installatie klaar. Open nu mujoco_demo\start_windows.bat.
pause
