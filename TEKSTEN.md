# Alle teksten die dit product kan tonen

**Gegenereerd uit `6ec0e32`, versie 0.4.2.**

Eenmalig gegenereerd om door te lezen. Het veroudert zodra er zinnen bijkomen — controleer de commit hierboven tegen de huidige stand van `main` voordat je een ronde begint. Het extractiescript en de bewakingstest komen er zodra het herschrijven begint.

## Hoe je dit leest

De hoofdstukken staan op **zichtbaarheid**: wat een bewoner dagelijks leest staat vooraan, wat alleen de installateur ooit ziet achteraan. Begin bij hoofdstuk 1.

In de kolom *Voorwaarde* staat waar de tekst vandaan komt — de functie of de tabel die hem levert. Dat is een aanwijzing, geen volledige beschrijving van wanneer hij verschijnt.

Twee markeringen:

- **`{...}`** is een waarde die wordt ingevuld: een getal, een naam, een bedrag. De zin blijft als geheel leesbaar.
- **⚠ samengesteld** betekent dat er clausules aan- en uitgezet worden. Dan bestaat de zin die de klant leest nergens in de broncode en kan niemand hem nalezen. Hoofdstuk 15 schrijft die gevallen uit.

Staat een tekst op meer dan één plek, dan staat dat erbij met **↔**. Hoofdstuk 16 zet ze bij elkaar, zodat je ze in één keer kunt rechttrekken in plaats van per plek tegen te komen.

**701 teksten**, waarvan 86 samengesteld en 114 op meer dan één plek.

## 1. Adviesteksten

*Wat de coach zegt. Een bewoner leest deze elke dag, op het Overzicht en in de Energiecoach.* — 27 teksten.

| Tekst | Voorwaarde | Waar |
|---|---|---|
| Aanvullende gegevens nodig | _advise_missing_data | `engine/advisor.py:158` |
| Vul de ontbrekende energiegegevens aan om een betrouwbaar advies te ontvangen. | _advise_missing_data | `engine/advisor.py:160` |
| De teruglevering ligt dicht bij de ingestelde maximale woningbelasting. Schakel indien mogelijk juist extra verbruikers in om het overschot zelf te benutten. | _advise_peak_risk | `engine/advisor.py:194` |
| Het actuele netvermogen ligt dicht bij de ingestelde maximale woningbelasting. Stel extra grootverbruikers indien mogelijk uit. | _advise_peak_risk | `engine/advisor.py:210` |
| Netbelasting hoog | _advise_peak_risk | `engine/advisor.py:208` |
| Teruglevering hoog | _advise_peak_risk | `engine/advisor.py:192` |
| De actuele energieprijs is relatief hoog. Stel flexibel energiegebruik indien mogelijk uit. | _advise_price | `engine/advisor.py:475` |
| De actuele energieprijs is relatief laag. Flexibele apparaten kunnen nu voordeliger worden gebruikt. | _advise_price | `engine/advisor.py:457` |
| Hoge energieprijs | _advise_price | `engine/advisor.py:473` |
| Lage energieprijs | _advise_price | `engine/advisor.py:455` |
| Zonneoverschot beschikbaar ↔ | _advise_solar_surplus | `engine/advisor.py:263` |
| € {...} ⚠ samengesteld | _euro | `engine/advisor.py:371` |
| De actuele energiesituatie vraagt momenteel niet om een aanpassing. | _neutral_advice | `engine/advisor.py:493` |
| Geen actie nodig | _neutral_advice | `engine/advisor.py:492` |
| Dit is een gunstig moment om {...} te gebruiken. ⚠ samengesteld | _surplus_message | `engine/advisor.py:301` |
| Er is momenteel zonneoverschot beschikbaar. | _surplus_message | `engine/advisor.py:300` |
| {...} Zelf verbruiken levert nu echter minder op dan terugleveren: {...} nu gebruiken kost naar schatting {...} ten opzichte van het overschot terugleveren. Wachten tot de terugleververgoeding lager ligt is voordeliger. ⚠ samengesteld | _surplus_message | `engine/advisor.py:315` |
| {...} {...} ⚠ samengesteld ↔ | _surplus_message | `engine/advisor.py:337` |
| {...} {...} Het levert op dit moment niets extra op, maar het kost ook niets. ⚠ samengesteld | _surplus_message | `engine/advisor.py:333` |
| {...} {...} Zolang de salderingsregeling geldt levert dit geen extra besparing op, maar het overschot zelf gebruiken blijft de meest efficiënte keuze. ⚠ samengesteld | _surplus_message | `engine/advisor.py:326` |
| {...} {...} {...} ⚠ samengesteld | _surplus_message | `engine/advisor.py:308` |
| Hoeveel dit oplevert is niet te berekenen zolang de terugleverkosten niet zijn ingevuld — vul ze in bij Woning, of zet ze op 0 als deze aansluiting ze niet betaalt. | _why_no_amount | `engine/advisor.py:423` |
| Hoeveel dit oplevert is niet te berekenen zolang de terugleverprijsbron geen bruikbare waarde geeft. Controleer die bij Energiebronnen. | _why_no_amount | `engine/advisor.py:412` |
| Hoeveel dit oplevert is niet te berekenen zolang er geen actuele prijs is. Controleer de prijsbron bij Energiebronnen. | _why_no_amount | `engine/advisor.py:397` |
| Hoeveel dit oplevert is niet te berekenen zonder de energie per cyclus van {...} — vul die in bij Apparaten. ⚠ samengesteld | _why_no_amount | `engine/advisor.py:386` |
| Hoeveel dit oplevert is niet te berekenen zonder de terugleververgoeding — vul die in bij Woning, of koppel een terugleverprijsbron. | _why_no_amount | `engine/advisor.py:417` |
| Hoeveel dit oplevert is niet te berekenen zonder het vaste leveringstarief — vul dat in bij Woning. | _why_no_amount | `engine/advisor.py:401` |

## 2. Coachantwoorden

*De antwoorden op de vijf vaste vragen, samengesteld in de backend.* — 40 teksten.

| Tekst | Voorwaarde | Waar |
|---|---|---|
| Het vermogen van je thuisbatterij kan niet uitgelezen worden. Een batterij die laadt verbruikt precies het overschot dat hier staat, dus dat getal kan te hoog zijn. Koppel de vermogenssensor van de batterij om dit op te lossen. ↔ | UNREADABLE_BATTERY_SENTENCE | `engine/providers.py:91` |
| de woninggegevens ↔ | _ITEM_LABELS | `engine/providers.py:61` |
| een compleet apparaatprofiel ↔ | _ITEM_LABELS | `engine/providers.py:65` |
| een geldige netbron ↔ | _ITEM_LABELS | `engine/providers.py:62` |
| een geldige zonnebron ↔ | _ITEM_LABELS | `engine/providers.py:63` |
| tijdvensters voor flexibele apparaten ↔ | _ITEM_LABELS | `engine/providers.py:66` |
| all-in prijs in €/kWh ↔ | _MEASUREMENT_LABELS | `engine/providers.py:74` |
| netbelasting in % ↔ | _MEASUREMENT_LABELS | `engine/providers.py:75` |
| netvermogen in W ↔ | _MEASUREMENT_LABELS | `engine/providers.py:76` |
| ontbrekende onderdelen ↔ | _MEASUREMENT_LABELS | `engine/providers.py:78` |
| zonneoverschot in W ↔ | _MEASUREMENT_LABELS | `engine/providers.py:77` |
| De stroomprijs is op dit moment laag, dus er is geen duur verbruik om te vermijden. ↔ | _SCORE_UNAVAILABLE_SENTENCES | `engine/providers.py:141` |
| Er is nog geen energiescore, omdat de installatie nog niet compleet is. De checklist hieronder laat zien wat er ontbreekt. | _SCORE_UNAVAILABLE_SENTENCES | `engine/providers.py:115` |
| Er is nu opwek, maar geen apparaat of batterij die verbruik kan verplaatsen. Er valt daarom niets te benutten dat nu niet al gebeurt. ↔ | _SCORE_UNAVAILABLE_SENTENCES | `engine/providers.py:124` |
| Het tarief is altijd gelijk en er zijn geen zonnepanelen, dus er is geen moment dat beter is dan een ander. Er valt daarom niets te optimaliseren. Het advies blijft gewoon werken. ↔ | _SCORE_UNAVAILABLE_SENTENCES | `engine/providers.py:119` |
| Je panelen leveren op dit moment niets en de stroomprijs is laag. Er is nu dus geen overschot om te benutten en geen duur verbruik om te vermijden. ↔ | _SCORE_UNAVAILABLE_SENTENCES | `engine/providers.py:132` |
| Je panelen leveren op dit moment niets, en bij een vast tarief is het ene moment niet beter dan het andere. Er is nu dus niets te verbeteren. ↔ | _SCORE_UNAVAILABLE_SENTENCES | `engine/providers.py:137` |
| Zolang de lage en de hoge prijsdrempel niet zijn ingevuld, is niet te bepalen of dit een duur moment is. Vul ze in bij Installatie. ↔ | _SCORE_UNAVAILABLE_SENTENCES | `engine/providers.py:128` |
| € {...} per kWh ⚠ samengesteld | _format_price | `engine/providers.py:265` |
| Alle gegevens voor een betrouwbaar advies zijn ingevuld. ↔ | _missing_data | `engine/providers.py:315` |
| Niet van toepassing op deze woning, en dus niet meegeteld: {...}. ⚠ samengesteld ↔ | _missing_data | `engine/providers.py:319` |
| Nog ontbrekend: {...}. ⚠ samengesteld | _missing_data | `engine/providers.py:313` |
| De netbelasting is niet te bepalen. Vul het maximale netvermogen in en koppel een netbron. | _peak_risk | `engine/providers.py:277` |
| Nee | _peak_risk | `engine/providers.py:284` |
| levert terug met ↔ | _peak_risk | `engine/providers.py:283` |
| {...}. De woning {...} {...}% van het ingestelde maximale netvermogen. ⚠ samengesteld | _peak_risk | `engine/providers.py:287` |
| De energiescore is nog niet berekend. ↔ | _score_breakdown | `engine/providers.py:357` |
| De energiescore is nog niet berekend. ↔ | _score_breakdown | `engine/providers.py:348` |
| De score op dit moment is {...}, opgebouwd uit: {...}. ⚠ samengesteld | _score_breakdown | `engine/providers.py:360` |
| Niet van toepassing op deze woning, en dus niet meegewogen: {...}. ⚠ samengesteld | _score_breakdown | `engine/providers.py:370` |
| {...} {...} ⚠ samengesteld ↔ | _score_breakdown | `engine/providers.py:352` |
| Er is op dit moment geen aanleiding om een apparaat te verplaatsen of juist nu te gebruiken. | _use_device_now | `engine/providers.py:252` |
| Ja. De all-in energieprijs is nu {...} en ligt onder de ingestelde lage prijsgrens. ⚠ samengesteld | _use_device_now | `engine/providers.py:242` |
| Ja. De woning levert veel terug aan het net; dat overschot kun je nu beter zelf gebruiken. | _use_device_now | `engine/providers.py:228` |
| Nu is geen gunstig moment: de all-in energieprijs is {...} en ligt boven de ingestelde hoge prijsgrens. ⚠ samengesteld | _use_device_now | `engine/providers.py:247` |
| Nu is geen gunstig moment: de netbelasting ligt dicht bij het ingestelde maximum. | _use_device_now | `engine/providers.py:233` |
| Er is op dit moment geen advies. | _why_advice | `engine/providers.py:195` |
| Gebaseerd op {...}. ⚠ samengesteld | _why_advice | `engine/providers.py:204` |
| {...}: {...} ⚠ samengesteld ↔ | _why_advice | `engine/providers.py:199` |
| No alternative coach provider is available in this release | async_generate | `engine/providers.py:187` |

## 3. Overzicht — tegels, meldingen en labels

*Het eerste scherm. Alles hier staat dagelijks in beeld.* — 43 teksten.

| Tekst | Voorwaarde | Waar |
|---|---|---|
| Niet beschikbaar ↔ | EMPTY_NOT_AVAILABLE | `frontend/tabs/overview.js:34` |
| Nog niet ingesteld | EMPTY_NOT_CONFIGURED | `frontend/tabs/overview.js:33` |
| De stroomprijs is op dit moment laag, dus er is geen duur verbruik om te vermijden. ↔ | cheap_price | `frontend/tabs/overview.js:101` |
| Actief | create | `frontend/tabs/overview.js:296` |
| Actuele energieprijs ↔ | create | `frontend/tabs/overview.js:171` |
| Actuele situatie | create | `frontend/tabs/overview.js:151` |
| Advies ↔ | create | `frontend/tabs/overview.js:193` |
| All-in, afgeleid van een marktprijs van {...}. ⚠ samengesteld | create | `frontend/tabs/overview.js:288` |
| Alle gegevens voor een betrouwbaar advies zijn ingevuld. ↔ | create | `frontend/tabs/overview.js:345` |
| Datakwaliteit ↔ | create | `frontend/tabs/overview.js:132` |
| Energiescore ↔ | create | `frontend/tabs/overview.js:119` |
| Energiescore ↔ | create | `frontend/tabs/overview.js:128` |
| Er zijn nog geen energiebronnen gekoppeld. Ga naar het tabblad Energiebronnen om je slimme meter of omvormer te koppelen. | create | `frontend/tabs/overview.js:305` |
| Er zijn op dit moment geen waarschuwingen. | create | `frontend/tabs/overview.js:250` |
| Fout ↔ | create | `frontend/tabs/overview.js:296` |
| Geen bruikbare prijsbron | create | `frontend/tabs/overview.js:278` |
| Geen cijfer | create | `frontend/tabs/overview.js:130` |
| Het vermogen van je thuisbatterij kan niet uitgelezen worden. Een batterij die laadt verbruikt precies het overschot dat hier staat, dus dat getal kan te hoog zijn. Koppel de vermogenssensor van de batterij om dit op te lossen. ↔ | create | `frontend/tabs/overview.js:369` |
| Laatste berekening ↔ | create | `frontend/tabs/overview.js:145` |
| Laden… | create | `frontend/tabs/overview.js:296` |
| Negatief betekent teruglevering aan het net. | create | `frontend/tabs/overview.js:352` |
| Netvermogen ↔ | create | `frontend/tabs/overview.js:152` |
| Niet van toepassing bij een vast contract | create | `frontend/tabs/overview.js:270` |
| Nog geen advies berekend ↔ | create | `frontend/tabs/overview.js:387` |
| Nog niet berekend ↔ | create | `frontend/tabs/overview.js:146` |
| Percentage van maximum | create | `frontend/tabs/overview.js:164` |
| Piekrisico: de netbelasting ligt op of boven de ingestelde waarschuwingsgrens. | create | `frontend/tabs/overview.js:380` |
| Status | create | `frontend/tabs/overview.js:144` |
| Waarschuwing ↔ | create | `frontend/tabs/overview.js:233` |
| Waarschuwingen | create | `frontend/tabs/overview.js:198` |
| Zodra er een energiebron gekoppeld is, verschijnt hier het hoofdadvies. ↔ | create | `frontend/tabs/overview.js:390` |
| Zonneoverschot ↔ | create | `frontend/tabs/overview.js:160` |
| Zonneproductie | create | `frontend/tabs/overview.js:156` |
| op dit moment | create | `frontend/tabs/overview.js:129` |
| {...} per kWh ⚠ samengesteld | create | `frontend/tabs/overview.js:284` |
| {...} van de {...} onderdelen van de datakwaliteit is nog niet compleet. Het tabblad Energiecoach laat zien welke. ⚠ samengesteld | create | `frontend/tabs/overview.js:342` |
| Er is nog geen cijfer, omdat de installatie nog niet compleet is. Het tabblad Energiecoach laat zien wat er ontbreekt. | incomplete_setup | `frontend/tabs/overview.js:57` |
| Overzicht | label | `frontend/tabs/overview.js:112` |
| Je panelen leveren op dit moment niets en de stroomprijs is laag. Er is nu dus geen overschot om te benutten en geen duur verbruik om te vermijden. ↔ | no_sun_cheap_price | `frontend/tabs/overview.js:86` |
| Je panelen leveren op dit moment niets, en bij een vast tarief is het ene moment niet beter dan het andere. Er is nu dus niets te verbeteren. ↔ | no_sun_fixed_tariff | `frontend/tabs/overview.js:94` |
| Het tarief is altijd gelijk en er zijn geen zonnepanelen, dus er is geen moment dat beter is dan een ander. Er valt daarom niets te optimaliseren. Het advies blijft gewoon werken. ↔ | no_variable_signal | `frontend/tabs/overview.js:71` |
| Er is nu opwek, maar geen apparaat of batterij die verbruik kan verplaatsen. Er valt daarom niets te benutten dat nu niet al gebeurt. ↔ | nothing_movable | `frontend/tabs/overview.js:79` |
| Zolang de lage en de hoge prijsdrempel niet zijn ingevuld, is niet te bepalen of dit een duur moment is. Vul ze in bij Installatie. ↔ | price_thresholds_missing | `frontend/tabs/overview.js:64` |

