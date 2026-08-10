# CLAUDE.md — werkinstructies DomotiApp Energy

## Wat dit project is

Een Home Assistant custom integration (`domotiapp_energy`) die dient als handmatig
configureerbare energiecoach. Wordt door DomotiTech uitgerold bij klanten via HACS.
De volledige functionele specificatie staat in **`SPEC.md`** — lees die bij twijfel,
en wijk er niet van af zonder het expliciet te melden.

Taal: code en README in het Engels, alle zichtbare UI-teksten in het Nederlands,
overleg met de ontwikkelaar in het Nederlands.

## Doelomgeving

- Home Assistant 2025.6 of nieuwer
- Python 3.13
- Geen externe runtime-dependencies (`manifest.json → requirements: []`)

## Harde regels (nooit overtreden)

1. **Geen automatische discovery of entity-matching.** Niet zoeken in het entity- of
   deviceregister, niet matchen op naam, geen suggesties, geen discoveryflow.
   Alle koppelingen komen uit expliciete gebruikersselectie in de GUI.
2. **Geen aansturing.** Geen `hass.services.async_call` naar een ander domein dan
   `domotiapp_energy`. De integratie meet, rekent, adviseert en waarschuwt — meer niet.
3. **Geen netwerk.** Geen externe API, cloud, telemetry, analytics, AI-provider of
   API-sleutel. Alles lokaal.
4. **Geen YAML-configuratie.** Alles via de UI.
5. **Geen externe frontendlibraries, geen CDN, geen React, geen build-stap.**
   Native ES-modules en bestaande Home Assistant-componenten.
6. **Geen browseropslag.** Geen localStorage, sessionStorage, IndexedDB of cookies.
   De backendstorage is de enige bron van waarheid.
7. **Geen hardcoded kleuren.** Uitsluitend Home Assistant themavariabelen.
   `#026FA1` mag nergens in de code voorkomen.
8. **Geen mockdata of placeholders in productiecode.**
9. **De revision verandert uitsluitend door een expliciete gebruikersactie.**
   Laden, herberekenen, achtergrondtaken en het wegschrijven van logboekregels
   verhogen de revision nooit; `async_load` schrijft helemaal niets. Alleen een
   wijziging aan de configuratie zelf (woning, bronnen, apparaten, voorkeuren)
   die uit de GUI komt, verhoogt de revision met 1. Anders verloopt de
   `expected_revision` van de frontend terwijl de gebruiker een formulier
   invult en wordt een geldige opslagpoging onterecht geweigerd.
   Afgeleide toestand (zoals de quarantaine van een rij met een onbekend type)
   wordt in het geheugen berekend, nooit teruggeschreven naar de storage.
10. **Paneelteksten staan in de frontendbestanden, niet in `translations/`.**
    Dat is besloten in fase 9 en vastgelegd in SPEC.md §26 met de reden: het zijn
    zinnen die de redenering dragen, en die horen naast het veld dat ze uitleggen.
    `translations/` bevat alleen wat HA zelf rendert (config flow, entiteitsnamen,
    services). Verplaats dit niet als "opruimwerk" — het verandert pas bij een klant
    buiten het Nederlandse taalgebied, en dan als eigen ronde.

11. **De zes entity-ID's zijn Engels en vast, ongeacht de UI-taal van de klant.**
    Ze staan in de README; klanten bouwen er dashboards, automatiseringen en
    langetermijnstatistieken op (`statistic_id` is de entity-ID zelf).

    Dit vecht bewust tegen wat op HA-standaardgedrag lijkt, dus ruim het niet op.
    HA leidt de object-id af uit de entiteitsnaam in de *native-entity-id-taal*:
    `entity_platform.EntityPlatformData.async_load_translations()` kiest
    `hass.config.language` zodra die in
    `homeassistant.generated.languages.NATIVE_ENTITY_IDS` staat, en die verzameling
    bevat 41 talen waaronder `nl`. Zonder tegenmaatregel heet de sensor bij een
    Nederlandse klant `sensor.domotiapp_energy_energiescore`.

    Daarom overridet `entity.py` de property `suggested_object_id` met de vaste
    Engelse naam uit `const.ENTITY_OBJECT_ID_NAMES`. `Entity` kent geen
    `_attr_suggested_object_id`, en `self.entity_id` zetten zou ook de
    devicenaam-prefix hard coderen. Zet nooit `_attr_name`: de weergavenaam moet
    de taal juist wél volgen. De devicenaam blijft vast `DomotiApp Energy`, omdat
    HA die vóór de object-id plakt.

    **Een wijziging aan deze ID's ná de eerste uitrol is een breaking change en
    vereist een major-versiebump.** Al geregistreerde entiteiten behouden hun ID,
    dus zo'n wijziging splitst het bestand in klanten met oude en nieuwe ID's,
    met gebroken dashboards en afgekapte statistieken bij de laatste groep.
    De tests in `tests/test_entities.py` bewaken dit in `en` én `nl`.

## Verplichte API-keuzes

