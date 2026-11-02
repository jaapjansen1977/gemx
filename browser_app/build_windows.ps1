$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function Invoke-Python {
    & python @args
    if ($LASTEXITCODE -ne 0) { throw "Python command failed: $args" }
}
Invoke-Python -m pip install -r browser_app/requirements.txt 'pyinstaller==6.16.0'
Invoke-Python -m unittest browser_app.test_server desktop_app.test_analysis -v
$EngineSource = 'build/browser-engine-source'
New-Item -ItemType Directory -Force $EngineSource | Out-Null
foreach ($Package in @('desktop_app', 'probe', 'shoulder', 'mujoco_demo')) {
    New-Item -ItemType Directory -Force "$EngineSource/$Package" | Out-Null
    Get-ChildItem "$Package/*.py" | Copy-Item -Destination "$EngineSource/$Package/"
}
Invoke-Python -m PyInstaller --noconfirm --clean --onedir --console --name GEMXBrowser `
    --paths . --collect-all mujoco --collect-all scipy --collect-all matplotlib --collect-all plotly `
    --collect-all glfw --collect-all OpenGL `
    --add-data 'browser_app/templates;browser_app/templates' `
    --add-data 'browser_app/static;browser_app/static' `
    --add-data 'mujoco_demo/data/motion.npz;mujoco_demo/data' `
    --add-data 'shoulder/results/shoulder.npz;shoulder/results' `
    --add-data 'build/browser-engine-source;engine_source' `
    browser_app/server.py
Copy-Item browser_app/README.md dist/GEMXBrowser/LEESMIJ.md
Invoke-Python desktop_app/collect_notices.py dist/GEMXBrowser/THIRD_PARTY_LICENSES
Compress-Archive -Path dist/GEMXBrowser -DestinationPath dist/GEMXBrowser-Windows.zip -Force
