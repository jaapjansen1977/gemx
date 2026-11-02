# GEM-X Bewegingslab — lokale browserinterface

Een browserinterface voor de bestaande experimentele schouderanalyse. Draait op
je privécomputer; Chrome of Edge toont de bediening, 3D-beweging en grafieken.
Er is geen hosting nodig en er worden door deze app geen beelden naar een
externe server geüpload. Deze versie is **nog niet als website via internet
beschikbaar**. Gebruik vanaf een andere computer vraagt een afzonderlijke,
afgeschermde hostingoplossing.

![Browserinterface na een echte proefclip-analyse](preview.png)

## Windows: starten zonder aparte Python-installatie

Open [de Windows-browserbuild op GitHub Actions](https://github.com/jaapjansen1977/gemx/actions/workflows/browser-app.yml).
Na een geslaagde run staat onder **Artifacts** de download `GEMXBrowser-Windows`.
De uitkomst van deze nieuwe Windows-build is nog niet vanuit de ontwikkelomgeving
bevestigd. De eerdere desktopbuild is een andere workflow.

1. Download het artefact en pak beide ZIP-lagen volledig uit.
2. Open `GEMXBrowser/GEMXBrowser.exe`. Laat `_internal` naast de EXE staan.
3. Er opent een browservenster. Laat het servervenster open tijdens gebruik.
4. Kies **Proefclip → Analyse starten** om meteen te testen.
5. Sluit de lokale server na gebruik met Ctrl+C in het servervenster.

De standaard lokale adresregel is `http://127.0.0.1:8765`. Dit adres werkt alleen
op de computer waarop het programma draait. Het is geen online website en geen
link die vanaf een werkcomputer naar je privécomputer leidt.

De browser-EXE wordt opnieuw op Windows gebouwd en getest: template en scripts,
echte analyse van de 60 proefclipframes, MuJoCo-validatie en een download via de
server-API. Een werkende Linux-test bewijst geen geslaagde Windows-EXE.

## Met bestaande Python starten

Vanuit de uitgepakte repositorymap, met Python 3.12:

```powershell
py -3.12 -m venv .venv-browser
.\.venv-browser\Scripts\python.exe -m pip install -r browser_app\requirements.txt
.\.venv-browser\Scripts\python.exe -m browser_app.server --open-browser
```

Op Linux kan dezelfde module worden gestart met de Python uit de bestaande
omgeving. De eerste installatie heeft internet nodig voor officiële pakketten.
Daarna werkt de proefclip zonder modeldownloads of externe scripts/fonts/CDN.

## Wat werkt

- Proefclip van 60 frames en 77 gewrichten analyseren.
- Achtergrondanalyse met voortgang en foutmelding; één analyse tegelijk.
- Volledige beweging controleren in MuJoCo, inclusief gewrichtsposities en botverbindingen.
- Dezelfde posities afspelen in een draaibaar browserskelet met gelijke lengteschaal
  in alle richtingen, tijdschuif, pauze en zoom.
- Gekalibreerde armheffing, YXY-axiale hoek en een aparte swing-twist-maat bekijken.
- CSV, PNG, meetrapport en complete resultaten-ZIP downloaden.
- Interface gebruiken op een smal scherm.

De browserweergave is **kinematisch**: de posities komen uit dezelfde gegevens
als de MuJoCo-skeletdemo. Het is geen ingebedde MuJoCo-physics-engine, witte
MyoFullBody-fit, spierberekening of nieuwe voetcontactoptimalisatie.

De eerste 0,5 s wordt standaard als neutrale beginhouding aangenomen. Dezelfde
vaste 3D-referentiecorrectie als in de desktop-app wordt toegepast. De getekende
skeletpunten worden niet verschoven. De hoeken blijven experimentele
humerothoracale metingen; anatomische ISB-validatie is niet aangetoond. De aparte
swing-twist-curve is geen vervanging met dezelfde definitie als ISB-YXY-axiale
rotatie. Onderbrekingen in de YXY-curve blijven zichtbaar bij instabiele standen.

## Eigen video verwerken

Daarvoor moet op dezelfde computer de aparte GEM-X-CPU-motor met de officiële
lokale modellen beschikbaar zijn, zoals beschreven bij [de desktop-app](../desktop_app/README.md)
en [de bestaande videopipeline](../probe/README.md). Deze browserversie downloadt
of bundelt de modellen niet. De werkelijke Windows-video-inferentie is nog niet
end-to-end gevalideerd.

De serverbeheerder stelt de motor bij het starten in; de webpagina kan zelf geen
Python-uitvoerbaar bestand of serverpaden kiezen. Bijvoorbeeld:

```powershell
.\.venv-browser\Scripts\python.exe -m browser_app.server --open-browser `
  --engine-python 'C:\pad\videomotor\Scripts\python.exe' `
  --engine-config 'C:\pad\weights\body_video_native77.yaml' `
  --soma-assets 'C:\pad\assets\soma'
```

Vervolgens wordt **Eigen video** beschikbaar. Ondersteund zijn MP4/MOV/AVI/MKV
(tot 256 MB), met een selectie van maximaal 60 seconden. Begin met 2 seconden:
de eerdere CPU-inferentie duurde circa 12 minuten voor zo'n clip. Ontbrekende
modellen of een mislukte analyse worden niet als een geslaagd resultaat getoond.
Het motorlogboek kan bij een fout worden gedownload.

## Opslag en lokaal gebruik

Bij starten via de CLI staan invoervideo's, logboeken en resultaten standaard in
`GEMX-resultaten/browser` onder je gebruikersmap. Met `--data-dir` kun je een
andere map kiezen. Bestanden blijven na afsluiten staan totdat je ze zelf
verwijdert. Download de gewenste resultaten voor je de server herstart; de
interface houdt nog geen blijvende analysegeschiedenis bij.

De server luistert alleen op `127.0.0.1`. Lokale sessiecookies, hostcontrole en
requesttokens beschermen de API tegen verzoeken vanaf andere websites. Dit is
geen gebruikerslogin of internetdeploymentsysteem. De lokale server moet niet
via een poortforward of tunnel als openbare dienst worden gepubliceerd.

## Verificatie

```bash
python -m unittest browser_app.test_server desktop_app.test_analysis -v
python -m browser_app.server --self-test outputs/nieuwe-browser-zelftest
```

De tests voeren de echte proefclip-analyse, MuJoCo-validatie en downloads uit.
Ook ongeldige invoer, requesttokens, onbekende analyses en een ontbrekende
videomotor worden gecontroleerd. Het zelftestrapport staat in
`browser-self-test.json` in de opgegeven map.

Daarnaast is de interface daadwerkelijk in Chromium bediend: analyse starten,
3D-framecoördinaten wisselen, afspelen/pauzeren, ZIP downloaden en mobiele layout
controleren. Er waren geen JavaScript-fouten of externe netwerkverzoeken.

## Windows-build

```powershell
powershell -File browser_app/build_windows.ps1
```

Uitvoer: `dist/GEMXBrowser-Windows.zip`, met de EXE, ondersteunende bestanden en
notices van de gebruikte pakketten. Deze build staat los van de desktopworkflow.

De browsercontrole is herhaalbaar met de optionele testafhankelijkheid
`playwright==1.64.1` en een geïnstalleerde Chromium-browser, terwijl de server draait:

```bash
python -m browser_app.check_browser --output outputs/browser-controle
```