| Doel | Gebruik dit | Niet dit |
|---|---|---|
| Static files | `hass.http.async_register_static_paths([StaticPathConfig(...)])` | `register_static_path` |
| Paneel | `panel_custom.async_register_panel` | handmatige frontend-calls |
| Entry-data | `entry.runtime_data` | `hass.data[DOMAIN]` |
| Platforms | `async_forward_entry_setups` | `async_setup_platforms` |
| State-events | `async_track_state_change_event` | `async_track_state_change` |
| Tijd | `homeassistant.util.dt` | `datetime.now()` |
| WS-admin | `@websocket_api.require_admin` | eigen check |

WebSocket-commando's en services worden **eenmalig in `async_setup`** geregistreerd,
nooit in `async_setup_entry` (breekt bij reload).

## Werkwijze

Werk in de fases uit `SPEC.md` §30. Per fase:

1. Bouw de fase af.
2. Draai `ruff check .` en `ruff format .`
3. Draai `pytest`
4. Los alles op tot beide schoon zijn.
5. Commit met een beschrijvende message, prefix `feat(fase-N):` of `fix:`.
6. **Push altijd direct na de commit** (`git push`). Controleer daarna met
   `gh run list` / `gh run view --log-failed` of Tests én Validate groen zijn,
   en meld de push plus de CI-uitslag in het eindrapport van de fase.
7. Rapporteer kort wat af is en wat nog open staat.

Begin niet aan een volgende fase voordat de tests van de huidige fase slagen.

### Een ronde eindigt op main, nooit op een blijvende branch

**`main` is altijd de laatste geverifieerde staat.** Sven installeert vanaf `main`
op productie, dus alles wat "af" is hoort daar te staan en niets anders.

Werk je op een branch — bij een ronde met meerdere samenhangende wijzigingen, of
wanneer de harnasrichtlijn zegt niet rechtstreeks op de standaardbranch te
committen — dan is de ronde pas klaar na deze stappen:

1. Push de branch.
2. **Open een PR** (`gh pr create --base main`). Dat is meteen de enige manier
   waarop CI draait: de workflows triggeren op `push` naar `main` en op
   `pull_request`, dus een losse branch krijgt geen enkele run. `gh workflow run`
   op een branch is een noodgreep, geen vervanging — een handmatige trigger zegt
   niets over wat er bij een merge gebeurt.
3. Wacht tot **Tests én Validate groen zijn**. Loopt een run vast op
   *"The job was not acquired by Runner of type hosted"*, dan is dat een storing
   bij GitHub en geen testfout: opnieuw aanbieden, en dat verschil expliciet
   melden in plaats van "CI is rood" te rapporteren.
4. **Merge naar `main`** en verwijder de branch.
5. Meld de merge, de CI-uitslag en de nieuwe stand van `main`.

#### Controleer vóór elke push of je branch nog bestaat

**Een `git push` zonder te kijken waar je staat kan op `main` landen.** Dat is één keer
gebeurd, op 2026-08-08: Sven merget een PR terwijl er nog gewerkt wordt, de branch
verdwijnt van de remote, en de volgende commit komt op `main` in plaats van in een PR.
De code was groen, maar hij had haar niet gezien voordat zij er stond — precies wat de
PR-route moet voorkomen.

Dus vóór elke push:

```powershell
git branch --show-current    # sta ik nog op mijn branch, of op main?
```

Sta je op `main` terwijl je aan een ronde werkt, maak de branch dan opnieuw aan en zet je
commits daarop:

```powershell
git checkout -b <ronde-naam>
```

**Push nooit rechtstreeks naar `main`** om een verdwenen branch heen te werken. Merk je
het pas achteraf, meld het dan meteen en laat de keuze om het recht te zetten aan Sven —
`main` herschrijven is zijn beslissing, niet die van jou. Hij meldt het voortaan wanneer
hij merget terwijl jij bezig bent, maar de controle blijft aan jouw kant: hij weet niet
waar jij in je ronde zit.

Laat nooit een afgeronde ronde als losse branch achter. Een branch die blijft
hangen betekent dat `main` en "wat af is" uit elkaar lopen, en dan klopt de
aanname waarop de productie-installatie rust niet meer.

### Het versienummer staat op vier plaatsen

`custom_components/domotiapp_energy/const.py` (`VERSION`), `manifest.json`,
`frontend/domotiapp-energy-panel.js` (`const VERSION`) en `pyproject.toml`. Ze
moeten gelijk zijn: `VERSION` bouwt het statische pad waaronder het paneel
geserveerd wordt en de paneelmodule draagt zijn eigen kopie voor de
cache-busting, dus uiteenlopen levert precies het half-oude paneel op dat het
versiepad moest voorkomen. `tests/test_panel.py` bewaakt dit.

**Sven tagt pas nadat jij "gemerged" hebt gemeld (afspraak 2026-08-09).** Hij tagde 0.13.0
terwijl de code nog op een branch stond; de release-workflow was groen, want die vergelijkt
de tag met `manifest.json` en `const.py` — **niet of die commit op `main` staat**. Was er
daarna nog iets aan de PR veranderd, dan had de release code bevat die nooit op `main` kwam.
Meld de merge dus expliciet, dat is het sein.

**Tags en releases maakt Sven zelf.** Bump het versienummer en de CHANGELOG,
meld dat `main` klaar is om te taggen, en maak nooit zelf een tag of release.

**Noem het te taggen versienummer als aparte regel in je eindrapport**, niet
terloops in een PR-tekst. Zo:

> **Te taggen: `0.2.0`** — niet 0.1.7, want het gereed-venster vervangt velden.

