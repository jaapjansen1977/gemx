$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function Invoke-Python {
    & python @args
    if ($LASTEXITCODE -ne 0) { throw "Python command failed: $args" }
}
Invoke-Python -m pip install -r browser_app/requirements.txt 'pyinstaller==6.16.0'
Invoke-Python -m unittest browser_app.test_server myo_fit.test_export_results -v
$EngineSource = 'build/browser-engine-source'
New-Item -ItemType Directory -Force $EngineSource | Out-Null
foreach ($Package in @('desktop_app', 'probe', 'shoulder', 'mujoco_demo', 'myo_fit')) {
    New-Item -ItemType Directory -Force "$EngineSource/$Package" | Out-Null
    Get-ChildItem "$Package/*.py" | Copy-Item -Destination "$EngineSource/$Package/"
}
Copy-Item myo_fit/mapping.json "$EngineSource/myo_fit/"
Invoke-Python -m PyInstaller --noconfirm --clean --onedir --console --name GEMXBrowser `
    --paths . --collect-all myo_sim --copy-metadata myo-sim --collect-all mujoco --collect-all scipy --collect-all matplotlib --collect-all plotly `
    --collect-all glfw --collect-all OpenGL `
    --add-data 'browser_app/templates;browser_app/templates' `
    --add-data 'browser_app/static;browser_app/static' `
    --add-data 'mujoco_demo/data/motion.npz;mujoco_demo/data' `
    --add-data 'myo_fit/results/fit.npz;myo_fit/results' `
    --add-data 'myo_fit/results/report.json;myo_fit/results' `
    --add-data 'myo_fit/results/preview.mp4;myo_fit/results' `
    --add-data 'myo_fit/mapping.json;myo_fit' `
    --add-data 'build/browser-engine-source;engine_source' `
    browser_app/server.py
Copy-Item browser_app/README.md dist/GEMXBrowser/LEESMIJ.md
Copy-Item desktop_app/setup_engine_windows.ps1 dist/GEMXBrowser/
Copy-Item -Recurse video_engine dist/GEMXBrowser/video_engine
Invoke-Python desktop_app/collect_notices.py dist/GEMXBrowser/THIRD_PARTY_LICENSES
Compress-Archive -Path dist/GEMXBrowser -DestinationPath dist/GEMXBrowser-Windows.zip -Force
