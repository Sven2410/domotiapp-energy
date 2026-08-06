# DomotiApp Energy — Implementatiespecificatie v0.1.0

> **Gebruiksaanwijzing:** commit dit bestand als `SPEC.md` in de root van de repo.
> Stuur Claude Code daarna deze kickoff:
>
> ```
> Lees SPEC.md volledig. Maak een kort uitvoeringsplan, inspecteer de repo en bouw
> vervolgens de MVP in de fases uit sectie 30. Commit per fase en draai na elke fase
> de tests. Stel alleen een vraag als een absoluut noodzakelijke technische waarde
> ontbreekt; gebruik anders de aannames uit SPEC.md. Stop niet bij lege bestanden.
> ```

---

## 0. Doelomgeving (vaststaand)

```text
Minimale Home Assistant-versie : 2025.6
Python (testroute)              : 3.13
Doelbrowsers                    : evergreen (Chrome/Safari/Firefox), incl. HA companion app
Licentie                        : MIT
```

**De doelomgeving loopt vóór op de testroute.** Een klant die vandaag de HA-container
`:stable` draait, zit op Python 3.14 met HA 2026.7; de testsuite draait op Python 3.13
met HA 2026.2.3. Dat is geen keuze van ons: `pytest-homeassistant-custom-component`
vereist vanaf 0.13.317 Python ≥ 3.14, en HA 2026.8 zelf ≥ 3.14.2, dus op 3.13 kan pip
niets nieuwers oplossen. Op 3.14 slaagt dezelfde suite ongewijzigd, maar tegen een
HA-bèta — en een bug in die bèta kost meer tijd dan hij oplevert. Bewuste keuze op
2026-08-05: blijven op 3.13 tot HA 2026.8 stabiel is. Zie CLAUDE.md, waar ook staat wat
groene CI daarmee wél en niet bewijst.

Alle gebruikte API's moeten bestaan in HA 2025.6 en niet deprecated zijn in de meest
recente HA-release. Controleer bij twijfel de actuele developer docs en documenteer de
keuze in een codecommentaar.

> **Wijziging t.o.v. v0.1.0 van deze spec:** de minimumversie is verhoogd van 2024.12 naar
> 2025.6. De testsuite draait tegen de nieuwste HA die
> `pytest-homeassistant-custom-component` meebrengt, niet tegen 2025.6; dat verschil is
> bewust en staat gedocumenteerd in `.github/workflows/tests.yml`. Elke API in de tabel
> hieronder is geverifieerd aanwezig in de wheel van `homeassistant==2025.6.0`.

Verplicht te gebruiken (niet de oudere varianten):

| Doel | Te gebruiken API |
|---|---|
| Static files | `await hass.http.async_register_static_paths([StaticPathConfig(...)])` |
| Paneel registreren | `panel_custom.async_register_panel(...)` |
| Paneel verwijderen | `frontend.async_remove_panel(hass, PANEL_URL_PATH)` |
| Entry-data | `entry.runtime_data` (typed `ConfigEntry` alias), **niet** `hass.data[DOMAIN]` |
| Platforms | `async_forward_entry_setups` / `async_unload_platforms` |
| State-listener | `async_track_state_change_event` |
| Periodiek | `async_track_time_interval` |
| Debounce | `homeassistant.helpers.debounce.Debouncer` |
| Opslag | `homeassistant.helpers.storage.Store` (subclass met `_async_migrate_func`) |
| Tijd/tijdzone | `homeassistant.util.dt` (`dt_util.now()`, `dt_util.utcnow()`) — **nooit** `datetime.now()` |
| WS-admincheck | `@websocket_api.require_admin` |

---

## 1. Productdoel

DomotiApp Energy is een **handmatig configureerbare** energiecoach voor woningen met
Home Assistant. De installateur koppelt zelf bronnen, apparaten, grenzen en voorkeuren.
De backend produceert daaruit een energiesamenvatting, datakwaliteitsscore, energiescore,
adviezen, piekwaarschuwingen en uitleg.

Deze versie gebruikt **geen externe AI-provider**: een lokale, deterministische regelmotor
met tekstsjablonen. De architectuur moet later een LLM-provider kunnen toevoegen zonder
de rekenmotor te herschrijven.

---

## 2. Niet-onderhandelbare uitgangspunten

### 2.1 Geen automatische herkenning
De integratie mag nooit zelfstandig entiteiten zoeken, apparaten herkennen, koppelingen
voorstellen, op naam matchen, het device-/entityregister doorzoeken op kandidaten, of een
discoveryflow starten. Alle koppelingen worden expliciet door de installateur gekozen.
De GUI mag uiteraard de normale HA entity-selector tonen (eventueel gefilterd op domein).

### 2.2 Geen aansturing in de MVP
Uitsluitend meten, berekenen, adviseren, uitleggen, waarschuwen. Geen enkele
`hass.services.async_call` naar een ander domein. Het datamodel legt wel `control_mode`
vast; de backend forceert in 0.1.0 alles behalve `monitor_only` naar `advice_only`.

### 2.3 Geen cloud
Geen externe API, AI-dienst, cloudopslag, telemetry, analytics, tracking, licentieserver,
account, API-sleutel of internetverbinding. Alles lokaal.

### 2.4 Geen YAML-configuratie
Volledig via de UI configureerbaar.

---

## 3. Projectidentiteit

```text
Naam            : DomotiApp Energy
Domein          : domotiapp_energy
Versie          : 0.1.0
GitHub-eigenaar : Sven2410
Repository      : https://github.com/Sven2410/domotiapp-energy
UI-taal         : Nederlands
README-taal     : Engels
```

`manifest.json`:

```json
{
  "domain": "domotiapp_energy",
  "name": "DomotiApp Energy",
  "codeowners": ["@Sven2410"],
  "config_flow": true,
  "dependencies": ["http", "frontend", "panel_custom", "websocket_api"],
  "documentation": "https://github.com/Sven2410/domotiapp-energy",
  "integration_type": "service",
  "iot_class": "calculated",
  "issue_tracker": "https://github.com/Sven2410/domotiapp-energy/issues",
  "requirements": [],
  "single_config_entry": true,
  "version": "0.1.0"
}
```

**De sleutelvolgorde is niet vrij.** Hassfest eist `domain`, dan `name`, dan de overige
sleutels alfabetisch, en faalt de CI met
`[MANIFEST] Manifest keys are not sorted correctly` bij elke andere volgorde. Houd deze
volgorde aan bij het toevoegen van een sleutel; groepeer niet op onderwerp.

> **Wijziging t.o.v. eerdere spec:** `integration_type` is `"service"`, niet `"helper"`.
> Helpers verschijnen onder *Instellingen → Apparaten & diensten → Helpers* en niet in de
> "Integratie toevoegen"-dialoog; dat botst met acceptatiecriterium 1 en met het eigen
> device in het device registry.

Geen externe runtime-Pythonpackages.

---

## 4. Repositorystructuur

```text
domotiapp-energy/
├── custom_components/domotiapp_energy/
│   ├── __init__.py
│   ├── manifest.json
│   ├── const.py
│   ├── config_flow.py
│   ├── models.py
│   ├── storage.py
│   ├── validators.py
│   ├── coordinator.py
│   ├── panel.py
│   ├── websocket_api.py
│   ├── sensor.py
│   ├── binary_sensor.py
│   ├── services.yaml
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── calculator.py
│   │   ├── advisor.py
│   │   ├── completeness.py
│   │   ├── reason_codes.py
│   │   └── providers.py
│   ├── frontend/
│   │   ├── domotiapp-energy-panel.js      # entrypoint
│   │   ├── core/  (state.js, api.js, dom.js, tap.js, forms.js)
│   │   └── tabs/  (overview.js, home.js, sources.js, devices.js,
│   │               preferences.js, coach.js, logbook.js)
│   └── translations/
│       ├── nl.json
│       └── en.json
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_config_flow.py
│   ├── test_storage.py
│   ├── test_validators.py
│   ├── test_calculator.py
│   ├── test_advisor.py
│   ├── test_websocket_api.py
│   └── test_entities.py
├── .github/workflows/{validate.yml,tests.yml}
├── .gitignore
├── hacs.json
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── SPEC.md
└── LICENSE            # MIT, houder: Sven2410
```

**Frontend splitsen is verplicht.** Eén JS-bestand voor zeven tabbladen wordt onwerkbaar
groot. Gebruik native ES-modules met relatieve imports; de hele `frontend/`-map wordt als
static path geserveerd, dus `import { x } from './core/state.js'` werkt.

Geen `strings.json`. Volledige vertalingen in `translations/nl.json` en `translations/en.json`
(inclusief de `services:`-sectie voor servicevertalingen). Geen verzonnen logo of brand-map.

---

## 5. HACS

`hacs.json`:

```json
{
  "name": "DomotiApp Energy",
  "render_readme": true,
  "homeassistant": "2025.6.0"
}
```

Alles wat nodig is om te draaien staat in `custom_components/domotiapp_energy/`,
inclusief de frontend.

**Workflows:**

- `validate.yml`: `home-assistant/actions/hassfest@master` **en** `hacs/action@main` met
  `category: integration` en `ignore: brands`.
  De brands-check faalt altijd voor een custom integration die niet in
  `home-assistant/brands` is opgenomen — vandaar de ignore. Documenteer dit in de workflow.
- `tests.yml`: Python 3.13, `pip install -e ".[dev]"`, `ruff check`, `ruff format --check`,
  `pytest --cov`.

---

## 6. Config flow

Eén stap, één entry.

Velden:
- `home_name` (tekst, default `Mijn woning`)
- `manual_setup_acknowledged` (boolean, moet `true` zijn om door te gaan)

Beschrijvingstekst (nl.json):

```text
DomotiApp Energy configureert geen apparaten automatisch. Na het toevoegen van de
integratie kun je via het DomotiApp Energy-paneel zelf energiebronnen, apparaten en
voorkeuren koppelen.
```