Dat is nodig omdat jij de versie kiest en Sven hem tagt, en die twee liepen een
keer uiteen: fase 1 bumpte naar 0.2.0 omdat het gereed-venster velden verving,
Sven tagde 0.1.6 als volgende in de reeks. Beide redeneringen waren op zichzelf
juist. Het gevolg is dat een klant **twee verschillende versienummers ziet**:
HACS toont de release, de integratiepagina in Home Assistant toont het manifest.

**De harde vangnet is `.github/workflows/release.yml`**, die op een tag-push
faalt zodra de tag afwijkt van `manifest.json` en `const.py`. Die controle
hangt niet van aandacht af, en hij slaat toe vóórdat de release gepubliceerd is
— HACS leest de release, niet de tag, dus een verkeerde tag is dan nog in te
trekken.

Een controle op `main` kan dit principieel niet vangen: tussen het bumpen in
een PR en het taggen draagt `main` per definitie een versie die nog niet
gereleased is, dus "versie gelijk aan laatste tag" zou daar permanent rood
staan.

## Commando's

Linten gebeurt lokaal in `.venv`, **testen gebeurt altijd in de testcontainer.**
Home Assistant pint `lru-dict==1.3.0`, waarvan geen cp313-wheel voor Windows bestaat;
`pip install -e ".[dev]"` slaagt daarom niet native op deze machine. Draai `pytest`
nooit vanuit `.venv`.

```powershell
# eenmalig: venv voor ruff (geen testdependencies)
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install ruff

# linten, per fase
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format .

# testen, per fase — bouwt het image zo nodig en forwardt alle argumenten
.\scripts\test.ps1
.\scripts\test.ps1 tests/test_storage.py -k revision
.\scripts\test.ps1 --cov=custom_components/domotiapp_energy --cov-report=term-missing
```

Het testimage installeert de dependencies in een eigen laag en wordt alleen opnieuw
gebouwd wanneer `pyproject.toml` verandert; de broncode is een bind-mount.

### Een frontendwijziging zien in de browser

De frontend wordt geserveerd onder een **versiepad** (`/domotiapp_energy_frontend/0.1.0/…`),
omdat `?v=` alleen de entrypoint bust: een relatieve `import` erft die querystring niet.
Dat lost het op voor de klant — een release verandert het pad, dus alle modules zijn nieuw.

**Tijdens ontwikkeling helpt dat niet**, want tussen twee iteraties verandert het
versienummer niet. Home Assistant heeft een **service worker** die op exacte URL cachet en
zichzelf bij elke load opnieuw registreert; Chrome bewaart de bestanden daarnaast nog in
de schijfcache. Een containerherstart is dus níet genoeg: je ziet je eigen wijziging niet,
en niets wijst erop dat je naar oude code kijkt.

**De betrouwbare route (Sven, 2026-08-06):** open DevTools met **F12**, rechtsklik dan op
de herlaadknop en kies **"Cache wissen en geforceerd opnieuw laden"**. Dat omzeilt óók de
service worker.

**Een gewone Ctrl+F5 volstaat hiervoor niet** — die haalt de schijfcache over, maar laat
de service worker zijn eigen kopie serveren. Dat is precies het verschil dat je uren kan
kosten, want het paneel laadt "vers" en draait toch oude modules.

Wil je het scripten (bijvoorbeeld vanuit browserautomatisering), dan doet dit hetzelfde,
gevolgd door een herlaadbeurt:

```javascript
const regs = await navigator.serviceWorker.getRegistrations();
await Promise.all(regs.map((r) => r.unregister()));
const names = await caches.keys();
await Promise.all(names.map((n) => caches.delete(n)));
// De schijfcache van Chrome hoort er ook bij: haal elk bestand één keer op met
// {cache: 'reload'}, dat herschrijft de opgeslagen kopie.
for (const file of ['domotiapp-energy-panel.js?v=0.1.0', 'core/dom.js', 'tabs/overview.js']) {
  await fetch(`/domotiapp_energy_frontend/0.1.0/${file}`, { cache: 'reload' });
}
```

Controleer of je echt verse code ziet met
`performance.getEntriesByType('resource')`: alles met `deliveryType: "cache-storage"`
kwam van de service worker, niet van de server.

### Frontendtests (JavaScript)

`pytest` kan geen JavaScript uitvoeren. De paneelcode heeft daarom **drie eigen lagen**,
en ze bewijzen verschillende dingen: jsdom met de testrunner van Node, en twee
Playwright-routes.

```powershell
npm install                # eenmalig (jsdom + Playwright)
npx playwright install chromium   # eenmalig, de browser zelf

npm test                   # laag 1: jsdom,      tests/frontend/*.test.mjs
npm run test:layout        # laag 2: echte browser, gestubde HA — draait in CI
.\scripts\browsertest.ps1  # laag 3: echte browser, echte HA — met de hand
```

**De dev-dependencies raken de integratie niet.** `custom_components/` verscheept geen
JavaScript-afhankelijkheden en heeft geen buildstap (regel 5); `package.json` bestaat
uitsluitend voor deze drie lagen.

#### Wat elke laag wél en niet kan bewijzen

Dit is de belangrijkste tabel van deze sectie. Een groene CI dekt **de eerste twee
kolommen**, en dat is minder dan het voelt.

