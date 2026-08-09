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

**802 Nederlandse teksten**, waarvan 109 op meer dan één plek. En 9 Engelse regels om na te lopen.


## `custom_components/domotiapp_energy/const.py`

| Tekst | Waar | Regel |
|---|---|---|
| Attention | module | 985 |
| Current advice | module | 982 |
| Data quality | module | 979 |
| DomotiApp | module | 21 |
| DomotiApp Energy ↔ | module | 18 |
| DomotiApp Energy ↔ | module | 39 |
| Energy Coach | module | 22 |
| Grid power | module | 980 |
| Home consumption | module | 984 |
| Mijn woning | module | 29 |
| Peak risk | module | 983 |
| Score | module | 978 |
| Solar surplus | module | 981 |

## `custom_components/domotiapp_energy/coordinator.py`

| Tekst | Waar | Regel |
|---|---|---|
| Advies opnieuw berekend | async_recalculate | 230 |
| De woning {...} {...}% van het ingestelde maximale netvermogen. Dat ligt op of boven de waarschuwingsgrens van {...}%. | _async_log_findings | 348 |
| Er is {...} W zonneoverschot beschikbaar. | _async_log_findings | 367 |
| Het energieadvies is opnieuw berekend. | async_recalculate | 231 |
| Linked entity %s changed | _handle_tracked_state_event | 241 |
| No linked entities to watch | async_rebuild_state_listener | 204 |
| Piekbelasting gesignaleerd | _async_log_findings | 347 |
| Watching %s linked entities | async_rebuild_state_listener | 207 |
| Zonneoverschot beschikbaar ↔ | _async_log_findings | 366 |
| levert terug met ↔ | _async_log_findings | 344 |
| {...} recalculate after configuration change | _handle_configuration_change | 270 |
| {...} safety recalculation | async_start | 187 |

## `custom_components/domotiapp_energy/engine/advisor.py`

| Tekst | Waar | Regel |
|---|---|---|
| Aanvullende gegevens nodig | _advise_missing_data | 205 |
| Bijna te laat om op tijd klaar te zijn | _advise_deadline | 591 |
| De actuele energieprijs is relatief hoog. Stel flexibel energiegebruik indien mogelijk uit. | _advise_price | 655 |
| De actuele energieprijs is relatief laag. Flexibele apparaten kunnen nu voordeliger worden gebruikt. | _advise_price | 637 |
| De actuele energiesituatie vraagt momenteel niet om een aanpassing. | _neutral_advice | 673 |
| De teruglevering ligt dicht bij de ingestelde maximale woningbelasting. Schakel indien mogelijk juist extra verbruikers in om de belasting te verlagen. Let op: terugleveren levert je op dit moment meer op dan zelf verbruiken, dus dit kost je geld. | _advise_peak_risk | 251 |
| De teruglevering ligt dicht bij de ingestelde maximale woningbelasting. Schakel indien mogelijk juist extra verbruikers in om het overschot zelf te benutten. | _advise_peak_risk | 245 |
| Dit is een gunstig moment om {...} te gebruiken. | _surplus_message | 417 |
| Er is momenteel zonneoverschot beschikbaar. | _surplus_message | 416 |
| Er is momenteel zonneoverschot beschikbaar. {...} maakt geluid en het zijn stille uren tot {...}. Wacht daarmee tot na {...}, of pas de stille uren aan bij Mijn voorkeuren. | _quiet_hours_message | 383 |
| Geen actie nodig | _neutral_advice | 672 |
| Het actuele netvermogen ligt dicht bij de ingestelde maximale woningbelasting. Stel extra grootverbruikers indien mogelijk uit. | _advise_peak_risk | 274 |
| Hoeveel dit oplevert is niet te berekenen zolang de terugleverkosten niet zijn ingevuld — vul ze in bij Woning, of zet ze op 0 als deze aansluiting ze niet betaalt. | _why_no_amount | 539 |
| Hoeveel dit oplevert is niet te berekenen zolang de terugleverprijsbron geen bruikbare waarde geeft. Controleer die bij Energiebronnen. | _why_no_amount | 528 |
| Hoeveel dit oplevert is niet te berekenen zolang er geen actuele prijs is. Controleer de prijsbron bij Energiebronnen. | _why_no_amount | 513 |
| Hoeveel dit oplevert is niet te berekenen zonder de energie per cyclus van {...} — vul die in bij Apparaten. | _why_no_amount | 502 |
| Hoeveel dit oplevert is niet te berekenen zonder de terugleververgoeding — vul die in bij Woning, of koppel een terugleverprijsbron. | _why_no_amount | 533 |
| Hoeveel dit oplevert is niet te berekenen zonder het vaste leveringstarief — vul dat in bij Woning. | _why_no_amount | 517 |
| Hoge energieprijs | _advise_price | 653 |
| Lage energieprijs | _advise_price | 635 |
| Netbelasting hoog | _advise_peak_risk | 272 |
| Start {...} nu als hij om {...} klaar moet zijn. | _advise_deadline | 593 |
| Teruglevering hoog | _advise_peak_risk | 260 |
| Vul de ontbrekende energiegegevens aan om een betrouwbaar advies te ontvangen. | _advise_missing_data | 207 |
| Zonneoverschot beschikbaar ↔ | _advise_solar_surplus | 339 |
| Zonneoverschot, maar het zijn stille uren | _advise_solar_surplus | 324 |
| {...} Zelf verbruiken levert nu echter minder op dan terugleveren: {...} nu gebruiken kost naar schatting {...} ten opzichte van het overschot terugleveren. Wachten tot de terugleververgoeding lager ligt is voordeliger. | _surplus_message | 431 |
| {...} {...} Het levert op dit moment niets extra op, maar het kost ook niets. | _surplus_message | 449 |
| {...} {...} Zolang de salderingsregeling geldt levert dit geen extra besparing op, maar het overschot zelf gebruiken blijft de meest efficiënte keuze. | _surplus_message | 442 |

## `custom_components/domotiapp_energy/engine/calculator.py`

| Tekst | Waar | Regel |
|---|---|---|
| Multiple enabled sources of type %r; none of them is used ↔ | _read_sources | 288 |

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
| DomotiApp Energy is niet geladen. Controleer de integratie in Instellingen. | api | 104 |
| Er is een onbekende fout opgetreden. ↔ | api | 98 |
| Er is een onbekende fout opgetreden. ↔ | api | 109 |
| Je hebt geen rechten voor deze actie. | api | 107 |

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
| Deze gegevens worden beheerd door DomotiTech. | roles | 47 |

