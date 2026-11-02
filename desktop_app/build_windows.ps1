$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function Invoke-Python {
    & python @args
    if ($LASTEXITCODE -ne 0) { throw "Python command failed: $args" }
}
Invoke-Python -m pip install -r desktop_app/requirements.txt 'pyinstaller==6.16.0'
Invoke-Python -m unittest myo_fit.test_export_results myo_fit.test_constraints -v
$EngineSource = 'build/desktop-engine-source'
New-Item -ItemType Directory -Force $EngineSource | Out-Null
foreach ($Package in @('desktop_app', 'probe', 'shoulder', 'mujoco_demo', 'myo_fit')) {
    New-Item -ItemType Directory -Force "$EngineSource/$Package" | Out-Null
    Get-ChildItem "$Package/*.py" | Copy-Item -Destination "$EngineSource/$Package/"
}
Copy-Item myo_fit/mapping.json "$EngineSource/myo_fit/"
Invoke-Python -m PyInstaller --noconfirm --clean --onedir --windowed --name GEMXDesktop `
    --paths . --collect-all myo_sim --copy-metadata myo-sim --collect-all mujoco --collect-all glfw --collect-all OpenGL --collect-all scipy --collect-all matplotlib `
    --hidden-import scipy.spatial.transform._rotation `
    --add-data 'mujoco_demo/data/motion.npz;mujoco_demo/data' `
    --add-data 'myo_fit/results/fit.npz;myo_fit/results' `
    --add-data 'myo_fit/results/report.json;myo_fit/results' `
    --add-data 'myo_fit/results/preview.mp4;myo_fit/results' `
    --add-data 'myo_fit/mapping.json;myo_fit' `
    --add-data 'build/desktop-engine-source;engine_source' `
    desktop_app/app.py
Copy-Item desktop_app/README.md dist/GEMXDesktop/LEESMIJ.md
Copy-Item desktop_app/setup_engine_windows.ps1 dist/GEMXDesktop/
Invoke-Python desktop_app/collect_notices.py dist/GEMXDesktop/THIRD_PARTY_LICENSES
Compress-Archive -Path dist/GEMXDesktop -DestinationPath dist/GEMXDesktop-Windows.zip -Force