Eisen:
- `single_config_entry: true` regelt de abort bij een tweede entry (`single_instance_allowed`)
  — **schrijf hiervoor geen eigen check**, test wel dat het gedrag klopt.
- Options flow of `async_step_reconfigure` voor de woningnaam. Kies één van beide en
  gebruik die consequent; bij wijziging moet de naam ook in de storage worden bijgewerkt
  en het device in het device registry worden hernoemd.
- Correct unloaden en herladen (`async_unload_entry`, `async_reload_entry`).
- Woningnaam staat in `entry.data`/`entry.options`; de uitgebreide configuratie in de
  storage helper. Bij conflict is de storage leidend voor alles behalve de naam.

De uitgebreide configuratie hoort **niet** in de config flow.

---

## 7. Zijpaneel

```text
Titel : DomotiApp Energy
Icoon : mdi:home-lightning-bolt
Pad   : domotiapp-energy
```

Volgorde in `async_setup_entry`:

1. Registreer static path voor `frontend/` (idempotent, module-level guard).
2. `panel_custom.async_register_panel(...)` met:
   - `webcomponent_name="domotiapp-energy-panel"`
   - `module_url="/domotiapp_energy_frontend/domotiapp-energy-panel.js?v=0.1.0"`
     — de `?v=`-querystring is **verplicht** tegen agressieve frontendcaching; koppel hem
     aan de versie in `const.py`.
   - `require_admin=False` (niet-admins krijgen read-only tabbladen; de backend beveiligt
     de schrijfacties)
   - `embed_iframe=False`
3. Bij unload/verwijderen: `frontend.async_remove_panel(hass, PANEL_URL_PATH)`.

Voorkom dubbele registratie bij reload.

---

## 8. GUI-indeling

Tabbladen: `Overzicht`, `Woning`, `Energiebronnen`, `Apparaten`, `Voorkeuren`,
`Energiecoach`, `Logboek`.

### Overzicht
Status integratie · datakwaliteit (%) · energiescore (0–100) · actueel netvermogen ·
zonneproductie · zonneoverschot · percentage van max. netvermogen · **actuele
energieprijs** · hoofdadvies · waarschuwingen · aantal geconfigureerde apparaten ·
tijdstip laatste berekening. Duidelijke lege statussen wanneer nog niets is ingesteld.

**Actuele energieprijs (toegevoegd in fase 8b).** Het paneel toonde de prijs nergens,
terwijl de rekenmotor er wel mee rekent — dat was een gat in deze spec. Getoond wordt het
**all-in bedrag per kWh**, want dat is de enige prijssoort die voorbij de rekenmotor
bestaat (§16). Kwam die uit een bron met `price_basis = market`, dan staat de gebruikte
**marktprijs eronder** als hint, zodat de omrekening tegen de sensor te controleren is in
plaats van geloofd te moeten worden. Twee lege statussen, bewust van elkaar te
onderscheiden:

- vast contract → "Niet van toepassing bij een vast contract" — er ís geen uurprijs, en
  die komt er ook niet;
- dynamisch contract zonder bruikbare prijsbron → "Geen bruikbare prijsbron" — dit is wél
  iets om te gaan oplossen.

Daarvoor dragen `EnergySnapshot` en `EnergyMetrics` naast `current_price_eur_kwh` ook
`market_price_eur_kwh`: de ruwe meting, uitsluitend gevuld bij een marktprijsbron. Bij een
all-in bron is er niets extra's te tonen, want dan zijn beide getallen hetzelfde.

### Woning
- `home_name`
- `phases` — 1 of 3
- `main_fuse_a` — hoofdzekering per fase in ampère (1–100)
- `max_grid_power_w` — maximaal toegestaan netvermogen
- `peak_warning_percent` — waarschuwing vanaf % (default 80)
- `contract_type` — `fixed` | `dynamic`
- `fixed_import_price_eur_kwh` — het **all-in** bedrag per afgenomen kWh, inclusief
  energiebelasting en btw. Dit veld wordt niet omgerekend; de hulptekst zegt dat.
- `energy_tax_eur_kwh` — energiebelasting **per kWh**, exclusief btw
- `supplier_markup_eur_kwh` — opslag van de leverancier **per kWh**, exclusief btw. De
  veldhulptekst moet dat net zo expliciet zeggen als bij `feed_in_cost_eur_kwh`:
  verschillende contracten rekenen een vast maandbedrag, en dat is hier niet de
  bedoeling. Mag negatief zijn — een korting is een echt contract.
- `vat_percent` — default `21`. Een veld en geen constante, om dezelfde reden als
  `net_metering_until` een datum is: het tarief verandert, en dat mag geen release kosten.
- `feed_in_price_eur_kwh` — het vaste **all-in** bedrag dat de klant per teruggeleverde
  kWh werkelijk vergoed krijgt. Geen marktprijs en geen percentage; dit veld wordt niet
  omgerekend. Een prijsbron voor teruglevering is een idee voor een volgende versie.
- `feed_in_cost_eur_kwh` — terugleverkosten **per kWh**. De veldhulptekst moet dat
  expliciet zeggen: verschillende leveranciers rekenen een vast maandbedrag per staffel,
  en dat is hier niet de bedoeling. Het advies gaat over één apparaatcyclus, dus alleen
  de marginale kosten zijn zinvol.
- `net_metering_until` — nullable datum, default `2027-01-01`. Zie §16.
- `low_price_threshold_eur_kwh` — **all-in**, zie §16
- `high_price_threshold_eur_kwh` — **all-in**, zie §16
- `min_solar_surplus_w` (default 500)
- `default_strategy` — `comfort` | `balanced` | `save` | `max_self_consumption`
- `control_level` — vast op `advice_only` in 0.1.0

**Alle prijsvelden zijn all-in (verplichte GUI-hulptekst).** De prijsgrenzen, het vaste
leveringstarief en de terugleververgoeding zijn bedragen inclusief energiebelasting en
btw, omdat de rekenmotor uitsluitend met all-in prijzen werkt (§16). De GUI toont dat in
het label van beide prijsgrenzen én één keer als toelichting bij de prijsvelden, met de
formule erbij. Zonder die tekst vult een installateur de grens in die zijn prijssensor
toont — een factor drie ernaast, zonder enige foutmelding.

**Relatie zekering ↔ max vermogen (expliciet vastleggen):**
theoretisch maximum = `phases × 230 V × main_fuse_a`.
De installateur vult `max_grid_power_w` zelf in; de GUI toont het theoretische maximum als
hint en toont een **waarschuwing (geen blokkade)** wanneer `max_grid_power_w` daarboven
ligt. Berekeningen gebruiken uitsluitend `max_grid_power_w`.

Andere bedieningsniveaus mogen als disabled toekomstige opties zichtbaar zijn, met de
tekst dat ze nog niet beschikbaar zijn.

### Energiebronnen
Types: `grid_meter`, `solar`, `current_price`, `price_forecast`, `solar_forecast`,
`home_battery`, `general_consumption`.

Velden:

```text
id (uuid4) · name · type · enabled · entity_id · value_source · attribute_name
unit · scale_factor · invert_value · notes
capabilities · control_forbidden · control_forbidden_reason
```

De laatste drie staan óók op een bron en niet alleen op een apparaat. Een omvormer die
uitgelezen én begrensd kan worden (SolarEdge) is in dit model een bron; zonder deze
velden zou hij twee keer ingevoerd moeten worden, als bron én als apparaat, op één stuk
hardware. Zie §12 voor wat de velden betekenen.

- `value_source` ∈ `state` | `attribute`; `attribute_name` alleen zichtbaar bij `attribute`.
- **Toegestane `unit`-waarden** (enum, geen vrije tekst):
  `W`, `kW`, `A`, `Wh`, `kWh`, `EUR/kWh`, `ct/kWh`, `%`, `none`.
  Conversie gebeurt uitsluitend op basis van deze expliciete keuze plus `scale_factor`.
  Nooit converteren op basis van de HA-`unit_of_measurement` of de entiteitsnaam.
- `scale_factor` default `1.0`, moet `> 0`.

Voor `grid_meter` extra:

```text
meter_mode        : single_signed | separate_import_export
positive_means    : import | export        (alleen bij single_signed)
import_entity_id  : (alleen bij separate_import_export)
export_entity_id  : (alleen bij separate_import_export)
```

Deze keuze wordt expliciet opgeslagen. Nooit afleiden of gokken.

Voor `current_price` extra:

```text
price_basis : all_in | market
```

**Even streng als `meter_mode`, en zonder default.** Een prijssensor kan de kale
marktprijs melden of de all-in prijs die de klant betaalt; in Nederland scheelt dat
ongeveer een factor drie (≈ € 0,08 tegen ≈ € 0,25). Wie dat niet vastlegt, laat de
rekenmotor gokken op de belangrijkste vergelijking die hij maakt. Is `price_basis` niet
gekozen, dan is de bron **onbruikbaar**: geen prijs, `reason_code =
missing_required_data`, en de rij telt als `invalid_item` in de datakwaliteit. Een
bestaande prijsbron valt daarmee uit tot iemand de keuze maakt — dat is het eerlijke
gedrag, want die informatie ontbrak werkelijk. Zie §16 voor de omrekening zelf.

`grid_meter` en `current_price` mogen hoogstens één ingeschakelde bron per type hebben;
zie §16 voor wat er gebeurt wanneer er toch meerdere staan.

**Tekenconventie thuisbatterij (verplichte GUI-hulptekst, fase 8).** Intern geldt voor
`home_battery`: **positief = laden** (de woning verbruikt), negatief = ontladen. Dit
spiegelt de netconventie. Batterijsensoren verschillen sterk per merk — sommige melden
laden juist als negatief — dus het formulier voor een batterijbron moet deze conventie
expliciet noemen, met de aanwijzing `invert_value` te gebruiken wanneer de sensor het
andersom rapporteert. Zonder die tekst gokt de installateur, en een verkeerd teken haalt
het zonneoverschot stilzwijgend onderuit.