## `custom_components/domotiapp_energy/frontend/domotiapp-energy-panel.js`

| Tekst | Waar | Regel |
|---|---|---|
| DomotiApp Energy tabbladen | domotiapp-energy-panel | 113 |
| Gegevens laden… | domotiapp-energy-panel | 235 |

## `custom_components/domotiapp_energy/frontend/tabs/coach.js`

| Tekst | Waar | Regel |
|---|---|---|
| Advies ↔ | coach | 34 |
| Advies ↔ | coach | 35 |
| Advies ↔ | coach | 139 |
| Alle gegevens voor een betrouwbaar advies zijn ingevuld. ↔ | coach | 283 |
| Bezig met berekenen… | coach | 197 |
| Deze vraag is nog niet beantwoord. Bereken opnieuw zodra er gegevens | coach | 189 |
| Energiecoach | coach | 58 |
| Er is op dit moment geen aanvullend advies. | coach | 88 |
| Geschatte besparing | coach | 68 |
| Het advies is opnieuw berekend. | coach | 202 |
| Hoe is mijn energiescore berekend? | coach | 30 |
| Hoofdadvies | coach | 65 |
| Is er risico op piekbelasting? | coach | 28 |
| Kan ik nu het beste een apparaat gebruiken? | coach | 27 |
| Kies een vraag; het antwoord verschijnt in beeld. | coach | 104 |
| Laatste berekening ↔ | coach | 70 |
| Niet te berekenen | coach | 68 |
| Nog geen advies berekend ↔ | coach | 225 |
| Nog niet berekend ↔ | coach | 70 |
| Onbekend | coach | 69 |
| Ontbrekende gegevens | coach | 94 |
| Opnieuw berekenen | coach | 72 |
| Overige adviezen | coach | 86 |
| Probleem | coach | 37 |
| Reden ↔ | coach | 69 |
| Vraag het de coach | coach | 100 |
| Waarom krijg ik dit advies? | coach | 26 |
| Waarschuwing ↔ | coach | 36 |
| Welke gegevens ontbreken nog? | coach | 29 |
| Zodra er een energiebron gekoppeld is, verschijnt hier het hoofdadvies. ↔ | coach | 228 |
| gekoppeld zijn. | coach | 190 |

## `custom_components/domotiapp_energy/frontend/tabs/devices.js`

