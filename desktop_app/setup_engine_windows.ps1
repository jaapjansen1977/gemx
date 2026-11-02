param(
    [string]$Destination = "$env:LOCALAPPDATA\GEMX\videomotor",
    [string]$PythonExecutable = '',
    [string]$FFmpegDirectory = '',
    [switch]$DownloadModels
)
$ErrorActionPreference = 'Stop'
$SourceRoot = Split-Path $PSScriptRoot -Parent
if (Test-Path "$PSScriptRoot/video_engine/doctor.py") { $SourceRoot = $PSScriptRoot }
if (-not (Test-Path "$SourceRoot/video_engine/doctor.py")) { throw 'Pak het volledige installatiepakket uit; de map video_engine ontbreekt.' }
$LogDirectory = "$env:LOCALAPPDATA\GEMX\setup-logs"
New-Item -ItemType Directory -Force $LogDirectory | Out-Null
$LogPath = Join-Path $LogDirectory ("install-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
Start-Transcript -Path $LogPath | Out-Null
function Invoke-BasePython {
    if ($PythonExecutable) { & $PythonExecutable @args } else { & py -3.12 @args }
    if ($LASTEXITCODE -ne 0) { throw "Python 3.12 command failed: $args" }
}
function Invoke-EnginePython {
    & $EnginePython @args
    if ($LASTEXITCODE -ne 0) { throw "Videomotorstap mislukt: $args. Log: $LogPath" }
}
try {
    if (-not $PythonExecutable -and -not (Get-Command py.exe -ErrorAction SilentlyContinue)) {
        throw 'Python 3.12 (64-bit) ontbreekt. Installeer de officiele Python van python.org en open daarna een nieuw PowerShell-venster.'
    }
    Invoke-BasePython -c "import sys,struct; assert sys.version_info[:2]==(3,12) and struct.calcsize('P')==8, 'Python 3.12 64-bit vereist'; print(sys.version)"
    if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) { throw 'Git ontbreekt. Installeer Git for Windows via git-scm.com en open een nieuw PowerShell-venster.' }
    if ($FFmpegDirectory) {
        $FFmpegDirectory = (Resolve-Path $FFmpegDirectory).Path
        $env:PATH = "$FFmpegDirectory;$env:PATH"
    }
    foreach ($Tool in @('ffmpeg.exe','ffprobe.exe')) {
        if (-not (Get-Command $Tool -ErrorAction SilentlyContinue)) {
            throw "$Tool ontbreekt. Installeer FFmpeg met ffprobe, of geef -FFmpegDirectory 'C:\pad\ffmpeg\bin' op. Zie video_engine/README.md."
        }
    }
    if (-not $FFmpegDirectory) { $FFmpegDirectory = Split-Path (Get-Command ffmpeg.exe).Source -Parent }
    $EnginePython = Join-Path $Destination 'Scripts\python.exe'
    if (Test-Path $Destination) {
        if (-not (Test-Path "$Destination/pyvenv.cfg")) { throw 'De doelmap bestaat maar is geen Python-omgeving. Kies een nieuwe -Destination; bestaande bestanden worden niet overschreven.' }
        & $EnginePython -c "import sys; assert sys.version_info[:2]==(3,12)"
        if ($LASTEXITCODE -ne 0) { throw 'De bestaande videomotor heeft geen Python 3.12. Kies een nieuwe doelmap.' }
    } else {
        Invoke-BasePython -m venv $Destination
    }
    $Destination = (Resolve-Path $Destination).Path
    $EnginePython = Join-Path $Destination 'Scripts\python.exe'
    if ($DownloadModels) {
        Invoke-BasePython -c "import shutil,sys; free=shutil.disk_usage(sys.argv[1]).free; print('Vrije ruimte: %.1f GB' % (free/1e9)); assert free>=20*1024**3, 'Voor volledige installatie minstens 20 GiB vrije ruimte beschikbaar maken'" $Destination
        Write-Host 'Modellen: circa 7,2 GB plus detector. Download is hervatbaar en wordt met SHA256 gecontroleerd.'
    }
    Write-Host 'CPU PyTorch installeren; geen CUDA-pakketten nodig.'
    Invoke-EnginePython -m pip install 'torch==2.10.0' --index-url https://download.pytorch.org/whl/cpu
    Invoke-EnginePython -m pip install -r "$SourceRoot/video_engine/requirements.txt"
    Invoke-EnginePython -m pip check
    $OldPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = $SourceRoot
    try {
        $Models = Join-Path $Destination 'models'
        $Report = Join-Path $Destination 'engine-check.json'
        if ($DownloadModels) {
            # Check native imports and codecs before spending time on 7+ GB of models.
            Invoke-EnginePython -m video_engine.doctor --root $Models --ffmpeg-bin $FFmpegDirectory --output $Report --dependencies-only
            Invoke-EnginePython -m video_engine.models --root $Models
            Invoke-EnginePython -m video_engine.doctor --root $Models --ffmpeg-bin $FFmpegDirectory --output $Report --register
            Write-Host 'Installatiecontrole geslaagd. Herstart de app: de videomotor wordt automatisch herkend.'
            Write-Host 'Nog nodig: een echte korte video verwerken op deze Windows-computer. Dat is geen onderdeel van alleen deze installatiecontrole.'
        } else {
            Invoke-EnginePython -m video_engine.doctor --root $Models --ffmpeg-bin $FFmpegDirectory --output $Report --dependencies-only
            Write-Host 'Pakketten gecontroleerd; modellen nog niet gecontroleerd of geregistreerd. Voer opnieuw uit met -DownloadModels voor eigen videoanalyse.'
        }
        Write-Host "Rapport: $Report"
    } finally { $env:PYTHONPATH = $OldPythonPath }
} finally {
    Write-Host "Installatielog: $LogPath"
    Stop-Transcript | Out-Null
}