### Apparaten
Lijst met naam · type · configuratiestatus · prioriteit · bedieningsniveau ·
datakwaliteit · bewerken · verwijderen.

Types: `ev_charger`, `home_battery`, `heat_pump`, `electric_boiler`, `dishwasher`,
`washing_machine`, `dryer`, `air_conditioning`, `pool_pump`, `generic_schedulable`,
`generic_monitor`.

Gemeenschappelijk basismodel met type-specifieke velden; niet elk type heeft in 0.1.0
een eigen algoritme.

Algemene velden:

```text
id (uuid4) · name · device_type · enabled · priority · location · control_mode
nominal_power_w · energy_per_cycle_kwh · duration_minutes
earliest_start · latest_finish · days_of_week · notes
capabilities · control_forbidden · control_forbidden_reason
```

- `earliest_start` / `latest_finish`: samen een tijdvenster. Een `latest_finish` die
  eerder valt dan `earliest_start` betekent een venster over middernacht (zie §16).
- `priority` ∈ `low` | `normal` | `high` | `critical`
- `control_mode` ∈ `monitor_only` | `advice_only` | `approval_required` | `automatic`
  → backend behandelt in 0.1.0 alles behalve `monitor_only` als `advice_only`
- **Extra veld:** `is_noisy` (boolean, default afhankelijk van type: true voor
  `washing_machine`, `dryer`, `dishwasher`, `pool_pump`). Zonder dit veld is de
  stille-urenregel niet implementeerbaar.
- **Extra veld:** `is_flexible` (boolean) — bepaalt of het apparaat in aanmerking komt voor
  verplaatsingsadvies. Default true voor de schakelbare types, false voor
  `generic_monitor` en `heat_pump`.

Optionele entiteitskoppelingen (mogen ontbreken, nooit lege string):

```text
status_entity · power_entity · energy_entity · remaining_time_entity
temperature_entity · battery_level_entity
```

Gebruik `null` of laat het veld weg. Nooit `""`.

### Voorkeuren

```text
quiet_hours_start · quiet_hours_end · allow_advice_during_quiet_hours
prefer_solar · prefer_low_price · respect_max_grid_load
min_savings_eur · max_advice_count (1–5)
show_technical_explanation · show_estimated_savings · show_confidence
```

**Verduidelijking `min_savings_eur`:** deze drempel filtert **uitsluitend** adviezen
waarvoor een `estimated_savings_eur` is berekend **die boven nul uitkomt**. Twee soorten
advies blijven altijd staan:

- advies zonder berekenbare besparing (veiligheid, piek, ontbrekende data, neutraal),
  want daar zegt de drempel niets over;
- advies waarvan de besparing op nul of lager uitkomt. Dat is een andere uitspraak: de
  reden om het apparaat nu te draaien geldt onverkort, er valt alleen niets extra's te
  verdienen. Onder saldering is dat het normale geval, en wegfilteren zou het paneel een
  jaar lang bijna stil maken terwijl het advies volkomen juist is.

De drempel geldt dus voor precies één situatie: er zit geld in, maar te weinig om de
klant mee lastig te vallen.

### Energiecoach
Huidige situatie · hoofdadvies · max. vijf aanvullende adviezen · reden per advies ·
relevante meetwaarden · geschatte besparing indien berekenbaar · betrouwbaarheid
(`low`/`medium`/`high`) · ontbrekende gegevens · knop `Opnieuw berekenen`.

Geen vrije chat. Wel een lokale vraagselector:

```text
Waarom krijg ik dit advies?
Kan ik nu het beste een apparaat gebruiken?
Is er risico op piekbelasting?
Welke gegevens ontbreken nog?
Hoe is mijn energiescore berekend?
```

Antwoorden komen uitsluitend uit gestructureerde backendresultaten
(`CoachResult.explanations: dict[str, str]`, gevuld door de backend). De frontend
concludeert nooit zelf.

### Logboek
Max. 200 gebeurtenissen. Types: `config_changed`, `device_added`, `device_removed`,
`advice_recalculated`, `source_unavailable`, `invalid_measurement`, `peak_risk_detected`,
`solar_surplus_detected`, `invalid_configuration`.

> `invalid_configuration` is toegevoegd t.o.v. de oorspronkelijke acht types. Een
> opgeslagen bron of apparaat met een onbekend type is een configuratieprobleem — geen
> beschikbaarheidsprobleem (`source_unavailable`) en geen ongeldige meting
> (`invalid_measurement`). Zie §12 voor de omgang met zulke rijen.

Toon: tijd · type · titel · korte omschrijving · ernst (`info`/`warning`/`error`/`success`).
Nooit volledige HA-stateobjecten opslaan. Knop "Logboek wissen", alleen voor admins.

**Anti-spam:** identieke opeenvolgende gebeurtenissen (zelfde type + zelfde subject) binnen
15 minuten worden niet opnieuw gelogd maar verhogen een `count`-veld op de laatste regel.
Zonder deze regel loopt het logboek bij elke herberekening vol.

---

## 9. GUI-techniek

### ha-form
Alle invoerformulieren gebruiken `ha-form` met een schema. Geen losse `ha-entity-picker`,
`ha-select`, `ha-textfield` of `ha-switch` als primaire besturing. Selectors: `entity`,
`number`, `boolean`, `select`, `text`, `time`, `date`.

> `date` is toegevoegd t.o.v. de oorspronkelijke lijst: `net_metering_until` uit §8 is een
> datum, en die in een tekstveld laten invullen levert precies de invoerfouten op die een
> selector voorkomt.

Label en hulptekst staan in het schema zelf (`label` en `helper` per veld, uitgelezen via
`computeLabel` en `computeHelper`), zodat een veld en de woorden die het uitleggen niet op
twee plaatsen kunnen gaan afwijken.

```javascript
form.hass = this._hass;
form.schema = schema;
form.data = data;
```

Eén `value-changed`-listener per formulierinstantie. Formulier niet opnieuw aanmaken bij
elke `hass`-update.

### Geen entityvoorstellen
Entity-selector mag alle HA-entiteiten tonen, eventueel gefilterd op domein. Geen eigen
zoek-, score-, detectie- of suggestielogica.

### DOM
`attachShadow({ mode: 'open' })`. Vaste DOM eenmalig via `_buildDOM()`, daarna alleen
waarden en zichtbaarheid via `_updateDOM()`. Nooit de volledige `innerHTML` opnieuw zetten.
Voor dynamische lijsten gericht items toevoegen/wijzigen/verwijderen op basis van `id`.

### Registratie

```javascript
if (!customElements.get('domotiapp-energy-panel')) {
  customElements.define('domotiapp-energy-panel', DomotiAppEnergyPanel);
}

console.info(
  '%c DOMOTIAPP ENERGY %c v0.1.0 ',
  'background: var(--primary-color); color: white; font-weight: bold;',
  'background: transparent; color: inherit;'
);
```

Het paneelelement ontvangt van HA de properties `hass`, `narrow`, `route`, `panel`.
Implementeer `set hass(hass)` en bewaar in `this._hass`.

### Geen externe libraries
Geen CDN-imports, geen React, geen build-stap. Native ES-modules en bestaande
HA-componenten.

### Communicatie
`this._hass.callWS(...)` voor de eigen WebSocket-API. `this._hass.callService(...)`
alleen wanneer later een echte HA-service nodig is. Nooit directe `fetch` naar HA.
Geen `localStorage`, `sessionStorage`, `IndexedDB` of cookies. De backendopslag is de
enige bron van waarheid.

---

## 10. Stijl

Uitsluitend themavariabelen:

```css
var(--primary-color) var(--primary-text-color) var(--secondary-text-color)
var(--divider-color) var(--card-background-color) var(--secondary-background-color)
var(--error-color) var(--warning-color) var(--success-color)
```

De DomotiTech-accentkleur `#026FA1` staat in het HA-thema en wordt **nooit** hardcoded.
De gebruiker heeft een Liquid Glass-thema dat automatisch op `ha-card` wordt toegepast:
geef `ha-card` daarom zelf geen `background`, `border-radius`, `box-shadow` of
`backdrop-filter`, tenzij strikt nodig voor een genest element.

`ha-card` voor hoofdsecties. Alle zichtbare teksten Nederlands. Professioneel en
klantgeschikt.

---

## 11. Mobiel en desktop

Responsive, één kolom smal, meerdere kolommen op desktop waar nuttig, max. contentbreedte
~1400 px gecentreerd, taphoogte ≥ 44 px, voldoende tussenruimte,
`env(safe-area-inset-bottom)`, geen horizontale scroll, dialogs met desktop-`max-width`,
bevestiging vóór verwijderen van een bron of apparaat.

```css
touch-action: manipulation;
-webkit-tap-highlight-color: transparent;
```

Centrale tap-helper: een tik telt alleen bij ≤ 8 px beweging. Nooit gegevens opslaan bij
`touchstart`.

---

## 12. Backendgegevensmodel

Getypeerde dataclasses met `slots=True`. Minimaal:

```text
HomeProfile · EnergySource · EntityBinding · DeviceProfile · UserPreferences
EnergySnapshot · EnergyMetrics · AdviceItem · CoachResult · LogEntry
StoredConfiguration
```

Elk model krijgt `to_dict()` en `from_dict()` met defensieve defaults; `from_dict` negeert
onbekende sleutels en herstelt ontbrekende velden naar de default in plaats van te crashen.

**Uitzondering: onbekend bron- of apparaattype.** Een `type`/`device_type` dat niet in de
toegestane lijst staat wordt **niet** naar een default gedegradeerd. Een corrupte
`grid_meter` die als `general_consumption` terugkomt, zou als huishoudelijk verbruik de
zonneoverschotformule in gaan — precies het gokken dat §2.1 verbiedt, alleen onzichtbaar.
In plaats daarvan blijft de rij bestaan en geldt:

