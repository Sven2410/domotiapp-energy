# Alle teksten die dit product kan tonen

**Gegenereerd door `scripts/extract_texts.py`. Niet met de hand bijwerken.**

Draai het script opnieuw na elke ronde die een zin toevoegt of herschrijft;
`tests/test_texts.py` faalt zolang dit bestand achterloopt. De diff van dit
bestand is wat een ronde aan de klant heeft toegevoegd, in zijn woorden.

## Hoe je dit leest

Gesorteerd per bestand, want dat is wat het script weet. De redactionele
indeling op zichtbaarheid komt terug wanneer het herschrijven begint — dan
is dit de invoer en niet de uitvoer.

- **`{...}`** is een waarde die wordt ingevuld: een getal, een naam,
  een bedrag.
- **↔** staat achter een tekst die op meer dan één plek in de broncode staat.
  Die twee moeten samen herschreven worden of ze lopen uiteen.
- De **CSS** van het paneel is eruit gefilterd; dat is opmaak, geen taal.
- **Engelse regels staan apart**, onderaan. Een Engelse zin in dit product is
  een fout tenzij zij een identifier is: de UI is Nederlands (CLAUDE.md).

**887 Nederlandse teksten**, waarvan 122 op meer dan één plek. En 11 Engelse regels om na te lopen.


## `custom_components/domotiapp_energy/const.py`

| Tekst | Waar | Regel |
|---|---|---|
| Attention | module | 1097 |
| Current advice | module | 1094 |
| Data quality | module | 1091 |
| DomotiApp | module | 21 |
| DomotiApp Energy ↔ | module | 18 |
| DomotiApp Energy ↔ | module | 39 |
| Energy Coach | module | 22 |
| Grid power | module | 1092 |
| Home consumption | module | 1096 |
| Mijn woning | module | 29 |
| Peak risk | module | 1095 |
| Score | module | 1090 |
| Solar surplus | module | 1093 |

## `custom_components/domotiapp_energy/coordinator.py`

| Tekst | Waar | Regel |
|---|---|---|
| Advies opnieuw berekend | async_recalculate | 257 |
| De woning {...} {...}% van het ingestelde maximale netvermogen. Dat ligt op of boven de waarschuwingsgrens van {...}%. | _async_log_findings | 527 |
| Er is {...} W zonneoverschot beschikbaar. | _async_log_findings | 546 |
| Het energieadvies is opnieuw berekend. | async_recalculate | 258 |
| Linked entity %s changed | _handle_tracked_state_event | 268 |
| No linked entities to watch | async_rebuild_state_listener | 231 |
| Piekbelasting gesignaleerd | _async_log_findings | 526 |
| Watching %s linked entities | async_rebuild_state_listener | 234 |
| Zonneoverschot beschikbaar ↔ | _async_log_findings | 545 |
| levert terug met ↔ | _async_log_findings | 523 |
| {...} forget ready flags of deleted appliances | _handle_configuration_change | 303 |
| {...} recalculate after configuration change | _handle_configuration_change | 308 |
| {...} safety recalculation | async_start | 214 |

## `custom_components/domotiapp_energy/engine/advisor.py`

| Tekst | Waar | Regel |
|---|---|---|
| Aanvullende gegevens nodig | _advise_missing_data | 227 |
| Bijna te laat om op tijd klaar te zijn | _advise_deadline | 801 |
| De actuele energieprijs is relatief hoog. Stel flexibel energiegebruik indien mogelijk uit. | _advise_price | 876 |
| De actuele energieprijs is relatief laag. Flexibele apparaten kunnen nu voordeliger worden gebruikt. | _advise_price | 858 |
| De actuele energiesituatie vraagt momenteel niet om een aanpassing. | _neutral_advice | 894 |
| De teruglevering ligt dicht bij de ingestelde maximale woningbelasting. Schakel indien mogelijk juist extra verbruikers in om de belasting te verlagen. Let op: terugleveren levert je op dit moment meer op dan zelf verbruiken, dus dit kost je geld. | _advise_peak_risk | 273 |
| De teruglevering ligt dicht bij de ingestelde maximale woningbelasting. Schakel indien mogelijk juist extra verbruikers in om het overschot zelf te benutten. | _advise_peak_risk | 267 |
| Dit is een gunstig moment om {...} te gebruiken. ↔ | _surplus_message | 503 |
| Dit is een gunstig moment om {...} te gebruiken. ↔ | _modulating_surplus_message | 569 |
| Er is momenteel zonneoverschot beschikbaar, maar {...} mag tussen {...} en {...} niet draaien. Dat is bij de installatie zo ingesteld en staat los van je stille uren. Na {...} kan het weer. | _no_run_message | 451 |
| Er is momenteel zonneoverschot beschikbaar. ↔ | _surplus_message | 502 |
| Er is momenteel zonneoverschot beschikbaar. ↔ | _modulating_surplus_message | 568 |
| Er is momenteel zonneoverschot beschikbaar. {...} maakt geluid en het zijn stille uren tot {...}. Wacht daarmee tot na {...}, of pas de stille uren aan bij Mijn voorkeuren. | _quiet_hours_message | 427 |
| Geen actie nodig | _neutral_advice | 893 |
| Het actuele netvermogen ligt dicht bij de ingestelde maximale woningbelasting. Stel extra grootverbruikers indien mogelijk uit. | _advise_peak_risk | 296 |
| Hoeveel dit oplevert is niet te berekenen zolang de terugleverkosten niet zijn ingevuld — vul ze in bij Woning, of zet ze op 0 als deze aansluiting ze niet betaalt. | _why_no_margin | 727 |
| Hoeveel dit oplevert is niet te berekenen zolang de terugleverprijsbron geen bruikbare waarde geeft. Controleer die bij Energiebronnen. | _why_no_margin | 716 |
| Hoeveel dit oplevert is niet te berekenen zolang er geen actuele prijs is. Controleer de prijsbron bij Energiebronnen. | _why_no_margin | 701 |
| Hoeveel dit oplevert is niet te berekenen zonder de energie per cyclus van {...} — vul die in bij Apparaten. | _why_no_amount | 638 |
| Hoeveel dit oplevert is niet te berekenen zonder de energie per laadsessie van {...} — vul die in bij Apparaten. | _why_no_amount | 634 |
| Hoeveel dit oplevert is niet te berekenen zonder de terugleververgoeding — vul die in bij Woning, of koppel een terugleverprijsbron. | _why_no_margin | 721 |
| Hoeveel dit oplevert is niet te berekenen zonder het vaste leveringstarief — vul dat in bij Woning. | _why_no_margin | 705 |
| Hoeveel dit per uur oplevert is niet te berekenen zonder het maximale laadvermogen van {...} — vul dat in bij Apparaten. | _why_no_rate | 668 |
| Hoeveel dit per uur oplevert is niet te berekenen zonder het nominale vermogen van {...} — vul dat in bij Apparaten. | _why_no_rate | 673 |
| Hoge energieprijs | _advise_price | 874 |
| Lage energieprijs | _advise_price | 856 |
| Netbelasting hoog | _advise_peak_risk | 294 |
| Start {...} nu als hij om {...} klaar moet zijn. | _deadline_message | 827 |
| Start {...} nu om {...} te halen. | _deadline_message | 826 |
| Teruglevering hoog | _advise_peak_risk | 282 |
| Vul de ontbrekende energiegegevens aan om een betrouwbaar advies te ontvangen. | _advise_missing_data | 229 |
| Zonneoverschot beschikbaar ↔ | _advise_solar_surplus | 382 |
| Zonneoverschot, maar dit apparaat mag nu niet draaien | _advise_solar_surplus | 351 |
| Zonneoverschot, maar het zijn stille uren | _advise_solar_surplus | 366 |
| {...} Zelf verbruiken levert nu echter minder op dan terugleveren: {...} nu gebruiken kost naar schatting {...} ten opzichte van het overschot terugleveren. Wachten tot de terugleververgoeding lager ligt is voordeliger. | _surplus_message | 520 |
| {...} {...} Het levert op dit moment niets extra op, maar het kost ook niets. | _surplus_message | 538 |
| {...} {...} Zolang de salderingsregeling geldt levert dit geen extra besparing op, maar het overschot zelf gebruiken blijft de meest efficiënte keuze. | _surplus_message | 531 |

## `custom_components/domotiapp_energy/engine/calculator.py`

| Tekst | Waar | Regel |
|---|---|---|
| Multiple enabled sources of type %r; none of them is used ↔ | _read_sources | 318 |

## `custom_components/domotiapp_energy/engine/providers.py`

