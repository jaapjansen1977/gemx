param(
    [string]$Destination = "$env:LOCALAPPDATA\GEMX\videomotor"
)
$ErrorActionPreference = 'Stop'
# Sets up dependencies only. No weights, detector archives or codecs are redistributed/downloaded here.
& py -3.12 -m venv $Destination
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 (64-bit) is required for the video engine setup.' }
$EnginePython = Join-Path $Destination 'Scripts\python.exe'
& $EnginePython -m pip install 'torch==2.10.0' --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { throw 'CPU PyTorch installation failed.' }
& $EnginePython -m pip install 'gem[video] @ git+https://github.com/NVlabs/GEM-X.git@20555befe2fbbe5b2015e1fff7ff214dc18ea9d6' 'py-soma-x==0.3.3' 'onnxruntime==1.31.1' 'opencv-python-headless==4.14.0.94' 'mujoco==3.3.7' 'numpy==2.5.4' 'scipy==1.18.1' 'matplotlib==3.11.2' 'psutil==7.2.2'
if ($LASTEXITCODE -ne 0) { throw 'Video engine installation failed; preserve the error output for diagnosis.' }
& $EnginePython -c "import gem, torch, onnxruntime; from gem.inference.body_video import run_body_video; print('Video engine imports passed; weights and ffmpeg still required.')"
if ($LASTEXITCODE -ne 0) { throw 'Video engine import check failed.' }
Write-Host "Video engine Python: $EnginePython"
Write-Host 'Select this Python, your release YAML and your local SOMA assets in the app. FFmpeg and ffprobe must be on PATH.'