- het opgeslagen type blijft ongewijzigd staan;
- `enabled` wordt op `false` gezet;
- de rij krijgt `invalid_reason = "unknown_type"`, zodat de rekenmotor hem nooit gebruikt
  en de datakwaliteit hem als `invalid_item` telt;
- er wordt een logregel geschreven met ernst `warning` en type `invalid_configuration`.

```python
@dataclass(slots=True)
class AdviceItem:
    id: str
    title: str
    message: str
    severity: str
    reason_code: str
    confidence: str
    recommended_time: str | None = None
    estimated_savings_eur: float | None = None
    related_device_ids: list[str] = field(default_factory=list)
    measurements: dict[str, float | str] = field(default_factory=dict)
```

**Drie soorten waarheid over aansturing, die niet door elkaar mogen lopen.** Ze staan
zowel op `EnergySource` als op `DeviceProfile`:

| Veld | Beschrijft | Soort waarheid |
|---|---|---|
| `capabilities` | wat de hardware kán | eigenschap van het apparaat |
| `control_mode` | wat de installateur wíl | intentie |
| `control_forbidden` (+ `_reason`) | wat is afgesproken met déze klant | afspraak |

`capabilities` is een lijst uit de vaste verzameling `read`, `switch`,
`set_power_limit`, `set_current`. Een lege lijst betekent *niet opgegeven*, niet *kan
niets*. Een token dat niet in de verzameling staat wordt weggegooid — anders zou de lijst
beweren dat er iets gecontroleerd is wat niet gecontroleerd is. Dat wijkt bewust af van
de behandeling van een onbekend `type`, dat juist bewaard blijft: een onbekend type
beschrijft een rij die bestaat, een onbekende capability beschrijft niets waar we ooit
op kunnen handelen.

**In 0.1.0 zijn deze velden puur registrerend**: er wordt niets aangestuurd (§2.2). Ze
staan er nu omdat ze in de formulieren van fase 8 horen en later toevoegen betekent bij
elke klant elk apparaat opnieuw langslopen.

**Wat een schrijfactie weigert, en wat niet (vastgelegd in fase 8a).** De WebSocket-API
weigert een rij **uitsluitend** bij `control_forbidden = true` in combinatie met een
aansturende `control_mode`. Al het andere dat de validatie vindt reist mee als `issue`
(§14) en wordt gewoon opgeslagen.

Dat onderscheid is bewust en mag later niet als inconsistentie worden "opgelost":

- **Half ingevuld is normaal werk.** Een installateur vult in een meterkast gaandeweg in.
  Een netmeter zonder metermodus levert een issue met ernst `error` op — de rekenmotor
  gebruikt hem niet — maar moet als tussenstand op te slaan zijn. Zou elke `error` de
  opslag blokkeren, dan is een halve rij niet te bewaren en gaat het werk verloren zodra
  iemand het formulier sluit.
- **Een afspraak mag niet sneuvelen.** `control_forbidden` legt vast wat met déze klant is
  afgesproken. Een `control_mode` die aanstuurt is een intentie die iemand later uit een
  dropdown kiest. De afspraak gaat daar boven, dus dit is het enige geval waarin de
  backend nee zegt, met foutcode `invalid_format`.

Op een `EnergySource` kan die blokkade vandaag niet afgaan: §8 geeft een bron wél
`control_forbidden` en `capabilities`, maar géén `control_mode`, dus er is geen intentie
die de afspraak kan tegenspreken. De controle is voor beide modellen geschreven en gaat
vanzelf gelden zodra een bron een eigen intentie krijgt.

Validatie kent hier één harde blokkade en twee waarschuwingen:

- `control_forbidden = true` met een `control_mode` die aanstuurt (`approval_required`
  of `automatic`) is een **fout**, geen waarschuwing. Een afspraak om iets niet aan te
  raken gaat boven elke intentie die iemand later invult. Dit is de enige harde blokkade
  in `validators.py`.
- Een aansturende `control_mode` zonder besturingscapability is een **waarschuwing**: de
  installateur beschrijft misschien hardware die hij gaat vervangen.
- `control_forbidden = true` zonder reden is een **waarschuwing**. Zonder die reden is de
  vlag over twee jaar onleesbaar, en dat is precies waar hij voor bestaat. De reden hoort
  zichtbaar te zijn in het apparaatoverzicht van fase 8.

Stabiele reason codes in `engine/reason_codes.py` (constants, geen losse strings):

```text
missing_required_data · solar_surplus_available · high_grid_load
high_grid_export · low_energy_price · high_energy_price
flexible_device_available · outside_allowed_window · quiet_hours_active
invalid_entity_state · insufficient_savings · neutral_energy_situation
```

> `high_grid_export` is toegevoegd t.o.v. de oorspronkelijke elf codes: overbelasting
> door teruglevering vraagt om het tegenovergestelde advies van overbelasting door
> afname. Zie §16.

UI-teksten worden opgebouwd op basis van deze codes. UUID4 voor handmatig toegevoegde
bronnen en apparaten.

---

## 13. Opslag

`Store` subclass, key `domotiapp_energy.config`, `version=1`, `minor_version=1`,
met een geïmplementeerde `_async_migrate_func(old_major_version, old_minor_version, old_data)`
die nu alleen de identiteitsmigratie doet maar de structuur klaarzet.

```json
{
  "schema_version": 1,
  "revision": 1,
  "home": {},
  "sources": [],
  "devices": [],
  "preferences": {},
  "logs": []
}
```

Eisen: versioned storage · migratiefunctie · max. 200 logregels (trimmen bij schrijven) ·
defensief laden · veilige defaults · geen secrets · geen kopieën van volledige entity
states · writes serialiseren met `asyncio.Lock` · frontend ontvangt de actuele revision ·
optimistic concurrency (zie §14).

**Wanneer de revision verandert.** De `revision` telt uitsluitend wijzigingen aan de
configuratie zelf — `home`, `sources`, `devices` en `preferences` — die voortkomen uit
een expliciete gebruikersactie. Zo'n wijziging verhoogt de revision met precies 1.

De volgende schrijfacties raken de revision **niet**:

- **Logboekschrijfacties.** Een regel toevoegen of het logboek wissen laat de revision
  ongemoeid. Dit is geen bug en moet niet als bug "gerepareerd" worden: de meeste
  logregels komen van de engine (`advice_recalculated`, `source_unavailable`,
  `invalid_configuration`), niet van de gebruiker. Zou zo'n achtergrondgebeurtenis de
  revision ophogen, dan verloopt de `expected_revision` die de frontend vasthoudt terwijl
  de gebruiker een formulier invult, en wordt een geldige opslagpoging geweigerd met
  `revision_conflict`. Het logboek valt niet onder wat `expected_revision` bewaakt.
- **Laden.** `async_load` schrijft niets, ook niet wanneer rijen in quarantaine gaan.
  Afgeleide toestand zoals `invalid_reason` wordt bij elke uitlezing uit het opgeslagen
  type berekend en nooit teruggeschreven (zie §12).
- **Herberekenen en overige achtergrondtaken.** Deze produceren runtime-resultaten, geen
  configuratie.

De woningnaam staat óók in de config entry; de uitgebreide configuratie in de storage.

**Verwijderen van de integratie wist de opgeslagen configuratie niet.**
`async_remove_entry` laat `.storage/domotiapp_energy.config` bewust staan: een
installateur die per ongeluk verwijdert, of die opnieuw installeert, wil niet twintig
apparaten opnieuw invoeren. De integratie opnieuw toevoegen pakt de configuratie weer op.

Dit mag niet stilzwijgend gebeuren, maar HA biedt er geen UI-haakje voor: `async_remove_entry`
is het enige aanknopingspunt en de endpoint achter de verwijderdialoog
(`DELETE /api/config/config_entries/entry/{id}`) geeft alleen `require_restart` terug.
Repairs en persistent notifications zouden zo'n melding wél kunnen dragen, maar staan in
§21 voor een latere release. Daarom: één INFO-logregel bij verwijderen die het pad noemt,
plus een troubleshooting-sectie in de README waarin staat hoe je bewust schoon begint.

---

## 14. WebSocket-API

Commando's:

```text
domotiapp_energy/config/get        domotiapp_energy/home/update
domotiapp_energy/sources/list      domotiapp_energy/sources/create
domotiapp_energy/sources/update    domotiapp_energy/sources/delete
domotiapp_energy/devices/list      domotiapp_energy/devices/create
domotiapp_energy/devices/update    domotiapp_energy/devices/delete
domotiapp_energy/preferences/get   domotiapp_energy/preferences/update
domotiapp_energy/coach/get         domotiapp_energy/coach/recalculate
domotiapp_energy/logs/list         domotiapp_energy/logs/clear
```

**Registreer alle commando's eenmalig in `async_setup`, niet in `async_setup_entry`.**
Registratie per entry breekt bij een reload.

**Optimistic concurrency (verplicht, ontbrak in de oorspronkelijke opdracht):**
elk schrijfcommando accepteert een verplicht veld `expected_revision: int`. Wijkt dit af
van de opgeslagen revision, dan wordt het verzoek geweigerd met foutcode
`revision_conflict` en de actuele configuratie meegestuurd, zodat de frontend kan
herladen. Zonder dit veld is de conflicttest uit §24 niet implementeerbaar.

Antwoordvorm van elk schrijfcommando: `{ "revision": <nieuw>, "item": <object|null> }`.

**Validatie-issues reizen mee (superset, vastgelegd in fase 8a).** Elk lees- én
schrijfantwoord krijgt er één sleutel bij:

```text
"issues": { "<subject>": [ {"field": "...", "code": "...",
                           "message": "...", "severity": "error"|"warning"} ] }
```

