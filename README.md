# GEM-X Body Motion → MuJoCo

Onderzoeksprototype voor het verwerken van video met de temporele GEM-X Body
Motion-pipeline en het afspelen van opgeslagen 3D-uitvoer als skelet in MuJoCo.

## Nu beschikbaar: skeletdemo van de proefclip

[Bekijk de MuJoCo-preview](mujoco_demo/preview.mp4) ·
[Volledige uitleg en bediening](mujoco_demo/README.md)

Op Windows:

1. Installeer Python 3.12 (64-bit) als die ontbreekt.
2. Download deze repository via **Code → Download ZIP** en pak alles uit.
3. Dubbelklik in `mujoco_demo` op **`install_windows.bat`** (eenmalig internet nodig).
4. Dubbelklik daarna op **`start_windows.bat`** om de clip offline af te spelen.

Spatie pauzeert, de pijltjestoetsen stappen door frames, R begint opnieuw,
S wisselt snelheid en L schakelt herhalen. De standaard MuJoCo-muisbediening
laat je draaien en zoomen.

Deze demo gebruikt de bestaande 2-secondenproef: 60 frames, 77 gewrichten.
Er is geen nieuwe GEM-X-analyse, PyTorch, CUDA of betaald abonnement nodig.
Het is kinematische weergave; fysische retargeting naar een mens-/robotmodel
is een volgende stap. Windows-startscripts zijn nog niet op Windows getest.
De MuJoCo-validatie en CPU-video-export zijn wel op Linux uitgevoerd.

## Eerdere proef

- [Eerste humerothoracale schouderanalyse](shoulder/README.md):
  [controlevideo](shoulder/results/shoulder-check.mp4), drie hoekverlopen en
  uitslagen voor beide kanten; anatomische kalibratie nog voorlopig.
- [SOMA-mesh met 18 voorlopige landmarks](landmarks/README.md):
  [video-overlay](landmarks/results/mesh-landmarks.mp4), coördinatenexport en
  voorlopige botlokale MyoFullBody-tegenpunten; anatomische controle nog nodig.
- [Eerste rotatiegestuurde MyoFullBody-fit](myo_fit/README.md): 60 frames,
  harde modelgrenzen en 51 koppelingen; [preview](myo_fit/results/preview.mp4).

- [Resultaten en downloads](RESULTATEN.md)
- [Exacte GEM-X-proefcode en installatie](probe/README.md)
- [Licentiecontrole](probe/LICENSE-REVIEW.md)

De videoanalyse van 2 seconden kostte 12 minuten 10 seconden en 4,44 GiB
gesamplede piek-RAM op de Linux-cloud-CPU. Dit is geen laptopbenchmark.
MuJoCo-afspelen gebruikt alleen de opgeslagen beweging en is veel lichter.

De repository bevat persoonlijke bewegingsdata en video: houd hem privé.
