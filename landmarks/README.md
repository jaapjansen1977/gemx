# SOMA-mesh met voorlopige landmarks

Eerste controleerbare plaatsingsproef op de bestaande **temporele Body Motion**
van 0–2 seconden: 60 beelden, SOMA MID (18.056 vertices, 36.108 driehoeken),
18 kandidaatpunten. Geen nieuwe video-inferentie of downloads nodig.

Bekijk [mesh-landmarks.mp4](results/mesh-landmarks.mp4) of
[het beeld op 1 seconde](results/frame-030.jpg).
De transparante mesh is uit de opgeslagen SOMA-pose én vorm gereconstrueerd.
De overlay schat geen nieuwe vorm uit pixels en is geen silhouette-fit.
Alle gele punten worden getoond, ook punten aan de achterzijde.
De CPU-renderer gebruikt driehoeken op dieptevolgorde; dat is een inspectiebeeld,
geen exacte rasterizer met pixelgewijze occlusietest.

## Wat de punten betekenen

Links/rechts: ASIS, PSIS, acromion, mediale/laterale elleboogepicondyl,
mediale/laterale knie-epicondyl en mediale/laterale malleolus.
Deze namen beschrijven **beoogde anatomische locaties**, geen gevalideerde
waarnemingen. Een eenvoudige neutrale-poseheuristiek zet beginpunten bij de
gewrichten. Het dichtstbijzijnde punt op het volledige meshoppervlak bepaalt
een vaste driehoek en drie barycentrische gewichten. Die blijven gedurende
de hele clip gelijk; de punten worden niet per beeld opnieuw gekozen.
Beginplaatsing, voor/achterrichting en de labels mediaal/lateraal moeten
anatomisch worden gecontroleerd. Vooral de ellebogen verdienen aandacht:
een afstand tot een gewricht plus oppervlaktereconstructie bepaalt nog geen
correcte epicondyl. Kleding en de monoculaire videoschatting beperken controle.
Er is geen ISB-conformiteit of anatomische nauwkeurigheid aangetoond.

`model-anchors.json` bevat onafhankelijke, voorlopige tegenpunten op het
standaard MyoFullBody. Dit zijn vaste botlokale offsets van heuristische
beginpunten, **geen** projecties op een huidmesh. De laterale malleolus hoort
anatomisch bij de fibula; dit model heeft geen afzonderlijk fibula-body, dus
de rigide tibia/fibula-groep wordt door het body `tibia_l/r` vertegenwoordigd.
Er zijn geen modelbestanden gewijzigd en de oorspronkelijke fit blijft behouden.

Alle punten hebben `fit_weight: 0`. Ze zijn nog niet toegevoegd aan de
optimalisatiedoelfunctie. De ruwe afstand tussen kandidaatparen is gemiddeld
ongeveer 8,3 cm, maximaal 18,4 cm: een diagnostiek van deze voorlopige
correspondenties, lichaamsvormen en bestaande houding samen, geen foutmeting
van anatomie. Optimaliseren op deze ongecontroleerde punten zou een
misleidend gunstige afstand kunnen geven.

## Bestanden en conventies

- `attachments.json`: MID-driehoekindices (nulgebaseerd), barycentrische
  gewichten in vertexvolgorde van `faces[face_id]`, kandidaatstatus en nulgewicht.
- `surface.npz`: de 60 cameraruimte-meshes, referentiemesh, topologie,
  puntposities in camera-, GEM-wereld- en MuJoCo-ruimte, tijden en intrinsics.
  Geen pickle nodig (`allow_pickle=False`).
- `model-anchors.json` en `.npz`: botnamen, botlokale posities en globale
  tegenpunten op de **bestaande** MyoFullBody-fit.
- `landmarks.csv`: namen, beeldindex, cliptijd, coördinatenruimte, xyz in meters
  en kandidaatstatus; elke ruimte heeft een afzonderlijke rij.
- `report.json`, `validation.json`: tijd/geheugen, bronhashes en technische checks.