## 4. Energiecoach — het scherm

*De omlijsting rond de adviezen en de vraagselector.* — 34 teksten.

| Tekst | Voorwaarde | Waar |
|---|---|---|
| Hoe is mijn energiescore berekend? | QUESTIONS | `frontend/tabs/coach.js:46` |
| Is er risico op piekbelasting? | QUESTIONS | `frontend/tabs/coach.js:44` |
| Kan ik nu het beste een apparaat gebruiken? | QUESTIONS | `frontend/tabs/coach.js:43` |
| Waarom krijg ik dit advies? | QUESTIONS | `frontend/tabs/coach.js:42` |
| Welke gegevens ontbreken nog? | QUESTIONS | `frontend/tabs/coach.js:45` |
| Advies ↔ | create | `frontend/tabs/coach.js:172` |
| Alle gegevens voor een betrouwbaar advies zijn ingevuld. ↔ | create | `frontend/tabs/coach.js:328` |
| Bezig met berekenen… | create | `frontend/tabs/coach.js:242` |
| Deze vraag is nog niet beantwoord. Bereken opnieuw zodra er gegevens gekoppeld zijn. | create | `frontend/tabs/coach.js:234` |
| Er is op dit moment geen aanvullend advies. | create | `frontend/tabs/coach.js:111` |
| Geschatte besparing | create | `frontend/tabs/coach.js:91` |
| Het advies is opnieuw berekend. | create | `frontend/tabs/coach.js:247` |
| Hoofdadvies | create | `frontend/tabs/coach.js:88` |
| Kies een vraag; het antwoord verschijnt in beeld. | create | `frontend/tabs/coach.js:127` |
| Laatste berekening ↔ | create | `frontend/tabs/coach.js:93` |
| Niet te berekenen | create | `frontend/tabs/coach.js:91` |
| Niet van toepassing op deze woning, en dus niet meegeteld: {...}. ⚠ samengesteld ↔ | create | `frontend/tabs/coach.js:320` |
| Nog geen advies berekend ↔ | create | `frontend/tabs/coach.js:270` |
| Nog niet berekend ↔ | create | `frontend/tabs/coach.js:93` |
| Onbekend | create | `frontend/tabs/coach.js:92` |
| Ontbrekende gegevens | create | `frontend/tabs/coach.js:117` |
| Opnieuw berekenen ↔ | create | `frontend/tabs/coach.js:95` |
| Overige adviezen | create | `frontend/tabs/coach.js:109` |
| Reden ↔ | create | `frontend/tabs/coach.js:92` |
| Vraag het de coach | create | `frontend/tabs/coach.js:123` |
| Zodra er een energiebron gekoppeld is, verschijnt hier het hoofdadvies. ↔ | create | `frontend/tabs/coach.js:273` |
| geschatte besparing € {...})} ⚠ samengesteld | create | `frontend/tabs/coach.js:213` |
| {...}: {...} ⚠ samengesteld ↔ | create | `frontend/tabs/coach.js:202` |
| € {...})} ⚠ samengesteld | create | `frontend/tabs/coach.js:280` |
| Probleem | error | `frontend/tabs/coach.js:53` |
| Advies ↔ | info | `frontend/tabs/coach.js:50` |
| Energiecoach | label | `frontend/tabs/coach.js:81` |
| Advies ↔ | success | `frontend/tabs/coach.js:51` |
| Waarschuwing ↔ | warning | `frontend/tabs/coach.js:52` |

## 5. Woorden voor codes

*Vertalingen van machinecodes naar Nederlands. Ontbreekt er één, dan leest de klant de code zelf.* — 22 teksten.

| Tekst | Voorwaarde | Waar |
|---|---|---|
| een compleet apparaatprofiel ↔ | device_profile_complete | `frontend/core/labels.js:46` |
| Er is een verplaatsbaar apparaat beschikbaar | flexible_device_available | `frontend/core/labels.js:33` |
| tijdvensters voor flexibele apparaten ↔ | flexible_devices_have_time_window | `frontend/core/labels.js:47` |
| een geldige netbron ↔ | grid_source_valid | `frontend/core/labels.js:43` |
| De energieprijs is hoog | high_energy_price | `frontend/core/labels.js:32` |
| De teruglevering is hoog | high_grid_export | `frontend/core/labels.js:30` |
| De netbelasting is hoog | high_grid_load | `frontend/core/labels.js:29` |
| de woninggegevens ↔ | home_profile_complete | `frontend/core/labels.js:42` |
| De besparing is te klein om te melden | insufficient_savings | `frontend/core/labels.js:36` |
| Een gekoppelde entiteit levert geen bruikbare waarde | invalid_entity_state | `frontend/core/labels.js:27` |
| De energieprijs is laag | low_energy_price | `frontend/core/labels.js:31` |
| Er ontbreken gegevens | missing_required_data | `frontend/core/labels.js:26` |
| netbelasting in % ↔ | netbelasting_procent | `frontend/core/labels.js:59` |
| netvermogen in W ↔ | netvermogen_w | `frontend/core/labels.js:60` |
| De situatie vraagt niet om een aanpassing | neutral_energy_situation | `frontend/core/labels.js:37` |
| ontbrekende onderdelen ↔ | ontbrekende_onderdelen | `frontend/core/labels.js:62` |
| Buiten het toegestane tijdvenster | outside_allowed_window | `frontend/core/labels.js:34` |
| all-in prijs in €/kWh ↔ | prijs_eur_kwh | `frontend/core/labels.js:58` |
| Het is nu stille uren | quiet_hours_active | `frontend/core/labels.js:35` |
| een geldige zonnebron ↔ | solar_source_valid | `frontend/core/labels.js:44` |
| Er is zonneoverschot | solar_surplus_available | `frontend/core/labels.js:28` |
| zonneoverschot in W ↔ | zonneoverschot_w | `frontend/core/labels.js:61` |

## 6. Logboekregels

*Wat er in het logboek verschijnt. Wordt gelezen als er iets misgaat.* — 53 teksten.

| Tekst | Voorwaarde | Waar |
|---|---|---|
| Configuration was modified: expected revision {...}, current revision is {...} ⚠ samengesteld | __init__ | `storage.py:65` |
| Deze energiebron ↔ | _apply | `websocket_api.py:697` |
| Deze energiebron ↔ | _apply | `websocket_api.py:662` |
| Dit apparaat ↔ | _apply | `websocket_api.py:813` |
| Dit apparaat ↔ | _apply | `websocket_api.py:859` |
| Dit apparaat ↔ | _apply | `websocket_api.py:778` |
| Dit apparaat heeft een onbekend type en is buiten werking gesteld. | _apply | `websocket_api.py:869` |
| Er bestaat al een apparaat met dit ID. | _apply | `websocket_api.py:738` |
| Er bestaat al een energiebron met dit ID. | _apply | `websocket_api.py:622` |
| DomotiApp Energy is niet geladen. | _async_get_data | `websocket_api.py:233` |
| De woning {...} {...}% van het ingestelde maximale netvermogen. Dat ligt op of boven de waarschuwingsgrens van {...}%. ⚠ samengesteld | _async_log_findings | `coordinator.py:348` |
| Er is {...} W zonneoverschot beschikbaar. ⚠ samengesteld | _async_log_findings | `coordinator.py:367` |
| Piekbelasting gesignaleerd | _async_log_findings | `coordinator.py:347` |
| Zonneoverschot beschikbaar ↔ | _async_log_findings | `coordinator.py:366` |
| levert terug met ↔ | _async_log_findings | `coordinator.py:344` |
| Cannot downgrade {...} from schema version {...}.{...} ⚠ samengesteld | _async_migrate_func | `storage.py:94` |
| Bron niet beschikbaar ↔ | _async_report_failures | `storage.py:335` |
| De energiebron '{...}' kon niet worden uitgelezen: de entiteit '{...}' bestaat niet of levert op dit moment geen waarde. (reden: {...}) ⚠ samengesteld | _async_report_failures | `storage.py:337` |
| De energiebron '{...}' leverde geen bruikbare meetwaarde. Controleer bij de entiteit '{...}' de gekozen waardebron, het attribuut en de eenheid. (reden: {...}) ⚠ samengesteld | _async_report_failures | `storage.py:344` |
| Ongeldige meting ↔ | _async_report_failures | `storage.py:342` |
| Could not write {...} ⚠ samengesteld | _async_write | `storage.py:592` |
| De configuratie kon niet worden opgeslagen. | _async_write | `websocket_api.py:267` |
| {...} bestaat niet. ⚠ samengesteld | _find | `websocket_api.py:380` |
| {...} recalculate after configuration change ⚠ samengesteld | _handle_configuration_change | `coordinator.py:270` |
| De configuratie is inmiddels gewijzigd. De actuele gegevens zijn opnieuw opgehaald. | _send_revision_conflict | `websocket_api.py:287` |
| Advies opnieuw berekend | async_recalculate | `coordinator.py:230` |
| Het energieadvies is opnieuw berekend. | async_recalculate | `coordinator.py:231` |
| De energiebron '{...}' heeft een onbekend type ('{...}') en is uitgeschakeld. Kies een geldig type om de bron weer te gebruiken. ⚠ samengesteld | async_report_invalid_rows | `storage.py:264` |
| Er zijn {...} ingeschakelde bronnen van het type '{...}'. Deze waarden zijn niet op te tellen en er is niet te bepalen welke de juiste is, dus geen van beide wordt gebruikt. Schakel er één uit of verwijder er één. ⚠ samengesteld | async_report_invalid_rows | `storage.py:242` |
| Het apparaat '{...}' heeft een onbekend type ('{...}') en is uitgeschakeld. Kies een geldig type om het apparaat weer te gebruiken. ⚠ samengesteld | async_report_invalid_rows | `storage.py:283` |
| Meerdere bronnen van hetzelfde type | async_report_invalid_rows | `storage.py:241` |
| Onbekend apparaattype | async_report_invalid_rows | `storage.py:282` |
| Onbekend brontype | async_report_invalid_rows | `storage.py:263` |
| {...} safety recalculation ⚠ samengesteld | async_start | `coordinator.py:187` |
| Configuration accessed before it was loaded | config | `storage.py:149` |
| Apparaat toegevoegd ↔ | handle_devices_create | `websocket_api.py:748` |
| Het apparaat '{...}' is toegevoegd. ⚠ samengesteld ↔ | handle_devices_create | `websocket_api.py:749` |
| Apparaat verwijderd ↔ | handle_devices_delete | `websocket_api.py:822` |
| Het apparaat '{...}' is verwijderd. ⚠ samengesteld ↔ | handle_devices_delete | `websocket_api.py:823` |
| Bediening gewijzigd | handle_devices_set_operation | `websocket_api.py:895` |
| De instellingen van '{...}' zijn bijgewerkt. ⚠ samengesteld | handle_devices_set_operation | `websocket_api.py:896` |
| Apparaat gewijzigd | handle_devices_update | `websocket_api.py:786` |
| Het apparaat '{...}' is bijgewerkt. ⚠ samengesteld ↔ | handle_devices_update | `websocket_api.py:787` |
| De woninggegevens zijn bijgewerkt. | handle_home_update | `websocket_api.py:536` |
| Woninggegevens gewijzigd | handle_home_update | `websocket_api.py:535` |
| De adviesvoorkeuren zijn bijgewerkt. | handle_preferences_update | `websocket_api.py:589` |
| Voorkeuren gewijzigd | handle_preferences_update | `websocket_api.py:588` |
| De energiebron '{...}' is toegevoegd. ⚠ samengesteld ↔ | handle_sources_create | `websocket_api.py:633` |
| Energiebron toegevoegd | handle_sources_create | `websocket_api.py:632` |
| De energiebron '{...}' is verwijderd. ⚠ samengesteld ↔ | handle_sources_delete | `websocket_api.py:707` |
| Energiebron verwijderd | handle_sources_delete | `websocket_api.py:706` |
| De energiebron '{...}' is bijgewerkt. ⚠ samengesteld ↔ | handle_sources_update | `websocket_api.py:671` |
| Energiebron gewijzigd | handle_sources_update | `websocket_api.py:670` |

## 7. Apparaten — velden en hulpteksten

*Deels bewonersgebied: de bedieningsvelden zijn van hem.* — 142 teksten.

