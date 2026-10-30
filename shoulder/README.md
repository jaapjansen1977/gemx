# Eerste humerothoracale schouderanalyse

[Controlevideo](results/shoulder-check.mp4) · [Grafieken](results/angles.png) ·
[CSV](results/angles.csv) · [Kalibratie en uitslagen](results/report.json)

Dit is een **voorlopige analyse met anatomische benaderingsassen**, geen
gevalideerde ISB-kalibratie. Beide bovenarmen worden ten opzichte van de
borstkas gemeten: humerothoracaal, niet glenohumeraal. De oorspronkelijke
temporele GEM-X Body Motion van de eerste twee seconden is hergebruikt.
Geen nieuwe video-inferentie, modeldownloads of wijziging van de MyoFullBody-fit.

## Kalibratiecontrole en beperkingen

Voor een anatomisch onderbouwde borstkasdefinitie ontbreken gecontroleerde
IJ-, C7-, PX- en T8-landmarks. De huidige heuristische elleboogepicondylen zijn
evenmin bruikbaar als gevalideerde bovenarmkalibratie: hun oorspronkelijke
laterale offsets lopen in de neutrale SOMA-T-pose vrijwel langs de bovenarm,
in plaats van dwars erop. Deze punten zijn daarom **niet** gebruikt om een
betrouwbare epicondylaire as te claimen.

De analyse maakt de aannames expliciet:

- Neutrale SOMA-geometrie met de opgeslagen vorm van beeld 0, zonder pose,
  globale rotatie of translatie. Dit is een modelreferentie, geen gemeten
  persoonlijke kalibratiehouding. De eerste videohouding wordt niet op nul gezet.
- Borstkas-Y: Hips naar Chest. Z: richting van rechterheup ten opzichte van
  linkerheup, georthogonaliseerd. X = Y kruis Z, met tekencontrole via de
  richting Head naar het gemiddelde van de ogen. Dit zijn geometrische proxies,
  geen vervanging van de vier ISB-borstkaslandmarks.
- Bovenarm-Y: van elleboogcentrumproxy (`ForeArm`) naar schoudercentrumproxy
  (`Arm`). X: de neutrale borstkasvoorwaartse richting loodrecht op die Y-as.
  Z = X kruis Y. Daardoor is de axiale nulstand **aangenomen**, niet gemeten
  met epicondylen of een functionele kalibratie.
- Deze frames worden met een vaste lokale rotatie aan `Chest` en `Arm`
  gekoppeld. De volledige opgeslagen segmentrotaties sturen de beweging;
  er worden geen hoeken per beeld uit nieuwe huidmarkers geschat.

De dynamische bovenarm-Y ligt binnen 0,04° van de schouder-ellebooglijn.
Dat controleert de technische koppeling, **niet** de anatomische juistheid.
De fijne MID-referentie en de eerdere XLO-rotatie-export blijven als afzonderlijke
bronnen benoemd; numerieke rotaties worden naar SO(3) geprojecteerd.

## Rotatieconventie

