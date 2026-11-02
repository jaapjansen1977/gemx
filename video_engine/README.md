# Eigen video voorbereiden op Windows

Deze installatie bereidt de echte **GEM-X-CPU-videomotor → MyoFullBody-modelfit**
voor. Na een geslaagde volledige controle herkennen de desktop- en browser-app
de motor automatisch. Er hoeven dan geen drie serverpaden meer te worden gezocht.

**Dit is nog geen bewijs dat een eigen Windows-video volledig verwerkt is.**
De installatiecontrole test pakketten, CPU-berekeningen, SOMA-geometrie,
modelcompilatie en codecs. Daarna volgt een echte korte videoproef op je pc.

## Installatiepakket downloaden

Bij [Windows video engine checks](https://github.com/jaapjansen1977/gemx/actions/workflows/video-engine.yml)
wordt het kleine artefact **GEMX-videomotor-setup** gemaakt, zonder modelgewichten
of binaries. Pak beide ZIP-lagen volledig uit. Open PowerShell in de uitgepakte
map `GEMX-videomotor` en gebruik daar:

```powershell
powershell -File setup_engine_windows.ps1 -DownloadModels
```

De vereisten hieronder blijven gelden. Dit pakket maakt installatie eenvoudiger;
een beschikbare ZIP is geen bewijs dat de afzonderlijke Windows-runtimecontrole
al is geslaagd. Je kunt ook vanuit de volledige repository werken; daarvoor staan
de commando's hieronder met het voorvoegsel `desktop_app\`.

## 1. Eenmalige voorbereiding

Gebruik je privécomputer met Windows 64-bit. Aanbevolen: 16 GB RAM, minimaal
20 GiB vrije schijfruimte voor modellen, pakketten, cache en resultaten. De
NVIDIA-modelbestanden zijn samen circa 7,2 GB, plus de personendetector.

Installeer als ze ontbreken:

- **Python 3.12, 64-bit**, via https://www.python.org/downloads/windows/.
  Controleer in een nieuw PowerShell-venster: `py -3.12 --version`.
- **Git for Windows**, via https://git-scm.com/downloads/win.
- **FFmpeg met ffprobe en libx264**. Met een beschikbare Windows Package Manager:
  `winget install --id Gyan.FFmpeg --exact`. Open daarna een nieuw PowerShell-
  venster en controleer `ffmpeg -version` en `ffprobe -version`.
  Een al uitgepakte eigen FFmpeg-build kan ook via `-FFmpegDirectory` worden gebruikt.

Gebruik een recente, volledig uitgepakte download van de repository. Open
PowerShell in de map met `desktop_app`, `video_engine` en `browser_app`.
De eerste installatie heeft internet nodig. De apps uploaden je video niet.

## 2. Installeren inclusief modellen

```powershell
powershell -File desktop_app\setup_engine_windows.ps1 -DownloadModels
```

Staat FFmpeg niet op PATH maar wel in een eigen map:

```powershell
powershell -File desktop_app\setup_engine_windows.ps1 -DownloadModels -FFmpegDirectory 'C:\ffmpeg\bin'
```

De standaarddoelmap is `%LOCALAPPDATA%\GEMX\videomotor`. Het script:

1. Controleert Python 3.12 (64-bit), Git en de codecs.
2. Maakt een aparte Python-omgeving of hergebruikt de bestaande passende omgeving.
3. Installeert CPU-only PyTorch en de vastgelegde GEM-X-, SOMA- en MyoSim-versies.
4. Downloadt de officiële vastgelegde NVIDIA-releases en detector. Onderbroken
   NVIDIA-downloads kunnen worden hervat; gereedstaande bestanden worden op
   SHA256 én grootte gecontroleerd.
5. Bewaart de originele release-YAML en maakt een afzonderlijke runtimeconfiguratie
   met Windows-bestandspaden. Netwerkarchitectuur en hoek-/fitdefinities veranderen niet.
6. Controleert de echte imports, Torch CPU-berekening, MyoFullBody-voorwaartse
   berekening, checksums, FFmpeg/ffprobe, libx264 en SOMA CPU-geometrie.
7. Registreert uitsluitend na slagen de lokale motor in `%LOCALAPPDATA%\GEMX\engine.json`.

Beveiligings-, TLS- en checksumcontroles worden niet uitgeschakeld. Bestaande
modelbestanden met een afwijkende checksum worden niet blind overschreven.
De modelvoorwaarden blijven gelden; zie [de bestaande bronnen en voorwaarden](../probe/LICENSE-REVIEW.md).
De detectorchecksum identificeert het eerder gebruikte ONNX-bestand en is geen
apart door de uitgever gepubliceerde handtekening. Een toegangs- of acceptatiefout
bij de officiële bron stopt de download; er wordt geen toegang omzeild.

Zonder `-DownloadModels` worden alleen pakketten en codecs gecontroleerd. Dat
registreert de motor nog niet als gereed voor eigen video. Dit is ook de eerste
Windows-CI-stap, zonder de meer-gigabyte modeldownloads.

## 3. Eerste echte proef

Herstart de **nieuwste appversie**. De browser kiest de geregistreerde motor
bij het starten; in de desktop-app worden lege motorvelden automatisch ingevuld.
Eerder handmatig opgeslagen desktopinstellingen blijven behouden.

- Kies een eigen video met één persoon goed in beeld.
- Selecteer eerst **2 seconden**, met een stilstaande beginhouding.
- Start de analyse en houd het voortgangslog zichtbaar. De eerdere Linux-CPU-
  proef duurde circa 12 minuten voor 2 s video; Windows kan anders presteren.
- Controleer na afloop het witte model, de modelcoördinaten, de download en het
  meetrapport met `source: mujoco_myofullbody_fit`.

De echte keten is video → temporele GEM-X-uitvoer → nieuwe MyoFullBody-fit →
modelcoördinaten en witte rendering. Zonder geslaagde fit wordt geen alternatief
als modelresultaat aangeboden. Deze stap is nodig voordat we kunnen zeggen dat
het op jouw Windows-computer van begin tot eind werkt.

## Problemen onderzoeken

Het volledige installatielog staat onder `%LOCALAPPDATA%\GEMX\setup-logs`.
Het controleverslag staat in de motor-map als `engine-check.json`. Die bestanden
kunnen worden gedeeld om fouten te onderzoeken; deel geen sleutels of wachtwoorden.

Opnieuw alleen controleren kan vanuit de repositorymap:

```powershell
& "$env:LOCALAPPDATA\GEMX\videomotor\Scripts\python.exe" -m video_engine.doctor `
  --root "$env:LOCALAPPDATA\GEMX\videomotor\models" `
  --output "$env:LOCALAPPDATA\GEMX\videomotor\engine-check.json" --register
```

Gebruik zo nodig ook `--ffmpeg-bin 'C:\ffmpeg\bin'`. Een eigen Python-pad voor
het maken van de omgeving kan met `-PythonExecutable` aan het installatiescript
worden doorgegeven. Het script verandert de globale Python- of PATH-instellingen
niet. Onderbreek grote downloads bij voorkeur niet, maar opnieuw uitvoeren is
ondersteund; reeds gecontroleerde bestanden worden hergebruikt.

## Wat is hier getest?

De kritieke native Windows-wheels voor Python 3.12 zijn beschikbaar: SOMA,
ONNX Runtime, OpenCV, Warp, USD, Cholespy en Rtree. Dit bewijst beschikbaarheid,
niet dat alle native libraries op jouw computer al laden.

De helpertests controleren hervatten, servers zonder Range-ondersteuning,
afwijzen van corrupte bestanden, behoud van bestaande bestanden, behoud van de
originele modelconfiguratie en uitsluitend registreren van complete profielen.
Een aparte [Windows-installatiecontrole](https://github.com/jaapjansen1977/gemx/actions/workflows/video-engine.yml)
installeert de CPU-stack en voert imports/model-/codeccontroles uit. De uitkomst
van die nieuwe workflow is nog niet bevestigd. Ook een groene dependency-run
bewijst nog geen modeldownload, SOMA-assettest of echte video-inferentie.