| Tekst | Voorwaarde | Waar |
|---|---|---|
| Aan- en uitschakelen ↔ | CAPABILITY_OPTIONS | `frontend/tabs/devices.js:104` |
| Laadstroom instellen ↔ | CAPABILITY_OPTIONS | `frontend/tabs/devices.js:106` |
| Uitlezen ↔ | CAPABILITY_OPTIONS | `frontend/tabs/devices.js:103` |
| Vermogensgrens instellen ↔ | CAPABILITY_OPTIONS | `frontend/tabs/devices.js:105` |
| Dinsdag | DAY_OPTIONS | `frontend/tabs/devices.js:125` |
| Donderdag | DAY_OPTIONS | `frontend/tabs/devices.js:127` |
| Maandag | DAY_OPTIONS | `frontend/tabs/devices.js:124` |
| Vrijdag | DAY_OPTIONS | `frontend/tabs/devices.js:128` |
| Woensdag | DAY_OPTIONS | `frontend/tabs/devices.js:126` |
| Zaterdag | DAY_OPTIONS | `frontend/tabs/devices.js:129` |
| Zondag | DAY_OPTIONS | `frontend/tabs/devices.js:130` |
| Batterijniveau | ENTITY_LINKS | `frontend/tabs/devices.js:177` |
| De aanvoertemperatuur van de warmtepomp. | ENTITY_LINKS | `frontend/tabs/devices.js:170` |
| De entiteit die zegt of het apparaat aan staat of draait. | ENTITY_LINKS | `frontend/tabs/devices.js:145` |
| De laadtoestand van de auto, als de laadpaal die meldt. | ENTITY_LINKS | `frontend/tabs/devices.js:181` |
| De laadtoestand van de thuisbatterij, in procenten. | ENTITY_LINKS | `frontend/tabs/devices.js:180` |
| De meterstand of het verbruik van dit apparaat. | ENTITY_LINKS | `frontend/tabs/devices.js:157` |
| De ruimtetemperatuur die deze airco regelt. | ENTITY_LINKS | `frontend/tabs/devices.js:172` |
| De watertemperatuur in de boiler. | ENTITY_LINKS | `frontend/tabs/devices.js:171` |
| Energieverbruikentiteit | ENTITY_LINKS | `frontend/tabs/devices.js:155` |
| Het actuele vermogen van dit apparaat. | ENTITY_LINKS | `frontend/tabs/devices.js:151` |
| Hoe lang de lopende cyclus nog duurt. | ENTITY_LINKS | `frontend/tabs/devices.js:163` |
| Resterende tijd | ENTITY_LINKS | `frontend/tabs/devices.js:161` |
| Statusentiteit | ENTITY_LINKS | `frontend/tabs/devices.js:143` |
| Temperatuursensor | ENTITY_LINKS | `frontend/tabs/devices.js:167` |
| Vermogensentiteit | ENTITY_LINKS | `frontend/tabs/devices.js:149` |
| Aansturing ↔ | SECTIONS | `frontend/tabs/devices.js:706` |
| Apparaat ↔ | SECTIONS | `frontend/tabs/devices.js:685` |
| Koppelingen en notities | SECTIONS | `frontend/tabs/devices.js:716` |
| Verbruik | SECTIONS | `frontend/tabs/devices.js:690` |
| Wanneer het mag draaien | SECTIONS | `frontend/tabs/devices.js:695` |
| Alleen adviseren ↔ | advice_only | `frontend/tabs/devices.js:97` |
| Airconditioning | air_conditioning | `frontend/tabs/devices.js:66` |
| Vragen om goedkeuring ↔ | approval_required | `frontend/tabs/devices.js:98` |
| Automatisch aansturen ↔ | automatic | `frontend/tabs/devices.js:99` |
| DomotiApp Energy rekent zelf terug wanneer het apparaat uiterlijk moet starten om dit te halen. | base | `frontend/tabs/devices.js:420` |
| Laat beide tijden leeg als er geen venster is; het apparaat mag dan op elk uur. Een venster telt wel mee voor de datakwaliteit, omdat het advies er gerichter van wordt. | base | `frontend/tabs/devices.js:415` |
| Vul hierboven een duur in, dan rekent DomotiApp Energy terug wanneer het apparaat uiterlijk moet starten. Zonder duur geldt dit alleen als "mag hierna niet meer draaien". | base | `frontend/tabs/devices.js:423` |
| Maakt geluid | behaviourFields | `frontend/tabs/devices.js:474` |
| Standaard voor dit type: {...}. Alleen verplaatsbare apparaten krijgen een verplaatsingsadvies, en alleen die hebben een tijdvenster nodig. ⚠ samengesteld | behaviourFields | `frontend/tabs/devices.js:483` |
| Standaard voor dit type: {...}. Lawaaiige apparaten worden tijdens de stille uren niet geadviseerd. ⚠ samengesteld | behaviourFields | `frontend/tabs/devices.js:475` |
| Verplaatsbaar in de tijd | behaviourFields | `frontend/tabs/devices.js:482` |
| Duur van een cyclus | charger | `frontend/tabs/devices.js:350` |
| Duur van een laadsessie | charger | `frontend/tabs/devices.js:350` |
| Energie per cyclus | charger | `frontend/tabs/devices.js:342` |
| Energie per laadsessie | charger | `frontend/tabs/devices.js:342` |
| Maximaal laadvermogen | charger | `frontend/tabs/devices.js:336` |
| Nominaal vermogen | charger | `frontend/tabs/devices.js:336` |
| Annuleren ↔ | create | `frontend/tabs/devices.js:836` |
| Apparaat ↔ | create | `frontend/tabs/devices.js:779` |
| Apparaat bewerken | create | `frontend/tabs/devices.js:980` |
| Apparaat toevoegen ↔ | create | `frontend/tabs/devices.js:732` |
| Apparaat toevoegen ↔ | create | `frontend/tabs/devices.js:980` |
| Apparaat verwijderen | create | `frontend/tabs/devices.js:1229` |
| Apparaten ↔ | create | `frontend/tabs/devices.js:729` |
| Bewerken ↔ | create | `frontend/tabs/devices.js:861` |
| Bewerken ↔ | create | `frontend/tabs/devices.js:883` |
| Bezig met opslaan… ↔ | create | `frontend/tabs/devices.js:1121` |
| Bezig met verwijderen… ↔ | create | `frontend/tabs/devices.js:1199` |
| Compleet. ↔ | create | `frontend/tabs/devices.js:963` |
| De configuratie is intussen ergens anders gewijzigd. Er is niets verwijderd; de lijst is opnieuw geladen. ↔ | create | `frontend/tabs/devices.js:1214` |
| De configuratie is intussen ergens anders gewijzigd. Je wijzigingen zijn niet opgeslagen; de lijst is opnieuw geladen. ↔ | create | `frontend/tabs/devices.js:1159` |
| Deze ingevulde gegevens horen niet bij dit apparaattype en verdwijnen bij opslaan: {...}. Zet het type terug om ze te behouden. ⚠ samengesteld | create | `frontend/tabs/devices.js:1034` |
| Dit apparaat is compleet: alles wat de datakwaliteit vraagt is ingevuld. | create | `frontend/tabs/devices.js:1027` |
| Het apparaat '{...}' is bijgewerkt. ⚠ samengesteld ↔ | create | `frontend/tabs/devices.js:1150` |
| Het apparaat '{...}' is toegevoegd. ⚠ samengesteld ↔ | create | `frontend/tabs/devices.js:1151` |
| Het apparaat '{...}' is verwijderd. ⚠ samengesteld ↔ | create | `frontend/tabs/devices.js:1207` |
| Instellen | create | `frontend/tabs/devices.js:883` |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Verwerp je ze, dan zijn ze weg. ↔ | create | `frontend/tabs/devices.js:1263` |
| Naamloos apparaat | create | `frontend/tabs/devices.js:878` |
| Nog geen apparaten. Voeg de apparaten toe waarover DomotiApp Energy mag adviseren, met hun vermogen, verbruik per cyclus en tijdvenster. | create | `frontend/tabs/devices.js:761` |
| Nog niet compleet: {...} ⚠ samengesteld ↔ | create | `frontend/tabs/devices.js:931` |
| Nog niet compleet: {...} {...}. Telt niet mee voor de datakwaliteit. ⚠ samengesteld | create | `frontend/tabs/devices.js:949` |
| Nog nodig voor een compleet apparaat: {...}. Opslaan mag ook zonder — het apparaat telt dan alleen nog niet mee voor de datakwaliteit. ⚠ samengesteld | create | `frontend/tabs/devices.js:1023` |
| Onbekend apparaattype '{...}'. Dit apparaat wordt niet gebruikt. ⚠ samengesteld | create | `frontend/tabs/devices.js:916` |
| Opslaan ↔ | create | `frontend/tabs/devices.js:835` |
| Terug naar het formulier ↔ | create | `frontend/tabs/devices.js:1266` |
| Uitgeschakeld — krijgt geen advies. | create | `frontend/tabs/devices.js:923` |
| Verwerpen ↔ | create | `frontend/tabs/devices.js:1265` |
| Verwijderen ↔ | create | `frontend/tabs/devices.js:862` |
| Weet je zeker dat je '{...}' wilt verwijderen? Er wordt daarna niet meer over geadviseerd. ⚠ samengesteld | create | `frontend/tabs/devices.js:1231` |
| Wijzigingen verwerpen? ↔ | create | `frontend/tabs/devices.js:1261` |
| zonder naam ↔ | create | `frontend/tabs/devices.js:1145` |
| · Aansturing uitgesloten — {...} ⚠ samengesteld | create | `frontend/tabs/devices.js:939` |
| Kritiek | critical | `frontend/tabs/devices.js:92` |
| Vaatwasser | dishwasher | `frontend/tabs/devices.js:63` |
| Droger | dryer | `frontend/tabs/devices.js:65` |
| Elektrische boiler | electric_boiler | `frontend/tabs/devices.js:62` |
| energie per cyclus | energy_per_cycle_kwh | `frontend/tabs/devices.js:251` |
| Laadpaal | ev_charger | `frontend/tabs/devices.js:59` |
| Aansturing uitgesloten voor deze installatie ↔ | fields | `frontend/tabs/devices.js:529` |
| Alleen registreren: er wordt niets aangestuurd. Niets aanvinken betekent "niet opgegeven", niet "kan niets". | fields | `frontend/tabs/devices.js:523` |
| Bedieningsniveau ↔ | fields | `frontend/tabs/devices.js:505` |
| Bij meerdere kandidaten wint de hoogste prioriteit. | fields | `frontend/tabs/devices.js:293` |
| DomotiApp Energy adviseert in deze versie alleen; alles behalve "alleen monitoren" wordt als adviseren behandeld. | fields | `frontend/tabs/devices.js:507` |
| Een afspraak met de klant, los van wat dit apparaat kan. | fields | `frontend/tabs/devices.js:530` |
| Een uitgeschakeld apparaat krijgt geen advies. | fields | `frontend/tabs/devices.js:281` |
| Ingeschakeld ↔ | fields | `frontend/tabs/devices.js:280` |
| Locatie | fields | `frontend/tabs/devices.js:286` |
| Naam ↔ | fields | `frontend/tabs/devices.js:272` |
| Notities ↔ | fields | `frontend/tabs/devices.js:309` |
| Prioriteit | fields | `frontend/tabs/devices.js:292` |
| Soort apparaat | fields | `frontend/tabs/devices.js:275` |
| Waar staat het? Alleen om het terug te herkennen. | fields | `frontend/tabs/devices.js:287` |
| Wat kan dit apparaat? | fields | `frontend/tabs/devices.js:521` |
| Overig, alleen meten | generic_monitor | `frontend/tabs/devices.js:69` |
| Overig, inplanbaar | generic_schedulable | `frontend/tabs/devices.js:68` |
| Warmtepomp | heat_pump | `frontend/tabs/devices.js:61` |
| Hoog | high | `frontend/tabs/devices.js:91` |
| Thuisbatterij ↔ | home_battery | `frontend/tabs/devices.js:60` |
| Dagen ↔ | if | `frontend/tabs/devices.js:462` |
| In minuten, voor een typische laadbeurt. Wordt getoetst aan het tijdvenster hieronder. | if | `frontend/tabs/devices.js:391` |
| In minuten. Wordt getoetst aan het tijdvenster hieronder. | if | `frontend/tabs/devices.js:395` |
| Klaar uiterlijk om ↔ | if | `frontend/tabs/devices.js:435` |
| Niet eerder klaar dan ↔ | if | `frontend/tabs/devices.js:449` |
| Noteer waarom, zodat dit later terug te vinden is. ↔ | if | `frontend/tabs/devices.js:539` |
| Op welke dagen dit apparaat mag draaien. | if | `frontend/tabs/devices.js:463` |
| Optioneel. Handig voor was die niet uren nat mag blijven liggen: zet hier bijvoorbeeld 06:00 als je hem om 07:00 uithaalt. Ligt deze tijd ná "klaar uiterlijk om", dan loopt het venster door tot de volgende dag — 22:00 tot 06:00 is het normale geval. | if | `frontend/tabs/devices.js:454` |
| Reden ↔ | if | `frontend/tabs/devices.js:538` |
| Dagen ↔ | known | `frontend/tabs/devices.js:614` |
| Klaar uiterlijk om ↔ | known | `frontend/tabs/devices.js:612` |
| Niet eerder klaar dan ↔ | known | `frontend/tabs/devices.js:613` |
| Reden ↔ | known | `frontend/tabs/devices.js:615` |
| Apparaten ↔ | label | `frontend/tabs/devices.js:724` |
| Laag | low | `frontend/tabs/devices.js:89` |
| Alleen monitoren | monitor_only | `frontend/tabs/devices.js:96` |
| nominaal vermogen | nominal_power_w | `frontend/tabs/devices.js:250` |
| Normaal | normal | `frontend/tabs/devices.js:90` |
| De energie van een gemiddelde draaiperiode. | perType | `frontend/tabs/devices.js:380` |
| De energie van één droogbeurt. | perType | `frontend/tabs/devices.js:379` |
| De energie van één programma, bijvoorbeeld 1,0 tot 1,5 kWh. | perType | `frontend/tabs/devices.js:377` |
| De energie van één wasbeurt. | perType | `frontend/tabs/devices.js:378` |
| Een schatting van een typische laadbeurt, bijvoorbeeld 10 kWh voor een dagelijkse rit. Exact kan niet: DomotiApp Energy weet niet hoe leeg de auto is, dus het advies rekent met dit getal en houdt zijn betrouwbaarheid daarom op "gemiddeld". | perType | `frontend/tabs/devices.js:373` |
| Het elektrische opgenomen vermogen, niet het thermische. | perType | `frontend/tabs/devices.js:364` |
| Het hoogste vermogen waarmee deze paal kan laden — niet wat de auto er vandaag van afneemt. | perType | `frontend/tabs/devices.js:361` |
| Het laad- of ontlaadvermogen van de batterij. | perType | `frontend/tabs/devices.js:363` |
| Het vermogen tijdens gebruik. | perType | `frontend/tabs/devices.js:367` |
| Het vermogen van het verwarmingselement. | perType | `frontend/tabs/devices.js:365` |
| Zwembadpomp | pool_pump | `frontend/tabs/devices.js:67` |
| De energie van één cyclus. | return | `frontend/tabs/devices.js:383` |
| Zonder dit getal is er geen besparing te berekenen. | return | `frontend/tabs/devices.js:384` |
| Wasmachine | washing_machine | `frontend/tabs/devices.js:64` |

## 8. Energiebronnen — velden en hulpteksten

*Installateursgebied.* — 136 teksten.