Bronconventie: Wu et al. (2005), *ISB recommendation on definitions of joint
coordinate systems … Part II*, Journal of Biomechanics 38, 981–992,
[doi:10.1016/j.jbiomech.2004.05.042](https://doi.org/10.1016/j.jbiomech.2004.05.042).
De Y–X–Y-ontbinding volgt die schouderbenadering; de benodigde anatomische
landmarkkalibratie is hier nog niet aangetoond. Daarom noemen we dit
**ISB-style** en niet een voltooide ISB-meting.

Actieve rotatiematrices met kolomvectoren: X anterior, Y superior, Z rechts.
`R_relative = R_thorax.T @ R_humerus`.
De expliciete intrinsieke YXY-tak is:

```
R_template = Ry(elevatievlak) @ Rx(-elevatie) @ Ry(axiale_rotatie)
```

Rechts gebruikt dit template rechtstreeks. Links wordt gespiegeld met
`S @ R_left @ S`, `S = diag(1, 1, -1)`: dezelfde interpretatie voor beide kanten,
geen ongemarkeerde linkse native Eulerreeks. Elevatievlak 0° = coronale abductie,
+90° = voorwaartse flexie. Elevatie positief bij heffen. Axiale rotatie positief
voor interne rotatie in het rechtertemplate en de overeenkomstige linkerspiegeling.
Het CSV bevat hoekwaarden in graden en cliptijden in seconden.

Bij elevatie 0° en 180° zijn elevatievlak en axiale rotatie niet afzonderlijk
identificeerbaar. We kiezen hier een conservatieve **20°-uitsluitingsgrens**:
alleen tussen 20° en 160° en bij minder dan 5° asdiscrepantie krijgen die twee
hoeken een numerieke geldigheidsmarkering. Dat is een gekozen conditioneringstest,
geen statistische betrouwbaarheidsgrens of bewijs van anatomische nauwkeurigheid.
Alle elevaties blijven beschikbaar. Ruwe hoekkolommen buiten het bruikbare
interval zijn diagnostisch; gebruik voor analyse de geldigheidsmarkering en
de continue kolommen, die daar leeg zijn.

Continue hoeken worden per aaneengesloten bruikbaar interval ontward.
Er wordt niet over uitgesloten beelden heen geïnterpoleerd of ontward.
Het rapport toont ook gevoeligheid voor grenzen van 10°, 20° en 30°.

## Uitslagen van deze clip

| Maat | Links | Rechts |
| --- | ---: | ---: |
| Elevatie minimum–maximum, hele clip | 19,3–122,6° | 17,9–110,8° |
| Elevatie-uitslag, hele clip | 103,3° | 92,8° |
| Elevatievlak minimum–maximum, langste bruikbare interval | −16,0–28,8° | −42,0–44,5° |
| Elevatievlak-uitslag, dat interval | 44,8° | 86,6° |
| Axiale rotatie minimum–maximum, dat interval | −58,4–4,7° | −51,3–34,5° |
| Axiale uitslag, dat interval | 63,1° | 85,8° |
| Tijdvenster voor elevatievlak/axiale statistieken | 0,90–1,93 s | 1,10–1,97 s |

Dit zijn **bewegingsuitslagen binnen deze korte clip en de gekozen aannames**,
geen maximale persoonlijke of klinische ROM. De tijdvensters verschillen per
kant. De axiale waarden zijn extra onzeker door de aangenomen transversale as.
Een kleine numerieke reconstructiefout maakt die aanname niet correct.

## Visuele controle en exports

De controlevideo toont op de oorspronkelijke clip de borstkas- en bovenarmassen
(X rood, Y groen, Z blauw), actuele hoeken en een cursor in drie tijdgrafieken.
`T` = thorax, `L/R` = linker/rechter humerus. Bij uitgesloten standen staat
`UNSTABLE` in plaats van een ogenschijnlijk betrouwbare axiale/planehoek.
Begin-, midden- en eindbeelden zijn opgeslagen voor inspectie. Er is geen
afzonderlijk gevalideerde beeldannotatie of ground truth.

- `shoulder.npz`: vaste-frame-uitkomsten, relatieve rotatiematrices, hoeken,
  maskers, gewrichtspunten en cliptijden, leesbaar zonder pickle.
- `angles.csv`: alle 60 beelden × beide kanten, ruwe en continue hoeken,
  conditionering en de expliciete status `unvalidated_anatomical_proxy`.
- `report.json`: exacte lokale kalibratierotaties, aannames en uitslagen.
- `neutral.npz/json`: reproduceerbare neutrale geometrie en modelbestandhashes.
- `validation.json`: reconstructie van relatieve rotaties uit de drie hoeken,
  orthogonaliteit, geometrische elevatiecontrole en drempelgevoeligheid.
- `angles.png/svg`: zelfstandige grafieken. `provenance.json`: broncode- en
  uitvoerhashes en pakketversies.

## Reproduceren

Vanaf de repositoryroot; gebruik de bestaande CPU-GEM/SOMA-omgeving voor
kalibratie en video, SciPy/NumPy voor analyse en Matplotlib voor de grafieken.
Matplotlib importeert geen GEM/MuJoCo; de aparte onderzoeksomgevingen mogen
behouden blijven. Alleen vertrouwde eigen `.pt`-uitvoer laden.

```bash
python -m shoulder.calibrate --raw reports/jaap-cpu-pilot-01/raw_motion.pt \
  --assets ../gemx-upstream/assets/soma --output outputs/neutral.npz
python -m shoulder.analyze --neutral outputs/neutral.npz \
  --threshold-deg 20 --output outputs/shoulder-review
python -m shoulder.validate outputs/shoulder-review
python -m shoulder.plot outputs/shoulder-review
python -m shoulder.render --directory outputs/shoulder-review \
  --video ../gemx-inputs/jaap-pilot-2s.mp4
python -m unittest shoulder.test_angles
```

Geen CUDA of betaalde dienst gebruikt. Windows is niet getest. Voor de volgende
anatomische verbetering zijn controleerbare borstkaslandmarks en een onderbouwde
epicondylaire/ functionele bovenarmkalibratie nodig; meer decimalen lossen dit niet op.
Zie de [bestaande licentiecontrole](../probe/LICENSE-REVIEW.md) en
[SOMA-licentie](../landmarks/SOMA_LICENSE). Er zijn geen modelgewichten toegevoegd.
