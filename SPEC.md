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
Minimale Home Assistant-versie : 2024.12
Python                          : 3.13
Doelbrowsers                    : evergreen (Chrome/Safari/Firefox), incl. HA companion app
Licentie                        : MIT
```

Alle gebruikte API's moeten bestaan in HA 2024.12 en niet deprecated zijn in de meest
recente HA-release. Controleer bij twijfel de actuele developer docs en documenteer de
keuze in een codecommentaar.

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
  "version": "0.1.0",
  "codeowners": ["@Sven2410"],
  "config_flow": true,
  "single_config_entry": true,
  "integration_type": "service",
  "iot_class": "calculated",
  "documentation": "https://github.com/Sven2410/domotiapp-energy",
  "issue_tracker": "https://github.com/Sven2410/domotiapp-energy/issues",
  "dependencies": ["http", "frontend", "panel_custom", "websocket_api"],
  "requirements": []
}
```

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
  "homeassistant": "2024.12.0"
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
zonneproductie · zonneoverschot · percentage van max. netvermogen · hoofdadvies ·
waarschuwingen · aantal geconfigureerde apparaten · tijdstip laatste berekening.
Duidelijke lege statussen wanneer nog niets is ingesteld.

### Woning
- `home_name`
- `phases` — 1 of 3
- `main_fuse_a` — hoofdzekering per fase in ampère (1–100)
- `max_grid_power_w` — maximaal toegestaan netvermogen
- `peak_warning_percent` — waarschuwing vanaf % (default 80)
- `contract_type` — `fixed` | `dynamic`
- `fixed_import_price_eur_kwh`
- `feed_in_price_eur_kwh`
- `low_price_threshold_eur_kwh`
- `high_price_threshold_eur_kwh`
- `min_solar_surplus_w` (default 500)
- `default_strategy` — `comfort` | `balanced` | `save` | `max_self_consumption`
- `control_level` — vast op `advice_only` in 0.1.0

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
```

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
```

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

**Verduidelijking `min_savings_eur`:** deze drempel filtert **uitsluitend** adviezen waarvoor
een `estimated_savings_eur` is berekend. Adviezen zonder berekenbare besparing
(veiligheid, piek, ontbrekende data, neutraal) worden nooit weggefilterd.

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
`solar_surplus_detected`.

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
`number`, `boolean`, `select`, `text`, `time`.

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

Stabiele reason codes in `engine/reason_codes.py` (constants, geen losse strings):

```text
missing_required_data · solar_surplus_available · high_grid_load
low_energy_price · high_energy_price · flexible_device_available
outside_allowed_window · quiet_hours_active · invalid_entity_state
insufficient_savings · neutral_energy_situation
```

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
states · writes serialiseren met `asyncio.Lock` · `revision` +1 bij elke wijziging ·
frontend ontvangt de actuele revision · optimistic concurrency (zie §14).

De woningnaam staat óók in de config entry; de uitgebreide configuratie in de storage.

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
      + 0.10 × flexibility_component (100 bij ≥1 bruikbaar flexibel apparaat, anders 0)
```

Afronden op hele getallen. Componentwaarden meegeven in het resultaat zodat de
vraagselector "Hoe is mijn energiescore berekend?" ze kan tonen.

Presenteer dit **niet** als wetenschappelijke efficiëntiescore. README en UI leggen uit dat
het een DomotiApp-indicator is voor de actuele mogelijkheid om energie slim te gebruiken.

### Adviesregels

| Situatie | Reason code | Tekst |
|---|---|---|
| Essentiële data ontbreekt | `missing_required_data` | Vul de ontbrekende energiegegevens aan om een betrouwbaar advies te ontvangen. |
| Netbelasting boven waarschuwingsgrens | `high_grid_load` | Het actuele netvermogen ligt dicht bij de ingestelde maximale woningbelasting. Stel extra grootverbruikers indien mogelijk uit. |
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
- Tijdvensters en stille uren worden geëvalueerd in de HA-tijdzone via `dt_util.now()`.
- Er is altijd exact één hoofdadvies; bij geen enkele treffer is dat
  `neutral_energy_situation`.

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
naam = woningnaam, manufacturer `DomotiApp`, model `Energy Coach`, sw_version `0.1.0`.
Nooit koppelen aan devices van andere integraties.

**Entity-ID's expliciet vastleggen.** Gebruik `_attr_has_entity_name = True` en
`_attr_translation_key`, plus `_attr_suggested_object_id` om deze exacte ID's te forceren:

| Entiteit | device_class | state_class | unit |
|---|---|---|---|
| `sensor.domotiapp_energy_score` | — | measurement | — |
| `sensor.domotiapp_energy_data_quality` | — | measurement | `%` |
| `sensor.domotiapp_energy_grid_power` | `power` | measurement | `W` |
| `sensor.domotiapp_energy_solar_surplus` | `power` | measurement | `W` |
| `sensor.domotiapp_energy_current_advice` | — | — | — |
| `binary_sensor.domotiapp_energy_peak_risk` | `problem` | — | — |

> De oorspronkelijke opdracht noemde `sensor.domotiapp_data_quality` naast
> `sensor.domotiapp_energy_score` — twee verschillende prefixen. Dat is hier
> geüniformeerd naar `domotiapp_energy_*`. Documenteer de exacte ID's in de README.

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

**Storage:** standaardconfiguratie · opslaan en laden · revision verhogen · limiet van 200
logs · onbekende velden defensief verwerken · migratiefunctie aanwezig en aanroepbaar.

**Validatie:** geldige/ongeldige entities · negatieve vermogens · scale factors ·
ontbrekende attributes · ongeldige tijdvensters · `latest_finish` vóór `earliest_start` ·
ongeldige hoofdzekering · `max_grid_power_w = 0` · eenheidsconversie kW→W en ct→EUR.

**Rekenmotor:** signed netmeter (beide `positive_means`) · separate import/export ·
zonneoverschot via netmeter · zonneoverschot via verbruik · geen betrouwbare berekening →
`None` + `missing_required_data` · piekwaarschuwing · lage prijs · hoge prijs ·
prijsadvies onderdrukt bij vast contract · stille uren incl. venster over middernacht ·
adviesprioriteit/sortering · neutrale situatie · datakwaliteit per checklist-item ·
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
