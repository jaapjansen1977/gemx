# Licentiecontrole — 29 oktober 2026

## Laatste stand na nieuwe publicatie

De volledige NVIDIA Open Model License is nu bereikbaar en gelezen, inclusief
de aangehaalde Trustworthy AI-voorwaarden. Tekstversie van 24 oktober 2025:
royaltyvrije, kosteloze gebruiksrechten; commercieel gebruik expliciet toegestaan;
NVIDIA claimt geen eigendom van uitvoer. Bij modeldistributie overeenkomst en
Notice met “Licensed by NVIDIA Corporation under the NVIDIA Open Model License”
meegeven. Geen guardrails of authenticatie omzeilen. De Trustworthy AI-voorwaarden
verbieden onrechtmatig gebruik; de beschreven persoonlijke onderzoeksproef is
geen beschreven verboden toepassing. De gebruiker heeft na de bespreking van
deze voorwaarden expliciet gevraagd de proef voort te zetten. Er is geen apart
acceptatieformulier ingevuld en geen externe publicatie of distributie uitgevoerd.

De technische onderzoeksproef wordt hervat met openbare officiële releases,
ongewijzigde licenties en verificatie van de gepubliceerde hashes. De HumanArt-
dataset zelf is niet nodig en niet gedownload. De eerder genoemde onduidelijkheid
over commerciële distributie van de exacte HumanArt-detectorgewichten blijft
expliciet open; dit verslag certificeert die rechten niet en behandelt research
niet als algemene licentievrijstelling. De tabel hieronder bewaart de eerdere
onderzoeksbevindingen; de toen onbereikbare NVIDIA-overeenkomst is nu gecontroleerd.

## Uitkomst

Aanvulling gebruikersdoel: research / proof of principle, door gebruiker bevestigd.
Dit is geen onderbouwing dat onderzoek automatisch niet-commercieel is of dat
licentievoorwaarden vervallen. Er is geen distributie geautoriseerd. Technische
voorbereiding mag verder; volledige NVIDIA-voorwaarden blijven vóór hervatting
van de modelproef te lezen. Netwerkconcept aangevuld met `www.nvidia.com` voor
die controle; `us.aws.cdn.hf.co` voor de modeldownloads stond al klaar. Publicatie
is niet door de agent uitgevoerd. De HumanArt-dataset wordt niet gedownload.

GEM-X en SOMA worden door hun uitgever uitdrukkelijk als geschikt voor commercieel
gebruik aangeboden. Dat ondersteunt lokaal, kosteloos gebruik onder voorwaarden;
het betekent niet dat alle onderdelen zonder licentieverplichtingen kunnen worden
gebruikt of gebundeld. De volledige automatische videopipeline krijgt nog geen
goedkeuring voor commercieel gebruik of distributie: er blijven concrete punten
open bij de detector en de toepasselijke modelvoorwaarden. Er worden tijdens deze
controle geen modellen uitgevoerd en geen verdere modelgewichten gedownload.

Dit is een technische controle van gepubliceerde voorwaarden, geen juridische
garantie of volledige controle van rechten van alle mogelijke rechthebbenden.

## Code en modellen afzonderlijk

