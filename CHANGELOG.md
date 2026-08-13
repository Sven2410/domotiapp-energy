# Changelog

## 0.30.0

Eén schone lezing sluit de hele stapel, en het logboek belooft minder. SPEC §63.6.4.

### Fixed

- **Een bron die weer werkt sloot maar één open regel per herberekening.** Lagen er meer
  open regels van dezelfde bron, dan kreeg elke regel een eigen "opgelost om", vijftien
  seconden na de vorige — en geen van die momenten was een herstel. Op een klantinstallatie
  gingen zo 112 regels dicht, tien minuten lang.

  Onder de dagkop van het paneel las dat als onzin: een regel van 23:32 op 11 augustus
  meldde "Opgelost om 12:49", want die 12:49 was de dag erna.

  Eén schone lezing sluit nu álle open regels van die bron, in één pas en met één
  schrijfactie in plaats van één per regel.

- **De stapel kon ook zonder upgrade ontstaan, en dat is de reden dat dit een fix is.**
  Twee routes waarbij er een tweede regel bij komt zonder dat er iets hersteld is: een
  storing die van karakter verandert (stilgevallen → onbereikbaar, meer dan een kwartier
  uit elkaar), en een verkeerd gekoppelde bron die na elke herstart opnieuw gemeld wordt en
  nooit schoon leest. In dat tweede geval bleven de oudere regels ná de reparatie voor
  altijd beweren dat de bron stuk was.

### Changed

- **"Opgelost om 16:32" heet nu "Weer uitgelezen om 16:32".** Wij weten niet wanneer een
  bron het weer deed; wij weten wanneer een herberekening haar schoon las. Dat scheelt tot
  vijf minuten, en over een herstart of upgrade heen willekeurig veel — voor elke regel
  behalve de nieuwste van een stapel is het een bovengrens.

- **De dag staat erbij zodra de sluiting op een andere dag valt** dan de regel zelf:
  *"Weer uitgelezen op 12 augustus om 12:49."* Een kale kloktijd erfde de dagkop erboven,
  en die klopte dan niet meer.

### Docs

- **`HARDWARE.md`** verzamelt wat we van merken en integraties hebben waargenomen, met per
  merk gescheiden wat *waargenomen* is, wat *afgeleid* is en wat *niet gemeten* is. Twee
  regels dragen het: elke waarneming noemt de installatie waar zij vandaan komt, en geen
  code vertakt ooit op merk. Ingevuld voor SolarEdge en Easee.

- **SPEC §63.6.3 gecorrigeerd.** Daar stond dat het samenvouwen "onder meer op de tekst"
  matcht; het vergelijkt alleen `event_type` en `subject`. Het gedrag klopte, de vastgelegde
  reden niet — en die reden verbood onbedoeld de datum in de zin hierboven.

- **SPEC §63.7** legt vast waar een meting die één tel lang fysiek onmogelijk is werkelijk
  kantelt, uit de formules afgeleid, en dat dit voor andere configuraties **ongemeten** is.

- **`scripts/solar_spikes.py`** telt kortstondige pieken in een vermogensreeks uit de
  recorder — alleen-lezen, geen onderdeel van de integratie. Het is het gereedschap waarmee
  de SolarEdge-waarnemingen in `HARDWARE.md` gemeten zijn, zodat een tweede installateur ze
  kan overdoen.

## 0.29.0

Het logboek spreekt niet meer over nu. SPEC §63.6.

### Fixed

- **Een storingsmelding bleef er de volgende ochtend staan alsof zij van dat moment was.**
  "De bron is niet bereikbaar, er is op dit moment geen meting", geschreven om 23:00 en
  gelezen om 09:00 met de omvormer alweer twee uur aan het leveren.

  Een regel in een logboek gaat over het moment waarop zij geschreven werd. De zin staat nu
  in de verleden tijd, en zodra de bron weer gelezen kan worden krijgt de regel er één zin
  bij: *"Opgelost om 07:02."* Geen tweede regel, dus het logboek blijft even ver
  terugkijken als het deed.

- **Bekende regressie van 0.28.0, hiermee opgelost.** In 0.28.0 kon een bron die van
  "niet bereikbaar" naar "nog geen waarde" ging en uren later terugviel, een **tweede**
  waarschuwing opleveren voor dezelfde storing. De stille melding was voor het
  anti-spamgeheugen niet te onderscheiden van een herstel.

  Wie 0.28.0 draait en dit ziet: het is dit, en het is nu weg. Er is verder niets aan de
  hand met de bron.

- **Een uitgeschakelde bron telde als "zojuist met succes gelezen".** Dat had in 0.28.0 nog
  geen gevolgen, maar het zou "uitgezet" als "gerepareerd" hebben gelezen zodra er gedrag
  aan hing.

### Changed

- Het opgeslagen logboek kreeg er één veld bij. Bestaande logboeken worden gewoon gelezen;
  regels van vóór deze versie dragen geen einde, en het paneel doet daar dan ook geen
  uitspraak over — "nog gaande" beweren over een oude regel zou dezelfde onwaarheid zijn
  als die deze versie wegneemt.

### Nog niet in deze versie

- Een omvormer die 's nachts slaapt levert nog steeds een melding op, en de datakwaliteit
  zakt er nog steeds van. Dat is een eigen ronde.

## 0.28.0

Een bron zonder waarde is geen kapotte bron. SPEC §63.5.

### Fixed

- **De reparatie van 0.27.1 hield acht herstarts op één dag niet tegen.** Op 11 augustus
  stonden er acht herstarts in Svens logboek, en na elke herstart verschenen dezelfde loze
  bronmeldingen weer — enkele seconden na het laden van de integratie.

  De poort van 0.27.1 vroeg "is Home Assistant klaar met opstarten", terwijl de melding
  beweert "deze bron is stuk". Dat zijn twee verschillende dingen. Home Assistant is klaar
  met opstarten op het moment dat je slimme meter zijn eerste telegram nog moet sturen: de
  entiteit bestáát dan, en staat op `unknown`.

- **`unknown` en `unavailable` worden niet langer als hetzelfde gelezen.** Home Assistant
  schrijft `unavailable` wanneer een integratie zegt dat zij het apparaat niet kan bereiken,
  en `unknown` wanneer de entiteit leeft en nog geen waarde heeft. Dat onderscheid ging bij
  ons één regel na het uitlezen verloren, samen met het verschil tussen "de entiteit bestaat
  niet" en "de meting is te oud".

  Vier situaties krijgen nu hun eigen reden en hun eigen zin in het logboek.

- **Een bron die nog nooit gelezen is, krijgt geen oordeel.** "Deze installatie heeft een
  kapotte bron" veronderstelt dat wij hem ooit hebben zien werken. Vlak na een herstart weten
  we dat niet, dus zeggen we het niet.

- **Een echte storing blijft gewoon gemeld.** Een omvormer die de hele avond geleverd heeft
  en om 23:00 van het netwerk valt, staat onverkort in het logboek — net als een verkeerd
  gekoppelde entiteit, die zelfs meteen gemeld wordt zonder op iets te wachten.

  Er zit **geen wachttijd** in deze reparatie. Die zou de echte storing verbergen en het
  herstartprobleem laten bestaan: de acht herstarts werden beslist door minder dan vijf
  seconden, en bij de achtste ging het toevallig goed.

### Changed

- Het logboek zegt voortaan wát er met een bron aan de hand is: "Bron niet bereikbaar",
  "Bron is stilgevallen", "Bron niet gevonden" of "Bron heeft nog geen waarde", elk met een
  eigen uitleg in plaats van één zin voor alle vier.

## 0.27.1

Geen loze waarschuwingen meer bij het opstarten. SPEC §63.

### Fixed

- **Bij elke herstart van Home Assistant meldde het logboek dat alle bronnen niet beschikbaar
  waren.** Dat kwam niet door je bronnen: DomotiApp Energy wordt opgezet zodra zijn eigen
  afhankelijkheden klaar zijn, en Home Assistant start integraties parallel — dus je
  omvormer, je prijsbron en je slimme meter bestonden op dat moment nog niet.

  De melding klopte feitelijk en betekende niets: een seconde later waren ze er wel. Bij elke
  update van Home Assistant kreeg je zo drie waarschuwingen die niets te betekenen hadden, en
  dat is erger dan ruis — het leert je waarschuwingen negeren.

  Een leesfout tijdens het opstarten gaat nu naar het technische log en niet naar het
  logboek, en zodra Home Assistant klaar is met starten wordt er opnieuw gerekend. Pas daarna
  telt een bron die niet gelezen kan worden als een echte melding.

## 0.27.0

Het logboek leest als een tijdlijn. SPEC §61.4 — het laatste openstaande deel van het
historisch overzicht.

### Gewijzigd

- **Elke dag krijgt een kop:** *Vandaag*, *Gisteren*, en daarvoor de dag voluit
  (*"zaterdag 9 augustus"*). Een gebeurtenis draagt dan alleen nog het tijdstip — *14:32* in
  plaats van *11-08-2026, 14:32:07 · Advies herberekend*.

  Wat er stond was technisch juist en las als een export. Wat er nu staat leest als wat er
  die dag gebeurde.

- **"Info" staat niet meer op elke regel.** Bij een waarschuwing of een fout blijft het woord
  staan — de betekenis mag nooit alleen in een kleur zitten — maar bij een gewone melding
  vertaalt dat woord niets en drukt het de zin eronder weg.

- **Het aantal van een samengevoegde reeks staat nu naast het tijdstip:** *"14:32 · 40 keer"*.
  Dat een reeks is samengevoegd blijft zichtbaar; veertig keer wegvallen is een ander verhaal
  dan één keer.

## 0.26.0

De weg terug op een wandtablet. SPEC §62.

Op een tablet met Fully Kiosk en zonder zijbalk is elke navigatie uit dit paneel
eenrichtingsverkeer: wie wegklikt, komt niet terug. Dat gold voor de link naar het
Energie-dashboard uit 0.25.0, en er was sowieso geen weg terug naar het hoofddashboard.

### Toegevoegd

- **Een terugknop linksboven**, naast de tabbalk en er buiten — het paneel verlaten is geen
  tabblad. Hij verschijnt zodra je bij Woning invult waar het hoofddashboard van deze woning
  staat.

- **Twee velden onder "Navigatie"** bij Woning: waar *terug* heen gaat, en waar het verbruik
  van deze klant staat. Ze verschillen per woning, dus ze worden niet geraden.

### Gewijzigd

- **De link naar het Energie-dashboard is voorwaardelijk geworden.** Is er geen adres
  ingevuld, dan staat de zin er nog steeds — hij bestaat om te zeggen wáár het antwoord
  woont — maar zonder link. Zo belandt niemand op een wandtablet ergens waar hij niet meer
  wegkomt, en blijft een klant die kWh zoekt weten waar dat staat.

### Niet gebouwd, en waarom

- **Geen pop-up met het Energie-dashboard erin.** Het kán: Home Assistant staat toe dat een
  pagina van dezelfde origin haar in een iframe zet. Maar dan draait de hele HA-frontend een
  tweede keer, mét zijbalk, in een venster op een wandtablet — een pagina in een pagina.

- **Geen kiosk-instelling.** Een leeg adres zegt al "hier mag niet genavigeerd worden". Een
  tweede vraag zou hetzelfde nog eens stellen, en met de eerste uiteen gaan lopen.

- **Niets in de datakwaliteit.** Een woning met een zijbalk heeft geen terugknop nodig en kan
  dat item dus nooit afvinken — precies de fout die dit project vijf keer heeft opgeruimd.

## 0.25.0

Het historisch overzicht, eerste helft. SPEC §61.

### Toegevoegd

- **"Hoe het gisteren ging"** op het Overzicht, onder de bediening: hoeveel uur er
  zonneoverschot was, wat het hoogste netvermogen was en of de installatie de hele dag
  compleet was. Drie feiten, en dat is een grens en geen richtlijn — een blok dat groeit
  wordt een dashboard.

  Elk feit zegt met opzet minder dan je zou willen. *"Ongeveer 4 uur zonneoverschot"* zegt
  niet dat je het gebruikt hebt, en er staat nergens wat het opgeleverd heeft: de coach
  adviseert, en of het advies is opgevolgd weet niemand.

  Is er nog geen hele dag geweest, dan staat er één zin in plaats van drie lege regels. En
  elk feit zegt erbij over hoeveel uur het iets weet zodra dat niet de hele dag is: een bron
  kan stil vallen terwijl de rest doorloopt, en aan het getal zelf is dat niet te zien.

