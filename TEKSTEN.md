# Alle teksten die dit product kan tonen

**Gegenereerd door `scripts/extract_texts.py`. Niet met de hand bijwerken.**

Draai het script opnieuw na elke ronde die een zin toevoegt of herschrijft;
`tests/test_texts.py` faalt zolang dit bestand achterloopt. De diff van dit
bestand is wat een ronde aan de klant heeft toegevoegd, in zijn woorden.

## Hoe je dit leest

Gesorteerd per bestand, want dat is wat het script weet. De redactionele
indeling op zichtbaarheid komt terug wanneer het herschrijven begint — dan
is dit de invoer en niet de uitvoer.

**Geen regelnummers.** Die stonden hier tot 0.32.0 en maakten van deze
inventaris iets dat onderhouden moest worden in plaats van andersom: één
toegevoegde commentaarregel verschoof tientallen nummers en liet
`tests/test_texts.py` rood worden om een wijziging die geen tekst raakte.
Dat gebeurde tweemaal in één week. Een zin is met zijn eigen woorden te
vinden; het bestand en de context zeggen genoeg.

- **`{...}`** is een waarde die wordt ingevuld: een getal, een naam,
  een bedrag.
- **↔** staat achter een tekst die op meer dan één plek in de broncode staat.
  Die twee moeten samen herschreven worden of ze lopen uiteen.
- De **CSS** van het paneel is eruit gefilterd; dat is opmaak, geen taal.
- **Engelse regels staan apart**, onderaan. Een Engelse zin in dit product is
  een fout tenzij zij een identifier is: de UI is Nederlands (CLAUDE.md).

**948 Nederlandse teksten**, waarvan 126 op meer dan één plek. En 15 Engelse regels om na te lopen.


## `custom_components/domotiapp_energy/const.py`

| Tekst | Waar |
|---|---|
| Attention | module |
| Current advice | module |
| Data quality | module |
| DomotiApp | module |
| DomotiApp Energy ↔ | module |
| DomotiApp Energy ↔ | module |
| Energy Coach | module |
| Grid power | module |
| Home consumption | module |
| Mijn woning | module |
| Peak risk | module |
| Score | module |
| Self consumption | module |
| Solar surplus | module |

## `custom_components/domotiapp_energy/coordinator.py`

| Tekst | Waar |
|---|---|
| Advies opnieuw berekend | async_recalculate |
| De woning {...} {...}% van het ingestelde maximale netvermogen. Dat ligt op of boven de waarschuwingsgrens van {...}%. | _async_log_findings |
| Er is {...} W zonneoverschot beschikbaar. | _async_log_findings |
| Het energieadvies is opnieuw berekend. | async_recalculate |
| Linked entity %s changed | _handle_tracked_state_event |
| No linked entities to watch | async_rebuild_state_listener |
| Not reporting %s source failures: Home Assistant is %s | _failures_worth_reporting |
| Not reporting source %s (%s): %s | _failures_worth_reporting |
| Piekbelasting gesignaleerd | _async_log_findings |
| Watching %s linked entities | async_rebuild_state_listener |
| Zonneoverschot beschikbaar ↔ | _async_log_findings |
| levert terug met ↔ | _async_log_findings |
| {...} forget ready flags of deleted appliances | _handle_configuration_change |
| {...} recalculate after configuration change | _handle_configuration_change |
| {...} safety recalculation | async_start |

## `custom_components/domotiapp_energy/engine/advisor.py`

| Tekst | Waar |
|---|---|
| Aanvullende gegevens nodig | _advise_missing_data |
| Bijna te laat om op tijd klaar te zijn | _advise_deadline |
| De actuele energieprijs is relatief hoog. Stel flexibel energiegebruik indien mogelijk uit. | _advise_price |
| De actuele energieprijs is relatief laag. Flexibele apparaten kunnen nu voordeliger worden gebruikt. | _advise_price |
| De actuele energiesituatie vraagt momenteel niet om een aanpassing. | _neutral_advice |
| De teruglevering ligt dicht bij de ingestelde maximale woningbelasting. Schakel indien mogelijk juist extra verbruikers in om de belasting te verlagen. Let op: terugleveren levert je op dit moment meer op dan zelf verbruiken, dus dit kost je geld. | _advise_peak_risk |
| De teruglevering ligt dicht bij de ingestelde maximale woningbelasting. Schakel indien mogelijk juist extra verbruikers in om het overschot zelf te benutten. | _advise_peak_risk |
| Dit is een gunstig moment om {...} te gebruiken. ↔ | _surplus_message |
| Dit is een gunstig moment om {...} te gebruiken. ↔ | _modulating_surplus_message |
| Er is momenteel zonneoverschot beschikbaar, maar {...} mag tussen {...} en {...} niet draaien. Dat is bij de installatie zo ingesteld en staat los van je stille uren. Na {...} kan het weer. | _no_run_message |
| Er is momenteel zonneoverschot beschikbaar. ↔ | _surplus_message |
| Er is momenteel zonneoverschot beschikbaar. ↔ | _modulating_surplus_message |
| Er is momenteel zonneoverschot beschikbaar. {...} maakt geluid en het zijn stille uren tot {...}. Wacht daarmee tot na {...}, of pas de stille uren aan bij Mijn voorkeuren. | _quiet_hours_message |
| Geen actie nodig | _neutral_advice |
| Het actuele netvermogen ligt dicht bij de ingestelde maximale woningbelasting. Stel extra grootverbruikers indien mogelijk uit. | _advise_peak_risk |
| Hoeveel dit oplevert is niet te berekenen zolang de terugleverkosten niet zijn ingevuld — vul ze in bij Woning, of zet ze op 0 als deze aansluiting ze niet betaalt. | _why_no_margin |
| Hoeveel dit oplevert is niet te berekenen zolang de terugleverprijsbron geen bruikbare waarde geeft. Controleer die bij Energiebronnen. | _why_no_margin |
| Hoeveel dit oplevert is niet te berekenen zolang er geen actuele prijs is. Controleer de prijsbron bij Energiebronnen. | _why_no_margin |
| Hoeveel dit oplevert is niet te berekenen zonder de energie per cyclus van {...} — vul die in bij Apparaten. | _why_no_amount |
| Hoeveel dit oplevert is niet te berekenen zonder de energie per laadsessie van {...} — vul die in bij Apparaten. | _why_no_amount |
| Hoeveel dit oplevert is niet te berekenen zonder de terugleververgoeding — vul die in bij Woning, of koppel een terugleverprijsbron. | _why_no_margin |
| Hoeveel dit oplevert is niet te berekenen zonder het vaste leveringstarief — vul dat in bij Woning. | _why_no_margin |
| Hoeveel dit per uur oplevert is niet te berekenen zonder het maximale laadvermogen van {...} — vul dat in bij Apparaten. | _why_no_rate |
| Hoeveel dit per uur oplevert is niet te berekenen zonder het nominale vermogen van {...} — vul dat in bij Apparaten. | _why_no_rate |
| Hoge energieprijs | _advise_price |
| Lage energieprijs | _advise_price |
| Netbelasting hoog | _advise_peak_risk |
| Start {...} nu als hij om {...} klaar moet zijn. | _deadline_message |
| Start {...} nu om {...} te halen. | _deadline_message |
| Teruglevering hoog | _advise_peak_risk |
| Vul de ontbrekende energiegegevens aan om een betrouwbaar advies te ontvangen. | _advise_missing_data |
| Zonneoverschot beschikbaar ↔ | _advise_solar_surplus |
| Zonneoverschot, maar dit apparaat mag nu niet draaien | _advise_solar_surplus |
| Zonneoverschot, maar het zijn stille uren | _advise_solar_surplus |
| {...} Terugleveren levert op dit moment echter meer op dan zelf verbruiken: {...} laten doorlopen kost naar schatting {...} per uur ten opzichte van het overschot terugleveren. | _modulating_surplus_message |
| {...} Zelf verbruiken levert nu echter minder op dan terugleveren: {...} nu gebruiken kost naar schatting {...} ten opzichte van het overschot terugleveren. Wachten tot de terugleververgoeding lager ligt is voordeliger. | _surplus_message |
| {...} {...} Het levert op dit moment niets extra op, maar het kost ook niets. | _surplus_message |
| {...} {...} Zolang de salderingsregeling geldt levert dit geen extra besparing op, maar het overschot zelf gebruiken blijft de meest efficiënte keuze. | _surplus_message |

## `custom_components/domotiapp_energy/engine/calculator.py`

| Tekst | Waar |
|---|---|
| Multiple enabled sources of type %r; none of them is used ↔ | _read_sources |

