# GEM-X Body Motion: onderzoeksproef

De eerste 2 seconden van de aangeleverde video zijn met de officiële temporele
Body Motion-pipeline op CPU verwerkt: 60 frames, 12 minuten 10 seconden,
4,44 GiB gesamplede piek-RAM op een Linux-cloudmachine met twee logische CPU’s.
Dit is geen benchmark van de Windows-laptop.

- [Alle resultaten als ZIP](reports/jaap-cpu-pilot-01.zip)
- [Video met skelet-overlay](reports/jaap-motion-overlay.mp4)

Open het gewenste bestand en kies op GitHub **Download raw file** (het
downloadpictogram) of **Raw** om het op te slaan.

Het ZIP-bestand bevat de oorspronkelijke modeluitvoer, 77 gewrichtsposities en
globale segmentrotaties per frame in camera- en wereldruimte, segmentnamen,
tijdstippen, eenheden, assenconventies, configuratie, code-/modelversies en
checksums, proefcode en meetrapport. Er zitten geen modelgewichten in.

De volledige video van 8,33 seconden en Windows zijn niet getest. Optionele
Contact/IK is niet uitgevoerd. Er is geen onafhankelijke nauwkeurigheidsmeting
of MuJoCo-retargeting uitgevoerd. Verdere licentiecontrole is nodig vóór
commerciële distributie van de externe HumanArt-detector.

**Privacy:** de overlay bevat een herkenbare persoon. Houd deze repository privé.