- **"Hoogste in 30 dagen"**, met erbij op hoeveel dagen de woning boven haar
  waarschuwingsgrens uitkwam. Het enige feit dat over een langere periode meeschaalt zonder
  scheef te trekken — het is een maximum en een telling, en geen van beide middelt iets weg —
  en het enige dat Home Assistant zelf niet kan tonen, want zij kent je maximale netvermogen
  niet.

  Twee getallen omdat een installateur een andere vraag stelt dan "hoe hoog": bij een klant
  die belt over een gesprongen zekering wil hij weten of de woning er structureel tegenaan
  zit of dat het één keer gebeurde.

- **Een verwijzing naar het Energie-dashboard**, in het blok zelf. Wie kWh, kosten of zelf
  verbruikte energie zoekt en hier niets vindt, concludeert dat het ontbreekt — niet dat het
  ergens anders beter staat.

- **`sensor.domotiapp_energy_self_consumption`** — de negende entiteit, en de enige van onze
  cijfers die zegt wat de *bewoner* deed. Home Assistant bewaart hem, dus je kunt er zelf een
  grafiek van maken. Een entiteit is een belofte: hij kan niet meer weg.

### Niet gebouwd, en waarom

- **Geen dagelijkse zelfbenutting.** Het gemiddelde van een verhouding is niet de verhouding
  van de sommen: een ochtenduur met 200 W opwek waarvan je alles gebruikt telt in zo'n
  gemiddelde even zwaar als een middaguur met 4 kW waarvan je de helft terugleverde. Dat
  getal valt structureel te hoog uit voor precies de woning die het meest te winnen heeft.
  De juiste dagwaarde vraagt om kWh, en die heeft het Energie-dashboard van HA al.

- **Geen verbruiksgrafieken.** Die leest HA rechtstreeks uit je meters; alles wat wij uit
  vermogensgemiddelden zouden bouwen is daar een slechtere kopie van.

## 0.24.0

Bediening staat op het Overzicht. SPEC §60.

De gereed-knop stond op Apparaten, en dat is het tabblad waar een installateur een woning
inricht. Een bewoner met een volle vaatwasser gaat daar niet heen — hij slaat het Overzicht
open. De toets die dat beslist: **waar staat iemand als hij dit doet?**

### Toegevoegd

- **"Wat je nu kunt doen"** op het Overzicht, direct onder `Advies`. Per apparaat waarvan de
  bewoner iets gevraagd wordt: wat het is, hoelang een gezette melding nog geldt, en één knop.

  De sectie bestaat zodra deze woning zoiets heeft, en verdwijnt bij een woning die niets te
  bedienen heeft — geen lege sectie die een tekortkoming aankondigt die niemand kan opheffen.

  **Eén sectie, niet één per soort handeling.** Bij de aansturingsrelease komen *Start nu*,
  *Stop* en *Goedkeuren* erbij als rijsoorten in dezelfde sectie. Anders zou de bewoner moeten
  weten wélke sectie zijn handeling draagt, en dat is precies het probleem dat deze verhuizing
  oplost.

### Gewijzigd

- **De knop "Klaar / vol" is weg bij Apparaten.** Twee plekken zijn alleen te verdedigen als
  het twee *momenten* zijn; Apparaten is geen moment dat een bewoner heeft. Bovendien leest een
  knop op een configuratierij alsof hij iets instelt in plaats van iets doet.

  Onder het advies in de Energiecoach blijft hij staan: dat is de aanleiding zelf.

- **Een apparaat op *Alleen meekijken* krijgt geen knop.** De melding voedt alleen het
  urgentie-advies, dus zonder advies vraagt hij om iets dat niemand leest — dezelfde regel als
  bij het tijdvenster en het apparaatprofiel.

## 0.23.0

De gereed-vlag: de coach adviseert een machine pas te starten als iemand heeft gezegd dat er
werk in zit. Fase 3 van SPEC §32.

### Toegevoegd

- **"Klaar / vol" op twee plekken** — op Apparaten bij het apparaat, en onder het advies dat
  erom vraagt. Dat is geen duplicatie maar de twee momenten waarop een bewoner eraan denkt:
  hij ruimt de keuken op en zet de machine aan het eind vol, of hij leest *"start nu om 07:00
  te halen"* en denkt "hij is niet vol" (§44.6).

- **Het vervalmoment staat er in woorden bij**, want een bewoner die 's avonds zijn vaatwasser
  vult moet weten dat de melding morgenochtend nog geldt: *"Staat vol. Dit vervalt morgen om
  07:00, of eerder zodra hij klaar is."*

  Is er geen status- of resttijdentiteit gekoppeld, dan kan het systeem "klaar" nooit zien, en
  dat staat er dan meteen bij — op het moment van indrukken, niet wanneer iemand zich afvraagt
  waarom er niets gebeurde: *"We kunnen niet zien wanneer hij klaar is, dus dit blijft staan
  tot morgen om 07:00. Zet het eerder uit als er niets meer in zit."*

- **Het veld *Moet gemeld worden dat er werk in zit*** op Apparaten. Standaard aan voor
  vaatwasser, wasmachine en droger; uit voor de rest, inclusief de laadpaal, die via zijn
  statuskoppeling zelf kan zien of er een auto hangt.

### Gewijzigd

- **Het urgentie-advies zegt nu wat het weet.** Staat de vlag, dan luidt het *"Start Vaatwasser
  nu om 07:00 te halen"* als waarschuwing — de zin en de zwaarte die §32.3 altijd al
  voorschreef. Staat hij niet, dan komt er geen advies: dat is de lege machine waarvoor deze
  hele ronde bestaat.

  Een apparaat dat geen vlag nodig heeft houdt de voorwaardelijke zin *"als hij om 07:00 klaar
  moet zijn"*. Voor zo'n apparaat is oprecht onbekend of er werk is, en een onbekend antwoord
  hoort zijn eigen voorwaarde te noemen in plaats van iets te beweren.

### Niet gebouwd, en waarom

- **Detectie van "klaar" via het vermogen** staat in §32.6 als derde methode en is er niet
  gekomen. Een vaatwasser die tussen wassen en drogen niets trekt, ziet er hetzelfde uit als
  een die klaar is — en die fout is stil: de vlag valt weg en de bewoner moet opnieuw drukken
  zonder te weten waarom.

  De winst zou bovendien klein zijn: de vlag vervalt al aan het einde van het gereed-venster,
  en een apparaat zonder venster krijgt sowieso geen urgentie-advies. Een status- of
  resttijdentiteit zegt het wél zeker, en die twee doen het werk.

## 0.22.0

Het laadminimum hangt aan de auto, niet aan de paal (SPEC §59), en het uurbedrag dat niet te
berekenen is legt nu uit waarom (SPEC §56.8).

Aanleiding voor het eerste is een meting op echte hardware: 7 A leverde 4765 W, wat 3 × 230 × 7
is. De auto laadt dus driefasig en het minimum is ~4140 W — niet de 1380 W die op grond van
"eenfasig laden" was ingevuld. Een factor drie, en niets in het product kon het zeggen.

> **0.21.0 is nooit uitgebracht.** De tag week af van het manifest, de release-workflow
> weigerde hem, en hij is ingetrokken vóór er een release stond. Alles wat voor die versie
> geschreven was staat hieronder.

### Toegevoegd

- **Het laagst gemeten vermogen staat op de apparaatrij**, voor apparaten met *Kan op
  deelvermogen draaien* aan: *"Nu: 0 W · laagste meting sinds herstart: 4140 W"*. Dat is het
  enige getal dat kan laten zien dat een ingevuld minimum te hoog staat — en dat is precies
  de helft van die fout die je niet kunt zien, want te hoog betekent dat het advies wegblijft
  en stilte lijkt op "geen overschot".

  Het gebruikt de vermogenssensor die er al is. De omgekeerde route — het aantal fasen
  uitrekenen uit vermogen en stroom — is bewust afgewezen: dat werkt alleen als de
  stroomsensor per fase meldt in plaats van de som, en niets in de waarde verraadt welke van
  de twee het is. Die aanname faalt stil in de schadelijke richting.

  *"Sinds herstart"* staat er niet voor niets bij: de waarneming leeft in het geheugen en gaat
  nooit naar de opslag. Zonder die woorden zou het lezen als *"het laagste dat deze paal kan"*,
  en dat is een uitspraak over de hardware die dit product niet kan doen.

### Gewijzigd

- **De hulptekst bij *Minimaal vermogen* zegt nu waar het getal vandaan komt.** Hij noemde
  1380 W en 4140 W zonder erbij te zeggen dat de keuze tussen die twee aan de **auto** hangt
  en niet aan de paal — en SPEC §57.3 ging een stap verder door eenfasig het waarschijnlijke
  geval te noemen. Beide getallen staan er nog, geen van beide wordt aangeprezen, en er staat
  bij dat meten met de auto aan de paal de enige manier is om het zeker te weten.

- **Het formulier rekent de ingevulde waarde terug naar ampère:** *"4140 W is ongeveer 18,0 A
  op één fase, of 6,0 A op drie fasen."* Ampère is het getal dat een laadpaal toont, dus dit
  is meteen de controle — 18 A op één fase is geen stand die een paal heeft.

  Er komt geen opgeslagen fasenveld: dat zou een waarde zijn die de motor nooit leest, en het
  zou naast `phases` bij Woning komen te staan, dat dezelfde vraag over het huís beantwoordt.

### Fixed

- **Een laadpaal zonder bedrag per uur zegt nu welk veld de som stopte.** Voor een apparaat
  dat neemt wat er over is, is het totaal met opzet leeg en is het bedrag per uur het
  antwoord (§56.4) — maar ontbrak dát bedrag ook, dan toonde de kaart geen van beide rijen
  en bleef het advies even opgewekt als altijd. De klant zag *"dit is een gunstig moment"*
  zonder één woord over de prijs die eronder ontbrak.

  Nu staat er bij: *"Hoeveel dit oplevert is niet te berekenen zonder het vaste
  leveringstarief — vul dat in bij Woning."* Dezelfde zinnen die het totaal al gebruikte,
  want een ontbrekende importprijs stopt beide sommen om dezelfde reden en wordt op dezelfde
  plek ingevuld.

  Is het laadvermogen zelf onbekend, dan zegt het advies dát: *"Hoeveel dit per uur oplevert
  is niet te berekenen zonder het maximale laadvermogen van Laadpaal — vul dat in bij
  Apparaten."* Dat is de enige andere term die het uurbedrag nodig heeft.

- **Een laadpaal wordt naar het veld gestuurd dat op zijn eigen formulier staat.** Het
  apparaatformulier vraagt een laadpaal om *Energie per laadsessie* en *Maximaal
  laadvermogen* — een auto heeft geen cyclus — terwijl het advies iedereen naar *de energie
  per cyclus* en *het nominale vermogen* verwees. Gevonden bij het splitsen hierboven, en het
  is dezelfde fout die deze zinnen juist moeten voorkomen: de installateur laten zoeken naar
  iets dat niet op zijn scherm staat.

  **Dezelfde fout stond op nog twee plekken**, gevonden bij de browsercontrole van deze
  release: de zin over wat er nog ontbreekt, zowel boven in het dialoogvenster als op de
  apparaatrij. Het venster zei *"Nog nodig voor een compleet apparaat: nominaal vermogen,
  energie per cyclus"* terwijl de twee velden eronder anders heetten. Alle drie de plekken
  vragen nu het apparaattype, net als het formulier zelf.

## 0.20.0

Een lege plek zegt nu niets in plaats van "mislukt". SPEC §58.2, uitgewerkt in §58.4.

### Gewijzigd