| | jsdom (`npm test`) | route 2 (`npm run test:layout`) | route 1 (`browsertest.ps1`) |
|---|---|---|---|
| Wat de paneelcode aan de DOM doet | ja | ja | ja |
| De cascade: wordt `.is-hidden` echt `display: none` | **nee** | ja | ja |
| Containerqueries, schermbreedtes, zijwaartse overloop | **nee** | ja | ja |
| Safe areas (gefakete insets) | **nee** | ja | ja |
| **Rendert `ha-form` een control, en accepteert die een klik** | **nee** | **nee** | **ja** |
| Slaat een waarde echt op en overleeft hij een herlaadbeurt | nee | nee | ja |
| Draait in CI | ja | ja | **nee** |

**Route 2 laadt geen enkel Home Assistant-component.** `ha-form`, `ha-input`,
`ha-select` en `ha-input-chip` horen bij HA, niet bij ons; ze binnenhalen zou een CDN of
een buildstap betekenen. In die pagina zijn het onbekende elementen: ze staan in de boom
en doen niets.

> **Een groene `npm run test:layout` zegt niets over of een control een klik accepteert.**

Dat is precies het gat waar de dagenselector doorheen viel. Verbreed daarom **nooit** een
test in route 2 tot "kijken of het formulier werkt" — heeft een vraag een gerenderde
control nodig, dan hoort hij in route 1.

**Route 1 schrijft naar de instance waar hij op wijst.** Elke rij die hij aanmaakt heet
`PLAYWRIGHT TESTRIJ` en wordt weer verwijderd. Blijft er na een afgebroken run toch één
staan, verwijder die dan op Apparaten.

Route 1 staat bewust niet in CI: hij heeft een draaiende HA, een token en een
configuratie nodig die verandert terwijl je werkt. In een workflow zou hij falen om
redenen die niets met de commit te maken hebben, en een check die zo faalt wordt
genegeerd.

**Vertrouw niet op de cascade van jsdom.** jsdom implementeert CSS maar gedeeltelijk, dus
een vraag als "wint een eigen `display`-regel van `[hidden]`?" kun je er niet mee
beantwoorden — en dat was precies de vraag waar fase 7a op stukliep. Toets in plaats
daarvan **ons eigen contract**: `setVisible()` uit `core/dom.js` zet de klasse
`is-hidden`, en het stylesheet zet daar `display: none !important` achter. Verberg nooit
iets met alleen het `hidden`-attribuut.

Een frontendwijziging is pas geverifieerd wanneer een test faalt zónder de fix. Draai bij
een bugfix eerst de test tegen de oude code.

**jsdom stubt `ha-form` volledig.** `.schema` en `.data` zetten alleen properties; er
wordt geen control gerenderd. Geen enkele test in deze laag kan dus bewijzen dat een
control een klik accepteert — zo is de dagenselector kapot uitgeleverd met een groene
suite. Toets hier wat de stub wél kan zien (bijvoorbeeld: geen enkele `select`-optie mag
een niet-string waarde dragen) en toets de control zelf in de browser — met
`.\scripts\browsertest.ps1`, de enige laag die hem rendert.

**Hoe die control er precies uitziet, is niet van ons.** Dezelfde
`select`-multiselector met zeven opties is inmiddels op drie manieren gerenderd:
combobox, checkboxes, en op HA 2026.7 een rij `ha-input-chip`s. Er veranderde niets aan
onze code. Pin daarom in route 1 geen componentnaam waar het niet nodig is (het naamveld
wordt gezocht als eerste zichtbare `input`, niet als `ha-textfield`), en verwacht dat een
HA-upgrade deze laag rood maakt — dat is precies waarvoor hij bestaat.

### Verifieer frontendwijzigingen zelf in de browser (afspraak Sven, 2026-08-06)

**Lever een frontendwijziging niet op zonder hem in de echte browser te hebben bediend**,
met claude-in-chrome en **echte kliks** — niet met synthetische `value-changed`-events.
Een synthetisch event bewijst de handler, niet de control. Ververs eerst langs de service
worker (zie hierboven), want anders test je oude code.

Reageert iets niet, vergelijk dan met een control in hetzelfde formulier die wél werkt;
het verschil is de oorzaak. Bij de dagenselector was dat het waardetype: zeven opties
renderen als combobox (werkt met strings), vier als checkboxes (nemen de waarde zoals hij
is). Controleer de hele keten tot in de backend en ruim testrijen daarna weer op.

### Lees testuitvoer, ga niet uit van groen

`npm test` schrijft zijn samenvatting met een `ℹ`-prefix; een grep-patroon dat daar niet
op past geeft stil niets terug. Dat is één keer misgegaan: een backtick in een
CSS-commentaar sloot de template literal van het stylesheet en brak het hele paneel,
terwijl de suite dat gewoon zou hebben gemeld. **Geen uitvoer is geen bewijs.** Draai
`npm test` via PowerShell en lees de regels `tests` / `pass` / `fail` expliciet.

### Een fixture kan de bug vastleggen in plaats van hem te vangen

Bij een nieuwe of gewijzigde fixture is de vraag **niet alleen** "is dit een realistisch
geval", maar ook: **codificeert deze waarde het gedrag dat ik wil, of het gedrag dat er
toevallig is?** Een default die een normaal geval heet en in werkelijkheid het foute
gedrag beschrijft, maakt de hele suite blind voor precies dat defect — en dan is groen
geen bewijs maar een bevestiging van de fout.