`<subject>` is `"home"`, `"preferences"` of het id van een bron of apparaat — precies de
sleutels die `validate_configuration` teruggeeft. De frontend zet elke melding daarmee bij
het veld waar hij over gaat (`ha-form.error`) in plaats van als één algemene zin.

De twee gedocumenteerde sleutels blijven ongewijzigd, dus een aanroeper die `issues`
negeert blijft werken. Het alternatief — een zeventiende commando `validate` — is
afgewezen: dat kost na élke opslag een tweede round trip, en precies die traagheid maakt
een formulier onprettig. De controle zelf is een handvol pure vergelijkingen over data die
al in het geheugen staat.

Foutcodes (consistent, in `const.py`):

```text
not_found · duplicate_id · invalid_format · revision_conflict
not_authorized · storage_error
```

Eisen: valideer elk request met Voluptuous · vertrouw nooit rechtstreeks op frontenddata ·
JSON-serialiseerbare resultaten · duidelijke loggerregels zonder woning- of persoonsdata.

Schrijfacties met `@websocket_api.require_admin`:

```text
home/update · sources/create · sources/update · sources/delete
devices/create · devices/update · devices/delete · preferences/update · logs/clear
```

Leesacties: elke ingelogde gebruiker. De frontend verbergt configuratietabbladen voor
niet-admins (`hass.user.is_admin`), maar de backend is altijd leidend.

**`coach/recalculate` blijft bewust open voor elke gebruiker**, ook al schrijft hij via de
coordinator een `advice_recalculated`-regel in het logboek. Een niet-admin kan daarmee
hooguit één regel per kwartier laten ontstaan — de anti-spam uit §8 klapt de rest samen —
en de alternatieven zijn slechter. Alleen loggen bij een admin maakt het logboek een
onbetrouwbare weergave van wat er werkelijk gebeurd is; het type helemaal niet loggen kost
traceerbaarheid die bij een klantstoring nodig is. Besloten door Sven op 2026-08-05; niet
opnieuw ter discussie stellen.

---

## 15. Entiteitswaarden uitlezen

Eén centrale functie in `validators.py`, bijvoorbeeld
`read_entity_value(hass, binding) -> ReadResult`, die:

1. controleert of de entiteit bestaat;
2. controleert of de state beschikbaar is;
3. bij `value_source=attribute` het ingestelde attribuut leest;
4. strings veilig omzet naar `float`;
5. `unknown`, `unavailable`, `none`, `""` en niet-numerieke waarden afwijst;
6. de `scale_factor` toepast;
7. `invert_value` toepast indien ingesteld;
8. eenheidsconversie toepast **uitsluitend** op basis van de expliciet gekozen `unit`
   (`kW → W` ×1000, `ct/kWh → EUR/kWh` ÷100, etc.);
9. een gestandaardiseerd resultaat teruggeeft
   (`ok: bool`, `value: float | None`, `reason_code: str | None`, `entity_id: str`).

Geen naamheuristiek. Geen conversie op basis van aannames of de HA-eenheid.

---

## 16. Rekenmotor

### Netvermogen
Interne normalisatie: **positief = afname van net, negatief = teruglevering**.

- `single_signed` + `positive_means=import` → waarde ongewijzigd
- `single_signed` + `positive_means=export` → waarde ×-1
- `separate_import_export` → `import_w - export_w`

### Zonneoverschot
Volgorde van bepaling (eerste die lukt wint, expliciet — niet gokken):

1. Netmeter geeft teruglevering: `solar_surplus_w = max(-grid_power_w, 0)`
   → betrouwbaarheid `high`
2. Zonnebron én algemeen verbruik beschikbaar:
   `solar_surplus_w = max(solar_power_w - household_consumption_w, 0)`
   → betrouwbaarheid `medium`
3. Anders: `solar_surplus_w = None`, `reason_code = missing_required_data`

Een thuisbatterij die laadt telt als verbruik; is er wel een batterijbron geconfigureerd
maar geen batterijvermogen leesbaar, dan zakt de betrouwbaarheid van variant 2 naar `low`.

### Netbelasting

```text
grid_load_percent = abs(grid_power_w) / max_grid_power_w * 100
```

`abs()` is bewust: de hoofdzekering begrenst beide richtingen, dus ook zware teruglevering
telt mee voor piekrisico. Bescherm tegen `max_grid_power_w in (None, 0)` → resultaat `None`
met `missing_required_data`.

`peak_risk = grid_load_percent >= peak_warning_percent`

**De richting bepaalt het advies, niet de waarschuwing.** `peak_risk` staat in beide
richtingen aan — het risico is echt, de zekering begrenst afname en teruglevering
gelijk. Het advies verschilt wel: bij afname moet er minder verbruikt worden, bij
teruglevering juist méér, want het overschot zelf gebruiken is precies wat de belasting
verlaagt. Eén gezamenlijke tekst zou bij teruglevering adviseren de belasting te
verergeren. Zie de twee aparte reason codes in de adviesregels hieronder; ze sluiten
elkaar uit, omdat `grid_power_w` niet tegelijk positief en negatief kan zijn.

### Datakwaliteit (0–100)
Gewogen checklist, transparant en testbaar:

| Item | Punten |
|---|---|
| Verplichte woninggegevens compleet (fasen, zekering, max vermogen, contracttype) | 20 |
| Minimaal één ingeschakelde netbron met geldige actuele waarde | 25 |
| Bruikbare zonnebron met geldige actuele waarde | 15 |
| Prijsinformatie beschikbaar (dynamisch: geldige prijsbron; vast: tarief ingevuld) | 15 |
| Minimaal één apparaatprofiel met vermogen én energie/cyclus | 15 |
| Alle flexibele apparaten hebben een tijdvenster | 10 |

Resultaat: `score`, `completed_items[]`, `missing_items[]`, `invalid_items[]`.

### Energiescore (0–100)
Expliciete formule zodat de uitkomst deterministisch en testbaar is:

```text
score = 0.30 × data_quality_score
      + 0.25 × peak_component        (100 bij <50% netbelasting, lineair naar 0 bij 100%)
      + 0.20 × solar_component       (100 bij surplus ≥ min_solar_surplus_w, anders lineair;
                                      0 bij onbekend)
      + 0.15 × price_component       (dynamisch: 100 bij prijs ≤ laag, 0 bij ≥ hoog,
                                      lineair ertussen; vast contract: 50)
      + 0.10 × flexibility_component (100 bij ≥1 bruikbaar, flexibel én compleet
                                      apparaat, anders 0)
```

**Wat "compleet" hier betekent (aangescherpt in fase 8b).** Oorspronkelijk telde elk
bruikbaar flexibel apparaat mee. Een rij met alleen een naam en een type voldeed daaraan,
dus een lege regel toevoegen leverde meteen tien scorepunten op — een meter die beloont
dat je iets hébt aangemaakt in plaats van wat de woning kán. Een klant wiens cijfer stijgt
door een lege regel kijkt naar een getal dat niets meet.

De grens ligt daarom op dezelfde plek als de datakwaliteitschecklist: een apparaat telt
mee wanneer het **bruikbaar, flexibel én compleet** is, waarbij compleet betekent
`nominal_power_w` **en** `energy_per_cycle_kwh` ingevuld. Zonder energie per cyclus valt er
geen besparing te noemen, en dan zegt een advies over dat apparaat niets concreets.

**Het tijdvenster hoort er bewust níet bij.** Een apparaat zonder venster mag op elk uur,
en is dus juist méér beschikbaar voor advies, niet minder. Het venster meewegen zou het
vrijere apparaat straffen en zou het aparte checklistitem voor tijdvensters een tweede keer
meetellen.

Eén gedeelde functie (`engine/completeness.py: is_complete_device_profile`) draagt deze
definitie, zodat de checklist, de energiescore en de markering in het apparaatformulier
niet uit elkaar kunnen lopen.

Afronden op hele getallen. Componentwaarden meegeven in het resultaat zodat de
vraagselector "Hoe is mijn energiescore berekend?" ze kan tonen.

**Onbekend versus niet van toepassing (verplicht onderscheid).** Een component die
geen waarde kan krijgen scoort niet automatisch neutraal:

- **Niet van toepassing** — het signaal bestaat in deze situatie niet en zou ook na
  volledig configureren niet ontstaan. Enige geval in 0.1.0: de prijscomponent bij een
  **vast contract**. Deze scoort `50`, zodat een correct ingerichte woning met een vast
  contract niet gestraft wordt voor iets wat niet bestaat.
- **Onbekend** — het signaal bestaat wel, maar is niet geconfigureerd of niet te lezen:
  geen `max_grid_power_w` (peakcomponent), geen bruikbare netbron, onbekend
  zonneoverschot, of een **dynamisch** contract zonder geldige prijsbron of zonder
  prijsgrenzen. Deze scoren `0`.

Zonder dit onderscheid houdt een halfingevulde configuratie een comfortabele score en
meet de energiescore vooral hoe weinig er is ingevuld.

**Meerdere bronnen van hetzelfde type.** `solar`, `general_consumption` en
`home_battery` tellen op: twee omvormers produceren samen meer. `grid_meter` en
`current_price` mogen **hoogstens één keer** voorkomen. Twee ingeschakelde bronnen van
zo'n type is een configuratiefout, geen situatie om uit te kiezen — de waarden zijn niet
op te tellen en er is niet te bepalen welke de juiste is. Gedrag: **geen van beide
gebruiken**, `reason_code = missing_required_data`, beide rijen tellen als `invalid_item`
in de datakwaliteit, en één logregel `invalid_configuration` per type via dezelfde
anti-spamroute als §12.

Presenteer dit **niet** als wetenschappelijke efficiëntiescore. README en UI leggen uit dat
het een DomotiApp-indicator is voor de actuele mogelijkheid om energie slim te gebruiken.

### Prijsopbouw en normalisatie

