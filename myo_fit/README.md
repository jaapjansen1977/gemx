# Eerste rotatiegestuurde MyoFullBody-fit

Deze onderzoeksproef past het ongewijzigde MyoFullBody-model aan de **opgeslagen
2-secondenclip** aan. De GEM-X-videoanalyse wordt niet herhaald.

[Bekijk de preview](results/preview.mp4): het MyoFullBody-botmodel met de
oorspronkelijke GEM-X-gewrichten als cyaan skelet eroverheen.

## Resultaat

- Alle 60 frames convergeerden; rekentijd 6,63 seconden op de Linux-cloud-CPU.
- Gemiddelde rotatieafwijking: **2,05°**, tegenover 15,22° voor een onveranderde
  referentiehouding. De kalibratie-/referentieframe 0 is uit deze gemiddelden weggelaten.
- Geen overschrijding van de beperkte scalar-gewrichten; alle **51 actieve
  gewrichtskoppelingen** zijn tot numerieke precisie voldaan. Er wordt apart
  gecontroleerd met MuJoCo's eigen equality-residuen.
- De schouder-/sleutelbeenkoppeling past minder goed: gemiddeld circa 8° voor
  de twee clavicula-mappings. Een laag totaalgetal betekent niet overal een goede fit.

Dit is overeenkomst met **referentie-uitgelijnde GEM-X-rotaties**, geen bewijs
van anatomische of klinische nauwkeurigheid. Vingers blijven in de referentiestand;
het gebruikte model heeft hier geen onafhankelijk beweegbare nek/hoofdgewrichten.
Er zijn geen ISB-landmarks, persoonskalibratie, spieractivaties of dynamische
contactsvoorwaarden opgelost.

## Methode en harde voorwaarden

Het model is vastgelegd op MyoHub/myo_sim commit
`93b0ca8f4ec90c9899ee7f05fee561e9911da91b`, versie-label 0.2.3, met MuJoCo 3.4.0.
De daadwerkelijke API op deze commit is `build_spec('myofullbody').compile()`;
de README van upstream noemt ook een niet aanwezige `build_model`-functie.
Het geladen model heeft 123 joints, `nq=129`, `nv=128` en 416 actuatoren.

`mapping.json` legt 20 voorlopige segmentkoppelingen vast. Wervelgroepen gebruiken
de oriëntatie van het genoemde distale representatieve bot; de overige wervels
volgen de originele modelkoppelingen. Dit is geen reeds gevalideerde ISB-mapping.

**Referentie-uitlijning:** frame 0 wordt gekoppeld aan een haalbare stock-model-
referentiehouding. De globale begin-yaw wordt uit links/rechts heupen bepaald.
Daarna krijgt elk segment één vaste lokale-frame-offset:
`target(t) = R_GEM(t) @ R_GEM(0).T @ R_Myo(reference)`.
Daarmee volgt de fit veranderingen vanaf die referentie. De absolute beginhouding
is dus een aanname, niet teruggevonden anatomische kalibratie. Frame 0 heeft
hierdoor per definitie vrijwel nul rotatiefout en telt niet als onafhankelijk bewijs.
De invoer is de bestaande Z-up-export van de skeletdemo, inclusief haar vaste
display-hoogteverschuiving; geen tweede assenomzetting.

Er worden 31 onafhankelijke romp-/arm-/beencoördinaten en drie rootrotatie-
parameters geoptimaliseerd. Roottranslatie volgt de geëxporteerde heuppositie.
Veertig onafhankelijke vingercoördinaten blijven op de haalbare referentiewaarde.
Het doel is geodetische segmentrotatiefout plus zwakke temporele/referentiepriors.
Gewrichtsposities worden niet als doel geoptimaliseerd.