Posities in meters, cliptijden in seconden. Camera: rechtsdraaiend,
X rechts / Y omlaag / Z vooruit. GEM-wereld: oorspronkelijke Y-up-rollout.
MuJoCo: exact dezelfde rotatie `[[1,0,0],[0,0,-1],[0,1,0]]` en constante
weergaveverplaatsing als `mujoco_demo/data/motion.npz`; geen nieuwe vloerfit.
De wereldpunten worden apart uit de opgeslagen wereldparameters gereconstrueerd,
niet via een aangenomen vaste cameratransformatie.

De oorspronkelijke grove SOMA-uitvoer gebruikte feitelijk XLO ondanks de MID-
vermelding in de oude FK-beschrijving. MID versus die export verschilt maximaal
circa 1,02 mm in een gewrichtscoördinaat. MID-mesh en MID-FK zijn onderling exact
gelijk. Dit verschil is vastgelegd; de oude uitvoer is niet aangepast.
De opgeslagen vormparameters mogen per beeld verschillen en worden ongewijzigd
gebruikt. Een vaste driehoek is dus nog geen over de clip gekalibreerd lichaam.

## Reproduceren

Gebruik de geïnstalleerde CPU-GEM/SOMA-omgeving van `probe` voor bouwen/renderen;
gebruik de aparte MuJoCo 3.4-omgeving van `myo_fit` voor modeltegenpunten.
Voer uit vanaf de repositoryroot. De paden hieronder zijn voorbeelden.
Laad alleen je eigen vertrouwde `raw_motion.pt`: PyTorch-pickle kan code uitvoeren.

```bash
python -m landmarks.build --results reports/jaap-cpu-pilot-01 \
  --assets ../gemx-upstream/assets/soma --output outputs/landmark-review
python -m landmarks.render --surface outputs/landmark-review \
  --video ../gemx-inputs/jaap-pilot-2s.mp4 --output outputs/landmark-review
# Wissel naar de bestaande myo_fit Python-omgeving:
python -m landmarks.model_anchors --surface outputs/landmark-review
python -m landmarks.validate outputs/landmark-review
python -m unittest landmarks.test_geometry
```

FFmpeg en OpenCV zijn nodig voor de overlay; er wordt geen binary gebundeld.
`build` registreert piek-RSS via Linux `resource`; dit is momenteel een
Linux-onderzoeksrunner, geen geteste Windows-app. Geheugen is proces-RSS,
geen meting van de complete procesboom. De tijd sluit Python-importtijd uit
en omvat geen render/modeltegenpunten. Alleen CPU-uitvoering is gebruikt;
Warp kan bij initialisatie melden dat geen CUDA-driver beschikbaar is.

Na inhoudelijke controle kunnen `face_id` en `barycentric` in een kopie van
`attachments.json` worden gecorrigeerd en met `--attachments bestand.json`
aan `build` worden meegegeven. Dezelfde MID-topologie en naamvolgorde zijn vereist.
Het wijzigen van een status of gewicht activeert op zichzelf geen fit.
Daarna volgen een gecontroleerde markerdoelfunctie naast de segmentrotaties,
persoonskalibratie en onafhankelijke validatie over meer lichamen.

## Versies en rechten

GEM-X `20555befe2fbbe5b2015e1fff7ff214dc18ea9d6`, SOMA-modelrevisie
`d281db2d01553f7230c56e764cec00fe27ef23f7`, py-soma-x 0.3.3,
MyoSim `93b0ca8f4ec90c9899ee7f05fee561e9911da91b`.
Broncode/modelbestanden en hun oorspronkelijke licenties blijven van toepassing.
De gegenereerde mesh is afgeleid van de SOMA-assets (Apache 2.0;
[meegeleverde licentie](SOMA_LICENSE)); geen modelgewichten worden gebundeld.
Zie ook [GEM-licentiecontrole](../probe/LICENSE-REVIEW.md) en
[MyoSim-licentie](../myo_fit/MYOSIM_LICENSE).
De video en lichaamsgeometrie zijn persoonlijke onderzoeksgegevens.