Een prijsbron zegt met `price_basis` wat hij levert (§8). De rekenmotor rekent een kale
marktprijs **bij het uitlezen** één keer om naar een all-in prijs, en daarna bestaat er in
het hele systeem nog maar één soort prijs:

```text
all_in = (marktprijs + opslag_leverancier + energiebelasting) × (1 + btw / 100)

price_basis = all_in   → de waarde wordt ongewijzigd gebruikt
price_basis = market   → bovenstaande formule
price_basis ontbreekt  → geen prijs; missing_required_data, rij telt als invalid_item
```

De omrekening gebeurt ná de eenheidsconversie van §15, zodat een bron in `ct/kWh` eerst
euro's wordt en daarna pas all-in.

**Waarom bij het uitlezen (en niet bij het vergelijken).** Het alternatief is de vraag
"welke soort prijs is dit?" meedragen tot in elke vergelijking, elke adviestekst en elk
getal in het paneel. Dat is precies het soort verspreide aanname waar dit project al
drie keer op is stukgelopen. Door één keer te normaliseren geldt overal hetzelfde getal:
de prijsgrenzen, de besparingsformule, de `price_component` van de energiescore, het
`prijs_eur_kwh`-meetgetal op een advies en het antwoord op "Kan ik nu het beste een
apparaat gebruiken?" vergelijken allemaal dezelfde eenheid.

**Gevolg dat vastligt: de prijsgrenzen zijn dus all-in.** Dat staat in het label en in de
hulptekst van beide velden (§8), anders vult iemand € 0,05 in omdat zijn sensor dat toont.

**Energiebelasting en opslag zijn verplicht zodra een bron `market` levert.** Ze staan op
`HomeProfile` en niet op de bron: het zijn eigenschappen van het contract, en bij twee
prijsbronnen zouden er twee kopieën ontstaan die uit elkaar kunnen lopen. Ontbreekt er
één, dan wordt de prijs **niet** gebruikt — ze op nul zetten zou de prijs met meer dan de
helft onderschatten terwijl elke grens, besparing en coachtekst hem als feit blijft
noemen. `validate_configuration` meldt dat bij de woning, want anders ziet de installateur
een bron die schoon valideert en nergens een prijs. Een expliciete `0` is wél een antwoord;
alleen "niet ingevuld" blokkeert. Btw kent wel een default en ontbreekt daarom nooit.

**De energiescore verandert hier niet van.** `price_component` kijkt puur relatief naar de
afstand tussen de twee grenzen, en dat blijft kloppen zolang prijs en grenzen dezelfde
eenheid hebben — wat normalisatie bij het uitlezen nu juist garandeert.

**Teruglevering wordt niet genormaliseerd.** `feed_in_price_eur_kwh` blijft een vast
all-in bedrag (§8). De importformule past er niet op: teruglevering levert doorgaans de
marktprijs op, eventueel met btw, maar zonder energiebelasting. Een aparte prijsbron voor
teruglevering is een idee voor een volgende versie, geen onderdeel van 0.1.0.

### Saldering en de besparingsformule

De salderingsregeling stopt in één keer op **2027-01-01**, zonder afbouw. Tot die datum
is een teruggeleverde kWh de volle leveringsprijs waard, dus zelf verbruiken levert
niets extra's op — behalve de terugleverkosten die je ermee vermijdt.

Eén formule dekt beide regimes:

```text
besparing = energie_per_cyclus × (importprijs − effectieve_terugleververgoeding
                                  + terugleverkosten)

effectieve_terugleververgoeding = importprijs           tijdens saldering
                                = feed_in_price         daarna
```

Elk bedrag in deze som is all-in: de dynamische prijs omdat hij bij het uitlezen is
genormaliseerd, het vaste tarief en de terugleverbedragen omdat het formulier er expliciet
om vraagt. Een kale marktprijs hierin zou de besparing met de energiebelasting overdrijven.

Tijdens saldering valt `importprijs − importprijs` weg en blijft
`energie × terugleverkosten` over. Daarna neemt het terugleveringstarief het over en
wordt het verschil echt. Er staat dus **geen datumtak in de rekenkern**.

De omslag is een instelling (`net_metering_until`) en geen controle tegen de kalender in
code: een klant kan een afwijkend contract hebben, en een datum is te verzetten om beide
regimes te testen. Het is een **datum en geen schakelaar**, zodat de omslag vanzelf
gebeurt in plaats van een bezoek aan elke klant op 1 januari 2027 te vereisen. `None`
betekent dat deze woning helemaal geen saldering heeft.

Een besparing die op nul of lager uitkomt wordt als `0.0` gerapporteerd, niet als
"onbekend": dat is een berekend antwoord. Levert de som nul op terwijl saldering nog
loopt, dan zegt de adviestekst er expliciet bij dat dit aan de salderingsregeling ligt —
"een gunstig moment" naast € 0,00 leest anders als een tegenspraak.

Dit raakt de energiescore niet: `price_component` kijkt naar de actuele prijs tegen de
prijsgrenzen en `solar_component` naar het overschot, en geen van beide gebruikt de
terugleververgoeding.

### Adviesregels

| Situatie | Reason code | Tekst |
|---|---|---|
| Essentiële data ontbreekt | `missing_required_data` | Vul de ontbrekende energiegegevens aan om een betrouwbaar advies te ontvangen. |
| Netbelasting boven waarschuwingsgrens door **afname** | `high_grid_load` | Het actuele netvermogen ligt dicht bij de ingestelde maximale woningbelasting. Stel extra grootverbruikers indien mogelijk uit. |
| Netbelasting boven waarschuwingsgrens door **teruglevering** | `high_grid_export` | De teruglevering ligt dicht bij de ingestelde maximale woningbelasting. Schakel indien mogelijk juist extra verbruikers in om het overschot zelf te benutten. |
| Voldoende zonneoverschot + flexibel apparaat binnen venster | `solar_surplus_available` | Er is momenteel zonneoverschot beschikbaar. Dit is een gunstig moment om [apparaatnaam] te gebruiken. |
| Prijs onder lage grens | `low_energy_price` | De actuele energieprijs is relatief laag. Flexibele apparaten kunnen nu voordeliger worden gebruikt. |
| Prijs boven hoge grens | `high_energy_price` | De actuele energieprijs is relatief hoog. Stel flexibel energiegebruik indien mogelijk uit. |
| Lawaaiig apparaat tijdens stille uren | `quiet_hours_active` | (advies onderdrukt of gemarkeerd) |
| Geen actie nodig | `neutral_energy_situation` | De actuele energiesituatie vraagt momenteel niet om een aanpassing. |

Aanvullende regels die expliciet vastliggen:

- **Prijsadviezen gelden alleen bij `contract_type = dynamic`** én een geldige prijsbron.
  Bij een vast contract worden `low_energy_price` en `high_energy_price` nooit gegenereerd.
- Stille uren: apparaten met `is_noisy = true` worden niet geadviseerd tussen
  `quiet_hours_start` en `quiet_hours_end` tenzij `allow_advice_during_quiet_hours = true`.
  Ondersteun een venster dat middernacht overschrijdt (bv. 22:00–07:00).
- **Apparaattijdvensters overschrijden middernacht op precies dezelfde manier.** Is
  `latest_finish` eerder dan `earliest_start`, dan loopt het venster door tot de volgende
  dag: een vaatwasser van 22:00 tot 06:00 is het normale scenario en moet instelbaar zijn.
  Begin inclusief, einde exclusief. Een venster waarvan begin en einde gelijk zijn is
  ongeldig (leeg of een volledige dag — niet te bepalen welke). De vensterlengte, en
  daarmee de controle of `duration_minutes` erin past, is
  `(einde − begin) mod 1440`.
- Tijdvensters en stille uren worden geëvalueerd in de HA-tijdzone via `dt_util.now()`.
- Er is altijd exact één hoofdadvies; bij geen enkele treffer is dat
  `neutral_energy_situation`.
- Het coachantwoord op **"Kan ik nu het beste een apparaat gebruiken?"** volgt dezelfde
  volgorde: zonneoverschot, dan piekbelasting, dan prijs. Pas als geen van die drie iets
  zegt, luidt het antwoord dat er geen aanleiding is. Een lage of hoge prijs noemt het
  bedrag erbij, uitdrukkelijk als **all-in** prijs — hetzelfde genormaliseerde getal dat
  tegen de prijsgrenzen is vergeleken. Zonder die tak stond er "geen aanleiding" terwijl
  er een prijsadvies naast in de lijst hing.

Sorteervolgorde: 1) veiligheid 2) piekbelasting 3) harde tijdsgrenzen 4) zonnebenutting
5) prijs 6) algemene optimalisatie. Nooit meer adviezen tonen dan `max_advice_count`.

---

## 17. Coacharchitectuur

Rekenen en formuleren strikt gescheiden:

```text
Calculator → EnergyMetrics → Advisor → AdviceItem[] → CoachProvider → CoachResult (NL-tekst)
```

```python
class CoachProvider(Protocol):
    async def async_generate(self, result: CoachResult) -> CoachResult: ...
```

Implementeer `RuleBasedCoachProvider`. Daarnaast uitsluitend een lege, niet-actieve
uitbreidingsinterface voor een toekomstige LLM-provider — geen OpenAI, Anthropic, Ollama
of andere provider in 0.1.0.

Een provider mag nooit waarden verzinnen, andere redenen geven dan de reason codes uit de
rekenmotor, apparaten aansturen, entiteiten selecteren of HA-services uitvoeren.

De provider wordt via dependency injection aan de coordinator meegegeven.

---

## 18. Coordinator en updates

- Geen polling van externe data.
- `async_track_state_change_event` op **uitsluitend** de expliciet gekoppelde entity_id's.
- **Herbouw de listener wanneer de configuratie verandert** (bron of apparaat toegevoegd,
  gewijzigd of verwijderd). Unsubscribe de oude listener eerst.