| Tekst | Voorwaarde | Waar |
|---|---|---|
| Aan- en uitschakelen ↔ | CAPABILITY_OPTIONS | `frontend/tabs/sources.js:121` |
| Laadstroom instellen ↔ | CAPABILITY_OPTIONS | `frontend/tabs/sources.js:123` |
| Uitlezen ↔ | CAPABILITY_OPTIONS | `frontend/tabs/sources.js:120` |
| Vermogensgrens instellen ↔ | CAPABILITY_OPTIONS | `frontend/tabs/sources.js:122` |
| Aansturing ↔ | SECTIONS | `frontend/tabs/sources.js:504` |
| Bron | SECTIONS | `frontend/tabs/sources.js:485` |
| Notities ↔ | SECTIONS | `frontend/tabs/sources.js:508` |
| Wat er gemeten wordt | SECTIONS | `frontend/tabs/sources.js:487` |
| % — procent | UNIT_OPTIONS | `frontend/tabs/sources.js:115` |
| A — ampère | UNIT_OPTIONS | `frontend/tabs/sources.js:110` |
| Geen eenheid | UNIT_OPTIONS | `frontend/tabs/sources.js:116` |
| W — watt | UNIT_OPTIONS | `frontend/tabs/sources.js:108` |
| Wh — wattuur | UNIT_OPTIONS | `frontend/tabs/sources.js:111` |
| ct/kWh — cent per kilowattuur | UNIT_OPTIONS | `frontend/tabs/sources.js:114` |
| kW — kilowatt | UNIT_OPTIONS | `frontend/tabs/sources.js:109` |
| kWh — kilowattuur | UNIT_OPTIONS | `frontend/tabs/sources.js:112` |
| €/kWh — euro per kilowattuur | UNIT_OPTIONS | `frontend/tabs/sources.js:113` |
| Naam van het attribuut ↔ | attribute_name | `frontend/tabs/sources.js:88` |
| Wat kan deze bron? | capabilities | `frontend/tabs/sources.js:92` |
| Aansturing uitsluiten | control_forbidden | `frontend/tabs/sources.js:93` |
| Reden ↔ | control_forbidden_reason | `frontend/tabs/sources.js:94` |
| Aansturing uitgesloten — {...} ⚠ samengesteld | create | `frontend/tabs/sources.js:690` |
| Annuleren ↔ | create | `frontend/tabs/sources.js:602` |
| Annuleren ↔ | create | `frontend/tabs/sources.js:790` |
| Bekijken | create | `frontend/tabs/sources.js:638` |
| Bewerken ↔ | create | `frontend/tabs/sources.js:617` |
| Bewerken ↔ | create | `frontend/tabs/sources.js:638` |
| Bezig met opslaan… ↔ | create | `frontend/tabs/sources.js:817` |
| Bezig met verwijderen… ↔ | create | `frontend/tabs/sources.js:888` |
| Bron toevoegen | create | `frontend/tabs/sources.js:521` |
| Compleet. ↔ | create | `frontend/tabs/sources.js:695` |
| De configuratie is intussen ergens anders gewijzigd. Er is niets verwijderd; de lijst is opnieuw geladen. ↔ | create | `frontend/tabs/sources.js:903` |
| De configuratie is intussen ergens anders gewijzigd. Je wijzigingen zijn niet opgeslagen; de lijst is opnieuw geladen. ↔ | create | `frontend/tabs/sources.js:844` |
| De energiebron '{...}' is bijgewerkt. ⚠ samengesteld ↔ | create | `frontend/tabs/sources.js:832` |
| De energiebron '{...}' is toegevoegd. ⚠ samengesteld ↔ | create | `frontend/tabs/sources.js:833` |
| De energiebron '{...}' is verwijderd. ⚠ samengesteld ↔ | create | `frontend/tabs/sources.js:896` |
| Energiebron | create | `frontend/tabs/sources.js:560` |
| Energiebron bewerken | create | `frontend/tabs/sources.js:711` |
| Energiebron toevoegen | create | `frontend/tabs/sources.js:711` |
| Energiebron verwijderen | create | `frontend/tabs/sources.js:919` |
| Energiebronnen ↔ | create | `frontend/tabs/sources.js:518` |
| Intern geldt voor een thuisbatterij: positief is laden — de woning verbruikt — en negatief is ontladen. Controleer wat deze sensor rapporteert en gebruik zo nodig "teken omdraaien". | create | `frontend/tabs/sources.js:745` |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Verwerp je ze, dan zijn ze weg. ↔ | create | `frontend/tabs/sources.js:953` |
| Naamloze bron | create | `frontend/tabs/sources.js:634` |
| Nog geen energiebronnen. Koppel je slimme meter, omvormer, prijsbron of thuisbatterij om DomotiApp Energy iets te laten meten. | create | `frontend/tabs/sources.js:542` |
| Nog niet compleet: {...} ⚠ samengesteld ↔ | create | `frontend/tabs/sources.js:683` |
| Onbekend brontype '{...}'. Deze bron wordt niet gebruikt. ⚠ samengesteld | create | `frontend/tabs/sources.js:668` |
| Opslaan ↔ | create | `frontend/tabs/sources.js:601` |
| Sluiten ↔ | create | `frontend/tabs/sources.js:790` |
| Terug naar het formulier ↔ | create | `frontend/tabs/sources.js:956` |
| Uitgeschakeld — wordt niet meegerekend. | create | `frontend/tabs/sources.js:675` |
| Verwerpen ↔ | create | `frontend/tabs/sources.js:955` |
| Verwijderen ↔ | create | `frontend/tabs/sources.js:618` |
| Weet je zeker dat je '{...}' wilt verwijderen? De metingen van deze bron tellen daarna nergens meer mee. ⚠ samengesteld | create | `frontend/tabs/sources.js:921` |
| Wijzigingen verwerpen? ↔ | create | `frontend/tabs/sources.js:951` |
| zonder naam ↔ | create | `frontend/tabs/sources.js:827` |
| {...} · {...} ⚠ samengesteld | create | `frontend/tabs/sources.js:652` |
| Actuele energieprijs ↔ | current_price | `frontend/tabs/sources.js:53` |
| Ingeschakeld ↔ | enabled | `frontend/tabs/sources.js:80` |
| Entiteit ↔ | entity_id | `frontend/tabs/sources.js:81` |
| Entiteit voor teruglevering ↔ | export_entity_id | `frontend/tabs/sources.js:83` |
| Actuele terugleververgoeding | feed_in_price | `frontend/tabs/sources.js:54` |
| Aansturing uitgesloten voor deze installatie ↔ | fields | `frontend/tabs/sources.js:415` |
| Alleen registreren: DomotiApp Energy stuurt in deze versie niets aan. Niets aanvinken betekent "niet opgegeven", niet "kan niets". | fields | `frontend/tabs/sources.js:409` |
| De status van de entiteit | fields | `frontend/tabs/sources.js:291` |
| Een afspraak met de klant, los van wat deze bron zou kunnen. | fields | `frontend/tabs/sources.js:416` |
| Een attribuut van de entiteit | fields | `frontend/tabs/sources.js:292` |
| Eén waarde met een plus- en minteken | fields | `frontend/tabs/sources.js:234` |
| Gescheiden afname en teruglevering | fields | `frontend/tabs/sources.js:238` |
| Hoe meet deze meter? ↔ | fields | `frontend/tabs/sources.js:226` |
| Waarde uitlezen uit ↔ | fields | `frontend/tabs/sources.js:286` |
| Wat kan deze bron behalve uitlezen? | fields | `frontend/tabs/sources.js:407` |
| Zonder deze keuze wordt de netmeter niet gebruikt. | fields | `frontend/tabs/sources.js:227` |
| Algemeen verbruik | general_consumption | `frontend/tabs/sources.js:58` |
| Netmeter | grid_meter | `frontend/tabs/sources.js:51` |
| Thuisbatterij ↔ | home_battery | `frontend/tabs/sources.js:57` |
| Afname van het net | if | `frontend/tabs/sources.js:256` |
| De all-in prijs die de klant betaalt | if | `frontend/tabs/sources.js:198` |
| De kale marktprijs, exclusief belasting en opslag | if | `frontend/tabs/sources.js:204` |
| De kale marktprijs, vóór inhouding van de leverancier | if | `frontend/tabs/sources.js:203` |
| De vergoeding die de klant werkelijk krijgt | if | `frontend/tabs/sources.js:197` |
| Een positieve waarde betekent | if | `frontend/tabs/sources.js:251` |
| Eenheid ↔ | if | `frontend/tabs/sources.js:310` |
| Entiteit ↔ | if | `frontend/tabs/sources.js:167` |
| Entiteit ↔ | if | `frontend/tabs/sources.js:248` |
| Entiteit voor afname ↔ | if | `frontend/tabs/sources.js:267` |
| Entiteit voor teruglevering ↔ | if | `frontend/tabs/sources.js:272` |
| Kies expliciet. Zonder deze keuze wordt de prijs niet gebruikt, omdat een kale marktprijs en een all-in prijs sterk verschillen. | if | `frontend/tabs/sources.js:188` |
| Kies expliciet. Zonder deze keuze wordt de vergoeding niet gebruikt. Een kale marktprijs wordt omgerekend met de inhouding die je bij Woning invult; er komt geen energiebelasting of btw bij. | if | `frontend/tabs/sources.js:185` |
| Let op de tekenconventie: positief betekent hier laden — de woning verbruikt — en negatief ontladen. Meldt deze sensor het andersom, zet deze schakelaar dan aan. | if | `frontend/tabs/sources.js:387` |
| Meestal niet nodig: gebruik hierboven "een positieve waarde betekent". | if | `frontend/tabs/sources.js:393` |
| Naam van het attribuut ↔ | if | `frontend/tabs/sources.js:302` |
| Noteer waarom, zodat dit later terug te vinden is. ↔ | if | `frontend/tabs/sources.js:427` |
| Notities ↔ | if | `frontend/tabs/sources.js:214` |
| Reden ↔ | if | `frontend/tabs/sources.js:424` |
| Schaalfactor ↔ | if | `frontend/tabs/sources.js:318` |
| Teken omdraaien ↔ | if | `frontend/tabs/sources.js:324` |
| Teruglevering aan het net | if | `frontend/tabs/sources.js:257` |
| Vermenigvuldiger vóór de eenheidsconversie. Standaard 1. | if | `frontend/tabs/sources.js:319` |
| Wat levert deze bron? ↔ | if | `frontend/tabs/sources.js:177` |
| Zet aan wanneer deze sensor het tegenovergestelde teken rapporteert. | if | `frontend/tabs/sources.js:395` |
| Entiteit voor afname ↔ | import_entity_id | `frontend/tabs/sources.js:82` |
| Teken omdraaien ↔ | invert_value | `frontend/tabs/sources.js:91` |
| Energiebronnen ↔ | label | `frontend/tabs/sources.js:513` |
| Hoe meet deze meter? ↔ | meter_mode | `frontend/tabs/sources.js:84` |
| Naam ↔ | name | `frontend/tabs/sources.js:78` |
| Notities ↔ | notes | `frontend/tabs/sources.js:95` |
| De entiteit die de actuele zonneproductie meldt, niet de dagopbrengst. | perType | `frontend/tabs/sources.js:342` |
| De entiteit die het laad- of ontlaadvermogen meldt, niet de laadtoestand. | perType | `frontend/tabs/sources.js:353` |
| De entiteit die het totale huishoudelijke verbruik meldt. | perType | `frontend/tabs/sources.js:354` |
| De entiteit met de prijs van dit moment. Hieronder geef je aan of dat de kale marktprijs of de all-in prijs is. | perType | `frontend/tabs/sources.js:344` |
| De entiteit met de prijzen van de komende uren. | perType | `frontend/tabs/sources.js:350` |
| De entiteit met de terugleververgoeding van dit moment. Gebruik dit alleen bij een dynamisch teruglevercontract; bij een vast bedrag vul je dat in bij Woning. | perType | `frontend/tabs/sources.js:347` |
| De entiteit met de verwachte opbrengst. | perType | `frontend/tabs/sources.js:351` |
| De entiteit waar deze bron uit gelezen wordt. | perType | `frontend/tabs/sources.js:356` |
| Voor een prijs: EUR/kWh of ct/kWh. ↔ | perType | `frontend/tabs/sources.js:362` |
| Voor een prijs: EUR/kWh of ct/kWh. ↔ | perType | `frontend/tabs/sources.js:363` |
| Voor een vermogen: W of kW. ↔ | perType | `frontend/tabs/sources.js:364` |
| Voor een vermogen: W of kW. ↔ | perType | `frontend/tabs/sources.js:365` |
| Voor een vermogen: W of kW. ↔ | perType | `frontend/tabs/sources.js:366` |
| Voor een verwachte opbrengst meestal Wh of kWh. | perType | `frontend/tabs/sources.js:367` |
| Wat betekent een positieve waarde? | positive_means | `frontend/tabs/sources.js:85` |
| Wat levert deze bron? ↔ | price_basis | `frontend/tabs/sources.js:86` |
| Prijsverwachting | price_forecast | `frontend/tabs/sources.js:55` |
| De eenheid waarin deze entiteit meet. | return | `frontend/tabs/sources.js:370` |
| Zoals jij hem vaststelt: de eenheid van de entiteit zelf wordt nooit gebruikt om te converteren. | return | `frontend/tabs/sources.js:371` |
| Schaalfactor ↔ | scale_factor | `frontend/tabs/sources.js:90` |
| Een uitgeschakelde bron wordt nergens in meegerekend. | schema | `frontend/tabs/sources.js:157` |
| Ingeschakeld ↔ | schema | `frontend/tabs/sources.js:156` |
| Naam ↔ | schema | `frontend/tabs/sources.js:148` |
| Soort bron ↔ | schema | `frontend/tabs/sources.js:151` |
| Zonnepanelen | solar | `frontend/tabs/sources.js:52` |
| Zonverwachting | solar_forecast | `frontend/tabs/sources.js:56` |
| Soort bron ↔ | type | `frontend/tabs/sources.js:79` |
| Eenheid ↔ | unit | `frontend/tabs/sources.js:89` |
| Waarde uitlezen uit ↔ | value_source | `frontend/tabs/sources.js:87` |

## 9. Woning — velden en hulpteksten

*Installateursgebied.* — 68 teksten.