| Tekst | Waar | Regel |
|---|---|---|
| "Alleen monitoren" legt vast dat dat zo moet blijven, ook als dat | devices | 465 |
| "alleen adviseren" om het weer mee te laten doen. | devices | 459 |
| "alleen monitoren" wordt als adviseren behandeld. | devices | 471 |
| "mag hierna niet meer draaien". | devices | 380 |
| ${device.name \|\| ↔ | devices | 1204 |
| ${device.name \|\| ↔ | devices | 1228 |
| Aan- en uitschakelen ↔ | devices | 83 |
| Aansturing ↔ | devices | 693 |
| Aansturing uitgesloten voor deze installatie ↔ | devices | 501 |
| Airconditioning | devices | 45 |
| Alleen adviseren ↔ | devices | 76 |
| Alleen monitoren | devices | 75 |
| Alleen registreren: er wordt niets aangestuurd. Niets aanvinken | devices | 495 |
| Annuleren ↔ | devices | 810 |
| Apparaat ↔ | devices | 667 |
| Apparaat ↔ | devices | 752 |
| Apparaat bewerken | devices | 990 |
| Apparaat toevoegen ↔ | devices | 715 |
| Apparaat toevoegen ↔ | devices | 990 |
| Apparaat verwijderen | devices | 1226 |
| Apparaten ↔ | devices | 707 |
| Apparaten ↔ | devices | 712 |
| Automatisch aansturen ↔ | devices | 78 |
| Batterijniveau | devices | 137 |
| Bedieningsniveau ↔ | devices | 479 |
| Bedieningsniveau ↔ | devices | 612 |
| Bewerken ↔ | devices | 836 |
| Bewerken ↔ | devices | 868 |
| Bezig met opslaan… ↔ | devices | 1118 |
| Bezig met verwijderen… ↔ | devices | 1196 |
| Bij meerdere kandidaten wint de hoogste prioriteit. | devices | 272 |
| Compleet. ↔ | devices | 973 |
| Dagen ↔ | devices | 423 |
| Dagen ↔ | devices | 598 |
| De aanvoertemperatuur van de warmtepomp. | devices | 130 |
| De configuratie is intussen ergens anders gewijzigd. Er is niets ↔ | devices | 1211 |
| De configuratie is intussen ergens anders gewijzigd. Je wijzigingen ↔ | devices | 1156 |
| De energie van een gemiddelde draaiperiode. | devices | 348 |
| De energie van één cyclus. | devices | 351 |
| De energie van één droogbeurt. | devices | 347 |
| De energie van één programma, bijvoorbeeld 1,0 tot 1,5 kWh. | devices | 345 |
| De energie van één wasbeurt. | devices | 346 |
| De entiteit die zegt of het apparaat aan staat of draait. | devices | 105 |
| De laadtoestand van de auto, als de laadpaal die meldt. | devices | 141 |
| De laadtoestand van de thuisbatterij, in procenten. | devices | 140 |
| De meterstand of het verbruik van dit apparaat. | devices | 117 |
| De ruimtetemperatuur die deze airco regelt. | devices | 132 |
| De watertemperatuur in de boiler. | devices | 131 |
| Deze ingevulde gegevens worden voor dit apparaat niet meer | devices | 1044 |
| Dinsdag | devices | 91 |
| Dit apparaat is compleet: alles wat de datakwaliteit vraagt is ingevuld. | devices | 1037 |
| Dit apparaat krijgt geen advies zolang het niet verplaatsbaar is. | devices | 464 |
| DomotiApp Energy adviseert in deze versie alleen; alles behalve | devices | 470 |
| DomotiApp Energy rekent zelf terug wanneer het apparaat uiterlijk | devices | 375 |
| Donderdag | devices | 93 |
| Droger | devices | 44 |
| Duur van een cyclus ↔ | devices | 318 |
| Duur van een cyclus ↔ | devices | 605 |
| Duur van een laadsessie | devices | 318 |
| Een afspraak met de klant, los van wat dit apparaat kan. | devices | 502 |
| Een schatting van een typische laadbeurt, bijvoorbeeld 10 kWh voor | devices | 341 |
| Een uitgeschakeld apparaat krijgt geen advies. | devices | 260 |
| Elektrische boiler | devices | 41 |
| Energie per cyclus ↔ | devices | 310 |
| Energie per cyclus ↔ | devices | 604 |
| Energie per laadsessie | devices | 310 |
| Energieverbruikentiteit | devices | 115 |
| Het actuele vermogen van dit apparaat. | devices | 111 |
| Het elektrische opgenomen vermogen, niet het thermische. | devices | 332 |
| Het hoogste vermogen waarmee deze paal kan laden — niet wat de auto | devices | 329 |
| Het laad- of ontlaadvermogen van de batterij. | devices | 331 |
| Het vermogen tijdens gebruik. | devices | 335 |
| Het vermogen van het verwarmingselement. | devices | 333 |
| Hoe lang de lopende cyclus nog duurt. | devices | 123 |
| Hoog | devices | 70 |
| In minuten, voor een typische laadbeurt. Wordt getoetst aan het | devices | 359 |
| In minuten. Wordt getoetst aan het tijdvenster hieronder. | devices | 363 |
| Ingeschakeld ↔ | devices | 259 |
| Instellen | devices | 868 |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Verwerp je ze, ↔ | devices | 1253 |
| Klaar uiterlijk om ↔ | devices | 396 |
| Klaar uiterlijk om ↔ | devices | 596 |
| Koppelingen | devices | 688 |
| Kritiek | devices | 71 |
| Laadpaal | devices | 38 |
| Laadstroom instellen ↔ | devices | 85 |
| Laag | devices | 68 |
| Laat beide tijden leeg als er geen venster is; het apparaat mag dan op | devices | 370 |
| Locatie | devices | 265 |
| Maakt geluid ↔ | devices | 435 |
| Maakt geluid ↔ | devices | 607 |
| Maandag | devices | 90 |
| Maximaal laadvermogen | devices | 304 |
| Naam ↔ | devices | 251 |
| Naamloos apparaat | devices | 853 |
| Niet eerder klaar dan ↔ | devices | 410 |
| Niet eerder klaar dan ↔ | devices | 597 |
| Nog geen apparaten. Voeg de apparaten toe waarover DomotiApp Energy | devices | 734 |
| Nog geen vermogenssensor gekoppeld — dit apparaat wordt alleen | devices | 949 |
| Nog nodig voor een compleet apparaat: | devices | 1033 |
| Nominaal vermogen ↔ | devices | 304 |
| Nominaal vermogen ↔ | devices | 603 |
| Normaal | devices | 69 |
| Noteer waarom, zodat dit later terug te vinden is. ↔ | devices | 511 |
| Notities ↔ | devices | 288 |
| Notities ↔ | devices | 702 |
| Op "alleen monitoren" krijgt dit apparaat geen advies. Zet het op | devices | 458 |
| Op welke dagen dit apparaat mag draaien. | devices | 424 |
| Opslaan ↔ | devices | 809 |
| Opslaan mag ook zonder — het apparaat telt dan alleen nog niet | devices | 1035 |
| Optioneel. Handig voor was die niet uren nat mag blijven liggen: | devices | 415 |
| Overig, alleen meten | devices | 48 |
| Overig, inplanbaar | devices | 47 |
| Prioriteit ↔ | devices | 271 |
| Prioriteit ↔ | devices | 606 |
| Reden ↔ | devices | 510 |
| Reden ↔ | devices | 599 |
| Resterende tijd | devices | 121 |
| Soort apparaat | devices | 254 |
| Statusentiteit | devices | 103 |
| Telt niet mee voor de datakwaliteit. | devices | 962 |
| Temperatuursensor | devices | 127 |
| Terug naar het formulier ↔ | devices | 1256 |
| Thuisbatterij ↔ | devices | 39 |
| Uitgeschakeld — krijgt geen advies. | devices | 919 |
| Uitlezen ↔ | devices | 82 |
| Vaatwasser | devices | 42 |
| Verbruik | devices | 672 |
| Vermogensentiteit | devices | 109 |
| Vermogensgrens instellen ↔ | devices | 84 |
| Verplaatsbaar in de tijd ↔ | devices | 443 |
| Verplaatsbaar in de tijd ↔ | devices | 613 |
| Verwerpen ↔ | devices | 1255 |
| Verwijderen ↔ | devices | 837 |
| Vragen om goedkeuring ↔ | devices | 77 |
| Vrijdag | devices | 94 |
| Vul hierboven een duur in, dan rekent DomotiApp Energy terug wanneer | devices | 378 |
| Waar staat het? Alleen om het terug te herkennen. | devices | 266 |
| Wanneer het mag draaien | devices | 677 |
| Warmtepomp | devices | 40 |
| Wasmachine | devices | 43 |
| Wat kan dit apparaat? | devices | 493 |
| Wijzigingen verwerpen? ↔ | devices | 1251 |
| Woensdag | devices | 92 |
| Zaterdag | devices | 95 |
| Zet het apparaattype, "verplaatsbaar in de tijd" of het | devices | 1046 |
| Zondag | devices | 96 |
| Zonder dit getal is er geen besparing te berekenen. | devices | 352 |
| Zwembadpomp | devices | 46 |
| alleen die hebben een tijdvenster nodig. | devices | 447 |
| bedieningsniveau terug om ze te behouden. | devices | 1047 |
| betekent "niet opgegeven", niet "kan niets". | devices | 496 |
| betrouwbaarheid daarom op "gemiddeld". | devices | 344 |
| dan zijn ze weg. ↔ | devices | 1254 |
| een dagelijkse rit. Exact kan niet: DomotiApp Energy weet niet hoe | devices | 342 |
| elk uur. Een venster telt wel mee voor de datakwaliteit, omdat het advies | devices | 371 |
| energie per cyclus | devices | 236 |
| er gerichter van wordt. | devices | 372 |
| er vandaag van afneemt. | devices | 330 |
| geen reden genoteerd ↔ | devices | 936 |
| gemeten, en er valt nu niets te meten. | devices | 950 |
| het apparaat uiterlijk moet starten. Zonder duur geldt dit alleen als | devices | 379 |
| later verandert. | devices | 466 |
| leeg de auto is, dus het advies rekent met dit getal en houdt zijn | devices | 343 |
| mag adviseren, met hun vermogen, verbruik per cyclus en tijdvenster. | devices | 735 |
| mee voor de datakwaliteit. | devices | 1036 |
| moet starten om dit te halen. | devices | 376 |
| nominaal vermogen | devices | 235 |
| tijd ná "klaar uiterlijk om", dan loopt het venster door tot de | devices | 417 |
| tijdvenster hieronder. | devices | 360 |
| verwijderd; de lijst is opnieuw geladen. ↔ | devices | 1212 |
| verwijderen? Er wordt daarna niet meer over geadviseerd. | devices | 1229 |
| volgende dag — 22:00 tot 06:00 is het normale geval. | devices | 418 |
| zet hier bijvoorbeeld 06:00 als je hem om 07:00 uithaalt. Ligt deze | devices | 416 |
| zijn niet opgeslagen; de lijst is opnieuw geladen. ↔ | devices | 1157 |
| zonder naam ↔ | devices | 1142 |

## `custom_components/domotiapp_energy/frontend/tabs/home.js`

| Tekst | Waar | Regel |
|---|---|---|
| (marktprijs + opslag + energiebelasting) × (1 + btw). Een prijsbron | home | 416 |
| 1 fase | home | 42 |
| 3 fasen | home | 43 |
| Aantal fasen | home | 37 |
| Adviesinstellingen | home | 356 |
| Alleen adviseren ↔ | home | 449 |
| Alleen nodig als je terugleverprijsbron de kale marktprijs levert. | home | 237 |
| Automatisch aansturen ↔ | home | 451 |
| Bedieningsniveau ↔ | home | 357 |
| Bedieningsniveau ↔ | home | 444 |
| Besparen | home | 302 |
| Bezig met opslaan… ↔ | home | 717 |
| Comfort | home | 300 |
| Contract en prijzen | home | 355 |
| Contractsoort | home | 173 |
| De configuratie is intussen ergens anders gewijzigd. Je wijzigingen ↔ | home | 738 |
| De salderingsregeling stopt landelijk op 1 januari 2027. Laat leeg als | home | 261 |
| De woninggegevens zijn opgeslagen. | home | 729 |
| DomotiApp Energy meet, rekent en adviseert; het stuurt in deze versie | home | 463 |
| DomotiApp Energy rekent overal met de all-in prijs: | home | 415 |
| Dynamisch tarief | home | 179 |
| Een bedrag per kWh, exclusief btw — géén vast maandbedrag. Reken een | home | 207 |
| Een bedrag per kWh, exclusief btw. Nodig zodra een prijsbron de kale | home | 196 |
| Een bedrag per teruggeleverde kWh — géén vast maandbedrag. Reken een | home | 251 |
| Energiebelasting | home | 194 |
| Gebalanceerd | home | 301 |
| Het all-in bedrag per kWh, inclusief energiebelasting en btw — dus wat | home | 188 |
| Het btw-percentage over de leveringsprijs. In Nederland 21%. | home | 216 |
| Het vaste bedrag dat de klant per teruggeleverde kWh daadwerkelijk | home | 225 |
| Het vermogen waarboven DomotiApp Energy waarschuwt. | home | 57 |
| Hier blijven ↔ | home | 480 |
| Hoge prijsgrens (all-in) | home | 278 |
| Hoofdzekering per fase | home | 50 |
| In ampère, zoals op de zekering staat. | home | 51 |
| Inhouding leverancier op teruglevering | home | 232 |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Sla ze op, of verwerp ↔ | home | 801 |
| Lage prijsgrens (all-in) | home | 267 |
| Maximaal netvermogen | home | 56 |
| Maximaal zelf verbruiken | home | 303 |
| Minimaal zonneoverschot | home | 289 |
| Naam van de woning | home | 34 |
| Opslaan ↔ | home | 471 |
| Opslag leverancier | home | 202 |
| Percentage van het maximale netvermogen. | home | 63 |
| Saldering geldt tot | home | 259 |
| Standaardstrategie | home | 295 |
| Terugleverkosten | home | 244 |
| Terugleververgoeding (all-in) | home | 221 |
| Vanaf dit overschot adviseert DomotiApp Energy een apparaat. | home | 290 |
| Vast leveringstarief (all-in) | home | 186 |
| Vast tarief | home | 178 |
| Vergelijk met de all-in prijs, niet met de kale marktprijs van je ↔ | home | 272 |
| Vergelijk met de all-in prijs, niet met de kale marktprijs van je ↔ | home | 280 |
| Verwerpen en verdergaan ↔ | home | 479 |
| Vragen om goedkeuring ↔ | home | 450 |
| Vul 0 in als er niets wordt ingehouden. | home | 238 |
| Waarschuwen vanaf | home | 62 |
| Wat de leverancier per teruggeleverde kWh inhoudt op de marktprijs. | home | 236 |
| Wijzigingen verwerpen ↔ | home | 472 |
| Woning | home | 348 |
| Woning en aansluiting | home | 354 |
| actuele gegevens. ↔ | home | 740 |
| al all-in is, wordt ongewijzigd gebruikt. Bij de bron zelf geef je aan | home | 418 |
| betaalt; laat het leeg als je het niet weet, dan toont de coach geen | home | 253 |
| de klant werkelijk betaalt. | home | 189 |
| deze woning niet saldeert; de omslag gaat daarna vanzelf. | home | 262 |
| die de kale marktprijs levert wordt daarmee omgerekend; een bron die | home | 417 |
| geen enkel apparaat aan. De andere bedieningsniveaus staan hier al wel, | home | 464 |
| geschatte besparing in plaats van een bedrag dat op een aanname rust. | home | 254 |
| maandbedrag niet om: alleen de opslag per kWh hoort hier. | home | 208 |
| maandstaffel om. Vul 0 in als deze aansluiting geen terugleverkosten | home | 252 |
| maar zijn nog niet beschikbaar. | home | 465 |
| marktprijs levert; die wordt hiermee naar een all-in prijs omgerekend. | home | 197 |
| niet omgerekend. | home | 227 |
| vergoed krijgt. Geen marktprijs en geen percentage: dit veld wordt | home | 226 |
| welke van de twee het is. | home | 419 |
| ze om verder te gaan. ↔ | home | 802 |
| zijn niet opgeslagen; het formulier is opnieuw geladen met de ↔ | home | 739 |
| zonder naam ↔ | home | 582 |
| zonder naam ↔ | home | 611 |

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
| Actief | overview | 338 |
| Actuele energieprijs ↔ | overview | 215 |
| Actuele situatie | overview | 182 |
| Advies ↔ | overview | 245 |
| Alle gegevens voor een betrouwbaar advies zijn ingevuld. ↔ | overview | 411 |
| Apparaten die nu draaien | overview | 221 |
| Datakwaliteit | overview | 152 |
| De stroomprijs is op dit moment laag, dus er is geen duur verbruik om | overview | 78 |
| Energiebronnen om je slimme meter of omvormer te koppelen. | overview | 355 |
| Energiescore | overview | 148 |
| Er is nog geen cijfer, omdat de installatie nog niet compleet is. | overview | 23 |
| Er is nu opwek, maar geen apparaat of batterij die verbruik kan | overview | 56 |
| Er zijn nog geen energiebronnen gekoppeld. Ga naar het tabblad | overview | 354 |
| Er zijn op dit moment geen waarschuwingen. | overview | 303 |
| Fout ↔ | overview | 338 |
| Geen bruikbare prijsbron | overview | 320 |
| Geen cijfer | overview | 150 |
| Het prijsmoment telt niet mee zolang de lage en de hoge prijsdrempel | overview | 104 |
| Het prijsmoment telt niet mee, want bij een vast tarief is het ene | overview | 101 |
| Het prijsmoment telt niet mee, want de actuele prijs is op dit moment | overview | 107 |
| Het prijsmoment telt niet mee, want de stroom is nu goedkoop en er is | overview | 110 |
| Het tabblad Energiecoach laat zien wat er ontbreekt. | overview | 24 |
| Het tarief is altijd gelijk en er zijn geen zonnepanelen, dus er is | overview | 37 |
| Het vermogen van je thuisbatterij kan niet uitgelezen worden. Een | overview | 450 |
| Je omvormer levert op dit moment geen waarde, dus het | overview | 464 |
| Je panelen leveren op dit moment niets en de stroomprijs is laag. Er | overview | 63 |
| Je panelen leveren op dit moment niets, en bij een vast tarief is het | overview | 71 |
| Je panelen leveren op dit moment, maar terugleveren levert je meer op | overview | 45 |
| Laatste berekening ↔ | overview | 176 |
| Laden… | overview | 338 |
| Negatief betekent teruglevering aan het net. | overview | 418 |
| Netvermogen | overview | 183 |
| Niet beschikbaar ↔ | overview | 17 |
| Niet van toepassing bij een vast contract | overview | 312 |
| Nog geen advies berekend ↔ | overview | 481 |
| Nog niet berekend ↔ | overview | 177 |
| Nog niet ingesteld | overview | 16 |
| Op dit moment | overview | 129 |
| Overzicht | overview | 118 |
| Percentage van maximum | overview | 208 |
| Status | overview | 175 |
| Thuisverbruik | overview | 136 |
| Waarschuwing ↔ | overview | 287 |
| Waarschuwingen | overview | 250 |
| Zelfbenutting | overview | 204 |
| Zodra er een energiebron gekoppeld is, verschijnt hier het hoofdadvies. ↔ | overview | 484 |
| Zolang de lage en de hoge prijsdrempel niet zijn ingevuld, is niet te | overview | 30 |
| Zonnebenutting telt niet mee, want deze woning heeft geen zonnepanelen. ↔ | overview | 88 |
| Zonnebenutting telt niet mee, want er is geen apparaat of batterij die | overview | 95 |
| Zonnebenutting telt niet mee, want je panelen leveren op dit moment niets. ↔ | overview | 90 |
| Zonnebenutting telt niet mee, want zonder netmeting is niet te zien | overview | 92 |
| Zonnebenutting telt niet mee: terugleveren levert je op dit moment meer | overview | 98 |
| Zonneoverschot | overview | 191 |
| Zonneproductie | overview | 187 |
| batterij die laadt of ontlaadt verschuift wat er van het net | overview | 451 |
| bepalen of dit een duur moment is. Vul ze in bij Installatie. | overview | 31 |
| bij Energiebronnen. | overview | 466 |
| dan de stroom je kost. Zelf verbruiken zou je nu geld kosten, dus er | overview | 46 |
| datakwaliteit is nog niet compleet. Het tabblad Energiecoach | overview | 409 |
| de batterij om dit op te lossen. | overview | 454 |
| dus geen duur verbruik om te vermijden. | overview | 111 |
| ene moment niet beter dan het andere. Er is nu dus niets te verbeteren. | overview | 72 |
| geen moment dat beter is dan een ander. Er valt daarom niets te | overview | 38 |
| hoeveel van je opwek je zelf gebruikt. | overview | 93 |
| is nu dus geen overschot om te benutten en geen duur verbruik om te | overview | 64 |
| is voordeliger. | overview | 48 |
| komt, dus het thuisverbruik is niet te berekenen en het | overview | 452 |
| laat zien welke. | overview | 410 |
| moment niet duurder dan het andere. | overview | 102 |
| niet uit te lezen. | overview | 108 |
| niet zijn ingevuld. Vul ze in bij Installatie. | overview | 105 |
| op dan de stroom je kost, dus je opwek zelf gebruiken zou je geld kosten. | overview | 99 |
| op dit moment | overview | 149 |
| optimaliseren. Het advies blijft gewoon werken. | overview | 39 |
| te vermijden. | overview | 79 |
| thuisverbruik is niet te berekenen. Controleer de zonnebron | overview | 465 |
| valt aan je opwek niets te benutten. De coach zegt hetzelfde: wachten | overview | 47 |
| verbruik naar dit moment kan verplaatsen. | overview | 96 |
| verplaatsen. Er valt daarom niets te benutten dat nu niet al gebeurt. | overview | 57 |
| zonneoverschot kan te hoog zijn. Koppel de vermogenssensor van | overview | 453 |

## `custom_components/domotiapp_energy/frontend/tabs/preferences.js`

| Tekst | Waar | Regel |
|---|---|---|
| Aantal adviezen | preferences | 81 |
| Advies met een berekende besparing bóven nul maar onder dit bedrag | preferences | 68 |
| Adviseer een apparaat wanneer er genoeg eigen opwek is. | preferences | 47 |
| Alleen van toepassing bij een dynamisch contract; bij een vast tarief | preferences | 54 |
| Bezig met opslaan… ↔ | preferences | 283 |
| De configuratie is intussen ergens anders gewijzigd. Je wijzigingen ↔ | preferences | 304 |
| De voorkeuren zijn opgeslagen. | preferences | 298 |
| Een venster over middernacht is het normale geval: 22:00 tot 07:00. | preferences | 31 |
| Geschatte besparing tonen | preferences | 92 |
| Hier blijven ↔ | preferences | 190 |
| Hoeveel adviezen er hoogstens tegelijk getoond worden. | preferences | 82 |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Sla ze op, of verwerp ↔ | preferences | 362 |
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
| actuele gegevens. ↔ | preferences | 306 |
| lawaaiige apparaten. Het advies verdwijnt niet, het zegt tot hoe laat. | preferences | 30 |
| nul uitkomt zolang de saldering loopt. | preferences | 71 |
| piek, ontbrekende gegevens — blijft altijd staan, net als advies dat op | preferences | 70 |
| wordt er nooit op prijs geadviseerd. | preferences | 55 |
| wordt niet getoond. Advies zonder berekenbare besparing — veiligheid, | preferences | 69 |
| ze om verder te gaan. ↔ | preferences | 363 |
| zijn niet opgeslagen; het formulier is opnieuw geladen met de ↔ | preferences | 305 |

## `custom_components/domotiapp_energy/frontend/tabs/sources.js`

| Tekst | Waar | Regel |
|---|---|---|
| ${source.name \|\| ↔ | sources | 830 |
| ${source.name \|\| ↔ | sources | 855 |
| % — procent | sources | 99 |
| A — ampère | sources | 94 |
| Aan- en uitschakelen ↔ | sources | 105 |
| Aansturing ↔ | sources | 459 |
| Aansturing uitgesloten voor deze installatie ↔ | sources | 383 |
| Aansturing uitsluiten | sources | 59 |
| Actuele energieprijs ↔ | sources | 31 |
| Actuele terugleververgoeding | sources | 32 |
| Afname van het net | sources | 237 |
| Algemeen verbruik | sources | 36 |
| Alleen registreren: DomotiApp Energy stuurt in deze versie niets aan. | sources | 377 |
| Annuleren ↔ | sources | 544 |
| Annuleren ↔ | sources | 730 |
| Bekijken | sources | 580 |
| Bewerken ↔ | sources | 559 |
| Bewerken ↔ | sources | 580 |
| Bezig met opslaan… ↔ | sources | 757 |
| Bezig met verwijderen… ↔ | sources | 822 |
| Bron | sources | 440 |
| Bron toevoegen | sources | 476 |
| Compleet. ↔ | sources | 641 |
| De all-in prijs die de klant betaalt | sources | 179 |
| De configuratie is intussen ergens anders gewijzigd. Er is niets ↔ | sources | 837 |
| De configuratie is intussen ergens anders gewijzigd. Je wijzigingen ↔ | sources | 784 |
| De eenheid waarin deze entiteit meet. | sources | 345 |
| De entiteit die de actuele zonneproductie meldt, niet de dagopbrengst. | sources | 317 |
| De entiteit die het laad- of ontlaadvermogen meldt, niet de laadtoestand. | sources | 328 |
| De entiteit die het totale huishoudelijke verbruik meldt. | sources | 329 |
| De entiteit met de prijs van dit moment. Hieronder geef je aan of dat | sources | 319 |
| De entiteit met de prijzen van de komende uren. | sources | 325 |
| De entiteit met de terugleververgoeding van dit moment. Gebruik dit | sources | 322 |
| De entiteit met de verwachte opbrengst. | sources | 326 |
| De entiteit waar deze bron uit gelezen wordt. | sources | 331 |
| De kale marktprijs, exclusief belasting en opslag | sources | 185 |
| De kale marktprijs, vóór inhouding van de leverancier | sources | 184 |
| De status van de entiteit | sources | 272 |
| De vergoeding die de klant werkelijk krijgt | sources | 178 |
| Dit brontype is nog niet in gebruik. DomotiApp Energy rekent alleen met | sources | 72 |
| Een afspraak met de klant, los van wat deze bron zou kunnen. | sources | 384 |
| Een attribuut van de entiteit | sources | 273 |
| Een positieve waarde betekent | sources | 232 |
| Een uitgeschakelde bron wordt nergens in meegerekend. | sources | 138 |
| Eenheid ↔ | sources | 55 |
| Eenheid ↔ | sources | 291 |
| Energiebron | sources | 508 |
| Energiebron bewerken | sources | 657 |
| Energiebron toevoegen | sources | 657 |
| Energiebron verwijderen | sources | 853 |
| Energiebronnen ↔ | sources | 468 |
| Energiebronnen ↔ | sources | 473 |
| Entiteit ↔ | sources | 47 |
| Entiteit ↔ | sources | 148 |
| Entiteit ↔ | sources | 229 |
| Entiteit voor afname ↔ | sources | 48 |
| Entiteit voor afname ↔ | sources | 248 |
| Entiteit voor teruglevering ↔ | sources | 49 |
| Entiteit voor teruglevering ↔ | sources | 253 |
| Eén waarde met een plus- en minteken | sources | 215 |
| Geen eenheid | sources | 100 |
| Gescheiden afname en teruglevering | sources | 219 |
| Hoe meet deze meter? ↔ | sources | 50 |
| Hoe meet deze meter? ↔ | sources | 207 |
| Ingeschakeld ↔ | sources | 46 |
| Ingeschakeld ↔ | sources | 137 |
| Intern geldt voor een thuisbatterij: positief is laden — de woning | sources | 691 |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Verwerp je ze, ↔ | sources | 880 |
| Kies expliciet. Zonder deze keuze wordt de prijs niet gebruikt, omdat | sources | 169 |
| Kies expliciet. Zonder deze keuze wordt de vergoeding niet | sources | 166 |
| Laadstroom instellen ↔ | sources | 107 |
| Let op de tekenconventie: positief betekent hier laden — de woning | sources | 355 |
| Meestal niet nodig: gebruik hierboven "een positieve waarde betekent". | sources | 361 |
| Naam ↔ | sources | 44 |
| Naam ↔ | sources | 126 |
| Naam van het attribuut ↔ | sources | 54 |
| Naam van het attribuut ↔ | sources | 283 |
| Naamloze bron | sources | 576 |
| Netmeter | sources | 29 |
| Niets aanvinken betekent "niet opgegeven", niet "kan niets". | sources | 378 |
| Nog geen energiebronnen. Koppel je slimme meter, omvormer, prijsbron | sources | 490 |
| Noteer waarom, zodat dit later terug te vinden is. ↔ | sources | 395 |
| Notities ↔ | sources | 61 |
| Notities ↔ | sources | 195 |
| Notities ↔ | sources | 463 |
| Opslaan ↔ | sources | 543 |
| Prijsverwachting | sources | 33 |
| Reden ↔ | sources | 60 |
| Reden ↔ | sources | 392 |
| Schaalfactor ↔ | sources | 56 |
| Schaalfactor ↔ | sources | 299 |
| Sluiten ↔ | sources | 730 |
| Soort bron ↔ | sources | 45 |
| Soort bron ↔ | sources | 129 |
| Teken omdraaien ↔ | sources | 57 |
| Teken omdraaien ↔ | sources | 305 |
| Terug naar het formulier ↔ | sources | 883 |
| Teruglevering aan het net | sources | 238 |
| Thuisbatterij ↔ | sources | 35 |
| Uitgeschakeld — wordt niet meegerekend. | sources | 610 |
| Uitlezen ↔ | sources | 104 |
| Vermenigvuldiger vóór de eenheidsconversie. Standaard 1. | sources | 300 |
| Vermogensgrens instellen ↔ | sources | 106 |
| Verwerpen ↔ | sources | 882 |
| Verwijderen ↔ | sources | 560 |
| Voor een prijs: EUR/kWh of ct/kWh. ↔ | sources | 337 |
| Voor een prijs: EUR/kWh of ct/kWh. ↔ | sources | 338 |
| Voor een vermogen: W of kW. ↔ | sources | 339 |
| Voor een vermogen: W of kW. ↔ | sources | 340 |
| Voor een vermogen: W of kW. ↔ | sources | 341 |
| Voor een verwachte opbrengst meestal Wh of kWh. | sources | 342 |
| W — watt | sources | 92 |
| Waarde uitlezen uit ↔ | sources | 53 |
| Waarde uitlezen uit ↔ | sources | 267 |
| Wat betekent een positieve waarde? | sources | 51 |
| Wat er gemeten wordt | sources | 442 |
| Wat kan deze bron behalve uitlezen? | sources | 375 |
| Wat kan deze bron? | sources | 58 |
| Wat levert deze bron? ↔ | sources | 52 |
| Wat levert deze bron? ↔ | sources | 158 |
| Wh — wattuur | sources | 95 |
| Wijzigingen verwerpen? ↔ | sources | 878 |
| Zet aan wanneer deze sensor het tegenovergestelde teken rapporteert. | sources | 363 |
| Zoals jij hem vaststelt: de eenheid van de entiteit zelf wordt nooit | sources | 346 |
| Zonder deze keuze wordt de netmeter niet gebruikt. | sources | 208 |
| Zonnepanelen | sources | 30 |
| Zonverwachting | sources | 34 |
| alleen bij een dynamisch teruglevercontract; bij een vast bedrag vul | sources | 323 |
| bewaard, maar er wordt op dit moment niets mee gedaan. | sources | 74 |
| ct/kWh — cent per kilowattuur | sources | 98 |
| dan zijn ze weg. ↔ | sources | 881 |
| de kale marktprijs of de all-in prijs is. | sources | 320 |
| deze schakelaar dan aan. | sources | 357 |
| die je bij Woning invult; er komt geen energiebelasting of btw bij. | sources | 168 |
| een kale marktprijs en een all-in prijs sterk verschillen. | sources | 170 |
| gebruikt om te converteren. | sources | 347 |
| gebruikt. Een kale marktprijs wordt omgerekend met de inhouding | sources | 167 |
| geen reden genoteerd ↔ | sources | 637 |
| het huidige moment en leest geen verwachtingen. De koppeling blijft | sources | 73 |
| je dat in bij Woning. | sources | 324 |
| kW — kilowatt | sources | 93 |
| kWh — kilowattuur | sources | 96 |
| of thuisbatterij om DomotiApp Energy iets te laten meten. | sources | 491 |
| rapporteert en gebruik zo nodig "teken omdraaien". | sources | 693 |
| verbruikt — en negatief is ontladen. Controleer wat deze sensor | sources | 692 |
| verbruikt — en negatief ontladen. Meldt deze sensor het andersom, zet | sources | 356 |
| verwijderd; de lijst is opnieuw geladen. ↔ | sources | 838 |
| verwijderen? De metingen van deze bron tellen daarna nergens meer mee. | sources | 856 |
| zijn niet opgeslagen; de lijst is opnieuw geladen. ↔ | sources | 785 |
| zonder naam ↔ | sources | 767 |
| €/kWh — euro per kilowattuur | sources | 97 |

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
| Begin en einde van de stille uren mogen niet gelijk zijn. | validate_preferences | 852 |
| De begin- en eindtijd van het gereed-venster mogen niet gelijk zijn. | _validate_time_window | 776 |
| De duur | validate_device_profile | 663 |
| De energiebelasting kan niet negatief zijn. | validate_home_profile | 352 |
| De hoge prijsgrens moet boven de lage prijsgrens liggen. | _validate_price_thresholds | 420 |
| De hoofdzekering moet tussen {...} en {...} ampère liggen. | validate_home_profile | 307 |
| De minimale besparing kan niet negatief zijn. | validate_preferences | 831 |
| De prijsbron levert de kale marktprijs. Vul de energiebelasting en de opslag van de leverancier per kWh in; zonder die twee is de all-in prijs niet te berekenen en wordt de prijs niet gebruikt. | _validate_price_components | 899 |
| De schaalfactor moet groter zijn dan 0. | validate_energy_source | 498 |
| De terugleverprijsbron levert de kale marktprijs. Vul in wat de leverancier per teruggeleverde kWh inhoudt; zonder dat bedrag is de vergoeding niet te berekenen en wordt de bron niet gebruikt. Vul 0 in als de leverancier niets inhoudt. | _validate_feed_in_components | 935 |
| De waarschuwingsgrens moet tussen {...} en {...} procent liggen. | validate_home_profile | 323 |
| Deze bron levert een prijs, maar de eenheid staat op '{...}'. Kies EUR/kWh of ct/kWh. | _validate_unit_matches_type | 458 |
| Deze bron meet vermogen, maar de eenheid staat op '{...}'. Kies W of kW. Let op: veel slimme-meterintegraties tonen vooral de meterstand in kWh; die is een totaal en geen vermogen, en levert een netbelasting die honderden keren te hoog is. | _validate_unit_matches_type | 444 |
| Dit bedieningsniveau vraagt om aansturing, maar er is geen besturingsmogelijkheid aangevinkt. Controleer wat deze apparatuur werkelijk ondersteunt. | _validate_control | 712 |
| Gebruik een geldige tijd in de vorm uu:mm. ↔ | _validate_time_window | 752 |
| Gebruik een geldige tijd in de vorm uu:mm. ↔ | validate_preferences | 842 |
| Geef aan of een positieve waarde afname of teruglevering betekent. | _validate_grid_meter | 601 |
| Geef aan wat deze bron levert: de kale marktprijs of de all-in prijs die de klant betaalt. Zonder die keuze wordt de prijs niet gebruikt. | _validate_price_source | 560 |
| Geef aan wat deze bron levert: de kale marktprijs of de vergoeding die de klant werkelijk krijgt. Zonder die keuze wordt de terugleververgoeding niet gebruikt. | _validate_price_source | 554 |
| Het apparaat past niet binnen het opgegeven gereed-venster. | _validate_time_window | 787 |
| Het apparaattype '{...}' is niet bekend. Kies een geldig type. | validate_device_profile | 633 |
| Het brontype '{...}' is niet bekend. Kies een geldig type. | validate_energy_source | 476 |
| Het btw-percentage moet tussen {...} en {...} liggen. | validate_home_profile | 342 |
| Het energieverbruik per cyclus | validate_device_profile | 661 |
| Het ingevulde netvermogen ligt boven het theoretische maximum van {...} W ({...} x 230 V x {...} A). Controleer de hoofdzekering. | _validate_max_grid_power | 394 |
| Het maximale netvermogen moet groter zijn dan 0 W. | _validate_max_grid_power | 382 |
| Het minimale zonneoverschot kan niet negatief zijn. | validate_home_profile | 361 |
| Het nominale vermogen | validate_device_profile | 657 |
| Kies 1 of 3 fasen. | validate_home_profile | 296 |
| Kies een geldig bedieningsniveau. | validate_device_profile | 652 |
| Kies een geldige eenheid. | validate_energy_source | 487 |
| Kies een geldige prioriteit. | validate_device_profile | 643 |
| Kies een vast of dynamisch contract. | validate_home_profile | 333 |
| Kies hoe de netmeter meet: één ondertekende waarde of gescheiden afname en teruglevering. | _validate_grid_meter | 580 |
| Koppel de entiteit die de afname meet. | _validate_grid_meter | 611 |
| Koppel de entiteit die de teruglevering meet. | _validate_grid_meter | 619 |
| Koppel een entiteit aan deze bron. ↔ | validate_energy_source | 525 |
| Koppel een entiteit aan deze bron. ↔ | _validate_grid_meter | 593 |
| Noteer waarom aansturing hier is uitgesloten, zodat de reden later terug te vinden is. | _validate_control | 726 |
| Toon minimaal {...} en maximaal {...} adviezen. | validate_preferences | 821 |
| Voor deze installatie is aansturing uitgesloten. Kies 'alleen monitoren' of 'alleen adviseren'. | _validate_control | 699 |
| Vul de naam in van het attribuut dat uitgelezen moet worden. | validate_energy_source | 510 |
| {...} kan niet negatief zijn. | validate_device_profile | 670 |

## `custom_components/domotiapp_energy/websocket_api.py`

| Tekst | Waar | Regel |
|---|---|---|
| Apparaat gewijzigd | handle_devices_update | 786 |
| Apparaat toegevoegd ↔ | handle_devices_create | 748 |
| Apparaat verwijderd ↔ | handle_devices_delete | 822 |
| Bediening gewijzigd | handle_devices_set_operation | 895 |
| De adviesvoorkeuren zijn bijgewerkt. | handle_preferences_update | 589 |
| De configuratie is inmiddels gewijzigd. De actuele gegevens zijn opnieuw opgehaald. | _send_revision_conflict | 287 |
| De configuratie kon niet worden opgeslagen. | _async_write | 267 |
| De energiebron '{...}' is bijgewerkt. | handle_sources_update | 671 |
| De energiebron '{...}' is toegevoegd. | handle_sources_create | 633 |
| De energiebron '{...}' is verwijderd. | handle_sources_delete | 707 |
| De instellingen van '{...}' zijn bijgewerkt. | handle_devices_set_operation | 896 |
| De woninggegevens zijn bijgewerkt. | handle_home_update | 536 |
| Deze energiebron ↔ | _apply | 662 |
| Deze energiebron ↔ | _apply | 697 |
| Dit apparaat ↔ | _apply | 778 |
| Dit apparaat ↔ | _apply | 813 |
| Dit apparaat ↔ | _apply | 859 |
| Dit apparaat heeft een onbekend type en is buiten werking gesteld. | _apply | 869 |
| DomotiApp Energy is niet geladen. | _async_get_data | 233 |
| Energiebron gewijzigd | handle_sources_update | 670 |
| Energiebron toegevoegd | handle_sources_create | 632 |
| Energiebron verwijderd | handle_sources_delete | 706 |
| Er bestaat al een apparaat met dit ID. | _apply | 738 |
| Er bestaat al een energiebron met dit ID. | _apply | 622 |
| Het apparaat '{...}' is bijgewerkt. | handle_devices_update | 787 |
| Het apparaat '{...}' is toegevoegd. | handle_devices_create | 749 |
| Het apparaat '{...}' is verwijderd. | handle_devices_delete | 823 |
| Voorkeuren gewijzigd | handle_preferences_update | 588 |
| Woninggegevens gewijzigd | handle_home_update | 535 |
| {...} bestaat niet. | _find | 380 |


## Engelse regels

| Tekst | Waar |
|---|---|
| DomotiApp Energy has been removed. The energy configuration is kept in %s under .storage/, so adding the integration again restores it. Delete that file to start over | `custom_components/domotiapp_energy/__init__.py:134` |
| No alternative coach provider is available in this release | `custom_components/domotiapp_energy/engine/providers.py:250` |
| Migrating %s from schema %s.%s to %s.%s | `custom_components/domotiapp_energy/storage.py:102` |
| Configuration accessed before it was loaded | `custom_components/domotiapp_energy/storage.py:149` |
| Could not read %s, continuing with a default configuration | `custom_components/domotiapp_energy/storage.py:197` |
| Energy source %s has unrecognised type %r and is disabled | `custom_components/domotiapp_energy/storage.py:257` |
| Device profile %s has unrecognised type %r and is disabled | `custom_components/domotiapp_energy/storage.py:276` |
| Energy source %s could not be read from %s (%s) | `custom_components/domotiapp_energy/storage.py:327` |
| Could not persist a configuration change | `custom_components/domotiapp_energy/websocket_api.py:263` |