| Onderdeel | Gecontroleerde bron | Bevinding en gevolg |
| --- | --- | --- |
| GEM-X-code, commit 20555befe2fbbe5b2015e1fff7ff214dc18ea9d6 | LICENSE, ATTRIBUTIONS.md, SPDX-headers | Standaard Apache-2.0: kosteloos gebruik en distributie toegestaan onder behoud van licentie en relevante notices; gewijzigde bestanden markeren. Uitzonderingen niet wegpoetsen. |
| GEM-X Body Motion/Body Pose en bijbehorende ViTPose-bundel, modelrevisie 4fce057963671fd95cd4154297944397e7b5a9a0 | Officiële modelkaart en LICENSE | Modelkaart zegt letterlijk “ready for commercial or non-commercial use” en verwijst voor het model naar NVIDIA Open Model License. De meegeleverde LICENSE is Apache-2.0; daarom is uitsluitend op die LICENSE afgaan onvoldoende. De gelinkte NVIDIA-overeenkomst kon vanuit deze omgeving niet worden opgehaald (HTTP 403). De volledige modelvoorwaarden en precieze dekking van elk checkpoint blijven te controleren vóór hervatting. |
| SOMA-code 0.3.3 en native SOMA-assets op d281db2d01553f7230c56e764cec00fe27ef23f7 | Pakketmetadata, asset-LICENSE, officiële SOMA-modelkaart | Apache-2.0; modelkaart vermeldt commercieel gebruik expliciet. Native SOMA gebruiken; geen afzonderlijk gelicentieerde SMPL/SMPL-X/MANO-bestanden ophalen. Hun optionele ondersteuning verleent geen licentie op die bestanden. |
| Bepaalde camerafuncties en handutilities in GEM-X | ATTRIBUTIONS.md, LICENSES/LicenseRef-OpenMDW-1.1.txt | OpenMDW-1.1 verleent kosteloze ruime rechten. Bij distributie overeenkomst en toepasselijke herkomst-/copyrightnotices behouden. Gebruik geldt als acceptatie van voorwaarden. Geen afzonderlijke betaalde licentie aangetroffen. |
| DINOv3-herkomst | Officiële Meta DINOv3 LICENSE.md | Royalty-free beperkte licentie met voorwaarden, onder meer meegeven van overeenkomst bij distributie en naamsvermelding bij onderzoekspublicaties. Geen algemeen non-commercial-verbod aangetroffen. De pipeline gebruikt Transformers en NVIDIA-checkpoints, geen apart gedownload origineel Meta-checkpoint. Exacte doorwerking op NVIDIA-checkpoints niet uitsluitend uit architectuurnaam afleiden; toepasselijkheid blijft vast te leggen. |
| Overige attributies in GEM-X | ATTRIBUTIONS.md | Bevat ook MIT, BSD-3-Clause en SAM License. De SAM-vermelding heeft geen volledige bestandsmapping. Niet stellen dat de hele repository uitsluitend Apache-2.0 is; toepasselijke notices meenemen en scope vóór bundeling bepalen. Geen SAM-modelgewichten opgehaald. |
| YOLOX HumanArt ONNX, yolox_x_8xb8-300e_humanart-a39d44ed | Officieel OpenMMLab-archief, detail.json, MMPose-LICENSE/README, HumanArt-LICENSE/README | MMPose/HumanArt-code is Apache-2.0, maar dat is niet automatisch een expliciete modelgewichtenlicentie. Het ONNX-archief bevat geen afzonderlijke licentie. HumanArt README beperkt de datasetaanvraag tot non-commercial purposes. Dit bewijst geen automatisch verbod op detectorgewichten, maar biedt ook geen sluitende commerciële toestemming daarvoor. Detector voorlopig niet verder gebruiken of distribueren; exacte gewichtenvoorwaarden of schriftelijke verduidelijking van uitgever nodig. |
| Python-pakketten | Metadata van alle geïnstalleerde distributies | Inventaris in license-evidence/installed-package-licenses.json. Veel MIT/BSD/Apache; daarnaast onder meer MPL-2.0 (certifi/tqdm), PSF/CNRI en TOST-1.0 (usd-core). Geen betaalde sleutelvereiste uit deze metadata gebleken. Metadata is geen volledige audit van gebundelde native libraries; werkelijke Windows-wheels en hun third-party notices vóór exe-bundeling nalopen. |
| FFmpeg en OpenCV-binaries | ffmpeg -L, meegeleverde OpenCV LICENSE-3RD-PARTY.txt | De huidige Linux-FFmpeg-build gebruikt GPL v2-or-later en libx264. Lokaal uitvoeren vereist geen aankoop. Distributie van een Windows-binary vraagt controle van de exacte build, licentie-/broncodeverplichtingen en codecvoorwaarden; dit maakt niet automatisch alle losse app-code GPL. OpenCV bevat eigen third-party notices. Nog geen Windows-exe gebouwd of verspreid. |

## Bronnen

- [GEM-X-code en licentie](https://github.com/NVlabs/GEM-X/tree/20555befe2fbbe5b2015e1fff7ff214dc18ea9d6)
- [GEM-X-modelkaart op gecontroleerde revisie](https://huggingface.co/nvidia/GEM-X/blob/4fce057963671fd95cd4154297944397e7b5a9a0/README.md)
- [Gelinkte NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/) — volledige tekst hier nog niet leesbaar
- [SOMA-modelkaart op gecontroleerde revisie](https://huggingface.co/nvidia/SOMA-X/blob/d281db2d01553f7230c56e764cec00fe27ef23f7/README.md)
- [MMPose-licentie](https://github.com/open-mmlab/mmpose/blob/main/LICENSE)
- [HumanArt datasetvoorwaarden](https://github.com/IDEA-Research/HumanArt#dataset-download)
- [DINOv3-licentie](https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md)

Opgehaalde teksten staan onder license-evidence/. De externe main-versies zijn
gelezen op deze datum; alleen de NVIDIA-modelkaarten en lokale GEM-X-code zijn
hier op expliciete commit vastgelegd.

## Eerst oplossen

1. De door de GEM-X-modelkaart aangewezen NVIDIA-overeenkomst volledig lezen en
   dekking voor Body Pose, Motion en ViTPose vastleggen.
2. Expliciete voorwaarden voor commercieel gebruik van de exacte YOLOX HumanArt-
   gewichten vaststellen. Bij onduidelijkheid de uitgever raadplegen; er is geen
   bericht verstuurd. Een eventuele andere detector is een zichtbare wijziging
   van de voorbewerking en mag de temporele Body Motion-pipeline niet vervangen.
3. Vóór distributie: notices/licenties en exacte Windows-dependencies en codecs
   controleren. Geen betaald model, geen toegangscontrole omzeilen, geen
   acceptatieformulier namens gebruiker invullen.

De eerdere detectorproef is technisch uitgevoerd vóór afronding van deze
controle. Haar technische resultaat is geen verklaring van commerciële rechten.
De HumanArt-dataset zelf is niet gedownload. Gebruikersvideo is niet openbaar
gemaakt of naar modelaanbieders gestuurd.