De afhankelijke coördinaten worden **exact geëlimineerd** via de originele
polynoomkoppelingen. Grenzen van alle afhankelijke én onafhankelijke gewrichten
worden doorgegeven aan hun onafhankelijke broncoördinaat. De optimizer krijgt
alleen haalbare verbonden intervallen; er worden geen modelgrenzen verruimd.
De onafhankelijke hoekgrenzen alleen zijn niet voldoende. Zo beperken de
gezamenlijke modelvoorwaarden hier beide kniehoeken tot ongeveer **1,09–42,07°**,
hoewel de primaire kniecoördinaat afzonderlijk 0–120° vermeldt. Dit is een
eigenschap van de combinatie van gepubliceerde modelvoorwaarden, geen vastgestelde
anatomische beperking van jouw knie. De gekozen intervallen staan in `report.json`.

Tijdens afspelen worden opgeslagen frames getoond. Vrije lineaire interpolatie
van alle `qpos` zou de polynoomkoppelingen tussen frames kunnen schenden.

## Installatie in een aparte omgeving

Behoud de bestaande skeletdemo-omgeving met MuJoCo 3.3.7. Deze proef vereist 3.4.0.
Onderstaande installatie vereist internet en Git; daarna werken fit en afspelen
met lokale modelbestanden. Het officiële MyoSim-model valt onder Apache-2.0;
er is geen betaalde licentie of CUDA nodig. Geen MyoSim-assets worden hier geherlicentieerd.

Vanuit de repositorymap, op Windows met Python 3.12 (64-bit) en Git geïnstalleerd:

```powershell
py -3.12 -m venv .venv-fit
.\.venv-fit\Scripts\python.exe -m pip install -r myo_fit\requirements.txt
.\.venv-fit\Scripts\python.exe -m myo_fit.validate --fit myo_fit\results\fit.npz
.\.venv-fit\Scripts\python.exe -m myo_fit.view
```

Bediening: spatie pauzeert; pijlen stappen per frame; R herstart, S wisselt snelheid,
L schakelt herhalen. De interactieve Windows-viewer is nog niet op Windows getest.

De fit opnieuw uitvoeren (uitvoermap moet nieuw zijn):

```powershell
.\.venv-fit\Scripts\python.exe -m myo_fit.fit --output outputs\nieuwe-fit
.\.venv-fit\Scripts\python.exe -m myo_fit.validate --fit outputs\nieuwe-fit\fit.npz
.\.venv-fit\Scripts\python.exe -m myo_fit.view --fit outputs\nieuwe-fit\fit.npz
```

Op Linux dezelfde modules uitvoeren met de Python uit de aparte omgeving.
Voor een MP4-preview is daarnaast FFmpeg met libx264 nodig:

```bash
python -m myo_fit.view --fit myo_fit/results/fit.npz --render outputs/myo-fit.mp4
python -m unittest myo_fit.test_constraints -v
```

`fit.npz` bevat de complete `qpos`, tijdstippen, botposities, brongewrichten,
doelrotaties, segment-frame-offsets en rotatiefouten. `report.json` bevat per-frame
optimizerstatus, grenzen-/koppelingchecks, model- en pakketversies en invoerhashes.
`validation.json` controleert de opgeslagen uitkomst opnieuw met het originele
model. De gegeven fouten zijn geen afstand tot ground truth of medisch oordeel.

Een aanvullende positiecontrole staat in `results/position-diagnostics.json`.
Dat zijn ruwe verschillen tussen geselecteerde model-body-origins en GEM-X-
gewrichten; die punten zijn niet anatomisch gelijkgesteld. Ze zijn niet als
fitdoel gebruikt en vormen geen ISB-marker- of nauwkeurigheidsvalidatie.

De MyoSim-licentie is opgenomen in `MYOSIM_LICENSE`. Bron en onderzoekscitaten:
[MyoHub/myo_sim](https://github.com/MyoHub/myo_sim/tree/93b0ca8f4ec90c9899ee7f05fee561e9911da91b)
(MyoSuite; MuscleMimic). MuJoCo en SciPy behouden hun eigen pakketlicenties.
