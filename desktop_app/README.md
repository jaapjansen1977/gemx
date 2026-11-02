# Windows-app: resultaten uit de MuJoCo-modelfit

De app gebruikt de **witte MyoFullBody-modelfit** als bron voor grafieken en CSV.
De metingen komen rechtstreeks uit de opgeslagen MuJoCo-`qpos`. Er wordt geen
GEM-X-hoekberekening of extra nulstandcorrectie gebruikt voor deze resultaten.

## Download en starten

Open [de Windows desktop-build](https://github.com/jaapjansen1977/gemx/actions/workflows/windows-app.yml)
en gebruik een geslaagde build met de MyoFullBody-aanpassing. Eerdere EXE's
gebruiken nog de vorige gegevensbron. De nieuwe Windows-build is nog niet
vanuit de ontwikkelomgeving bevestigd.

Download het artefact **GEMXDesktop-Windows**, pak beide ZIP-lagen uit en open
`GEMXDesktop.exe`. Laat `_internal` naast de EXE staan. Begin met **Bestaande
proefclip**: de opgeslagen witte modelfit wordt opnieuw in MuJoCo gecontroleerd.
**MuJoCo openen** speelt dezelfde fit af in het witte model. **Hoekgrafiek** toont
een overzicht; **Resultatenmap** bevat alle 122 coördinaten en de ruwe `qpos`.
Voor interactief kiezen tussen coördinaten is er de
[browserinterface](../browser_app/README.md), met dezelfde gegevensbron.

## Welke waarden?

- `review/angles.csv`: alle 122 scalar-modelcoördinaten, in graden of meters.
- `review/qpos.csv`: alle 129 configuratiewaarden, inclusief roottranslatie en
  quaternion in oorspronkelijke MuJoCo-eenheden.
- `review/model-coordinates.npz`: exacte qpos, modelwaarden en opnieuw berekende
  body-posities/rotaties.
- `review/report.json`: bronhash, modelcommit, qpos-index, eenheid en rol per
  coördinaat; geen extra nulcorrectie.

De verdeling is 31 geoptimaliseerde, 51 door modelkoppelingen bepaalde en
40 vaste coördinaten. De laatste zijn geen onafhankelijk gemeten vingerbeweging.
De modelwaarden zijn niet automatisch anatomische ISB-hoeken. De bestaande
beginreferentie, kniegrenzen en overige beperkingen van de fit blijven gelden;
spierkrachten en voetcontact worden niet geoptimaliseerd.

## Eigen video

Kies de Python-omgeving van de videomotor, de officiële GEM-X-releaseconfiguratie
en de SOMA-assetsmap. De motor draait GEM-X, fit daarna MyoFullBody aan de
segmentrotaties en exporteert de **nieuwe modelfit**. Zonder geldige fit wordt
geen alternatief resultaat als modelfit aangeboden. De extra rendering vraagt
FFmpeg en ffprobe op PATH.

De motor vereist MuJoCo 3.4.0 en MyoSim op commit
`93b0ca8f4ec90c9899ee7f05fee561e9911da91b`. Het installatiescript
`setup_engine_windows.ps1` bereidt die dependencies voor, maar downloadt geen
GEM-X-/detectorgewichten. Daarvoor blijft [probe/README.md](../probe/README.md)
van toepassing. Nieuwe video-inferentie op Windows is nog niet end-to-end getest.
De eerdere CPU-proef duurde circa 12 minuten voor 2 s video; start kort.

## Python en bouwen

Met Python 3.12 en Git, vanuit de repositoryroot:

```powershell
python -m pip install -r desktop_app/requirements.txt
python -m desktop_app.app
python -m desktop_app.app --self-test outputs/nieuwe-model-desktop-test
python -m unittest myo_fit.test_export_results myo_fit.test_constraints -v
```

Op Windows maakt `powershell -File desktop_app/build_windows.ps1` de ZIP met EXE,
modelassets, ondersteunende bibliotheken en third-party notices. De bouwtests
controleren de echte modelfit; een Linux-test bewijst niet dat de Windows-EXE
al werkt. De oorspronkelijke losse MuJoCo-skeletdemo blijft als aparte
onderzoeksweergave bestaan en is niet de bron van de appmetingen.