- **De sectiekop op Energiecoach heet nu "Gegevens voor je advies".** Hij heette
  *"Ontbrekende gegevens"* en stond bij een complete woning boven de zin *"Alle gegevens voor
  een betrouwbaar advies zijn ingevuld"* — een kop die een tekort belooft en het er direct
  onder ontkent. Voor de woning van §58, waar niets ontbreekt en niets zal gaan ontbreken, was
  dat de laatste plek op het scherm die nog naar een gebrek wees.

  Of er iets ontbreekt is een feit over dit moment, dus het staat nu waar de feiten staan:
  **"Nog ontbrekend:"** verschijnt boven de lijst, en verdwijnt met de lijst mee. Dezelfde
  woorden waarmee de coach zelf *"Welke gegevens ontbreken nog?"* beantwoordt.

### Fixed

- **"Geschatte besparing: Niet te berekenen" is weg waar er niets te berekenen viel.** Alleen
  het zonneoverschot-advies draagt ooit een bedrag; bij elk ander advies kondigde die rij een
  som aan die nooit geprobeerd was. Onder *"de situatie vraagt niet om een aanpassing"* las dat
  als een mislukte berekening, terwijl er simpelweg niets te besparen is omdat er niets te
  veranderen is.

  De rij verschijnt nu wanneer er een bedrag is. Werd er wél gerekend en lukte het niet, dan
  staat de reden al één regel hoger in het advies zelf, mét het veld dat de som stopte — meer
  waard dan *"Niet te berekenen"* ooit was.

- **Een modulerende laadpaal toont zijn opbrengst nu ook bij het hoofdadvies.** Voor een paal
  die neemt wat er over is, is het totaal met opzet leeg en is het bedrag per uur het antwoord
  (§56.4) — maar het hoofdadvies las alleen het totaal. De klant kreeg *"Niet te berekenen"*
  terwijl het bedrag ongebruikt in de payload zat; de lijst met overige adviezen toonde het
  sinds 0.18.0 wel.

  Er is nu een tweede rij, **"Geschatte opbrengst per uur"**, met *"Zolang dit zonneoverschot
  er is."* eronder. Een eigen rij en een eigen label, want de twee bedragen mogen nooit in
  dezelfde regel of dezelfde vergelijking komen.

### Openstaand

- **Een modulerend apparaat waarvan ook het uurbedrag niet te berekenen is** — geen leesbare
  prijs, dus geen marge — toont nu geen van beide rijen, en het advies legt niet uit waarom.
  De datakwaliteit en het antwoord op *"welke gegevens ontbreken nog?"* melden de ontbrekende
  prijsinformatie wel. **Genoteerd bij §56 als §56.8**, want het uitleggen hoort bij
  `_surplus_message`: `_why_no_amount` begint bij de energie per cyclus, en dat veld gebruikt
  een modulerende paal niet. Die functie wees in 0.18.0 al een keer de verkeerde schuldige
  aan, en dat is genoeg reden om hem hier niet op los te laten.

- **§54.7 op echte hardware.** Ongewijzigd sinds 0.19.0: SPEC §57.3 beschrijft wat er voor
  Svens eigen Easee ingevuld moet worden.

### Documentatie

- **SPEC §58: woning 1, het rijtjeshuis zonder zon.** De laatste van de drie, en de eerste
  woningronde zonder blokkade of stille fout. Geen zon, geen batterij, geen auto, vast
  contract: de woning waar het vaakst "niet van toepassing" op het scherm staat.

  **Het antwoord op de vraag waarvoor zij bedoeld was:** een lege plek leest daar als
  informatie en niet als gebrek. De twee dingen die nog wrongen zijn hierboven opgelost, en
  §58.4 legt vast dat het één regel bleek te zijn: een rij of een kop bestaat omdat er iets te
  zeggen is.


## 0.19.0

Twee regels over eenheden, en waarom ze verschillen. SPEC §57, uit §54.6.

### Fixed

- **Een geweigerde vermogenssensor wordt niet meer stil overgeslagen.** Koppelde je een
  entiteit die niet in W of kW meet — een meterstand in kWh is de klassieke misgreep, waar het
  bronformulier in zoveel woorden voor waarschuwt — dan toonde de rij niets, precies zoals bij
  een apparaat waaraan niemand iets gekoppeld had.

  De rij zegt nu: *"De gekoppelde vermogenssensor is niet te gebruiken: hij moet in W of kW
  meten en een waarde melden."* Weigeren mag, zwijgen niet.

- **Het formulier zegt nu welke van de twee eenheidsregels waar geldt.** Op Energiebronnen
  kiest de installateur de eenheid zelf en leest hij dat die van de entiteit nooit gebruikt
  wordt; bij een apparaatkoppeling is het andersom, en daar stond geen woord over.

### Overwogen en niet gedaan

- **De twee regels gelijktrekken.** Het verschil is terecht en volgt uit het gevolg: de
  eenheid van een bron bepaalt het netvermogen, het overschot, de score en elke zin die
  daarop rust, terwijl die van een apparaatkoppeling één getal op één rij bepaalt.
  Gelijktrekken zou ofwel een nutteloos veld op elk apparaat opleveren, ofwel een bron die de
  entiteit gelooft in precies het geval waarin dat honderden keren misgaat.

### Openstaand

- **§54.7 op echte hardware.** Sven heeft zelf een Easee; de simulatie van woning 3 gebruikte
  verzonnen entiteiten. SPEC §57.3 beschrijft wat er ingevuld moet worden — welke waarde in
  `min_power_w` hoort bij één of drie fasen, welke sensor de juiste `power_entity` is, en
  waar op te letten als het advies uitblijft.


## 0.18.0

De twee structurele gaten van woning 3, samen. SPEC §56.

### Toegevoegd

- **Een deadline die niet elke dag hoeft te gelden** (`ready_days`). De bewoner van woning 3:
  *"laad hem vol als ik morgen weg moet, en anders alleen wanneer het gunstig is."* Dat was
  niet in te vullen — de deadline had geen eigen dagdimensie en erfde die van `days_of_week`,
  dus meedoen impliceerde een deadline.

  Op een dag zonder deadline doet het apparaat gewoon mee aan het zonne- en prijsadvies, en
  krijgt het geen urgentie-advies over een tijd die er niet is. Leeg laten betekent elke dag,
  wat het altijd deed — er migreert niets.

- **Apparatuur die op deelvermogen kan draaien** (`can_modulate`, `min_power_w`). Een laadpaal
  werd beoordeeld op zijn maximum, dus bij 2100 W overschot en een paal van 3680 W zweeg hij
  en werd de wasmachine geadviseerd. Op de gewone Nederlandse middag — auto thuis, panelen
  leveren minder dan het laadmaximum — kreeg de klant dus geen advies over precies het
  apparaat waarvoor hij dit systeem kocht.

  **Een wasmachine kan het overschot niet aannemen, een laadpaal wel.** De regel is daarom
  additief: niet-modulerende apparatuur wordt onveranderd op haar volle vermogen beoordeeld.

  `min_power_w` heeft geen standaard en kan die niet hebben: zes ampère is 1380 W op één fase
  en 4140 W op drie. Daardoor is de overstap vanzelf veilig — `can_modulate` staat standaard
  aan voor een laadpaal, en zonder dat minimum verandert er niets.

- **Een besparing per uur** voor apparatuur zonder cyclus. Het advies "laad op wat er over is"
  heeft geen einde, dus er is geen totaal; `energie_per_cyclus × marge` zette een
  overtuigende € 1,20 onder advies over de eerstvolgende twintig minuten zon.

  Het totaal blijft daarom **leeg**, en dat is het juiste antwoord en geen gebrek. Het heeft
  bovendien een tweede werking: `estimated_savings_eur` is waar de drempel `min_savings_eur`
  tegenaan gelegd wordt, en een tarief in dat veld zou tegen een totaal vergeleken worden —
  een paal die € 0,12 per uur oplevert zou achter een drempel van € 0,25 verdwijnen.

### Fixed

- **De zin sprak het bedrag tegen.** Met een leeg totaal las `_surplus_message` "de som kon
  niet gemaakt worden" en ging op zoek naar de ontbrekende term — dus een laadpaal met een
  prima tarief eronder vertelde de installateur de terugleverkosten in te vullen die hij net
  had ingevoerd. Gevonden in de browser, want elke laag eronder klopte met zichzelf.

## Onuitgebracht

### Documentatie

- **SPEC §54: woning 3, het rijtjeshuis met de laadpaal.** Bevindingenronde zonder code.
  Negen bevindingen, waarvan **twee structureel** en allebei op het laadpaalpad — dat nog
  nooit op een echte installatie was gelopen.

- **SPEC §55: voorstel voor een deadline die niet elke dag geldt.** Op papier, vóór er code
  komt, want het raakt het datamodel. Voorlopig akkoord van Sven; nog niet gebouwd.

- **SPEC §56: het ontwerp voor de laadpaal die meebeweegt met de zon.** §54.4 en §54.7 samen,
  want los van elkaar lossen ze niets op. Bevat `ready_days`, een modulatieschakelaar met een
  minimum-laadvermogen, de vervanging van `nominal_power_w <= surplus`, en een tweede soort
  besparingsbedrag — per uur in plaats van per cyclus. **Ontwerp, nog geen code.**

## 0.17.0

De opruimronde van §49.2: dezelfde regel, drie keer, en drie keer een andere reparatie.
SPEC §53.

### Fixed

- **Een onleesbare stille-urentijd wordt niet meer stil vervangen.** Hij viel terug op 22:00
  of 07:00 — een tijd die de bewoner nooit invoerde, die er volkomen normaal uitziet, en die
  hij dus nooit als fout zou herkennen. Dat is slechter dan het lege veld dat het
  gereed-venster overhield: een verkeerde waarde die zich voordoet als een antwoord.

  De waarde blijft nu staan en de melding *"Gebruik een geldige tijd in de vorm uu:mm."*
  landt op het veld. **Zolang de fout er staat gelden de stille uren niet** — dat is bewust:
  de fout is zichtbaar, en deze integratie stuurt geen meldingen, dus het advies staat in een
  paneel en maakt niemand wakker.

  Een *afwezige* waarde neemt nog steeds de default. Alleen een waarde die er staat en niet
  te lezen is, blijft staan.

- **Een onleesbare salderingsdatum wordt geweigerd in plaats van weggegooid.** `1-1-2027` —
  precies zoals een Nederlandse installateur het schrijft — werd `None`, en `None` betekent
  op dit veld niet "onbekend" maar **"deze woning saldeert niet"**. Een typefout verlegde zo
  stilzwijgend de hele besparingsformule, met `success` en een nieuwe revision.

  Nu geweigerd aan de WebSocket-grens met `invalid_format`. Dat kan hier omdat het paneel
  deze fout niet kán maken: zijn datumkiezer levert altijd ISO. Op de laadweg blijft een
  corrupt bestand `None` opleveren, want daar moet er íets uitkomen.

### Overig

- **`scripts/ha_check.py --merge`.** `devices/update` en `sources/update` vervangen de hele
  rij — bewust, want het apparaatformulier wist een veld door het weg te laten — en `--field`
  nodigt uit om één ding te noemen. Die combinatie wiste twee keer op één dag de helft van
  een rij.

  `--merge` haalt de opgeslagen rij op, legt de genoemde velden erover en meldt wat er
  veranderde. Zonder `--merge` waarschuwt het script, ook bij `--dry-run` — juist daar, want
  dat draai je om een aanroep te controleren vóór je hem afvuurt.

## 0.16.0

"Maakt niet uit wanneer hij klaar is" is nu een antwoord in plaats van een gat. SPEC §52.

### Toegevoegd

- **Een schakelaar boven het gereed-venster: *Maakt niet uit wanneer hij klaar is*.** De
  droger die op elk moment mag draaien is volledig beschreven, en kostte toch tien punten
  datakwaliteit — twee lege tijdvelden betekenden tegelijk "ik heb geen eis" en "ik heb dit
  nog niet ingevuld". Alleen het tweede hoort te tellen.

  **Het apparaat blijft volledig adviseerbaar.** Er verandert niets aan het
  zonneoverschot-advies, aan `has_movable_load` of aan de energiescore; er verdwijnt alleen
  een deadline om naartoe te rekenen, en daarmee het urgentie-advies voor dat apparaat — wat
  klopt, want er is geen urgentie.

  Leegte telt nooit als antwoord: een half ingerichte installatie zakt nog steeds. Alleen een
  expliciete keuze vinkt het item af.