| Tekst | Voorwaarde | Waar |
|---|---|---|
| Besparen | ADVICE_SCHEMA | `frontend/tabs/home.js:386` |
| Comfort | ADVICE_SCHEMA | `frontend/tabs/home.js:384` |
| Gebalanceerd | ADVICE_SCHEMA | `frontend/tabs/home.js:385` |
| Maximaal zelf verbruiken | ADVICE_SCHEMA | `frontend/tabs/home.js:387` |
| Minimaal zonneoverschot | ADVICE_SCHEMA | `frontend/tabs/home.js:373` |
| Standaardstrategie | ADVICE_SCHEMA | `frontend/tabs/home.js:379` |
| Vanaf dit overschot adviseert DomotiApp Energy een apparaat. | ADVICE_SCHEMA | `frontend/tabs/home.js:374` |
| 1 fase | CONNECTION_SCHEMA | `frontend/tabs/home.js:72` |
| 3 fasen | CONNECTION_SCHEMA | `frontend/tabs/home.js:73` |
| Aantal fasen | CONNECTION_SCHEMA | `frontend/tabs/home.js:67` |
| Het vermogen waarboven DomotiApp Energy waarschuwt. | CONNECTION_SCHEMA | `frontend/tabs/home.js:87` |
| Hoofdzekering per fase | CONNECTION_SCHEMA | `frontend/tabs/home.js:80` |
| In ampère, zoals op de zekering staat. | CONNECTION_SCHEMA | `frontend/tabs/home.js:81` |
| Maximaal netvermogen | CONNECTION_SCHEMA | `frontend/tabs/home.js:86` |
| Naam van de woning ↔ | CONNECTION_SCHEMA | `frontend/tabs/home.js:64` |
| Percentage van het maximale netvermogen. | CONNECTION_SCHEMA | `frontend/tabs/home.js:93` |
| Waarschuwen vanaf | CONNECTION_SCHEMA | `frontend/tabs/home.js:92` |
| Btw | CONTRACT_SCHEMA | `frontend/tabs/home.js:299` |
| Contractsoort | CONTRACT_SCHEMA | `frontend/tabs/home.js:257` |
| De salderingsregeling stopt landelijk op 1 januari 2027. Laat leeg als deze woning niet saldeert; de omslag gaat daarna vanzelf. | CONTRACT_SCHEMA | `frontend/tabs/home.js:345` |
| Dynamisch tarief | CONTRACT_SCHEMA | `frontend/tabs/home.js:263` |
| Een bedrag per kWh, exclusief btw — géén vast maandbedrag. Reken een maandbedrag niet om: alleen de opslag per kWh hoort hier. | CONTRACT_SCHEMA | `frontend/tabs/home.js:291` |
| Een bedrag per kWh, exclusief btw. Nodig zodra een prijsbron de kale marktprijs levert; die wordt hiermee naar een all-in prijs omgerekend. | CONTRACT_SCHEMA | `frontend/tabs/home.js:280` |
| Een bedrag per teruggeleverde kWh — géén vast maandbedrag. Reken een maandstaffel om. Vul 0 in als deze aansluiting geen terugleverkosten betaalt; laat het leeg als je het niet weet, dan toont de coach geen geschatte besparing in plaats van een bedrag dat op een aanname rust. | CONTRACT_SCHEMA | `frontend/tabs/home.js:335` |
| Energiebelasting | CONTRACT_SCHEMA | `frontend/tabs/home.js:278` |
| Het all-in bedrag per kWh, inclusief energiebelasting en btw — dus wat de klant werkelijk betaalt. | CONTRACT_SCHEMA | `frontend/tabs/home.js:272` |
| Het btw-percentage over de leveringsprijs. In Nederland 21%. | CONTRACT_SCHEMA | `frontend/tabs/home.js:300` |
| Het vaste bedrag dat de klant per teruggeleverde kWh daadwerkelijk vergoed krijgt. Geen marktprijs en geen percentage: dit veld wordt niet omgerekend. | CONTRACT_SCHEMA | `frontend/tabs/home.js:309` |
| Hoge prijsgrens (all-in) | CONTRACT_SCHEMA | `frontend/tabs/home.js:362` |
| Inhouding leverancier op teruglevering | CONTRACT_SCHEMA | `frontend/tabs/home.js:316` |
| Lage prijsgrens (all-in) | CONTRACT_SCHEMA | `frontend/tabs/home.js:351` |
| Opslag leverancier | CONTRACT_SCHEMA | `frontend/tabs/home.js:286` |
| Saldering geldt tot | CONTRACT_SCHEMA | `frontend/tabs/home.js:343` |
| Terugleverkosten | CONTRACT_SCHEMA | `frontend/tabs/home.js:328` |
| Terugleververgoeding (all-in) | CONTRACT_SCHEMA | `frontend/tabs/home.js:305` |
| Vast leveringstarief (all-in) | CONTRACT_SCHEMA | `frontend/tabs/home.js:270` |
| Vast tarief | CONTRACT_SCHEMA | `frontend/tabs/home.js:262` |
| Vergelijk met de all-in prijs, niet met de kale marktprijs van je prijsbron. ↔ | CONTRACT_SCHEMA | `frontend/tabs/home.js:356` |
| Vergelijk met de all-in prijs, niet met de kale marktprijs van je prijsbron. ↔ | CONTRACT_SCHEMA | `frontend/tabs/home.js:364` |
| Wat de leverancier per teruggeleverde kWh inhoudt op de marktprijs. Alleen nodig als je terugleverprijsbron de kale marktprijs levert. Vul 0 in als er niets wordt ingehouden. | CONTRACT_SCHEMA | `frontend/tabs/home.js:320` |
| Adviesinstellingen | create | `frontend/tabs/home.js:451` |
| Alleen adviseren ↔ | create | `frontend/tabs/home.js:571` |
| Automatisch aansturen ↔ | create | `frontend/tabs/home.js:573` |
| Bedieningsniveau ↔ | create | `frontend/tabs/home.js:452` |
| Bedieningsniveau ↔ | create | `frontend/tabs/home.js:566` |
| Bezig met opslaan… ↔ | create | `frontend/tabs/home.js:871` |
| Contract en prijzen | create | `frontend/tabs/home.js:450` |
| De bron levert de kale marktprijs; de inhouding hieronder wordt daarvan afgetrokken. Er komt geen energiebelasting of btw bij — dat geldt alleen voor stroom die je afneemt. | create | `frontend/tabs/home.js:751` |
| De bron levert de vergoeding zelf, dus de inhouding wordt niet gebruikt. | create | `frontend/tabs/home.js:754` |
| De configuratie is intussen ergens anders gewijzigd. Je wijzigingen zijn niet opgeslagen; het formulier is opnieuw geladen met de actuele gegevens. ↔ | create | `frontend/tabs/home.js:892` |
| De prijsbron "{...}" levert de all-in prijs, dus die wordt ongewijzigd gebruikt. Energiebelasting, opslag leverancier en btw zijn daarom uitgeschakeld: ze rekenen alleen een kale marktprijs om. Zet de prijsbron op "kale marktprijs" als je ze wél wilt gebruiken, of verwijder de bron om alles zelf in te vullen. ⚠ samengesteld | create | `frontend/tabs/home.js:718` |
| De terugleverprijsbron "{...}" bepaalt de vergoeding, dus het vaste bedrag hierboven is uitgeschakeld en blijft bewaard. ⚠ samengesteld | create | `frontend/tabs/home.js:747` |
| De woninggegevens zijn opgeslagen. | create | `frontend/tabs/home.js:883` |
| Deze gegevens horen bij het andere contracttype en worden nu niet gebruikt, maar blijven bewaard: {...}. ⚠ samengesteld | create | `frontend/tabs/home.js:709` |
| DomotiApp Energy meet, rekent en adviseert; het stuurt in deze versie geen enkel apparaat aan. De andere bedieningsniveaus staan hier al wel, maar zijn nog niet beschikbaar. | create | `frontend/tabs/home.js:585` |
| DomotiApp Energy rekent overal met de all-in prijs: (marktprijs + opslag + energiebelasting) × (1 + btw). Een prijsbron die de kale marktprijs levert wordt daarmee omgerekend; een bron die al all-in is, wordt ongewijzigd gebruikt. Bij de bron zelf geef je aan welke van de twee het is. | create | `frontend/tabs/home.js:537` |
| Het ingevulde netvermogen ligt boven het theoretische maximum van {...} W ({...} × 230 V × {...} A). Controleer de hoofdzekering. ⚠ samengesteld | create | `frontend/tabs/home.js:774` |
| Hier blijven ↔ | create | `frontend/tabs/home.js:602` |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Sla ze op, of verwerp ze om verder te gaan. ↔ | create | `frontend/tabs/home.js:961` |
| Opslaan ↔ | create | `frontend/tabs/home.js:593` |
| Theoretisch maximum: {...} W ({...} × 230 V × {...} A). ⚠ samengesteld | create | `frontend/tabs/home.js:777` |
| Verwerpen en verdergaan ↔ | create | `frontend/tabs/home.js:601` |
| Vragen om goedkeuring ↔ | create | `frontend/tabs/home.js:572` |
| Wijzigingen verwerpen ↔ | create | `frontend/tabs/home.js:594` |
| Woning en aansluiting | create | `frontend/tabs/home.js:449` |
| Zolang de salderingsregeling geldt — tot {...} — telt de terugleververgoeding niet mee in de berekening: een teruggeleverde kWh is dan evenveel waard als een afgenomen kWh. Vul hem nu al in, dan klopt de besparing zodra de saldering stopt. De terugleverkosten tellen wél mee, ook vandaag. ⚠ samengesteld | create | `frontend/tabs/home.js:734` |
| Installatie | label | `frontend/tabs/installation.js:53` |
| Woning | label | `frontend/tabs/home.js:443` |

## 10. Mijn voorkeuren

*Volledig bewonersgebied.* — 28 teksten.

| Tekst | Voorwaarde | Waar |
|---|---|---|
| Aantal adviezen | DISPLAY_SCHEMA | `frontend/tabs/preferences.js:98` |
| Geschatte besparing tonen | DISPLAY_SCHEMA | `frontend/tabs/preferences.js:109` |
| Hoeveel adviezen er hoogstens tegelijk getoond worden. | DISPLAY_SCHEMA | `frontend/tabs/preferences.js:99` |
| Technische onderbouwing tonen | DISPLAY_SCHEMA | `frontend/tabs/preferences.js:104` |
| Stille uren tot | QUIET_SCHEMA | `frontend/tabs/preferences.js:43` |
| Stille uren van | QUIET_SCHEMA | `frontend/tabs/preferences.js:33` |
| Toch adviseren tijdens de stille uren | QUIET_SCHEMA | `frontend/tabs/preferences.js:48` |
| Tussen deze tijden krijgen lawaaiige apparaten geen advies. Een venster over middernacht is het normale geval: 22:00 tot 07:00. | QUIET_SCHEMA | `frontend/tabs/preferences.js:35` |
| Zet aan wanneer de bewoner er geen last van heeft. | QUIET_SCHEMA | `frontend/tabs/preferences.js:49` |
| Advies met een berekende besparing bóven nul maar onder dit bedrag wordt niet getoond. Advies zonder berekenbare besparing — veiligheid, piek, ontbrekende gegevens — blijft altijd staan, net als advies dat op nul uitkomt zolang de saldering loopt. | THRESHOLD_SCHEMA | `frontend/tabs/preferences.js:85` |
| Minimale besparing | THRESHOLD_SCHEMA | `frontend/tabs/preferences.js:81` |
| Adviseer een apparaat wanneer er genoeg eigen opwek is. | WEIGHING_SCHEMA | `frontend/tabs/preferences.js:58` |
| Alleen van toepassing bij een dynamisch contract; bij een vast tarief wordt er nooit op prijs geadviseerd. | WEIGHING_SCHEMA | `frontend/tabs/preferences.js:65` |
| Op prijs adviseren | WEIGHING_SCHEMA | `frontend/tabs/preferences.js:63` |
| Zonneoverschot benutten | WEIGHING_SCHEMA | `frontend/tabs/preferences.js:57` |
| Bezig met opslaan… ↔ | create | `frontend/tabs/preferences.js:318` |
| De configuratie is intussen ergens anders gewijzigd. Je wijzigingen zijn niet opgeslagen; het formulier is opnieuw geladen met de actuele gegevens. ↔ | create | `frontend/tabs/preferences.js:339` |
| De voorkeuren zijn opgeslagen. | create | `frontend/tabs/preferences.js:333` |
| Hier blijven ↔ | create | `frontend/tabs/preferences.js:218` |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Sla ze op, of verwerp ze om verder te gaan. ↔ | create | `frontend/tabs/preferences.js:397` |
| Opslaan ↔ | create | `frontend/tabs/preferences.js:212` |
| Stille uren | create | `frontend/tabs/preferences.js:170` |
| Verwerpen en verdergaan ↔ | create | `frontend/tabs/preferences.js:217` |
| Wanneer een advies de moeite waard is | create | `frontend/tabs/preferences.js:172` |
| Wat je te zien krijgt | create | `frontend/tabs/preferences.js:173` |
| Wat weegt mee | create | `frontend/tabs/preferences.js:171` |
| Wijzigingen verwerpen ↔ | create | `frontend/tabs/preferences.js:213` |
| Mijn voorkeuren | label | `frontend/tabs/preferences.js:164` |

## 11. Logboek — het scherm

| Tekst | Voorwaarde | Waar |
|---|---|---|
| Advies herberekend | advice_recalculated | `frontend/tabs/logbook.js:37` |
| Configuratie gewijzigd | config_changed | `frontend/tabs/logbook.js:34` |
| Bezig met wissen… | create | `frontend/tabs/logbook.js:157` |
| Het logboek is gewist. | create | `frontend/tabs/logbook.js:161` |
| Het logboek is leeg. Hier komt te staan wat DomotiApp Energy signaleert: configuratiewijzigingen, bronnen die wegvallen en piekmomenten. | create | `frontend/tabs/logbook.js:81` |
| Logboek ↔ | create | `frontend/tabs/logbook.js:65` |
| Logboek wissen ↔ | create | `frontend/tabs/logbook.js:68` |
| Logboek wissen ↔ | create | `frontend/tabs/logbook.js:173` |
| Weet je zeker dat je het logboek wilt wissen? De gebeurtenissen zijn daarna weg. De configuratie zelf verandert niet. | create | `frontend/tabs/logbook.js:175` |
| Wissen | create | `frontend/tabs/logbook.js:177` |
| {...} · {...} keer samengevoegd ⚠ samengesteld | create | `frontend/tabs/logbook.js:124` |
| Apparaat toegevoegd ↔ | device_added | `frontend/tabs/logbook.js:35` |
| Apparaat verwijderd ↔ | device_removed | `frontend/tabs/logbook.js:36` |
| Fout ↔ | error | `frontend/tabs/logbook.js:55` |
| Info | info | `frontend/tabs/logbook.js:52` |
| Configuratieprobleem | invalid_configuration | `frontend/tabs/logbook.js:42` |
| Ongeldige meting ↔ | invalid_measurement | `frontend/tabs/logbook.js:39` |
| Logboek ↔ | label | `frontend/tabs/logbook.js:60` |
| Piekrisico gesignaleerd | peak_risk_detected | `frontend/tabs/logbook.js:40` |
| Zonneoverschot gesignaleerd | solar_surplus_detected | `frontend/tabs/logbook.js:41` |
| Bron niet beschikbaar ↔ | source_unavailable | `frontend/tabs/logbook.js:38` |
| Gelukt | success | `frontend/tabs/logbook.js:53` |
| Waarschuwing ↔ | warning | `frontend/tabs/logbook.js:54` |

## 12. Gedeelde onderdelen

*Dialogen, formulierhulp, rolmeldingen.* — 22 teksten.