Dit is een **andere faalmodus** dan de gevallen hierboven. Daar toetsten tests de vorm
in plaats van de uitkomst (de `ha-form`-stub, de jsdom-cascade). Hier wérd de uitkomst
getoetst, alleen tegen een verkeerd voorbeeld.

Twee keer voorgekomen, beide in augustus 2026 en beide pas gevonden in de echte HA:

- **`feed_in_cost_eur_kwh` stond nergens in `_config()`**, dus stond hij op `None`, en
  elke besparingstest rekende stilzwijgend met "onbekend = 0". Precies de aanname die
  ronde B moest opheffen. De fixture beschreef de bug.
- **`_device()` had `nominal_power_w = 2000.0`** terwijl vrijwel elke zonnetest
  `solar_surplus_w = 1500.0` gebruikte. Elke test beschreef dus een vaatwasser die het
  overschot niet kon draaien — het defect dat later "benut je zonneoverschot" op een
  net-import van 1400 W bleek te zetten. Jarenlang groen.

Praktisch: zet bij een fixturewaarde die een aanname draagt **de reden in de docstring**,
niet alleen de waarde. Zodra je hem moet uitleggen, valt op of hij het gedrag beschrijft
dat je wilt. Beide fixtures dragen die uitleg nu.

#### Vierde variant: de hernoeming die een assertie stil omdraait

Zoek-en-vervang maakt een assertie **syntactisch correct en semantisch fout in één
beweging, zonder dat er iets rood wordt.** Dat is precies waar het gereedschap goed in
is: de vorm kloppend houden.

Voorbeeld, augustus 2026. Bij het gereed-venster werd `earliest_start` → `ready_from` en
`latest_finish` → `ready_before` overal vervangen. Deze assertie ging mee:

```python
("ready_from", COMPLETENESS_ITEM_TIME_WINDOWS),   # was earliest_start
("ready_before", COMPLETENESS_ITEM_TIME_WINDOWS), # was latest_finish
# ...één van de twee weglaten → verwacht dat het venster-item ontbreekt
```

Onder het oude model klopte dat: een half startvenster wás geen venster. Onder het nieuwe
model is één grens een volwaardig antwoord — "klaar uiterlijk om 20:15" is wat de meeste
bewoners bedoelen. De test verifieerde dus actief het defect, en op productie zakte de
datakwaliteit tien punten voor precies de configuratie waarvoor het gereed-venster is
gebouwd.

**De vraag bij een hernoeming is niet of iedereen de nieuwe naam leest, maar of het
nieuwe veld hetzelfde betekent en of elke consument nog klopt met de nieuwe betekenis.**

Concreet: loop na een hernoeming elke *lezer* van het veld langs, niet alleen elke
schrijver. Betekende het oude veld iets anders, dan is de kans groot dat één predicaat
nu twee vragen bedient — in dit geval betekende `has_time_window` zowel "is er iets
ingevuld" (checklist) als "is er een venster om tegen te toetsen" (advisor), en die twee
liepen uiteen zodra een halve grens geldig werd.

#### Vijfde variant: de default die niets las, tot er gedrag aan hing

`_metrics()` in `tests/test_advisor.py` zette `solar_surplus_confidence` niet, dus stond
hij op de modeldefault `low`. Onzichtbaar zolang dat niveau alleen een etiket voedde. Toen
0.4.1 er gedrag aan hing — geen overschot-advies bij een onbetrouwbare meting — vielen
**38 tests tegelijk om**, allemaal omdat ze een woning met een onleesbare batterij
beschreven terwijl ze adviesinhoud dachten te toetsen.

**Een fixturewaarde die niets leest, is niet ongevaarlijk maar onzichtbaar.** Hij hoeft
alleen te kloppen tegen de code die hem gebruikt, dus zonder gebruiker neemt hij stil aan
wat de dataclass hem geeft. Vraag bij een default waarop een fixture leunt: *wat zou dit
beschrijven als het ineens ging meetellen?*

#### Zesde variant: de verificatie die haar invoer uit de verwachte uitkomst afleidt

**De belangrijkste van de zes**, want hij verklaart waarom de browserafspraak hier niet
hielp (Sven, productie, 2026-08-08).

De tegel koos `nothing_movable` op het bestáán van een zonnerij, terwijl de bijbehorende
zin "er is nu opwek" zegt. 's Avonds bij 0 W kreeg de klant dus te horen dat zijn panelen
leverden. Beide lagen misten het:

- de enige test voor dat geval zette `sensor.pv` op 2000 — mét opwek;
- de browsercontrole koppelde de zonnebron aan een helper die 2875 W stond — mét opwek.

In beide gevallen was de zin toevallig waar, dus er viel niets op. **Ik had per code een
toestand gezocht die hem opleverde en toen gecontroleerd of de zin erbij paste.** Dat
toetst of een tak rendert, niet of het de juiste tak is.