- **De twee tijdvelden gaan inactief in plaats van weg** wanneer de schakelaar aanstaat, en
  hun waarden blijven bewaard. Verbergen zou de weg terug achter de schakelaar zetten die
  haar verborg.

- **Het is een bewonersveld.** Hij mag een deadline zetten, dus hij moet ook kunnen zeggen
  dat hij er geen heeft. Dat is het spiegelbeeld van het niet-draaien-venster uit §51, dat
  juist bewust van de installateur is — twee velden in hetzelfde vak, op de tegenovergestelde
  manier beschermd, omdat ze van verschillende mensen zijn.

### Documentatie

- **CLAUDE.md, negende variant: twee plekken die dezelfde vraag anders beantwoorden.** Twee
  keer voorgekomen — `has_time_window` in 0.6.1 en `_deadline_is_reachable` in 0.15.0. Beide
  plekken draaien, beide zijn op zichzelf verdedigbaar, en geen enkele test kan het zien,
  want elke test toetst zijn eigen kant.

## 0.15.0

Een apparaat kan nu uren hebben waarin het helemaal niet mag draaien. SPEC §51.

### Toegevoegd

- **Een niet-draaien-venster per apparaat**, met twee grenzen en de gewone middernachtwikkel:
  *"niet draaien vanaf 23:00, weer toegestaan vanaf 07:00"*. Voor de droger onder de
  kinderkamer, of wat er ook staat waar geluid 's nachts niet kan.

  **Dit is niet hetzelfde als de stille uren, en dat is de hele reden dat het bestaat.** De
  stille uren zijn van de bewoner en gelden voor de woning; ze stellen advies uit. Dit is van
  de installateur, geldt voor dit apparaat, en onderdrukt het. Een bewoner die zijn stille
  uren inkort verliest de bescherming niet — hij kan dit veld niet eens wijzigen.

- **De hele draaitijd telt mee, niet het startmoment.** Een droger van ruim twee uur met een
  verbod vanaf 23:00 wordt ook om 22:00 niet geadviseerd: hij zou om kwart over twaalf nog
  draaien.

- **Een zin wanneer het venster een advies onderdrukt.** Anders is er alleen stilte, en dan
  gaat de bewoner in Mijn voorkeuren zoeken — waar de stille uren staan — en vindt daar niets
  dat het verklaart. De zin wijst naar de installatie en zegt tot wanneer.

  Hij verschijnt pas wanneer er niets anders te adviseren valt: een verklaring mag nooit een
  advies verdringen waar de bewoner iets mee kan.

- **Een melding wanneer het verbod en de deadline elkaar uitsluiten.** Een wasmachine die
  klaar moet zijn tussen 07:00 en 08:00, 90 minuten draait en niet vóór 07:00 mag draaien,
  heeft geen enkele mogelijke starttijd. Zonder melding zou hij nooit advies krijgen en zou
  niemand weten waarom. De melding noemt beide eisen, want welke moet wijken is niet aan ons.

### Overig

- `outside_allowed_window` krijgt zijn eerste lezer. De code stond sinds 0.1.0 gedefinieerd
  en werd nooit uitgezonden.
- `is_within_window` is naar `models.py` verhuisd, waar de rest van de klokrekenkunde staat;
  `validators.py` exporteert de naam opnieuw, dus elke aanroeper vindt hem waar hij stond.

## 0.14.0

De reparatieronde van SPEC §49, in de volgorde die Sven vaststelde. SPEC §50.

### Fixed

- **De wasmachine van een normale woning kreeg een onterechte fout.** Een gereed-venster van
  07:00 tot 08:00 met een cyclus van 90 minuten meldde *"Het apparaat past niet binnen het
  opgegeven gereed-venster"*, met severity `error` op de duur — het enige getal waar de
  bewoner zeker van is.

  Beide grenzen van het gereed-venster zijn **eindtijden**; het apparaat draait over
  `[ready_from − duur, ready_before]` en er hoeft niets ergens in te passen. Die toets kwam
  ongewijzigd mee uit `earliest_start`/`latest_finish`, waar het paar wél een draaivenster
  begrensde, en kon onder de huidige betekenis nooit terecht aanslaan. Drie tests hielden de
  oude betekenis vast en zijn vervangen.

  Ervoor in de plaats komt de enige duur-versus-klok-regel die wel geldt: een cyclus van 24
  uur of langer heeft geen starttijd op een 24-uursklok.

- **Een tijd die niet te lezen is, wordt niet meer stil weggegooid.** `0730` in het uurvak —
  wat je typt als je "half acht" snel invult, en wat de HTML-control toelaat — werd `None`,
  ononderscheidbaar van "niet ingevuld". De opslag meldde succes en het veld was leeg bij
  terugkomst.

  De waarde blijft nu staan en de melding *"Gebruik een geldige tijd in de vorm uu:mm."* —
  die al bestond en nooit kon afgaan — landt op het veld waar hij over gaat.

- **Eén veld bijwerken wist niet meer de rest van het woningprofiel.** `home/update` en
  `preferences/update` voegen samen: een afwezige sleutel laat het veld met rust, een
  expliciete `null` wist het. Eén bedrag invullen zette hiervoor twaalf andere waarden terug
  op hun default, met `success` en een nieuwe revision.

- **Een revisieconflict gooit geen ingevuld formulier meer weg.** De revision telt de hele
  configuratie, dus een conflict betekent meestal dat er ergens ánders iets veranderde. Alle
  vier de formulieren behandelden het als "jouw rij is verouderd" en begonnen opnieuw; een
  compleet ingevuld apparaat ging zo verloren omdat er op een tweede scherm een bron
  bijkwam.

  De invoer blijft nu staan, de nieuwe revision wordt overgenomen, en er is een eigen zin
  voor elk van de drie situaties: er veranderde iets anders, deze rij veranderde ook, of deze
  rij is verwijderd.

- **Vast contract met een prijsbron op marktbasis was een doodlopende weg.** Zonder ingevuld
  tarief kwam er geen prijs, geen melding, en geen veld om het op te lossen: de
  energiebelasting, de opslag en de btw werden op contractsoort gefilterd. Ze volgen nu de
  marktprijs — ze staan er zodra er een marktprijs is om om te rekenen, en de validatie
  meldt op dezelfde voorwaarde.

## 0.13.1

De voorrangsregel van 0.13.0 omgedraaid waar zij verkeerd was.

### Fixed

- **Bij een vast contract wint het ingevulde tarief van een gekoppelde prijsbron.** 0.13.0
  liet een meting overal winnen, en toonde € 0,306 uit een testbron aan een woning die
  € 0,24171 betaalt. Een vast tarief is een *afspraak*, geen meting; een bron kan om
  allerlei redenen gekoppeld zijn en geen daarvan is wat de klant betaalt.

  Bij een dynamisch contract blijft de bron leidend — daar verandert de prijs werkelijk per
  uur. Staat het tariefveld bij een vast contract leeg, dan vult de bron alsnog aan.

- **De rij zegt nu wat een gekoppelde bron hier wel en niet doet.** Een bron die compleet
  is, gelezen wordt en niets bepaalt, wekt anders de indruk dat hij meetelt (SPEC §48.4).

  De zin draagt beide helften: *"De gekoppelde prijsbron bepaalt dit bedrag niet, maar neemt
  het over zodra dit veld leeg is of het contract dynamisch wordt."* Alleen de eerste helft
  was te absoluut — dan leest een installateur dat de rij dood gewicht is en verwijdert hij
  haar, waarna de volgende contractwijziging zonder prijs aankomt.

### Documentatie

- **SPEC §48.5:** de terugleverbron staat hier los van. Leveren en terugleveren zijn losse
  contractdimensies — een vast leveringstarief sluit een variàbele terugleververgoeding niet
  uit, dus die bron blijft leidend ongeacht de contractsoort.

- **CLAUDE.md:** Sven tagt pas nadat de merge gemeld is. De release-workflow vergelijkt de
  tag met de versienummers, niet of die commit op `main` staat.

- **SPEC §49: woning 2, tweede helft.** Bevindingenronde zonder code — apparaten, het
  gereed-venster en de bewonersweergave, ingericht met SPEC.md dicht. Zes bevindingen,
  waarvan twee stil gegevensverlies en één een onterechte foutmelding op precies de
  configuratie waarvoor het gereed-venster gebouwd is. Plus wat goed ging, en de
  voorgestelde volgorde van afhandelen.

- **`_validate_price_components`:** de docstring beweerde dat een vast contract
  `current_price_eur_kwh` nooit raadpleegt. Dat is sinds 0.13.0 onwaar; het gat eronder
  (vast contract, marktbasis-bron, leeg tariefveld) is erin opgeschreven in plaats van
  stil gedicht.

## 0.13.0

Een vast contract heeft ook een prijs. SPEC §48.

### Fixed

- **Het Overzicht zei "Niet van toepassing bij een vast contract"** terwijl de klant zowel
  een ingevuld all-in tarief had als een werkende prijsbron. De rij keek naar de
  contractsoort in plaats van naar wat er beschikbaar was.

  **Nu één predicaat, `import_price_now`, en het stond op vier plekken los van elkaar**: de
  marge in de calculator, de besparing in de advisor, het checklistitem in de datakwaliteit
  en de rij in het paneel. Een meting wint van een ingetypt tarief; het ingevulde tarief
  vult aan bij een vast contract; anders zegt de rij wat het zou beantwoorden.

- **De rij zegt er nu bij waar de prijs vandaan komt.** Een gemeten prijs houdt zichzelf
  actueel, een ingetypt tarief overleeft een contractwijziging zonder iets te zeggen — en
  alleen de klant weet dat dat gebeurd is.

- **Het datakwaliteitsitem vraagt niet langer "een prijs op de manier die dit contract
  nodig heeft"**, maar of er een prijs is. Een woning met een prijsbron miste dat item
  omdat zij het tariefveld leeg liet.

### Changed

- **Tonen en adviseren lopen niet meer door elkaar** (SPEC §48.2). Bij een vast contract
  wordt de prijs gétoond en er wordt niet over geádviseerd — er is immers geen goedkoop
  moment om naartoe te schuiven. De contractsoort zegt iets over *variatie*, niet over of
  er een prijs bestaat.

- **De zonprognose verloopt niet meer** (SPEC §47.4, besluit van Sven): de prognose van
  vanochtend is 's avonds nog steeds die van vandaag. De voorwaarde die erbij hoort: wie
  hem toont, toont hoe oud hij is. In de mapping staat daarom `None` en geen groot getal
  dat op een grens lijkt.

## 0.12.0

Een installateur kwam bij een vreemde woning niet voorbij de netmeter. SPEC §47.

### Fixed

- **Bronnen die per uur of alleen bij verandering rapporteren werden geweigerd.** Één
  constante van vijftien minuten gold voor alles: een dynamische prijs die per uur
  publiceert was drie kwartier van elk uur "onleesbaar", en een terugleversensor die
  's nachts terecht 0 blijft maakte de hele netmeter onbruikbaar.

  **Nu drie vensters, elk met zijn reden** (SPEC §47.1): meting 15 minuten, prijs 90,
  en rustende waarden 240. Een nieuw brontype moet er expliciet één kiezen — een
  guard-test faalt zodra dat vergeten wordt, zodat dit niet terugzakt naar één constante
  met uitzonderingen.

- **De twee helften van een gescheiden netmeter worden apart gewogen** (SPEC §47.2). De
  exporthelft krijgt het rustende venster; wordt hij daarna nog geweigerd, dan noemt de
  melding de exportentiteit in plaats van de importentiteit die het goed doet.

  Dit was de zwaarste van de twee: de modus *gescheiden afname en teruglevering* — wat een
  P1-lezer standaard oplevert — leek volledig dood, terwijl de bronrij "Compleet" zei.