## `custom_components/domotiapp_energy/engine/providers.py`

| Tekst | Waar |
|---|---|
| Alle gegevens voor een betrouwbaar advies zijn ingevuld. ↔ | _missing_data |
| De coach kan {...} op dit moment niet gebruiken; op de tabbladen Energiebronnen en Apparaten staat per rij wat eraan schort. | _missing_data |
| De energiescore is nog niet berekend. ↔ | _score_breakdown |
| De energiescore is nog niet berekend. ↔ | _score_breakdown |
| De netbelasting is niet te bepalen. Vul het maximale netvermogen in en koppel een netbron. | _peak_risk |
| De score op dit moment is {...}, opgebouwd uit: {...}. | _score_breakdown |
| De stroomprijs is op dit moment laag, dus er is geen duur verbruik om te vermijden. | module |
| Er is nog geen energiescore, omdat de installatie nog niet compleet is. De checklist hieronder laat zien wat er ontbreekt. | module |
| Er is nu opwek, maar geen apparaat of batterij die verbruik kan verplaatsen. Er valt daarom niets te benutten dat nu niet al gebeurt. | module |
| Er is op dit moment geen aanleiding om een apparaat te verplaatsen of juist nu te gebruiken. | _use_device_now |
| Er is op dit moment geen advies. | _why_advice |
| Gebaseerd op {...}. | _why_advice |
| Het prijsmoment telt niet mee zolang de lage en de hoge prijsdrempel niet zijn ingevuld. Vul ze in bij Installatie. | module |
| Het prijsmoment telt niet mee, want bij een vast tarief is het ene moment niet duurder dan het andere. | module |
| Het prijsmoment telt niet mee, want de actuele prijs is op dit moment niet uit te lezen. | module |
| Het prijsmoment telt niet mee, want de stroom is nu goedkoop en er is dus geen duur verbruik om te vermijden. | module |
| Het tarief is altijd gelijk en er zijn geen zonnepanelen, dus er is geen moment dat beter is dan een ander. Er valt daarom niets te optimaliseren. Het advies blijft gewoon werken. | module |
| Het vermogen van je thuisbatterij kan niet uitgelezen worden. Een batterij die laadt of ontlaadt verschuift wat er van het net komt, dus het thuisverbruik is niet te berekenen en het zonneoverschot kan te hoog zijn. Koppel de vermogenssensor van de batterij om dit op te lossen. | module |
| Ja. De all-in energieprijs is nu {...} en ligt onder de ingestelde lage prijsgrens. | _use_device_now |
| Ja. De woning levert veel terug aan het net; dat overschot kun je nu beter zelf gebruiken. | _use_device_now |
| Je panelen leveren op dit moment niets en de stroomprijs is laag. Er is nu dus geen overschot om te benutten en geen duur verbruik om te vermijden. | module |
| Je panelen leveren op dit moment niets, en bij een vast tarief is het ene moment niet beter dan het andere. Er is nu dus niets te verbeteren. | module |
| Je panelen leveren op dit moment, maar terugleveren levert je meer op dan de stroom je kost. Zelf verbruiken zou je nu geld kosten, dus er valt aan je opwek niets te benutten. De coach zegt hetzelfde: wachten is voordeliger. | module |
| Nee | _peak_risk |
| Niet van toepassing op deze woning, en dus niet meegeteld: {...}. | _missing_data |
| Nog ontbrekend: {...}. | _missing_data |
| Nu is geen gunstig moment: de all-in energieprijs is {...} en ligt boven de ingestelde hoge prijsgrens. | _use_device_now |
| Nu is geen gunstig moment: de netbelasting ligt dicht bij het ingestelde maximum. | _use_device_now |
| Zolang de lage en de hoge prijsdrempel niet zijn ingevuld, is niet te bepalen of dit een duur moment is. Vul ze in bij Installatie. | module |
| Zonnebenutting telt niet mee, want deze woning heeft geen zonnepanelen. ↔ | module |
| Zonnebenutting telt niet mee, want er is geen apparaat of batterij die verbruik naar dit moment kan verplaatsen. | module |
| Zonnebenutting telt niet mee, want je panelen leveren op dit moment niets. ↔ | module |
| Zonnebenutting telt niet mee, want zonder netmeting is niet te zien hoeveel van je opwek je zelf gebruikt. | module |
| Zonnebenutting telt niet mee: terugleveren levert je op dit moment meer op dan de stroom je kost, dus je opwek zelf gebruiken zou je geld kosten. | module |
| all-in prijs in €/kWh ↔ | module |
| de woninggegevens ↔ | module |
| een compleet apparaatprofiel ↔ | module |
| een geldige netbron ↔ | module |
| een geldige zonnebron ↔ | module |
| levert terug met ↔ | _peak_risk |
| netbelasting in % ↔ | module |
| netvermogen in W ↔ | module |
| ontbrekende onderdelen ↔ | module |
| tijdvensters voor flexibele apparaten ↔ | module |
| zonneoverschot in W ↔ | module |
| {...} koppelingen | _missing_data |
| {...}. De woning {...} {...}% van het ingestelde maximale netvermogen. | _peak_risk |
| één koppeling | _missing_data |
| € {...} per kWh | _format_price |

## `custom_components/domotiapp_energy/frontend/core/api.js`

| Tekst | Waar |
|---|---|
| DomotiApp Energy is niet geladen. Controleer de integratie in Instellingen. | api |
| Er is een onbekende fout opgetreden. ↔ | api |
| Er is een onbekende fout opgetreden. ↔ | api |
| Je hebt geen rechten voor deze actie. | api |

## `custom_components/domotiapp_energy/frontend/core/dialog.js`

| Tekst | Waar |
|---|---|
| Annuleren ↔ | dialog |
| Annuleren ↔ | dialog |
| Escape | dialog |
| Sluiten ↔ | dialog |
| Verwijderen ↔ | dialog |
| Verwijderen ↔ | dialog |

## `custom_components/domotiapp_energy/frontend/core/dom.js`

| Tekst | Waar |
|---|---|
| Gisteren | dom |
| Niet beschikbaar ↔ | dom |
| Nog niet berekend ↔ | dom |
| Vandaag | dom |
| button button-primary | dom |

## `custom_components/domotiapp_energy/frontend/core/labels.js`

| Tekst | Waar |
|---|---|
| Buiten het toegestane tijdvenster | labels |
| De besparing is te klein om te melden | labels |
| De energieprijs is hoog | labels |
| De energieprijs is laag | labels |
| De netbelasting is hoog | labels |
| De situatie vraagt niet om een aanpassing | labels |
| De teruglevering is hoog | labels |
| De uiterste starttijd komt in zicht | labels |
| Een gekoppelde entiteit bestaat niet | labels |
| Een gekoppelde entiteit heeft nog geen waarde | labels |
| Een gekoppelde entiteit is niet bereikbaar | labels |
| Een gekoppelde entiteit is stilgevallen | labels |
| Een gekoppelde entiteit levert geen bruikbare waarde | labels |
| Er is een verplaatsbaar apparaat beschikbaar | labels |
| Er is zonneoverschot | labels |
| Er ontbreken gegevens | labels |
| Het is nu stille uren | labels |
| all-in prijs in €/kWh ↔ | labels |
| de woninggegevens ↔ | labels |
| een compleet apparaatprofiel ↔ | labels |
| een geldige netbron ↔ | labels |
| een geldige zonnebron ↔ | labels |
| netbelasting in % ↔ | labels |
| netvermogen in W ↔ | labels |
| ontbrekende onderdelen ↔ | labels |
| tijdvensters voor flexibele apparaten ↔ | labels |
| zonneoverschot in W ↔ | labels |

## `custom_components/domotiapp_energy/frontend/core/roles.js`

| Tekst | Waar |
|---|---|
| Deze gegevens worden beheerd door DomotiTech. | roles |

## `custom_components/domotiapp_energy/frontend/domotiapp-energy-panel.js`

| Tekst | Waar |
|---|---|
| Dashboard | domotiapp-energy-panel |
| DomotiApp Energy tabbladen | domotiapp-energy-panel |
| Gegevens laden… | domotiapp-energy-panel |
| Terug naar het dashboard | domotiapp-energy-panel |

## `custom_components/domotiapp_energy/frontend/tabs/coach.js`