**De omkering, en zij geldt breder dan tests.** Bij een selector — of wat dan ook dat één
uitkomst kiest uit meerdere — is de vraag niet *"welke toestand levert deze uitkomst op"*
maar **"gegeven deze situatie, welke uitkomst hoort erbij"**. In de testlaag is dat een
tabel van situaties met de verwachte uitkomst ernaast, één rij per situatie; zie
`test_which_sentence_the_tile_gets`. Zo'n rij is een oordeel over de keuze in plaats van
een bevestiging van een tak, en hij dwingt de randgevallen af die je anders niet bedenkt.

**Bij browserverificatie geldt hetzelfde, en daar is het makkelijker te vergeten.** Stuur
de browser aan vanuit de situatie ("het is avond en de panelen staan stil — wat hoort hier
te staan?"), niet vanuit de code ("hoe krijg ik deze tak op het scherm?"). Doe je het
tweede, dan bouw je twee lagen die elkaar bevestigen in plaats van corrigeren, en is de
browsercontrole geen tweede mening maar dezelfde mening in een ander venster.

Praktisch gevolg voor elke zin die door een voorwaarde gekozen wordt: **de voorwaarde moet
toetsen wat de zin beweert.** Zegt de zin "nu", dan mag de voorwaarde niet uit de
configuratie komen.

#### Zevende variant: de toets klopt, maar de code draait niet

**Ernstiger dan de zes ervoor**, want daar toetste een test de verkeerde uitkomst — hier
was de toets correct en werd de code in productie nooit uitgevoerd.

Het vermogen per apparaat werd gelezen in `Calculator.calculate()`. **De coordinator roept
die methode nooit aan**: hij gebruikt `build_snapshot` en `derive_metrics` apart, omdat de
hysterese-latch daartussen zit. Elke test gebruikte `calculate()`, dus 588 tests waren
groen terwijl het paneel niets toonde. Het viel alleen op doordat Sven het in de browser
wilde zien.

**De vraag die hem vangt:** *roept het product deze functie werkelijk aan, of alleen mijn
test?* Stel hem bij elk nieuw stuk logica dat je aan een bestaande functie hangt, en
beantwoord hem door het aanroeppad terug te lopen tot aan de coordinator, een
WebSocket-handler of een entiteit — niet tot aan de test.

**Waar hij het vaakst opgaat:** een klasse met meerdere instapmethoden waarvan er één een
gemakkelijke samenstelling is. Die samenstelling is aantrekkelijk in een test (één
aanroep, alles klaar) en juist daarom bypassen de echte aanroepers hem, omdat zij tussen de
stappen iets moeten doen.

**Structurele tegenmaatregel:** houd zo'n samenstellende methode leeg. `calculate()` is nu
één regel die `derive_metrics(config, build_snapshot(config))` teruggeeft en verder niets,
met een docstring die zegt dat de coordinator hem niet gebruikt. Wat daar bijkomt is
zichtbaar fout in plaats van stil dood.

#### Achtste variant: de test klopt, en de aanname eronder niet

**De belangrijkste van de acht, want hij is met geen enkele test te vinden.**

Gevonden op 2026-08-09, bij het inrichten van een vreemde woning. Eén constante van
vijftien minuten weigerde een prijssensor die per uur publiceert en een terugleversensor
die 's nachts terecht 0 blijft. Het paneel zei dat de bronnen onleesbaar waren; de
installateur kon niets doen.

En er was een test die precies dit gebied dekte, met een docstring die uitlegde waarom:

```python
async def test_a_steady_reading_is_not_stale(...):
    hass.states.async_set(ENTITY_ID, "1500")
    freezer.tick(timedelta(minutes=ENTITY_STALE_AFTER_MINUTES + 1))
    hass.states.async_set(ENTITY_ID, "1500")   # opnieuw gerapporteerd, zoals echte hardware
    assert read_entity_value(hass, _binding(unit=UNIT_W)).ok is True
```

Die test is goed. Hij toetst het ontwerp, en het ontwerp klopt met zichzelf. Wat er
misging zit in die ene regel commentaar — *zoals echte hardware* — want dat is geen
uitspraak over onze code maar **over de wereld**:

> Elke gekoppelde bron rapporteert minstens elk kwartier opnieuw.

Waar voor een P1-lezer en voor pollende integraties. Onwaar voor alles wat alleen bij
verandering schrijft: MQTT met retain, Zigbee-stekkers, templatesensoren,
`input_number`-helpers, en een uurlijkse dynamische prijs.

**De vraag die hem vangt**, te stellen bij elke regel die iets weigert, afkapt, drempelt
of verwerpt:

> **Welke aanname over de wereld maakt deze regel, en welke apparaten van een klant
> voldoen daar niet aan?**

**En de kanttekening die erbij hoort: een unittest kan die aanname per definitie niet
weerleggen.** Hij bouwt zijn eigen wereld — hij schrijft de state een moment voordat hij
hem leest, dus elke entiteit is altijd vers. De test bevestigt de aanname in plaats van
haar te toetsen, hoe zorgvuldig hij ook geschreven is. Daar is een echte installatie voor
nodig, of een aanname die zo expliciet is opgeschreven dat iemand haar kan tegenspreken.

Praktisch gevolg: schrijf zo'n aanname **in de code, naast het getal**, in de vorm "dit
geldt omdat …" en niet "dit is zo". `SOURCE_STALE_MINUTES` doet dat nu per brontype, en
een guard-test dwingt af dat een nieuw type zijn eigen keuze krijgt in plaats van er
stilzwijgend een te erven (SPEC.md §47).

### Negende variant: twee plekken die dezelfde vraag anders beantwoorden

**Twee keer voorgekomen, en de tweede keer had ik hem moeten zien aankomen.**

Dit is niet "een test toetst het verkeerde" en ook niet "de code draait niet". Beide plekken
draaien, beide zijn op zichzelf verdedigbaar, en ze zijn het oneens over dezelfde vraag.

1. **0.6.1 — `has_time_window`.** Eén predicaat bediende twee vragen: *"is er iets ingevuld"*
   (checklist) en *"is er een venster om tegen te toetsen"* (advisor). Zolang een half
   venster ongeldig was vielen die samen; op het moment dat één grens een volwaardig antwoord
   werd, liepen ze uiteen. Opgelost door ze te splitsen in `has_ready_window` en
   `has_complete_ready_window`.
2. **§51 — `_deadline_is_reachable`.** De advisor trok de grens al expliciet: met alleen een
   deadline is er geen startvenster, want *"klaar om 08:00"* betekent de **volgende** 08:00 en
   welke dat is hangt af van wanneer je het vraagt. Mijn nieuwe validator wist dat niet en
   liep stilzwijgend de hele dag af — hij claimde onmogelijkheid in een geval dat niet te
   beslissen is.

**Wat de twee gemeen hebben:** de ene plek had de grens al doordacht en opgeschreven, en de
andere kwam er later bij zonder hem te lezen. In beide gevallen stond het antwoord er al,
één functie verderop, in een docstring.

> **De vraag die hem vangt, te stellen zodra je een predicaat schrijft dat op bekende velden
> oordeelt:** *stelt iets anders in dit project deze vraag al, en wat antwoordt het?*

Niet "bestaat er een helper die ik kan hergebruiken" — dat is de gewone opruimvraag. Dit gaat
over de *betekenis*: twee plekken die "is dit venster bruikbaar" verschillend beantwoorden
zijn een bug die geen van beide tests kan zien, want elke test toetst zijn eigen kant.

**Praktisch:** grep vóór het schrijven op de velden waar je op gaat oordelen
(`ready_before`, `no_run_from`, …) en lees elke lezer die je vindt — niet om code te delen,
maar om te zien welke randgevallen daar al beslecht zijn. Dat is dezelfde beweging als de
vierde variant vraagt na een hernoeming, nu vooraf in plaats van achteraf.

### Een eis die niet van toepassing is, gepresenteerd als een gebrek

**Vijf keer voorgekomen, allemaal in de datakwaliteit**, en elke keer opnieuw ontdekt door
een klant in plaats van door ons:

1. tijdvensters bij een woning zonder apparaten;
2. de zonnebron bij een woning zonder panelen;
3. de prijscomponent bij een vast contract (de energiescore, zelfde vorm);
4. een cyclus bij een `generic_monitor` — die per definitie geen cyclus heeft;
5. een tijdvenster bij een apparaat dat de bewoner op *Alleen meekijken* had gezet.

**De vorm is altijd dezelfde:** een item wordt gesteld op grond van *bestaan* — er is een
rij, er is een apparaat — terwijl het iets vraagt dat alleen betekenis heeft bij een
*eigenschap* van dat ding. De klant ziet dan een tekortkoming die hij niet kan opheffen,
en zijn cijfer zakt voor iets waar hij niets aan kan doen.

**De vraag die het vangt, te stellen bij elk nieuw item en bij elke wijziging aan een
bestaand item:**

> Kan een woning die het betreffende ding niet heeft, of niet op die manier gebruikt, dit
> item ooit afvinken? Zo nee, dan hoort het niet gesteld te worden.

Niet "kan hij het invullen" maar "kan hij het afvinken" — dat is het verschil tussen een
gat en een eis die niet van toepassing is.

Praktisch: de toepasselijkheid hoort te hangen aan **waar de gevraagde waarde voor
gebruikt wordt**, niet aan het bestaan van de rij. Zo vragen het apparaatprofiel en het
tijdvenster allebei om iets dat alleen advies dient, en hangen ze daarom allebei aan
`is_advisable` (SPEC.md §16). Toen die vraag over de zes items werd gesteld kwam er
onmiddellijk een vijfde geval uit dat nog niemand had gemeld.

### De testomgeving loopt gelijk met de klant (sinds 2026-08-09)

| | Python | Home Assistant |
|---|---|---|
| Testcontainer en CI | 3.14 | 2026.8.1 (via `pytest-homeassistant-custom-component` 0.13.355) |
| Testinstance `ha-dev` (`:stable`) | 3.14 | 2026.8.x |

**Dit was vijf maanden verschil en dat is nu weg.** Op Python 3.13 loste pip
`pytest-homeassistant-custom-component` 0.13.316 op met HA 2026.2.3, terwijl de klant
2026.7 draaide. Vanaf 0.13.317 vereist het harnas Python ≥ 3.14 en HA 2026.8 zelf ≥ 3.14.2,
dus de twee hingen aan elkaar.

Het besluit van 2026-08-05 was om te wachten tot 2026.8 stabiel was, en niet tegen een bèta
te testen. **2026.8.0 kwam op 5 augustus, 2026.8.1 op 7 augustus**; de overstap is op 9
augustus gedaan en kostte **geen enkele codewijziging** — 646 tests groen op de eerste
poging, en de 131 waarschuwingen komen allemaal uit Home Assistant zelf, niet uit ons.

**Wat dit niet verandert:** de ondergrond blijft HA 2025.6 (`hacs.json`). Testen tegen de
nieuwste release is hoe je deprecaties vroeg ziet; de ondergrens bewaak je door de
API-tabel in SPEC.md §0 na te lopen, niet met deze workflow.

**Wat dit wel verandert:** groene CI zegt nu iets over de HA-versie die de klant draait. Dat
was hiervoor niet zo, en het is precies waarom
[de browserroutes](#frontendtests-javascript) bestaan — de `ha-input`-wissel die route 1
vond, was op 2026.2.3 niet te zien.

**`requires-python` in `pyproject.toml` gaat over het testgereedschap, niet over de
integratie.** Er wordt geen Python-pakket gedistribueerd (`packages = []`); Home Assistant
laadt `custom_components/` rechtstreeks.


### Verificatie tegen de draaiende HA

`scripts/ha_check.py` leest via de REST-API de zes entiteiten uit de testinstance en kan
een `input_number` zetten om een herberekening te forceren. Het leest `HA_URL` en
`HA_TOKEN` uit `.env` in de repo-root (**staat in `.gitignore`, nooit committen**).

```powershell
py -3.13 .\scripts\ha_check.py                 # toon de zes entiteiten
py -3.13 .\scripts\ha_check.py --set -5700     # zet de netmeter en toon opnieuw
py -3.13 .\scripts\ha_check.py --json          # ruwe states, om zelf door te spitten

# WebSocket-commando's, eventueel als een andere gebruiker
py -3.13 .\scripts\ha_check.py --ws domotiapp_energy/config/get
py -3.13 .\scripts\ha_check.py --ws domotiapp_energy/config/get --as READONLY
```

`--as SUFFIX` pakt `HA_TOKEN_<SUFFIX>` uit `.env`, zodat de rechtencontrole met een
niet-admin token aantoonbaar is. `--ws` verstuurt uitsluitend `domotiapp_energy/*` en
`auth/current_user`; dat laatste om te bewijzen bij wélke gebruiker een token hoort.

### Een payload meegeven: gebruik `--field`, niet `--data`

JSON tussen aanhalingstekens is vanuit Windows PowerShell 5 vrijwel niet te typen: enkele
quotes, ingesloten dubbele quotes en regeleindes vechten met elkaar. **Gebruik daarom
`--field key=value`**, herhaalbaar, met een punt voor nesting. Er komt dan geen JSON aan
te pas. Elke waarde wordt als JSON gelezen wanneer dat kan (`3`, `true`, `null`) en
anders als tekst, dus alleen een waarde mét spatie heeft nog aanhalingstekens nodig.

Onderstaand voorbeeld is precies zo in PowerShell uitgevoerd (geverifieerd 2026-08-06):

```powershell
py -3.13 .\scripts\ha_check.py --ws domotiapp_energy/sources/create `
    --field expected_revision=12 `
    --field source.id=prijs `
    --field source.type=current_price `
    --field source.name="Dynamische prijs" `
    --field source.price_basis=market `
    --field source.entity_id=input_number.stroomprijs `
    --field source.unit=EUR/kWh
```

Twee hulpmiddelen erbij:

- **`--dry-run`** print het frame dat verstuurd zou worden en stopt. Het leest `.env`
  niet en heeft geen draaiende instance nodig, dus het is de snelste manier om te
  controleren of een aanroep goed quoteert vóór je hem echt afvuurt.
- **`--data-file PAD`** leest de payload uit een bestand (`-` is stdin), voor een grote
  payload of om er één met `--field` op aan te passen. Een UTF-8 BOM is toegestaan, want
  dat is wat `Set-Content -Encoding UTF8` in PowerShell 5 schrijft.

`--data '<json>'` bestaat nog voor bash, maar is in PowerShell de weg van de minste
weerstand niet.

**Dit is een verificatiehulpmiddel, geen vervanging van de testsuite.** Een fase is pas
klaar wanneer `pytest` slaagt; dit script vangt wat de testharnas per definitie niet ziet
(een andere HA-versie, een andere UI-taal, echte entiteiten). De entity-ID-fout van
fase 5 stond groen in de tests terwijl de werkelijkheid afweek — dat is precies waar dit
script voor is.

Het script gebruikt uitsluitend de standaardbibliotheek en voegt **niets** toe aan
`custom_components/` of aan de runtime-requirements. Zet er geen productielogica in.

## Testomgeving

Er draait een Home Assistant-testinstance in Docker met
`custom_components/domotiapp_energy` als bind-mount. Na een codewijziging herstart de
ontwikkelaar die container handmatig; je hoeft dat niet zelf te doen, maar meld het
wel wanneer een wijziging een herstart vereist.

## Stijl van samenwerken

- Meld het expliciet wanneer je van `SPEC.md` afwijkt, en waarom.
- Verzin geen ontbrekende waarden: als een noodzakelijke technische keuze ontbreekt in
  `SPEC.md`, stel één gerichte vraag.
- Rapporteer eerlijk wat nog niet werkt. Een lijst met open punten is waardevoller
  dan een claim dat alles af is.
- Geen "voor de volledigheid" toegevoegde features die niet in `SPEC.md` staan.