### Waarom geen enkele test dit vond

De test die dit gebied dekte was góéd, en toetste het ontwerp precies. De fout zat in de
aanname erónder: *elke gekoppelde bron rapporteert minstens elk kwartier opnieuw*. Waar
voor een P1-lezer, onwaar voor MQTT, Zigbee, templatesensoren en een uurlijkse prijs. Een
unittest kan zo'n aanname niet weerleggen — hij schrijft de state een moment voordat hij
hem leest. Vastgelegd als achtste variant in CLAUDE.md.

### Documentatie

- **SPEC §46:** een status zegt wat er uitkomt, niet of het formulier vol is — en wat de
  status bepaalt, levert ook de uitleg. Breed vastgelegd, ook voor rijen en schermen die
  er nog niet zijn.

## Nog niet uitgebracht

### Testgereedschap (raakt de integratie niet)

- **De testomgeving loopt weer gelijk met de klant.** Python 3.14 en Home Assistant
  **2026.8.1** in de testcontainer en in CI, in plaats van 3.13 met HA 2026.2.3. Dat
  verschil was vijf maanden, en het bestond omdat het testharnas vanaf 0.13.317 Python
  3.14 vereist en HA 2026.8 zelf ≥ 3.14.2.

  Het besluit van 5 augustus was om te wachten tot 2026.8 stabiel zou zijn in plaats van
  tegen een bèta te testen. Die kwam op 5 augustus (2026.8.0) en 7 augustus (2026.8.1).

  **De overstap kostte geen enkele codewijziging**: 646 tests groen op de eerste poging,
  en de 131 waarschuwingen komen allemaal uit Home Assistant zelf.

  De ondergrens blijft HA 2025.6 (`hacs.json`); die bewaken we door de API-tabel na te
  lopen, niet met deze workflow.

- **Eén ding mocht niet mee, en dat bleek meteen.** Ruff's `target-version` op py314
  zetten liet de formatter `except (ValueError, HomeAssistantError):` herschrijven naar de
  haakloze vorm van PEP 758 — syntax die Python 3.13 niet eens kan parsen. De integratie
  wordt geladen door de Python van de klant, en de ondersteunde ondergrens is HA 2025.6 op
  3.13. `target-version` en `python_version` blijven daarom op 3.13, met de reden ernaast.

## 0.11.1

Een tegel die zichzelf tegensprak, en een map voor het logo.

### Fixed

- **De aandachtstegel stond rood naast "Geen actie nodig".** De vier redenen waren niet het
  probleem — `neutral_energy_situation` stond er nooit tussen. De entiteit las een tweede
  bron: elke onleesbare meting in de metrics zette hem aan, terwijl de tekst uit het
  hoofdadvies bleef komen. Kleur en zin kwamen dus uit twee verschillende objecten en
  konden elkaar tegenspreken.

  Daar kwam bij dat "onleesbaar" ook het doodgewone geval dekt waarin een entiteit even
  `unavailable` is — bij een herstart, een integratie die herlaadt, een omvormer die
  uitvalt. Niet zeldzaam en niets aan te doen: precies wat de knop betekenisloos maakt.

  **De regel is nu dat wat de tegel aanzet ook de zin levert**, en alleen het advies doet
  dat. Drie redenen, en de tegenspraak is niet opgelost maar onmogelijk (SPEC §45.6).

  Wat het kost, eerlijk gezegd: een bron die door geen checklistitem gevraagd wordt — een
  groepenkastmeter, een thuisbatterij — kan onleesbaar zijn zonder dat de tegel rood wordt.
  Dat blijft zichtbaar op de bronrij, in de datakwaliteit en in het logboek.

### Added

- **`custom_components/domotiapp_energy/brand/`** voor het logo, met een README erin die
  precies zegt welke bestanden en formaten Home Assistant verwacht. Sinds HA 2026.3 draagt
  een custom integration zijn eigen merkafbeeldingen; `home-assistant/brands` accepteert
  daar geen pull requests meer voor. Geverifieerd tegen 2026.7.4.

### Documentatie

- **SPEC §39.9:** bij 320 CSS-pixels breekt de tabbalk naar drie regels. Gemeten, en op
  besluit van Sven zo gelaten — de tightening is op 358px afgestemd en zijn klanten hebben
  geen telefoons uit 2016.

## Nog niet uitgebracht

### Testgereedschap (raakt de integratie niet)

- **Twee Playwright-routes naast de jsdom-laag.** `npm run test:layout` draait het paneel
  in een echte browser met een gestubde Home Assistant en staat in CI; het beantwoordt wat
  jsdom niet kan beslissen: de cascade, containerqueries, schermbreedtes en de meetkunde
  die de safe areas opleveren. `.\scripts\browsertest.ps1` draait tegen de draaiende
  Home Assistant met echte kliks, en is de enige laag die `ha-form` rendert.

- **Wat elke laag niet kan bewijzen staat in CLAUDE.md**, als tabel. De belangrijkste
  regel: een groene CI zegt niets over de vraag of een control een klik accepteert. Dat is
  het gat waar de dagenselector doorheen viel, en het gaat niet dicht met meer tests in
  een laag die geen controls rendert.

- **Meteen iets gevonden.** Op HA 2026.7 rendert dezelfde zevendaagse multiselector als
  een rij `ha-input-chip`s — de derde vorm na de combobox en de checkboxes, zonder dat er
  iets aan onze code veranderde. En het tekstveld is geen `ha-textfield` meer maar
  `ha-input`/`wa-input`.

- **Bekende grens:** bij 320 CSS-pixels breekt de tabbalk nog naar drie regels. De
  tightening is op 358px afgestemd (SPEC §39); de test staat daarom op 360 en dit is
  gemeten, geen aanname.

## 0.11.0

Eén tegel op je eigen dashboard, in plaats van twee stukken YAML per woning. SPEC §45.

### Added

- **Een achtste entiteit: `binary_sensor.domotiapp_energy_attention`.** Aan met
  `device_class: problem` zodra er iets is waar een mens nu iets aan kan doen, uit wanneer
  alles leesbaar is en er niets aan de hand is. Drie attributen erbij — `advice_title`,
  `message` en `reason_code` — zodat een `tile`-kaart met `state_content: advice_title` de
  reden op de tweede regel zet in plaats van "Probleem".

  Daarmee is een knop op een eigen dashboard **één tegel om te plakken**. De vorige README
  beschreef hetzelfde met een `template`-sensor in `configuration.yaml`, en dat is precies de
  plek waar drift ontstaat: bij twintig woningen staan er twintig kopieën van onze definitie
  buiten ons versiebeheer.

- **Vier redenen, vastgelegd in SPEC §45.2 met de reden erbij.** Ontbrekende gegevens, een
  onleesbare bron, en de aansluiting tegen zijn grens in beide richtingen. Een hoge prijs
  hoort er bewust niet bij: dat is de markt twee keer per dag, en een tegel die elke avond
  rood staat wordt een tegel die niemand nog bekijkt. Elke code die erbij komt, maakt de knop
  minder waard — daarom staat de vraag die een kandidaat moet doorstaan nu in de spec.

  De onleesbare bron staat er los in omdat `invalid_entity_state` **nooit** een adviesreden
  wordt: hij komt uit de validators en landt in de metrics. Een tegel die alleen naar het
  advies kijkt, blijft grijs terwijl een sensor dood is — en dat is nu juist de storing
  waarvoor een installateur gebeld wordt.

### Documentatie

- **README: het knopblok is nu één tegel**, met de attributentabel erbij en een waarschuwing
  over kiosk-modus: de tegel navigeert, en de weg terug is de zijbalk. Staat die uit, dan
  komt het wandtablet niet meer van het paneel af.

- **SPEC §19 is bijgewerkt** — de tabel telde nog zes entiteiten terwijl er zeven waren;
  home consumption (0.5.0) ontbrak en attention is nu toegevoegd.

- **SPEC §44: de sturingsindeling.** Alleen papier, geen code. Waar de knoppen komen te staan
  wanneer de aansturingsrelease er is: de toestemming blijft op Apparaten, de handeling staat
  bij het advies dat erom vraagt, en er komt één sectie `Nu aangestuurd` op het Overzicht met
  één stopknop per apparaat.

  Twee dingen die deze sectie oplost en die anders bij het bouwen pas opvallen: wat "stoppen"
  precies terugdraait en wat er direct daarna gebeurt (anders start hetzelfde apparaat binnen
  één cyclus opnieuw), en dat de ratel uit §43.3 geen weergavevraag meer is zodra er
  aangestuurd wordt — dan schakelt hardware mee met meetruis.

## 0.10.0

Fase 2 van het gereed-venster: het urgentie-advies. SPEC §43.

### Added

- **DomotiApp Energy zegt nu wanneer je moet starten om het te halen.** Heeft een apparaat een
  deadline en een duur, dan verschijnt een half uur voor de uiterste starttijd: *"Start
  Vaatwasser nu als hij om 07:00 klaar moet zijn."* Het staat op rang 3 en wint daarmee van
  zon en prijs — een deadline is hard, wachten op zon is een optimalisatie.

  Geen prognose nodig: je hoeft de toekomst niet te kennen om te weten dat later starten het
  onhaalbaar maakt.

- **Eén apparaat krijgt één advies.** Een vaatwasser binnen zijn urgentievenster terwijl de
  zon schijnt leverde twee items over dezelfde machine, allebei met hetzelfde verzoek. De
  hoogste rang blijft over. Advies over de woning — piek, prijs, veiligheid — wordt niet
  samengevoegd; twee daarvan kunnen tegelijk waar zijn.

### Wat dit advies bewust nog niet doet

Het weet niet of er werk te doen is: de vlag "de machine is vol" is fase 3. Daarom is de zin
**voorwaardelijk** en de toon informatief in plaats van een waarschuwing. Een waarschuwing die
de helft van de tijd over een lege machine gaat, leert mensen waarschuwingen negeren. Met de
vlag erbij wordt het *"Start Vaatwasser nu om 07:00 te halen"* en een echte waarschuwing.

Het zwijgt ook zodra de deadline niet meer haalbaar is — een half uur eerder dan SPEC §32.3
voorschreef. Om 04:30 nog zeggen dat hij om 07:00 klaar is, is onwaar voor een cyclus van drie
uur.

## 0.9.0

Drie dingen die je vandaag op je scherm zag en die er niet hoorden. SPEC §42.

### Changed

- **Stille uren stellen uit in plaats van te zwijgen.** Een lawaaiig apparaat verdween tot nu
  toe uit het advies, en de bewoner zag niets — niet te onderscheiden van "er is geen
  overschot". Nu staat er: *"Er is momenteel zonneoverschot beschikbaar. Vaatwasser maakt
  geluid en het zijn stille uren tot 07:00. Wacht daarmee tot na 07:00, of pas de stille uren
  aan bij Mijn voorkeuren."* Een stil apparaat wint nog steeds: het uitstel komt pas als er
  niets anders is.

  Daarmee stuurt `quiet_hours_active` eindelijk iets uit. Er staat geen bedrag onder — dat zou
  lezen als een argument om het uitstel te negeren.

- **De hulptekst bij de stille uren beschrijft het nieuwe gedrag.** Hij zei "krijgen lawaaiige
  apparaten geen advies", en dat was het oude.

### Fixed

- **Het hoofdadvies stond twee keer op het Overzicht** wanneer het zelf een waarschuwing was —
  eenmaal als advies, eenmaal in de lijst eronder. Het Energiecoach-tabblad deed dit al goed.
  En als het hoofdadvies de enige waarschuwing is, staat er nu niets in plaats van *"geen
  waarschuwingen"*: die zin zou de regel erboven tegenspreken.

- **De tabbalk paste niet op een telefoon.** Zes tabbladen wikkelden naar drie regels, een
  derde van het scherm. Twee nu, met de iconen erbij: 87px in plaats van ongeveer 130.

### Removed

- `allow_advice_during_quiet_hours`. In de uitstellende vorm is er niets meer om uit te
  schakelen; wie het niet eens is met het venster, verzet het venster.