| Tekst | Waar | Regel |
|---|---|---|
| Alle gegevens voor een betrouwbaar advies zijn ingevuld. ↔ | _missing_data | 378 |
| De energiescore is nog niet berekend. ↔ | _score_breakdown | 411 |
| De energiescore is nog niet berekend. ↔ | _score_breakdown | 420 |
| De netbelasting is niet te bepalen. Vul het maximale netvermogen in en koppel een netbron. | _peak_risk | 340 |
| De score op dit moment is {...}, opgebouwd uit: {...}. | _score_breakdown | 423 |
| De stroomprijs is op dit moment laag, dus er is geen duur verbruik om te vermijden. | module | 158 |
| Er is nog geen energiescore, omdat de installatie nog niet compleet is. De checklist hieronder laat zien wat er ontbreekt. | module | 126 |
| Er is nu opwek, maar geen apparaat of batterij die verbruik kan verplaatsen. Er valt daarom niets te benutten dat nu niet al gebeurt. | module | 141 |
| Er is op dit moment geen aanleiding om een apparaat te verplaatsen of juist nu te gebruiken. | _use_device_now | 315 |
| Er is op dit moment geen advies. | _why_advice | 258 |
| Gebaseerd op {...}. | _why_advice | 267 |
| Het prijsmoment telt niet mee zolang de lage en de hoge prijsdrempel niet zijn ingevuld. Vul ze in bij Installatie. | module | 196 |
| Het prijsmoment telt niet mee, want bij een vast tarief is het ene moment niet duurder dan het andere. | module | 192 |
| Het prijsmoment telt niet mee, want de actuele prijs is op dit moment niet uit te lezen. | module | 200 |
| Het prijsmoment telt niet mee, want de stroom is nu goedkoop en er is dus geen duur verbruik om te vermijden. | module | 204 |
| Het tarief is altijd gelijk en er zijn geen zonnepanelen, dus er is geen moment dat beter is dan een ander. Er valt daarom niets te optimaliseren. Het advies blijft gewoon werken. | module | 130 |
| Het vermogen van je thuisbatterij kan niet uitgelezen worden. Een batterij die laadt of ontlaadt verschuift wat er van het net komt, dus het thuisverbruik is niet te berekenen en het zonneoverschot kan te hoog zijn. Koppel de vermogenssensor van de batterij om dit op te lossen. | module | 101 |
| Ja. De all-in energieprijs is nu {...} en ligt onder de ingestelde lage prijsgrens. | _use_device_now | 305 |
| Ja. De woning levert veel terug aan het net; dat overschot kun je nu beter zelf gebruiken. | _use_device_now | 291 |
| Je panelen leveren op dit moment niets en de stroomprijs is laag. Er is nu dus geen overschot om te benutten en geen duur verbruik om te vermijden. | module | 149 |
| Je panelen leveren op dit moment niets, en bij een vast tarief is het ene moment niet beter dan het andere. Er is nu dus niets te verbeteren. | module | 154 |
| Je panelen leveren op dit moment, maar terugleveren levert je meer op dan de stroom je kost. Zelf verbruiken zou je nu geld kosten, dus er valt aan je opwek niets te benutten. De coach zegt hetzelfde: wachten is voordeliger. | module | 135 |
| Nee | _peak_risk | 347 |
| Niet van toepassing op deze woning, en dus niet meegeteld: {...}. | _missing_data | 382 |
| Nog ontbrekend: {...}. | _missing_data | 376 |
| Nu is geen gunstig moment: de all-in energieprijs is {...} en ligt boven de ingestelde hoge prijsgrens. | _use_device_now | 310 |
| Nu is geen gunstig moment: de netbelasting ligt dicht bij het ingestelde maximum. | _use_device_now | 296 |
| Zolang de lage en de hoge prijsdrempel niet zijn ingevuld, is niet te bepalen of dit een duur moment is. Vul ze in bij Installatie. | module | 145 |
| Zonnebenutting telt niet mee, want deze woning heeft geen zonnepanelen. ↔ | module | 173 |
| Zonnebenutting telt niet mee, want er is geen apparaat of batterij die verbruik naar dit moment kan verplaatsen. | module | 183 |
| Zonnebenutting telt niet mee, want je panelen leveren op dit moment niets. ↔ | module | 176 |
| Zonnebenutting telt niet mee, want zonder netmeting is niet te zien hoeveel van je opwek je zelf gebruikt. | module | 179 |
| Zonnebenutting telt niet mee: terugleveren levert je op dit moment meer op dan de stroom je kost, dus je opwek zelf gebruiken zou je geld kosten. | module | 187 |
| all-in prijs in €/kWh ↔ | module | 84 |
| de woninggegevens ↔ | module | 71 |
| een compleet apparaatprofiel ↔ | module | 75 |
| een geldige netbron ↔ | module | 72 |
| een geldige zonnebron ↔ | module | 73 |
| levert terug met ↔ | _peak_risk | 346 |
| netbelasting in % ↔ | module | 85 |
| netvermogen in W ↔ | module | 86 |
| ontbrekende onderdelen ↔ | module | 88 |
| tijdvensters voor flexibele apparaten ↔ | module | 76 |
| zonneoverschot in W ↔ | module | 87 |
| {...}. De woning {...} {...}% van het ingestelde maximale netvermogen. | _peak_risk | 350 |
| € {...} per kWh | _format_price | 328 |

## `custom_components/domotiapp_energy/frontend/core/api.js`

| Tekst | Waar | Regel |
|---|---|---|
| DomotiApp Energy is niet geladen. Controleer de integratie in Instellingen. | api | 125 |
| Er is een onbekende fout opgetreden. ↔ | api | 119 |
| Er is een onbekende fout opgetreden. ↔ | api | 130 |
| Je hebt geen rechten voor deze actie. | api | 128 |

## `custom_components/domotiapp_energy/frontend/core/dialog.js`

| Tekst | Waar | Regel |
|---|---|---|
| Annuleren ↔ | dialog | 141 |
| Annuleren ↔ | dialog | 164 |
| Escape | dialog | 89 |
| Sluiten ↔ | dialog | 24 |
| Verwijderen ↔ | dialog | 139 |
| Verwijderen ↔ | dialog | 163 |

## `custom_components/domotiapp_energy/frontend/core/dom.js`

| Tekst | Waar | Regel |
|---|---|---|
| Niet beschikbaar ↔ | dom | 44 |
| Nog niet berekend ↔ | dom | 68 |
| button button-primary | dom | 175 |

## `custom_components/domotiapp_energy/frontend/core/labels.js`

| Tekst | Waar | Regel |
|---|---|---|
| Buiten het toegestane tijdvenster | labels | 13 |
| De besparing is te klein om te melden | labels | 16 |
| De energieprijs is hoog | labels | 11 |
| De energieprijs is laag | labels | 10 |
| De netbelasting is hoog | labels | 8 |
| De situatie vraagt niet om een aanpassing | labels | 17 |
| De teruglevering is hoog | labels | 9 |
| De uiterste starttijd komt in zicht | labels | 15 |
| Een gekoppelde entiteit levert geen bruikbare waarde | labels | 6 |
| Er is een verplaatsbaar apparaat beschikbaar | labels | 12 |
| Er is zonneoverschot | labels | 7 |
| Er ontbreken gegevens | labels | 5 |
| Het is nu stille uren | labels | 14 |
| all-in prijs in €/kWh ↔ | labels | 32 |
| de woninggegevens ↔ | labels | 22 |
| een compleet apparaatprofiel ↔ | labels | 26 |
| een geldige netbron ↔ | labels | 23 |
| een geldige zonnebron ↔ | labels | 24 |
| netbelasting in % ↔ | labels | 33 |
| netvermogen in W ↔ | labels | 34 |
| ontbrekende onderdelen ↔ | labels | 36 |
| tijdvensters voor flexibele apparaten ↔ | labels | 27 |
| zonneoverschot in W ↔ | labels | 35 |

## `custom_components/domotiapp_energy/frontend/core/roles.js`

| Tekst | Waar | Regel |
|---|---|---|
| Deze gegevens worden beheerd door DomotiTech. | roles | 54 |

## `custom_components/domotiapp_energy/frontend/domotiapp-energy-panel.js`

| Tekst | Waar | Regel |
|---|---|---|
| DomotiApp Energy tabbladen | domotiapp-energy-panel | 113 |
| Gegevens laden… | domotiapp-energy-panel | 235 |

## `custom_components/domotiapp_energy/frontend/tabs/coach.js`

| Tekst | Waar | Regel |
|---|---|---|
| Advies ↔ | coach | 35 |
| Advies ↔ | coach | 36 |
| Advies ↔ | coach | 174 |
| Alle gegevens voor een betrouwbaar advies zijn ingevuld. ↔ | coach | 399 |
| Bezig met berekenen… | coach | 277 |
| Deze vraag is nog niet beantwoord. Bereken opnieuw zodra er gegevens | coach | 239 |
| Energiecoach | coach | 59 |
| Er is op dit moment geen aanvullend advies. | coach | 111 |
| Gegevens voor je advies | coach | 128 |
| Geschatte besparing | coach | 73 |
| Geschatte opbrengst per uur | coach | 78 |
| Het advies is opnieuw berekend. | coach | 282 |
| Hoe is mijn energiescore berekend? | coach | 31 |
| Hoofdadvies | coach | 66 |
| Is er risico op piekbelasting? | coach | 29 |
| Kan ik nu het beste een apparaat gebruiken? | coach | 28 |
| Kies een vraag; het antwoord verschijnt in beeld. | coach | 139 |
| Klaar / vol ↔ | coach | 88 |
| Klaar / vol ↔ | coach | 317 |
| Laatste berekening ↔ | coach | 80 |
| Nog geen advies berekend ↔ | coach | 321 |
| Nog niet berekend ↔ | coach | 80 |
| Nog ontbrekend: | coach | 129 |
| Onbekend | coach | 79 |
| Opnieuw berekenen | coach | 82 |
| Overige adviezen | coach | 109 |
| Probleem | coach | 38 |
| Reden ↔ | coach | 79 |
| Toch niet vol ↔ | coach | 317 |
| Vraag het de coach | coach | 135 |
| Waarom krijg ik dit advies? | coach | 27 |
| Waarschuwing ↔ | coach | 37 |
| Welke gegevens ontbreken nog? | coach | 30 |
| Zodra er een energiebron gekoppeld is, verschijnt hier het hoofdadvies. ↔ | coach | 324 |
| Zolang dit zonneoverschot er is. | coach | 346 |
| gekoppeld zijn. | coach | 240 |