- Debounce herberekeningen (`Debouncer`, cooldown ~2 s, `immediate=False`).
- Voorkom gelijktijdige berekeningen met een lock.
- Update na berekening de eigen entities en het coachresultaat.
- Periodieke veiligheidsherberekening elke 5 minuten via `async_track_time_interval`.
- Alle unsubscribes correct opruimen bij unload (`entry.async_on_unload`).

---

## 19. Home Assistant-entiteiten

Eén eigen device in het device registry, identifier `(DOMAIN, entry.entry_id)`,
**naam vast `DomotiApp Energy`**, manufacturer `DomotiApp`, model `Energy Coach`,
sw_version `0.1.0`. Nooit koppelen aan devices van andere integraties.

De woningnaam staat in de config entry en in het paneel. Hij mag op het device
zichtbaar worden gemaakt (bijvoorbeeld in een model- of via-veld), maar hij bepaalt
**nooit** de entity-ID's — anders krijgt elke klant andere ID's en is de lijst hieronder
niet vast te leggen.

**De entity-ID's zijn Engels en vast, ongeacht de UI-taal van de klant.** Ze staan in
de README, en klanten bouwen er dashboards, automatiseringen en langetermijnstatistieken
op — `statistic_id` van een sensor mét `state_class` is de entity-ID zelf, dus een
verschuivende ID breekt ook de historie.

Gebruik `_attr_has_entity_name = True` en `_attr_translation_key`, en **override
daarnaast de property `suggested_object_id`** zodat die de vaste Engelse naam
teruggeeft. HA bouwt de object-id dan op als
`slugify(devicenaam + " " + die naam)`; de devicenaam-prefix en het slugifyen blijven
van HA, alleen de naam wordt vastgepind. De weergavenaam blijft gewoon de vertaling —
zet dus nooit `_attr_name`.

> **Correctie t.o.v. v0.1.0 van deze spec.** Deze sectie stelde eerder dat de object-id
> uit de Engelse vertaling komt (`object_id_platform_translations`) en dat een
> geforceerde object-id verboden was. Dat eerste is onjuist. In
> `entity_platform.EntityPlatformData.async_load_translations()` geldt:
>
> ```python
> object_id_language = (
>     hass.config.language
>     if hass.config.language in languages.NATIVE_ENTITY_IDS
>     else languages.DEFAULT_LANGUAGE
> )
> ```
>
> `homeassistant.generated.languages.NATIVE_ENTITY_IDS` bevat 41 talen, waaronder `nl`,
> `de` en `fr`. Een Nederlandse installatie kreeg daardoor
> `sensor.domotiapp_energy_energiescore` en een Engelse `sensor.domotiapp_energy_score`.
> Dit is bewust HA-gedrag ("native entity IDs") en voor een gewone integratie gewenst;
> voor dit product niet. `Entity` kent geen `_attr_suggested_object_id`, dus de property
> overriden is de enige manier om de ID vast te zetten zonder óók de devicenaam-prefix
> hard te coderen. Vastgesteld tegen HA 2026.2.3 en 2026.8.0b5, en bevestigd in de
> draaiende testinstance.

| Entiteit | Engelse naam | device_class | state_class | unit |
|---|---|---|---|---|
| `sensor.domotiapp_energy_score` | `Score` | — | measurement | — |
| `sensor.domotiapp_energy_data_quality` | `Data quality` | — | measurement | `%` |
| `sensor.domotiapp_energy_grid_power` | `Grid power` | `power` | measurement | `W` |
| `sensor.domotiapp_energy_solar_surplus` | `Solar surplus` | `power` | measurement | `W` |
| `sensor.domotiapp_energy_current_advice` | `Current advice` | — | — | — |
| `binary_sensor.domotiapp_energy_peak_risk` | `Peak risk` | `problem` | — | — |

Deze Engelse namen staan tweemaal: in `translations/en.json` en in
`const.ENTITY_OBJECT_ID_NAMES`. Het vertaalbestand tijdens runtime lezen zou blokkerende
I/O in de event loop zijn, dus een test vergelijkt beide lijsten.

Fase 5 bevat tests die bevestigen dat deze zes ID's ontstaan, dat ze niet meebewegen met
de taal (`en` én `nl`), en dat de weergavenaam wél de taal volgt.

> Twee dingen die hierbij horen. (1) HA gebruikt `device.name_by_user or device.name`:
> hernoemt een gebruiker het device vóór de eerste registratie, dan wijken de ID's af.
> Al geregistreerde entiteiten behouden hun ID — een wijziging aan deze ID's raakt dus
> alleen nieuwe installaties en is na de eerste uitrol een breaking change (CLAUDE.md).
> (2) De oorspronkelijke opdracht noemde
> `sensor.domotiapp_data_quality` naast `sensor.domotiapp_energy_score` — twee
> verschillende prefixen. Dat is hier geüniformeerd naar `domotiapp_energy_*`.
> Documenteer de exacte ID's in de README.

Unique ID's: `f"{entry.entry_id}_{key}"`.

`sensor.domotiapp_energy_current_advice`:
- state = adviestitel, **hard afgekapt op 255 tekens** (HA-limiet);
- volledige tekst, reason code, betrouwbaarheid en meetwaarden in attributes;
- attributes samen onder ~16 kB houden; maximaal de top-5 adviezen.

Availability: entiteiten blijven beschikbaar zolang de integratie draait; ontbrekende
brondata levert `None` (state `unknown`), **niet** `unavailable`. Anders verdwijnt de
data-kwaliteitsmeter precies wanneer je hem nodig hebt.

De sensors werken ook zonder geopend zijpaneel.

---

## 20. Services

```text
domotiapp_energy.recalculate
domotiapp_energy.clear_log
```

Registreer in `async_setup` (eenmalig, niet per entry) en verwijder ze niet bij unload van
een enkele entry. Beschrijf ze in `services.yaml` en vertaal in `translations/*.json`.

- `recalculate`: forceert een berekening, stuurt niets aan.
- `clear_log`: wist alleen het interne logboek.

**Admincheck expliciet implementeren** (HA doet dit niet automatisch voor services):

```python
if call.context.user_id is not None:
    user = await hass.auth.async_get_user(call.context.user_id)
    if user is None or not user.is_admin:
        raise Unauthorized()
```

Aanroepen zonder `user_id` (automations, scripts) worden toegestaan; documenteer dit.

---

## 21. Foutafhandeling

De integratie mag niet crashen wanneer: een gekoppelde entiteit verdwijnt · een entiteit
`unknown` wordt · een attribuut niet meer bestaat · een gebruiker een ongeldige waarde
opslaat · een apparaat onvolledig is · het storagebestand beschadigde velden bevat · de
frontend een onbekend ID stuurt · de frontend een verouderde revision gebruikt.

Nederlandse, begrijpelijke foutmeldingen in de GUI. HA-logging zonder gegevenslekken
(nooit entity states, woningnaam of locatie in warnings). Geen brede `except Exception`
zonder logging en motivatie.

Repairs en persistent notifications: **fase 2**, expliciet documenteren als zodanig.

---

## 22. Frontendstatus en gelijktijdigheid

De frontend moet: een laadstatus tonen · besturingselementen uitschakelen tijdens opslaan ·
een geslaagde opslag bevestigen · backendfouten tonen · bij `revision_conflict` de
configuratie opnieuw ophalen en de gebruiker informeren · nooit succes suggereren voordat
de backend bevestigt · unsaved changes herkennen · bevestiging vragen voordat een dialoog
met wijzigingen sluit.

Eén centrale frontendstate met drie strikt gescheiden delen:
`config` (backendwaarheid) · `live` (coach/metrics) · `draft` (tijdelijke formulierdata).

---

## 23. Toegankelijkheid

Label bij elk veld · duidelijke foutteksten · toetsenbordbediening · zichtbare focusstatus ·
semantische `<button>`-elementen · `aria-label` waar nodig · contrast via themavariabelen ·
nooit informatie uitsluitend via kleur (altijd tekst of icoon + tekst). Iconen zijn
aanvullend, nooit de enige drager van betekenis.

---

## 24. Tests

Gebruik `pytest` met `pytest-homeassistant-custom-component` (versie afgestemd op de
doel-HA-versie). `tests/conftest.py`:

```python
pytest_plugins = "pytest_homeassistant_custom_component"

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield
```

**Config flow:** succesvolle setup · abort `single_instance_allowed` bij tweede entry ·
ongeldige invoer (acknowledgement niet aangevinkt) · reconfigure/options van de woningnaam.
*(De oorspronkelijke eis "annuleren" is geschrapt: de config-flow-API kent geen
annuleerstap die zinvol te testen is.)*

**Storage:** standaardconfiguratie · opslaan en laden · revision +1 bij een
configuratiewijziging · revision ongewijzigd bij laden en bij logboekschrijfacties (§13) ·
limiet van 200 logs · onbekende velden defensief verwerken · migratiefunctie aanwezig en
aanroepbaar.

**Validatie:** geldige/ongeldige entities · negatieve vermogens · scale factors ·
ontbrekende attributes · ongeldige tijdvensters (halve vensters, gelijke begin- en
eindtijd) · `latest_finish` vóór `earliest_start` wordt correct als middernachtvenster
geëvalueerd, inclusief de controle of `duration_minutes` erin past · ongeldige
hoofdzekering · `max_grid_power_w = 0` · eenheidsconversie kW→W en ct→EUR.

**Rekenmotor:** signed netmeter (beide `positive_means`) · separate import/export ·
zonneoverschot via netmeter · zonneoverschot via verbruik · geen betrouwbare berekening →
`None` + `missing_required_data` · piekwaarschuwing · lage prijs · hoge prijs ·
prijsadvies onderdrukt bij vast contract · stille uren incl. venster over middernacht ·
apparaattijdvenster over middernacht · twee ingeschakelde netmeters → geen van beide
gebruikt · adviesprioriteit/sortering · neutrale situatie · datakwaliteit per
checklist-item · scorecomponent onbekend → 0 versus niet van toepassing → 50 ·
energiescore met vaste invoer → vaste uitkomst.

