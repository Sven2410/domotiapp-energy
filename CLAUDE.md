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

`pytest` kan geen JavaScript uitvoeren. De paneelcode heeft daarom een eigen testlaag:
jsdom plus de ingebouwde testrunner van Node.

```powershell
npm install     # eenmalig
npm test        # tests/frontend/*.test.mjs
```

**Dit is de enige dev-dependency van het project en raakt de integratie niet.**
`custom_components/` verscheept geen JavaScript-afhankelijkheden en heeft geen buildstap
(CLAUDE.md-regel 5); `package.json` bestaat uitsluitend voor deze tests.

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
een niet-string waarde dragen) en toets de control zelf in de browser.

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

### Versieverschil tussen tests en de draaiende HA (bewuste keuze, niet oplossen)

| | Python | Home Assistant |
|---|---|---|
| Testcontainer en CI | 3.13 | 2026.2.3 (via `pytest-homeassistant-custom-component` 0.13.316) |
| Testinstance `ha-dev` (`:stable`) | 3.14.6 | 2026.7.4 |

De testharnas pint HA; wij kiezen die versie niet. Vanaf 0.13.317 vereist
`pytest-homeassistant-custom-component` **Python ≥ 3.14**, en HA 2026.8 zelf vereist
≥ 3.14.2. Op Python 3.13 lost pip daarom 0.13.316 met HA 2026.2.3 op — vijf maanden
ouder dan wat de klant draait. Op Python 3.14 lost dezelfde `pyproject.toml` 0.13.353
met HA 2026.8.0b5 op en slaagt de hele suite ongewijzigd (geverifieerd 2026-08-05).

**Besluit van Sven, 2026-08-05: we blijven op 3.13.** Overstappen betekent testen tegen
een HA-bèta, en een bug in die bèta kost uren zoeken in code die niets mankeert.
**Heroverwegen zodra HA 2026.8 stabiel is** — stel het dan voor, voer het niet
stilzwijgend door in een fase.

**Groene CI bewijst daarmee geen 3.14-gedrag**, en ook geen gedrag van de HA-versie die
de klant draait. Wat een fase écht in HA doet, controleer je met de verificatieroute
hieronder.

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
