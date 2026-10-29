# Code van de uitgevoerde CPU-proef

Dit is de Python-proef die de eerste 2 seconden van de aangeleverde video heeft
verwerkt. Er is nog geen Windows-interface of exe. De uitvoering is gevalideerd
op Linux, Python 3.12.14, met twee logische CPU's en PyTorch 2.10.0+cpu.

## Bestanden en herkomst

- `cpu_probe.py`: exact de uitgevoerde proefcode, inclusief ruwe Motion-opslag,
  SOMA-FK-export, timing, geheugenmeting en Python-netwerkblokkade.
  SHA256: `d4c1e02e9ed8c2594214c5517aa90509495b0fd2aedd99b53ef8c7b93513aed9`.
- `download_models.py`: gebruikte downloader, met vastgelegde officiële
  modelrevisies en controle van gepubliceerde LFS-SHA256s en bestandsgroottes.
  Deze cloudversie verwacht `/workspace/gemx` en `/workspace/gemx-upstream`.
- `render_overlay.py`: de gebruikte projectie-/tekenlogica van de overlay,
  omgezet van een eenmalig commando naar een script met padargumenten. Dit is
  geen byte-identieke kopie van dat eenmalige commando. Het gebruikt de reeds
  opgeslagen temporele voorspelling; het voert geen Pose-model uit.
- `requirements-linux-cpu.txt`: exacte geïnstalleerde Python-pakketversies,
  exclusief de afzonderlijke GEM-X-checkout. Geen universele Windows-lockfile.
- `manifests/`: gebruikte modelversies, checksums en herkomst van de proefcode.
- `LICENSE-REVIEW.md`: onderzochte licenties en resterende distributievragen.