**WebSocket:** lezen als normale gebruiker · schrijven als admin · schrijven geweigerd voor
niet-admin · onbekend apparaat-ID → `not_found` · duplicate ID → `duplicate_id` ·
verouderde `expected_revision` → `revision_conflict`.

**Entities:** correcte state · correcte eenheid · availability bij ontbrekende data ·
updates na herberekening · advies-state afgekapt op 255 tekens.

Ontwikkelafhankelijkheden uitsluitend in `pyproject.toml` onder `[project.optional-dependencies] dev`,
nooit in `manifest.json → requirements`.

---

## 25. Codekwaliteit

Moderne type hints · `dataclass(slots=True)` waar geschikt · async HA-API's · geen
blokkerende I/O in de event loop · duidelijke modules · kleine functies · dependency
injection voor de rekenmotor · constants in `const.py` · geen magic strings · geen globale
mutabele configuratie · geen brede `except Exception` zonder logging en reden · geen dode
code · geen mockdata in productiecode.

`pyproject.toml` bevat configuratie voor Ruff (`target-version = "py313"`), pytest
(`asyncio_mode = "auto"`), coverage en waar praktisch mypy.

Wanneer deze spec een API-naam noemt die inmiddels is gewijzigd: gebruik de huidige
officiële variant en documenteer de afwijking in een codecommentaar én in de eindrapportage.

---

## 26. README (Engels)

Bevat: product description · current MVP capabilities · strict manual configuration
principle · privacy and local processing · installation via HACS custom repository ·
manual installation · setup · uitleg van elk tabblad · supported source types · supported
device profile types · **exacte lijst gegenereerde entity-ID's** · services · limitations ·
troubleshooting · development instructions · test commands · security notes · roadmap.

Verplichte zinnen:

```text
DomotiApp Energy does not automatically discover, select, or control devices in version 0.1.0.
```

```text
The DomotiApp Energy Score is a local advisory indicator and not a certified energy-efficiency rating.
```

### Waar de paneelteksten staan (besloten in fase 9)

`translations/{nl,en}.json` bevat **uitsluitend wat Home Assistant zelf rendert en nodig
heeft**: de config flow, de zes entiteitsnamen en de twee servicebeschrijvingen. HA zoekt
die op sleutel op en kiest zelf de taal.

**De teksten in het paneel blijven hardgecodeerd Nederlands in de frontendbestanden.** Dat
is een keuze, geen omissie:

- HA's vertaallader bedient een custom paneel niet. Het goed doen betekent zelf JSON
  ophalen en een lookup bouwen: nieuwe machinerie, een extra faalpunt bij het laden, en
  een tweede plek waar een tekst kan ontbreken.
- **De doorslaggevende reden:** dit zijn geen labels maar zinnen die de redenering dragen
  ("géén vast maandbedrag", "telt niet mee voor de datakwaliteit", "positief betekent hier
  laden"). Hun waarde zit erin dat ze naast het veld staan dat ze uitleggen, waar degene
  die dat veld schrijft ze ook leest. In een apart JSON-bestand lopen ze uit de pas met
  het veld waar ze over gaan — en dan is de tekst erger dan geen tekst.
- §8 vraagt Nederlandse UI-teksten; vertaalbaarheid is hier geen doel op zich.

Dit staat los van de entity-ID's: die zijn Engels en vast, juist zodat de UI-taal ze niet
kan verplaatsen (§19).

**De voorwaarde waaronder dit antwoord verandert:** een klant buiten het Nederlandse
taalgebied. Dan wordt het een echte feature met een eigen ronde — een lader, een
sleutelconventie en een tweede taalbestand — en geen refactor die in een fase wordt
meegenomen. Behandel het tot die tijd niet als achterstallig werk.

---

## 27. CHANGELOG

```markdown
# Changelog

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
```

---

## 28. Niet bouwen

Automatische device discovery · automatische entity matching · machine learning · externe
AI-koppeling · vrije-tekst chatbot · automatische bediening · laadpaalregeling ·
batterijoptimalisatie · 24-uurs lineaire programmering · kalenderintegratie ·
weersvoorspelling · energieprijs-API · licentiesysteem · gebruikersaccount · mobiele app ·
externe database · cloudbackend.

Alleen nette uitbreidingspunten waar dat logisch is.

---

## 29. Acceptatiecriteria

1. De integratie is via de UI toe te voegen (Integratie toevoegen → DomotiApp Energy).
2. Er kan maximaal één config entry bestaan.
3. Het paneel verschijnt automatisch in de zijbalk.
4. Een admin kan woninggegevens handmatig invullen.
5. Een admin kan energiebronnen handmatig toevoegen.
6. Een admin kan apparaten handmatig toevoegen.
7. Nergens automatische matching of discovery.
8. Configuratie overleeft een HA-herstart.
9. Geselecteerde entiteiten worden veilig uitgelezen.
10. Datakwaliteitsscore wordt berekend.
11. Energiescore wordt berekend.
12. Minimaal zonne-, prijs-, piek- en ontbrekende-data-adviezen worden gegenereerd.
13. De frontend toont de gestructureerde adviezen correct.
14. De eigen sensors worden aangemaakt en bijgewerkt met de exacte ID's uit §19.
15. Niet-admins kunnen de configuratie niet wijzigen (ook niet via directe WS-calls).
16. De integratie functioneert zonder internetverbinding.
17. De integratie stuurt geen apparaten aan (geen `async_call` naar andere domeinen).
18. Tests voor de kritieke logica slagen.
19. README en CHANGELOG aanwezig.
20. Repository klaar voor HACS-publicatie; `validate.yml` slaagt.

---

## 30. Werkwijze en fasering

Werk in fases. **Commit per fase en draai na elke fase `ruff check` en `pytest`.**
Rapporteer kort na elke fase wat af is.

| Fase | Inhoud | Klaar wanneer |
|---|---|---|
| 1 | Repo-inspectie, `pyproject.toml`, `manifest.json`, `hacs.json`, `const.py`, workflows, LICENSE, .gitignore | `ruff check` slaagt |
| 2 | `models.py`, `storage.py` + tests | `test_storage.py` slaagt |
| 3 | `validators.py` + tests | `test_validators.py` slaagt |
| 4 | `engine/` (calculator, completeness, advisor, reason_codes, providers) + tests | `test_calculator.py`, `test_advisor.py` slagen |
| 5 | `config_flow.py`, `__init__.py`, `coordinator.py`, `sensor.py`, `binary_sensor.py`, `services.yaml` + tests | `test_config_flow.py`, `test_entities.py` slagen |
| 6 | `websocket_api.py` + tests | `test_websocket_api.py` slaagt |
| 7 | `panel.py` + frontend core (state, api, dom, tap, forms) + tabbladen Overzicht/Woning | paneel laadt en toont echte data |
| 8 | Overige tabbladen: Energiebronnen, Apparaten, Voorkeuren, Energiecoach, Logboek | CRUD werkt end-to-end |
| 9 | Vertalingen, README, CHANGELOG, eindcontroles | zie hieronder |

**Eindcontroles (fase 9), expliciet uitvoeren en rapporteren:**

- Grep op deprecated API's: `register_static_path`, `async_track_state_change(`,
  `hass.data[DOMAIN]`, `async_setup_platforms`, `datetime.now()`.
- Grep op verboden patronen: `fetch(`, `localStorage`, `sessionStorage`, `#026FA1`,
  `hass.services.async_call` naar een ander domein dan `domotiapp_energy`.
- Bevestig dat er nergens entity-matching, scoring op naam of discovery plaatsvindt.
- Bevestig dat er geen mock- of placeholderdata in productiecode staat.

**De frontendcontrole is niet langer alleen grep.** Fase 7a liet zien waarom: drie bugs
(tabbladen die stapelden, rechten die niet verborgen, iconen zonder tekst) kwamen alle
drie uit dezelfde CSS-cascaderegel, terwijl parsen, importeren, HTTP-controles en de
volledige pytest-suite groen stonden. Geen van die controles bouwde ooit een DOM op.

Vanaf fase 7a geldt daarom:

- de paneelcode heeft een eigen testlaag (`npm test`, jsdom + `node --test`), die in
  `tests.yml` naast `pytest` draait;
- zichtbaarheid loopt uitsluitend via `setVisible()` uit `core/dom.js`, dat de klasse
  `is-hidden` zet; het `hidden`-attribuut alleen is niet genoeg, omdat elke eigen
  `display`-regel het in de cascade verslaat;
- de tests toetsen dat klassecontract, niet de cascade van jsdom — die is te
  onvolledig om erop te bouwen;
- een frontendfix telt pas als geverifieerd wanneer de bijbehorende test aantoonbaar
  faalt op de code van vóór de fix.

Alleen een echte browser toetst de werkelijke cascade. Een headless-browsertest
(Playwright) is de aanbevolen laatste controle vóór de eerste klantuitrol; die staat
bewust buiten deze fasering.

Wanneer een frontendfunctie te groot blijkt: bouw eerst een functionele eenvoudige variant
in plaats van een visueel uitgebreide, niet-werkende mock-up.

---

## 31. Eindrapport

Lever aan het eind:

- korte samenvatting van wat gebouwd is;
- belangrijkste architectuurkeuzes en afwijkingen van deze spec (met reden);
- lijst van aangemaakte en gewijzigde bestanden;
- uitgevoerde tests en resultaten (inclusief coverage);
- technische beperkingen;
- exacte handmatige installatiestappen;
- exacte stappen om de eerste woning te configureren;
- overzicht van logische fase-2-uitbreidingen.

Meld eerlijk welke onderdelen nog niet volledig werken. Een eerlijke lijst met open punten
is waardevoller dan een claim dat alles af is.