| Tekst | Voorwaarde | Waar |
|---|---|---|
| Deze gegevens worden beheerd door DomotiTech. | MANAGED_NOTICE | `frontend/core/roles.js:113` |
| [hidden], .is-hidden { display: none !important; } :host { --domotiapp-font-heading: var(--ha-font-family-heading, inherit); --domotiapp-space-row: 20px; --domotiapp-space-section: 40px; display: block; padding: 32px 16px; padding-bottom: calc(32px + env(safe-area-inset-bottom)); box-sizing: border-box; color: var(--primary-text-color); touch-action: manipulation; -webkit-tap-highlight-color: transparent; } .layout { max-width: 1400px; margin: 0 auto; } .label, .tab-button, .button, .stat-label { font-size: 0.7rem; font-weight: 500; letter-spacing: 0.12em; text-transform: uppercase; color: var(--secondary-text-color); } .tabs { display: flex; flex-wrap: wrap; gap: 4px 24px; max-width: 760px; margin: 0 auto var(--domotiapp-space-section); border-bottom: 1px solid var(--divider-color); } .tab-button { display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 0 2px; border: none; border-bottom: 2px solid transparent; margin-bottom: -1px; background: none; cursor: pointer; } .tab-button ha-icon { --mdc-icon-size: 18px; } .tab-button[aria-selected='true'] { color: var(--primary-color); border-bottom-color: var(--primary-color); } .tab-button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 4px; } .tab-content { display: grid; grid-template-columns: minmax(0, 760px); justify-content: center; gap: var(--domotiapp-space-section); } .card-title { margin: 0; padding: 32px 32px 0; font-family: var(--domotiapp-font-heading); font-size: 1.5rem; font-weight: 400; letter-spacing: 0.01em; } .card-body { padding: 24px 32px 32px; } .subheading { margin: var(--domotiapp-space-section) 0 12px; font-family: var(--domotiapp-font-heading); font-size: 1.1rem; font-weight: 400; color: var(--primary-color); } .display-row { display: flex; flex-wrap: wrap; gap: 40px; margin-bottom: var(--domotiapp-space-section); } .display-metric { display: flex; flex-direction: column; gap: 8px; min-width: 120px; } .display-figure { display: flex; align-items: baseline; gap: 8px; } .display-value { font-size: 3rem; font-weight: 300; line-height: 1; font-variant-numeric: lining-nums tabular-nums; } .display-suffix, .display-empty { font-size: 0.85rem; color: var(--secondary-text-color); } .stat-row { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 12px; padding: var(--domotiapp-space-row) 0; border-top: 1px solid var(--divider-color); } .stat-value-wrap { display: flex; flex-direction: column; align-items: flex-end; text-align: right; } .stat-value { font-size: 1.05rem; font-variant-numeric: lining-nums tabular-nums; overflow-wrap: anywhere; } .stat-value.is-empty { color: var(--secondary-text-color); font-style: italic; } .stat-hint { margin-top: 4px; font-size: 0.8rem; color: var(--secondary-text-color); } .notice { display: flex; align-items: flex-start; gap: 12px; margin-top: var(--domotiapp-space-row); padding-top: var(--domotiapp-space-row); border-top: 1px solid var(--divider-color); font-size: 0.9rem; color: var(--secondary-text-color); } .notice[data-tone='warning'] { color: var(--warning-color); } .notice ha-icon { flex: none; --mdc-icon-size: 20px; } .advice-title { margin: 0 0 8px; font-family: var(--domotiapp-font-heading); font-size: 1.25rem; font-weight: 400; } .advice-message { margin: 0 0 var(--domotiapp-space-row); max-width: 58ch; line-height: 1.6; color: var(--secondary-text-color); } .advice-list { display: flex; flex-direction: column; } .advice-item { padding: var(--domotiapp-space-row) 0; border-top: 1px solid var(--divider-color); } .advice-item-title { margin: 6px 0 4px; font-size: 1rem; } .advice-item-message { margin: 0; max-width: 58ch; line-height: 1.6; color: var(--secondary-text-color); } ha-form { display: block; } .actions { display: flex; flex-wrap: wrap; gap: 16px; margin-top: var(--domotiapp-space-section); padding-top: var(--domotiapp-space-row); border-top: 1px solid var(--divider-color); } .button { min-height: 44px; padding: 0 20px; border: 1px solid var(--divider-color); border-radius: 4px; background: none; color: var(--primary-text-color); cursor: pointer; } .button-primary { border-color: var(--primary-color); background: var(--primary-color); color: var(--text-primary-color); } .button:disabled { opacity: 0.5; cursor: default; } .button:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; } .row-list { display: flex; flex-direction: column; } .row-item { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 16px; padding: var(--domotiapp-space-row) 0; border-top: 1px solid var(--divider-color); } .row-main { flex: 1 1 220px; min-width: 0; } .row-name { margin: 0 0 4px; font-size: 1.05rem; overflow-wrap: anywhere; } .row-meta { margin: 0; font-size: 0.85rem; color: var(--secondary-text-color); } .row-status { display: inline-flex; align-items: center; gap: 6px; margin-top: 6px; font-size: 0.8rem; color: var(--secondary-text-color); } .row-status[data-tone='warning'] { color: var(--warning-color); } .row-status[data-tone='error'] { color: var(--error-color); } .row-status ha-icon { --mdc-icon-size: 16px; } .row-buttons { display: flex; flex-wrap: wrap; gap: 8px; } .empty-text { margin: var(--domotiapp-space-row) 0 0; max-width: 58ch; line-height: 1.6; color: var(--secondary-text-color); } .tab-actions .actions { margin-top: 0; padding-top: 0; border-top: none; } .section + .section { border-top: 1px solid var(--divider-color); } .section-toggle { display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; min-height: 44px; padding: 12px 0; border: none; background: none; color: var(--primary-text-color); text-align: left; cursor: pointer; } .section-toggle:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; } .section-title { font-size: 0.7rem; font-weight: 500; letter-spacing: 0.12em; text-transform: uppercase; color: var(--secondary-text-color); } .section-chevron { flex: none; --mdc-icon-size: 20px; color: var(--secondary-text-color); } .section-body { padding-bottom: var(--domotiapp-space-row); } .question-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: var(--domotiapp-space-row); } .plain-list { margin: 0; padding: 0; list-style: none; } .plain-item { padding: 12px 0; border-top: 1px solid var(--divider-color); } .dialog { position: fixed; inset: 0; z-index: 10; display: flex; align-items: center; justify-content: center; padding: 16px; padding-bottom: calc(16px + env(safe-area-inset-bottom)); box-sizing: border-box; } .dialog-scrim { position: absolute; inset: 0; background: var(--mdc-dialog-scrim-color, rgba(0, 0, 0, 0.5)); backdrop-filter: var(--ha-dialog-scrim-backdrop-filter, none); } .dialog-surface { position: relative; display: flex; flex-direction: column; width: 100%; max-width: 640px; max-height: 100%; border-radius: 8px; background: var(--card-background-color); color: var(--primary-text-color); box-shadow: var(--ha-card-box-shadow, none); overflow: hidden; } .dialog-surface:focus { outline: none; } .dialog-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 24px 24px 0; } .dialog-title { margin: 0; font-family: var(--domotiapp-font-heading); font-size: 1.35rem; font-weight: 400; } .dialog-close { flex: none; display: flex; align-items: center; justify-content: center; width: 44px; height: 44px; margin: -10px -10px 0 0; border: none; background: none; color: var(--secondary-text-color); cursor: pointer; } .dialog-close:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; } .dialog-body { padding: 16px 24px 0; overflow-y: auto; } .dialog-message { margin: 0 0 8px; max-width: 58ch; line-height: 1.6; } .dialog-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 12px; padding: 24px; } .button-danger { border-color: var(--error-color); color: var(--error-color); } .layout { container-type: inline-size; container-name: panel; } @container panel (max-width: 600px) { .tabs { gap: 0 16px; margin-bottom: var(--domotiapp-space-row); } .tab-content { gap: var(--domotiapp-space-row); } .card-title { padding: 20px 20px 0; font-size: 1.3rem; } .card-body { padding: 16px 20px 24px; } .display-row { gap: 24px; } .display-value { font-size: 2.4rem; } } @media (max-width: 600px) { :host { padding: 16px 12px; padding-bottom: calc(16px + env(safe-area-inset-bottom)); } .dialog { padding: 0; } .dialog-surface { max-width: none; height: 100%; border-radius: 0; padding-bottom: env(safe-area-inset-bottom); } } .banner { display: flex; align-items: center; gap: 8px; max-width: 760px; margin: 0 auto var(--domotiapp-space-row); font-size: 0.9rem; color: var(--secondary-text-color); } .banner[data-tone='error'] { color: var(--error-color); } | STYLES | `frontend/domotiapp-energy-panel.js:65` |
| DomotiApp Energy tabbladen | _buildDOM | `frontend/domotiapp-energy-panel.js:756` |
| Gegevens laden… | _update | `frontend/domotiapp-energy-panel.js:889` |
| button button-primary | button | `frontend/core/dom.js:258` |
| Annuleren ↔ | cancelButton | `frontend/core/dialog.js:199` |
| Sluiten ↔ | closeButton | `frontend/core/dialog.js:60` |
| Verwijderen ↔ | confirmButton | `frontend/core/dialog.js:197` |
| {...}: {...} ⚠ samengesteld ↔ | describeOrphanedErrors | `frontend/core/forms.js:124` |
| Nog niet berekend ↔ | displayMetric | `frontend/core/dom.js:123` |
| %c DOMOTIAPP ENERGY %c v{...} ⚠ samengesteld | if | `frontend/domotiapp-energy-panel.js:956` |
| DomotiApp Energy is niet geladen. Controleer de integratie in Instellingen. | if | `frontend/core/api.js:152` |
| Er is een onbekende fout opgetreden. ↔ | if | `frontend/core/api.js:146` |
| Er is een onbekende fout opgetreden. ↔ | if | `frontend/core/api.js:157` |
| Je hebt geen rechten voor deze actie. | if | `frontend/core/api.js:155` |
| background: transparent; color: inherit; | if | `frontend/domotiapp-energy-panel.js:958` |
| background: var(--primary-color); color: white; font-weight: bold; | if | `frontend/domotiapp-energy-panel.js:957` |
| {...} Dit veld wordt beheerd door DomotiTech; geef het aan hen door. ⚠ samengesteld | if | `frontend/core/roles.js:131` |
| Annuleren ↔ | onTap | `frontend/core/dialog.js:228` |
| Escape | onTap | `frontend/core/dialog.js:125` |
| Verwijderen ↔ | onTap | `frontend/core/dialog.js:227` |
| Niet beschikbaar ↔ | statRow | `frontend/core/dom.js:85` |

## 13. Validatiemeldingen

*Verschijnen naast een veld bij het opslaan. Vrijwel alleen de installateur ziet deze.* — 43 teksten.

| Tekst | Voorwaarde | Waar |
|---|---|---|
| Dit bedieningsniveau vraagt om aansturing, maar er is geen besturingsmogelijkheid aangevinkt. Controleer wat deze apparatuur werkelijk ondersteunt. | _validate_control | `validators.py:700` |
| Noteer waarom aansturing hier is uitgesloten, zodat de reden later terug te vinden is. | _validate_control | `validators.py:714` |
| Voor deze installatie is aansturing uitgesloten. Kies 'alleen monitoren' of 'alleen adviseren'. | _validate_control | `validators.py:687` |
| De terugleverprijsbron levert de kale marktprijs. Vul in wat de leverancier per teruggeleverde kWh inhoudt; zonder dat bedrag is de vergoeding niet te berekenen en wordt de bron niet gebruikt. Vul 0 in als de leverancier niets inhoudt. | _validate_feed_in_components | `validators.py:923` |
| Geef aan of een positieve waarde afname of teruglevering betekent. | _validate_grid_meter | `validators.py:589` |
| Kies hoe de netmeter meet: één ondertekende waarde of gescheiden afname en teruglevering. | _validate_grid_meter | `validators.py:568` |
| Koppel de entiteit die de afname meet. | _validate_grid_meter | `validators.py:599` |
| Koppel de entiteit die de teruglevering meet. | _validate_grid_meter | `validators.py:607` |
| Koppel een entiteit aan deze bron. ↔ | _validate_grid_meter | `validators.py:581` |
| Het ingevulde netvermogen ligt boven het theoretische maximum van {...} W ({...} x 230 V x {...} A). Controleer de hoofdzekering. ⚠ samengesteld | _validate_max_grid_power | `validators.py:382` |
| Het maximale netvermogen moet groter zijn dan 0 W. | _validate_max_grid_power | `validators.py:370` |
| De prijsbron levert de kale marktprijs. Vul de energiebelasting en de opslag van de leverancier per kWh in; zonder die twee is de all-in prijs niet te berekenen en wordt de prijs niet gebruikt. | _validate_price_components | `validators.py:887` |
| Geef aan wat deze bron levert: de kale marktprijs of de all-in prijs die de klant betaalt. Zonder die keuze wordt de prijs niet gebruikt. | _validate_price_source | `validators.py:548` |
| Geef aan wat deze bron levert: de kale marktprijs of de vergoeding die de klant werkelijk krijgt. Zonder die keuze wordt de terugleververgoeding niet gebruikt. | _validate_price_source | `validators.py:542` |
| De hoge prijsgrens moet boven de lage prijsgrens liggen. | _validate_price_thresholds | `validators.py:408` |
| De begin- en eindtijd van het gereed-venster mogen niet gelijk zijn. | _validate_time_window | `validators.py:764` |
| Gebruik een geldige tijd in de vorm uu:mm. ↔ | _validate_time_window | `validators.py:740` |
| Het apparaat past niet binnen het opgegeven gereed-venster. | _validate_time_window | `validators.py:775` |
| Deze bron levert een prijs, maar de eenheid staat op '{...}'. Kies EUR/kWh of ct/kWh. ⚠ samengesteld | _validate_unit_matches_type | `validators.py:446` |
| Deze bron meet vermogen, maar de eenheid staat op '{...}'. Kies W of kW. Let op: veel slimme-meterintegraties tonen vooral de meterstand in kWh; die is een totaal en geen vermogen, en levert een netbelasting die honderden keren te hoog is. ⚠ samengesteld | _validate_unit_matches_type | `validators.py:432` |
| De duur | validate_device_profile | `validators.py:651` |
| Het apparaattype '{...}' is niet bekend. Kies een geldig type. ⚠ samengesteld | validate_device_profile | `validators.py:621` |
| Het energieverbruik per cyclus | validate_device_profile | `validators.py:649` |
| Het nominale vermogen | validate_device_profile | `validators.py:645` |
| Kies een geldig bedieningsniveau. | validate_device_profile | `validators.py:640` |
| Kies een geldige prioriteit. | validate_device_profile | `validators.py:631` |
| {...} kan niet negatief zijn. ⚠ samengesteld | validate_device_profile | `validators.py:658` |
| De schaalfactor moet groter zijn dan 0. | validate_energy_source | `validators.py:486` |
| Het brontype '{...}' is niet bekend. Kies een geldig type. ⚠ samengesteld | validate_energy_source | `validators.py:464` |
| Kies een geldige eenheid. | validate_energy_source | `validators.py:475` |
| Koppel een entiteit aan deze bron. ↔ | validate_energy_source | `validators.py:513` |
| Vul de naam in van het attribuut dat uitgelezen moet worden. | validate_energy_source | `validators.py:498` |
| De energiebelasting kan niet negatief zijn. | validate_home_profile | `validators.py:340` |
| De hoofdzekering moet tussen {...} en {...} ampère liggen. ⚠ samengesteld | validate_home_profile | `validators.py:295` |
| De waarschuwingsgrens moet tussen {...} en {...} procent liggen. ⚠ samengesteld | validate_home_profile | `validators.py:311` |
| Het btw-percentage moet tussen {...} en {...} liggen. ⚠ samengesteld | validate_home_profile | `validators.py:330` |
| Het minimale zonneoverschot kan niet negatief zijn. | validate_home_profile | `validators.py:349` |
| Kies 1 of 3 fasen. | validate_home_profile | `validators.py:284` |
| Kies een vast of dynamisch contract. | validate_home_profile | `validators.py:321` |
| Begin en einde van de stille uren mogen niet gelijk zijn. | validate_preferences | `validators.py:840` |
| De minimale besparing kan niet negatief zijn. | validate_preferences | `validators.py:819` |
| Gebruik een geldige tijd in de vorm uu:mm. ↔ | validate_preferences | `validators.py:830` |
| Toon minimaal {...} en maximaal {...} adviezen. ⚠ samengesteld | validate_preferences | `validators.py:809` |