## 0.8.1

### Fixed

- **De schermvullende dialoog schoof op een iPhone onder de statusbalk.** De titel viel achter
  de klok en het kruisje achter het batterijpictogram — en een schermvullende dialoog heeft
  geen achtergrond meer om weg te tikken en een telefoon geen Escape, dus dat kruisje was de
  enige uitweg. De stylesheet gebruikte `env(safe-area-inset-bottom)` vier keer en de andere
  drie zijden nul keer. Alle vier de kanten worden nu gerespecteerd, ook links en rechts voor
  de uitsparing in landschap, en het paneel zelf net zo goed.

### Added

- **`scripts/extract_texts.py` schrijft `TEKSTEN.md`.** Het handgemaakte document was drie
  ronden verouderd, en een document dat stil veroudert wordt gelezen alsof het klopt.
  `tests/test_texts.py` faalt zolang het achterloopt. De CSS van het paneel is eruit
  gefilterd en Engelse regels staan apart, zodat ze per stuk beoordeeld kunnen worden.

### Waarom dit niet meer op één telefoon hoeft

Een `env()`-waarde is niet te zetten — niet vanuit CSS, niet vanuit script — dus wat je er
niet in kunt schrijven, kun je ook niet toetsen. Elke inset loopt nu door een custom property,
en daarmee wordt "respecteert de dialoog de statusbalk" een controle die elke browser bij elke
vensterbreedte kan doen. Dat vond meteen een tweede fout in de reparatie zelf: padding valt
buiten `height: 100%`, dus zonder `box-sizing: border-box` werd het blad hoger dan het scherm.

## 0.8.0

De visuele ronde: verfijnen, geen herontwerp. SPEC §39.

### Changed

- **Compacter én groter.** De lucht tussen rijen komt ongeveer een derde in en de getallen
  gaan omhoog: een meetregel leest nu 1,2rem in plaats van 1,05, een kopgetal 3,4rem in
  plaats van 3. De kaartkoppen gaan juist iets omlaag — de hiërarchie op een kaart hoort van
  het getal uit te gaan, niet van de titel. Drie kaarten passen weer op één scherm.

- **De apparaatdialoog opent nog twee secties in plaats van drie.** *Apparaat* en *Verbruik*
  zijn de hele eerste doorloop; de datakwaliteit vraagt niets daarbuiten. De volgorde volgt
  wat een installateur als eerste invult, *Koppelingen* staat nu vóór *Aansturing*, en
  *Notities* is een eigen sectie zoals bij Energiebronnen.

- **Een rij bestaat op grond van wat de woning heeft, niet van wat er nu gemeten wordt.** Een
  woning zonder panelen zag drie regels over zonne-apparatuur, alle drie leeg en geen ervan
  op te lossen. Die verdwijnen, net als *Apparaten die nu draaien* wanneer geen enkel
  apparaat een vermogenssensor koppelt. Wat blijft is de andere helft van de regel: een rij
  die deze woning wél heeft en nu niets levert, blijft staan — dat is een storing die gezien
  moet worden, geen ruis.

- **Op een telefoon delen de knoppen van een rij de volle breedte.** *Bewerken* en
  *Verwijderen* stonden als twee etiketgrote doelen tegen de rechterrand; nu heeft een duim
  een halve regel.

## 0.7.2

Het staartje van de opruimronde, en het legde een regel bloot die er nog niet stond.

### Fixed

- **Een vaatwasser op "alleen meekijken" liet niet meer zien dat hij geen advies krijgt.**
  0.7.1 haalde het bedieningsniveau uit de rij omdat *"Alleen adviseren"* loog bij een
  apparaat dat nooit advies krijgt — en raakte daarmee ook het geval waarin het niveau juist
  de réden is. Met een gekoppelde vermogenssensor las de rij *"Vaatwasser · Keuken ·
  2.000 W"* en *"Compleet."*, met de eigen instructie van de bewoner nergens. Het niveau
  staat er weer bij zodra het de reden is.

- **Het bedieningsniveau bij een thuisbatterij is een keuze zonder gevolg.** Geen van de vier
  niveaus verandert daar iets: een batterij wordt nooit geadviseerd, dus valt er niets uit of
  aan te zetten. Het veld verdwijnt daar, en *verplaatsbaar in de tijd* met hem — die staat
  in dezelfde klasse en doet er evenmin iets.

### Changed

- **Het bedieningsniveau zegt nu wat de keuze voor dít apparaat doet.** Drie hele zinnen in
  plaats van één. Bij een apparaat dat nog niet verplaatsbaar is: *"Dit apparaat krijgt geen
  advies zolang het niet verplaatsbaar is. 'Alleen monitoren' legt vast dat dat zo moet
  blijven, ook als dat later verandert."* En op *alleen monitoren* staat de weg terug erbij.

### Waarom het veld niet zomaar weg kon

**Een veld dat een toestand kan veranderen mag nooit door die toestand verborgen worden.**
`monitor_only` is niet een gevolg van "dit apparaat krijgt geen advies", het is de oorzaak.
Verbergen omdat er geen advies komt, sluit de bewoner op in zijn eigen keuze — en de vijf
andere velden die hij bezit zijn in die toestand al weg, dus hij houdt een scherm over waarin
hij niets mag aanraken. Staat nu als eigen soort in SPEC §38.3.

## 0.7.1

Eén thema: **het product vroeg of bood iets dat niets deed.** Daarna is die categorie leeg.

### Changed

- **De twee prognosebronnen staan niet meer in de keuzelijst.** *Prijsverwachting* en
  *Zonverwachting* waren een volledige keuze, met een hulptekst die uitnodigde een entiteit
  te koppelen, en de motor las ze nergens. Een bestaande rij blijft gewoon werken en zegt
  nu waar zij aan toe is: *"Dit brontype is nog niet in gebruik. DomotiApp Energy rekent
  alleen met het huidige moment en leest geen verwachtingen. De koppeling blijft bewaard,
  maar er wordt op dit moment niets mee gedaan."*

- **Een apparaat waar nooit advies over komt, krijgt de adviesvragen niet meer.**
  Prioriteit, "maakt geluid" en het tijdvenster ordenen, dempen en timen advies; zonder
  advies vragen ze om een keuze die niemand leest. Ze komen terug zodra je het apparaat wél
  verplaatsbaar maakt. Bij een thuisbatterij viel dat op: verplaatsbaar van nature,
  geadviseerd nooit, en toch gevraagd op welke dagen hij mocht draaien.

- **Een slimme stekker wordt niet meer om zijn eigen vermogen gevraagd.** Bij *Overig,
  alleen meten* verdwijnen vermogen, energie per cyclus en duur: die vragen gaan over het
  apparaat áchter de stekker, en dat is deze rij niet. Bij een thuisbatterij verdwijnen de
  twee cyclusvelden; het vermogen blijft, want dat beschrijft wel iets.

- **De regel onder een alleen-gemeten apparaat noemt geen adviesbegrippen meer.** Er stond
  *"Overig, alleen meten · Normaal · Alleen adviseren"* — een prioriteit die niets ordent,
  naast een bedieningsniveau dat advies belooft aan een apparaat dat er geen krijgt. Nu:
  type, locatie en vermogen.

### Fixed

- **Een thuisbatterij werd om een energie per cyclus gevraagd.** Een batterij heeft geen
  cyclus: niemand start hem, hij volgt het overschot vanzelf. Hetzelfde geval als de
  tabletlader in 0.6.1, één apparaattype verderop — en het had een eigen as nodig, want een
  batterij ís verplaatsbaar, dus die vlag kon het niet dragen.

- **Een verborgen veld werd gewist zodra een buurveld veranderde.** Een sectie gaf alle
  velden terug die zij kent, ook de niet-getoonde, en las daar `undefined` voor. Een
  vaatwasser die je bewust op "maakt geen geluid" had gezet, verloor dat zodra je hem op
  "alleen meekijken" zette en weer terug.

- **De waarschuwing over weg te gooien gegevens noemde ook standaardwaarden.** Een verse
  slimme stekker meldde dat zijn prioriteit en geluidsvlag verdwenen — twee waarden die het
  formulier zelf had ingevuld en die de backend precies zo teruggeeft.

### Removed

- `validators.has_errors`. Bestond, werd getest, en werd door niets gebruikt: niet door de
  motor, niet door de WebSocket-API, niet door het paneel (SPEC §37.2b). De assertie die
  hem leesbaar maakte staat nu in de testlaag, waar hij altijd al thuishoorde.

## 0.7.0

### Fixed

- **De score beloonde het negeren van het advies.** Ligt de terugleververgoeding hoger dan
  de importprijs, dan raadt de coach aan te wáchten met je zonneoverschot — en ging de
  zonnebenutting omhoog zodra je dat advies naast je neerlegde. De as vervalt nu zolang die
  marge negatief is. Niet omgedraaid: omgedraaid zou hij "verbruik minder" gaan meten, en
  dat is de zuinigheidsmeter die de score nooit heeft willen zijn.

- **De coach kon dat alleen zeggen over een apparaat.** De zin *"wachten is voordeliger"*
  hing aan een apparaat met een energie per cyclus, dus juist een woning met panelen en
  geen zo'n apparaat hoorde het nooit — terwijl dat de woning is waarvan de zonne-as toch
  al wegvalt. De marge is nu een gegeven van de woning, dat de score, de tegel en het
  advies alle drie lezen.

- **De waarschuwing bij hoge teruglevering beloofde voordeel dat er niet was.** Bij een
  negatieve marge zegt zij nu dat extra verbruik de belasting verlaagt én dat het je geld
  kost. Het argument eronder blijft de zekering; die trekt zich van tarieven niets aan.

### Added

- **Zelfbenutting staat op het Overzicht, ook als er geen cijfer is.** Welk deel van je
  opwek je zelf gebruikt is een meting, geen oordeel: hij staat er zodra je netmeter en je
  omvormer uitleesbaar zijn. Een woning die 4.654 W opwekt en 1.635 W zelf gebruikt las
  eerst niets en leest nu 35%.

- **De tegel zegt ook bij een cijfer wat er niet meetelde.** Negen zinnen, één per reden.
  Zonder dat las je 88 zonder te weten dat je zonneoverschot buiten beschouwing bleef.

### Changed

- **Het thuisverbruik is het kopgetal van het Overzicht geworden**, en de energiescore
  staat ernaast. De score mag met opzet afwezig zijn, en dan hoort de grootste plek op het
  scherm niet van hem te zijn. Het thuisverbruik verhuist daarmee uit `Actuele situatie`;
  het staat er niet twee keer.

## 0.6.1

### Fixed

- **An appliance that is only measured was told its energy per cycle was missing.** A
  tablet charger on a smart plug, added as `generic_monitor` — a type whose whole meaning
  is that there is no cycle. Both appliance items on the checklist now apply only to an
  appliance the coach can advise about, so they leave the numerator *and* the denominator
  and the score goes **up** rather than down. The same held for a `heat_pump`.

- **"Alleen meekijken" did nothing at all.** `control_mode = monitor_only` is the
  resident's own off switch (SPEC.md §33) and the advisor never read it: a dishwasher he
  had switched off was still advised on. It now stops the advice, and it stops the
  checklist asking for a time window for that appliance — the fifth case of a requirement
  that does not apply, found by auditing all six items rather than by a customer.

- **The asterisk in the appliance form follows the same rule.** No field is marked
  required on an appliance that will never be advised about.

### Changed

- **An appliance that only measures says what it still needs.** *"Nog geen
  vermogenssensor gekoppeld — dit apparaat wordt alleen gemeten, en er valt nu niets te
  meten."* A plain line, with no weight in the data quality: the resident's number does
  not move.

## 0.6.0

### Added

- **`power_entity` finally does something.** It was asked of the installer on every
  appliance form, stored, and watched by the coordinator — so filling it in made the
  integration recalculate more often and changed nothing else. Each appliance that links
  one now shows its live power on Apparaten, and the Overzicht carries a count of how many
  are running. SPEC.md §37.

  An appliance without a link gets no line at all: not "onbekend", not "0 W". The unit
  comes from the entity and only `W` and `kW` are accepted — a kilowatt read as a watt is
  off by a thousand.

