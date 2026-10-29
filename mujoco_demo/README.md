# Afspelen van de GEM-X-proefclip in MuJoCo

Deze demo speelt de **eerste 2 seconden** van de eerdere proef af als een
3D-skelet: 60 frames op 30 Hz, 77 gewrichten en 76 verbindingen. De geconverteerde
bewegingsdata zijn meegeleverd. Je hoeft GEM-X, PyTorch of modelgewichten niet
te installeren en de video hoeft niet opnieuw geanalyseerd te worden.

## Starten op Windows

1. Installeer **Python 3.12 (64-bit) voor Windows** via [python.org](https://www.python.org/downloads/windows/) als die nog ontbreekt.
2. Download de repository via GitHub: **Code → Download ZIP**, en pak het ZIP-bestand helemaal uit. Werk je al met Git, haal dan de nieuwste versie op.
3. Open de map `mujoco_demo` en dubbelklik **`install_windows.bat`**. Dit maakt een afzonderlijke Python-omgeving en installeert MuJoCo en de vereiste pakketten. Alleen deze eerste installatie heeft internet nodig.
4. Dubbelklik daarna **`start_windows.bat`**. Het skelet wordt in een draaibaar MuJoCo-venster afgespeeld.

MuJoCo gebruikt OpenGL voor het venster. Intel Iris Xe kan hiervoor dienen; er
is geen CUDA of NVIDIA-GPU nodig. De Windows-startscripts zijn meegeleverd maar
niet op een Windows-machine getest. Bij een fout blijft het venster met de
foutmelding open. Er is nog geen exe.

Je kunt dezelfde stappen ook in PowerShell uitvoeren, vanuit de repositorymap:

```powershell
py -3.12 -m venv .venv-mujoco
.\.venv-mujoco\Scripts\python.exe -m pip install -r mujoco_demo\requirements.txt
.\.venv-mujoco\Scripts\python.exe -m mujoco_demo validate
.\.venv-mujoco\Scripts\python.exe -m mujoco_demo play
```

## Bediening

| Toets | Actie |
| --- | --- |
| Spatie | Pauzeren / verder afspelen |
| Pijl links / rechts | Eén opgeslagen frame terug / vooruit; pauzeert |
| R | Terug naar begin |
| S | Snelheid wisselen: 0,25×, 0,5×, 1×, 2× |
| L | Herhalen aan / uit |

Draai en zoom met de standaard MuJoCo-muisbediening. Sluit het venster om te
stoppen. De console toont tijd, pauzestatus, snelheid en herhaalstatus na een
toetsaanslag. Blauw betekent de anatomische linkerkant volgens GEM-X; oranje
de rechterkant. Via **geom group 3** in de MuJoCo-viewer kun je de lokale
segmentassen zichtbaar maken: rood X, groen Y, blauw Z.

De korte clip herhaalt standaard. Omdat de eindhouding niet gelijk is aan de
beginhouding, kan de sprong bij herhalen zichtbaar zijn. Binnen de clip gebruiken
posities lineaire interpolatie en rotaties quaternion-SLERP.

## Wat deze demo doet

Dit is **kinematische weergave**, nog geen fysisch gesimuleerd mensmodel of
robot. De gewrichten zijn MuJoCo-`mocap`-bodies. Hun posities en oriëntaties worden
rechtstreeks uit de opgeslagen GEM-X-uitvoer ingesteld; capsulevormen verbinden
de gewrichten. Er zijn geen vrijheidsgraden (`nq = nv = 0`), actuatoren,
zwaartekrachtintegratie, contactsimulatie of IK-retargeting. Botlengtes worden
visueel gevolgd zoals ze in de voorspelling beschikbaar zijn.

De oorspronkelijke metingen blijven in hun eigen exportbestand ongewijzigd.
De demo past een rechtshandige wereldassenomzetting toe:

```text
GEM-X: Y omhoog             MuJoCo: Z omhoog
(x, y, z)                  (x, -z, y)

C = [ 1  0  0 ]
    [ 0  0 -1 ]
    [ 0  1  0 ]

p_mujoco = C @ p_native + vaste_display_verschuiving
R_mujoco = C @ R_native
```

De SOMA-segmentlokale assen worden behouden; alleen de wereldbasis verandert.
Daarom wordt de rotatie niet als `C @ R @ C.T` berekend. Quaternions gebruiken
MuJoCo-volgorde **w, x, y, z**. Eén vaste hoogteverschuiving voor de hele clip
plaatst het laagste gewricht 2,5 cm boven de getekende vloer. Dit is een
displaykeuze, geen voetcontactcorrectie. De waarde staat in `data/metadata.json`.
Er wordt geen absolute wereldrichting of gekalibreerde lichaamsmaat afgeleid.

## Bestanden

- `data/motion.npz`: geconverteerde posities, rotaties, quaternions, namen,
  parent-indices, clip-/brontijdstippen, conversiematrix en displayverschuiving.
- `data/skeleton.xml`: MuJoCo-model in de eerste houding. Het XML-bestand alleen
  toont een stilstaand skelet; het Python-programma verzorgt de animatie.
- `data/metadata.json`: bron-SHA256, eenheden, conversie en validatie-uitkomst.
- `data/validation.json`: MuJoCo-validatie van alle 60 frames.
- `preview.mp4`: gerenderd voorbeeld van de volledige proefclip.
- `skeleton.py`: conversie, interpolatie en MuJoCo-model.
- `__main__.py`: voorbereiden, controleren, afspelen en video-export.

## Andere export omzetten

Vanuit de repositorymap, met de demo-omgeving actief:

```bash
python -m mujoco_demo prepare --input /pad/naar/kinematics.npz --output-dir outputs/andere-demo
python -m mujoco_demo play --motion outputs/andere-demo/motion.npz
```

De invoer moet dezelfde GEM-X-exportstructuur hebben als de eerdere proef:
één persoon, globale meterposities en segmentrotaties, namen, Root-inclusieve
parent-IDs en oplopende tijdstippen. Gebruik de globale uitvoer, niet cameraruimte.
`prepare` controleert de geometrie in MuJoCo en schrijft de geconverteerde data.

## Validatie en video-export

```bash
python -m unittest mujoco_demo.test_demo -v
python -m mujoco_demo validate
python -m mujoco_demo render --output outputs/mujoco-skeleton.mp4
```

Video-export vraagt apart **FFmpeg met libx264 op PATH**. Dat is niet nodig voor
het afspeelvenster. Op headless Linux kiest de demo EGL; deze cloudproef gebruikte
Mesa **llvmpipe**, dus software-rendering op CPU. Zowel de 60-framevalidatie als
de echte MuJoCo-video-export slaagden. De vijf regressietests controleren onder
meer assen, parent-mapping, capsule-uitlijning, SLERP en de afspeelbediening.

Maximale positieafwijking ten opzichte van de geconverteerde data: 0 m;
rotatiematrixafwijking circa 2,1×10⁻⁶ door afronding. Dat controleert de omzetting,
niet de nauwkeurigheid van GEM-X ten opzichte van de echte beweging.

## Licenties en privacy

MuJoCo is beschikbaar onder Apache-2.0 en vereist geen betaalde MuJoCo-licentie.
De installatie downloadt de officiële Pythonpakketten; hun eigen licenties en
notices blijven gelden. Zie `THIRD_PARTY_NOTICES.md`. Er worden geen GEM-X-
modelgewichten of MuJoCo-binaries in deze repository meegeleverd. Deze demo
verandert niets aan de eerder vastgelegde rechtenvragen rond modeldistributie.
De bewegingsdata en preview komen uit je eigen video; houd de repository privé.