## 14. Wat Home Assistant zelf toont

*Config flow, entiteitsnamen en services. Deze staan wél in `translations/`.* — 20 teksten.

| Tekst | Voorwaarde | Waar |
|---|---|---|
| Actueel advies | entity > sensor > current_advice > name | `translations/nl.json` |
| Berekent het energieadvies direct opnieuw. Stuurt geen enkel apparaat aan. | services > recalculate > description | `translations/nl.json` |
| Bevestig dat je de energiebronnen en apparaten zelf instelt. | config > error > acknowledgement_required | `translations/nl.json` |
| Datakwaliteit ↔ | entity > sensor > data_quality > name | `translations/nl.json` |
| De naam van de woning is bijgewerkt. | config > abort > reconfigure_successful | `translations/nl.json` |
| DomotiApp Energy | config > step > user > title | `translations/nl.json` |
| DomotiApp Energy | config > step > reconfigure > title | `translations/nl.json` |
| DomotiApp Energy configureert geen apparaten automatisch. Na het toevoegen van de integratie kun je via het DomotiApp Energy-paneel zelf energiebronnen, apparaten en voorkeuren koppelen. | config > step > user > description | `translations/nl.json` |
| DomotiApp Energy is al ingesteld. Er is één instantie mogelijk. | config > abort > single_instance_allowed | `translations/nl.json` |
| Energiescore ↔ | entity > sensor > score > name | `translations/nl.json` |
| Ik begrijp dat alles handmatig wordt ingesteld | config > step > user > data > manual_setup_acknowledged | `translations/nl.json` |
| Logboek wissen ↔ | services > clear_log > name | `translations/nl.json` |
| Naam van de woning ↔ | config > step > user > data > home_name | `translations/nl.json` |
| Naam van de woning ↔ | config > step > reconfigure > data > home_name | `translations/nl.json` |
| Netvermogen ↔ | entity > sensor > grid_power > name | `translations/nl.json` |
| Opnieuw berekenen ↔ | services > recalculate > name | `translations/nl.json` |
| Piekrisico | entity > binary_sensor > peak_risk > name | `translations/nl.json` |
| Wijzig de naam van deze woning. De energieconfiguratie zelf blijft in het DomotiApp Energy-paneel staan. | config > step > reconfigure > description | `translations/nl.json` |
| Wist het interne logboek van DomotiApp Energy. Wijzigt geen configuratie. | services > clear_log > description | `translations/nl.json` |
| Zonneoverschot ↔ | entity > sensor > solar_surplus > name | `translations/nl.json` |

## 15. Samengestelde zinnen

Dit is het deel dat er het meest toe doet. Een zin die uit losse clausules wordt opgebouwd, leest niemand ooit als geheel — ook de schrijver niet. Zo kwam de tegel eraan die 's avonds beweerde dat de zon scheen.

**De regel:** elke bereikbare variant hoort uitgeschreven te zijn, óf de zin hoort gesplitst te worden in hele zinnen die door een situatie gekozen worden.

### 15.1 Met vertakking — hier bestaat de zin nergens als geheel

**`engine/advisor.py:_surplus_message` — Het zonneoverschot-advies. Vijf uitkomsten, plus vijf onder de eerste.**

- Er is momenteel zonneoverschot beschikbaar. Dit is een gunstig moment om <apparaat> te gebruiken.
- Er is momenteel zonneoverschot beschikbaar. Dit is een gunstig moment om <apparaat> te gebruiken. Het levert op dit moment niets extra op, maar het kost ook niets.
- Er is momenteel zonneoverschot beschikbaar. Dit is een gunstig moment om <apparaat> te gebruiken. Zolang de salderingsregeling geldt levert dit geen extra besparing op, maar het overschot zelf gebruiken blijft de meest efficiënte keuze.
- Er is momenteel zonneoverschot beschikbaar. Zelf verbruiken levert nu echter minder op dan terugleveren: <apparaat> nu gebruiken kost naar schatting <bedrag> ten opzichte van het overschot terugleveren. Wachten tot de terugleververgoeding lager ligt is voordeliger.
- Er is momenteel zonneoverschot beschikbaar. Dit is een gunstig moment om <apparaat> te gebruiken. <één van de vijf zinnen van _why_no_amount>

**`engine/providers.py:_why_advice` — Antwoord op “Waarom krijg ik dit advies?”**

- <adviestekst>
- <adviestekst> Gebaseerd op <meetwaarden>.

**`engine/providers.py:_missing_data` — Antwoord op “Welke gegevens ontbreken nog?”**

- Alle gegevens voor een betrouwbaar advies zijn ingevuld.
- Nog ontbrekend: <items>.
- Alle gegevens voor een betrouwbaar advies zijn ingevuld. Niet van toepassing op deze woning, en dus niet meegeteld: <items>.
- Nog ontbrekend: <items>. Niet van toepassing op deze woning, en dus niet meegeteld: <items>.
- … en elk van deze vier gevolgd door de batterijzin, wanneer het zonneoverschot overschat kan zijn.

**`engine/providers.py:_score_breakdown` — Antwoord op “Hoe is mijn energiescore berekend?”**

- De score op dit moment is <n>, opgebouwd uit: <componenten>.
- De score op dit moment is <n>, opgebouwd uit: <componenten>. Niet van toepassing op deze woning, en dus niet meegewogen: <componenten>.
- … of één van de zeven hele zinnen uit §35.9 wanneer er geen cijfer is.

**`tabs/coach.js:detailLine` — De regel onder elk aanvullend advies**

- <meetwaarde>: <waarde>
- <meetwaarde>: <waarde> · geschatte besparing € <bedrag>
- geschatte besparing € <bedrag>

Deze vier horen gesplitst te worden op dezelfde manier als de tegelteksten in §35.9: één hele zin per situatie.

### 15.2 Met alleen een waardeplaats — leesbaar als geheel

Hier wordt één waarde ingevuld en verandert de zin verder niet. Ze staan hier zodat je ze kunt herlezen met de waarde erin gedacht.

| Zin | Waar |
|---|---|
| Hoeveel dit oplevert is niet te berekenen zonder de energie per cyclus van {...} — vul die in bij Apparaten. | `engine/advisor.py:386` |
| € {...} | `engine/advisor.py:371` |
| {...}. De woning {...} {...}% van het ingestelde maximale netvermogen. | `engine/providers.py:287` |
| Ja. De all-in energieprijs is nu {...} en ligt onder de ingestelde lage prijsgrens. | `engine/providers.py:242` |
| Nu is geen gunstig moment: de all-in energieprijs is {...} en ligt boven de ingestelde hoge prijsgrens. | `engine/providers.py:247` |
| € {...} per kWh | `engine/providers.py:265` |
| {...} per kWh | `frontend/tabs/overview.js:284` |
| All-in, afgeleid van een marktprijs van {...}. | `frontend/tabs/overview.js:288` |
| {...} van de {...} onderdelen van de datakwaliteit is nog niet compleet. Het tabblad Energiecoach laat zien welke. | `frontend/tabs/overview.js:342` |
| {...}: {...} | `frontend/tabs/coach.js:202` |
| geschatte besparing € {...})} | `frontend/tabs/coach.js:213` |
| € {...})} | `frontend/tabs/coach.js:280` |
| Niet van toepassing op deze woning, en dus niet meegeteld: {...}. | `frontend/tabs/coach.js:320` |
| {...} recalculate after configuration change | `coordinator.py:270` |
| {...} safety recalculation | `coordinator.py:187` |
| De woning {...} {...}% van het ingestelde maximale netvermogen. Dat ligt op of boven de waarschuwingsgrens van {...}%. | `coordinator.py:348` |
| Er is {...} W zonneoverschot beschikbaar. | `coordinator.py:367` |
| Configuration was modified: expected revision {...}, current revision is {...} | `storage.py:65` |
| Cannot downgrade {...} from schema version {...}.{...} | `storage.py:94` |
| De energiebron '{...}' kon niet worden uitgelezen: de entiteit '{...}' bestaat niet of levert op dit moment geen waarde. (reden: {...}) | `storage.py:337` |
| De energiebron '{...}' leverde geen bruikbare meetwaarde. Controleer bij de entiteit '{...}' de gekozen waardebron, het attribuut en de eenheid. (reden: {...}) | `storage.py:344` |
| Er zijn {...} ingeschakelde bronnen van het type '{...}'. Deze waarden zijn niet op te tellen en er is niet te bepalen welke de juiste is, dus geen van beide wordt gebruikt. Schakel er één uit of verwijder er één. | `storage.py:242` |
| De energiebron '{...}' heeft een onbekend type ('{...}') en is uitgeschakeld. Kies een geldig type om de bron weer te gebruiken. | `storage.py:264` |
| Het apparaat '{...}' heeft een onbekend type ('{...}') en is uitgeschakeld. Kies een geldig type om het apparaat weer te gebruiken. | `storage.py:283` |
| Could not write {...} | `storage.py:592` |
| {...} bestaat niet. | `websocket_api.py:380` |
| De energiebron '{...}' is toegevoegd. | `websocket_api.py:633` |
| De energiebron '{...}' is bijgewerkt. | `websocket_api.py:671` |
| De energiebron '{...}' is verwijderd. | `websocket_api.py:707` |
| Het apparaat '{...}' is toegevoegd. | `websocket_api.py:749` |
| Het apparaat '{...}' is bijgewerkt. | `websocket_api.py:787` |
| Het apparaat '{...}' is verwijderd. | `websocket_api.py:823` |
| De instellingen van '{...}' zijn bijgewerkt. | `websocket_api.py:896` |
| Standaard voor dit type: {...}. Lawaaiige apparaten worden tijdens de stille uren niet geadviseerd. | `frontend/tabs/devices.js:475` |
| Standaard voor dit type: {...}. Alleen verplaatsbare apparaten krijgen een verplaatsingsadvies, en alleen die hebben een tijdvenster nodig. | `frontend/tabs/devices.js:483` |
| Onbekend apparaattype '{...}'. Dit apparaat wordt niet gebruikt. | `frontend/tabs/devices.js:916` |
| Nog niet compleet: {...} | `frontend/tabs/devices.js:931` |
| · Aansturing uitgesloten — {...} | `frontend/tabs/devices.js:939` |
| Nog niet compleet: {...} {...}. Telt niet mee voor de datakwaliteit. | `frontend/tabs/devices.js:949` |
| Nog nodig voor een compleet apparaat: {...}. Opslaan mag ook zonder — het apparaat telt dan alleen nog niet mee voor de datakwaliteit. | `frontend/tabs/devices.js:1023` |
| Deze ingevulde gegevens horen niet bij dit apparaattype en verdwijnen bij opslaan: {...}. Zet het type terug om ze te behouden. | `frontend/tabs/devices.js:1034` |
| Het apparaat '{...}' is bijgewerkt. | `frontend/tabs/devices.js:1150` |
| Het apparaat '{...}' is toegevoegd. | `frontend/tabs/devices.js:1151` |
| Het apparaat '{...}' is verwijderd. | `frontend/tabs/devices.js:1207` |
| Weet je zeker dat je '{...}' wilt verwijderen? Er wordt daarna niet meer over geadviseerd. | `frontend/tabs/devices.js:1231` |
| {...} · {...} | `frontend/tabs/sources.js:652` |
| Onbekend brontype '{...}'. Deze bron wordt niet gebruikt. | `frontend/tabs/sources.js:668` |
| Nog niet compleet: {...} | `frontend/tabs/sources.js:683` |
| Aansturing uitgesloten — {...} | `frontend/tabs/sources.js:690` |
| De energiebron '{...}' is bijgewerkt. | `frontend/tabs/sources.js:832` |
| De energiebron '{...}' is toegevoegd. | `frontend/tabs/sources.js:833` |
| De energiebron '{...}' is verwijderd. | `frontend/tabs/sources.js:896` |
| Weet je zeker dat je '{...}' wilt verwijderen? De metingen van deze bron tellen daarna nergens meer mee. | `frontend/tabs/sources.js:921` |
| Deze gegevens horen bij het andere contracttype en worden nu niet gebruikt, maar blijven bewaard: {...}. | `frontend/tabs/home.js:709` |
| De prijsbron "{...}" levert de all-in prijs, dus die wordt ongewijzigd gebruikt. Energiebelasting, opslag leverancier en btw zijn daarom uitgeschakeld: ze rekenen alleen een kale marktprijs om. Zet de prijsbron op "kale marktprijs" als je ze wél wilt gebruiken, of verwijder de bron om alles zelf in te vullen. | `frontend/tabs/home.js:718` |
| Zolang de salderingsregeling geldt — tot {...} — telt de terugleververgoeding niet mee in de berekening: een teruggeleverde kWh is dan evenveel waard als een afgenomen kWh. Vul hem nu al in, dan klopt de besparing zodra de saldering stopt. De terugleverkosten tellen wél mee, ook vandaag. | `frontend/tabs/home.js:734` |
| De terugleverprijsbron "{...}" bepaalt de vergoeding, dus het vaste bedrag hierboven is uitgeschakeld en blijft bewaard. | `frontend/tabs/home.js:747` |
| Het ingevulde netvermogen ligt boven het theoretische maximum van {...} W ({...} × 230 V × {...} A). Controleer de hoofdzekering. | `frontend/tabs/home.js:774` |
| Theoretisch maximum: {...} W ({...} × 230 V × {...} A). | `frontend/tabs/home.js:777` |
| {...} · {...} keer samengevoegd | `frontend/tabs/logbook.js:124` |
| {...}: {...} | `frontend/core/forms.js:124` |
| {...} Dit veld wordt beheerd door DomotiTech; geef het aan hen door. | `frontend/core/roles.js:131` |
| %c DOMOTIAPP ENERGY %c v{...} | `frontend/domotiapp-energy-panel.js:956` |
| De hoofdzekering moet tussen {...} en {...} ampère liggen. | `validators.py:295` |
| De waarschuwingsgrens moet tussen {...} en {...} procent liggen. | `validators.py:311` |
| Het btw-percentage moet tussen {...} en {...} liggen. | `validators.py:330` |
| Het ingevulde netvermogen ligt boven het theoretische maximum van {...} W ({...} x 230 V x {...} A). Controleer de hoofdzekering. | `validators.py:382` |
| Deze bron meet vermogen, maar de eenheid staat op '{...}'. Kies W of kW. Let op: veel slimme-meterintegraties tonen vooral de meterstand in kWh; die is een totaal en geen vermogen, en levert een netbelasting die honderden keren te hoog is. | `validators.py:432` |
| Deze bron levert een prijs, maar de eenheid staat op '{...}'. Kies EUR/kWh of ct/kWh. | `validators.py:446` |
| Het brontype '{...}' is niet bekend. Kies een geldig type. | `validators.py:464` |
| Het apparaattype '{...}' is niet bekend. Kies een geldig type. | `validators.py:621` |
| Toon minimaal {...} en maximaal {...} adviezen. | `validators.py:809` |
| {...} kan niet negatief zijn. | `validators.py:658` |

## 16. Dezelfde tekst op meerdere plekken