### Fixed

- **The reader sat in the one method the coordinator never calls.** `read_device_power`
  hung off `Calculator.calculate()`, and the coordinator uses `build_snapshot` and
  `derive_metrics` separately because the hysteresis latch sits between them. Every test
  used `calculate()`, so 588 of them passed while the panel showed nothing at all. Found
  by driving the running instance.

  The power is now a reading in the snapshot, where the other readings are.

### Known limitations

- **Five more device links still ask for a binding and read nothing**: `status_entity`,
  `energy_entity`, `remaining_time_entity`, `temperature_entity` and
  `battery_level_entity`. They are watched by the coordinator, so linking one causes
  recalculations that do nothing with the value. Listed in SPEC.md §37.2 with the rest of
  the audit.

- **The `price_forecast` and `solar_forecast` source types are offered and never read.**
  Not a field you can skip but a whole source type in the list, with helper text inviting
  you to link an entity. Forecasting is out of scope (§28); the choice should not have
  been on the menu.

## 0.5.0

### Added

- **Thuisverbruik, the first figure a resident looks for, and the one that was missing.**
  Grid power is a *net* figure: a home exporting 2400 W while producing 3000 is using 600,
  and nothing on screen said so. It now sits at the top of Actuele situatie, above the grid
  power — which is a consequence of consumption minus production and had been standing
  above its own causes. SPEC.md §36.

  Derived from `netvermogen + zonneproductie − batterijvermogen`, which for the common
  installation (P1 meter and inverter) is the first two terms. A measured
  `general_consumption` source wins from the derivation.

- **`sensor.domotiapp_energy_home_consumption`**, a seventh entity. The six existing ids
  are untouched, so no dashboard and no statistics series breaks. English and fixed like
  the rest, guarded in `en` and `nl`.

### Changed

- **The unreadable-battery sentence now covers both figures it touches.** The same blind
  spot affects the solar surplus and the home consumption, and two near-identical warnings
  on one card is worse than one that names both.

### Known limitations

- **A configured source that cannot be read withholds the figure rather than guessing.**
  Panels the engine cannot read mean the consumption is unknown, and the panel says which
  source to check. A home *without* panels is a different case: production is a true zero
  there and the figure appears normally.

- **An unreadable home battery withholds it too, unlike the solar surplus**, which keeps
  its number with a caveat. Deliberate: a charging battery shifts the surplus, but is
  attributed to the household in full here — 3.5 kW on screen where the house uses 500 W.
  The reasoning is in SPEC.md §36.3; do not level the two without reading it.

## 0.4.2

### Fixed

- **The tile claimed the sun was shining at nine in the evening.** With the panels at
  0 W it said *"Er is nu opwek, maar geen apparaat of batterij die verbruik kan
  verplaatsen"*. The condition behind that sentence asked whether a solar **row** was
  configured, not whether it was producing anything — the difference between "not
  applicable" and "happens to be zero" that SPEC.md §35.1 draws everywhere else.

  The selector now receives the snapshot and shares `_production_now` with the solar
  component, so the sentence and the measurement cannot mean different things.

- **The mirror of the same fault.** A dynamic-tariff home in the sun with nothing movable
  fell through to a sentence saying its panels were producing nothing — and lost the one
  useful thing it could have been told.

### Changed

- **One catch-all sentence became four.** *"Er is nu geen opwek om zelf te gebruiken en
  geen duur moment om te vermijden"* asserted two measurements it could not both
  guarantee: it offered expensive hours to a home on a fixed tariff, and mentioned panels
  to a home that has none. There are now separate sentences for panels idle on a dynamic
  tariff, panels idle on a fixed tariff, a cheap hour without panels, and price thresholds
  that were never filled in.

  Each is written out in full and selected by a situation. Composing one sentence from
  interchangeable clauses would mean the sentence a customer reads exists nowhere in the
  source, and nobody could review it.

- **"Er is geen eigen opwek" is now "er zijn geen zonnepanelen"** in the fixed-tariff
  sentence. The same ambiguity between a configuration and a measurement, in the wording
  this time.

- **Unset price thresholds get their own sentence and a warning tone.** A dynamic home
  whose thresholds are empty cannot be told the hour is cheap, because nothing knows that.
  It is a shortcoming somebody can close, and it now says so.

## 0.4.1

Two removals from the Overzicht, and one defect that came to light behind the second.

### Fixed

- **The coach advised using a solar surplus it knew might not exist.** When a home
  battery is configured whose power cannot be read, a charging battery consumes exactly
  the surplus shown on screen. The advice fired anyway — "start the dishwasher now", with
  a euro amount underneath — carrying the label "betrouwbaarheid: laag", which suppressed
  nothing and which no resident can act on.

  Surplus advice is now withheld entirely in that situation, and the panel says what is
  wrong instead: *"Het vermogen van je thuisbatterij kan niet uitgelezen worden… Koppel de
  vermogenssensor van de batterij om dit op te lossen."* The same sentence answers "welke
  gegevens ontbreken nog?" in the coach.

### Removed

- **The confidence label, everywhere a customer could see it.** The row on the Overzicht,
  the row in the Energiecoach, the "betrouwbaarheid gemiddeld" suffix behind each further
  advice, the trailing sentence in the coach's answers, and the `show_confidence`
  preference that switched them.

  The three levels conflated two different things. `high` versus `medium` said which route
  the engine took to a number that was correct either way — our business, not the
  customer's — while reading as doubt about his own data. `low` was never a shade of
  confidence at all but a blind spot, and it is now a sentence naming its cause and its
  fix. The engine keeps all three levels: the advisor still caps a charger's advice at
  medium, and the new suppression rests on them.

- **The Configuratie card at the bottom of the Overzicht.** The home name and the row
  counts restate two other tabs, are not a reading of this moment, and cost a screenful on
  a phone. The one useful line — "er zijn nog geen energiebronnen gekoppeld" — moved up to
  Actuele situatie, next to the empty readings it explains.

## 0.4.0

The energy score measures one thing now: how much of what this home *could* use well, it
actually used. Full redesign, SPEC.md §35. Nothing has to be re-entered and no stored
configuration changes.

### Changed

- **Two components instead of five: solar utilisation and price.** Both answer the same
  question about the same moment — did movable consumption fall where it should — and
  they weigh the same, because there is no honest ground to split them.

  Three components were removed for failing one of the two rules the score now has. A
  component is left out when the home **cannot influence it in this situation** — not
  when the signal happens to be zero — and **following the coach's advice may never
  lower the score.**

- **The peak component is gone from the score, and only from the score.** It fell exactly
  when the resident did what the coach had just asked: on a 1x25 A connection, plugging
  in the car at a low price took that axis from 100 to 57, costing 10 to 16 points in the
  same minute the advice appeared. The peak warning, the hysteresis, the binary sensor and
  the two advice rules are untouched.

- **The data quality is a gate rather than a term.** It no longer weighs 0.30 in the
  resident's number, which made that number mostly a report on the installer's paperwork.
  Instead there is no score at all until the three unconditional checklist items are
  answered — the home profile, a usable grid source and a price. A fresh install still
  cannot score 100: it scores nothing.

- **The flexibility component is gone.** It measured whether a complete appliance
  *existed*, which nothing the resident does today changes, and it charged for the same
  appliance the data quality checklist already counts.

- **The price component measures the house, not the market.** It used to score the hour
  alone, so every dynamic home scored 0 at 18:00 and 100 at 03:00 whatever it did, and two
  identical houses — one asleep, one running the dryer — scored the same. It is now the
  price position multiplied by the share of the connection actually being drawn, and it
  does not apply at all below the low threshold, where there is nothing to avoid.

- **Solar utilisation only counts when there is something to shift.** A home with panels,
  no battery and no complete flexible appliance cannot raise its self-consumption by any
  action, so scoring it was a discount and not a measurement. Adding a battery or
  completing an appliance switches the axis on.

- **A missing reading no longer scores zero.** An unreadable price or an unset threshold
  drops the component instead of deducting for it. The omission is reported by the data
  quality checklist and by the gate, where the person who can fix it will see it.

### Added

- **The panel says why there is no score, in a sentence.** A tile with a dash reads as a
  fault, and three of the four reasons are not faults at all: no variable signal, nothing
  movable, or nothing to improve at this moment. Only an incomplete installation is a
  shortcoming, and only that one carries a warning tone. The coach answers the same way
  under "Hoe is mijn energiescore berekend?".

### Known limitations

- **A home with a fixed contract and no solar panels never receives a number.** It has no
  moment that is better than another, so there is nothing to measure — an accepted
  consequence of the principle rather than a gap. All advice keeps working; the score is
  an extra, not a precondition. SPEC.md §35.9 lists what such a home would need.

- **`sensor.domotiapp_energy_score` is `unknown` more often**, which shows up as gaps in
  the long-term statistics. A daily average over this sensor is not meaningful.

- **The score still jumps when a component steps in or out**, because it is a reading of
  one moment. A score over a window is the real answer and needs its own design.

## 0.3.0

The panel now knows the difference between the installer and the resident. Round 1 of
SPEC.md §33; nothing has to be re-entered.

### Fixed

- **A resident could not set his own quiet hours.** The Voorkeuren tab is made entirely
  of statements about what *he* wants from the advice — when to be left alone, how many
  pieces of advice to show, whether to show the estimated saving — and it sat behind the
  admin lock with three other tabs. So did the ready window, which had just been built
  for him.

  Both of those are now his, and `preferences/update` no longer requires an admin.

- **A resident could not see a mistake in his own installation.** Four tabs disappeared
  entirely for a non-admin, so a main fuse entered as 25 A with a 40 in the meter cupboard
  stayed invisibly wrong until something went wrong with it.

### Changed

- **Six tabs instead of seven, and the same six for everybody.** `Woning` and
  `Energiebronnen` became two sections of one **`Installatie`** tab, and `Voorkeuren` is
  now **`Mijn voorkeuren`**. No tab is hidden from anyone; what a resident does not own is
  shown greyed out, with "Deze gegevens worden beheerd door DomotiTech." next to it.

  One tab set rather than one per role, so that a resident on the phone and the installer
  are looking at the same screen.

- **An appliance is split down the middle.** The resident sets how it should behave —
  `Klaar uiterlijk om`, `Niet eerder klaar dan`, the days, whether it may be noisy, its
  priority, and whether it may be steered at all. Everything else stays with the
  installer: the power, the energy per cycle, the entity links, and the agreement not to
  control it.

  His off switch is `Alleen meekijken`, not the enable toggle: that is what the control
  mode is for.

- **An agreement not to control an appliance now actually holds something back.** Until a
  resident could pick a control mode, the check could not fire in practice — only an admin
  could set the mode, and an admin also records the agreement.

- A validation message about a field a resident cannot touch now reads as something to
  pass on rather than as an instruction he cannot carry out.

### Removed

- **`Standaardstrategie` and `Rekening houden met de maximale netbelasting`.** Both were
  stored, validated and rendered, and read by nothing. Both sat on the border of resident
  territory, so without a decision they would have moved to a tab where a resident clicks
  them and nothing happens — which is worse than not offering them.

  No migration: unknown keys in an existing store are ignored, so nothing else is touched.

## 0.2.1

### Fixed

- **An appliance with only a deadline counted as having no time window at all.** A
  dishwasher set to "klaar uiterlijk om 20:15" was reported under "tijdvensters voor
  flexibele apparaten" as missing data, and the data quality dropped ten points — for
  exactly the configuration the ready window was built to make possible.

  One predicate served two different questions. The checklist asks *did you tell us when
  this has to be finished*, where a deadline on its own is a complete answer. The advisor
  asks *is there a window to test the current moment against*, which needs two edges. They
  are now `has_ready_window` and `has_complete_ready_window`, and the checklist uses the
  first.

  This only affects appliances configured with a single bound, which 0.2.0 made possible.
  Existing appliances are unaffected: the old start window required both ends too, so
  nothing changed for them on upgrade.

### Added