| Tekst | Waar |
|---|---|
| Advies ↔ | coach |
| Advies ↔ | coach |
| Advies ↔ | coach |
| Alle gegevens voor een betrouwbaar advies zijn ingevuld. ↔ | coach |
| Bezig met berekenen… | coach |
| Deze vraag is nog niet beantwoord. Bereken opnieuw zodra er gegevens | coach |
| Energiecoach | coach |
| Er is op dit moment geen aanvullend advies. | coach |
| Gegevens voor je advies | coach |
| Geschatte besparing | coach |
| Geschatte opbrengst per uur | coach |
| Het advies is opnieuw berekend. | coach |
| Hoe is mijn energiescore berekend? | coach |
| Hoofdadvies | coach |
| Is er risico op piekbelasting? | coach |
| Kan ik nu het beste een apparaat gebruiken? | coach |
| Kies een vraag; het antwoord verschijnt in beeld. | coach |
| Klaar / vol ↔ | coach |
| Klaar / vol ↔ | coach |
| Laatste berekening ↔ | coach |
| Nog geen advies berekend ↔ | coach |
| Nog niet berekend ↔ | coach |
| Nog ontbrekend: | coach |
| Onbekend | coach |
| Opnieuw berekenen | coach |
| Overige adviezen | coach |
| Probleem | coach |
| Reden ↔ | coach |
| Toch niet vol ↔ | coach |
| Vraag het de coach | coach |
| Waarom krijg ik dit advies? | coach |
| Waarschuwing ↔ | coach |
| Welke gegevens ontbreken nog? | coach |
| Zodra er een energiebron gekoppeld is, verschijnt hier het hoofdadvies. ↔ | coach |
| Zolang dit zonneoverschot er is. | coach |
| gekoppeld zijn. | coach |

## `custom_components/domotiapp_energy/frontend/tabs/devices.js`