De modelcode zelf komt ongewijzigd uit
[NVlabs/GEM-X, commit 20555befe2fbbe5b2015e1fff7ff214dc18ea9d6](https://github.com/NVlabs/GEM-X/tree/20555befe2fbbe5b2015e1fff7ff214dc18ea9d6).
Die broncode wordt niet als een nieuwe implementatie voorgesteld of hier
stilzwijgend geherlicentieerd. Modelgewichten zijn niet in deze repository opgenomen.

## Installatie: geteste cloudindeling

Gebruik een bestaande geïsoleerde checkout; maak geen Git-worktree tenzij dat
expliciet wordt gevraagd. De volgende indeling correspondeert met de proef:

```text
/workspace/gemx/                 deze repository
/workspace/gemx-upstream/        officiële GEM-X-code op bovengenoemde commit
/workspace/gemx-cpu-venv/        Python 3.12-omgeving
```

Voor een nieuwe installatie, vanuit `/workspace` (een bestaande checkout niet
overschrijven of resetten):

```bash
git clone https://github.com/NVlabs/GEM-X.git gemx-upstream
git -C gemx-upstream checkout 20555befe2fbbe5b2015e1fff7ff214dc18ea9d6
python3.12 -m venv /workspace/gemx-cpu-venv
/workspace/gemx-cpu-venv/bin/python -m pip install 'torch==2.10.0' --index-url https://download.pytorch.org/whl/cpu
/workspace/gemx-cpu-venv/bin/python -m pip install -r /workspace/gemx/probe/requirements-linux-cpu.txt
/workspace/gemx-cpu-venv/bin/python -m pip install --no-deps -e /workspace/gemx-upstream
```

FFmpeg moet op PATH staan, inclusief `ffprobe` en `libx264` voor de gebruikte
normalisatie/overlay. Bewaar de voorwaarden van de exact gebruikte FFmpeg-build
als je binaries wilt distribueren. Er is geen CUDA-PyTorch nodig; de proef weigert
CUDA-builds. SOMA/Warp kan melden dat geen CUDA-driver aanwezig is; in de proef
was uitsluitend het CPU-apparaat beschikbaar en gebruikt.

## Modellen eenmalig downloaden

Lees eerst de officiële licenties/modelkaarten; zie `LICENSE-REVIEW.md`.
Gebruik alleen de officiële bronnen en omzeil geen toegang of acceptatie.
Na installatie:

```bash
cd /workspace/gemx
/workspace/gemx-cpu-venv/bin/python probe/download_models.py
```

De gebruikte YOLOX-detector kwam afzonderlijk uit het officiële OpenMMLab-archief:

```bash
mkdir -p /workspace/gemx-upstream/weights
curl --fail --location \
  https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/yolox_x_8xb8-300e_humanart-a39d44ed.zip \
  --output /workspace/gemx-upstream/weights/yolox_humanart.zip
/workspace/gemx-cpu-venv/bin/python - <<'PY'
from pathlib import Path
from shutil import copyfileobj
from zipfile import ZipFile
import hashlib
root = Path('/workspace/gemx-upstream/weights')
with ZipFile(root / 'yolox_humanart.zip') as archive:
    assert archive.testzip() is None
    members = [n for n in archive.namelist() if n.endswith('/end2end.onnx')]
    assert len(members) == 1
    with archive.open(members[0]) as source, (root / 'yolox_humanart.onnx').open('wb') as target:
        copyfileobj(source, target)
digest = hashlib.sha256((root / 'yolox_humanart.onnx').read_bytes()).hexdigest()
assert digest == '8e9ea96a176bd48501eaaa77216e49ee30794d2f8ba80c7b9862beca4ea972da'
PY
```

Die laatste hash identificeert het daadwerkelijk gebruikte ONNX-bestand; dit is
geen apart door de uitgever gepubliceerde cryptografische handtekening.

## Proef opnieuw uitvoeren

De oorspronkelijke invoervideo is niet los in de repository gezet. Lever je eigen
lokale videopad aan. Elke uitvoering vereist een nieuwe uitvoermap. Deze proef
duurde ongeveer 12 minuten voor 2 seconden video; herhalen is kostbaar in tijd.

```bash
cd /workspace/gemx
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 XDG_CACHE_HOME=/workspace/.cache \
  /workspace/gemx-cpu-venv/bin/python -u probe/cpu_probe.py \
  --video '/pad/naar/jaap beweegt.mp4' \
  --config /workspace/gemx-upstream/weights/body_video_native77.yaml \
  --soma-assets /workspace/gemx-upstream/assets/soma \
  --output outputs/nieuwe-proef --duration 2 --threads 2 --offline-check
```

Er wordt `run_body_video` gebruikt, met native77 ViTPose-waarnemingen,
Body Pose-features, camerabeweging en het echte temporele Motion-checkpoint.
Geen framegewijze Body Pose-fallback. Optionele Contact/IK is niet uitgevoerd.
De runner stelt een schrijfbare Warp-cache in de uitvoermap in.

`--offline-check` weigert Python-socketverbindingen en schakelt ONNX-telemetrie
uit; dit is geen OS-brede netwerkisolatie van native libraries. De proef slaagde
met nul waargenomen Python-socketpogingen en lokale modelbestanden.

Uitvoer: `raw_motion.pt`, `kinematics.npz`, `kinematics.json`, `benchmark.json`.
De NPZ bevat camera-/wereldposities in meters, globale 3×3 segmentrotaties,
77 namen, tijdstippen in seconden en Root-inclusieve parent-IDs. De JSON beschrijft
de native assen en matrixconventie. Dit zijn geen MuJoCo-qpos of gekalibreerde
bewegingsmetingen. Laad alleen vertrouwde `.pt`-bestanden.

## Overlay uit opgeslagen resultaten

Voor de gebruikte portretvideo maak je eerst exact hetzelfde genormaliseerde
fragment. Dit vraagt geen modelinferentie:

```bash
/workspace/gemx-cpu-venv/bin/python - <<'PY'
from gem.inference.video import normalize_video
normalize_video('/pad/naar/jaap beweegt.mp4', 'outputs/jaap-pilot-2s.mp4', start=0, duration=2)
PY
/workspace/gemx-cpu-venv/bin/python probe/render_overlay.py \
  --results outputs/nieuwe-proef --normalized-video outputs/jaap-pilot-2s.mp4
```

Gebruik daarvoor een clip die exact met de opgeslagen uitvoer uitgelijnd is.
Het overlayscript is specifiek voor de gebruikte 1080×1920-portretclip.

## Validatie en beperkingen

De echte proef slaagde met 60 frames en 77 gewrichten: 730,34 s totale wandtijd,
4,44 GiB gesamplede procesboom-RSS. De FK-export is apart getest met echte SOMA-
assets en bekende rotatie/verplaatsing. 50 bestaande upstreamtests slaagden:

```bash
cd /workspace/gemx-upstream
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  /workspace/gemx-cpu-venv/bin/python -m pytest \
  tests/inference/test_motion.py tests/motion/test_api.py \
  tests/common/test_dinov3_pretrained.py tests/common/test_geometry.py -q
```

Deze tests vervangen geen nauwkeurigheidsmeting of Windows-validatie. De volledige
8,33 seconden video, Windows-uitvoering, GUI en exe zijn nog niet gerealiseerd.
De Linux-installatie is geen bewijs dat alle onderdelen op Windows werken.