- A release workflow that fails when a git tag does not match the version in
  `manifest.json` and `const.py`. 0.2.0 was released under the tag 0.1.6, so HACS showed
  one version and Home Assistant another, and nothing went red. It runs before the release
  is published, so a mismatched tag can still be withdrawn.

## 0.2.0

The time window on an appliance now asks when it must be **finished** instead of when
it may start. Phase 1 of SPEC.md §32; nothing has to be re-entered.

### Fixed

- **An appliance could be advised too late to finish inside its own window.** A
  180-minute dishwasher with a finish time of 06:00 was advised at 05:55 and would have
  run until 08:55 — nearly three hours past the time the resident gave. For a machine
  that has to be emptied at 07:00, or that should be silent during the quiet hours, that
  is exactly the situation the window was meant to prevent.

  The old model only asked whether *now* fell inside the window; it never asked whether
  enough of the window was left. The validator did not catch it either, because it
  checked that the duration *fitted* the window rather than that the start was late
  enough. The start moment is now derived from the deadline and the duration, so this
  cannot happen.

  **This is why the window may look stricter after upgrading. It is a correction, not a
  change of mind:** the same dishwasher is now advised to start by 03:00.

### Changed

- `Vroegste start` and `Laatste eindtijd` are replaced by **`Klaar uiterlijk om`** and
  **`Niet eerder klaar dan`**. Same number of fields, and the question is the one a
  resident can actually answer: a deadline, not a start time.
- **`Niet eerder klaar dan` is new in kind.** It has no equivalent in a start window and
  covers what noise settings never could: washing that finishes at 03:00 sits wet until
  someone takes it out. That is spoilage, not noise.
- `Duur van een cyclus` finally does something. It is what turns a deadline into a start
  moment; without it, the deadline falls back to its old meaning of "may not run after"
  and no duration is guessed.
- Either bound may now stand alone. The old start window needed both ends or neither,
  because half a window was undefined; a ready window is not.

### Migration

Existing appliances are translated on reading — no customer re-enters anything, and the
configuration file is only rewritten on the next save:

```text
ready_from   = earliest_start + duration_minutes
ready_before = latest_finish
```

`earliest_start` meant "do not start before", so adding the duration makes it exactly
"do not be finished before". For an appliance without a duration the translation is
completely neutral.

## 0.1.5

A validation message that has nowhere to go, and two places it was going wrong.

### Fixed

- **A validation message whose field is not on screen now appears as a notice.**
  `ha-form` hangs each message on its field, so a message for a field the current
  schema leaves out was handed over and silently dropped. Every form in the panel
  filters its schema on something — the contract type, the source type, whether a
  device is flexible — so this was a property of conditional forms rather than a
  quirk of one card. All four tabs go through the same split, including the one that
  renders every field today, so it stays covered when that changes.
- A fixed contract is no longer asked for the energy tax and the supplier markup. It
  never consults the live price — not in the savings formula, not in the price advice,
  not in the score, not in the checklist — so the request went nowhere. This was the
  case that surfaced the defect above: the panel hides both fields on a fixed contract
  for exactly the reason the values are unused, so the installer saw nothing at all.
- A feed-in price source without a stated basis is now reported. It shipped in 0.1.4
  refused by the engine and reported nowhere, so the row did nothing and said nothing.
  The message is worded for the feed-in side rather than the import side.

### Added

- An explanation on the Woning tab of why the feed-in amounts do nothing yet: while
  net metering applies, a fed-in kWh is worth the same as one taken from the grid, so
  the feed-in tariff is never consulted. It names the date from `Saldering geldt tot`
  and points out that the **feed-in cost does** count today — that is the one term
  that survives the cancellation.

## 0.1.4

The feed-in tariff can now come from an entity, for homes on a dynamic feed-in
contract. **This matters from 1 January 2027**, when net metering ends and the
feed-in tariff becomes the entire difference between using your own solar and
selling it.

### Added

- A new source type, **Actuele terugleververgoeding** (`feed_in_price`). It reuses
  `price_basis` — the question is the same — but is converted by its own formula:
  the market price *minus* what the supplier keeps. No energy tax and no VAT, because
  neither is levied on power the home did not take. Running feed-in through the import
  formula would have overstated the tariff roughly threefold, which is why this is a
  separate source type rather than a flag on the price source.
- **Inhouding leverancier op teruglevering** (`feed_in_markup_eur_kwh`) on the Woning
  tab, for a source that reports the bare market price. No default: a silent zero
  would overstate what the customer receives. An explicit 0 is a valid answer, and
  the panel says so. A market feed-in source without it is refused and reported,
  the same way the import components are.
- A linked feed-in source takes over from the fixed **Terugleververgoeding**. That
  field is disabled rather than cleared, so removing the source restores it.

### Notes

- A negative feed-in rate is kept as such. Negative market prices are real, and then
  feeding in costs money — which makes using your own solar worth *more*, and the
  savings figure reflects that.
- At most one feed-in source, like the grid meter and the price source.
- Nothing changes for a home on a fixed feed-in tariff, which is every installation
  until it links a source.

## 0.1.3

Two advice defects a customer would recognise as nonsense on sight, and the energy
score that punished a home for things it could not change.

**The energy score will move on upgrade, and mostly upwards.** A home on a fixed
contract without smart appliances could not score above 82.5 no matter what it did;
that ceiling is gone. The solar component now measures something different — see below.

### Fixed

- A device is no longer advised when the surplus cannot run it. 600 W of surplus used
  to produce "benut je zonneoverschot" for a 2000 W dishwasher, with 1400 W coming off
  the grid and the estimated saving calculated as though the whole cycle came from the
  roof. Worse, when several appliances qualified the engine sorted on raw power and so
  picked the one that fitted *worst*. It now picks the largest appliance the surplus
  can actually carry. A device whose power is unknown is not excluded — that would be
  a guess in the other direction.
- `days_of_week` is enforced. It was stored, shown in the form, and read by nothing:
  a resident who unticked Sunday was advised to run the dishwasher on Sunday anyway.
  The panel asked, they answered, and the engine overruled them silently.
- A fixed contract is no longer scored 50 out of 100 on price. It was meant as neutral,
  but on an axis where everything else reaches 100 it was a permanent 7.5-point
  deduction for choosing a fixed contract — and the constant's own comment claimed the
  score was not dragged down by it. The component is left out of the score entirely.
- A home with no usable appliances is no longer scored 0 on flexibility. There is
  nothing to be flexible with and no setting would change that. A home that *does*
  have appliances and none of them flexible still scores a real 0, because that is a
  gap the installer can close.

### Changed

- **The solar component measured the opposite of its name.** It scored the surplus —
  power flowing *out* to the grid — so a home exporting everything got 100 and a home
  consuming all its own production got 0, while the field was labelled "zonnebenutting"
  and sat beside a coach advising the resident to use their surplus themselves. The
  score rewarded exactly what the advice discourages. It now measures what share of
  current production is used at home, and does not apply when there is no production:
  at night nothing is being wasted, and a nightly zero cost a home twenty points for
  nothing. This was an error in the specification, not only in the code, and SPEC.md
  §16 now records it as such.
- The energy score is the share of the applicable weight, like the data quality
  checklist. A component that cannot apply leaves both the sum and the divisor.
- The score is presented as a reading of this moment — "op dit moment" instead of
  "van 100" — and the coach names the components a home is not judged on.

## 0.1.2

The second round of findings from the production install. Where 0.1.1 was about
what the integration does to the hardware it runs on, this one is about what it
asks the installer and what it claims to the customer.

### Fixed

- The data quality checklist no longer holds a home to items about hardware it does
  not have. A home with solar panels and a smart meter but no smart appliances was
  told "2 van de 6 onderdelen is nog niet compleet" forever, and nothing it could
  configure would ever close them. Items are now asked only when a source row or an
  appliance says the home owns the thing, and the score is the share of what
  applies — so 100 stays reachable. A home that *does* have a solar row and cannot
  read it still loses the points, which is the distinction the whole thing rests on.
- An empty "Terugleverkosten" no longer counts as zero. Empty means unknown and now
  produces no estimated saving at all; enter 0 to say the connection pays nothing.
  Under net metering this was the entire answer — the avoided feed-in cost is the
  only term that survives — so a blank field silently produced "€ 0,00" for
  something that had never been worked out.
- A saving that works out negative is shown as a negative amount. It used to be
  clamped to zero, which hid the one situation worth knowing about: when the feed-in
  tariff exceeds the import price, self-consumption costs money. The advice text
  follows the arithmetic instead of saying "gunstig moment" over a loss.
- The asterisk is gone from "Vroegste start" and "Laatste eindtijd". It marked them
  as required directly above a helper reading "laat beide tijden leeg als er geen
  venster is" — the form contradicting itself in two adjacent lines. A window is a
  quality item, not a required field, and the helper now says what leaving it out
  costs.

### Changed

- Energiebelasting, opslag leverancier and btw are disabled when the linked price
  source already reports an all-in price. They exist to convert a bare market price;
  with nothing to convert they were three numbers that would never be read. They are
  disabled rather than hidden, and their values are kept, so an installer can still
  see what a market-price source would need.
- A charger is asked what a charger has: "Maximaal laadvermogen", "Energie per
  laadsessie" and "Duur van een laadsessie" instead of nominal power and cycles. The
  energy is explicitly a typical session, because nothing in this release knows how
  empty the car is, and advice built on it is capped at medium confidence for that
  reason. The state of charge arrives with the vehicle of a later release.
- Every €/kWh field takes the same step, fine enough for a real tariff. They
  disagreed — 0,001 on some, 0,0001 on others, same unit and same card — and both
  were coarser than the six decimals a supplier bills, such as 0,241710.

## 0.1.1

Findings from the first installation on a production Home Assistant OS with a real
P1 meter, SolarEdge inverter and Easee charger. Nothing here changes what the
integration does; it changes what it does to the hardware it runs on and what it
tells the customer.

**Upgrading is recommended for every installation with a smart meter.** The
storage fix alone is a reason: the previous release rewrote its configuration
file thousands of times a day on a meter that reports every second.

### Fixed

- The storage file is no longer rewritten on every recalculation. A repeated event
  collapses into a counter, but that counter used to be flushed to disk immediately;
  with a meter reporting every second that was thousands of writes a day and real wear
  on the SD card or eMMC. Repeats are now held in memory and written at most once a
  minute, and a pending counter is flushed on unload and on shutdown.
- Repeated events collapse even when two of them alternate. The anti-spam rule only ever
  looked at the newest line, so a peak risk and a solar surplus reported in the same pass
  each found the other at the front and started a new line — two writes per
  recalculation, from the rule meant to prevent exactly that.
- Switching the contract type no longer discards the other contract's values. The
  contract card is only handed the fields in force, so everything belonging to the other
  contract was merged back as "cleared" — and saving wrote those nulls to storage while
  the panel said the values were kept.
- Reason codes, confidence levels and checklist keys no longer reach the screen. The
  primary advice showed "missing_required_data" where a sentence belonged, and the
  surplus showed "Betrouwbaarheid: high". Every lookup now hides its row rather than
  falling back to the identifier, and a test enforces that each code has a Dutch word.

### Changed

- Thresholds have hysteresis and the headline advice a minimum dwell time, so a meter
  reporting every second no longer switches warnings and the estimated saving on and off
  continuously. Fixed constants, not settings.
- Entity readings older than 15 minutes are refused. A meter that quietly stops
  reporting used to keep its last value forever, presented with full confidence.
- The recalculation debounce is 15 seconds rather than 2.
- A source whose unit does not match what its type measures now produces a warning —
  the kWh meter reading of a P1 linked as a grid meter reads as millions of watts.

### Documented

- Peak risk is measured across the whole connection, not per phase. Named as a known
  limitation in the README and SPEC because on a three-phase installation with an EV
  charger it is the most likely failure.

## 0.1.0

- Initial Home Assistant custom integration.
- Manual home, energy source and appliance configuration.
- Local deterministic energy advisor.
- Data completeness score.
- Energy score.
- Grid peak warning.
- Solar surplus advice.
- Dynamic price advice.
- Dutch custom panel.
- No automatic discovery or device control.