Elke regel hier is een tekst die je op één plek kunt herschrijven en op een andere kunt vergeten. De zeven tegelteksten staan er bewust twee keer in — het paneel toont ze, de coach zegt ze — en er is een test die bewaakt dat geen van beide kanten een situatie mist, maar niet dat de bewoording gelijk blijft.

| Tekst | Plekken |
|---|---|
| Reden | `frontend/tabs/coach.js:92` · `frontend/tabs/devices.js:538` · `frontend/tabs/devices.js:615` · `frontend/tabs/sources.js:424` · `frontend/tabs/sources.js:94` |
| Annuleren | `frontend/core/dialog.js:199` · `frontend/core/dialog.js:228` · `frontend/tabs/devices.js:836` · `frontend/tabs/sources.js:602` · `frontend/tabs/sources.js:790` |
| Advies | `frontend/tabs/coach.js:172` · `frontend/tabs/coach.js:50` · `frontend/tabs/coach.js:51` · `frontend/tabs/overview.js:193` |
| Notities | `frontend/tabs/devices.js:309` · `frontend/tabs/sources.js:214` · `frontend/tabs/sources.js:508` · `frontend/tabs/sources.js:95` |
| Opslaan | `frontend/tabs/devices.js:835` · `frontend/tabs/home.js:593` · `frontend/tabs/preferences.js:212` · `frontend/tabs/sources.js:601` |
| Bewerken | `frontend/tabs/devices.js:861` · `frontend/tabs/devices.js:883` · `frontend/tabs/sources.js:617` · `frontend/tabs/sources.js:638` |
| Verwijderen | `frontend/core/dialog.js:197` · `frontend/core/dialog.js:227` · `frontend/tabs/devices.js:862` · `frontend/tabs/sources.js:618` |
| Bezig met opslaan… | `frontend/tabs/devices.js:1121` · `frontend/tabs/home.js:871` · `frontend/tabs/preferences.js:318` · `frontend/tabs/sources.js:817` |
| Alle gegevens voor een betrouwbaar advies zijn ingevuld. | `engine/providers.py:315` · `frontend/tabs/coach.js:328` · `frontend/tabs/overview.js:345` |
| {...}: {...} | `engine/providers.py:199` · `frontend/core/forms.js:124` · `frontend/tabs/coach.js:202` |
| Energiescore | `frontend/tabs/overview.js:119` · `frontend/tabs/overview.js:128` · `translations/nl.json` |
| Nog niet berekend | `frontend/core/dom.js:123` · `frontend/tabs/coach.js:93` · `frontend/tabs/overview.js:146` |
| Waarschuwing | `frontend/tabs/coach.js:52` · `frontend/tabs/logbook.js:54` · `frontend/tabs/overview.js:233` |
| Dit apparaat | `websocket_api.py:778` · `websocket_api.py:813` · `websocket_api.py:859` |
| Naam | `frontend/tabs/devices.js:272` · `frontend/tabs/sources.js:148` · `frontend/tabs/sources.js:78` |
| Ingeschakeld | `frontend/tabs/devices.js:280` · `frontend/tabs/sources.js:156` · `frontend/tabs/sources.js:80` |
| Bedieningsniveau | `frontend/tabs/devices.js:505` · `frontend/tabs/home.js:452` · `frontend/tabs/home.js:566` |
| Entiteit | `frontend/tabs/sources.js:167` · `frontend/tabs/sources.js:248` · `frontend/tabs/sources.js:81` |
| Voor een vermogen: W of kW. | `frontend/tabs/sources.js:364` · `frontend/tabs/sources.js:365` · `frontend/tabs/sources.js:366` |
| Logboek wissen | `frontend/tabs/logbook.js:173` · `frontend/tabs/logbook.js:68` · `translations/nl.json` |
| {...} {...} | `engine/advisor.py:337` · `engine/providers.py:352` |
| Zonneoverschot beschikbaar | `coordinator.py:366` · `engine/advisor.py:263` |
| Het vermogen van je thuisbatterij kan niet uitgelezen worden. Een batterij die laadt verbruikt precies het overschot dat hier staat, dus dat getal kan te hoog zijn. Koppel de vermogenssensor van de batterij om dit op te lossen. | `engine/providers.py:91` · `frontend/tabs/overview.js:369` |
| de woninggegevens | `engine/providers.py:61` · `frontend/core/labels.js:42` |
| een geldige netbron | `engine/providers.py:62` · `frontend/core/labels.js:43` |
| een geldige zonnebron | `engine/providers.py:63` · `frontend/core/labels.js:44` |
| een compleet apparaatprofiel | `engine/providers.py:65` · `frontend/core/labels.js:46` |
| tijdvensters voor flexibele apparaten | `engine/providers.py:66` · `frontend/core/labels.js:47` |
| all-in prijs in €/kWh | `engine/providers.py:74` · `frontend/core/labels.js:58` |
| netbelasting in % | `engine/providers.py:75` · `frontend/core/labels.js:59` |
| netvermogen in W | `engine/providers.py:76` · `frontend/core/labels.js:60` |
| zonneoverschot in W | `engine/providers.py:77` · `frontend/core/labels.js:61` |
| ontbrekende onderdelen | `engine/providers.py:78` · `frontend/core/labels.js:62` |
| Het tarief is altijd gelijk en er zijn geen zonnepanelen, dus er is geen moment dat beter is dan een ander. Er valt daarom niets te optimaliseren. Het advies blijft gewoon werken. | `engine/providers.py:119` · `frontend/tabs/overview.js:71` |
| Er is nu opwek, maar geen apparaat of batterij die verbruik kan verplaatsen. Er valt daarom niets te benutten dat nu niet al gebeurt. | `engine/providers.py:124` · `frontend/tabs/overview.js:79` |
| Zolang de lage en de hoge prijsdrempel niet zijn ingevuld, is niet te bepalen of dit een duur moment is. Vul ze in bij Installatie. | `engine/providers.py:128` · `frontend/tabs/overview.js:64` |
| Je panelen leveren op dit moment niets en de stroomprijs is laag. Er is nu dus geen overschot om te benutten en geen duur verbruik om te vermijden. | `engine/providers.py:132` · `frontend/tabs/overview.js:86` |
| Je panelen leveren op dit moment niets, en bij een vast tarief is het ene moment niet beter dan het andere. Er is nu dus niets te verbeteren. | `engine/providers.py:137` · `frontend/tabs/overview.js:94` |
| De stroomprijs is op dit moment laag, dus er is geen duur verbruik om te vermijden. | `engine/providers.py:141` · `frontend/tabs/overview.js:101` |
| levert terug met | `coordinator.py:344` · `engine/providers.py:283` |
| Niet van toepassing op deze woning, en dus niet meegeteld: {...}. | `engine/providers.py:319` · `frontend/tabs/coach.js:320` |
| De energiescore is nog niet berekend. | `engine/providers.py:348` · `engine/providers.py:357` |
| Niet beschikbaar | `frontend/core/dom.js:85` · `frontend/tabs/overview.js:34` |
| Datakwaliteit | `frontend/tabs/overview.js:132` · `translations/nl.json` |
| Laatste berekening | `frontend/tabs/coach.js:93` · `frontend/tabs/overview.js:145` |
| Netvermogen | `frontend/tabs/overview.js:152` · `translations/nl.json` |
| Zonneoverschot | `frontend/tabs/overview.js:160` · `translations/nl.json` |
| Actuele energieprijs | `frontend/tabs/overview.js:171` · `frontend/tabs/sources.js:53` |
| Fout | `frontend/tabs/logbook.js:55` · `frontend/tabs/overview.js:296` |
| Nog geen advies berekend | `frontend/tabs/coach.js:270` · `frontend/tabs/overview.js:387` |
| Zodra er een energiebron gekoppeld is, verschijnt hier het hoofdadvies. | `frontend/tabs/coach.js:273` · `frontend/tabs/overview.js:390` |
| Opnieuw berekenen | `frontend/tabs/coach.js:95` · `translations/nl.json` |
| Bron niet beschikbaar | `frontend/tabs/logbook.js:38` · `storage.py:335` |
| Ongeldige meting | `frontend/tabs/logbook.js:39` · `storage.py:342` |
| De energiebron '{...}' is toegevoegd. | `frontend/tabs/sources.js:833` · `websocket_api.py:633` |
| De energiebron '{...}' is bijgewerkt. | `frontend/tabs/sources.js:832` · `websocket_api.py:671` |
| Deze energiebron | `websocket_api.py:662` · `websocket_api.py:697` |
| De energiebron '{...}' is verwijderd. | `frontend/tabs/sources.js:896` · `websocket_api.py:707` |
| Apparaat toegevoegd | `frontend/tabs/logbook.js:35` · `websocket_api.py:748` |
| Het apparaat '{...}' is toegevoegd. | `frontend/tabs/devices.js:1151` · `websocket_api.py:749` |
| Het apparaat '{...}' is bijgewerkt. | `frontend/tabs/devices.js:1150` · `websocket_api.py:787` |
| Apparaat verwijderd | `frontend/tabs/logbook.js:36` · `websocket_api.py:822` |
| Het apparaat '{...}' is verwijderd. | `frontend/tabs/devices.js:1207` · `websocket_api.py:823` |
| Thuisbatterij | `frontend/tabs/devices.js:60` · `frontend/tabs/sources.js:57` |
| Alleen adviseren | `frontend/tabs/devices.js:97` · `frontend/tabs/home.js:571` |
| Vragen om goedkeuring | `frontend/tabs/devices.js:98` · `frontend/tabs/home.js:572` |
| Automatisch aansturen | `frontend/tabs/devices.js:99` · `frontend/tabs/home.js:573` |
| Uitlezen | `frontend/tabs/devices.js:103` · `frontend/tabs/sources.js:120` |
| Aan- en uitschakelen | `frontend/tabs/devices.js:104` · `frontend/tabs/sources.js:121` |
| Vermogensgrens instellen | `frontend/tabs/devices.js:105` · `frontend/tabs/sources.js:122` |
| Laadstroom instellen | `frontend/tabs/devices.js:106` · `frontend/tabs/sources.js:123` |
| Klaar uiterlijk om | `frontend/tabs/devices.js:435` · `frontend/tabs/devices.js:612` |
| Niet eerder klaar dan | `frontend/tabs/devices.js:449` · `frontend/tabs/devices.js:613` |
| Dagen | `frontend/tabs/devices.js:462` · `frontend/tabs/devices.js:614` |
| Aansturing uitgesloten voor deze installatie | `frontend/tabs/devices.js:529` · `frontend/tabs/sources.js:415` |
| Noteer waarom, zodat dit later terug te vinden is. | `frontend/tabs/devices.js:539` · `frontend/tabs/sources.js:427` |
| Apparaat | `frontend/tabs/devices.js:685` · `frontend/tabs/devices.js:779` |
| Aansturing | `frontend/tabs/devices.js:706` · `frontend/tabs/sources.js:504` |
| Apparaten | `frontend/tabs/devices.js:724` · `frontend/tabs/devices.js:729` |
| Apparaat toevoegen | `frontend/tabs/devices.js:732` · `frontend/tabs/devices.js:980` |
| Nog niet compleet: {...} | `frontend/tabs/devices.js:931` · `frontend/tabs/sources.js:683` |
| Compleet. | `frontend/tabs/devices.js:963` · `frontend/tabs/sources.js:695` |
| zonder naam | `frontend/tabs/devices.js:1145` · `frontend/tabs/sources.js:827` |
| De configuratie is intussen ergens anders gewijzigd. Je wijzigingen zijn niet opgeslagen; de lijst is opnieuw geladen. | `frontend/tabs/devices.js:1159` · `frontend/tabs/sources.js:844` |
| Bezig met verwijderen… | `frontend/tabs/devices.js:1199` · `frontend/tabs/sources.js:888` |
| De configuratie is intussen ergens anders gewijzigd. Er is niets verwijderd; de lijst is opnieuw geladen. | `frontend/tabs/devices.js:1214` · `frontend/tabs/sources.js:903` |
| Wijzigingen verwerpen? | `frontend/tabs/devices.js:1261` · `frontend/tabs/sources.js:951` |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Verwerp je ze, dan zijn ze weg. | `frontend/tabs/devices.js:1263` · `frontend/tabs/sources.js:953` |
| Verwerpen | `frontend/tabs/devices.js:1265` · `frontend/tabs/sources.js:955` |
| Terug naar het formulier | `frontend/tabs/devices.js:1266` · `frontend/tabs/sources.js:956` |
| Soort bron | `frontend/tabs/sources.js:151` · `frontend/tabs/sources.js:79` |
| Entiteit voor afname | `frontend/tabs/sources.js:267` · `frontend/tabs/sources.js:82` |
| Entiteit voor teruglevering | `frontend/tabs/sources.js:272` · `frontend/tabs/sources.js:83` |
| Hoe meet deze meter? | `frontend/tabs/sources.js:226` · `frontend/tabs/sources.js:84` |
| Wat levert deze bron? | `frontend/tabs/sources.js:177` · `frontend/tabs/sources.js:86` |
| Waarde uitlezen uit | `frontend/tabs/sources.js:286` · `frontend/tabs/sources.js:87` |
| Naam van het attribuut | `frontend/tabs/sources.js:302` · `frontend/tabs/sources.js:88` |
| Eenheid | `frontend/tabs/sources.js:310` · `frontend/tabs/sources.js:89` |
| Schaalfactor | `frontend/tabs/sources.js:318` · `frontend/tabs/sources.js:90` |
| Teken omdraaien | `frontend/tabs/sources.js:324` · `frontend/tabs/sources.js:91` |
| Voor een prijs: EUR/kWh of ct/kWh. | `frontend/tabs/sources.js:362` · `frontend/tabs/sources.js:363` |
| Energiebronnen | `frontend/tabs/sources.js:513` · `frontend/tabs/sources.js:518` |
| Sluiten | `frontend/core/dialog.js:60` · `frontend/tabs/sources.js:790` |
| Naam van de woning | `frontend/tabs/home.js:64` · `translations/nl.json` |
| Vergelijk met de all-in prijs, niet met de kale marktprijs van je prijsbron. | `frontend/tabs/home.js:356` · `frontend/tabs/home.js:364` |
| Wijzigingen verwerpen | `frontend/tabs/home.js:594` · `frontend/tabs/preferences.js:213` |
| Verwerpen en verdergaan | `frontend/tabs/home.js:601` · `frontend/tabs/preferences.js:217` |
| Hier blijven | `frontend/tabs/home.js:602` · `frontend/tabs/preferences.js:218` |
| De configuratie is intussen ergens anders gewijzigd. Je wijzigingen zijn niet opgeslagen; het formulier is opnieuw geladen met de actuele gegevens. | `frontend/tabs/home.js:892` · `frontend/tabs/preferences.js:339` |
| Je hebt wijzigingen die nog niet zijn opgeslagen. Sla ze op, of verwerp ze om verder te gaan. | `frontend/tabs/home.js:961` · `frontend/tabs/preferences.js:397` |
| Logboek | `frontend/tabs/logbook.js:60` · `frontend/tabs/logbook.js:65` |
| Er is een onbekende fout opgetreden. | `frontend/core/api.js:146` · `frontend/core/api.js:157` |
| Gebruik een geldige tijd in de vorm uu:mm. | `validators.py:740` · `validators.py:830` |
| Koppel een entiteit aan deze bron. | `validators.py:513` · `validators.py:581` |