## `custom_components/domotiapp_energy/frontend/tabs/devices.js`

| Tekst | Waar | Regel |
|---|---|---|
| "Alleen monitoren" legt vast dat dat zo moet blijven, ook als dat | devices | 626 |
| "alleen adviseren" om het weer mee te laten doen. | devices | 620 |
| "alleen monitoren" wordt als adviseren behandeld. | devices | 632 |
| "mag hierna niet meer draaien". | devices | 414 |
| ${device.name \|\| ↔ | devices | 1488 |
| ${device.name \|\| ↔ | devices | 1512 |
| Aan- en uitschakelen ↔ | devices | 92 |
| Aansturing ↔ | devices | 872 |
| Aansturing uitgesloten voor deze installatie ↔ | devices | 662 |
| Airconditioning | devices | 47 |
| Alleen adviseren ↔ | devices | 85 |
| Alleen monitoren | devices | 84 |
| Alleen registreren: er wordt niets aangestuurd. Niets aanvinken | devices | 656 |
| Annuleren ↔ | devices | 998 |
| Apparaat ↔ | devices | 835 |
| Apparaat ↔ | devices | 940 |
| Apparaat bewerken | devices | 1248 |
| Apparaat toevoegen ↔ | devices | 894 |
| Apparaat toevoegen ↔ | devices | 1248 |
| Apparaat verwijderen | devices | 1510 |
| Apparaten ↔ | devices | 886 |
| Apparaten ↔ | devices | 891 |
| Automatisch aansturen ↔ | devices | 87 |
| Batterijniveau | devices | 154 |
| Bedieningsniveau ↔ | devices | 640 |
| Bedieningsniveau ↔ | devices | 777 |
| Bewerken ↔ | devices | 1033 |
| Bewerken ↔ | devices | 1087 |
| Bezig met opslaan… ↔ | devices | 1376 |
| Bezig met verwijderen… ↔ | devices | 1480 |
| Bij meerdere kandidaten wint de hoogste prioriteit. | devices | 306 |
| Compleet. ↔ | devices | 1231 |
| Dagen ↔ | devices | 517 |
| Dagen ↔ | devices | 763 |
| De aanvoertemperatuur van de warmtepomp. | devices | 147 |
| De configuratie is intussen ergens anders gewijzigd. Er is niets ↔ | devices | 1495 |
| De energie van een gemiddelde draaiperiode. | devices | 382 |
| De energie van één cyclus. | devices | 385 |
| De energie van één droogbeurt. | devices | 381 |
| De energie van één programma, bijvoorbeeld 1,0 tot 1,5 kWh. | devices | 379 |
| De energie van één wasbeurt. | devices | 380 |
| De entiteit die zegt of het apparaat aan staat of draait. | devices | 114 |
| De gekoppelde vermogenssensor is niet te gebruiken: hij moet | devices | 1071 |
| De laadtoestand van de auto, als de laadpaal die meldt. | devices | 158 |
| De laadtoestand van de thuisbatterij, in procenten. | devices | 157 |
| De meterstand of het verbruik van dit apparaat. | devices | 134 |
| De ruimtetemperatuur die deze airco regelt. | devices | 149 |
| De watertemperatuur in de boiler. | devices | 148 |
| Deze ingevulde gegevens worden voor dit apparaat niet meer | devices | 1302 |
| Dinsdag | devices | 100 |
| Dit apparaat is compleet: alles wat de datakwaliteit vraagt is ingevuld. | devices | 1295 |
| Dit apparaat is intussen ergens anders verwijderd. Je invoer staat | devices | 1437 |
| Dit apparaat is intussen ook ergens anders gewijzigd. Je invoer | devices | 1444 |
| Dit apparaat krijgt geen advies zolang het niet verplaatsbaar is. | devices | 625 |
| DomotiApp Energy adviseert in deze versie alleen; alles behalve | devices | 631 |
| DomotiApp Energy rekent zelf terug wanneer het apparaat uiterlijk | devices | 409 |
| Donderdag | devices | 102 |
| Droger | devices | 46 |
| Duur van een cyclus ↔ | devices | 352 |
| Duur van een cyclus ↔ | devices | 770 |
| Duur van een laadsessie | devices | 352 |
| Een afspraak met de klant, los van wat dit apparaat kan. | devices | 663 |
| Een schatting van een typische laadbeurt, bijvoorbeeld 10 kWh voor | devices | 375 |
| Een uitgeschakeld apparaat krijgt geen advies. | devices | 294 |
| Elektrische boiler | devices | 43 |
| Energie per cyclus ↔ | devices | 344 |
| Energie per cyclus ↔ | devices | 769 |
| Energie per laadsessie | devices | 344 |
| Energieverbruikentiteit | devices | 132 |
| Er is intussen ergens anders iets aan de configuratie gewijzigd, maar ↔ | devices | 1449 |
| Het actuele vermogen van dit apparaat. Anders dan bij een energiebron | devices | 125 |
| Het elektrische opgenomen vermogen, niet het thermische. | devices | 366 |
| Het hoogste vermogen waarmee deze paal kan laden — niet wat de auto | devices | 363 |
| Het laad- of ontlaadvermogen van de batterij. | devices | 365 |
| Het minste waarmee het apparaat nog iets doet. | devices | 543 |
| Het vermogen tijdens gebruik. | devices | 369 |
| Het vermogen van het verwarmingselement. | devices | 367 |
| Hoe lang de lopende cyclus nog duurt. | devices | 140 |
| Hoog | devices | 79 |
| In minuten, voor een typische laadbeurt. Wordt getoetst aan het | devices | 393 |
| In minuten. Wordt getoetst aan het tijdvenster hieronder. | devices | 397 |
| Ingeschakeld ↔ | devices | 293 |
| Instellen | devices | 1087 |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Verwerp je ze, ↔ | devices | 1537 |
| Kan op deelvermogen draaien ↔ | devices | 571 |
| Kan op deelvermogen draaien ↔ | devices | 779 |
| Klaar / vol ↔ | devices | 1031 |
| Klaar / vol ↔ | devices | 1081 |
| Klaar uiterlijk om ↔ | devices | 452 |
| Klaar uiterlijk om ↔ | devices | 757 |
| Koppelingen | devices | 867 |
| Kritiek | devices | 80 |
| Laadpaal | devices | 40 |
| Laadstroom instellen ↔ | devices | 94 |
| Laag | devices | 77 |
| Laat beide tijden leeg als er geen venster is; het apparaat mag dan op | devices | 404 |
| Laat leeg als de deadline elke dag geldt. Voor een laadpaal is dit | devices | 472 |
| Ligt deze tijd vóór "niet draaien vanaf", dan loopt het verbod door | devices | 511 |
| Locatie | devices | 299 |
| Maakt geluid ↔ | devices | 563 |
| Maakt geluid ↔ | devices | 772 |
| Maakt niet uit wanneer hij klaar is ↔ | devices | 442 |
| Maakt niet uit wanneer hij klaar is ↔ | devices | 760 |
| Maandag | devices | 99 |
| Maximaal laadvermogen | devices | 338 |
| Minimaal vermogen ↔ | devices | 583 |
| Minimaal vermogen ↔ | devices | 781 |
| Moet gemeld worden dat er werk in zit ↔ | devices | 589 |
| Moet gemeld worden dat er werk in zit ↔ | devices | 780 |
| Naam ↔ | devices | 285 |
| Naamloos apparaat | devices | 1055 |
| Niet draaien vanaf ↔ | devices | 493 |
| Niet draaien vanaf ↔ | devices | 761 |
| Niet eerder klaar dan ↔ | devices | 480 |
| Niet eerder klaar dan ↔ | devices | 758 |
| Nog geen apparaten. Voeg de apparaten toe waarover DomotiApp Energy | devices | 922 |
| Nog geen vermogenssensor gekoppeld — dit apparaat wordt alleen | devices | 1207 |
| Nog nodig voor een compleet apparaat: | devices | 1291 |
| Nominaal vermogen ↔ | devices | 338 |
| Nominaal vermogen ↔ | devices | 768 |
| Normaal | devices | 78 |
| Noteer waarom, zodat dit later terug te vinden is. ↔ | devices | 672 |
| Notities ↔ | devices | 322 |
| Notities ↔ | devices | 881 |
| Op "alleen monitoren" krijgt dit apparaat geen advies. Zet het op | devices | 619 |
| Op welke dagen dit apparaat mag draaien. | devices | 518 |
| Op welke dagen geldt dit ↔ | devices | 466 |
| Op welke dagen geldt dit ↔ | devices | 759 |
| Opslaan ↔ | devices | 997 |
| Opslaan mag ook zonder — het apparaat telt dan alleen nog niet | devices | 1293 |
| Opslaan om hem te bewaren. | devices | 1451 |
| Optioneel. Handig voor was die niet uren nat mag blijven liggen: | devices | 485 |
| Overig, alleen meten | devices | 50 |
| Overig, inplanbaar | devices | 49 |
| Prioriteit ↔ | devices | 305 |
| Prioriteit ↔ | devices | 771 |
| Reden ↔ | devices | 671 |
| Reden ↔ | devices | 764 |
| Resterende tijd | devices | 138 |
| Soort apparaat | devices | 288 |
| Statusentiteit | devices | 112 |
| Telt niet mee voor de datakwaliteit. | devices | 1220 |
| Temperatuursensor | devices | 144 |
| Terug naar het formulier ↔ | devices | 1540 |
| Thuisbatterij ↔ | devices | 41 |
| Toch niet vol ↔ | devices | 1081 |
| Uitgeschakeld — krijgt geen advies. | devices | 1177 |
| Uitlezen ↔ | devices | 91 |
| Uren waarin dit apparaat helemaal niet mag draaien, bijvoorbeeld | devices | 500 |
| Vaatwasser | devices | 44 |
| Verbruik | devices | 840 |
| Vermogensentiteit | devices | 118 |
| Vermogensgrens instellen ↔ | devices | 93 |
| Verplaatsbaar in de tijd ↔ | devices | 604 |
| Verplaatsbaar in de tijd ↔ | devices | 778 |
| Verwerpen ↔ | devices | 1539 |
| Verwijderen ↔ | devices | 1034 |
| Vragen om goedkeuring ↔ | devices | 86 |
| Vrijdag | devices | 103 |
| Vul hierboven een duur in, dan rekent DomotiApp Energy terug wanneer | devices | 412 |
| Waar staat het? Alleen om het terug te herkennen. | devices | 300 |
| Wanneer het mag draaien | devices | 851 |
| Warmtepomp | devices | 42 |
| Wasmachine | devices | 45 |
| Wat kan dit apparaat? | devices | 654 |
| Weer toegestaan vanaf ↔ | devices | 509 |
| Weer toegestaan vanaf ↔ | devices | 762 |
| Wijzigingen verwerpen? ↔ | devices | 1535 |
| Woensdag | devices | 101 |
| Zaterdag | devices | 104 |
| Zet dit aan als elk moment goed is. De coach adviseert dit apparaat | devices | 444 |
| Zet dit aan voor apparatuur die minder dan haar maximum kan | devices | 576 |
| Zet het apparaattype, "verplaatsbaar in de tijd" of het | devices | 1304 |
| Zondag | devices | 105 |
| Zonder dit getal is er geen besparing te berekenen. | devices | 386 |
| Zwembadpomp | devices | 48 |
| alleen die hebben een tijdvenster nodig. | devices | 608 |
| andere dagen mag hij gewoon wachten op zon of een lage prijs — hij | devices | 474 |
| bedieningsniveau terug om ze te behouden. | devices | 1305 |
| betekent "niet opgegeven", niet "kan niets". | devices | 657 |
| betrouwbaarheid daarom op "gemiddeld". | devices | 378 |
| dan gewoon op een gunstig moment, alleen zonder deadline om naartoe | devices | 445 |
| dan zijn ze weg. ↔ | devices | 1538 |
| een dagelijkse rit. Exact kan niet: DomotiApp Energy weet niet hoe | devices | 376 |
| elk uur. Een venster telt wel mee voor de datakwaliteit, omdat het advies | devices | 405 |
| energie per cyclus | devices | 258 |
| energie per laadsessie | devices | 263 |
| er gerichter van wordt. | devices | 406 |
| er vandaag van afneemt. | devices | 364 |
| geadviseerd, dus een droger van ruim twee uur krijgt bij een verbod | devices | 503 |
| gebruiken, zoals de meeste laadpalen. Zonder het minimum hieronder | devices | 577 |
| geen reden genoteerd ↔ | devices | 1194 |
| gemeten, en er valt nu niets te meten. | devices | 1208 |
| het apparaat uiterlijk moet starten. Zonder duur geldt dit alleen als | devices | 413 |
| het terug wilt. | devices | 1439 |
| hier nog, maar opslaan lukt niet meer; maak het opnieuw aan als je | devices | 1438 |
| in W of kW meten en een waarde melden. | devices | 1072 |
| krijgt dan nog steeds advies, alleen zonder deadline. | devices | 475 |
| later verandert. | devices | 627 |
| leeg de auto is, dus het advies rekent met dit getal en houdt zijn | devices | 377 |
| lege machine geadviseerd. | devices | 599 |
| mag adviseren, met hun vermogen, verbruik per cyclus en tijdvenster. | devices | 923 |
| maximaal laadvermogen | devices | 262 |
| mee voor de datakwaliteit. | devices | 1294 |
| meestal de werkweek: op die dagen moet de auto vol zijn, en op de | devices | 473 |
| moet starten om dit te halen. | devices | 410 |
| nadat iemand op "Klaar / vol" heeft gedrukt. Zo wordt er nooit een | devices | 598 |
| niet aan dit apparaat. Je invoer staat er nog; druk opnieuw op | devices | 1450 |
| nominaal vermogen | devices | 257 |
| of kW meten. Een meterstand in kWh is een totaal en geen vermogen, en | devices | 127 |
| omdat het onder een slaapkamer staat. Laat beide leeg als er geen | devices | 501 |
| staat er nog; als je nu opslaat, vervangt hij die andere wijziging. ↔ | devices | 1445 |
| te rekenen — en de datakwaliteit rekent het als beantwoord in plaats | devices | 446 |
| tijd ná "klaar uiterlijk om", dan loopt het venster door tot de | devices | 487 |
| tijdvenster hieronder. | devices | 394 |
| tot de volgende dag — 23:00 tot 07:00 is het normale geval. | devices | 512 |
| van als ontbrekend. | devices | 447 |
| vanaf 23:00 al vanaf 20:45 geen advies meer. | devices | 504 |
| verandert er niets. | devices | 578 |
| verbod is. Een cyclus die het venster in zou lopen wordt ook niet | devices | 502 |
| verwijderd; de lijst is opnieuw geladen. ↔ | devices | 1496 |
| verwijderen? Er wordt daarna niet meer over geadviseerd. | devices | 1513 |
| volgende dag — 22:00 tot 06:00 is het normale geval. | devices | 488 |
| wordt de eenheid hier van de entiteit zelf overgenomen: hij moet in W | devices | 126 |
| wordt geweigerd — de rij zegt dat dan ook. | devices | 128 |
| zet hier bijvoorbeeld 06:00 als je hem om 07:00 uithaalt. Ligt deze | devices | 486 |
| zonder naam ↔ | devices | 1400 |

## `custom_components/domotiapp_energy/frontend/tabs/home.js`

| Tekst | Waar | Regel |
|---|---|---|
| (marktprijs + opslag + energiebelasting) × (1 + btw). Een prijsbron | home | 435 |
| 1 fase | home | 42 |
| 3 fasen | home | 43 |
| Aantal fasen | home | 37 |
| Adviesinstellingen | home | 375 |
| Alleen adviseren ↔ | home | 468 |
| Alleen nodig als je terugleverprijsbron de kale marktprijs levert. | home | 256 |
| Automatisch aansturen ↔ | home | 470 |
| Bedieningsniveau ↔ | home | 376 |
| Bedieningsniveau ↔ | home | 463 |
| Besparen | home | 321 |
| Bezig met opslaan… ↔ | home | 736 |
| Comfort | home | 319 |
| Contract en prijzen | home | 374 |
| Contractsoort | home | 192 |
| De salderingsregeling stopt landelijk op 1 januari 2027. Laat leeg als | home | 280 |
| De woninggegevens zijn intussen ergens anders gewijzigd. Het | home | 766 |
| De woninggegevens zijn opgeslagen. | home | 748 |
| DomotiApp Energy meet, rekent en adviseert; het stuurt in deze versie | home | 482 |
| DomotiApp Energy rekent overal met de all-in prijs: | home | 434 |
| Dynamisch tarief | home | 198 |
| Een bedrag per kWh, exclusief btw — géén vast maandbedrag. Reken een | home | 226 |
| Een bedrag per kWh, exclusief btw. Nodig zodra een prijsbron de kale | home | 215 |
| Een bedrag per teruggeleverde kWh — géén vast maandbedrag. Reken een | home | 270 |
| Energiebelasting | home | 213 |
| Er is intussen ergens anders iets aan de configuratie gewijzigd, ↔ | home | 773 |
| Gebalanceerd | home | 320 |
| Het all-in bedrag per kWh, inclusief energiebelasting en btw — dus wat | home | 207 |
| Het btw-percentage over de leveringsprijs. In Nederland 21%. | home | 235 |
| Het vaste bedrag dat de klant per teruggeleverde kWh daadwerkelijk | home | 244 |
| Het vermogen waarboven DomotiApp Energy waarschuwt. | home | 57 |
| Hier blijven ↔ | home | 499 |
| Hoge prijsgrens (all-in) | home | 297 |
| Hoofdzekering per fase | home | 50 |
| In ampère, zoals op de zekering staat. | home | 51 |
| Inhouding leverancier op teruglevering | home | 251 |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Sla ze op, of verwerp ↔ | home | 837 |
| Lage prijsgrens (all-in) | home | 286 |
| Maximaal netvermogen | home | 56 |
| Maximaal zelf verbruiken | home | 322 |
| Minimaal zonneoverschot | home | 308 |
| Naam van de woning | home | 34 |
| Opslaan ↔ | home | 490 |
| Opslag leverancier | home | 221 |
| Percentage van het maximale netvermogen. | home | 63 |
| Saldering geldt tot | home | 278 |
| Standaardstrategie | home | 314 |
| Terugleverkosten | home | 263 |
| Terugleververgoeding (all-in) | home | 240 |
| Vanaf dit overschot adviseert DomotiApp Energy een apparaat. | home | 309 |
| Vast leveringstarief (all-in) | home | 205 |
| Vast tarief | home | 197 |
| Vergelijk met de all-in prijs, niet met de kale marktprijs van je ↔ | home | 291 |
| Vergelijk met de all-in prijs, niet met de kale marktprijs van je ↔ | home | 299 |
| Verwerpen en verdergaan ↔ | home | 498 |
| Vragen om goedkeuring ↔ | home | 469 |
| Vul 0 in als er niets wordt ingehouden. | home | 257 |
| Waarschuwen vanaf | home | 62 |
| Wat de leverancier per teruggeleverde kWh inhoudt op de marktprijs. | home | 255 |
| Wijzigingen verwerpen ↔ | home | 491 |
| Woning | home | 367 |
| Woning en aansluiting | home | 373 |
| al all-in is, wordt ongewijzigd gebruikt. Bij de bron zelf geef je aan | home | 437 |
| betaalt; laat het leeg als je het niet weet, dan toont de coach geen | home | 272 |
| de klant werkelijk betaalt. | home | 208 |
| deze woning niet saldeert; de omslag gaat daarna vanzelf. | home | 281 |
| die de kale marktprijs levert wordt daarmee omgerekend; een bron die | home | 436 |
| formulier is opnieuw geladen met de actuele gegevens, zodat je ↔ | home | 767 |
| geen enkel apparaat aan. De andere bedieningsniveaus staan hier al wel, | home | 483 |
| geschatte besparing in plaats van een bedrag dat op een aanname rust. | home | 273 |
| maandbedrag niet om: alleen de opslag per kWh hoort hier. | home | 227 |
| maandstaffel om. Vul 0 in als deze aansluiting geen terugleverkosten | home | 271 |
| maar niet aan de woninggegevens. Je invoer staat er nog; druk | home | 774 |
| maar zijn nog niet beschikbaar. | home | 484 |
| marktprijs levert; die wordt hiermee naar een all-in prijs omgerekend. | home | 216 |
| niet omgerekend. | home | 246 |
| niet overschrijft wat je niet gezien hebt. ↔ | home | 768 |
| opnieuw op Opslaan om hem te bewaren. ↔ | home | 775 |
| vergoed krijgt. Geen marktprijs en geen percentage: dit veld wordt | home | 245 |
| welke van de twee het is. | home | 438 |
| ze om verder te gaan. ↔ | home | 838 |
| zonder naam ↔ | home | 601 |
| zonder naam ↔ | home | 630 |

## `custom_components/domotiapp_energy/frontend/tabs/installation.js`

| Tekst | Waar | Regel |
|---|---|---|
| Installatie | installation | 29 |

## `custom_components/domotiapp_energy/frontend/tabs/logbook.js`

| Tekst | Waar | Regel |
|---|---|---|
| Advies herberekend | logbook | 20 |
| Apparaat toegevoegd ↔ | logbook | 18 |
| Apparaat verwijderd ↔ | logbook | 19 |
| Bezig met wissen… | logbook | 135 |
| Bron niet beschikbaar ↔ | logbook | 21 |
| Configuratie gewijzigd | logbook | 17 |
| Configuratieprobleem | logbook | 25 |
| Fout ↔ | logbook | 33 |
| Gelukt | logbook | 31 |
| Het logboek is gewist. | logbook | 139 |
| Het logboek is leeg. Hier komt te staan wat DomotiApp Energy | logbook | 59 |
| Info | logbook | 30 |
| Logboek ↔ | logbook | 38 |
| Logboek ↔ | logbook | 43 |
| Logboek wissen ↔ | logbook | 46 |
| Logboek wissen ↔ | logbook | 151 |
| Ongeldige meting ↔ | logbook | 22 |
| Piekrisico gesignaleerd | logbook | 23 |
| Waarschuwing ↔ | logbook | 32 |
| Weet je zeker dat je het logboek wilt wissen? De gebeurtenissen | logbook | 153 |
| Wissen | logbook | 155 |
| Zonneoverschot gesignaleerd | logbook | 24 |
| zijn daarna weg. De configuratie zelf verandert niet. | logbook | 154 |

## `custom_components/domotiapp_energy/frontend/tabs/overview.js`

| Tekst | Waar | Regel |
|---|---|---|
| Actief | overview | 351 |
| Actuele energieprijs ↔ | overview | 215 |
| Actuele situatie | overview | 182 |
| Advies ↔ | overview | 245 |
| Alle gegevens voor een betrouwbaar advies zijn ingevuld. ↔ | overview | 424 |
| Apparaten die nu draaien | overview | 221 |
| Datakwaliteit | overview | 152 |
| De stroomprijs is op dit moment laag, dus er is geen duur verbruik om | overview | 78 |
| Energiebronnen om je slimme meter of omvormer te koppelen. | overview | 368 |
| Energiescore | overview | 148 |
| Er is nog geen cijfer, omdat de installatie nog niet compleet is. | overview | 23 |
| Er is nu opwek, maar geen apparaat of batterij die verbruik kan | overview | 56 |
| Er zijn nog geen energiebronnen gekoppeld. Ga naar het tabblad | overview | 367 |
| Er zijn op dit moment geen waarschuwingen. | overview | 303 |
| Fout ↔ | overview | 351 |
| Geen bruikbare prijsbron | overview | 315 |
| Geen cijfer | overview | 150 |
| Het prijsmoment telt niet mee zolang de lage en de hoge prijsdrempel | overview | 104 |
| Het prijsmoment telt niet mee, want bij een vast tarief is het ene | overview | 101 |
| Het prijsmoment telt niet mee, want de actuele prijs is op dit moment | overview | 107 |
| Het prijsmoment telt niet mee, want de stroom is nu goedkoop en er is | overview | 110 |
| Het tabblad Energiecoach laat zien wat er ontbreekt. | overview | 24 |
| Het tarief is altijd gelijk en er zijn geen zonnepanelen, dus er is | overview | 37 |
| Het vermogen van je thuisbatterij kan niet uitgelezen worden. Een | overview | 463 |
| Je omvormer levert op dit moment geen waarde, dus het | overview | 477 |
| Je panelen leveren op dit moment niets en de stroomprijs is laag. Er | overview | 63 |
| Je panelen leveren op dit moment niets, en bij een vast tarief is het | overview | 71 |
| Je panelen leveren op dit moment, maar terugleveren levert je meer op | overview | 45 |
| Laatste berekening ↔ | overview | 176 |
| Laden… | overview | 351 |
| Negatief betekent teruglevering aan het net. | overview | 431 |
| Netvermogen | overview | 183 |
| Niet beschikbaar ↔ | overview | 17 |
| Nog geen advies berekend ↔ | overview | 494 |
| Nog geen prijs bekend — koppel een prijsbron of vul het vaste leveringstarief in | overview | 316 |
| Nog niet berekend ↔ | overview | 177 |
| Nog niet ingesteld | overview | 16 |
| Op dit moment | overview | 129 |
| Overzicht | overview | 118 |
| Percentage van maximum | overview | 208 |
| Status | overview | 175 |
| Thuisverbruik | overview | 136 |
| Vast leveringstarief, zoals ingevuld bij Woning. | overview | 332 |
| Vast leveringstarief, zoals ingevuld bij Woning. De gekoppelde prijsbron bepaalt dit bedrag niet, maar neemt het over zodra dit veld leeg is of het contract dynamisch wordt. | overview | 331 |
| Waarschuwing ↔ | overview | 287 |
| Waarschuwingen | overview | 250 |
| Zelfbenutting | overview | 204 |
| Zodra er een energiebron gekoppeld is, verschijnt hier het hoofdadvies. ↔ | overview | 497 |
| Zolang de lage en de hoge prijsdrempel niet zijn ingevuld, is niet te | overview | 30 |
| Zonnebenutting telt niet mee, want deze woning heeft geen zonnepanelen. ↔ | overview | 88 |
| Zonnebenutting telt niet mee, want er is geen apparaat of batterij die | overview | 95 |
| Zonnebenutting telt niet mee, want je panelen leveren op dit moment niets. ↔ | overview | 90 |
| Zonnebenutting telt niet mee, want zonder netmeting is niet te zien | overview | 92 |
| Zonnebenutting telt niet mee: terugleveren levert je op dit moment meer | overview | 98 |
| Zonneoverschot | overview | 191 |
| Zonneproductie | overview | 187 |
| batterij die laadt of ontlaadt verschuift wat er van het net | overview | 464 |
| bepalen of dit een duur moment is. Vul ze in bij Installatie. | overview | 31 |
| bij Energiebronnen. | overview | 479 |
| dan de stroom je kost. Zelf verbruiken zou je nu geld kosten, dus er | overview | 46 |
| datakwaliteit is nog niet compleet. Het tabblad Energiecoach | overview | 422 |
| de batterij om dit op te lossen. | overview | 467 |
| dus geen duur verbruik om te vermijden. | overview | 111 |
| ene moment niet beter dan het andere. Er is nu dus niets te verbeteren. | overview | 72 |
| geen moment dat beter is dan een ander. Er valt daarom niets te | overview | 38 |
| hoeveel van je opwek je zelf gebruikt. | overview | 93 |
| is nu dus geen overschot om te benutten en geen duur verbruik om te | overview | 64 |
| is voordeliger. | overview | 48 |
| komt, dus het thuisverbruik is niet te berekenen en het | overview | 465 |
| laat zien welke. | overview | 423 |
| moment niet duurder dan het andere. | overview | 102 |
| niet uit te lezen. | overview | 108 |
| niet zijn ingevuld. Vul ze in bij Installatie. | overview | 105 |
| op dan de stroom je kost, dus je opwek zelf gebruiken zou je geld kosten. | overview | 99 |
| op dit moment | overview | 149 |
| optimaliseren. Het advies blijft gewoon werken. | overview | 39 |
| te vermijden. | overview | 79 |
| thuisverbruik is niet te berekenen. Controleer de zonnebron | overview | 478 |
| valt aan je opwek niets te benutten. De coach zegt hetzelfde: wachten | overview | 47 |
| verbruik naar dit moment kan verplaatsen. | overview | 96 |
| verplaatsen. Er valt daarom niets te benutten dat nu niet al gebeurt. | overview | 57 |
| zonneoverschot kan te hoog zijn. Koppel de vermogenssensor van | overview | 466 |

## `custom_components/domotiapp_energy/frontend/tabs/preferences.js`

| Tekst | Waar | Regel |
|---|---|---|
| Aantal adviezen | preferences | 81 |
| Advies met een berekende besparing bóven nul maar onder dit bedrag | preferences | 68 |
| Adviseer een apparaat wanneer er genoeg eigen opwek is. | preferences | 47 |
| Alleen van toepassing bij een dynamisch contract; bij een vast tarief | preferences | 54 |
| Bezig met opslaan… ↔ | preferences | 283 |
| De voorkeuren zijn intussen ergens anders gewijzigd. Het | preferences | 312 |
| De voorkeuren zijn opgeslagen. | preferences | 298 |
| Een venster over middernacht is het normale geval: 22:00 tot 07:00. | preferences | 31 |
| Er is intussen ergens anders iets aan de configuratie gewijzigd, ↔ | preferences | 319 |
| Geschatte besparing tonen | preferences | 92 |
| Hier blijven ↔ | preferences | 190 |
| Hoeveel adviezen er hoogstens tegelijk getoond worden. | preferences | 82 |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Sla ze op, of verwerp ↔ | preferences | 378 |
| Mijn voorkeuren | preferences | 141 |
| Minimale besparing | preferences | 64 |
| Op prijs adviseren | preferences | 52 |
| Opslaan ↔ | preferences | 184 |
| Stille uren | preferences | 147 |
| Stille uren tot | preferences | 38 |
| Stille uren van | preferences | 23 |
| Technische onderbouwing tonen | preferences | 87 |
| Tussen deze tijden raadt DomotiApp Energy aan om te wachten met | preferences | 29 |
| Verwerpen en verdergaan ↔ | preferences | 189 |
| Wanneer een advies de moeite waard is | preferences | 149 |
| Wat je te zien krijgt | preferences | 150 |
| Wat weegt mee | preferences | 148 |
| Wijzigingen verwerpen ↔ | preferences | 185 |
| Zonneoverschot benutten | preferences | 46 |
| formulier is opnieuw geladen met de actuele gegevens, zodat je ↔ | preferences | 313 |
| lawaaiige apparaten. Het advies verdwijnt niet, het zegt tot hoe laat. | preferences | 30 |
| maar niet aan je voorkeuren. Je invoer staat er nog; druk | preferences | 320 |
| niet overschrijft wat je niet gezien hebt. ↔ | preferences | 314 |
| nul uitkomt zolang de saldering loopt. | preferences | 71 |
| opnieuw op Opslaan om hem te bewaren. ↔ | preferences | 321 |
| piek, ontbrekende gegevens — blijft altijd staan, net als advies dat op | preferences | 70 |
| wordt er nooit op prijs geadviseerd. | preferences | 55 |
| wordt niet getoond. Advies zonder berekenbare besparing — veiligheid, | preferences | 69 |
| ze om verder te gaan. ↔ | preferences | 379 |

## `custom_components/domotiapp_energy/frontend/tabs/sources.js`

| Tekst | Waar | Regel |
|---|---|---|
| ${source.name \|\| ↔ | sources | 855 |
| ${source.name \|\| ↔ | sources | 880 |
| % — procent | sources | 100 |
| A — ampère | sources | 95 |
| Aan- en uitschakelen ↔ | sources | 106 |
| Aansturing ↔ | sources | 460 |
| Aansturing uitgesloten voor deze installatie ↔ | sources | 384 |
| Aansturing uitsluiten | sources | 60 |
| Actuele energieprijs ↔ | sources | 32 |
| Actuele terugleververgoeding | sources | 33 |
| Afname van het net | sources | 238 |
| Algemeen verbruik | sources | 37 |
| Alleen registreren: DomotiApp Energy stuurt in deze versie niets aan. | sources | 378 |
| Annuleren ↔ | sources | 545 |
| Annuleren ↔ | sources | 731 |
| Bekijken | sources | 581 |
| Bewerken ↔ | sources | 560 |
| Bewerken ↔ | sources | 581 |
| Bezig met opslaan… ↔ | sources | 780 |
| Bezig met verwijderen… ↔ | sources | 847 |
| Bron | sources | 441 |
| Bron toevoegen | sources | 477 |
| Compleet. ↔ | sources | 642 |
| De all-in prijs die de klant betaalt | sources | 180 |
| De configuratie is intussen ergens anders gewijzigd. Er is niets ↔ | sources | 862 |
| De eenheid waarin deze entiteit meet. | sources | 346 |
| De entiteit die de actuele zonneproductie meldt, niet de dagopbrengst. | sources | 318 |
| De entiteit die het laad- of ontlaadvermogen meldt, niet de laadtoestand. | sources | 329 |
| De entiteit die het totale huishoudelijke verbruik meldt. | sources | 330 |
| De entiteit met de prijs van dit moment. Hieronder geef je aan of dat | sources | 320 |
| De entiteit met de prijzen van de komende uren. | sources | 326 |
| De entiteit met de terugleververgoeding van dit moment. Gebruik dit | sources | 323 |
| De entiteit met de verwachte opbrengst. | sources | 327 |
| De entiteit waar deze bron uit gelezen wordt. | sources | 332 |
| De kale marktprijs, exclusief belasting en opslag | sources | 186 |
| De kale marktprijs, vóór inhouding van de leverancier | sources | 185 |
| De status van de entiteit | sources | 273 |
| De vergoeding die de klant werkelijk krijgt | sources | 179 |
| Deze energiebron is intussen ergens anders verwijderd. Je invoer | sources | 758 |
| Deze energiebron is intussen ook ergens anders gewijzigd. Je invoer | sources | 765 |
| Dit brontype is nog niet in gebruik. DomotiApp Energy rekent alleen met | sources | 73 |
| Een afspraak met de klant, los van wat deze bron zou kunnen. | sources | 385 |
| Een attribuut van de entiteit | sources | 274 |
| Een positieve waarde betekent | sources | 233 |
| Een uitgeschakelde bron wordt nergens in meegerekend. | sources | 139 |
| Eenheid ↔ | sources | 56 |
| Eenheid ↔ | sources | 292 |
| Energiebron | sources | 509 |
| Energiebron bewerken | sources | 658 |
| Energiebron toevoegen | sources | 658 |
| Energiebron verwijderen | sources | 878 |
| Energiebronnen ↔ | sources | 469 |
| Energiebronnen ↔ | sources | 474 |
| Entiteit ↔ | sources | 48 |
| Entiteit ↔ | sources | 149 |
| Entiteit ↔ | sources | 230 |
| Entiteit voor afname ↔ | sources | 49 |
| Entiteit voor afname ↔ | sources | 249 |
| Entiteit voor teruglevering ↔ | sources | 50 |
| Entiteit voor teruglevering ↔ | sources | 254 |
| Er is intussen ergens anders iets aan de configuratie gewijzigd, maar ↔ | sources | 770 |
| Eén waarde met een plus- en minteken | sources | 216 |
| Geen eenheid | sources | 101 |
| Gescheiden afname en teruglevering | sources | 220 |
| Hoe meet deze meter? ↔ | sources | 51 |
| Hoe meet deze meter? ↔ | sources | 208 |
| Ingeschakeld ↔ | sources | 47 |
| Ingeschakeld ↔ | sources | 138 |
| Intern geldt voor een thuisbatterij: positief is laden — de woning | sources | 692 |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Verwerp je ze, ↔ | sources | 905 |
| Kies expliciet. Zonder deze keuze wordt de prijs niet gebruikt, omdat | sources | 170 |
| Kies expliciet. Zonder deze keuze wordt de vergoeding niet | sources | 167 |
| Laadstroom instellen ↔ | sources | 108 |
| Let op de tekenconventie: positief betekent hier laden — de woning | sources | 356 |
| Meestal niet nodig: gebruik hierboven "een positieve waarde betekent". | sources | 362 |
| Naam ↔ | sources | 45 |
| Naam ↔ | sources | 127 |
| Naam van het attribuut ↔ | sources | 55 |
| Naam van het attribuut ↔ | sources | 284 |
| Naamloze bron | sources | 577 |
| Netmeter | sources | 30 |
| Niets aanvinken betekent "niet opgegeven", niet "kan niets". | sources | 379 |
| Nog geen energiebronnen. Koppel je slimme meter, omvormer, prijsbron | sources | 491 |
| Noteer waarom, zodat dit later terug te vinden is. ↔ | sources | 396 |
| Notities ↔ | sources | 62 |
| Notities ↔ | sources | 196 |
| Notities ↔ | sources | 464 |
| Opslaan ↔ | sources | 544 |
| Prijsverwachting | sources | 34 |
| Reden ↔ | sources | 61 |
| Reden ↔ | sources | 393 |
| Schaalfactor ↔ | sources | 57 |
| Schaalfactor ↔ | sources | 300 |
| Sluiten ↔ | sources | 731 |
| Soort bron ↔ | sources | 46 |
| Soort bron ↔ | sources | 130 |
| Teken omdraaien ↔ | sources | 58 |
| Teken omdraaien ↔ | sources | 306 |
| Terug naar het formulier ↔ | sources | 908 |
| Teruglevering aan het net | sources | 239 |
| Thuisbatterij ↔ | sources | 36 |
| Uitgeschakeld — wordt niet meegerekend. | sources | 611 |
| Uitlezen ↔ | sources | 105 |
| Vermenigvuldiger vóór de eenheidsconversie. Standaard 1. | sources | 301 |
| Vermogensgrens instellen ↔ | sources | 107 |
| Verwerpen ↔ | sources | 907 |
| Verwijderen ↔ | sources | 561 |
| Voor een prijs: EUR/kWh of ct/kWh. ↔ | sources | 338 |
| Voor een prijs: EUR/kWh of ct/kWh. ↔ | sources | 339 |
| Voor een vermogen: W of kW. ↔ | sources | 340 |
| Voor een vermogen: W of kW. ↔ | sources | 341 |
| Voor een vermogen: W of kW. ↔ | sources | 342 |
| Voor een verwachte opbrengst meestal Wh of kWh. | sources | 343 |
| W — watt | sources | 93 |
| Waarde uitlezen uit ↔ | sources | 54 |
| Waarde uitlezen uit ↔ | sources | 268 |
| Wat betekent een positieve waarde? | sources | 52 |
| Wat er gemeten wordt | sources | 443 |
| Wat kan deze bron behalve uitlezen? | sources | 376 |
| Wat kan deze bron? | sources | 59 |
| Wat levert deze bron? ↔ | sources | 53 |
| Wat levert deze bron? ↔ | sources | 159 |
| Wh — wattuur | sources | 96 |
| Wijzigingen verwerpen? ↔ | sources | 903 |
| Zet aan wanneer deze sensor het tegenovergestelde teken rapporteert. | sources | 364 |
| Zoals jij hem vaststelt: de eenheid van de entiteit zelf wordt nooit | sources | 347 |
| Zonder deze keuze wordt de netmeter niet gebruikt. | sources | 209 |
| Zonnepanelen | sources | 31 |
| Zonverwachting | sources | 35 |
| alleen bij een dynamisch teruglevercontract; bij een vast bedrag vul | sources | 324 |
| als je hem terug wilt. | sources | 760 |
| bewaard, maar er wordt op dit moment niets mee gedaan. | sources | 75 |
| ct/kWh — cent per kilowattuur | sources | 99 |
| dan zijn ze weg. ↔ | sources | 906 |
| de kale marktprijs of de all-in prijs is. | sources | 321 |
| deze schakelaar dan aan. | sources | 358 |
| die je bij Woning invult; er komt geen energiebelasting of btw bij. | sources | 169 |
| een kale marktprijs en een all-in prijs sterk verschillen. | sources | 171 |
| gebruikt om te converteren. | sources | 348 |
| gebruikt. Een kale marktprijs wordt omgerekend met de inhouding | sources | 168 |
| geen reden genoteerd ↔ | sources | 638 |
| het huidige moment en leest geen verwachtingen. De koppeling blijft | sources | 74 |
| je dat in bij Woning. | sources | 325 |
| kW — kilowatt | sources | 94 |
| kWh — kilowattuur | sources | 97 |
| niet aan deze bron. Je invoer staat er nog; druk opnieuw op Opslaan | sources | 771 |
| of thuisbatterij om DomotiApp Energy iets te laten meten. | sources | 492 |
| om hem te bewaren. | sources | 772 |
| rapporteert en gebruik zo nodig "teken omdraaien". | sources | 694 |
| staat er nog; als je nu opslaat, vervangt hij die andere wijziging. ↔ | sources | 766 |
| staat hier nog, maar opslaan lukt niet meer; maak hem opnieuw aan | sources | 759 |
| verbruikt — en negatief is ontladen. Controleer wat deze sensor | sources | 693 |
| verbruikt — en negatief ontladen. Meldt deze sensor het andersom, zet | sources | 357 |
| verwijderd; de lijst is opnieuw geladen. ↔ | sources | 863 |
| verwijderen? De metingen van deze bron tellen daarna nergens meer mee. | sources | 881 |
| zonder naam ↔ | sources | 790 |
| €/kWh — euro per kilowattuur | sources | 98 |

## `custom_components/domotiapp_energy/panel.py`

| Tekst | Waar | Regel |
|---|---|---|
| Panel %s is already registered | async_register_panel | 57 |

## `custom_components/domotiapp_energy/storage.py`

| Tekst | Waar | Regel |
|---|---|---|
| Bron niet beschikbaar ↔ | _async_report_failures | 335 |
| De energiebron '{...}' heeft een onbekend type ('{...}') en is uitgeschakeld. Kies een geldig type om de bron weer te gebruiken. | async_report_invalid_rows | 264 |
| De energiebron '{...}' kon niet worden uitgelezen: de entiteit '{...}' bestaat niet of levert op dit moment geen waarde. (reden: {...}) | _async_report_failures | 337 |
| De energiebron '{...}' leverde geen bruikbare meetwaarde. Controleer bij de entiteit '{...}' de gekozen waardebron, het attribuut en de eenheid. (reden: {...}) | _async_report_failures | 344 |
| Er zijn {...} ingeschakelde bronnen van het type '{...}'. Deze waarden zijn niet op te tellen en er is niet te bepalen welke de juiste is, dus geen van beide wordt gebruikt. Schakel er één uit of verwijder er één. | async_report_invalid_rows | 242 |
| Het apparaat '{...}' heeft een onbekend type ('{...}') en is uitgeschakeld. Kies een geldig type om het apparaat weer te gebruiken. | async_report_invalid_rows | 283 |
| Meerdere bronnen van hetzelfde type | async_report_invalid_rows | 241 |
| Multiple enabled sources of type %r; none of them is used ↔ | async_report_invalid_rows | 236 |
| Onbekend apparaattype | async_report_invalid_rows | 282 |
| Onbekend brontype | async_report_invalid_rows | 263 |
| Ongeldige meting ↔ | _async_report_failures | 342 |

## `custom_components/domotiapp_energy/validators.py`

| Tekst | Waar | Regel |
|---|---|---|
| Begin en einde van de stille uren mogen niet gelijk zijn. | validate_preferences | 982 |
| De begin- en eindtijd van het gereed-venster mogen niet gelijk zijn. | _validate_time_window | 825 |
| De begin- en eindtijd van het verbod mogen niet gelijk zijn. | _validate_no_run_window | 880 |
| De duur | validate_device_profile | 671 |
| De energiebelasting kan niet negatief zijn. | validate_home_profile | 360 |
| De hoge prijsgrens moet boven de lage prijsgrens liggen. | _validate_price_thresholds | 428 |
| De hoofdzekering moet tussen {...} en {...} ampère liggen. | validate_home_profile | 315 |
| De minimale besparing kan niet negatief zijn. | validate_preferences | 961 |
| De prijsbron levert de kale marktprijs. Vul de energiebelasting en de opslag van de leverancier per kWh in; zonder die twee is de all-in prijs niet te berekenen en wordt de prijs niet gebruikt. | _validate_price_components | 1045 |
| De schaalfactor moet groter zijn dan 0. | validate_energy_source | 506 |
| De terugleverprijsbron levert de kale marktprijs. Vul in wat de leverancier per teruggeleverde kWh inhoudt; zonder dat bedrag is de vergoeding niet te berekenen en wordt de bron niet gebruikt. Vul 0 in als de leverancier niets inhoudt. | _validate_feed_in_components | 1081 |
| De waarschuwingsgrens moet tussen {...} en {...} procent liggen. | validate_home_profile | 331 |
| Deze bron levert een prijs, maar de eenheid staat op '{...}'. Kies EUR/kWh of ct/kWh. | _validate_unit_matches_type | 466 |
| Deze bron meet vermogen, maar de eenheid staat op '{...}'. Kies W of kW. Let op: veel slimme-meterintegraties tonen vooral de meterstand in kWh; die is een totaal en geen vermogen, en levert een netbelasting die honderden keren te hoog is. | _validate_unit_matches_type | 452 |
| Deze twee eisen zijn niet allebei te halen: het apparaat mag niet draaien op het moment dat het zou moeten starten om op tijd klaar te zijn. Verruim het verbod, of verzet de tijd waarop het klaar moet zijn. | _validate_no_run_window | 889 |
| Dit bedieningsniveau vraagt om aansturing, maar er is geen besturingsmogelijkheid aangevinkt. Controleer wat deze apparatuur werkelijk ondersteunt. | _validate_control | 721 |
| Een cyclus van 24 uur of langer is niet te combineren met een gereed-venster: er is dan geen starttijd op de klok te bepalen. | _validate_time_window | 807 |
| Gebruik een geldige tijd in de vorm uu:mm. ↔ | _validate_time_window | 781 |
| Gebruik een geldige tijd in de vorm uu:mm. ↔ | _validate_no_run_window | 859 |
| Gebruik een geldige tijd in de vorm uu:mm. ↔ | validate_preferences | 972 |
| Geef aan of een positieve waarde afname of teruglevering betekent. | _validate_grid_meter | 609 |
| Geef aan wat deze bron levert: de kale marktprijs of de all-in prijs die de klant betaalt. Zonder die keuze wordt de prijs niet gebruikt. | _validate_price_source | 568 |
| Geef aan wat deze bron levert: de kale marktprijs of de vergoeding die de klant werkelijk krijgt. Zonder die keuze wordt de terugleververgoeding niet gebruikt. | _validate_price_source | 562 |
| Het apparaattype '{...}' is niet bekend. Kies een geldig type. | validate_device_profile | 641 |
| Het brontype '{...}' is niet bekend. Kies een geldig type. | validate_energy_source | 484 |
| Het btw-percentage moet tussen {...} en {...} liggen. | validate_home_profile | 350 |
| Het energieverbruik per cyclus | validate_device_profile | 669 |
| Het ingevulde netvermogen ligt boven het theoretische maximum van {...} W ({...} x 230 V x {...} A). Controleer de hoofdzekering. | _validate_max_grid_power | 402 |
| Het maximale netvermogen moet groter zijn dan 0 W. | _validate_max_grid_power | 390 |
| Het minimale zonneoverschot kan niet negatief zijn. | validate_home_profile | 369 |
| Het nominale vermogen | validate_device_profile | 665 |
| Kies 1 of 3 fasen. | validate_home_profile | 304 |
| Kies een geldig bedieningsniveau. | validate_device_profile | 660 |
| Kies een geldige eenheid. | validate_energy_source | 495 |
| Kies een geldige prioriteit. | validate_device_profile | 651 |
| Kies een vast of dynamisch contract. | validate_home_profile | 341 |
| Kies hoe de netmeter meet: één ondertekende waarde of gescheiden afname en teruglevering. | _validate_grid_meter | 588 |
| Koppel de entiteit die de afname meet. | _validate_grid_meter | 619 |
| Koppel de entiteit die de teruglevering meet. | _validate_grid_meter | 627 |
| Koppel een entiteit aan deze bron. ↔ | validate_energy_source | 533 |
| Koppel een entiteit aan deze bron. ↔ | _validate_grid_meter | 601 |
| Noteer waarom aansturing hier is uitgesloten, zodat de reden later terug te vinden is. | _validate_control | 735 |
| Toon minimaal {...} en maximaal {...} adviezen. | validate_preferences | 951 |
| Voor deze installatie is aansturing uitgesloten. Kies 'alleen monitoren' of 'alleen adviseren'. | _validate_control | 708 |
| Vul de naam in van het attribuut dat uitgelezen moet worden. | validate_energy_source | 518 |
| {...} kan niet negatief zijn. | validate_device_profile | 678 |

## `custom_components/domotiapp_energy/websocket_api.py`

| Tekst | Waar | Regel |
|---|---|---|
| Apparaat gewijzigd | handle_devices_update | 860 |
| Apparaat toegevoegd ↔ | handle_devices_create | 822 |
| Apparaat verwijderd ↔ | handle_devices_delete | 896 |
| Bediening gewijzigd | handle_devices_set_operation | 969 |
| De adviesvoorkeuren zijn bijgewerkt. | handle_preferences_update | 663 |
| De configuratie is inmiddels gewijzigd. De actuele gegevens zijn opnieuw opgehaald. | _send_revision_conflict | 337 |
| De configuratie kon niet worden opgeslagen. | _async_write | 317 |
| De energiebron '{...}' is bijgewerkt. | handle_sources_update | 745 |
| De energiebron '{...}' is toegevoegd. | handle_sources_create | 707 |
| De energiebron '{...}' is verwijderd. | handle_sources_delete | 781 |
| De instellingen van '{...}' zijn bijgewerkt. | handle_devices_set_operation | 970 |
| De woninggegevens zijn bijgewerkt. | handle_home_update | 601 |
| Deze energiebron ↔ | _apply | 736 |
| Deze energiebron ↔ | _apply | 771 |
| Dit apparaat ↔ | _apply | 852 |
| Dit apparaat ↔ | _apply | 887 |
| Dit apparaat ↔ | _apply | 933 |
| Dit apparaat bestaat niet. | handle_devices_set_ready | 1004 |
| Dit apparaat heeft een onbekend type en is buiten werking gesteld. | _apply | 943 |
| DomotiApp Energy is niet geladen. | _async_get_data | 283 |
| Energiebron gewijzigd | handle_sources_update | 744 |
| Energiebron toegevoegd | handle_sources_create | 706 |
| Energiebron verwijderd | handle_sources_delete | 780 |
| Er bestaat al een apparaat met dit ID. | _apply | 812 |
| Er bestaat al een energiebron met dit ID. | _apply | 696 |
| Gebruik een datum in de vorm jjjj-mm-dd, of null als deze woning niet saldeert. | _iso_date | 186 |
| Gebruik een datum in de vorm jjjj-mm-dd, of null. | _iso_date | 190 |
| Het apparaat '{...}' is bijgewerkt. | handle_devices_update | 861 |
| Het apparaat '{...}' is toegevoegd. | handle_devices_create | 823 |
| Het apparaat '{...}' is verwijderd. | handle_devices_delete | 897 |
| Voorkeuren gewijzigd | handle_preferences_update | 662 |
| Woninggegevens gewijzigd | handle_home_update | 600 |
| {...} bestaat niet. | _find | 430 |


## Engelse regels

| Tekst | Waar |
|---|---|
| DomotiApp Energy has been removed. The energy configuration is kept in %s under .storage/, so adding the integration again restores it. Delete that file to start over | `custom_components/domotiapp_energy/__init__.py:145` |
| Clearing ready flag for %r: %s reports %r | `custom_components/domotiapp_energy/coordinator.py:406` |
| No alternative coach provider is available in this release | `custom_components/domotiapp_energy/engine/providers.py:250` |
| Dropping ready flag for %r: %r is not a timestamp | `custom_components/domotiapp_energy/runtime_store.py:83` |
| Migrating %s from schema %s.%s to %s.%s | `custom_components/domotiapp_energy/storage.py:102` |
| Configuration accessed before it was loaded | `custom_components/domotiapp_energy/storage.py:149` |
| Could not read %s, continuing with a default configuration | `custom_components/domotiapp_energy/storage.py:197` |
| Energy source %s has unrecognised type %r and is disabled | `custom_components/domotiapp_energy/storage.py:257` |
| Device profile %s has unrecognised type %r and is disabled | `custom_components/domotiapp_energy/storage.py:276` |
| Energy source %s could not be read from %s (%s) | `custom_components/domotiapp_energy/storage.py:327` |
| Could not persist a configuration change | `custom_components/domotiapp_energy/websocket_api.py:313` |