| Tekst | Waar |
|---|---|
| "Alleen monitoren" legt vast dat dat zo moet blijven, ook als dat | devices |
| "alleen adviseren" om het weer mee te laten doen. | devices |
| "alleen monitoren" wordt als adviseren behandeld. | devices |
| "mag hierna niet meer draaien". | devices |
| ${device.name \|\| ↔ | devices |
| ${device.name \|\| ↔ | devices |
| Aan- en uitschakelen ↔ | devices |
| Aansturing ↔ | devices |
| Aansturing uitgesloten voor deze installatie ↔ | devices |
| Airconditioning | devices |
| Alleen adviseren ↔ | devices |
| Alleen monitoren | devices |
| Alleen registreren: er wordt niets aangestuurd. Niets aanvinken | devices |
| Annuleren ↔ | devices |
| Apparaat ↔ | devices |
| Apparaat ↔ | devices |
| Apparaat bewerken | devices |
| Apparaat toevoegen ↔ | devices |
| Apparaat toevoegen ↔ | devices |
| Apparaat verwijderen | devices |
| Apparaten ↔ | devices |
| Apparaten ↔ | devices |
| Automatisch aansturen ↔ | devices |
| Batterijniveau | devices |
| Bedieningsniveau ↔ | devices |
| Bedieningsniveau ↔ | devices |
| Bewerken ↔ | devices |
| Bewerken ↔ | devices |
| Bezig met opslaan… ↔ | devices |
| Bezig met verwijderen… ↔ | devices |
| Bij meerdere kandidaten wint de hoogste prioriteit. | devices |
| Compleet. ↔ | devices |
| Dagen ↔ | devices |
| Dagen ↔ | devices |
| De aanvoertemperatuur van de warmtepomp. | devices |
| De configuratie is intussen ergens anders gewijzigd. Er is niets ↔ | devices |
| De energie van een gemiddelde draaiperiode. | devices |
| De energie van één cyclus. | devices |
| De energie van één droogbeurt. | devices |
| De energie van één programma, bijvoorbeeld 1,0 tot 1,5 kWh. | devices |
| De energie van één wasbeurt. | devices |
| De entiteit die zegt of het apparaat aan staat of draait. | devices |
| De gekoppelde vermogenssensor is niet te gebruiken: hij moet | devices |
| De laadtoestand van de auto, als de laadpaal die meldt. | devices |
| De laadtoestand van de thuisbatterij, in procenten. | devices |
| De meterstand of het verbruik van dit apparaat. | devices |
| De ruimtetemperatuur die deze airco regelt. | devices |
| De watertemperatuur in de boiler. | devices |
| Deze ingevulde gegevens worden voor dit apparaat niet meer | devices |
| Dinsdag | devices |
| Dit apparaat is compleet: alles wat de datakwaliteit vraagt is ingevuld. | devices |
| Dit apparaat is intussen ergens anders verwijderd. Je invoer staat | devices |
| Dit apparaat is intussen ook ergens anders gewijzigd. Je invoer | devices |
| Dit apparaat krijgt geen advies zolang het niet verplaatsbaar is. | devices |
| DomotiApp Energy adviseert in deze versie alleen; alles behalve | devices |
| DomotiApp Energy rekent zelf terug wanneer het apparaat uiterlijk | devices |
| Donderdag | devices |
| Droger | devices |
| Duur van een cyclus ↔ | devices |
| Duur van een cyclus ↔ | devices |
| Duur van een laadsessie | devices |
| Een afspraak met de klant, los van wat dit apparaat kan. | devices |
| Een schatting van een typische laadbeurt, bijvoorbeeld 10 kWh voor | devices |
| Een uitgeschakeld apparaat krijgt geen advies. | devices |
| Elektrische boiler | devices |
| Energie per cyclus ↔ | devices |
| Energie per cyclus ↔ | devices |
| Energie per laadsessie | devices |
| Energieverbruikentiteit | devices |
| Er is intussen ergens anders iets aan de configuratie gewijzigd, maar ↔ | devices |
| Het actuele vermogen van dit apparaat. Anders dan bij een energiebron | devices |
| Het elektrische opgenomen vermogen, niet het thermische. | devices |
| Het hoogste vermogen waarmee deze paal kan laden — niet wat de auto | devices |
| Het laad- of ontlaadvermogen van de batterij. | devices |
| Het minste waarmee het apparaat nog iets doet. | devices |
| Het vermogen tijdens gebruik. | devices |
| Het vermogen van het verwarmingselement. | devices |
| Hoe lang de lopende cyclus nog duurt. | devices |
| Hoog | devices |
| In minuten, voor een typische laadbeurt. Wordt getoetst aan het | devices |
| In minuten. Wordt getoetst aan het tijdvenster hieronder. | devices |
| Ingeschakeld ↔ | devices |
| Instellen | devices |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Verwerp je ze, ↔ | devices |
| Kan op deelvermogen draaien ↔ | devices |
| Kan op deelvermogen draaien ↔ | devices |
| Klaar uiterlijk om ↔ | devices |
| Klaar uiterlijk om ↔ | devices |
| Koppelingen | devices |
| Kritiek | devices |
| Laadpaal | devices |
| Laadstroom instellen ↔ | devices |
| Laag | devices |
| Laat beide tijden leeg als er geen venster is; het apparaat mag dan op | devices |
| Laat leeg als de deadline elke dag geldt. Voor een laadpaal is dit | devices |
| Ligt deze tijd vóór "niet draaien vanaf", dan loopt het verbod door | devices |
| Locatie | devices |
| Maakt geluid ↔ | devices |
| Maakt geluid ↔ | devices |
| Maakt niet uit wanneer hij klaar is ↔ | devices |
| Maakt niet uit wanneer hij klaar is ↔ | devices |
| Maandag | devices |
| Maximaal laadvermogen | devices |
| Minimaal vermogen ↔ | devices |
| Minimaal vermogen ↔ | devices |
| Moet gemeld worden dat er werk in zit ↔ | devices |
| Moet gemeld worden dat er werk in zit ↔ | devices |
| Naam ↔ | devices |
| Naamloos apparaat ↔ | devices |
| Niet draaien vanaf ↔ | devices |
| Niet draaien vanaf ↔ | devices |
| Niet eerder klaar dan ↔ | devices |
| Niet eerder klaar dan ↔ | devices |
| Nog geen apparaten. Voeg de apparaten toe waarover DomotiApp Energy | devices |
| Nog geen vermogenssensor gekoppeld — dit apparaat wordt alleen | devices |
| Nog nodig voor een compleet apparaat: | devices |
| Nominaal vermogen ↔ | devices |
| Nominaal vermogen ↔ | devices |
| Normaal | devices |
| Noteer waarom, zodat dit later terug te vinden is. ↔ | devices |
| Notities ↔ | devices |
| Notities ↔ | devices |
| Op "alleen monitoren" krijgt dit apparaat geen advies. Zet het op | devices |
| Op welke dagen dit apparaat mag draaien. | devices |
| Op welke dagen geldt dit ↔ | devices |
| Op welke dagen geldt dit ↔ | devices |
| Opslaan ↔ | devices |
| Opslaan mag ook zonder — het apparaat telt dan alleen nog niet | devices |
| Opslaan om hem te bewaren. | devices |
| Optioneel. Handig voor was die niet uren nat mag blijven liggen: | devices |
| Overig, alleen meten | devices |
| Overig, inplanbaar | devices |
| Prioriteit ↔ | devices |
| Prioriteit ↔ | devices |
| Reden ↔ | devices |
| Reden ↔ | devices |
| Resterende tijd | devices |
| Soort apparaat | devices |
| Statusentiteit | devices |
| Telt niet mee voor de datakwaliteit. | devices |
| Temperatuursensor | devices |
| Terug naar het formulier ↔ | devices |
| Thuisbatterij ↔ | devices |
| Uitgeschakeld — krijgt geen advies. | devices |
| Uitlezen ↔ | devices |
| Uren waarin dit apparaat helemaal niet mag draaien, bijvoorbeeld | devices |
| Vaatwasser | devices |
| Verbruik | devices |
| Vermogensentiteit | devices |
| Vermogensgrens instellen ↔ | devices |
| Verplaatsbaar in de tijd ↔ | devices |
| Verplaatsbaar in de tijd ↔ | devices |
| Verwerpen ↔ | devices |
| Verwijderen ↔ | devices |
| Vragen om goedkeuring ↔ | devices |
| Vrijdag | devices |
| Vul hierboven een duur in, dan rekent DomotiApp Energy terug wanneer | devices |
| Waar staat het? Alleen om het terug te herkennen. | devices |
| Wanneer het mag draaien | devices |
| Warmtepomp | devices |
| Wasmachine | devices |
| Wat kan dit apparaat? | devices |
| Weer toegestaan vanaf ↔ | devices |
| Weer toegestaan vanaf ↔ | devices |
| Wijzigingen verwerpen? ↔ | devices |
| Woensdag | devices |
| Zaterdag | devices |
| Zet dit aan als elk moment goed is. De coach adviseert dit apparaat | devices |
| Zet dit aan voor apparatuur die minder dan haar maximum kan | devices |
| Zet het apparaattype, "verplaatsbaar in de tijd" of het | devices |
| Zondag | devices |
| Zonder dit getal is er geen besparing te berekenen. | devices |
| Zwembadpomp | devices |
| alleen die hebben een tijdvenster nodig. | devices |
| andere dagen mag hij gewoon wachten op zon of een lage prijs — hij | devices |
| bedieningsniveau terug om ze te behouden. | devices |
| betekent "niet opgegeven", niet "kan niets". | devices |
| betrouwbaarheid daarom op "gemiddeld". | devices |
| dan gewoon op een gunstig moment, alleen zonder deadline om naartoe | devices |
| dan zijn ze weg. ↔ | devices |
| een dagelijkse rit. Exact kan niet: DomotiApp Energy weet niet hoe | devices |
| elk uur. Een venster telt wel mee voor de datakwaliteit, omdat het advies | devices |
| energie per cyclus | devices |
| energie per laadsessie | devices |
| er gerichter van wordt. | devices |
| er vandaag van afneemt. | devices |
| geadviseerd, dus een droger van ruim twee uur krijgt bij een verbod | devices |
| gebruiken, zoals de meeste laadpalen. Zonder het minimum hieronder | devices |
| geen reden genoteerd ↔ | devices |
| gemeten, en er valt nu niets te meten. | devices |
| het apparaat uiterlijk moet starten. Zonder duur geldt dit alleen als | devices |
| het terug wilt. | devices |
| hier nog, maar opslaan lukt niet meer; maak het opnieuw aan als je | devices |
| in W of kW meten en een waarde melden. | devices |
| krijgt dan nog steeds advies, alleen zonder deadline. | devices |
| later verandert. | devices |
| leeg de auto is, dus het advies rekent met dit getal en houdt zijn | devices |
| lege machine geadviseerd. | devices |
| mag adviseren, met hun vermogen, verbruik per cyclus en tijdvenster. | devices |
| maximaal laadvermogen | devices |
| mee voor de datakwaliteit. | devices |
| meestal de werkweek: op die dagen moet de auto vol zijn, en op de | devices |
| moet starten om dit te halen. | devices |
| nadat iemand op "Klaar / vol" heeft gedrukt. Zo wordt er nooit een | devices |
| niet aan dit apparaat. Je invoer staat er nog; druk opnieuw op | devices |
| nominaal vermogen | devices |
| of kW meten. Een meterstand in kWh is een totaal en geen vermogen, en | devices |
| omdat het onder een slaapkamer staat. Laat beide leeg als er geen | devices |
| staat er nog; als je nu opslaat, vervangt hij die andere wijziging. ↔ | devices |
| te rekenen — en de datakwaliteit rekent het als beantwoord in plaats | devices |
| tijd ná "klaar uiterlijk om", dan loopt het venster door tot de | devices |
| tijdvenster hieronder. | devices |
| tot de volgende dag — 23:00 tot 07:00 is het normale geval. | devices |
| van als ontbrekend. | devices |
| vanaf 23:00 al vanaf 20:45 geen advies meer. | devices |
| verandert er niets. | devices |
| verbod is. Een cyclus die het venster in zou lopen wordt ook niet | devices |
| verwijderd; de lijst is opnieuw geladen. ↔ | devices |
| verwijderen? Er wordt daarna niet meer over geadviseerd. | devices |
| volgende dag — 22:00 tot 06:00 is het normale geval. | devices |
| wordt de eenheid hier van de entiteit zelf overgenomen: hij moet in W | devices |
| wordt geweigerd — de rij zegt dat dan ook. | devices |
| zet hier bijvoorbeeld 06:00 als je hem om 07:00 uithaalt. Ligt deze | devices |
| zonder naam ↔ | devices |

## `custom_components/domotiapp_energy/frontend/tabs/home.js`

| Tekst | Waar |
|---|---|
| (marktprijs + opslag + energiebelasting) × (1 + btw). Een prijsbron | home |
| /lovelace/0. Zonder dit adres verschijnt er geen terugknop. Op een | home |
| 1 fase | home |
| 3 fasen | home |
| Aantal fasen | home |
| Adviesinstellingen | home |
| Alleen adviseren ↔ | home |
| Alleen nodig als je terugleverprijsbron de kale marktprijs levert. | home |
| Automatisch aansturen ↔ | home |
| Bedieningsniveau ↔ | home |
| Bedieningsniveau ↔ | home |
| Besparen | home |
| Bezig met opslaan… ↔ | home |
| Comfort | home |
| Contract en prijzen | home |
| Contractsoort | home |
| De salderingsregeling stopt landelijk op 1 januari 2027. Laat leeg als | home |
| De woninggegevens zijn intussen ergens anders gewijzigd. Het | home |
| De woninggegevens zijn opgeslagen. | home |
| DomotiApp Energy meet, rekent en adviseert; het stuurt in deze versie | home |
| DomotiApp Energy rekent overal met de all-in prijs: | home |
| Dynamisch tarief | home |
| Een bedrag per kWh, exclusief btw — géén vast maandbedrag. Reken een | home |
| Een bedrag per kWh, exclusief btw. Nodig zodra een prijsbron de kale | home |
| Een bedrag per teruggeleverde kWh — géén vast maandbedrag. Reken een | home |
| Energiebelasting | home |
| Energiedashboard | home |
| Er is intussen ergens anders iets aan de configuratie gewijzigd, ↔ | home |
| Gebalanceerd | home |
| Geen terugknop ingesteld. Nodig bij een wandtablet zonder zijbalk. | home |
| Het adres van het hoofddashboard van deze woning, bijvoorbeeld | home |
| Het all-in bedrag per kWh, inclusief energiebelasting en btw — dus wat | home |
| Het btw-percentage over de leveringsprijs. In Nederland 21%. | home |
| Het vaste bedrag dat de klant per teruggeleverde kWh daadwerkelijk | home |
| Het vermogen waarboven DomotiApp Energy waarschuwt. | home |
| Hier blijven ↔ | home |
| Hoge prijsgrens (all-in) | home |
| Hoofdzekering per fase | home |
| In ampère, zoals op de zekering staat. | home |
| Inhouding leverancier op teruglevering | home |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Sla ze op, of verwerp ↔ | home |
| Lage prijsgrens (all-in) | home |
| Maximaal netvermogen | home |
| Maximaal zelf verbruiken | home |
| Minimaal zonneoverschot | home |
| Naam van de woning | home |
| Navigatie | home |
| Opslaan ↔ | home |
| Opslag leverancier | home |
| Percentage van het maximale netvermogen. | home |
| Saldering geldt tot | home |
| Standaardstrategie | home |
| Terug naar dashboard | home |
| Terugleverkosten | home |
| Terugleververgoeding (all-in) | home |
| Vanaf dit overschot adviseert DomotiApp Energy een apparaat. | home |
| Vast leveringstarief (all-in) | home |
| Vast tarief | home |
| Vergelijk met de all-in prijs, niet met de kale marktprijs van je ↔ | home |
| Vergelijk met de all-in prijs, niet met de kale marktprijs van je ↔ | home |
| Verwerpen en verdergaan ↔ | home |
| Vragen om goedkeuring ↔ | home |
| Vul 0 in als er niets wordt ingehouden. | home |
| Waar het verbruik in kWh van deze woning staat, meestal /energy. | home |
| Waarschuwen vanaf | home |
| Wat de leverancier per teruggeleverde kWh inhoudt op de marktprijs. | home |
| Wijzigingen verwerpen ↔ | home |
| Woning | home |
| Woning en aansluiting | home |
| Zonder dit adres noemt het Overzicht het dashboard wel, maar zonder | home |
| al all-in is, wordt ongewijzigd gebruikt. Bij de bron zelf geef je aan | home |
| betaalt; laat het leeg als je het niet weet, dan toont de coach geen | home |
| de klant werkelijk betaalt. | home |
| deze woning niet saldeert; de omslag gaat daarna vanzelf. | home |
| die de kale marktprijs levert wordt daarmee omgerekend; een bron die | home |
| formulier is opnieuw geladen met de actuele gegevens, zodat je ↔ | home |
| geen enkel apparaat aan. De andere bedieningsniveaus staan hier al wel, | home |
| geschatte besparing in plaats van een bedrag dat op een aanname rust. | home |
| link — zodat niemand op een wandtablet ergens belandt waar hij niet | home |
| maandbedrag niet om: alleen de opslag per kWh hoort hier. | home |
| maandstaffel om. Vul 0 in als deze aansluiting geen terugleverkosten | home |
| maar niet aan de woninggegevens. Je invoer staat er nog; druk | home |
| maar zijn nog niet beschikbaar. | home |
| marktprijs levert; die wordt hiermee naar een all-in prijs omgerekend. | home |
| meer wegkomt. | home |
| niet omgerekend. | home |
| niet overschrijft wat je niet gezien hebt. ↔ | home |
| opnieuw op Opslaan om hem te bewaren. ↔ | home |
| vergoed krijgt. Geen marktprijs en geen percentage: dit veld wordt | home |
| wandtablet zonder zijbalk kan de bewoner dit paneel dan niet verlaten. | home |
| welke van de twee het is. | home |
| ze om verder te gaan. ↔ | home |
| zonder naam ↔ | home |
| zonder naam ↔ | home |

## `custom_components/domotiapp_energy/frontend/tabs/installation.js`

| Tekst | Waar |
|---|---|
| Installatie ↔ | installation |

## `custom_components/domotiapp_energy/frontend/tabs/logbook.js`

| Tekst | Waar |
|---|---|
| Advies herberekend | logbook |
| Apparaat toegevoegd ↔ | logbook |
| Apparaat verwijderd ↔ | logbook |
| Bezig met wissen… | logbook |
| Bron niet beschikbaar | logbook |
| Configuratie gewijzigd | logbook |
| Configuratieprobleem | logbook |
| Fout ↔ | logbook |
| Gelukt | logbook |
| Het logboek is gewist. | logbook |
| Het logboek is leeg. Hier komt te staan wat DomotiApp Energy | logbook |
| Info | logbook |
| Logboek ↔ | logbook |
| Logboek ↔ | logbook |
| Logboek wissen ↔ | logbook |
| Logboek wissen ↔ | logbook |
| Ongeldige meting ↔ | logbook |
| Piekrisico gesignaleerd | logbook |
| Waarschuwing ↔ | logbook |
| Weer uitgelezen, binnen een minuut. | logbook |
| Weet je zeker dat je het logboek wilt wissen? De gebeurtenissen | logbook |
| Wissen | logbook |
| Zonneoverschot gesignaleerd | logbook |
| zijn daarna weg. De configuratie zelf verandert niet. | logbook |

## `custom_components/domotiapp_energy/frontend/tabs/overview.js`

| Tekst | Waar |
|---|---|
| Actief | overview |
| Actuele energieprijs ↔ | overview |
| Actuele situatie | overview |
| Advies ↔ | overview |
| Alle gegevens voor een betrouwbaar advies zijn ingevuld. ↔ | overview |
| Alle onderdelen van de datakwaliteit zijn ingevuld. Er is wel | overview |
| Apparaten die nu draaien | overview |
| Boven de drempel die ook het advies gebruikt. | overview |
| Datakwaliteit | overview |
| De hele dag compleet | overview |
| De stroomprijs is op dit moment laag, dus er is geen duur verbruik om | overview |
| Energiebronnen om je slimme meter of omvormer te koppelen. | overview |
| Energiecoach laat zien wat. | overview |
| Energiescore | overview |
| Er is nog geen cijfer, omdat de installatie nog niet compleet is. | overview |
| Er is nog geen geschiedenis van gisteren. Vanaf de eerste hele dag | overview |
| Er is nu opwek, maar geen apparaat of batterij die verbruik kan | overview |
| Er is op dit moment niets te doen. | overview |
| Er ontbreekt nog iets voor een betrouwbaar advies. Het tabblad | overview |
| Er zijn nog geen energiebronnen gekoppeld. Ga naar het tabblad | overview |
| Er zijn op dit moment geen waarschuwingen. | overview |
| Fout ↔ | overview |
| Geen afname gemeten | overview |
| Geen bruikbare prijsbron | overview |
| Geen cijfer | overview |
| Het prijsmoment telt niet mee zolang de lage en de hoge prijsdrempel | overview |
| Het prijsmoment telt niet mee, want bij een vast tarief is het ene | overview |
| Het prijsmoment telt niet mee, want de actuele prijs is op dit moment | overview |
| Het prijsmoment telt niet mee, want de stroom is nu goedkoop en er is | overview |
| Het tabblad Energiecoach laat zien wat er ontbreekt. | overview |
| Het tarief is altijd gelijk en er zijn geen zonnepanelen, dus er is | overview |
| Het vermogen van je thuisbatterij kan niet uitgelezen worden. Een | overview |
| Hoe het gisteren ging | overview |
| Hoogste in 30 dagen | overview |
| Hoogste netvermogen | overview |
| Installatie ↔ | overview |
| Je omvormer levert op dit moment geen waarde, dus het | overview |
| Je panelen leveren op dit moment niets en de stroomprijs is laag. Er | overview |
| Je panelen leveren op dit moment niets, en bij een vast tarief is het | overview |
| Je panelen leveren op dit moment, maar terugleveren levert je meer op | overview |
| Klaar / vol ↔ | overview |
| Klaar / vol ↔ | overview |
| Laatste berekening ↔ | overview |
| Laden… | overview |
| Naamloos apparaat ↔ | overview |
| Negatief betekent teruglevering aan het net. | overview |
| Netvermogen | overview |
| Niet beschikbaar ↔ | overview |
| Niet de hele dag compleet | overview |
| Niet gemeten ↔ | overview |
| Niet gemeten ↔ | overview |
| Niet gemeten ↔ | overview |
| Nog geen advies berekend ↔ | overview |
| Nog geen prijs bekend — koppel een prijsbron of vul het vaste leveringstarief in | overview |
| Nog niet berekend ↔ | overview |
| Nog niet ingesteld | overview |
| Op dit moment | overview |
| Overzicht | overview |
| Percentage van maximum | overview |
| Status | overview |
| Thuisverbruik | overview |
| Toch niet vol ↔ | overview |
| Vast leveringstarief, zoals ingevuld bij Woning. | overview |
| Vast leveringstarief, zoals ingevuld bij Woning. De gekoppelde prijsbron bepaalt dit bedrag niet, maar neemt het over zodra dit veld leeg is of het contract dynamisch wordt. | overview |
| Voor kWh, kosten en wat je zelf verbruikte: | overview |
| Waarschuwing ↔ | overview |
| Waarschuwingen | overview |
| Wat je nu kunt doen | overview |
| Zelfbenutting | overview |
| Zodra er een energiebron gekoppeld is, verschijnt hier het hoofdadvies. ↔ | overview |
| Zolang de lage en de hoge prijsdrempel niet zijn ingevuld, is niet te | overview |
| Zonnebenutting telt niet mee, want deze woning heeft geen zonnepanelen. ↔ | overview |
| Zonnebenutting telt niet mee, want er is geen apparaat of batterij die | overview |
| Zonnebenutting telt niet mee, want je panelen leveren op dit moment niets. ↔ | overview |
| Zonnebenutting telt niet mee, want zonder netmeting is niet te zien | overview |
| Zonnebenutting telt niet mee: terugleveren levert je op dit moment meer | overview |
| Zonneoverschot ↔ | overview |
| Zonneoverschot ↔ | overview |
| Zonneproductie | overview |
| batterij die laadt of ontlaadt verschuift wat er van het net | overview |
| bepalen of dit een duur moment is. Vul ze in bij Installatie. | overview |
| bij Energiebronnen. | overview |
| cijfer. Op het tabblad Energiebronnen staat per bron wat eraan schort. | overview |
| dan de stroom je kost. Zelf verbruiken zou je nu geld kosten, dus er | overview |
| de batterij om dit op te lossen. | overview |
| de coach op dit moment niet kan gebruiken; die telt niet mee in dit | overview |
| dus geen duur verbruik om te vermijden. | overview |
| een bron die | overview |
| ene moment niet beter dan het andere. Er is nu dus niets te verbeteren. | overview |
| geen moment dat beter is dan een ander. Er valt daarom niets te | overview |
| het Energie-dashboard van Home Assistant ↔ | overview |
| het Energie-dashboard van Home Assistant ↔ | overview |
| hoeveel van je opwek je zelf gebruikt. | overview |
| is nu dus geen overschot om te benutten en geen duur verbruik om te | overview |
| is voordeliger. | overview |
| komt, dus het thuisverbruik is niet te berekenen en het | overview |
| moment niet duurder dan het andere. | overview |
| niet uit te lezen. | overview |
| niet zijn ingevuld. Vul ze in bij Installatie. | overview |
| op dan de stroom je kost, dus je opwek zelf gebruiken zou je geld kosten. | overview |
| op dit moment | overview |
| optimaliseren. Het advies blijft gewoon werken. | overview |
| staat hier hoe het ging. | overview |
| te vermijden. | overview |
| thuisverbruik is niet te berekenen. Controleer de zonnebron | overview |
| valt aan je opwek niets te benutten. De coach zegt hetzelfde: wachten | overview |
| verbruik naar dit moment kan verplaatsen. | overview |
| verplaatsen. Er valt daarom niets te benutten dat nu niet al gebeurt. | overview |
| zonneoverschot kan te hoog zijn. Koppel de vermogenssensor van | overview |

## `custom_components/domotiapp_energy/frontend/tabs/preferences.js`

| Tekst | Waar |
|---|---|
| Aantal adviezen | preferences |
| Advies met een berekende besparing bóven nul maar onder dit bedrag | preferences |
| Adviseer een apparaat wanneer er genoeg eigen opwek is. | preferences |
| Alleen van toepassing bij een dynamisch contract; bij een vast tarief | preferences |
| Bezig met opslaan… ↔ | preferences |
| De voorkeuren zijn intussen ergens anders gewijzigd. Het | preferences |
| De voorkeuren zijn opgeslagen. | preferences |
| Een venster over middernacht is het normale geval: 22:00 tot 07:00. | preferences |
| Er is intussen ergens anders iets aan de configuratie gewijzigd, ↔ | preferences |
| Geschatte besparing tonen | preferences |
| Hier blijven ↔ | preferences |
| Hoeveel adviezen er hoogstens tegelijk getoond worden. | preferences |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Sla ze op, of verwerp ↔ | preferences |
| Mijn voorkeuren | preferences |
| Minimale besparing | preferences |
| Op prijs adviseren | preferences |
| Opslaan ↔ | preferences |
| Stille uren | preferences |
| Stille uren tot | preferences |
| Stille uren van | preferences |
| Technische onderbouwing tonen | preferences |
| Tussen deze tijden raadt DomotiApp Energy aan om te wachten met | preferences |
| Verwerpen en verdergaan ↔ | preferences |
| Wanneer een advies de moeite waard is | preferences |
| Wat je te zien krijgt | preferences |
| Wat weegt mee | preferences |
| Wijzigingen verwerpen ↔ | preferences |
| Zonneoverschot benutten | preferences |
| formulier is opnieuw geladen met de actuele gegevens, zodat je ↔ | preferences |
| lawaaiige apparaten. Het advies verdwijnt niet, het zegt tot hoe laat. | preferences |
| maar niet aan je voorkeuren. Je invoer staat er nog; druk | preferences |
| niet overschrijft wat je niet gezien hebt. ↔ | preferences |
| nul uitkomt zolang de saldering loopt. | preferences |
| opnieuw op Opslaan om hem te bewaren. ↔ | preferences |
| piek, ontbrekende gegevens — blijft altijd staan, net als advies dat op | preferences |
| wordt er nooit op prijs geadviseerd. | preferences |
| wordt niet getoond. Advies zonder berekenbare besparing — veiligheid, | preferences |
| ze om verder te gaan. ↔ | preferences |

## `custom_components/domotiapp_energy/frontend/tabs/sources.js`

| Tekst | Waar |
|---|---|
| ${source.name \|\| ↔ | sources |
| ${source.name \|\| ↔ | sources |
| % — procent | sources |
| A — ampère | sources |
| Aan- en uitschakelen ↔ | sources |
| Aansturing ↔ | sources |
| Aansturing uitgesloten voor deze installatie ↔ | sources |
| Aansturing uitsluiten | sources |
| Actuele energieprijs ↔ | sources |
| Actuele terugleververgoeding | sources |
| Afname van het net | sources |
| Algemeen verbruik | sources |
| Alleen registreren: DomotiApp Energy stuurt in deze versie niets aan. | sources |
| Annuleren ↔ | sources |
| Annuleren ↔ | sources |
| Bekijken | sources |
| Bewerken ↔ | sources |
| Bewerken ↔ | sources |
| Bezig met opslaan… ↔ | sources |
| Bezig met verwijderen… ↔ | sources |
| Bron | sources |
| Bron toevoegen | sources |
| Compleet ingevuld, maar op dit moment niet uit te lezen. | sources |
| Compleet. ↔ | sources |
| De all-in prijs die de klant betaalt | sources |
| De configuratie is intussen ergens anders gewijzigd. Er is niets ↔ | sources |
| De eenheid waarin deze entiteit meet. | sources |
| De entiteit die de actuele zonneproductie meldt, niet de dagopbrengst. | sources |
| De entiteit die het laad- of ontlaadvermogen meldt, niet de laadtoestand. | sources |
| De entiteit die het totale huishoudelijke verbruik meldt. | sources |
| De entiteit met de prijs van dit moment. Hieronder geef je aan of dat | sources |
| De entiteit met de prijzen van de komende uren. | sources |
| De entiteit met de terugleververgoeding van dit moment. Gebruik dit | sources |
| De entiteit met de verwachte opbrengst. | sources |
| De entiteit waar deze bron uit gelezen wordt. | sources |
| De kale marktprijs, exclusief belasting en opslag | sources |
| De kale marktprijs, vóór inhouding van de leverancier | sources |
| De status van de entiteit | sources |
| De vergoeding die de klant werkelijk krijgt | sources |
| Deze energiebron is intussen ergens anders verwijderd. Je invoer | sources |
| Deze energiebron is intussen ook ergens anders gewijzigd. Je invoer | sources |
| Dit brontype is nog niet in gebruik. DomotiApp Energy rekent alleen met | sources |
| Een afspraak met de klant, los van wat deze bron zou kunnen. | sources |
| Een attribuut van de entiteit | sources |
| Een positieve waarde betekent | sources |
| Een uitgeschakelde bron wordt nergens in meegerekend. | sources |
| Eenheid ↔ | sources |
| Eenheid ↔ | sources |
| Energiebron | sources |
| Energiebron bewerken | sources |
| Energiebron toevoegen | sources |
| Energiebron verwijderen | sources |
| Energiebronnen ↔ | sources |
| Energiebronnen ↔ | sources |
| Entiteit ↔ | sources |
| Entiteit ↔ | sources |
| Entiteit ↔ | sources |
| Entiteit voor afname ↔ | sources |
| Entiteit voor afname ↔ | sources |
| Entiteit voor teruglevering ↔ | sources |
| Entiteit voor teruglevering ↔ | sources |
| Er is intussen ergens anders iets aan de configuratie gewijzigd, maar ↔ | sources |
| Eén waarde met een plus- en minteken | sources |
| Geen eenheid | sources |
| Gescheiden afname en teruglevering | sources |
| Hoe meet deze meter? ↔ | sources |
| Hoe meet deze meter? ↔ | sources |
| Ingeschakeld ↔ | sources |
| Ingeschakeld ↔ | sources |
| Intern geldt voor een thuisbatterij: positief is laden — de woning | sources |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Verwerp je ze, ↔ | sources |
| Kies expliciet. Zonder deze keuze wordt de prijs niet gebruikt, omdat | sources |
| Kies expliciet. Zonder deze keuze wordt de vergoeding niet | sources |
| Laadstroom instellen ↔ | sources |
| Let op de tekenconventie: positief betekent hier laden — de woning | sources |
| Meestal niet nodig. Zet dit alleen aan wanneer beide entiteiten | sources |
| Meestal niet nodig: gebruik hierboven "een positieve waarde betekent". | sources |
| Naam ↔ | sources |
| Naam ↔ | sources |
| Naam van het attribuut ↔ | sources |
| Naam van het attribuut ↔ | sources |
| Naamloze bron | sources |
| Netmeter | sources |
| Niets aanvinken betekent "niet opgegeven", niet "kan niets". | sources |
| Nog geen energiebronnen. Koppel je slimme meter, omvormer, prijsbron | sources |
| Noteer waarom, zodat dit later terug te vinden is. ↔ | sources |
| Notities ↔ | sources |
| Notities ↔ | sources |
| Notities ↔ | sources |
| Opslaan ↔ | sources |
| Prijsverwachting | sources |
| Reden ↔ | sources |
| Reden ↔ | sources |
| Schaalfactor ↔ | sources |
| Schaalfactor ↔ | sources |
| Sluiten ↔ | sources |
| Soort bron ↔ | sources |
| Soort bron ↔ | sources |
| Teken omdraaien ↔ | sources |
| Teken omdraaien ↔ | sources |
| Terug naar het formulier ↔ | sources |
| Teruglevering aan het net | sources |
| Thuisbatterij ↔ | sources |
| Uitgeschakeld — wordt niet meegerekend. | sources |
| Uitlezen ↔ | sources |
| Vermenigvuldiger vóór de eenheidsconversie. Standaard 1. | sources |
| Vermogensgrens instellen ↔ | sources |
| Verwerpen ↔ | sources |
| Verwijderen ↔ | sources |
| Voor een prijs: EUR/kWh of ct/kWh. ↔ | sources |
| Voor een prijs: EUR/kWh of ct/kWh. ↔ | sources |
| Voor een vermogen: W of kW. ↔ | sources |
| Voor een vermogen: W of kW. ↔ | sources |
| Voor een vermogen: W of kW. ↔ | sources |
| Voor een verwachte opbrengst meestal Wh of kWh. | sources |
| W — watt | sources |
| Waarde uitlezen uit ↔ | sources |
| Waarde uitlezen uit ↔ | sources |
| Wat betekent een positieve waarde? | sources |
| Wat er gemeten wordt | sources |
| Wat kan deze bron behalve uitlezen? | sources |
| Wat kan deze bron? | sources |
| Wat levert deze bron? ↔ | sources |
| Wat levert deze bron? ↔ | sources |
| Wh — wattuur | sources |
| Wijzigingen verwerpen? ↔ | sources |
| Zet aan wanneer deze sensor het tegenovergestelde teken rapporteert. | sources |
| Zoals jij hem vaststelt: de eenheid van de entiteit zelf wordt nooit | sources |
| Zonder deze keuze wordt de netmeter niet gebruikt. | sources |
| Zonnepanelen | sources |
| Zonverwachting | sources |
| alleen bij een dynamisch teruglevercontract; bij een vast bedrag vul | sources |
| als je hem terug wilt. | sources |
| bewaard, maar er wordt op dit moment niets mee gedaan. | sources |
| ct/kWh — cent per kilowattuur | sources |
| dan zijn ze weg. ↔ | sources |
| de kale marktprijs of de all-in prijs is. | sources |
| deze schakelaar dan aan. | sources |
| die je bij Woning invult; er komt geen energiebelasting of btw bij. | sources |
| een kale marktprijs en een all-in prijs sterk verschillen. | sources |
| gebruikt om te converteren. | sources |
| gebruikt. Een kale marktprijs wordt omgerekend met de inhouding | sources |
| geen reden genoteerd ↔ | sources |
| het huidige moment en leest geen verwachtingen. De koppeling blijft | sources |
| hierboven hun waarde met een minteken melden. | sources |
| je dat in bij Woning. | sources |
| kW — kilowatt | sources |
| kWh — kilowattuur | sources |
| niet aan deze bron. Je invoer staat er nog; druk opnieuw op Opslaan | sources |
| of thuisbatterij om DomotiApp Energy iets te laten meten. | sources |
| om hem te bewaren. | sources |
| rapporteert en gebruik zo nodig "teken omdraaien". | sources |
| staat er nog; als je nu opslaat, vervangt hij die andere wijziging. ↔ | sources |
| staat hier nog, maar opslaan lukt niet meer; maak hem opnieuw aan | sources |
| verbruikt — en negatief is ontladen. Controleer wat deze sensor | sources |
| verbruikt — en negatief ontladen. Meldt deze sensor het andersom, zet | sources |
| verwijderd; de lijst is opnieuw geladen. ↔ | sources |
| verwijderen? De metingen van deze bron tellen daarna nergens meer mee. | sources |
| zonder naam ↔ | sources |
| €/kWh — euro per kilowattuur | sources |

## `custom_components/domotiapp_energy/panel.py`

| Tekst | Waar |
|---|---|
| Panel %s is already registered | async_register_panel |

## `custom_components/domotiapp_energy/storage.py`

| Tekst | Waar |
|---|---|
| Bron heeft nog geen waarde | _async_report_failures |
| Bron is stilgevallen | _async_report_failures |
| Bron niet bereikbaar | _async_report_failures |
| Bron niet gevonden | _async_report_failures |
| De energiebron '{...}' heeft een onbekend type ('{...}') en is uitgeschakeld. Kies een geldig type om de bron weer te gebruiken. | async_report_invalid_rows |
| De energiebron '{...}' is gekoppeld aan '{...}', en die entiteit bestond wel maar droeg geen meetwaarde. | _async_report_failures |
| De energiebron '{...}' leverde geen bruikbare meetwaarde. Controleer bij de entiteit '{...}' de gekozen waardebron, het attribuut en de eenheid. (reden: {...}) | _async_report_failures |
| De energiebron '{...}' verwijst naar de entiteit '{...}', en die bestaat niet in deze Home Assistant. Controleer of de entiteit hernoemd of verwijderd is. | _async_report_failures |
| De energiebron '{...}' was niet bereikbaar. De integratie achter '{...}' meldde de entiteit als niet beschikbaar, dus er was geen meting. | _async_report_failures |
| De energiebron '{...}' was stilgevallen. De entiteit '{...}' bestond nog en meldde geen storing, maar had te lang geen nieuwe waarde gerapporteerd om nog als een meting te gelden. | _async_report_failures |
| Er zijn {...} ingeschakelde bronnen van het type '{...}'. Deze waarden zijn niet op te tellen en er is niet te bepalen welke de juiste is, dus geen van beide wordt gebruikt. Schakel er één uit of verwijder er één. | async_report_invalid_rows |
| Het apparaat '{...}' heeft een onbekend type ('{...}') en is uitgeschakeld. Kies een geldig type om het apparaat weer te gebruiken. | async_report_invalid_rows |
| Meerdere bronnen van hetzelfde type | async_report_invalid_rows |
| Multiple enabled sources of type %r; none of them is used ↔ | async_report_invalid_rows |
| Onbekend apparaattype | async_report_invalid_rows |
| Onbekend brontype | async_report_invalid_rows |
| Ongeldige meting ↔ | _async_report_failures |

## `custom_components/domotiapp_energy/validators.py`

| Tekst | Waar |
|---|---|
| Begin en einde van de stille uren mogen niet gelijk zijn. | validate_preferences |
| De begin- en eindtijd van het gereed-venster mogen niet gelijk zijn. | _validate_time_window |
| De begin- en eindtijd van het verbod mogen niet gelijk zijn. | _validate_no_run_window |
| De duur | validate_device_profile |
| De energiebelasting kan niet negatief zijn. | validate_home_profile |
| De hoge prijsgrens moet boven de lage prijsgrens liggen. | _validate_price_thresholds |
| De hoofdzekering moet tussen {...} en {...} ampère liggen. | validate_home_profile |
| De minimale besparing kan niet negatief zijn. | validate_preferences |
| De prijsbron levert de kale marktprijs. Vul de energiebelasting en de opslag van de leverancier per kWh in; zonder die twee is de all-in prijs niet te berekenen en wordt de prijs niet gebruikt. | _validate_price_components |
| De schaalfactor moet groter zijn dan 0. | validate_energy_source |
| De terugleverprijsbron levert de kale marktprijs. Vul in wat de leverancier per teruggeleverde kWh inhoudt; zonder dat bedrag is de vergoeding niet te berekenen en wordt de bron niet gebruikt. Vul 0 in als de leverancier niets inhoudt. | _validate_feed_in_components |
| De waarschuwingsgrens moet tussen {...} en {...} procent liggen. | validate_home_profile |
| Deze bron levert een prijs, maar de eenheid staat op '{...}'. Kies EUR/kWh of ct/kWh. | _validate_unit_matches_type |
| Deze bron meet vermogen, maar de eenheid staat op '{...}'. Kies W of kW. Let op: veel slimme-meterintegraties tonen vooral de meterstand in kWh; die is een totaal en geen vermogen, en levert een netbelasting die honderden keren te hoog is. | _validate_unit_matches_type |
| Deze twee eisen zijn niet allebei te halen: het apparaat mag niet draaien op het moment dat het zou moeten starten om op tijd klaar te zijn. Verruim het verbod, of verzet de tijd waarop het klaar moet zijn. | _validate_no_run_window |
| Dit bedieningsniveau vraagt om aansturing, maar er is geen besturingsmogelijkheid aangevinkt. Controleer wat deze apparatuur werkelijk ondersteunt. | _validate_control |
| Een cyclus van 24 uur of langer is niet te combineren met een gereed-venster: er is dan geen starttijd op de klok te bepalen. | _validate_time_window |
| Gebruik een adres binnen deze Home Assistant, beginnend met een schuine streep — bijvoorbeeld /lovelace/0. | _validate_dashboard_paths |
| Gebruik een geldige tijd in de vorm uu:mm. ↔ | _validate_time_window |
| Gebruik een geldige tijd in de vorm uu:mm. ↔ | _validate_no_run_window |
| Gebruik een geldige tijd in de vorm uu:mm. ↔ | validate_preferences |
| Geef aan of een positieve waarde afname of teruglevering betekent. | _validate_grid_meter |
| Geef aan wat deze bron levert: de kale marktprijs of de all-in prijs die de klant betaalt. Zonder die keuze wordt de prijs niet gebruikt. | _validate_price_source |
| Geef aan wat deze bron levert: de kale marktprijs of de vergoeding die de klant werkelijk krijgt. Zonder die keuze wordt de terugleververgoeding niet gebruikt. | _validate_price_source |
| Het apparaattype '{...}' is niet bekend. Kies een geldig type. | validate_device_profile |
| Het brontype '{...}' is niet bekend. Kies een geldig type. | validate_energy_source |
| Het btw-percentage moet tussen {...} en {...} liggen. | validate_home_profile |
| Het energieverbruik per cyclus | validate_device_profile |
| Het ingevulde netvermogen ligt boven het theoretische maximum van {...} W ({...} x 230 V x {...} A). Controleer de hoofdzekering. | _validate_max_grid_power |
| Het maximale netvermogen moet groter zijn dan 0 W. | _validate_max_grid_power |
| Het minimale zonneoverschot kan niet negatief zijn. | validate_home_profile |
| Het nominale vermogen | validate_device_profile |
| Kies 1 of 3 fasen. | validate_home_profile |
| Kies een geldig bedieningsniveau. | validate_device_profile |
| Kies een geldige eenheid. | validate_energy_source |
| Kies een geldige prioriteit. | validate_device_profile |
| Kies een vast of dynamisch contract. | validate_home_profile |
| Kies hoe de netmeter meet: één ondertekende waarde of gescheiden afname en teruglevering. | _validate_grid_meter |
| Koppel de entiteit die de afname meet. | _validate_grid_meter |
| Koppel de entiteit die de teruglevering meet. | _validate_grid_meter |
| Koppel een entiteit aan deze bron. ↔ | validate_energy_source |
| Koppel een entiteit aan deze bron. ↔ | _validate_grid_meter |
| Noteer waarom aansturing hier is uitgesloten, zodat de reden later terug te vinden is. | _validate_control |
| Toon minimaal {...} en maximaal {...} adviezen. | validate_preferences |
| Voor deze installatie is aansturing uitgesloten. Kies 'alleen monitoren' of 'alleen adviseren'. | _validate_control |
| Vul de naam in van het attribuut dat uitgelezen moet worden. | validate_energy_source |
| {...} kan niet negatief zijn. | validate_device_profile |

## `custom_components/domotiapp_energy/websocket_api.py`

| Tekst | Waar |
|---|---|
| Apparaat gewijzigd | handle_devices_update |
| Apparaat toegevoegd ↔ | handle_devices_create |
| Apparaat verwijderd ↔ | handle_devices_delete |
| Bediening gewijzigd | handle_devices_set_operation |
| De adviesvoorkeuren zijn bijgewerkt. | handle_preferences_update |
| De configuratie is inmiddels gewijzigd. De actuele gegevens zijn opnieuw opgehaald. | _send_revision_conflict |
| De configuratie kon niet worden opgeslagen. | _async_write |
| De energiebron '{...}' is bijgewerkt. | handle_sources_update |
| De energiebron '{...}' is toegevoegd. | handle_sources_create |
| De energiebron '{...}' is verwijderd. | handle_sources_delete |
| De instellingen van '{...}' zijn bijgewerkt. | handle_devices_set_operation |
| De woninggegevens zijn bijgewerkt. | handle_home_update |
| Deze energiebron ↔ | _apply |
| Deze energiebron ↔ | _apply |
| Dit apparaat ↔ | _apply |
| Dit apparaat ↔ | _apply |
| Dit apparaat ↔ | _apply |
| Dit apparaat bestaat niet. | handle_devices_set_ready |
| Dit apparaat heeft een onbekend type en is buiten werking gesteld. | _apply |
| DomotiApp Energy is niet geladen. | _async_get_data |
| Energiebron gewijzigd | handle_sources_update |
| Energiebron toegevoegd | handle_sources_create |
| Energiebron verwijderd | handle_sources_delete |
| Er bestaat al een apparaat met dit ID. | _apply |
| Er bestaat al een energiebron met dit ID. | _apply |
| Gebruik een datum in de vorm jjjj-mm-dd, of null als deze woning niet saldeert. | _iso_date |
| Gebruik een datum in de vorm jjjj-mm-dd, of null. | _iso_date |
| Het apparaat '{...}' is bijgewerkt. | handle_devices_update |
| Het apparaat '{...}' is toegevoegd. | handle_devices_create |
| Het apparaat '{...}' is verwijderd. | handle_devices_delete |
| Voorkeuren gewijzigd | handle_preferences_update |
| Woninggegevens gewijzigd | handle_home_update |
| {...} bestaat niet. | _find |


## Engelse regels

| Tekst | Waar |
|---|---|
| DomotiApp Energy has been removed. The energy configuration is kept in %s under .storage/, so adding the integration again restores it. Delete that file to start over | `custom_components/domotiapp_energy/__init__.py` |
| Clearing ready flag for %r: %s reports %r | `custom_components/domotiapp_energy/coordinator.py` |
| Home Assistant has started: recalculating | `custom_components/domotiapp_energy/coordinator.py` |
| Not reporting source %s (%s): %s, and it has not been read successfully since Home Assistant started | `custom_components/domotiapp_energy/coordinator.py` |
| Could not read the %s statistics | `custom_components/domotiapp_energy/engine/history.py` |
| No recorder: skipping the history | `custom_components/domotiapp_energy/engine/history.py` |
| No alternative coach provider is available in this release | `custom_components/domotiapp_energy/engine/providers.py` |
| Dropping ready flag for %r: %r is not a timestamp | `custom_components/domotiapp_energy/runtime_store.py` |
| Configuration accessed before it was loaded | `custom_components/domotiapp_energy/storage.py` |
| Could not read %s, continuing with a default configuration | `custom_components/domotiapp_energy/storage.py` |
| Device profile %s has unrecognised type %r and is disabled | `custom_components/domotiapp_energy/storage.py` |
| Energy source %s could not be read from %s (%s) | `custom_components/domotiapp_energy/storage.py` |
| Energy source %s has unrecognised type %r and is disabled | `custom_components/domotiapp_energy/storage.py` |
| Migrating %s from schema %s.%s to %s.%s | `custom_components/domotiapp_energy/storage.py` |
| Could not persist a configuration change | `custom_components/domotiapp_energy/websocket_api.py` |
