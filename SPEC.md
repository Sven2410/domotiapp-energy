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

Tabbladen: `Overzicht`, `Energiecoach`, `Apparaten`, `Mijn voorkeuren`, `Installatie`,
`Logboek` — zes, en dezelfde zes voor een installateur en een bewoner (§33.6).
`Installatie` bevat de secties `Woning` en `Energiebronnen`, die hieronder afzonderlijk
beschreven blijven omdat het twee verschillende soorten gegevens zijn.

**Wie welk veld mag wijzigen staat in §33.4**, niet hieronder. Deze sectie beschrijft
wélke velden er zijn; de eigenaarschapskaart beschrijft van wie ze zijn.

### Overzicht
Status integratie · datakwaliteit (%) · energiescore (0–100) · actueel netvermogen ·
zonneproductie · zonneoverschot · percentage van max. netvermogen · **actuele
energieprijs** · hoofdadvies · waarschuwingen · tijdstip laatste berekening.
Duidelijke lege statussen wanneer nog niets is ingesteld.

**Vervallen in 0.4.1: de kaart `Configuratie`** (woningnaam, aantal bronnen, aantal
apparaten). Zij herhaalde wat twee tabbladen verderop staat en was geen meting van dit
moment, terwijl zij op een telefoon een schermvulling kostte. De hint "er zijn nog geen
energiebronnen gekoppeld" is behouden en verhuisd naar `Actuele situatie`, waar de lege
metingen staan.

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
- `control_level` — vast op `advice_only` in 0.1.0

> `default_strategy` is geschrapt in ronde 1 (§33.5): het veld werd opgeslagen,
> gevalideerd en getoond, en door niets gelezen. Voeg het niet terug toe zonder een lezer
> in dezelfde ronde.

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
ready_from · ready_before · days_of_week · notes
capabilities · control_forbidden · control_forbidden_reason
```

- `ready_from` / `ready_before`: samen het **gereed-venster** — wanneer het apparaat
  klaar moet zijn, niet wanneer het mag starten (§32). Het startvenster is afgeleid:
  `ready_before − duration_minutes` is het laatste moment waarop starten nog op tijd is.
  Een `ready_before` die eerder valt dan `ready_from` betekent een venster over
  middernacht (zie §16). Beide velden zijn onafhankelijk optioneel.
  Vervangt `earliest_start` / `latest_finish`; zie §32.4 voor de migratie.
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

Type-specifieke velden bij `ev_charger` (§34.3):

```text
target_soc_percent      0–100, nullable, geen default   — bewonersveld (§33.4)
vehicle_capacity_kwh    > 0, nullable, geen default     — installateursveld
```

Samen met `battery_level_entity`, `nominal_power_w` en `ready_before` maken deze twee het
verschil tussen een laadpaal die **gepland** kan worden en een die **opportunistisch**
laadt. Dat onderscheid wordt niet als modus opgeslagen maar als predicaat afgeleid; zie
§34.4 voor waarom dat hier anders ligt dan bij `meter_mode` en `price_basis`.

### Voorkeuren

```text
quiet_hours_start · quiet_hours_end · allow_advice_during_quiet_hours
prefer_solar · prefer_low_price
min_savings_eur · max_advice_count (1–5)
show_technical_explanation · show_estimated_savings
```

Dit tabblad heet `Mijn voorkeuren` en is **volledig bewonersgebied** (§33.4): elk veld
hier is een uitspraak over wat de bewoner van het advies wil, niet over wat de woning is.

> `respect_max_grid_load` is geschrapt in ronde 1 (§33.5), om dezelfde reden als
> `default_strategy`: opgeslagen en getoond, door niets gelezen.

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
relevante meetwaarden · geschatte besparing indien berekenbaar · ontbrekende
gegevens · knop `Opnieuw berekenen`.

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
domotiapp_energy/devices/set_operation
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
devices/create · devices/update · devices/delete · logs/clear
```

Leesacties: elke ingelogde gebruiker. De frontend verbergt geen enkel tabblad meer; zij
grijst uit wat een bewoner niet bezit (§33.7), en de backend is altijd leidend.

> **Gewijzigd in ronde 1 (§33.9).** `preferences/update` stond in bovenstaande lijst en
> staat er niet meer in; `devices/set_operation` is erbij gekomen en staat er bewust
> buiten. De regel is niet langer "alles wat de configuratie wijzigt", maar:
> **`require_admin` bewaakt installateursvelden.** De grens ligt bij wíens gegevens er
> veranderen, niet bij óf er iets verandert. Lees §33.9 voordat je dit als gat in de
> beveiliging repareert.

**Configuratie is niet hetzelfde als bediening — en dat onderscheid is bewust.**

De lijst hierboven is niet "alles wat schrijft", maar "alles wat de **configuratie**
wijzigt". Dat is werk van de installateur, en het is wat `expected_revision` bewaakt.
Daarnaast bestaat er een tweede soort schrijfactie: de **bewoner die iets over de
huidige toestand meldt**. Die raakt de configuratie niet, verhoogt de revision niet, en
mag daarom door elke ingelogde gebruiker worden uitgevoerd.

Vandaag valt daar `coach/recalculate` onder, en vanaf het gereed-venster ook
`devices/set_ready` (§32.5) — de bewoner die zegt dat de machine vol is. Beide zijn
**opzettelijk niet** `require_admin`.

**Ronde 1 voegt hier een tweede as aan toe, en die vervangt deze niet.** Naast
configuratie-versus-bediening bestaat sinds §33 het onderscheid tussen configuratie van de
*installateur* en configuratie van de *bewoner*. `preferences/update` en
`devices/set_operation` wijzigen wél de configuratie en verhogen wél de revision, en staan
tóch open voor elke ingelogde gebruiker — omdat het zijn gegevens zijn. De twee assen
samen: `require_admin` geldt voor een commando dat **installateursconfiguratie** wijzigt.

**Timmer dit later niet dicht als inconsistentie.** Een bewoner die zijn eigen vaatwasser
niet als "vol" mag markeren omdat hij geen beheerder is, kan de functie niet gebruiken —
en dan is het hele gereedheidsmodel zinloos voor precies de persoon voor wie het bedoeld
is. Een commando hoort in de admin-lijst wanneer het de opgeslagen configuratie verandert,
niet omdat het toevallig schrijft.

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

**De drie niveaus blijven in de motor en verdwijnen van het scherm (besluit 0.4.1).**
Ze gooiden twee onvergelijkbare dingen op één as:

- `high` versus `medium` zegt wélke route de motor nam naar een getal dat in beide
  gevallen klopt. Dat is een implementatiedetail. Als "betrouwbaarheid: gemiddeld" naast
  een correcte meting leest het als twijfel over de gegevens van de klant, en er is geen
  handeling die het verandert.
- `low` is geen gradatie maar een **blinde vlek**: er hangt een batterij aan de woning
  waarvan het vermogen niet leesbaar is, en een ladende batterij verbruikt precies het
  overschot dat op het scherm staat. Het getal kan kilowatts mis zijn.

Daaruit volgen twee regels.

**Het overschot-advies vuurt niet op een overschot dat overschat kan zijn.** Dat was het
werkelijke gebrek: de coach adviseerde de vaatwasser aan te zetten op een overschot dat
er misschien niet was, met een besparingsbedrag eronder, en het etiket `low` onderdrukte
niets. Het etiket zag eruit alsof het probleem was afgehandeld. Zie ook §35.1 regel 2 —
een advies dat op een aantoonbaar onbetrouwbaar getal rust, is geen streng advies maar
een verkeerd advies.

**De blinde vlek wordt een zin die de oorzaak en de oplossing noemt**, naast het getal op
het Overzicht en in het coachantwoord op "welke gegevens ontbreken nog?". Niet als
checklistitem: de batterijrij bestáát, er ontbreekt geen invoer, en de datakwaliteit hoort
er dus niet voor te zakken.

Het predicaat heet `EnergyMetrics.solar_surplus_may_be_overstated` en is afgeleid, niet
opgeslagen. Het eist een overschot: variant 3 levert óók `low` maar zonder getal, en zonder
getal valt er niets te overschatten.

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

**Bekende beperking: dit is een totaal, terwijl de zekering per fase begrenst.**
`max_grid_power_w` is één getal voor de hele woning en `grid_power_w` is de som over de
fasen. Bij een drie-fasen aansluiting is de werkelijke overbelasting bijna altijd
éénfasig: 25 A op L2 terwijl de som op 40% staat is voor deze berekening onzichtbaar. Dat
is precies het waarschijnlijkste faalgeval van de doelgroep — een drie-fasen woning met
een laadpaal, waar de laadpaal zelf de onbalans veroorzaakt. Een P1-meter publiceert het
vermogen per fase wel degelijk.

Dit is bewust niet in 0.1.0 opgelost, omdat het optionele bindings per fase op de
netmeter vraagt en daarmee een eigen ronde is: drie extra entiteitkoppelingen, een
maximum per fase naast het totaal, en `grid_load_percent` als het maximum van de vier in
plaats van één deling. Tot die ronde er is, geldt: **de piekwaarschuwing dekt overbelasting
van de aansluiting als geheel, niet van een enkele fase.** Dat staat ook in de README
onder Limitations, want een installateur moet dit weten vóór hij het bij een klant zet.

**Hysterese (toegevoegd na de eerste uitrol op echte hardware).** `peak_risk` is geen kale
vergelijking meer. Een P1-meter meldt elke seconde, dus een belasting die rond de
waarschuwingsgrens hangt zette de waarschuwing — en daarmee het hele hoofdadvies —
onophoudelijk aan en uit. De vergelijking schakelt aan op `peak_warning_percent` en pas
weer uit onder `peak_warning_percent − PEAK_RISK_RELEASE_MARGIN_PERCENT`. Hetzelfde geldt
voor het zonneoverschot tegen `min_solar_surplus_w`, dat uitschakelt onder
`SOLAR_SURPLUS_RELEASE_FRACTION` daarvan, en het hoofdadvies zelf blijft minimaal
`PRIMARY_ADVICE_MIN_DWELL_SECONDS` staan tenzij er iets urgenters komt of de data het niet
langer draagt.

Het zijn **vaste constanten en geen instellingen**: dit beschrijft hoe de rekenmotor met
meters omgaat, niet iets waar een klant een mening over heeft — en een instelling hier zou
een instelling zijn die uitgezet kan worden. De toestand hoort in de coordinator
(`engine/hysteresis.py`), zodat de calculator en de advisor pure functies van hun invoer
blijven en zonder klok testbaar zijn.

### Datakwaliteit (0–100)
Gewogen checklist, transparant en testbaar:

| Item | Punten | Geldt wanneer |
|---|---|---|
| Verplichte woninggegevens compleet (fasen, zekering, max vermogen, contracttype) | 20 | altijd |
| Minimaal één ingeschakelde netbron met geldige actuele waarde | 25 | altijd |
| Bruikbare zonnebron met geldige actuele waarde | 15 | er bestaat een zonnebronrij |
| Prijsinformatie beschikbaar (dynamisch: geldige prijsbron; vast: tarief ingevuld) | 15 | altijd |
| Minimaal één apparaatprofiel met vermogen én energie/cyclus | 15 | er is ≥1 bruikbaar apparaat |
| Alle flexibele apparaten hebben een tijdvenster | 10 | er is ≥1 bruikbaar flexibel apparaat |

> Het apparaatitem krijgt er bij de laadpaalronde één voorwaarde bij en **geen nieuw item
> en geen andere weging** (§34.6): een laadpaal met een SOC-koppeling maar zonder
> accucapaciteit of doel-SOC is onvolledig. Een laadpaal *zonder* die koppeling verandert
> hier niets — die laadt opportunistisch en mist niets.

**De score is het aandeel van wat van toepassing is**, niet de som van alle punten:

```text
score = round(100 × behaalde punten van geldende items / punten van geldende items)
```

Een item dat niet geldt telt niet mee in teller én noemer, en komt terug in
`not_applicable_items[]` — niet in `missing_items[]`. Bij een woning die alle zes
dingen heeft sommeren de gewichten tot 100 en verandert er niets.

#### De zes items, één voor één getoetst (0.6.1)

Nagelopen op verzoek van Sven, nadat de checklist voor de **vierde** keer klaagde over
iets wat niet van toepassing was. De vraag per item: geldt dit voor élke woning, of alleen
voor een woning die het betreffende ding daadwerkelijk heeft?

| # | Item | Geldt wanneer | Oordeel |
|---|---|---|---|
| 1 | Woninggegevens | altijd | terecht — elke woning heeft fasen, een zekering en een contract |
| 2 | Netbron | altijd | terecht — zonder netmeting meet de integratie niets |
| 3 | Prijsinformatie | altijd | terecht — elke woning betaalt een tarief, vast of dynamisch |
| 4 | Zonnebron | er bestaat een zonnerij | terecht, gerepareerd in ronde B |
| 5 | Apparaatprofiel | ~~≥1 bruikbaar apparaat~~ → **≥1 *advisable* apparaat** | **fout, gerepareerd** |
| 6 | Tijdvensters | ~~≥1 bruikbaar *flexibel* apparaat~~ → **≥1 *advisable* apparaat** | **het vijfde geval** |

**Item 6 was het geval dat nog niemand had gevonden.** Het keek al naar `is_flexible`,
maar niet naar het bedieningsniveau: een vaatwasser die de bewoner op *"Alleen
meekijken"* had gezet leverde nog steeds de eis van een tijdvenster op, voor een apparaat
waarover niets geadviseerd wordt.

Beide items hangen nu aan hetzelfde predicaat, en dat is geen toeval: ze vragen allebei om
iets dat alleen betekenis heeft wanneer er advies uit volgt. Een compleet profiel zodat er
een besparing te noemen valt, een venster zodat het advies te timen is.

```text
is_advisable(apparaat) = is_usable ∧ is_flexible ∧ control_mode ≠ monitor_only
```

**Waarom voorwaardelijk** (bevinding productie-installatie, ronde B): een woning met
zonnepanelen en een slimme meter maar zonder slimme apparaten kreeg permanent "2 van
de 6 onderdelen is nog niet compleet", en geen enkele handeling van de bewoner kon
dat sluiten. Datakwaliteit hoort te meten wat je hebt ingevuld, niet wat je niet
bezit — dezelfde redenering waarmee de aansturingsterm uit de energiescore is
geweerd (§16, "de score meet mogelijkheid").

**Wat "geldt" bepaalt is nooit een gok.** Een bronrij is een expliciete uitspraak van
de installateur over wat de woning heeft; geen rij is geen uitspraak, dus het item
wordt niet gesteld. Er wordt niets afgeleid uit het entity- of deviceregister
(harde regel 1). Een zonnebron die er wél is maar niets levert kost gewoon punten —
"geen panelen" is geen tekortkoming, "panelen die we niet kunnen uitlezen" wel.

De drie onvoorwaardelijke items zijn waar de integratie voor bestaat: zonder
woningprofiel, netbron en prijs meet zij niets. Ze staan er ook voor dat een verse
installatie geen 100 kan scoren omdat zij nog niets heeft.

Resultaat: `score`, `completed_items[]`, `missing_items[]`, `not_applicable_items[]`,
`invalid_items[]`.

### Energiescore (0–100)

> **Vervangen door §35 (ontwerp, nog niet gebouwd).** Onderstaande beschrijving is wat er
> vandaag draait. §35 herontwerpt de score rond het principe *benut / benutbaar*, laat
> `peak_component` en `flexibility_component` vervallen en maakt `data_quality` een poort
> in plaats van een term. Lees §35 vóór je hier iets aan verandert.

**De score is een meting van dít moment, geen rapportcijfer over de woning.** Het
paneel zegt dat ook: "op dit moment", niet "van 100". 's Nachts vallen componenten
weg omdat er niets te meten valt, niet omdat er iets mis is.

Gewichten per component:

| Component | Gewicht | Geldt wanneer |
|---|---|---|
| `data_quality_component` | 0,30 | altijd |
| `peak_component` | 0,25 | altijd (100 bij <50% netbelasting, lineair naar 0 bij 100%) |
| `solar_component` | 0,20 | er is opwek op dit moment |
| `price_component` | 0,15 | dynamisch contract |
| `flexibility_component` | 0,10 | er is ≥1 bruikbaar apparaat |

**De score is het aandeel van wat van toepassing is**, dezelfde regel als de
datakwaliteit:

```text
score = round(100 × Σ(gewicht × component) / Σ(gewicht))   over de geldende componenten
```

Een component die niet geldt komt in `not_applicable_components[]` en valt uit
teller én noemer. Bij een woning waar alle vijf gelden sommeren de gewichten tot
1,0 en verandert er niets.

**Waarom voorwaardelijk** (bevinding productie-installatie, 2026-08-07). Een vast
contract scoorde 50 op prijs, bedoeld als neutraal — maar op een as waar de rest 100
kan halen is 50 een permanente aftrek van 7,5 punten voor het kiezen van een vast
contract. Een woning zonder apparaten scoorde 0 op flexibiliteit, nog eens 10 punten.
Samen een plafond van 82,5 voor een woning die niets fout deed. **Een component die
permanent 0 of 50 is en niet door gedrag te beïnvloeden valt, is een korting en geen
meting** — dezelfde redenering waarmee de aansturingsterm uit deze score is geweerd.

"Niet van toepassing" heeft geen getal op een 0–100-as; het enige neutrale is niet
meewegen. Onbekend blijft wél 0: het signaal bestaat en is niet geconfigureerd.

### Terugleverprijs (§16, vanaf 0.1.4)

Een woning kan een **dynamische terugleververgoeding** hebben, los van haar
importcontract. Daarom is `feed_in_price` een eigen brontype naast `current_price`,
en geen vlag erop: import dynamisch met teruglevering vast komt net zo goed voor als
andersom.

`price_basis` wordt hergebruikt — de vraag is identiek — maar **de omrekening is een
andere**, en dat is de reden dat het een eigen type is:

```text
import:        (marktprijs + opslag + energiebelasting) × (1 + btw)
teruglevering:  marktprijs − feed_in_markup_eur_kwh
```

Geen energiebelasting, want die wordt niet geheven over stroom die je niet hebt
afgenomen, en geen btw erbovenop: wat de klant ontvangt is wat op de factuur komt.
De importformule op een terugleverwaarde loslaten zou de vergoeding **ruwweg
verdrievoudigen** — dezelfde factor die `price_basis` überhaupt verplicht maakte.

De opslag wordt **afgetrokken** waar de importopslag wordt opgeteld: aan deze kant van
de meter verlaagt wat de leverancier inhoudt je opbrengst.

- `feed_in_markup_eur_kwh` staat op **HomeProfile**, niet op de bron: hij hoort bij het
  contract, niet bij de sensor — dezelfde redenering als bij de importcomponenten.
- **Geen default.** Een stille 0 zou overschatten wat de klant krijgt. Een expliciete
  0 is wél een antwoord ("deze leverancier houdt niets in"); alleen "niet ingevuld"
  blokkeert, en `validate_configuration` meldt dat tegen de woning.
- **Een bruikbare bron wint van `feed_in_price_eur_kwh`.** De rij aanmaken is de
  expliciete uitspraak dat de vergoeding varieert. Het vaste veld blijft bewaard en
  wordt in het paneel uitgeschakeld, niet gewist, zodat het terugkomt zodra de bron
  weg is.
- **De uitkomst mag negatief zijn en wordt niet geklemd.** Negatieve marktprijzen
  bestaan, en dan kóst terugleveren geld. In de besparingsformule maakt dat zelf
  verbruiken juist méér waard, wat klopt.
- Er kan er hoogstens één zijn (`EXCLUSIVE_SOURCE_TYPES`), net als bij de netmeter en
  de prijsbron.

**Tijdgebonden.** Zolang de saldering geldt is een teruggeleverde kWh de kale
retailprijs waard en wordt deze waarde nooit geraadpleegd; **na 1 januari 2027 is de
terugleverprijs het hele verschil** in `saving = energie × (import − teruglevering +
terugleverkosten)`.

#### De zonnecomponent — de oude definitie was fout

**`solar_component` mat tot 0.1.2 het tegenovergestelde van zijn eigen naam.** Hij
scoorde het *overschot*, en overschot is `max(-netvermogen, 0)`: vermogen dat de
woning **uit** gaat. Daarmee kreeg een woning die alles terugleverde een 100 en een
woning die al haar opwek zelf verbruikte een 0 — terwijl het veld "zonnebenutting"
heette en er een coach naast stond die adviseert het overschot juist zelf te
gebruiken. **De score beloonde precies het gedrag dat het advies afraadt.**

Dit staat hier expliciet omdat het een fout in de specificatie was, niet alleen in de
code: de oude regel ("100 bij surplus ≥ min_solar_surplus_w") beschreef beschikbaarheid
en noemde het benutting.

Vanaf 0.1.3:

```text
solar_component = (opwek − teruglevering) / opwek × 100      als opwek > 0
                = niet van toepassing                         als opwek = 0 of onbekend
```

Geen opwek betekent dat er niets verspild wordt, dus valt er niets te scoren. Een
nachtelijke 0 kostte een woning twintig punten voor iets wat geen tekortkoming is.

De component blijft **door gedrag beïnvloedbaar**, en dat is wat hem een meting houdt
in plaats van een korting: wie de vaatwasser aanzet terwijl de zon schijnt verhoogt
hem, met of zonder slim apparaat. Dat is precies het advies dat de coach geeft.

#### De flexibiliteitscomponent

Geen enkel bruikbaar apparaat → **niet van toepassing**: er valt niets te verplaatsen
en geen enkele instelling verandert dat. Wél apparaten maar geen enkele flexibel én
compleet → een echte **0**, want dat is een gat dat de installateur kan dichten. Dat
is dezelfde grens als tussen "niet gevraagd" en "ontbrekend" in de checklist.

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

**Een validatiemelding landt altijd zichtbaar.** `ha-form` hangt elke melding aan
zijn veld, dus een melding voor een veld dat het huidige schema niet rendert wordt
aangenomen en weggegooid. Elk formulier in dit paneel filtert zijn schema ergens
op — contracttype, brontype, of een apparaat verplaatsbaar is — dus dit is een
eigenschap van voorwaardelijke formulieren en niet een eigenaardigheid van één kaart.
De frontend splitst de fouten daarom in *zichtbaar* en *verweesd*, en toont de
verweesde als notice met het veldlabel erbij (`core/forms.js`).

Gevonden doordat een vast contract om de energiebelasting werd gevraagd terwijl het
paneel dat veld op een vast contract juist verbergt: de installateur zag een prijsbron
die niet werkte en nergens een reden (bevinding productie-installatie, 2026-08-07).

Aanvullende regels die expliciet vastliggen:

- **Het overschot moet het apparaat kunnen dragen.** Een apparaat waarvan
  `nominal_power_w` groter is dan het actuele overschot wordt niet geadviseerd.
  Tot 0.1.2 werd alleen `surplus >= min_solar_surplus_w` getoetst, waardoor 600 W
  overschot "benut je zonneoverschot" opleverde voor een vaatwasser van 2000 W —
  1400 W kwam van het net, en de besparing werd berekend alsof de hele cyclus van
  het dak kwam. Een apparaat met **onbekend** vermogen wordt niet uitgesloten: dat
  zou een gok de andere kant op zijn (§12).
- **Bij meerdere kandidaten wint de grootste die past**, na prioriteit. Die sortering
  bestond al, maar zonder de bovenstaande filter koos zij juist het apparaat dat het
  slechtst paste.
- **`days_of_week` wordt gehandhaafd.** Een apparaat krijgt geen advies op een dag die
  de bewoner heeft uitgevinkt. Tot 0.1.2 werd het veld opgeslagen en getoond maar door
  niets gelezen: het paneel vroeg, de bewoner antwoordde, en de motor overrulede dat
  stilzwijgend. Een genegeerde instructie is erger dan een afwezig veld. Een lege lijst
  kan niet voorkomen — die normaliseert naar alle dagen, want "geen enkele dag" is wat
  uitschakelen voor is.
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
| `sensor.domotiapp_energy_home_consumption` | `Home consumption` | `power` | measurement | `W` |
| `sensor.domotiapp_energy_current_advice` | `Current advice` | — | — | — |
| `binary_sensor.domotiapp_energy_peak_risk` | `Peak risk` | `problem` | — | — |
| `binary_sensor.domotiapp_energy_attention` | `Attention` | `problem` | — | — |

Deze Engelse namen staan tweemaal: in `translations/en.json` en in
`const.ENTITY_OBJECT_ID_NAMES`. Het vertaalbestand tijdens runtime lezen zou blokkerende
I/O in de event loop zijn, dus een test vergelijkt beide lijsten.

Home consumption kwam er in 0.5.0 bij en attention in 0.11.0 (§45); beide zijn
toevoegingen, dus geen enkele bestaande ID verschoof.

Fase 5 bevat tests die bevestigen dat deze ID's ontstaan, dat ze niet meebewegen met
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
15. Niet-admins kunnen geen **installateursvelden** wijzigen, ook niet via directe
    WS-calls; de bewonersvelden uit §33.4 kunnen zij wél wijzigen en niets daarbuiten.
    *(Herschreven in ronde 1. De oude formulering — "de configuratie niet wijzigen" —
    beschreef een product waarin de bewoner zijn eigen stille uren niet kon instellen.)*
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

---

## 32. Het gereed-venster en gereedheid (ontwerp, nog niet gebouwd)

**Status: ontwerp.** Hiervan is nog geen regel code geschreven. Deze sectie legt het
model vast zodat het gelezen en aangevallen kan worden vóórdat er iets bestaat. De
aansturing zelf blijft buiten beschouwing; dit gaat uitsluitend over wat er geregistreerd
wordt en wat de coach ermee zegt.

### 32.1 Waarom het huidige model niet klopt

Een bewoner die zegt *"hij mag draaien wanneer het gunstig is, als hij maar om 7 uur
klaar is"* kan dat vandaag niet invullen. Hij kan alleen een **startvenster** opgeven, en
dat is een ander soort uitspraak.

Drie gevolgen:

1. **Bederf is niet uit te drukken.** Een wasmachine die om 03:00 klaar is, laat het
   wasgoed vier uur nat liggen. Dat is geen geluidsprobleem — `is_noisy` dekt het niet —
   maar een eis aan de *eindtijd*: klaar kort vóórdat er iemand is om het eruit te halen.
   Met een startvenster is dat niet te zeggen, want dezelfde starttijd is goed of fout
   afhankelijk van hoe lang het programma duurt.
2. **`duration_minutes` doet niets.** Het veld wordt opgeslagen en getoond, en de
   rekenmotor raadpleegt het nergens; alleen een validator controleert of het in het
   venster past. Zie de staande regel dat een opgeslagen veld zonder gebruik een belofte
   is die we niet nakomen (§12).
3. **Er is geen urgentie.** De motor kent alleen "nu" en zegt nooit dat je nú moet
   starten om een moment te halen.

### 32.2 Het gereed-venster

Twee velden vervangen `earliest_start` en `latest_finish`. **Even veel invoer, een
preciezere vraag:**

```text
ready_from    — niet eerder klaar dan   (tegen bederf; optioneel)
ready_before  — uiterlijk klaar         (de deadline; optioneel)
```

Het startvenster is voortaan **afgeleid**, niet ingevoerd:

```text
laatste start  = ready_before - duration_minutes
vroegste start = ready_from   - duration_minutes
```

Daarmee krijgt `duration_minutes` zijn functie: zonder de duur is er geen deadline te
berekenen.

- Beide velden zijn onafhankelijk optioneel. Alleen `ready_before` is het normale geval
  ("klaar om 7:00, eerder mag ook"). Alleen `ready_from` betekent "niet eerder klaar
  dan", zonder bovengrens. Geen van beide betekent: geen tijdsbeperking.
- Een `ready_before` die vóór `ready_from` valt is een venster over middernacht, met
  dezelfde regel als overal: lengte is `(einde - begin) mod 1440`, begin inclusief, einde
  exclusief, gelijke tijden ongeldig (§16).
- **Zonder `duration_minutes` degradeert `ready_before` naar de oude betekenis**: "mag
  niet meer draaien na". Dat is de veilige terugval en het dichtst bij wat er nu gebeurt.
  Er is dan geen urgentie-advies, want dat vereist de duur. Er wordt geen duur geraden.

### 32.3 Het urgentie-advies

Hieruit volgt een advies dat vandaag niet bestaat en dat **geen enkele prognose
vereist** — je hoeft de toekomst niet te kennen om te weten dat je nú moet starten:

| | |
|---|---|
| Reason code | `deadline_approaching` |
| Rank | **3 — harde tijdsgrenzen** |
| Severity | `warning` |
| Tekst | "Start [naam] nu om [tijd] te halen." |

Rank 3 staat al in de sorteervolgorde van §16 en was tot nu toe leeg; dit advies vult die
plek. Het staat daarmee **boven** zonnebenutting en prijs, en dat is de bedoeling: een
deadline is hard, wachten op zon is een optimalisatie.

Het advies vuurt wanneer `nu >= laatste start - URGENCY_LEAD_MINUTES` en het apparaat nog
werk te doen heeft (§32.5), en loopt tot de deadline. Daarna zwijgt het: "je hebt het
gemist" helpt niemand.

`URGENCY_LEAD_MINUTES` is een **vaste constante, geen instelling** — dezelfde redenering
als bij de hysterese (§16): dit beschrijft hoe de motor met tijd omgaat, niet iets waar
een klant een mening over heeft.

### 32.4 Migratiepad: niemand vult iets opnieuw in

De vertaling is getrouw en gebeurt in `_async_migrate_func` van de `Store` bij een
verhoogde `minor_version`. Dat is een **schemamigratie, geen gebruikersactie**, dus de
revision blijft ongemoeid (§13):

```text
ready_from   = earliest_start + duration_minutes   (of earliest_start zonder duur)
ready_before = latest_finish
```

`earliest_start` betekende "niet starten vóór"; opgeteld bij de duur is dat exact "niet
klaar vóór". `latest_finish` betekende "mag niet meer draaien na", wat het dichtst bij
een deadline ligt.

#### Het oude venstermodel was defect, niet alleen anders

**Dit hoort in de CHANGELOG als bugfix**, en niet als "het werkt ineens anders" — anders
leest een klant een correctie als een grillige wijziging (besluit Sven, 2026-08-07).

Het oude model toetste alleen of de *start* binnen het venster viel. Een vaatwasser van
180 minuten met `latest_finish` op 06:00 mocht daardoor om 05:55 beginnen en liep tot
08:55 door — bijna drie uur voorbij de eindtijd die de bewoner had opgegeven. Voor een
apparaat dat om 07:00 leeggeruimd moet worden, of dat in de stille uren hoort te zwijgen,
is dat precies het scenario dat het venster moest voorkomen.

De validator zag het niet: die controleerde of de duur in het venster *paste*
(`duration_minutes > window_length`), nooit of er op het gekozen moment nog genoeg tijd
over was.

Het nieuwe model eist dat dezelfde vaatwasser om 03:00 begint. Dat is strenger, en het is
de correctie. Voor een apparaat zonder ingevulde duur is de migratie volledig
gedragsneutraal.

### 32.5 Gereedheid, en waarom de vlag niet in de configuratie hoort

Een vaatwasser start zodra de klep dichtgaat, maar niets in dit systeem weet of er vaat in
zit. Zonder dat gegeven adviseert de coach vroeg of laat het draaien van een lege machine
— een advies dat een bewoner absurd vindt, en dat kost meer vertrouwen dan geen advies.

**Eén configuratieveld:**

```text
needs_ready_flag — boolean, default per type
```

Default `true` voor `dishwasher`, `washing_machine` en `dryer`; **`false` voor de rest,
inclusief `ev_charger`.**

**Waarom een laadpaal `false` krijgt** (besluit Sven, 2026-08-07): een lader meldt via
`status_entity` zelf of er een auto hangt, en een vlag die de bewoner met de hand moet
omzetten terwijl het systeem het kan zien is precies het invulwerk waar deze ronde vanaf
wil. Voor een lader zónder statuskoppeling is dat jammer; dat wordt opgelost met een
koppeling, niet met een knop. Het blijft een **typedefault**, dus een installateur kan
hem aanzetten waar hij wél nodig is.

**De vlag zelf staat buiten de configuratie**, in een eigen store:

```text
key:  domotiapp_energy.runtime
{ "ready": { "<device_id>": "<iso timestamp>" } }
```

**De reden is hard.** De vlag gaat automatisch uit zodra het programma klaar is. Zou hij
in de configuratie staan, dan is dat een schrijfactie die niet van de gebruiker komt, en
die verhoogt de revision — waarna de `expected_revision` van een openstaand formulier
verloopt en een geldige opslagpoging wordt geweigerd met `revision_conflict` (§13). Een
vaatwasser die twee keer per dag draait zou dat twee keer per dag doen. Dat is precies de
fout die in ronde A de formulieren brak.

De runtime-store heeft dus **geen revision** en valt buiten `expected_revision`. Hij wordt
direct geschreven; twee tot vier schrijfacties per apparaat per dag zijn verwaarloosbaar
en vragen niet om de uitgestelde flush die het logboek nodig had (§13).

**Bediening, geen configuratie.** Het WS-commando `domotiapp_energy/devices/set_ready` is
**niet** `require_admin`: dit is de bewoner die zegt dat de machine vol is, niet de
installateur die iets instelt. Zelfde behandeling als `coach/recalculate` (§14).

### 32.6 "Klaar" detecteren

In volgorde van betrouwbaarheid; de eerste die kan, wint:

| # | Bron | Signaal |
|---|---|---|
| 1 | `status_entity` | gaat naar `off`, `idle` of `standby` |
| 2 | `remaining_time_entity` | bereikt 0 |
| ~~3~~ | ~~`power_entity`~~ | **vervallen, zie hieronder** |

**Methode 3 is niet gebouwd** (besluit Sven, 2026-08-11, bij het bouwen van fase 3).

De aanleiding was zijn vraag: een vaatwasser die tussen wassen en drogen even niets
trekt, ziet er hetzelfde uit als een vaatwasser die klaar is — welke N kies je, en
wat gebeurt er als je het mis hebt? Bij het beantwoorden bleek het antwoord niet in
de keuze van N te zitten:

- **De faalwijze is stil.** Eén vermogenspiek van een display of een smart plug en
  de vlag valt weg, zonder dat iemand ziet waarom. De bewoner moet opnieuw op de
  knop drukken en weet niet dat dat nodig is.
- **En de winst is er bijna niet.** De vlag vervalt al aan het einde van het
  gereed-venster, en een apparaat zónder venster krijgt sowieso geen urgentie-advies
  (geen deadline, dus geen laatste start). Vermogensdetectie zou dus alleen een vlag
  inkorten die toch al op het punt stond te vervallen.

Een zichtbare, zelfcorrigerende fout — advies voor een machine die al gedraaid heeft
— is goedkoper dan een onzichtbare die de hele functie stilzet. Dus: **zwijgen in
plaats van gokken**, zoals overal in dit project.

Wat er wél gebeurt bij een apparaat zonder koppeling staat hieronder, en dat is de
tweede helft van dit besluit.

De statenlijst bij methode 1 is vast en wordt gedocumenteerd. Meldt de entiteit iets
anders, dan is er geen detectie; er wordt niet geraden welke toestand "klaar" zou kunnen
betekenen.

**Is er geen enkele entiteit gekoppeld, dan wordt er niet gegokt.** Het paneel zegt erbij
dat we niet kunnen zien wanneer het apparaat klaar is, en de bewoner zet de vlag zelf uit.

**En het zegt dat op het moment dat hij de knop indrukt**, niet pas wanneer hij zich
afvraagt waarom er niets gebeurde (besluit Sven, 2026-08-11). Daarom draagt het
antwoord van `set_ready` een `auto_clears` mee, en kiest het paneel tussen twee hele
zinnen:

> *"Staat vol. Dit vervalt vanavond om 22:00, of eerder zodra hij klaar is."*

> *"Staat vol. We kunnen niet zien wanneer hij klaar is, dus dit blijft staan tot
> morgen om 07:00. Zet het eerder uit als er niets meer in zit."*

**Wel vervalt de vlag**, en dat is geen aanname over de machine maar een
houdbaarheidstermijn op de *intentie*: "hij is vol" van vanochtend zegt niets meer over
morgen. Zonder vervaltermijn blijft een vergeten vlag het urgentie-advies eeuwig voeden.

| Situatie | Vervalt |
|---|---|
| Apparaat met een gereed-venster | aan het einde van dat venster |
| Apparaat zonder venster | **24 uur na het zetten** |

**Niet om middernacht** (besluit Sven, 2026-08-07). Middernacht is precies verkeerd voor
een woning die 's avonds laat de vaatwasser vult: de vlag zou verlopen voordat de machine
gedraaid heeft. Vierentwintig uur zegt bovendien iets zinnigers — als er een dag lang
niets is gebeurd, klopt er iets anders niet.

`READY_FLAG_MAX_AGE_HOURS` is een **vaste constante, niet instelbaar**, net als de
hysterese en `URGENCY_LEAD_MINUTES`.

**Het paneel noemt het vervalmoment** bij het zetten van de vlag, zodat een bewoner er
niet door verrast wordt.

### 32.7 De vier beperkingen: wat wel en wat niet

| Beperking | Voorbeeld | Dekking |
|---|---|---|
| **Contract** | nachtdraaien loont alleen bij een dynamisch tarief | bestaand; geen nieuw veld |
| **Overlast** | droger midden in de nacht | bestaand: `is_noisy` + stille uren |
| **Bederf** | was die om 03:00 klaar is | **nieuw: `ready_from`** |
| **Aanwezigheid** | geen droger aan als niemand thuis is | **bewust buiten deze ronde** |

**Contract vraagt geen veld.** De motor kiest al op `contract_type` welk advies hij geeft.
Wat ontbreekt is *planning* — hij kent alleen "nu" en heeft geen prijs- of zonneprognose,
dus hij kan nooit zeggen "wacht tot morgenmiddag". Het gereed-venster is de goedkoopste
manier om planning binnen te halen zónder prognose.

**Aanwezigheid blijft eruit**, en dat is een keuze:

- het staat loodrecht op het gereed-venster en de gereedheid, die wél samenhangen;
- het vereist een entiteitskoppeling die niet elke klant heeft;
- het is later toe te voegen zonder migratie: één optioneel veld en één filter in de
  apparaatselectie.

### 32.8 Wat deze ronde niet raakt

- **De aansturing zelf.** Eigen release, eigen spec.
- **De laadtoestand van een auto en het voertuig als object.** Zolang die er niet is,
  blijft "energie per laadsessie" een schatting en blijft het advies gecapt op `medium`
  (§16).

  > **Deels ingehaald door §34.** De laadtoestand komt daar wél binnen, met een
  > doel-SOC en een accucapaciteit erbij, en voor een laadpaal die daarmee compleet is
  > vervalt de cap op `medium`. Het **voertuig als eigen object** blijft eruit, en die
  > grens is in §34.7 expliciet getrokken: één auto per paal, geen wagenpark.
- **Prijs- en zonneprognose**, en daarmee het activeren van `solar_forecast`. Echte
  planning is een eigen onderwerp; het urgentie-advies levert het grootste deel van de
  winst zonder.

### 32.9 Gevolgen elders

- **§8**: `earliest_start` / `latest_finish` vervallen uit het veldoverzicht,
  `ready_from` / `ready_before` / `needs_ready_flag` komen erbij. `duration_minutes`
  verdwijnt niet langer uit het formulier — het heeft nu een functie.
- **§13**: een tweede store, zonder revision, met de motivatie uit §32.5.
- **§14**: `devices/set_ready`, zonder `require_admin`, met het onderscheid tussen
  configuratie en bediening dat daar nu is vastgelegd.
- **§16**: `deadline_approaching` in de reason codes en op rank 3; de vensterregels
  verwijzen naar het gereed-venster.
- **De datakwaliteitschecklist**: het item `flexible_devices_have_time_window` gaat over
  het gereed-venster in plaats van het startvenster. De weging verandert niet.

### 32.10 Bouwvolgorde

Drie fases, elk met een eigen PR, elk op zichzelf bruikbaar:

| Fase | Inhoud | Klaar wanneer |
|---|---|---|
| 1 | `ready_from` / `ready_before`, de afgeleide start, de migratie, formulier en validatie | een bestaande woning laadt ongewijzigd door en het nieuwe venster stuurt het advies |
| 2 | `deadline_approaching` op rank 3, met `URGENCY_LEAD_MINUTES`, en de duur via `required_duration_minutes(device, snapshot)` (§34.8) | het advies verschijnt op tijd en wint van zon en prijs |
| 3 | `needs_ready_flag`, de runtime-store, `set_ready`, detectie en vervaltermijn | de vlag stuurt het urgentie-advies en gaat vanzelf uit |

Fase 2 kan pas na 1 (de deadline volgt uit het venster), fase 3 kan pas na 2 (de vlag
bepaalt of het urgentie-advies mag vuren).

---

## 33. Twee rollen: de installateur en de bewoner

**Status: ontwerp, ronde 1.** Deze sectie legt vast wie welk veld bezit, wat een
bewoner ziet en mag, en waarom de admincontrole in de WebSocket-API van vorm
verandert zonder zwakker te worden.

### 33.1 De context die tot nu toe niet opgeschreven stond

DomotiApp Energy staat uitsluitend bij klanten van DomotiTech, als onderdeel van een
pakket. Er zijn twee soorten gebruikers, en ze hebben verschillende vragen:

- **de installateur** richt de woning in en beheert de configuratie;
- **de bewoner** is baas over zijn eigen woning en bepaalt wat de automatisering doet.

De bewoner moet zo min mogelijk hoeven zoeken.

Uit die tweede zin volgt het scenario waar deze hele sectie op rust: **de bewoner die
belt.** Hij ziet dat zijn hoofdzekering op 25 A staat terwijl er 40 in de meterkast zit,
en hij belt DomotiTech. Vandaag kan dat niet — hij ziet het veld niet, dus de fout blijft
onzichtbaar fout staan, en niemand ontdekt hem tot er iets misgaat.

### 33.2 Wat er vandaag misgaat

Een niet-admin ziet drie van de zeven tabbladen: Overzicht, Energiecoach, Logboek. Achter
het adminslot zitten Woning, Energiebronnen, Apparaten en **Voorkeuren**.

Dat laatste is een defect en niet alleen een ongelukkige indeling. Voorkeuren bestaat
vrijwel volledig uit bewonersinstellingen — stille uren, hoeveel adviezen ik wil zien, of
ik de geschatte besparing wil zien — en is volledig dichtgetimmerd. **Een bewoner kan
vandaag zijn eigen stille uren niet instellen.** Hetzelfde geldt voor het gereed-venster
uit paragraaf 32, dat expliciet voor hem is gebouwd: hij mag zeggen dat de machine vol is
(`set_ready`, bewust geen `require_admin`) maar niet wanneer zij klaar moet zijn.

### 33.3 Het criterium

> **De installateur bezit wat de woning *is*. De bewoner bezit wat de woning moet *doen*.**

Een fout in de eerste categorie is voor de bewoner iets om te **melden**, niet om te
repareren. Daarom is het antwoord op 33.2 niet "geef hem meer rechten" maar: laat hem
alles zien, laat hem bewerken wat van hem is, en zeg bij de rest wie het beheert.

Dit criterium is geen weergave van vertrouwen. Een bewoner mag `main_fuse_a` niet zetten
omdat hij niet in de meterkast heeft gekeken, niet omdat hij niet te vertrouwen is.

### 33.4 De veldeigenaarschapskaart

Dit is de normatieve lijst. Zij staat in de code op een plek (`frontend/core/roles.js`)
en nergens anders; een veld dat er niet in staat is installateursgebied, zodat een nieuw
veld standaard veilig is en niet standaard open.

| Formulier | Bewoner bezit | Installateur bezit |
|---|---|---|
| **Installatie, woning** | *(niets)* | `home_name`, `phases`, `main_fuse_a`, `max_grid_power_w`, `peak_warning_percent`, `contract_type`, alle prijs-, belasting-, btw-, teruglever- en salderingsvelden, `low_price_threshold_eur_kwh`, `high_price_threshold_eur_kwh`, `min_solar_surplus_w`, `control_level` |
| **Installatie, energiebronnen** | *(niets)* | alles |
| **Apparaten** | `control_mode`, `ready_from`, `ready_before`, `days_of_week`, `is_noisy`, `priority` | `name`, `device_type`, `enabled`, `location`, `notes`, `nominal_power_w`, `energy_per_cycle_kwh`, `duration_minutes`, `is_flexible`, `capabilities`, `control_forbidden` (+reden), alle `entity_links` |
| **Mijn voorkeuren** | alles | *(niets)* |

Vier grenzen die niet vanzelf spreken en daarom hier hun reden krijgen:

- **`home_name` blijft van de installateur**, ook al is het de naam van andermans huis.
  Hij staat ook in de config entry en hernoemt het device in het device registry
  (paragraaf 6 en 19); het is dus geen paneelveld maar een HA-object. Hem openzetten zou
  `home/update` uit de adminlijst trekken voor een cosmetisch veld.
- **De prijsgrenzen blijven van de installateur**, hoewel "wat vind ik duur" een
  smaakoordeel is. Ze zijn all-in bedragen in euro's per kWh en hun hulptekst
  veronderstelt een technische lezer (paragraaf 16). Dit is de meest waarschijnlijke
  kandidaat voor een volgende ronde; hem nu verplaatsen zou een derde WS-commando kosten
  voor twee velden.
- **`enabled` blijft van de installateur, `control_mode` niet.** De uitknop van de bewoner
  is `monitor_only`, en dat is precies waar `control_mode` voor bestaat. `enabled` haalt
  de hele rij uit de datakwaliteit en de rekenmotor, en dat is een andere handeling.
- **`is_flexible` van de installateur, `is_noisy` van de bewoner.** `is_flexible` is een
  uitspraak over de machine (kan dit ding verplaatst worden), `is_noisy` over het
  huishouden (heb ik daar 's nachts last van).

### 33.5 Twee dode velden worden geschrapt, niet verhuisd

`default_strategy` en `respect_max_grid_load` worden opgeslagen, gevalideerd en getoond,
en **door niets gelezen**. Beide liggen op de grens van bewonersgebied, dus zonder besluit
zouden ze in deze ronde meeverhuizen, en dan staat er een knop op het tabblad van de
bewoner die niets doet. Dat is slechter dan geen knop: een genegeerde instructie kost meer
vertrouwen dan een afwezig veld (dezelfde regel die `days_of_week` in 0.1.2 heeft
gerepareerd).

Ze verdwijnen uit `HomeProfile`, `UserPreferences`, de formulieren en `validators.py`.
`from_dict` negeert onbekende sleutels, dus een bestaande opslag laadt ongewijzigd door en
er is geen migratie nodig. Besluit Sven, 2026-08-07: **komen ze later terug, dan met een
lezer in dezelfde ronde.**

### 33.6 Tabbladindeling: een set voor beide rollen

Zeven tabbladen worden er zes, voor iedereen:

```text
Overzicht - Energiecoach - Apparaten - Mijn voorkeuren - Installatie - Logboek
```

`Installatie` is het samengaan van `Woning` en `Energiebronnen` als twee secties onder een
tabknop. Het hoeft **geen** enkel bestand te worden; de tab mag zijn twee bestaande
modules onder elkaar monteren.

**Beide rollen zien dezelfde zes tabbladen. Er is geen tabblad dat een bewoner niet ziet.**

Dat is de kern van het voorstel en het is een keuze tegen het alternatief in (twee
tabbladensets, een per rol). De reden is het telefoongesprek uit 33.1: met twee sets
kijken installateur en bewoner naar verschillende schermen en is *"ga naar Installatie,
wat staat er bij Hoofdzekering?"* geen bruikbare zin. Een set betekent een mentaal model,
een codepad en een testmatrix. Het scheelt de installateur bovendien ook een tabblad.

De bewoner heeft daarmee vijf vragen en vijf plekken: hoe doe ik het (Overzicht), wat moet
ik nu doen (Energiecoach), wanneer moet de vaatwasser klaar zijn (Apparaten), laat me
slapen (Mijn voorkeuren), waarom staat mijn zekering verkeerd (Installatie). Het Logboek
is diagnostiek en wordt zelden geopend, maar hoort niet verborgen: het is de enige plek
waar staat wat er is gebeurd.

### 33.7 Zichtbaar maar niet bewerkbaar, zonder tweede formulierpad

Er komt **geen** read-onlyvariant van enig formulier. Het mechanisme bestaat al en is in
de browser bewezen (ronde B, bevinding 4a):

- `ha-form` draagt een per-veld `disabled: true` uit het schema door tot een echte
  uitgeschakelde control, **met behoud van de waarde**;
- `home.js` mapt zijn schema al en injecteert `disabled: true` bij de prijscomponenten
  zodra een all-in bron bestaat.

De implementatie is daarom een functie in `core/forms.js`:

```text
applyRole(schema, isAdmin) -> schema waarin elk installateursveld disabled: true draagt
```

met de eigenaarschapskaart uit 33.4 in `core/roles.js` als enige bron. Daarnaast per
kaart, voor een niet-admin:

- de opslaanknop verborgen via `setVisible` (nooit alleen `hidden`, zie CLAUDE.md);
- toevoegen en verwijderen verborgen, want een bewoner voegt geen bron of apparaat toe;
- een `notice()` met de vaste tekst **"Deze gegevens worden beheerd door DomotiTech."**

**Een rij mag nooit verborgen worden voor een bewoner.** Uitgrijzen is het hele punt: een
verborgen fout blijft fout.

**Wat de testlaag hier wel en niet kan.** De jsdom-stub van `ha-form` zet alleen
properties en rendert geen control, dus **geen enkele test in die laag kan bewijzen dat
een uitgegrijsd veld een klik weigert.** Wat daar wel toetsbaar is, en verplicht wordt:
voor elk formulier draagt bij `isAdmin = false` elk installateursveld `disabled: true` en
elk bewonersveld niet. Dat vangt de drift die ontstaat zodra iemand een veld toevoegt.

Het gedrag zelf wordt geverifieerd in de echte browser, met echte kliks, **als tweede
gebruiker zonder adminrechten** (staande afspraak, CLAUDE.md). Dat vereist een niet-admin
HA-account voor het paneel; voor de WS-kant bestaat die route al (`ha_check.py --as`).

### 33.8 Een foutmelding aan een bewoner luidt anders

`splitFieldErrors` blijft ongewijzigd werken: een uitgegrijsd veld is gerenderd, dus de
melding landt er gewoon op. Maar de **tekst** klopt niet meer.

"Vul de energiebelasting aan" bij een veld dat de lezer niet kan aanraken is een opdracht
die hij niet kan uitvoeren, precies de faalvorm die paragraaf 16 al beschrijft voor een
melding die nergens landt, alleen een stap later. Voor een niet-admin geldt daarom: een
melding op een **installateursveld** wordt vervangen door een meldzin die zegt dat
DomotiTech dit beheert en dat hij het kan doorgeven. Een melding op een **bewonersveld**
blijft ongewijzigd, want dat kan hij wel oplossen.

De backendteksten veranderen niet. Dit is een vertaling in de frontend, op dezelfde plek
waar de verweesde meldingen al worden opgevangen.

### 33.9 De WebSocket-API: `require_admin` bewaakt installateursvelden

Paragraaf 14 legde de grens bij **configuratie versus bediening**: wat de opgeslagen
configuratie wijzigt is admin, wat de huidige toestand meldt (`coach/recalculate`,
`devices/set_ready`) niet. Die grens is niet fout, maar hij dekt dit geval niet: de stille
uren en het gereed-venster van een bewoner *zijn* configuratie, verhogen wel de revision,
en horen toch niet achter het adminslot.

De regel wordt daarom:

> **`require_admin` bewaakt installateursvelden, niet alle schrijfacties.**

**Timmer dit later niet dicht als inconsistentie.** Dat een niet-admin een schrijfcommando
mag uitvoeren dat de revision ophoogt, ziet eruit als een gat in de beveiliging en is het
niet: de grens ligt bij *wiens* gegevens er veranderen, niet bij *of* er iets verandert.
Een bewoner die zijn eigen stille uren niet mag zetten omdat hij geen beheerder is, kan de
functie niet gebruiken, en dan is het tabblad Voorkeuren zinloos voor precies de persoon
voor wie het bedoeld is. Zelfde redenering als bij `set_ready` in 32.5.

Concreet:

| Commando | Nu | Wordt |
|---|---|---|
| `home/update` | admin | **ongewijzigd admin**, de hele Installatietab is installateursgebied (33.4) |
| `sources/*` | admin | **ongewijzigd admin** |
| `devices/create`, `devices/update`, `devices/delete` | admin | **ongewijzigd admin**, de volledige rij blijft installateurswerk |
| `logs/clear` | admin | **ongewijzigd admin** |
| `preferences/update` | admin | **open voor elke ingelogde gebruiker**, elk veld is bewonersgebied |
| `devices/set_operation` | — | **nieuw, open voor elke ingelogde gebruiker** |

`devices/update` blijft dus volledig admin, en dat is bewust. Er is geen veldfilter op dat
commando: zou een bewoner het mogen aanroepen, dan kan hij `nominal_power_w`,
`entity_links` en `control_forbidden` overschrijven, en verdwijnt een afspraak met een
klik.

### 33.10 `devices/set_operation`

```text
domotiapp_energy/devices/set_operation
  device_id         : str
  expected_revision : int
  operation         : { control_mode?, ready_from?, ready_before?,
                        days_of_week?, is_noisy?, priority? }
```

- **Strikte allow-list.** Elke andere sleutel in `operation` levert `invalid_format` op.
  Niet negeren, niet stilzwijgend laten vallen: een verzoek dat meer wil dan het mag is
  een fout die de aanroeper hoort te zien.
- **Geen `require_admin`**, om de reden in 33.9. Een admin mág hem gebruiken, maar het
  paneel doet dat niet: een installateur bewerkt de hele rij en slaat die heel op via
  `devices/update`, een bewoner bewerkt zijn zes velden en stuurt alleen die. Twee paden,
  omdat het twee verschillende handelingen zijn.
- **Verhoogt de revision met 1**, want dit *is* een configuratiewijziging uit een
  expliciete gebruikersactie (paragraaf 13). Dat wijkt bewust af van `set_ready`, dat in
  een eigen store zonder revision leeft omdat die vlag vanzelf uitgaat.
- Antwoordvorm gelijk aan elk ander schrijfcommando: `{ "revision", "item", "issues" }`.
- Dezelfde validatie als `devices/update`, inclusief de blokkade uit 33.11.

### 33.11 `control_forbidden` wordt hier voor het eerst dragend

Paragraaf 12 noemt drie soorten waarheid over aansturing. Ze mappen exact op de twee
rollen:

| Veld | Soort waarheid | Eigenaar |
|---|---|---|
| `capabilities` | wat de hardware kan | installateur |
| `control_forbidden` (+reden) | wat met deze klant is afgesproken | installateur |
| `control_mode` | wat er gewild wordt | **bewoner** |

De enige harde blokkade in `validators.py`, `control_forbidden = true` samen met een
aansturende `control_mode`, was tot nu toe een dode regel: alleen een admin kon ooit
`control_mode` zetten, en die zet ook `control_forbidden`. **Vanaf deze ronde is het het
veto van de installateur over wat de bewoner wil**, en dat is exact waar paragraaf 12 hem
voor ontwierp. De blokkade geldt onverkort op `set_operation`, met foutcode
`invalid_format`.

Daaruit volgt ook wat het paneel moet tonen: een bewoner die `control_mode` niet mag
verhogen omdat er een afspraak op ligt, hoort **de reden** te zien. Daarom is
`control_forbidden_reason` zichtbaar voor de bewoner, uitgegrijsd zoals de rest.

### 33.12 Gevolgen elders

- **Paragraaf 8**: `default_strategy` vervalt uit Woning, `respect_max_grid_load` uit
  Voorkeuren. De tabbladenlijst wordt de zes uit 33.6.
- **Paragraaf 14**: de regel uit 33.9 en het nieuwe commando uit 33.10. Het bestaande
  onderscheid configuratie/bediening blijft staan; er komt een tweede as bij.
- **Paragraaf 29, acceptatiecriterium 15**: "Niet-admins kunnen de configuratie niet
  wijzigen (ook niet via directe WS-calls)" wordt: *"Niet-admins kunnen geen
  installateursvelden wijzigen, ook niet via directe WS-calls; de bewonersvelden uit 33.4
  kunnen zij wel wijzigen en niets daarbuiten."*
- **Paragraaf 7**: het paneel blijft `require_admin=False`; ongewijzigd.
- **README**: de rolindeling hoort bij *setup* en bij *security notes*: welke velden een
  bewoner mag wijzigen, en dat de backend dat afdwingt.

### 33.13 Wat deze ronde niet raakt

- **De prijsgrenzen naar de bewoner.** Kandidaat voor later (33.4), nu niet.
- **De energiescore.** Eigen ronde, eigen SPEC-sectie.
- **De laadpaal.** Eigen ronde; `target_soc_percent` is een bewonersveld en
  `vehicle_capacity_kwh` een installateursveld, dus de kaart uit 33.4 breidt dan uit
  zonder van vorm te veranderen.
- **Rollen fijner dan twee.** Er is geen derde rol en geen per-veldrecht per klant. Twee
  rollen volgen uit `hass.user.is_admin`, dat HA al bijhoudt; iets fijners vereist een
  eigen gebruikersadministratie en die hoort niet in deze integratie.

### 33.14 Klaar wanneer

- een niet-admin ziet zes tabbladen, kan op elk daarvan elk veld **lezen**, en kan
  uitsluitend de bewonersvelden uit 33.4 wijzigen;
- een niet-admin die het probeert via een directe WS-call op een installateursveld krijgt
  `not_authorized` of `invalid_format`, aantoonbaar met `ha_check.py --as`;
- de frontendtests tonen per formulier aan dat de eigenaarschapskaart wordt toegepast;
- de twee dode velden zijn weg en een bestaande opslag laadt ongewijzigd door;
- geverifieerd in de echte browser als niet-adminaccount, met echte kliks.

---

## 34. De laadpaal: twee modi die geen glijdende schaal zijn

**Status: ontwerp, besloten maar niet gebouwd.** Deze sectie legt het datamodel vast en
zegt wat het formulier toont. De aansturing zelf blijft de aansturingsrelease (§32.8); dit
gaat over wat er geregistreerd wordt, wat het paneel ermee laat zien en wat de coach
ermee zegt.

### 34.1 Waarom dit twee dingen zijn en niet één met een schuifje

Een laadpaal kent twee manieren van laden die niets met elkaar te maken hebben:

| | Wat de bewoner zegt | Wat het systeem moet kunnen |
|---|---|---|
| **Plannen** | "vol om 7 uur" | uitrekenen hoeveel er nog in moet, dus hoe lang het duurt, dus wanneer het uiterlijk moet beginnen |
| **Opportunistisch** | "laad wanneer het goedkoop is" | herkennen dat de prijs laag is |

Het verschil is niet gradueel, en dat komt door één ding: **zonder de laadtoestand van de
auto bestaat de hoeveelheid niet.** Geen hoeveelheid betekent geen duur, en geen duur
betekent geen laatste startmoment. Een deadline die niet uit te rekenen is, is slechter
dan geen deadline: dan zou het urgentie-advies (§32.3) op een gok vuren, en dat is precies
wat harde regel 1 verbiedt.

Opportunistisch laden is dus geen afgezwakte planning. Het is een andere uitspraak, die
niets nodig heeft wat er niet is.

### 34.2 De laadtoestand alleen is niet genoeg

`battery_level_entity` bestaat al voor `ev_charger`, met de hulptekst "de laadtoestand van
de auto, als de laadpaal die meldt". Maar een percentage is geen energie. Om van een SOC
naar een laadduur te komen:

```text
laadduur_minuten = (doel% − huidig%) / 100 × accucapaciteit_kwh / laadvermogen_w × 60000
```

Wat daarvoor nodig is, en wat er vandaag van bestaat:

| Nodig | Bestaat |
|---|---|
| huidige SOC | **ja** — `battery_level_entity` |
| doel-SOC | **nee** |
| accucapaciteit van de auto in kWh | **nee** — een laadpaal publiceert dit niet |
| laadvermogen | ja — `nominal_power_w` |
| de deadline | ja — `ready_before` (§32.2) |

"Vol" is bij bijna niemand 100%, en de capaciteit weet de paal niet: hij meet stroom, niet
de auto die eraan hangt. Dat zijn precies de twee dingen die een latere release niet kan
afleiden en waarvoor je anders bij elke klant terug moet — dezelfde reden waarom
`capabilities` en `control_forbidden` vroeg zijn toegevoegd (§12).

### 34.3 De twee velden

```text
target_soc_percent      0–100, nullable      — bewonersveld  (§33.4)
vehicle_capacity_kwh    > 0, nullable        — installateursveld
```

**Waarom de eigenaars verschillen.** De capaciteit is een eigenschap van de auto, dus
hetzelfde soort feit als de hoofdzekering: iets wat je opzoekt, niet iets waar je een
mening over hebt. Het doelpercentage is een mening — 80% voor de accu, 100% voor een lange
rit — en het is er één die per week verandert. Daarmee valt hij aan dezelfde kant van
§33.3 als het gereed-venster.

`target_soc_percent` komt er dus bij in `DEVICE_OPERATION_FIELDS` (`const.py`) en in de
bewonerslijst van `frontend/core/roles.js`; `vehicle_capacity_kwh` in geen van beide.
De kaart uit §33.4 breidt daarmee uit zonder van vorm te veranderen.

**Geen defaults.** Niet 80, niet 100, niet een gemiddelde accu. Een stille default zou een
laadduur produceren die op niets slaat, en die duur gaat rechtstreeks een advies in dat
zegt wanneer je moet beginnen. Dezelfde regel als bij `energy_tax_eur_kwh` en
`feed_in_markup_eur_kwh`: een expliciete waarde is een antwoord, "niet ingevuld" blokkeert
(§16).

### 34.4 Geen modus-enum, maar een predicaat

De actieve modus wordt **niet opgeslagen.** Er komt geen `charge_strategy: deadline |
opportunistic`.

```text
kan_plannen(apparaat) =  battery_level_entity is gekoppeld
                       ∧ vehicle_capacity_kwh is ingevuld
                       ∧ target_soc_percent is ingevuld
                       ∧ nominal_power_w is ingevuld
                       ∧ ready_before is ingevuld
```

**Waarom dit afwijkt van `meter_mode` en `price_basis`, die juist wél strikte
opgeslagen keuzes zijn.** Die twee vragen iets wat alleen de installateur weet en wat het
systeem nooit kan zien: een sensor zegt niet of hij de kale marktprijs levert. Hier kan
het systeem wél zien wat het moet weten — of er een SOC-entiteit gekoppeld is, is geen
onbekende. Een enum ernaast introduceert een toestand die de werkelijkheid kan tegenspreken
(`modus = deadline`, geen SOC-koppeling), en dan hebben we een opgeslagen intentie die de
motor moet weigeren. Dat is het soort veld waar §12 een quarantaine voor moest bedenken.

**De vorm bestaat al in dit project**, en dat is het tweede argument: `has_ready_window`
versus `has_complete_ready_window` beantwoordt precies zo de vraag "is deze configuratie
compleet genoeg voor dít gedrag" met een predicaat in plaats van met een vlag. Er zijn dan
ook twee predicaten nodig en niet één, om dezelfde reden als daar — de checklist en de
motor stellen niet dezelfde vraag. Zie §34.6.

De naam en de plaats liggen vast: `engine/completeness.py`, naast
`is_complete_device_profile`, zodat de checklist, het formulier en de coach niet uit
elkaar kunnen lopen.

### 34.5 Het formulier

Bij `device_type = ev_charger`, en alleen daar:

- **`vehicle_capacity_kwh`** staat er altijd. Het is een feit over de auto en het is ook
  zonder planning zinvol om te weten.
- **`target_soc_percent` en het deadlineblok verschijnen alleen wanneer
  `battery_level_entity` gekoppeld is.** Zonder die koppeling is er niets te plannen, en
  een deadlineveld tonen dat nergens toe leidt is dezelfde fout als een batterijniveau op
  een vaatwasser (§8): een vraag zonder antwoord, op het scherm gehouden.
- Het paneel zegt in **één zin** welke modus actief is en waarom. Niet als waarschuwing —
  opportunistisch laden is een volwaardige keuze, geen tekortkoming:

  > *Deze laadpaal laadt opportunistisch: op de goedkoopste momenten, op vol vermogen.
  > Koppel de laadtoestand van de auto om in plaats daarvan op een tijdstip te kunnen
  > plannen.*

- Is de SOC wél gekoppeld maar ontbreekt de capaciteit of het doelpercentage, dan zegt de
  zin dát, met de naam van het ontbrekende veld. Dit is het geval waarin de bewoner iets
  verwacht dat niet gebeurt, en dan is stilte de duurste optie.

`ready_from` blijft ook hier gewoon bestaan en betekent hetzelfde: niet eerder klaar dan.
Bij een auto is dat zelden zinvol, maar er is geen reden hem te verbergen.

### 34.6 De drie lezers, in dezelfde ronde als de velden

Een opgeslagen veld zonder lezer is een belofte die we niet nakomen (§12, en het is de
reden dat `default_strategy` in §33.5 geschrapt is in plaats van verhuisd). Deze twee
velden krijgen daarom in hun eigen ronde drie lezers, en geen ervan stuurt iets aan:

1. **De datakwaliteitschecklist.** Een laadpaal met een SOC-koppeling maar zonder
   capaciteit of doel-SOC is onvolledig, en dat is een gat dat de installateur kan
   dichten — precies het onderscheid tussen "niet gevraagd" en "ontbrekend" uit §16. Dit
   is het tweede predicaat: `is_complete_device_profile` blijft ongewijzigd (vermogen en
   energie per cyclus, voor álle types), en hiernaast komt de vraag of een *planbare*
   laadpaal compleet beschreven is. Ze door elkaar halen zou elke laadpaal zonder SOC
   incompleet maken, en dat is hij niet.
2. **Het paneel toont de afgeleide planning.** "Bij starten om 23:40 is de auto om 07:00
   op 80%." Dat is weergave, geen aansturing (§2.2), en het is meteen de controle op de
   invoer: een capaciteit die er tien keer naast zit, is aan die zin te zien.
3. **Het urgentie-advies van fase 2** rekent zijn laatste startmoment met de afgeleide
   duur in plaats van met `duration_minutes`. Zie §34.8.

### 34.7 Eén auto per paal, en niet meer

**Het model draagt de auto die gewoonlijk aan deze paal hangt. Niet twee auto's, geen
wagenpark.**

Dat staat hier omdat het anders bij de derde klant ontdekt wordt in plaats van nu besloten:
`vehicle_capacity_kwh` hangt aan de laadpaal, dus een huishouden met twee auto's die om en
om laden krijgt één capaciteit voor beide. De planning klopt dan voor de ene en niet voor
de andere, zonder dat iets dat meldt.

Dit is bewust **niet** opgelost, en het alternatief is duidelijk genoeg om te kunnen
afwijzen: een `Vehicle` als eigen object met een koppeling naar de paal, plus een manier om
te weten wélke auto er nu hangt. Dat laatste is het echte werk — het vereist een signaal
dat de meeste palen niet leveren, en zonder dat signaal is het raden welke auto er staat.
Dat is harde regel 1.

Voor twee auto's met sterk verschillende accu's is het eerlijke antwoord daarom: **koppel
de laadtoestand niet, en laad opportunistisch.** Dat werkt zonder capaciteit en zonder
gok. Het staat in de README onder Limitations, want een installateur moet dit weten vóór
hij het invult.

### 34.8 Wat dit voor fase 2 betekent (en waarom het nu al telt)

Voor een vaatwasser is de duur een opgeslagen constante. Voor een laadpaal is zij een
**functie van de actuele laadtoestand**, die elk kwartier verandert.

Dat botst met hoe het startmoment vandaag wordt afgeleid. `DeviceProfile.latest_start` en
`DeviceProfile.earliest_start` zijn **properties op het profiel** en lezen
`self.duration_minutes`. Een property op een dataclass kan per definitie niet naar de
snapshot kijken, dus voor een laadpaal kán het juiste antwoord daar niet uit komen.

Daarom, **in fase 2 en niet later**:

```text
engine/…: required_duration_minutes(device, snapshot) -> int | None
          latest_start_minutes(device, snapshot)      -> int | None
```

Fase 2 hoeft de laadpaal **niet** te ondersteunen: `required_duration_minutes` geeft in
die fase gewoon `device.duration_minutes` terug. Het punt is dat het urgentie-advies zijn
deadline via die functie berekent in plaats van via de property, zodat de laadpaal later
een tak in één functie is en niet een herbouw van het advies.

De properties op `DeviceProfile` blijven bestaan voor wat ze wél goed doen — het
formulier en de validatie, die geen snapshot hebben.

**Dit is de enige reden dat deze sectie vóór fase 2 geschreven is.** De velden zelf hebben
geen haast; de vorm van de duurberekening wel, want die is nu vijf regels en later een
verbouwing.

### 34.9 Opportunistisch laden vraagt geen enkel nieuw veld

De coach kent `low_energy_price` al. Voor een opportunistische laadpaal is dat hetzelfde
advies met een ander onderwerp, en er is geen stopvoorwaarde nodig: de auto stopt zelf
wanneer hij vol is.

Eén verfijning is het overwegen waard maar hoort niet in deze ronde: een lader met
capability `set_current` kan meemoduleren, dus de regel "het overschot moet het apparaat
kunnen dragen" (§16) ligt voor hem anders dan voor een vaatwasser, die alleen aan of uit
kan. Dat is adviesvorming en geen datamodel, en het kan zonder migratie later.

### 34.10 Gevolgen elders

- **§8, Apparaten**: `target_soc_percent` en `vehicle_capacity_kwh` als type-specifieke
  velden bij `ev_charger`.
- **§33.4**: `target_soc_percent` wordt een bewonersveld en komt in
  `DEVICE_OPERATION_FIELDS`; `vehicle_capacity_kwh` blijft installateursgebied.
- **§16, datakwaliteit**: een extra voorwaarde binnen het bestaande apparaatitem, geen
  nieuw item en geen nieuwe weging. Een laadpaal zonder SOC-koppeling verandert niets.
- **§32.8**: de daar geparkeerde regel dat "energie per laadsessie" een schatting blijft
  en het advies op `medium` gecapt is, vervalt **alleen** voor een laadpaal die
  `kan_plannen`. Voor de rest blijft zij staan.
- **README**: de beperking uit §34.7 onder Limitations, en de twee velden bij de
  apparaattypes.

### 34.11 Wat deze ronde niet raakt

- **De aansturing.** Eigen release, eigen spec. Hier wordt gerekend en getoond.
- **Het voertuig als eigen object.** Zie §34.7; de grens is bewust getrokken.
- **Prijs- en zonneprognose.** Ongewijzigd buiten beeld (§32.8). De planning die hier
  ontstaat is "wanneer moet ik uiterlijk beginnen", niet "wanneer is het het goedkoopst".

### 34.12 Klaar wanneer

- een laadpaal zonder SOC-koppeling gedraagt zich exact als vandaag, en het paneel zegt
  in één zin dat hij opportunistisch laadt;
- een laadpaal mét SOC, capaciteit, doel-SOC, vermogen en deadline toont de afgeleide
  planning in het paneel, en de datakwaliteit meldt het ontbreken van capaciteit of
  doel-SOC bij zo'n paal;
- `required_duration_minutes` bestaat en wordt door het urgentie-advies gebruikt, ook al
  geeft zij in fase 2 nog gewoon `duration_minutes` terug;
- een bestaande configuratie laadt ongewijzigd door — beide velden zijn nullable, dus er
  is geen migratie.

## 35. De energiescore: benut / benutbaar

**Status: gebouwd tot en met §35.9; §35.4d, §35.8b en §35.9b zijn ontwerp en nog niet
gebouwd.** Deze sectie vervangt "Energiescore (0–100)" uit §16 in zijn geheel. Zij is bewust vóór de code geschreven, omdat de twee vorige herzieningen
juist daaraan zijn bezweken: er werd per ronde één component gerepareerd tegen een principe
dat nergens stond, en de ronde daarna vond het volgende component dat er niet aan voldeed.

- **0.1.3** — `solar_component` mat het overschot en heette zelfverbruik. Hij beloonde
  precies wat de coach afraadt.
- **0.1.2 en 0.1.5** — de voorwaardelijke weging, omdat een vast contract en een woning
  zonder apparaten permanent punten kwijt waren.

Beide reparaties waren juist. Geen van beide was af, want geen van beide kon zeggen wat de
score eigenlijk meet.

### 35.1 Het principe, en de twee regels die eruit volgen

> **benut / benutbaar, waarbij benutbaar volgt uit wat deze woning heeft.**

Een woning zonder stuurbare apparaten scoort hoger dan een woning die ze wél heeft maar
niet benut. De teller is wat er daadwerkelijk benut is; de noemer is wat er op dit moment,
in deze woning, te benutten viel. Beide kanten volgen uit de configuratie die de
installateur heeft vastgelegd en uit de meting van dit moment — nergens uit een aanname
over hoe een gemiddelde woning eruitziet.

Daaruit volgen twee regels. **Elke component die ooit aan deze score wordt toegevoegd moet
er langs, en elke component die er nu in zit is eraan getoetst** (§35.3 en §35.5).

#### Regel 1 — de wegvalregel

> **Een component valt weg wanneer de woning hem in deze situatie niet kan beïnvloeden —
> niet wanneer het signaal toevallig nul is.**

Het onderscheid zit in de vraag "kán hier iets aan veranderen", niet in de vraag "is de
waarde nu nul". Een woning die om drie uur 's nachts niets teruglevert heeft geen slechte
zonnebenutting; er valt niets te benutten. Een woning die om drie uur 's middags de helft
van haar opwek exporteert terwijl de vaatwasser leeg klaarstaat, heeft dat wél.

De regel stond er al impliciet en werd twee keer verkeerd toegepast — dat is de reden dat
hij hier woordelijk staat.

Hij heeft één gevolg dat expliciet besloten is (Sven, 2026-08-07): **de score levert
regelmatig geen getal op.** Dat is de bedoeling.

> Een tegel die zegt "op dit moment niets te meten" is eerlijker dan een cijfer dat iets
> beweert wat niet waar is.

Dat getal heeft nu al twee keer iets verkeerds beweerd, en dat kost meer dan een lege tegel.

#### Regel 2 — de adviesregel

> **Volgt de bewoner het advies van de coach op, dan mag de score daar niet door dalen —
> en negeert hij het, dan mag de score daar niet door stijgen.**

De coach en de score kijken naar dezelfde meting op hetzelfde moment. Wijzen ze
verschillende kanten op, dan is er per definitie één van de twee fout — en het is niet de
coach, want die is het product. Een component die zakt wanneer de bewoner doet wat er
gevraagd wordt, is geen strenge meting maar een verkeerde.

Dit is de scherpste van de twee regels, want hij is te falsificeren: neem elke adviesregel
die de coach kent, voer hem uit op de snapshot, en kijk of de score gelijk blijft of stijgt.
Zakt hij, dan hoort de component die zakte er niet in — hoe verdedigbaar zijn eigen
redenering ook is. Zo is `peak_component` eruit gegaan (§35.4b), en zo moet elke volgende
kandidaat beoordeeld worden.

**De tweede helft is er later bij gekomen, omdat de eerste helft alleen niet genoeg bleek**
(Sven, productie, 2026-08-09). Bij een negatieve zelfverbruikmarge raadt de coach aan te
wáchten met het overschot. Doet de bewoner dat, dan blijft `solar_component` staan waar hij
stond — hij dáált niet, dus de regel zoals zij eerst luidde was niet overtreden. De
overtreding zat in de spiegel: zet de bewoner de vaatwasser tóch aan, dan **stijgt** de
score. Een score die het negeren van het advies beloont is even fout als een score die het
opvolgen ervan afstraft, en alleen de tweede vorm stond er.

Beide helften worden per adviesregel getest, en dat is een andere toets dan de score als
geheel: de acceptatiecriteria in §35.13 eisen een test **per adviesregel**, in beide
richtingen.

### 35.2 Wat de score níét is

Dit onderscheid is onderweg drie keer bijgesteld, en staat daarom hier vast voordat iemand
het opnieuw verkeerd leest.

| De score is niet | Waarom niet, en waar het wél staat |
|---|---|
| **een zuinigheidsmeter** | Hij zegt nooit "gebruik minder". De oven om 18:00 aanzetten is geen fout; eten koken op het duurste moment van de dag is wat een oven doet. De score gaat over het *moment* waarop verplaatsbaar verbruik valt, niet over de hoeveelheid. |
| **een oordeel over de installatie** | Hoe compleet de installateur heeft ingevuld is de **datakwaliteit**, die als eigen percentage naast de score staat. Dat is administratie van DomotiTech, geen prestatie van de bewoner. |
| **een oordeel over wat de woning bezit** | Geen panelen, geen slimme apparaten, een vast contract: het zijn keuzes, geen tekortkomingen. Ze verlagen de score niet — ze verkleinen wat er te meten valt. |
| **een rapportcijfer over de woning** | Het is een meting van dít moment. Het paneel zegt "op dit moment", niet "van 100". |
| **een maat voor aansturing** | De score meet mogelijkheid, niet controle. Of de integratie iets aanstuurt hoort er niet in; dat is de aansturingsrelease en die verandert hier niets aan. |

### 35.3 De audit: vier van de vijf voldoen niet

**Dit is een herontwerp en geen bijstelling.** Van de vijf componenten die vandaag draaien
voldoet er één aan het principe.

| Component | Gewicht | Meet feitelijk | Volgt het principe |
|---|---|---|---|
| `data_quality_component` | 0,30 | hoe compleet de installateur invulde | nee |
| `peak_component` | 0,25 | absolute belasting t.o.v. de aansluiting | nee |
| `solar_component` | 0,20 | zelfverbruik / opwek | **ja** |
| `price_component` | 0,15 | of de markt nu goedkoop is | nee |
| `flexibility_component` | 0,10 | of er één compleet flexibel apparaat bestáát | nee |

Vier van de vijf meten een eigenschap van de woning of van het weer, en niet iets wat de
bewoner op dit moment beïnvloedt. Samen dragen ze 0,80 van het gewicht.

### 35.4 De vier schuurgevallen

Alle vier zijn ze in de praktijk gevonden, niet bedacht.

#### (a) Panelen zonder verplaatsbare last

Een woning met panelen, zonder batterij en zonder één compleet flexibel apparaat, kan haar
zelfverbruik niet verhogen op het moment dat de zon schijnt. 100% zelfverbruik is voor die
woning fysiek onbereikbaar. De as is dan een korting en geen meting, en dat is in strijd
met regel 1.

**Voorstel: `solar_component` geldt alleen wanneer er iets te verplaatsen ís** — minimaal
één bruikbaar, flexibel én compleet apparaat, of een thuisbatterij.

Het bijeffect is precies wat er gewenst is: een batterij toevoegen zet de component áán.
Het plafond en de lat gaan tegelijk omhoog, wat de eerlijke beschrijving is van wat een
batterij met een woning doet.

#### (b) Het opvolgen van het advies verlaagt de score

**Het ernstigste geval, en de aanleiding voor regel 2.** Concreet, op een 1×25 A-aansluiting
(5750 W):

```text
prijs laag, coach zegt "laad nu de auto"
vóór:   400 W  →  7% belasting  →  peak_component 100
ná:    4100 W  → 71% belasting  →  peak_component  57
```

Dat kost 10 tot 16 punten in dezelfde minuut waarin de coach het aanraadt.

De oorzaak is dat `peak_component` een hoofdruimtemaat is met een knik op een vaste 50%.
Daardoor scoort een grotere aansluiting beter bij identiek gedrag, en daardoor kost normaal
gebruik punten op een kleine aansluiting.

**Voorstel: `peak_component` verdwijnt uit de score.** Dat is meer dan eerder voorgesteld —
daar stond het ankeren van de helling op `peak_warning_percent`, zodat de aftrek pas begint
waar de installateur heeft vastgelegd dat het in dít huis een probleem wordt. Drie redenen
waarom dat niet ver genoeg gaat:

1. **Het lost (b) niet op, het verkleint het.** Op een kleine aansluiting kan een
   werkelijk geadviseerde laadsessie nog steeds over `peak_warning_percent` komen. Dan
   daalt de score nog altijd op het moment dat de bewoner doet wat er gevraagd wordt, en
   dat is precies wat regel 2 verbiedt.
2. **Onder de drempel is er niets te verbeteren.** De component staat dan op 100 en geen
   enkele handeling verandert dat. Dat is dezelfde vorm als de permanente 50 van het vaste
   contract, alleen aan de andere kant van de as — een component die niemand kan bewegen.
   Zie de toets in §35.5.
3. **Het is dubbeltelling.** Het piekrisico heeft al een eigen binaire sensor, een eigen
   waarschuwing en een eigen adviesregel (§16). Het hoeft niet óók nog in het cijfer van de
   bewoner te zitten om gezien te worden.

Het piekrisico verdwijnt dus niet uit het product — `peak_risk`, de waarschuwing, de
hysterese en de twee reason codes blijven ongewijzigd. Alleen het cijfer laat het los.

#### (c) De prijscomponent meet het weer

Elke dynamische woning scoort om 18:00 nul en om 03:00 honderd, ongeacht gedrag. Twee
identieke huizen, één slapend en één met de droger aan, scoren op dat moment gelijk. De
component meet de markt, niet de bewoner.

**Voorstel**, zonder enige prognose en volledig uit de bestaande snapshot:

```text
prijspositie = clamp((prijs − laag) / (hoog − laag), 0, 1)
importdeel   = clamp(max(netvermogen, 0) / max_grid_power_w, 0, 1)
component    = 100 × (1 − prijspositie × importdeel)
```

Nu meet hij wat de woning doet op het moment dat het duur is. De slapende woning scoort
hoog, de woning met de droger aan laag, en teruglevering bij een hoge prijs telt als volle
benutting — want dat is het ook.

**De component geldt niet wanneer de prijs op of onder de lage drempel staat.** Dan is
`prijspositie` nul en is er niets te vermijden; de component zou 100 zijn zonder dat iemand
iets kan doen, en dat is regel 1. Op de drempel zelf is hij precies 100, dus het in- en
uitstappen gaat zonder sprong in de component.

**De as is bewust asymmetrisch.** Duur verbruik vermijden is gedrag; goedkoop verbruik
opzoeken is dat alleen wanneer je iets te draaien hád. Een woning die om 03:00 slaapt
straffen omdat zij goedkope stroom niet benut, zou de score laten eisen dat er een droger
aangaat. Daarom meet deze as alleen de vermijdkant.

#### (d) Terugleveren levert meer op dan zelf verbruiken

**Gevonden op productie (Sven, 2026-08-09), en de aanleiding voor de tweede helft van
regel 2.** Een zonnige ochtend: 4.654 W opwek, 1.635 W thuisverbruik, dus 3.019 W terug
naar het net. `solar_component` zou 35 zijn. Alleen ligt de terugleververgoeding op dat
moment hóger dan de importprijs, dus elke kWh die deze woning zelf verbruikt kost haar
geld. 35% is dan geen matige benutting maar een neutraal feit, en de handeling die het
getal verhoogt is precies de handeling die de bewoner geld kost.

De coach weet dit al en zegt het ook — *"Wachten tot de terugleververgoeding lager ligt is
voordeliger"* — maar de score doet er niets mee.

##### De marge, en waarom hij naar de woning verhuist

De grootheid die dit beslist staat al in de motor, verstopt in de besparingssom van de
advisor (§16):

```text
besparing = energie_per_cyclus × (importprijs − effectieve terugleververgoeding + terugleverkosten)
```

De haakjes zijn **apparaatonafhankelijk**; het apparaat levert alleen de schaal. Dat is de
**zelfverbruikmarge** in EUR/kWh, en zij hoort in `EnergyMetrics` te staan met de
besparingssom als vermenigvuldiging erbovenop — dezelfde afspraak als bij
`has_movable_load` en §34.4, zodat score, tegel en advies niet uiteen kunnen lopen.

Dat zij nu in de advisor zit, is niet alleen onnetjes maar aantoonbaar schadelijk: de zin
over wachten hangt aan een apparaat met een energie per cyclus. Precies de woning uit dit
voorbeeld heeft er geen — dat is de reden dat `solar_component` daar al wegvalt op
`has_movable_load` — dus **de coach kent de situatie alleen in de tak die deze klant niet
krijgt.**

##### Wegvallen, niet omdraaien

**Voorstel: `solar_component` geldt niet wanneer de zelfverbruikmarge aantoonbaar negatief
is.** Geen straf, geen omkering: niet van toepassing, net als bij nacht of bij niets
verplaatsbaars.

De verleiding is om de as om te draaien zodra terugleveren loont. Drie redenen om dat niet
te doen:

1. **De betekenis van "hoog" kantelt dan op iets dat niet in het getal zit.** Zelfde tegel,
   zelfde label, zelfde 0–100, en 70 's ochtends zou tegengesteld gedrag beschrijven aan 70
   's middags. Dat is erger dan geen getal — het is de vorm van fout waar §35.1 tegen
   geschreven is.
2. **Regel 1: wat kan de bewoner doen om de omgekeerde as te verhogen? Minder verbruiken.**
   De as meet zelfbenutting van *al* het verbruik, niet alleen van het verplaatsbare deel;
   de oven telt mee en die is niet te verplaatsen. Omgedraaid wordt hij letterlijk de
   zuinigheidsmeter die §35.2 drie herzieningen lang geweigerd heeft.
3. **Er valt op dat moment niets naartoe te verplaatsen.** Het advies is wachten. Een as
   waarvan de aanbevolen handeling "niets doen" is, is geen benuttingsas.

##### De grens, en wat er bij een onbekende marge gebeurt

| Marge | `solar_component` | Waarom |
|---|---|---|
| positief | geldt | zelf verbruiken levert geld op; de as wijst dezelfde kant op als het advies |
| **nul** | **geldt** | saldering met terugleverkosten 0. De coach adviseert daar nog steeds zelf verbruiken (*"blijft de meest efficiënte keuze"*), dus score en advies blijven het eens. Besluit Sven, 2026-08-09 |
| negatief | vervalt | terugleveren levert meer op; de as zou het negeren van het advies belonen |
| onbekend | geldt | zie hieronder |

**De as vervalt alleen wanneer de marge aantoonbaar negatief is.** Een onbekende marge laat
hem staan zoals vandaag. Dat is geen gok over het onbekende maar een regel over het
bewezene, en het voorkomt dat een leeg veld van de installateur het cijfer van de bewoner
wegneemt — precies wat §35.7 opruimde.

**Als beperking te noemen, want zij is echt:** een woning waarvan de terugleververgoeding
of de terugleverkosten niet ingevuld zijn, kan op een negatieve marge draaien zonder dat de
score het merkt. Het gat is kleiner dan het lijkt — onder saldering is de marge gelijk aan
de terugleverkosten en dus nooit negatief, zodat het geval alleen kan optreden bij een
woning zonder saldering, en juist daar zijn de velden ingevuld die de coach toch al nodig
heeft — maar het is er.

##### Bijvangst: de exportwaarschuwing verkoopt een voordeel dat er niet is

`high_grid_export` zegt *"Schakel indien mogelijk juist extra verbruikers in om het
overschot zelf te benutten."* Het argument eronder is de zekering en dat blijft kloppen,
maar de tweede helft van de zin belooft voordeel. Bij een negatieve marge is dat onwaar.
De zin hoort in dezelfde ronde te worden gesplitst in het capaciteitsargument, dat altijd
geldt, en het voordeelargument, dat aan de marge hangt.

### 35.5 De toets: wat kan de bewoner concreet doen?

Dit is regel 1 en regel 2 samen, in de vorm van één vraag per component:

> **Is er geen concreet antwoord op "wat kan de bewoner nú doen om deze component te
> verhogen", dan hoort de component niet in de score.**

| Component | Wat de bewoner concreet kan doen | Blijft |
|---|---|---|
| `solar_component` | De vaatwasser of de wasmachine nu aanzetten, de auto nu laden, de batterij laten laden. Elke kWh die nu zelf gebruikt wordt in plaats van teruggeleverd, verhoogt hem direct. | **ja** |
| `price_component` | Wachten met de droger tot de prijs zakt; nu minder van het net afnemen. Zichtbaar binnen één update. | **ja** |
| `peak_component` | Boven de drempel: iets zwaars uitzetten. Daaronder — dus vrijwel altijd — niets; hij staat op 100 en beweegt niet. En boven de drempel botst hij met regel 2. | nee, §35.4(b) |
| `flexibility_component` | Niets. Hij meet of er een compleet apparaatprofiel bestáát, en dat profiel invullen is het werk van de installateur. Voor de bewoner is het een vast getal. | nee, §35.6 |
| `data_quality_component` | Niets. Het is per definitie de administratie van DomotiTech. | nee, wordt poort (§35.7) |

De twee componenten die overblijven zijn precies de twee waarop de coach ook daadwerkelijk
advies geeft. Dat is geen toeval maar het gevolg van regel 2: een score die met het advies
meebeweegt, kan alleen bestaan uit assen waarover advies gegeven wordt.

### 35.6 `flexibility_component` vervalt

Twee onafhankelijke redenen, elk voldoende:

- **Hij meet bestaan in plaats van gebruik.** Of er één compleet flexibel apparaat is,
  verandert niet door iets wat de bewoner vandaag doet.
- **Hij telt dubbel.** Hij gebruikt hetzelfde predicaat als een checklistitem van 15 punten
  in de datakwaliteit, dus een complete vaatwasser levert twee keer punten op.

Wat hij wilde uitdrukken — "deze woning kan iets verplaatsen" — komt terug op de plek waar
het thuishoort: als voorwaarde van `solar_component` (§35.4a). Daar is het geen punt maar
een poortje, en dat is wat het altijd was.

### 35.7 `data_quality` wordt een poort, geen term

De datakwaliteit blijft bestaan, blijft berekend worden en blijft als eigen percentage in
het paneel staan. Zij weegt alleen niet meer mee in de energiescore.

**De poort is geen percentage maar een voorwaarde**, zodat er geen drempelgetal verzonnen
hoeft te worden:

> De energiescore is `None` zolang niet alle drie de **onvoorwaardelijke** checklistitems
> compleet zijn: de verplichte woninggegevens, minimaal één bruikbare netbron, en
> prijsinformatie.

Dat zijn exact de drie items waarvan §16 al zegt dat de integratie zonder hen niets meet.
Het paneel noemt in dat geval welke van de drie ontbreekt, in plaats van een cijfer te
tonen.

Dit bewaart de garantie waarvoor `data_quality_component` in de score zat — **een verse
installatie kan geen 100 halen** — en wel op de enige manier die klopt: zij haalt niets.
Tegelijk verdwijnt de installateursadministratie uit het cijfer van de bewoner, waar zij
bovendien al als eigen percentage naast stond.

### 35.8 De nieuwe samenstelling

```text
poort:  de drie onvoorwaardelijke checklistitems compleet   → anders None
```

| Component | Gewicht | Geldt wanneer |
|---|---|---|
| `solar_component` | 0,50 | er is opwek op dit moment, het netvermogen is leesbaar, de woning heeft iets te verplaatsen, én de zelfverbruikmarge is niet aantoonbaar negatief (§35.4d) |
| `price_component` | 0,50 | dynamisch contract, prijs en beide drempels bekend, `max_grid_power_w` bekend, én de prijs staat boven de lage drempel |

De rekenregel blijft ongewijzigd — het aandeel van wat van toepassing is:

```text
energiescore = round(100 × Σ(gewicht × component) / Σ(gewicht))   over de geldende componenten
             = None                                              wanneer geen component geldt
```

**Waarom gelijke gewichten.** Er is geen grond om ze te splitsen: beide beantwoorden
dezelfde vraag over hetzelfde moment, namelijk of verplaatsbaar verbruik op het juiste
moment viel. Bovendien doet de verhouding er alleen toe wanneer beide gelden — zon én een
hoge prijs — en juist dan wijzen ze dezelfde kant op, want het overschot zelf gebruiken is
niet importeren. Een verzonnen verhouding zou hier niets toevoegen behalve een getal dat
niemand kan verantwoorden.

**Een ontbrekende invoer geeft geen 0 meer, maar laat de component wegvallen.** Dit
draait de bestaande regel uit §16 om ("onbekend blijft wél 0: het signaal bestaat en is
niet geconfigureerd"), en dat is opzet. Onder het nieuwe principe is een niet
geconfigureerd signaal het werk van de installateur, en de bewoner kan er niets aan doen —
dus is het een aftrek van precies het soort dat deze herziening opruimt. Het ontbreken
wordt gemeld waar het thuishoort: in de datakwaliteit, en bij de drie onvoorwaardelijke
items in de poort.

`not_applicable_components[]` blijft bestaan en blijft door het paneel genoemd worden. Een
score uit één component in plaats van twee ziet er anders uit alsof er iets is overgeslagen.

### 35.8b De meting en het oordeel zijn twee dingen

**Toegevoegd 2026-08-09, en het herstelt een fout die vanaf het begin in dit ontwerp zat.**

`solar_component` is tegelijk een *meting* — welk deel van de opwek deze woning zelf
gebruikt — en een *oordeel*, want hij gaat als cijfer de score in waar hoog goed is. Zolang
die twee samenvallen valt dat niet op. Zodra ze uiteenlopen gooit het ontwerp de meting weg
omdat het oordeel oneerlijk zou zijn:

> 4.654 W opwek, 1.635 W zelf gebruikt. De woning heeft niets verplaatsbaars, dus de as
> vervalt, dus er staat geen cijfer — terwijl 35% een waar, bewegend en begrijpelijk getal
> is dat de bewoner precies vertelt wat zijn panelen op dat moment doen.

Het oordeel hoorde weg te vallen. De meting niet. Daarom scheidt deze subsectie ze:

| | De meting | Het oordeel |
|---|---|---|
| Wat het is | zelfbenutting, thuisverbruik, prijs, netvermogen | de energiescore |
| Wanneer het er is | zodra de invoer leesbaar is | alleen wanneer er iets te benutten valt |
| Waar het staat | als regel in `Actuele situatie` | in de scoretegel |
| Richting | geen. Een meting is geen doel | hoog is goed, en dat moet waar zijn |

**Zelfbenutting wordt daarom een gewone meetregel**, zichtbaar zodra er opwek én een
leesbaar netvermogen is — ongeacht de poort, ongeacht verplaatsbare last, ongeacht de
marge. Dat is dezelfde waarde die `solar_component` gebruikt wanneer hij geldt, dus één
berekening met twee lezers en geen kans op twee getallen die verschillen.

**De naam is hier geen detail.** Twee ware breuken over dezelfde minuut geven een
tegengestelde indruk:

| | Formule | Het voorbeeld hierboven |
|---|---|---|
| **Zelfbenutting** (dit getal, en de score-as) | zelf gebruikt / opwek | 1.635 / 4.654 = **35%** |
| **Zelfvoorziening** | zelf opgewekt / eigen verbruik | 1.635 / 1.635 = **100%** |

Op dat moment draait de woning volledig op zon. Een tegel die 35% "zelfvoorziening" noemt
liegt zonder één verkeerd cijfer — dezelfde faalmodus als de zinnen in §35.9, maar dan in
het label. Het getal heet **zelfbenutting**, overal.

**Een niet-score-getal komt nooit op de plek van de score.** Voor de bewoner is het getal
dat in de scoretegel staat de score, welk label er ook boven hangt. De meting hoort tussen
de meterstanden, waar zij niet als rapportcijfer te lezen is.

**Dat is ook het antwoord op "de tegel mag niet leeg zijn".** Dat is een indelingsvraag en
geen scorevraag. Er is altijd een getal op het scherm — 's nachts bij een vast contract
zonder panelen is dat het thuisverbruik (§36) — en het **kopgetal van het Overzicht wordt
het thuisverbruik in plaats van de energiescore** (besluit Sven, 2026-08-09; §36.5 noemde
het al als kandidaat voor de visuele ronde). De eerste en grootste plek op het scherm is
dan nooit leeg, en een afwezige score is een regel eronder in plaats van een gat bovenaan.

**Waarom de score zelf géén altijd-getal wordt.** benut/benutbaar is een breuk en
*benutbaar* is soms werkelijk nul. Alle drie de manieren om die nul te omzeilen kosten meer
dan een afwezige score:

1. **de noemer een bodem geven** — een verzonnen "wat je had kunnen verplaatsen" bij een
   woning die niets te verplaatsen heeft. Dat is de aanname over een gemiddelde woning die
   §35.1 in zijn eerste alinea verbiedt;
2. **leegte als 100 lezen** — dan scoort elke woning 's nachts 100, wordt de zaagtand van
   §35.10 groter in plaats van kleiner, en beweert het cijfer een prestatie op een moment
   waarop er geen gedrag was;
3. **de laatst bekende waarde vasthouden** — dat is de score over een venster, en dus de
   historie-ronde (§35.10). Legitiem, maar het vraagt opslag van een reeks en een eigen
   ontwerp; halverwege inbouwen is de losse reparatie waar §35 tegen geschreven is.

### 35.9 Wanneer een woning een cijfer krijgt, en wat daarvoor nodig is

Uit §35.8 volgt dat een deel van de klanten **nooit** een cijfer ziet. Dat is de keuze van
§35.1 concreet gemaakt en het is geaccepteerd (Sven, 2026-08-08): liever geen getal dan een
getal dat iets beweert wat niet waar is. Sinds §35.8b betekent dat niet langer een scherm
zonder getallen: de metingen staan er, alleen het oordeel ontbreekt.

Deze subsectie legt vast wat een woning nodig heeft om wél een cijfer te krijgen, zodat de
installateur die vraag aan de keukentafel kan beantwoorden zonder te gokken.

| Wat de woning heeft | Welke as gaat aan | Vanaf wanneer er een cijfer staat |
|---|---|---|
| Dynamisch contract | `price_component` | zodra de prijs boven de lage drempel staat — in de praktijk een groot deel van de dag |
| Panelen **en** ≥1 bruikbaar, flexibel, compleet apparaat | `solar_component` | zodra er opwek is |
| Panelen **en** een thuisbatterij | `solar_component` | zodra er opwek is |
| Panelen zonder verplaatsbare last | geen | nooit, tot er iets verplaatsbaars bijkomt |
| Panelen, maar terugleveren loont meer (§35.4d) | `solar_component` staat uit | zolang de marge negatief is niet uit de zon; wel uit de prijs, wanneer die as geldt |
| Vast contract, geen panelen | geen | nooit |

**De goedkoopste route naar een cijfer is bijna nooit iets kopen**, en dat hoort in dit
gesprek genoemd te worden:

1. **Een dynamisch contract** zet de prijsas aan zonder één apparaat in huis te veranderen.
2. **Een bestaand apparaat compleet maken** — vermogen en energie per cyclus invullen en
   als flexibel markeren — zet bij een woning met panelen de zonneas aan. Dat is
   configuratiewerk van de installateur, geen aanschaf.
3. **Pas daarna** komt hardware in beeld, en dan om wat het doet, niet om wat het met het
   cijfer doet.

**Hoe dit wél en niet gezegd wordt.** Niet: *"je score is laag, koop een batterij."* Die
zin is onwaar in beide helften — de score is niet laag, hij is er niet, en een batterij
verhoogt hem niet automatisch maar zet alleen de as aan waarop de woning dan beoordeeld
wordt. Wel:

> *"Deze woning heeft op dit moment geen wisselend signaal om verbruik naar toe te
> verplaatsen. Er valt dus niets te optimaliseren, en daarom staat er geen cijfer. Het
> advies blijft gewoon werken."*

**De coach blijft in alle gevallen doorwerken.** Een woning zonder cijfer krijgt nog steeds
adviezen — het piekrisico, de teruglevering, de vaatwasser op het juiste moment — alleen
zonder getal ernaast. De score is een extra, geen voorwaarde.

**De paneeltekst zegt waaróm, niet alleen dát.** Een tegel met een streepje leest als een
storing; een tegel met een reden leest als een antwoord. Per geval, in het paneel:

| Situatie | Code | Wat de tegel zegt |
|---|---|---|
| Poort dicht (§35.7) | `incomplete_setup` | *Er is nog geen cijfer, omdat de installatie nog niet compleet is. Het tabblad Energiecoach laat zien wat er ontbreekt.* |
| Dynamisch, drempels niet ingevuld | `price_thresholds_missing` | *Zolang de lage en de hoge prijsdrempel niet zijn ingevuld, is niet te bepalen of dit een duur moment is. Vul ze in bij Installatie.* |
| Vast tarief, geen panelen | `no_variable_signal` | *Het tarief is altijd gelijk en er zijn geen zonnepanelen, dus er is geen moment dat beter is dan een ander. Er valt daarom niets te optimaliseren. Het advies blijft gewoon werken.* |
| Er ís opwek, terugleveren loont meer (§35.4d) | `feed_in_pays_better` | *Je panelen leveren op dit moment, maar terugleveren levert je meer op dan de stroom je kost. Zelf verbruiken zou je nu geld kosten, dus er valt aan je opwek niets te benutten. De coach zegt hetzelfde: wachten is voordeliger.* |
| Er ís opwek, niets verplaatsbaars | `nothing_movable` | *Er is nu opwek, maar geen apparaat of batterij die verbruik kan verplaatsen. Er valt daarom niets te benutten dat nu niet al gebeurt.* |
| Panelen stil, dynamisch, prijs laag | `no_sun_cheap_price` | *Je panelen leveren op dit moment niets en de stroomprijs is laag. Er is nu dus geen overschot om te benutten en geen duur verbruik om te vermijden.* |
| Panelen stil, vast tarief | `no_sun_fixed_tariff` | *Je panelen leveren op dit moment niets, en bij een vast tarief is het ene moment niet beter dan het andere. Er is nu dus niets te verbeteren.* |
| Geen panelen, dynamisch, prijs laag | `cheap_price` | *De stroomprijs is op dit moment laag, dus er is geen duur verbruik om te vermijden.* |

**Twee van de acht zijn een tekortkoming** — de gesloten poort en de ontbrekende
drempels — en die twee dragen een waarschuwingstoon. De andere zes beschrijven een
woning die niets fout doet: geen waarschuwingskleur, geen uitroepteken. `feed_in_pays_better`
hoort nadrukkelijk bij die zes — daar verdient de bewoner geld, en een waarschuwingskleur
zou daar een probleem van maken. Deze teksten staan in de frontendbestanden, niet in
`translations/` (§26).

**Wanneer twee redenen tegelijk waar zijn, wint de reden die blijft staan als de andere
wordt opgelost.** Daarom staat `feed_in_pays_better` vóór `nothing_movable`: een woning met
opwek, niets verplaatsbaars én een negatieve marge heeft niets aan de zin over een apparaat
dat ze mist, want ook mét dat apparaat zou zij het nu niet moeten aanzetten. De woning uit
§35.4d is precies dat geval.

**Elke variant is als geheel geschreven en wordt door een situatie gekozen** (besluit
0.4.2). De verleiding is om er één zin van te maken die zijn helften aan- en uitzet, maar
dan bestaat de zin die de klant leest nergens in de broncode en kan niemand hem nalezen.
Acht hele zinnen zijn te lezen, te herschrijven en op te nemen in de zinneninventaris;
een sjabloon met gaten is dat niet.

**De voorwaarde moet toetsen wat de zin beweert.** Dat ging mis in 0.4.1: `nothing_movable`
werd gekozen op het bestáán van een zonnerij terwijl zijn zin "er is nu opwek" zegt, dus
een woning kreeg 's avonds te horen dat haar panelen leverden. De selector krijgt daarom de
snapshot en gebruikt dezelfde `_production_now` als `solar_component`. Configuratie
beantwoordt "wat heeft deze woning", alleen een meting beantwoordt "wat doet zij nu" — regel
1 van §35.1, toegepast op de teksten in plaats van op de componenten.

### 35.9b Ook mét een cijfer hoort de tegel te zeggen wat er niet meetelt

De zinnen uit §35.9 verschijnen **alleen wanneer er géén cijfer is**. Dat was houdbaar
zolang een wegvallende component betekende dat er niets te melden viel, en §35.4d haalt dat
onderuit: een dynamische woning in de zon met een negatieve marge krijgt een score uit
alleen de prijs-as. De bewoner leest 88 en er staat nergens dat zijn zonneoverschot buiten
beschouwing bleef, laat staan waarom.

`not_applicable_components[]` bestaat al voor precies dit doel — §35.8 zegt dat het paneel
ze noemt — maar **de frontend leest het veld nergens.** Het wordt berekend, meegestuurd en
weggegooid; hetzelfde patroon als de velden uit §37.2, nu tussen backend en paneel in
plaats van tussen formulier en motor.

Daarom: **een reden per component, niet één reden per tegel.** Naast het cijfer staat per
niet-geldende as dezelfde zin die hij zou hebben gehad als hij de enige was. Bijvoorbeeld:

> **88** — Je vermijdt duur verbruik goed. Je zonneoverschot telt nu niet mee: terugleveren
> levert je meer op dan het zelf gebruiken.

Dat is een cijfer mét uitleg, en de uitleg zegt niet dat de bewoner het slecht doet. De
bestaande tegelzin blijft wat hij is voor het geval dat er helemaal geen cijfer is; deze
komt ernaast, niet in de plaats.

### 35.10 Bekende beperking: de zaagtand

Een momentmeting waarvan componenten in en uit stappen, springt. Onder het huidige ontwerp
gaat dezelfde woning van 72 overdag naar 91 's nachts zonder dat iemand iets doet —
negentien punten heen en terug per dag — omdat een component laten wegvallen de score naar
het gemiddelde van de rest trekt.

Het herontwerp maakt dit **kleiner maar niet weg**, en verandert wel de aard ervan:

- De nachtsprong verdwijnt als sprong. Vallen beide componenten weg, dan komt er geen ander
  getal maar géén getal. Dat is de eerlijke vorm.
- De resterende sprong zit tussen twee momenten waarop verschillende componenten gelden.
  Concreet, een dynamische woning met panelen en een vaatwasser: 's middags `solar` 30 en
  `price` niet van toepassing → 30; 's avonds `solar` weg en `price` 90 → 90. Zestig punten
  verschil op één dag, zonder dat de bewoner iets fout deed.

**De echte oplossing is een score over een venster in plaats van over een moment**, en dat
is de historie-ronde (bevinding 14, ronde D). Hier benoemd en geparkeerd, niet half
opgelost: het venster vraagt om opslag van een reeks en om een eigen ontwerp, en het
halverwege inbouwen zou precies het soort losse reparatie zijn waar deze sectie tegen
geschreven is.

### 35.11 Gevolgen elders

- **§16, "Energiescore (0–100)"** — vervangen door deze sectie. De gewichtentabel met vijf
  componenten vervalt.
- **`const.py`** — `SCORE_COMPONENT_DATA_QUALITY`, `SCORE_COMPONENT_PEAK`,
  `SCORE_COMPONENT_FLEXIBILITY` en `PEAK_COMPONENT_FULL_BELOW_PERCENT` vervallen;
  `SCORE_COMPONENT_WEIGHTS` houdt twee sleutels.
- **`engine/completeness.py`** — een nieuw predicaat `has_movable_load(config)`, naast
  `is_complete_device_profile` en de gereed-vensterpredicaten, zodat de score, de checklist
  en het paneel niet uit elkaar kunnen lopen. Dezelfde afspraak als §34.4.
- **`engine/calculator.py`** — `_peak_component` en `_flexibility_component` verdwijnen;
  `_grid_load_percent` en `_peak_risk` blijven ongewijzigd, want de waarschuwing blijft.
- **`EnergyMetrics`** — twee velden erbij: `self_consumption_margin_eur_kwh` (§35.4d) en
  `self_consumption_percent` (§35.8b), allebei `None` wanneer de invoer ontbreekt. Beide
  hebben een lezer vóórdat ze bestaan: de eerste de score en de advisor, de tweede het
  paneel. Zie de audit in §37.2 voor waarom die volgorde vaststaat.
- **`engine/advisor.py`** — `_solar_savings` wordt `energie × marge` en rekent de marge niet
  langer zelf uit; de zin van `high_grid_export` splitst het capaciteitsargument van het
  voordeelargument (§35.4d).
- **De sensor `energy_score`** — wordt vaker `unknown`. Dat is zichtbaar in de
  langetermijnstatistieken als een gat in de reeks, en dat hoort in de README onder
  Limitations: een gemiddelde over een dag is voor deze sensor niet zinvol.
- **Het paneel** — de tegel krijgt de teksten uit §35.9, noemt welke componenten niet van
  toepassing zijn en waarom (§35.9b), en toont bij een gesloten poort welk onvoorwaardelijk
  item ontbreekt. `Actuele situatie` krijgt de regel **Zelfbenutting** (§35.8b), en het
  thuisverbruik wordt het kopgetal van het Overzicht in plaats van de score.
- **README** — de beschrijving van de score, de tabel uit §35.9 zodat een installateur haar
  bij de hand heeft, en de drie beperkingen uit §35.4d, §35.9 en §35.10.

### 35.12 Wat deze ronde niet raakt

- **De datakwaliteit zelf.** Zelfde items, zelfde gewichten, zelfde berekening. Alleen haar
  rol in de energiescore verandert.
- **Het piekrisico.** `peak_risk`, de hysterese, de waarschuwing en de twee reason codes
  blijven exact zoals ze zijn.
- **De adviesregels.** De coach verandert niet. Deze sectie maakt de score consistent met
  het advies, niet andersom.
- **Prognose.** Alles komt uit de bestaande snapshot van dit moment.

### 35.13 Klaar wanneer

- geen enkele configuratiehandeling van de installateur verhoogt of verlaagt de
  energiescore, en een test bewijst dat voor de datakwaliteit en voor het toevoegen van een
  apparaat;
- **regel 2 is per adviesregel in beide richtingen getest**: het opvolgen van elk advies dat
  de coach kan geven verhoogt de score of laat hem gelijk — nooit lager — én het negeren
  ervan verlaagt de score of laat hem gelijk, nooit hoger;
- een woning met panelen zonder verplaatsbare last krijgt geen `solar_component`, en het
  toevoegen van een batterij zet hem aan;
- een dynamische woning bij een lage prijs krijgt geen `price_component`; bij een hoge
  prijs zakt hij zichtbaar wanneer het importvermogen stijgt;
- **een negatieve zelfverbruikmarge zet `solar_component` uit en een positieve zet hem aan**;
  bij een marge van precies nul geldt hij, en bij een onbekende marge ook (§35.4d). Getoetst
  als tabel van situaties met de verwachte uitkomst ernaast, niet als vier losse takken;
- **de zelfverbruikmarge komt uit `EnergyMetrics` en wordt door de coordinator gevuld**, niet
  alleen door `Calculator.calculate()`; het aanroeppad is teruggelopen tot de coordinator
  (CLAUDE.md, zevende variant);
- **zelfbenutting staat op `Actuele situatie` zodra er opwek en een leesbaar netvermogen is**,
  óók wanneer er geen score is, en het getal is exact dat van `solar_component` wanneer die
  geldt;
- een woning die één van de drie onvoorwaardelijke items mist, krijgt `None` en het paneel
  noemt welk item;
- elk van de acht gevallen uit de tabel in §35.9 levert de bijbehorende zin op, en niet een
  streepje. Getoetst vanuit de situatie — één rij per situatie met de verwachte zin ernaast —
  en niet door per zin een toestand te zoeken die hem oplevert;
- **de browsercontrole vertrekt van de situatie, niet van de tak**: de avondtegel wordt
  bekeken met de panelen werkelijk stil en de negatieve-margetegel met een
  terugleververgoeding die werkelijk boven de importprijs ligt (CLAUDE.md, zesde variant);
- de zaagtand is niet opgelost en staat als beperking in de README, net als de onbekende
  marge uit §35.4d.

## 36. Thuisverbruik: het getal dat er als eerste hoort te staan

**Status: gebouwd.** Bevinding 3 uit de eerste productie-installatie.

### 36.1 Waarom dit ontbreekt en waarom dat opvalt

Het Overzicht toont het **netvermogen**, en dat is een saldo — geen verbruik. Een woning
met panelen die om 13:00 "−2.400 W" ziet staan, leest daar niet in dat haar huis op dat
moment 600 W trekt. Er staat geen enkel getal op het scherm dat de vraag "wat gebruikt
mijn huis nu" beantwoordt.

Dat is niet één ontbrekend getal tussen andere. Het is het getal waar de rest aan
opgehangen wordt: zonder thuisverbruik is "benut je zonneoverschot" een advies waarvan
de bewoner de aanleiding niet ziet.

**Wat er al bestaat en waarom het niet volstaat.** `household_consumption_w` staat al in
`EnergySnapshot`, maar alleen als *gemeten* waarde uit een `general_consumption`-bron, en
hij haalt `EnergyMetrics` niet — het paneel ziet hem dus nooit. Hij wordt op precies één
plek gebruikt: als invoer voor variant 2 van het zonneoverschot (§16). Vrijwel geen
woning heeft zo'n bron; wél heeft vrijwel elke woning een netmeter en een omvormer, en
daaruit is het verbruik af te leiden.

### 36.2 De energiebalans

```text
thuisverbruik = netvermogen + zonneproductie − batterijvermogen
```

met de conventies die er al staan (§16): netvermogen positief = import, batterijvermogen
positief = laden. Een ladende batterij is een verbruiker die geen huishoudelijke last is,
dus hij gaat eraf; een ontladende batterij levert vermogen aan het huis en telt er via
zijn negatieve waarde bij op.

Bij de meest voorkomende installatie — P1-meter en omvormer, geen batterij — is dat
`netvermogen + zonneproductie`, en verder niets.

**De uitkomst wordt geklemd op nul.** Negatief thuisverbruik bestaat niet. Meetruis en
twee sensoren die niet op dezelfde seconde bemonsteren kunnen kortstondig −40 W opleveren,
en dat op het scherm zetten roept een vraag op waar geen antwoord op is. Klemmen is hier
geen gok maar een natuurkundige ondergrens.

### 36.3 Wanneer er geen getal is

Dezelfde structuur als het zonneoverschot, en om dezelfde reden: **een ontbrekende term
wordt niet als nul gelezen.**

| Situatie | Uitkomst |
|---|---|
| Netvermogen onleesbaar | geen getal |
| Zonnerij bestaat, waarde onleesbaar | geen getal |
| Geen zonnerij geconfigureerd | opwek telt als 0 — de woning heeft geen panelen |
| Batterijrij bestaat, vermogen onleesbaar | geen getal |
| Geen batterijrij geconfigureerd | batterij telt als 0 |

Het onderscheid in de tabel is dat van §35.1 regel 1: **een rij die er niet is, is een
uitspraak van de installateur dat de woning het ding niet heeft; een rij die er wel is en
niets levert, is een gat.** Geen panelen betekent geen opwek en dat is een feit. Panelen
die we niet kunnen uitlezen betekent dat we het verbruik niet kennen, en dan hoort er
niets te staan.

#### De onleesbare batterij wijkt hier bewust af van het zonneoverschot

**Dit is geen slordigheid en hoort niet gelijkgetrokken te worden** (besluit Sven,
2026-08-08). Bij een batterijrij waarvan het vermogen niet leesbaar is doen de twee
getallen expliciet iets anders:

| | Zonneoverschot (§16) | Thuisverbruik |
|---|---|---|
| Wat er gebeurt | het getal **verschuift** | het getal is **volledig verkeerd** |
| Uitkomst | getal blijft staan, met een zin erbij | geen getal |

Bij het overschot schuift een ladende batterij de waarde op en klopt hij de rest van de
dag gewoon; de zin ernaast dekt dat af, en het advies dat erop rustte is onderdrukt. Bij
het thuisverbruik wordt het laadvermogen **volledig aan het huishouden toegeschreven** —
3.500 W op het scherm waar het huis er 500 gebruikt. Dat is geen onzeker getal maar een
verkeerd getal, en er valt geen richting bij te geven omdat laden en ontladen tegengesteld
werken.

De regel achter beide is dus dezelfde en de uitkomst verschilt daarom: **toon een getal
met een voorbehoud zolang het bruikbaar blijft, en toon niets zodra het dat niet meer
is.** Wie deze twee ooit gelijk wil trekken, moet die regel weerleggen en niet de
inconsistentie.

### 36.4 Een gemeten bron wint van de afleiding

Is er een bruikbare `general_consumption`-bron, dan is dát het thuisverbruik. De afleiding
vult alleen in wat niet gemeten wordt.

Een meting is nauwkeuriger dan een verschil van twee andere metingen, en de installateur
die zo'n bron heeft gekoppeld heeft daarmee gezegd dat dit de waarheid is. Het paneel
vermeldt niet welke van de twee routes het was: voor de bewoner is het één getal, en de
installateur ziet de bron staan bij Energiebronnen.

### 36.5 Waar het op het Overzicht komt

**Boven het netvermogen, als eerste regel van `Actuele situatie`.** Sven's neiging, en
ik onderschrijf hem met een sterker argument dan volgorde van zoeken.

De regels in die kaart lezen nu als een verzameling *meterstanden*. Thuisverbruik is de
enige die de vraag "wat doet mijn huis" beantwoordt; de rest beschrijft wat er waarheen
stroomt. Het netvermogen is bovendien een **gevolg** van verbruik minus opwek, dus het
staat in de verkeerde volgorde: eerst het gevolg, dan pas de oorzaken.

Er is een tweede argument dat losstaat van betekenis. Het netvermogen draagt een teken en
heeft daarom een uitleg nodig ("negatief betekent teruglevering aan het net"); het
thuisverbruik is altijd positief en heeft er geen. Het zelfsprekende getal bovenaan en het
getal met de voetnoot eronder leest beter dan andersom.

**Het tegenargument, en waarom het niet doorslaat.** Het netvermogen is een meting en het
thuisverbruik meestal een afleiding; een afgeleid getal bovenaan kan suggereren dat het de
primaire meting is. Maar het paneel toont het zonneoverschot al net zo goed afgeleid, en
voor een bewoner is de afleiding hier het betekenisvollere getal. Wie de meting wil ziet
haar er direct onder.

De nieuwe volgorde van `Actuele situatie`:

```text
Thuisverbruik · Netvermogen · Zonneproductie · Zonneoverschot ·
Percentage van maximum · Actuele energieprijs
```

**Voor de visuele ronde**, niet nu: dit is de sterkste kandidaat om van een gewone regel
een kopgetal te worden. Dat is een vormbeslissing en hoort daar thuis.

> **Ingehaald door §35.8b (2026-08-09).** Het thuisverbruik wordt het kopgetal, en het
> besluit valt daar in plaats van in de visuele ronde omdat het daar geen vormvraag is maar
> een gevolg: de energiescore mag afwezig zijn, dus de grootste plek op het scherm kan niet
> van hem zijn.

### 36.6 De zinnen, per situatie

Volgens de regel uit §35.9 en CLAUDE.md: eerst opschrijven welke zin bij welke situatie
hoort, dan pas bouwen. Elke zin staat hier als geheel; er wordt niets uit clausules
opgebouwd.

| Situatie | Wat er staat |
|---|---|
| Thuisverbruik bekend | het getal, zonder zin |
| Geen netmeting | *Niet beschikbaar* (de bestaande lege status; de checklist meldt de netbron al) |
| Zonnerij onleesbaar | *Niet beschikbaar*, plus: *Je omvormer levert op dit moment geen waarde, dus het thuisverbruik is niet te berekenen. Controleer de zonnebron bij Energiebronnen.* |
| Batterijvermogen onleesbaar | *Niet beschikbaar*, plus de bestaande batterijzin (§16) |

**De batterijzin wordt uitgebreid in plaats van verdubbeld.** Hij zegt nu dat het
*zonneoverschot* te hoog kan zijn. Met thuisverbruik erbij raakt dezelfde blinde vlek twee
getallen op één kaart, en twee bijna gelijke waarschuwingen naast elkaar is erger dan één
die beide noemt. Voorstel:

> *Het vermogen van je thuisbatterij kan niet uitgelezen worden. Een batterij die laadt of
> ontlaadt verschuift wat er van het net komt, dus het thuisverbruik is niet te berekenen
> en het zonneoverschot kan te hoog zijn. Koppel de vermogenssensor van de batterij om dit
> op te lossen.*

Dat vervangt `UNREADABLE_BATTERY_SENTENCE` op beide plekken waar hij staat (backend en
paneel), en het is meteen een voorbeeld van wat de zinneninventaris moet opleveren:
één plek waar zichtbaar is dat dezelfde zin twee keer bestaat.

### 36.7 De nieuwe entiteit

```text
sensor.domotiapp_energy_home_consumption
```

- **Een toevoeging, geen wijziging.** De zes bestaande ID's blijven exact zoals ze zijn,
  dus geen enkel dashboard en geen enkele statistiekreeks breekt. Dit is de veilige kant
  van harde regel 11.
- **Engels en vast**, via `ENTITY_OBJECT_ID_NAMES` (`"Home consumption"`), met dezelfde
  `suggested_object_id`-override als de rest. Bewaakt in `en` én `nl`, zoals de zes
  andere — anders heet hij bij een Nederlandse klant `sensor.domotiapp_energy_thuisverbruik`.
- **W, `device_class: power`, `state_class: measurement`**, zodat hij in de
  langetermijnstatistieken van Home Assistant bruikbaar is.
- **`unknown` wanneer er geen getal is**, nooit 0. Dat is dezelfde regel als bij de score:
  een nul zou een meting beweren.
- De README-lijst gaat van zes naar zeven ID's.

### 36.8 Wat dit niet raakt

- **De datakwaliteit.** Geen nieuw checklistitem en geen andere weging: er komt geen
  configuratie bij, alles wordt afgeleid uit bronnen die al gevraagd worden.
- **De energiescore.** Geen nieuwe component. Thuisverbruik is een meting, geen
  benuttingsas — er is geen antwoord op "wat kan de bewoner doen om dit te verhogen" dat
  ook maar iets met benutting te maken heeft, en §35.5 zegt dan: niet in de score.
- **Het zonneoverschot.** Variant 2 blijft de *gemeten* `general_consumption` gebruiken en
  niet de afleiding. Anders zou het overschot uit zichzelf worden afgeleid: het
  thuisverbruik komt uit het netvermogen, en het overschot ook.
- **De adviesregels.** De coach krijgt er geen regel bij.

### 36.9 Klaar wanneer

- een woning met alleen een netmeter en een omvormer toont een thuisverbruik dat gelijk is
  aan netvermogen plus zonneproductie, en het staat bovenaan `Actuele situatie`;
- een woning met een `general_consumption`-bron toont de gemeten waarde en niet de
  afleiding;
- een onleesbare zonnerij of batterijrij levert geen getal en de bijbehorende zin uit
  §36.6, terwijl een woning *zonder* die rij gewoon een getal krijgt;
- meetruis levert nooit een negatief getal op;
- `sensor.domotiapp_energy_home_consumption` bestaat met die exacte ID in `en` én `nl`, en
  de zes bestaande ID's zijn ongewijzigd;
- de datakwaliteit en de energiescore geven op elke bestaande testconfiguratie exact
  dezelfde uitkomst als ervoor.

## 37. Verbruik per apparaat, en de velden die om aandacht vroegen zonder iets te doen

### 37.1 Wat er gebouwd is

**`power_entity` heeft eindelijk een lezer.** Het veld werd op elk apparaatformulier
gevraagd, opgeslagen, én door de coordinator bewaakt — dus invullen zorgde ervoor dat de
integratie vaker herrekende en verder niets. Nu levert het per apparaat het actuele
vermogen.

- **Op Apparaten**, als regel onder het apparaat waar het over gaat: *Nu: 1.150 W*.
- **Op het Overzicht** alleen een telling: *Apparaten die nu draaien*. Een telling is een
  feit over de woning; de apparaten zelf horen op Apparaten, waar ze beschreven staan. Ze
  op beide schermen zetten maakt van het Overzicht een dashboard, en dat is precies wat de
  indeling niet wilde zijn.

**Een apparaat zonder koppeling krijgt geen regel.** Niet "onbekend", niet "0 W". Zo'n
apparaat is geen gat, en een kolom lege waarden meldt een storing waar niets aan de hand
is — dezelfde regel als bij de tegelteksten.

**De eenheid komt van de entiteit zelf, en alleen `W` en `kW` worden geaccepteerd.** Een
vermogenssensor die geen van beide meldt wordt overgeslagen in plaats van als watt gelezen:
een kilowatt die als watt binnenkomt zit er duizend keer naast, en dat is precies de stille
gok die §15 verbiedt.

**`DEVICE_RUNNING_MIN_POWER_W = 10`** bepaalt wanneer een apparaat "draait". Sluimerverbruik
is bij de meeste huishoudelijke apparaten een paar watt, dus dit is een vloer onder de ruis
en geen oordeel over het apparaat. Een vaste constante en geen voorkeur, om dezelfde reden
als de hysterese-constanten (§16): het beschrijft hoe de motor een meter leest.

De telling is **afwezig** wanneer geen enkel apparaat een vermogensentiteit koppelt. "0
draaien" zou een meting beweren over elk apparaat in huis.

### 37.2 Velden die om invoer of een koppeling vragen zonder lezer

**Volledige inventarisatie, gemaakt op verzoek van Sven (2026-08-09)**, omdat een veld dat
om aandacht vraagt en niets doet vertrouwen kost bij elke installatie. Niet alles hieronder
wordt in deze ronde opgelost; de lijst staat hier zodat er niets opnieuw ontdekt hoeft te
worden.

#### Nog open — vragen om een koppeling en doen niets

| Veld | Waar gevraagd | Gevolg vandaag |
|---|---|---|
| `status_entity` | elk apparaatformulier | bewaakt, nooit gelezen |
| `energy_entity` | elk apparaatformulier | bewaakt, nooit gelezen |
| `remaining_time_entity` | elk apparaatformulier | bewaakt, nooit gelezen |
| `temperature_entity` | elk apparaatformulier | bewaakt, nooit gelezen |
| `battery_level_entity` | apparaatformulier bij `ev_charger` | bewaakt, nooit gelezen — §34 geeft het een lezer |
| brontype `price_forecast` | ~~keuzelijst Energiebronnen~~ | **opgelost in 0.7.1, §38.1** |
| brontype `solar_forecast` | ~~keuzelijst Energiebronnen~~ | **opgelost in 0.7.1, §38.1** |

**De twee brontypen zijn het ernstigst.** Dit is geen veld dat je kunt overslaan: het staat
als keuze in de lijst, met een hulptekst die uitnodigt een entiteit te koppelen (*"De
entiteit met de verwachte opbrengst"*). Wie hem invult krijgt een bron die nergens in
meetelt. §28 zegt al dat prognose niet gebouwd wordt; de keuze had dan niet aangeboden
moeten worden.

**De vijf koppelingen kosten meer dan niets.** De coordinator zet ze in de lijst van
bewaakte entiteiten, dus elke statuswijziging veroorzaakt een herberekening die met
diezelfde waarde niets doet. Invullen maakt de integratie drukker zonder enig effect.

#### Bewust leeg tot de aansturingsrelease

Deze zijn vroeg toegevoegd omdat ze anders bij elke klant opnieuw uitgevraagd moeten
worden (§12), en ze vragen de installateur niet om iets in te vullen:

- `capabilities` op bron en apparaat — alleen gevalideerd, nooit gebruikt;
- `control_forbidden_reason` — wordt getoond in de lijst, maar door de motor niet gelezen;
- `control_level` op de woning — staat uitgeschakeld in het formulier met uitleg erbij.
  **§44.9 stelt voor hem het plafond van de woning te maken**, en geeft hem daarmee zijn
  lezer: de modus van een apparaat kan er dan nooit boven uit.

#### Geen lezer, en dat is goed

- `notes` op bron en apparaat, en `location` op een apparaat. Documentatie voor de
  installateur; teruggetoond worden ís hun functie.

#### Wat wél een lezer heeft, tegen de verwachting in

Twee die tijdens de inventarisatie voor dood werden aangezien:

- **`duration_minutes`** wordt gelezen, via `DeviceProfile.latest_start` in de
  venstertoets van de advisor. Het rekent terug wanneer een apparaat uiterlijk moet
  starten.
- **`energy_tax_eur_kwh`, `supplier_markup_eur_kwh`, `vat_percent`,
  `feed_in_markup_eur_kwh`, `net_metering_until`, `scale_factor`, `invert_value`,
  `value_source`, `attribute_name`** worden alle gelezen via een property of via
  `read_entity_value`. Een zoekopdracht die alleen de motor doorzoekt mist ze.

### 37.2b Code die alleen door tests bereikt wordt

Naar aanleiding van het defect in deze ronde — de lezer zat in `Calculator.calculate()`,
dat de coordinator nooit aanroept — is de hele package nagelopen op functies die
productiecode nergens aanroept. Op verzoek van Sven (2026-08-09), met het argument dat dit
waarschijnlijk niet het enige geval was.

**Resultaat: één echte vondst.**

| Functie | Oordeel |
|---|---|
| `validators.has_errors` | **dood.** Bestond, werd getest, werd door niets gebruikt — noch door de motor, noch door de WebSocket-API, noch door het paneel. **Weg in 0.7.1, §38.5.** |
| `Calculator.calculate` | alleen tests, en dat mag: hij is sinds deze ronde één regel die de twee helften samenstelt, met een docstring die zegt dat de coordinator hem niet gebruikt. Er kan zich niets meer in verstoppen. |
| `Store._async_migrate_func` | geen vondst: een haak die Home Assistant zelf aanroept bij een schemawijziging. |

De overige ~55 treffers zijn vals alarm van dezelfde soort als bij de veldaudit
(§37.2): properties worden als attribuut gelezen en niet aangeroepen,
WebSocket-handlers worden door een decorator geregistreerd, en callbacks gaan als
referentie mee. **Een zoekopdracht op `naam(` vindt die niet**, precies zoals een
zoekopdracht over `engine/` de velden achter een property miste.

De frontend heeft dit gat niet: `mountPanel` in de testlaag start het paneel langs dezelfde
weg als Home Assistant zelf.

### 37.3 Wat deze ronde niet raakt

- **De adviesregels.** Het vermogen per apparaat wordt getoond, niet geïnterpreteerd. Of
  een apparaat draait terwijl de coach het afraadt is een adviesvraag en hoort bij fase 2.
- **De datakwaliteit en de energiescore.** Geen nieuw checklistitem, geen component. Een
  gekoppelde vermogenssensor mag het cijfer van de bewoner niet bewegen.
- **De vijf overige koppelingen.** Zie §37.2; ze krijgen een lezer of ze verdwijnen, maar
  niet in deze ronde.

### 37.4 Klaar wanneer

- een apparaat met een gekoppelde vermogenssensor toont zijn actuele vermogen op Apparaten,
  en een apparaat zonder koppeling toont daar niets;
- een sensor in kW wordt omgerekend, en een sensor zonder eenheid wordt overgeslagen;
- het Overzicht toont het aantal draaiende apparaten, en niets wanneer geen enkel apparaat
  een vermogensentiteit koppelt;
- sluimerverbruik telt niet als draaiend;
- datakwaliteit en energiescore geven op elke bestaande testconfiguratie exact dezelfde
  uitkomst als ervoor.

## 38. De opruimronde: alles wat om aandacht vroeg zonder iets te doen

**Status: gebouwd in 0.7.1.** Eén thema, en daarna is de categorie leeg: *het product vroeg
of bood iets dat niets deed.* De inventarisatie staat in §37.2; dit is wat ermee gebeurd is.

De vraag die elk punt hieronder verbindt is niet "gebruiken wij dit veld", maar:

> **Kan de installateur of de bewoner hier iets invullen dat ooit gelezen wordt?**

Zo nee, dan mag het niet gevraagd worden. Dat is dezelfde vraag als bij de datakwaliteit
(§16, de vijf gevallen van een eis die niet van toepassing is), nu gesteld over het
formulier in plaats van over de checklist.

### 38.1 De twee prognosebronnen: uit de lijst, niet uit het model

`price_forecast` en `solar_forecast` stonden als volwaardige keuze in Energiebronnen, met
een hulptekst die uitnodigde een entiteit te koppelen — *"De entiteit met de verwachte
opbrengst"* — en de motor las ze nergens. §28 zegt dat prognose niet gebouwd wordt; de
keuze had dan niet aangeboden moeten worden.

**Optie D, goedgekeurd door Sven (2026-08-09): uit de keuzelijst, geldig in het model.**

| | Wat er gebeurt |
|---|---|
| Nieuwe rij | het type is niet te kiezen |
| Bestaande rij | blijft geldig, blijft bewaard, blijft leesbaar in het formulier |
| Rijweergave | een informatieve regel die zegt dat er niets mee gedaan wordt |

**Waarom niet uit `SOURCE_TYPES`.** Dan zou elke bestaande rij in quarantaine gaan —
*"Onbekend brontype"*, niet gebruikt, met een foutkleur — voor een keuze die het product
zelf heeft aangeboden. Dat is een hardere straf dan de situatie verdient en de installateur
kan hem niet ongedaan maken.

De goedgekeurde zin, woordelijk:

> *Dit brontype is nog niet in gebruik. DomotiApp Energy rekent alleen met het huidige
> moment en leest geen verwachtingen. De koppeling blijft bewaard, maar er wordt op dit
> moment niets mee gedaan.*

Hij staat op de rij **vóór** de compleetheidscontrole: een installateur naar een veld sturen
op een rij die door niets gelezen wordt, is hem werk laten afmaken dat geen effect heeft.
Toon: informatief. De rij is niet stuk.

**Het type blijft in de keuzelijst staan zolang de rij hem draagt.** Een select waarvan de
huidige waarde ontbreekt rendert leeg, en de eerste opslag herschrijft de rij dan stil naar
wat er toevallig gekozen wordt — een keuzelijst die opgeslagen gegevens verandert omdat wij
haar waarde hebben weggehaald.

### 38.2 De thuisbatterij had een eigen as nodig

`home_battery` als **apparaattype** is verplaatsbaar by default, dus advisable, dus vroeg de
checklist om een energie per cyclus. Een batterij heeft geen cyclus: niemand start hem, hij
volgt het overschot vanzelf.

Dat is hetzelfde geval als de tabletlader van 0.6.1, één type verderop — maar de reparatie
van toen kon het niet dragen. Die hing alles aan `is_advisable`, en `is_advisable` leunde op
`is_flexible`. Een batterij **is** verplaatsbaar; energie door de tijd schuiven is precies
wat hij doet. Hem inflexibel noemen zou het probleem verstoppen achter een bewering die
gewoon onwaar is.

Daarom een derde as: **`NEVER_ADVISED_DEVICE_TYPES`**, types waar de coach de bewoner nooit
iets over kan zeggen, ongeacht wat er aangevinkt staat.

> De vraag om een type hieraan toe te voegen is niet "gebruiken wij het al", maar **"bestaat
> er een moment waarop een bewoner geadviseerd kan worden dit te starten"**. Zo nee, dan is
> elk veld dat advies voedt een vraag zonder lezer.

**Dit raakt `has_movable_load` niet.** Dat is een uitspraak over de woning — kan verbruik
naar de zon verplaatst worden — en een batterij doet dat zonder dat iemand geadviseerd
wordt. De zonne-as blijft dus aan, wat precies de reden is dat de batterij in dat predicaat
staat (§35.4a).

### 38.3 Drie soorten velden die verdwijnen, en het verschil

| Soort | Wat het is | Voorbeeld | Wanneer verborgen |
|---|---|---|---|
| **Adviesbegrip** | ordent, timet of dempt advies | prioriteit, maakt geluid, dagen, tijdvenster | zodra er nooit advies komt |
| **Beschrijft niets** | geen waar antwoord voor dit type | vermogen en cyclus bij een slimme stekker | idem |
| **Adviesschakelaar** | bepáált of er advies komt | verplaatsbaar in de tijd, bedieningsniveau | **alleen bij een type dat nooit advies krijgt** |

De eerste twee komen **terug zodra het apparaat advisable wordt**, en dat is wat de override
van een dood spoor redt: vink *verplaatsbaar in de tijd* aan op een slimme stekker en iemand
heeft gezegd dat er advies moet volgen — en dan is het apparaat achter de stekker precies
waar vermogen en cyclus over gaan. Alleen op type verbergen zou een verplicht veld hebben
achtergelaten dat niet in te vullen is, en dat is de vorm van defect die deze ronde opruimt
in plaats van verplaatst.

**De warmtepomp blijft er bewust buiten.** Zijn nominale vermogen beschrijft iets echts, ook
al leest niemand het. Of wij daar überhaupt naar moeten vragen is een aparte open vraag
(§37.2), en die hier beantwoorden door het veld te verbergen zou hem terloops beslissen.

#### De eenrichtingsdeur

De derde soort is er later bij gekomen, en hij bestaat omdat de eerste twee regels op hem
losgelaten precies het tegenovergestelde bereiken van wat ze bedoelen.

> **Een veld dat een toestand kan veranderen mag nooit door die toestand verborgen worden.**
> Anders is het een deur die maar één kant op gaat.

`control_mode = monitor_only` is niet iets wat volgt uit "dit apparaat krijgt geen advies" —
het is er de **oorzaak** van. Verberg je het veld omdat het apparaat geen advies krijgt, dan
kan de bewoner die zijn vaatwasser op *alleen meekijken* zette hem nooit meer aanzetten. En
het is erger dan één vast veld: `control_mode` is één van de zes velden die de bewoner bezit
(§33.4), en de andere vijf zijn in die toestand al verborgen volgens de eerste regel. Wat
overblijft is een dialoog waarin hij niets mag aanraken, over zijn eigen apparaat.

**Waarom `is_flexible` er nooit onder viel, en dat is het punt dat de volgende ronde anders
opnieuw fout doet.** Hij is nooit verborgen omdat hij er nooit *voor in aanmerking kwam*: hij
staat niet in de lijst adviesbegrippen en niet in de lijst velden zonder waar antwoord. Dat
was geluk, geen ontwerp — beide lijsten zijn opgesteld door te kijken wat een veld *voedt*,
en deze twee voeden niets, ze **schakelen**. Wie de volgende ronde een lijst uitbreidt met
"alles wat alleen advies dient", pakt ze allebei mee, en dan zit de deur dicht.

Vandaar dat ze een eigen soort krijgen, met een eigen regel, in plaats van een uitzondering
in de andere twee.

**Waar ze wél weggaan.** Bij een type uit `NEVER_ADVISED_DEVICE_TYPES` schakelen ze niets:
op een thuisbatterij verandert geen van beide `is_advisable`, en geen van beide verandert
`has_movable_load`. Er is dan ook geen handeling in dat formulier die het apparaat advisable
maakt, dus er is geen deur om open te houden. Vastgelegd in
`test_nothing_on_a_battery_changes_whether_it_is_advised`, zodat het verbergen aan een
bewijs hangt in plaats van aan een redenering.

#### Wat het bedieningsniveau zegt waar het blijft staan

Drie hele zinnen, gekozen door de situatie — dezelfde afspraak als bij de tegelteksten
(§35.9), want ook hier bestaat een zin die uit helften wordt opgebouwd nergens in de bron.

| Situatie | Wat de hulptekst zegt |
|---|---|
| Advisable | *DomotiApp Energy adviseert in deze versie alleen; alles behalve "alleen monitoren" wordt als adviseren behandeld.* |
| Niet advisable, en niet door dit veld | *Dit apparaat krijgt geen advies zolang het niet verplaatsbaar is. "Alleen monitoren" legt vast dat dat zo moet blijven, ook als dat later verandert.* |
| Op `monitor_only` | *Op "alleen monitoren" krijgt dit apparaat geen advies. Zet het op "alleen adviseren" om het weer mee te laten doen.* |

De middelste is waarom het veld op een alleen-gemeten apparaat blijft staan. De oude zin was
waar over het product en zei niets over dít apparaat, waar sowieso niets behandeld wordt —
dat leest als een keuze zonder gevolg, en zo werd hij ook gemeld. Goed gezegd is het een
staande uitspraak: hij bepaalt wat er gebeurt op de dag dat iemand wél *verplaatsbaar*
aanvinkt.

De laatste is de weg terug, in woorden, voor de enige persoon die hem nodig heeft.

**De vier bedieningsniveaus blijven alle vier selecteerbaar**, ook waar er niets bestuurd
wordt. Dat is een besluit uit §12 en het staat los van deze sectie: de afspraak kan alleen
weersproken worden — en dus verdedigd — als de tegenspraak uitgedrukt kan worden. Het
alternatief dat overwogen is (alleen de zinloze opties weghalen) zou dat stilzwijgend
terugdraaien, en het lost bij de batterij niets op: daar blijven er dan nul over.

**Verbergen, niet tonen-en-uitschakelen.** Dat laatste is de andere afspraak in dit project
(het bedieningsniveau op Woning, §33.4a) en die geldt voor een veld dat in een latere release
beantwoordbaar wordt. Hier is niets te vroeg: de vraag is verkeerd voor dít apparaat. Een
verborgen veld met een waarde erin wordt bij naam genoemd voordat het bij opslaan verdwijnt,
door dezelfde melding die elke andere typewissel afhandelt.

**Een standaardwaarde wordt niet als verlies gemeld.** Een verse slimme stekker draagt een
prioriteit *Normaal* en een geluidsvlag die uit het type volgt; geen van beide heeft de
installateur getypt, en de backend geeft ze bij een ontbrekend veld precies zo terug
(`TYPE_DEFAULT` in `models.py`). Melden dat ze weggegooid worden, benoemt een verlies dat
niet plaatsvindt.

#### De rijweergave: tonen wat een gevolg heeft

Er stond *"Overig, alleen meten · Normaal · Alleen adviseren"*: een prioriteit die niets
ordent, naast een bedieningsniveau dat advies belooft aan een apparaat dat er geen krijgt.
Voor zo'n apparaat blijft over wat hem identificeert — type, locatie, vermogen.

**Het bedieningsniveau blijft staan waar het de réden is dat er geen advies komt.** Dat is
dezelfde regel als in het formulier, van de andere kant bekeken: toon wat een gevolg heeft.
0.7.1 liet het niveau in één keer vallen en repareerde daarmee de leugen maar maakte een
ergere. Een vaatwasser die de bewoner op *alleen meekijken* had gezet en die een
vermogenssensor heeft, las:

```text
Vaatwasser · Keuken · 2.000 W
Compleet.
```

Zijn eigen instructie stond nergens meer, en de statusregel dekt het niet af: de zin *"dit
apparaat wordt alleen gemeten"* verschijnt alleen zolang er géén vermogenssensor gekoppeld
is. Bij `monitor_only` staat het niveau er daarom weer bij; bij *alleen adviseren* op een
alleen-gemeten apparaat niet, want daar zegt het niets.

### 38.4 Een sectie mag alleen teruggeven wat zij toont

Gevonden doordat §38.3 het uitlokte, en het is een bug van vóór deze ronde.

Elk `ha-form` in de dialoog krijgt de velden die zijn sectie **declareert**, en rendert
daarvan alleen wat betekenis heeft. De wijzigingshandler kopieerde de hele gedeclareerde
lijst terug en las `undefined` voor elk verborgen veld — dus een vaatwasser die de
installateur bewust op *maakt geen geluid* had gezet, verloor dat zodra hij hem op *alleen
meekijken* zette en weer terug. Stil, en precies wat "verbergen is nooit wissen" verbiedt.

De handler kijkt nu naar wat er werkelijk op het scherm staat.

### 38.5 `validators.has_errors` is weg

Bestond, werd getest, werd door niets gebruikt (§37.2b). De assertie die hem leesbaar maakte
is meeverhuisd naar `tests/test_validators.py`, waar hij altijd al thuishoorde: dat is de
enige plek die hem ooit heeft aangeroepen.

### 38.6 Wat deze ronde niet raakt

- **De datakwaliteit en de energiescore.** Geen enkel cijfer beweegt. De batterij verlaat
  teller *én* noemer, zoals elk item dat niet van toepassing is.
- **De vijf apparaatkoppelingen zonder lezer** (`status_entity`, `energy_entity`,
  `remaining_time_entity`, `temperature_entity`, `battery_level_entity`). Ze beschrijven iets
  echts en wachten op een lezer; zie §37.2.
- **De velden die bewust leeg staan tot de aansturingsrelease** (`capabilities`,
  `control_forbidden_reason`, `control_level`).

### 38.7 Klaar wanneer

- de twee prognosetypes zijn niet te kiezen, een bestaande rij blijft geldig en zegt waarom
  er niets mee gebeurt, en opslaan verandert haar type niet;
- een thuisbatterij wordt nergens om een energie per cyclus of een tijdvenster gevraagd, en
  telt nog steeds als verplaatsbare last;
- een slimme stekker vraagt geen vermogen, cyclus of duur, en vraagt ze wél zodra hij
  verplaatsbaar wordt gemaakt;
- prioriteit, geluid en het tijdvenster verdwijnen bij een apparaat waar nooit advies over
  komt, en komen terug zodra iemand het verplaatsbaar maakt;
- **de twee adviesschakelaars blijven staan zolang zij iets kunnen schakelen**: een bewoner
  die zijn vaatwasser op *alleen meekijken* zet, kan hem in datzelfde scherm weer aanzetten;
- de rij van zo'n apparaat toont type, locatie en vermogen, plus het bedieningsniveau
  wanneer dát de reden is dat er geen advies komt;
- een verborgen veld overleeft een wijziging aan zijn buurveld, en een standaardwaarde wordt
  niet als verlies gemeld;
- `validators.has_errors` bestaat niet meer.

## 39. De visuele ronde: compacter, en groter waar het telt

**Status: gebouwd in 0.8.0.** Verfijnen, geen herontwerp. Het layoutpatroon uit fase 8 is de
norm gebleven: één kolom, hairlines in plaats van kaders, kleine kapitalen als stille
structuurstem. Wat vaststond en niet is aangeraakt: het Liquid Glass-thema blijft leidend,
`ha-card` krijgt geen eigen achtergrond, ronding, schaduw of `backdrop-filter`, kleur komt
uitsluitend uit themavariabelen, en er is geen serif.

### 39.1 Compacter en groter is één ruil, geen tegenstelling

De lucht tussen rijen en de grootte van de getallen zijn twee verschillende budgetten. Het
eerste was royaal begroot en kostte een schermvol scrollen per tabblad; het tweede was zuinig
begroot en liet de getallen — waarvoor de klant het paneel opent — lezen als bodytekst.

| | Was | Is | Waarom |
|---|---|---|---|
| `--domotiapp-space-row` | 20px | **14px** | de hairline scheidt, niet de witruimte |
| `--domotiapp-space-section` | 40px | **26px** | drie kaarten passen weer op één scherm |
| kaartpadding | 32px | **26px** (mobiel 16px) | op 358px bleef er weinig over voor inhoud |
| `.stat-value` | 1,05rem | **1,2rem** | het getal is de regel, niet het etiket |
| `.display-value` | 3rem | **3,4rem** (mobiel 2,6rem) | het kopgetal domineert nu echt |
| `.card-title` | 1,5rem | **1,4rem** | een kop hoeft niet mee te groeien met een getal |

Die laatste is de omkering die de ruil zichtbaar maakt: **de koppen gaan iets omlaag terwijl
de cijfers omhoog gaan.** De hiërarchie op een kaart hoort van het getal uit te gaan, niet van
de titel.

### 39.2 De dialoog opent nog maar twee secties

Fase 8 gaf de dialoog inklapbare secties; er stonden er drie open, en dat is op een telefoon
in een meterkast bijna het hele scherm voordat er iets getypt is.

Open: **Apparaat** en **Verbruik**. Dat is de hele eerste doorloop — de datakwaliteit vraagt
niets buiten die twee. Wat erna komt is een tweede bezoek en kost één tik.

De volgorde volgt wat een installateur als eerste invult: *Apparaat → Verbruik → Wanneer het
mag draaien → Koppelingen → Aansturing → Notities.* Koppelingen zijn naar voren gehaald,
vóór Aansturing: sensoren koppelen hoort bij de installatie, het bedieningsniveau stuurt in
deze release niets aan. Notities zijn een eigen sectie geworden, zoals bij Energiebronnen —
dat waren twee verschillende indelingen voor hetzelfde soort dialoog.

**De aanvechtbare helft:** *Wanneer het mag draaien* is dichtgegaan, en die sectie bevat het
gereed-venster dat een punt waard is op de datakwaliteit. Het is alleen geen punt voor
*compleetheid* (§16), en het is de enige sectie die de bewoner op zijn eigen scherm opent in
plaats van de installateur bij oplevering.

### 39.3 Een lege rij: bestaan volgt de configuratie, waarde volgt de meting

Bij een woning zonder panelen stonden er drie regels over zonne-apparatuur: *Zonneproductie —
Nog niet ingesteld*, *Zonneoverschot — Niet beschikbaar*, *Zelfbenutting — Niet beschikbaar*.
Drie tekortkomingen die de bewoner nooit kan opheffen, over hardware waarvan de installateur
al heeft gezegd dat zij er niet is.

> **Een rij bestaat op grond van wat de woning heeft; haar waarde volgt uit wat er nu gemeten
> wordt.**

Dat zijn twee vragen, en ze door elkaar halen gaat in beide richtingen mis:

| Fout | Gevolg |
|---|---|
| rij verbergen omdat er *nu* geen waarde is | een storing verdwijnt mee — een onleesbare netmeter is dan gewoon van de kaart |
| rij tonen die deze woning *nooit* kan vullen | een gebrek melden dat niet bestaat |

Daarom hangt het **bestaan** van een rij aan de configuratie, die stabiel is en niet knippert,
en betekent *"Niet beschikbaar"* weer wat het hoort te betekenen: **deze woning heeft het ding
wel en we kunnen het nu niet lezen.**

Dat is precies het onderscheid tussen *kan niet* en *nu even niet*, en het is dezelfde lezing
van een bronrij als overal elders: een rij is de uitspraak van de installateur dat de woning
het ding heeft, in- of uitgeschakeld (`engine/completeness.py`).

Concreet weg bij een woning zonder zonnerij: Zonneproductie, Zonneoverschot, Zelfbenutting en
de batterijzin. Weg wanneer geen enkel apparaat een vermogensentiteit koppelt: *Apparaten die
nu draaien*. Blijven staan, altijd: netvermogen, percentage van maximum en de prijs — dat zijn
de onvoorwaardelijke items, en een lege regel daar is een storing die gezien moet worden.

### 39.4 Wat de consistentiecontrole opleverde

Nagelopen over alle zes tabbladen: kaartindeling, kopstijl, knopplaatsing en lege statussen.

**Al consistent, en het patroon staat hier zodat het zo blijft:**

- **Knoppen.** Een actie die bij één kaart hoort staat *in* die kaart (`Opnieuw berekenen`,
  `Apparaat toevoegen`, `Bron toevoegen`, `Logboek wissen`); een actie die het hele tabblad
  opslaat staat *na* de kaarten in `.tab-actions` (Woning, Mijn voorkeuren). Een opslaknop
  onder een onderwerpkop leest anders alsof hij dat onderwerp opslaat.
- **Eén primaire knop per scherm.** Blauw is voorbehouden aan koppen, links en die ene knop.
  `Logboek wissen` is bewust niet primair.
- **Lege lijsten** gaan overal via `createRowList({ emptyText })`, lege waarden via de
  `empty`-tekst van `statRow`.
- **Dialoogacties** staan overal in dezelfde volgorde: Annuleren, dan Opslaan.

**Rechtgezet:** de sectie-indeling van de apparaatdialoog en die van de brondialoog liepen
uiteen (§39.2).

**Bewuste uitzondering:** `.subheading` wordt precies één keer gebruikt, voor *Waarschuwingen*
binnen de Advieskaart. Dat is wat een subkop is: een tweede lijst binnen één kaart. Er een
eigen kaart van maken zou een kaart toevoegen aan het drukste tabblad, tegen §39.1 in.

### 39.5 Mobiel

Getoetst met de paneelbreedte op **358px** — dat is wat de containerquery meet, en dat is de
eerlijke toets: met de Home Assistant-zijbalk open op een tablet is het scherm ruim en het
paneel niet.

- één kolom, geen enkele horizontale scroll — geen element in de shadow root heeft
  `scrollWidth > clientWidth`;
- elk tikdoel ≥ 44px, gemeten in plaats van aangenomen: nul knoppen, tabbladen of
  sectiekoppen eronder;
- **de knoppen van een rij gaan over de volle breedte en delen de regel.** Op een telefoon
  stonden *Bewerken* en *Verwijderen* als twee etiketgrote doelen tegen de rechterrand; nu
  heeft een duim een halve regel.

**Niet getoetst, en dat is een echte beperking:** de dialoog wordt schermvullend via een
`@media (max-width: 600px)` op het *viewport*, en het browservenster liet zich in deze
omgeving niet verkleinen — `resize_window` meldt succes en `window.innerWidth` blijft 1920.
De containerquery is dus wel echt getoetst en de mediaquery niet. Die CSS is ongewijzigd
sinds de ronde waarin zij wel is nagelopen.

### 39.9 Bekende beperking: 320 CSS-pixels

De tabbalk breekt bij 320px nog naar drie regels. De tightening is afgestemd op 358px, en
bij 360 en breder past hij op twee. Gemeten met de browsertests, niet aangenomen.

**Besluit van Sven, 2026-08-09: dit blijft zo.** 320px is een iPhone SE uit 2016; de
klanten van DomotiTech hebben tablets en moderne telefoons. De browsertest toetst daarom
op 360 — en de grens is niet opgerekt om groen te worden, want dan zou de test niet meer
beschrijven wat er ontworpen is.

## 40. De safe areas, en hoe je ze toetst zonder telefoon

**Status: gebouwd in 0.8.1.** Productiebug op Sven's iPhone, gemeld op 2026-08-09.

### 40.1 Wat er misging

De schermvullende dialoog opende met zijn titel achter de klok en zijn sluitknop achter het
batterijpictogram. De oorzaak is precies wat Sven vermoedde: de stylesheet gebruikte
`env(safe-area-inset-bottom)` **vier keer** en de andere drie zijden **nul keer**. Zodra een
element de volle hoogte gebruikt, heb je op iOS ook `safe-area-inset-top` nodig.

**Dit is geen cosmetisch gebrek maar een val.** Een dialoog heeft drie uitgangen — de
achtergrondklik, Escape en het kruisje — en bij een schermvullende dialoog blijven er nul
over: de achtergrond ligt volledig onder het oppervlak en een telefoon heeft geen Escape.
Het kruisje was de enige uitweg, en die zat onder de statusbalk.

Nagelopen op alle vier de zijden en op alles wat de volle hoogte of breedte gebruikt:

| Plek | Was | Is |
|---|---|---|
| `.dialog-surface` (volle hoogte) | alleen onder | alle vier, plus `box-sizing: border-box` |
| `:host` (het paneel zelf) | alleen onder | links en rechts via `max()`, voor de uitsparing in landschap |
| `.dialog` (bureaublad) | alleen onder | ongewijzigd; daar raakt niets een rand |

`box-sizing` is er bijgekomen omdat de eerste versie van de reparatie een tweede fout maakte:
padding valt **buiten** `height: 100%`, dus het blad werd net zoveel hoger dan het scherm als
de insets diep zijn, en beide uiteinden vielen eraf. Dezelfde bug, één laag lager.

### 40.2 De toets: vervals de inset in plaats van hem op te wekken

De vraag van Sven was de belangrijkste van deze ronde: *hoe toetsen we dit zonder dat ik elke
mobiele wijziging op mijn eigen telefoon controleer?* Dat schaalt niet naar klanten met
andere toestellen, en het viewport van de ontwikkelmachine liet zich niet verkleinen
(`resize_window` meldt succes, `window.innerWidth` blijft staan).

**Een env()-waarde is niet te zetten** — niet vanuit CSS, niet vanuit script. Wat je er niet
in kunt schrijven, kun je ook niet toetsen. Dus loopt elke inset nu door een custom property:

```css
--domotiapp-safe-top: env(safe-area-inset-top, 0px);
```

Daarmee verschuift het probleem van "welk apparaat rendert dit" naar "welke waarde staat er in
deze variabele", en dat laatste is in elke browser te zetten. De controle wordt:

1. zet de vier tokens op de maten van een iPhone (59/34, of 59 links en rechts in landschap);
2. leg de vormregels van de telefoon-mediaquery er met de hand overheen;
3. meet: valt de kop onder de statusbalk, eindigen de knoppen boven de home-indicator, past
   het blad binnen het scherm, en is het kruisje het bovenste element op zijn eigen midden
   (`elementFromPoint`, want aanwezig is niet hetzelfde als aantikbaar).

**Dat vond meteen de `box-sizing`-fout in de reparatie zelf**, vóór de tweede oplevering aan
een echte telefoon. Dat is het bewijs dat de aanpak werkt en niet alleen de vorige fout
afdekt.

**Daarom staan de insets bewust buiten de mediaquery.** Alleen een schermvullend blad kan een
uitsparing raken, dus de verleiding is om ze in `@media (max-width: 600px)` te zetten. Maar
dan zit de enige regel die op een telefoon goed moet zijn achter de enige voorwaarde die geen
enkele geautomatiseerde controle hier kan aanzetten. Op een bureaublad zijn alle insets `0px`,
dus onvoorwaardelijk kost niets.

**Wat de mediaquery zelf doet — breedte, hoogte, ronding — blijft ongetoetst in dit project.**
Dat is eerlijk op te schrijven en niet op te lossen zonder een echt smal viewport; het is de
kandidaat voor de Playwright-ronde, die viewports wél kan zetten.

### 40.3 De bewaking

Vier tests in de frontendlaag, op de stylesheet zelf in plaats van op de rendering — jsdom
doet geen cascade (CLAUDE.md), dus dit is een declaratiecontrole en het zegt dat ook:

- elke inset loopt door een token; **geen enkele bare `env()`** buiten de vier definities;
- `.dialog-surface` declareert alle vier de kanten;
- de insets staan **niet** in de mediaquery;
- `:host` gebruikt `max()` voor links en rechts.

Die vangen de terugval — iemand die een nieuw schermvullend element toevoegt zonder insets —
en de browsercontrole met vervalste waarden vangt de geometrie.

## 41. De zinneninventaris wordt gegenereerd

**Status: het script en de bewaking zijn gebouwd in 0.8.1. Het herschrijven zelf is
uitgesteld tot het einde** (besluit Sven, 2026-08-09): er komen nog zinnen bij, en nu
herschrijven betekent het overdoen.

### 41.1 Waarom generatie en niet onderhoud

`TEKSTEN.md` is één keer met de hand gemaakt, bij 0.4.2, en was bij 0.8.0 drie ronden
verouderd: tien zinnen van de scoretegel, de gesplitste exportwaarschuwing, de prognosezin en
de drie niveauzinnen waren er allemaal bij gekomen zonder dat het document bewoog.

**Een document dat stil veroudert is erger dan geen document**, want het wordt gelezen alsof
het klopt. Dus: `scripts/extract_texts.py` schrijft het, en `tests/test_texts.py` faalt zolang
het achterloopt. De reparatie is één commando.

Het bijeffect is wat het bruikbaar maakt tussen nu en het herschrijven: **de diff van
`TEKSTEN.md` is wat een ronde aan de klant heeft toegevoegd, in zijn woorden.**

### 41.2 Wat het script wel en niet doet

Alleen de standaardbibliotheek, en niets ervan raakt `custom_components/` — dezelfde regel als
`ha_check.py`.

- **Python** via `ast`: elke stringconstante en elke f-string, met de slots als `{...}`.
  Docstrings vallen af; dat is de enige string in het pakket die niemand ooit ziet.
- **JavaScript** via een regex over enkele aanhalingstekens, met commentaar eruit.
- **De CSS eruit.** De stylesheet is een template literal van honderden regels waarvan elke
  declaratie op een string lijkt. Blijft die staan, dan is twee derde van de inventaris
  opvulling en leest niemand hem een tweede keer.
- **Engels apart gemarkeerd**, onderaan, in plaats van weggefilterd. Een Engelse zin in de UI
  is een fout tenzij het een identifier is — maar de logregels die daar opduiken hóren Engels
  te zijn, en dat per regel beoordelen is precies het punt.

De taalherkenning leunt op stopwoorden die de twee talen **niet** delen. Dat is geen detail:
op de eerste draai stond `is` in de Nederlandse verzameling, en dat ene gedeelde woord zette
elke Engelse logregel in het Nederlandse hoofdstuk.

**Wat het niet doet is oordelen.** Het verzamelt en sorteert; de herschrijfronde leest. De
redactionele indeling op zichtbaarheid — wat een bewoner dagelijks ziet vooraan, wat alleen de
installateur ooit ziet achteraan — komt terug wanneer dat herschrijven begint. Dan is dit
bestand de invoer en niet de uitvoer.

### 41.3 Het filter is een heuristiek en zegt dat

Een string telt als tekst wanneer hij lang genoeg is, geen identifier, pad, icoon,
formaatspecificatie of CSS-declaratie is, en een spatie bevat of met een hoofdletter begint.
Dat laat er te veel door in plaats van te weinig, en dat is de goede kant: een vals positief
is een regel die iemand overslaat, een vals negatief is een zin die niemand nakijkt.

## 42. Ronde A: wat er zichtbaar mankeerde

**Status: gebouwd in 0.9.0.** Drie kleine dingen die een klant vandaag zag, samen in één
ronde omdat ze alle drie klein zijn en alle drie zichtbaar. Daarna is de visuele ronde echt
dicht en kan fase 2 er nieuwe schermen bijzetten.

### 42.1 Het hoofdadvies stond er twee keer

Op het Overzicht staat het hoofdadvies bovenaan de Advieskaart en daaronder de lijst
waarschuwingen. Is het hoofdadvies zélf een waarschuwing — en dat is het bij elke woning die
nog niet compleet is — dan las de klant hem twee keer op één kaart.

Het Energiecoach-tabblad doet dit al goed sinds het gebouwd is (*"lists everything after the
primary one, without repeating it"*), dus er lag een precedent en de reparatie is één filter.

**De lastige helft is de lege staat.** *"Er zijn op dit moment geen waarschuwingen"* is alleen
waar wanneer er geen enkele is. Staat het hoofdadvies er als waarschuwing en verder niets, dan
is het juiste antwoord **niets zeggen**: de waarschuwing staat er, direct erboven. Die zin
alsnog tonen zou de regel erboven tegenspreken.

| Situatie | Wat de kaart doet |
|---|---|
| hoofdadvies is een waarschuwing, verder geen | alleen het hoofdadvies; geen lijst, geen zin |
| hoofdadvies is een waarschuwing, plus andere | de andere in de lijst, zonder het hoofdadvies |
| niets is een waarschuwing | *Er zijn op dit moment geen waarschuwingen.* |

### 42.2 Stille uren stellen uit, ze zwijgen niet

Bevinding 12 uit de eerste productie-installatie, en het gebruikt eindelijk een reason code
die gedefinieerd was en nooit werd uitgestuurd.

Tot 0.9.0 haalde het stille-urenvenster een lawaaiig apparaat uit de kandidatenlijst, en
verdween het advies. De bewoner zag niets en wist niet waarom — de stilte was niet te
onderscheiden van "er is geen overschot".

**Nu blijft het advies staan en verandert het van vorm:**

> *Er is momenteel zonneoverschot beschikbaar. Vaatwasser maakt geluid en het zijn stille uren
> tot 18:00. Wacht daarmee tot na 18:00, of pas de stille uren aan bij Mijn voorkeuren.*

Reason code `quiet_hours_active`, dezelfde rang als het gewone overschotadvies: het gaat over
hetzelfde moment en dezelfde meting, alleen de aanbevolen handeling verschilt. Het **vervangt**
het overschotadvies en komt er niet naast.

**Een stil apparaat wint, en dat is de volgorde die telt.** De regel vraagt eerst om een
kandidaat zonder de stille-urenvoorwaarde en pas als die er niet is met. Andersom zou een
bruikbaar advies ingeruild worden voor een uitstel, terwijl er een vaatwasser in de garage
staat waar niemand last van heeft.

**Geen bedrag onder een uitstel.** Het euro-bedrag beantwoordt "wat levert het op om dit nu te
doen", en het advies is om het nu niet te doen; een bedrag ernaast leest als een argument om
het uitstel te negeren.

**`allow_advice_during_quiet_hours` is weg.** Die schakelde het hele advies uit, en in de
uitstellende vorm is er niets meer om uit te schakelen. Een opgeslagen waarde wordt door
`from_dict` genegeerd in plaats van gemigreerd: niets leest hem, dus er is niets over te
zetten. Wie het niet eens is met het venster, verzet het venster — en de zin zegt waar.

De hulptekst bij de stille uren zei *"krijgen lawaaiige apparaten geen advies"*. Dat
beschreef het oude gedrag; hij zegt nu wat er werkelijk gebeurt. Een hulptekst die het vorige
gedrag uitlegt, leert de installateur iets aan dat niet meer waar is.

### 42.3 De tabbalk paste niet op een telefoon

Zes tabbladen met een icoon en een label wikkelden op 358px naar **drie regels**: een derde
van het scherm was tabbalk voordat er iets gelezen was.

Twee regels nu, door de tussenruimte, de letterspatiëring en het icoon elk een beetje te laten
inleveren. Gemeten: 87px in plaats van ongeveer 130, elk tikdoel nog 44px, geen horizontale
scroll.

**De iconen blijven.** Ze weglaten had dezelfde breedte opgeleverd, en ze zijn waar een
bewoner een tabblad aan herkent wanneer hij zoekt naar het tabblad dat zijn installateur door
de telefoon noemde. Dat is precies het gesprek waarvoor de zes tabbladen voor beide rollen
gelijk zijn (§33.6).

## 43. Fase 2: het urgentie-advies

**Status: gebouwd in 0.10.0.** Fase 2 uit de bouwvolgorde van §32.10. `deadline_approaching`
op rang 3 — de plek "harde tijdsgrenzen" die sinds 0.1.0 leegstond.

### 43.1 De zinnen, per situatie

Opgeschreven vóór de regel gebouwd werd, dezelfde afspraak als bij de tegelteksten (§35.9).

| Situatie | Wat er staat |
|---|---|
| Nu binnen `[laatste start − 30, laatste start]` | *Start {naam} nu als hij om {tijd} klaar moet zijn.* |
| Nog ruim op tijd | niets — "nu" zou onwaar zijn |
| Voorbij de laatste start, deadline nog niet verstreken | niets — zie §43.2 |
| Deadline verstreken | niets (§32.3: "je hebt het gemist" helpt niemand) |
| Geen duur ingevuld | niets — zonder duur is er geen laatste start, en die wordt niet geraden |
| Apparaat niet advisable of vandaag niet toegestaan | niets, via de bestaande regels |

### 43.2 Twee afwijkingen van §32.3, allebei om dezelfde reden

§32.3 legt vast: tekst *"Start [naam] nu om [tijd] te halen"*, severity `warning`, en het
advies *"loopt tot de deadline"*. Twee daarvan zijn hier anders, en beide keren omdat de zin
moet toetsen wat hij beweert.

**Het venster stopt bij de laatste start, niet bij de deadline.** Voor een vaatwasser van 180
minuten met een deadline van 07:00 is de laatste start 04:00. Om 04:30 nog zeggen *"start nu,
dan is hij om 07:00 klaar"* is gewoon onwaar — hij is dan om 07:30 klaar. Er is op dat moment
geen ware zin die helpt, en dan is zwijgen het antwoord dat §32.3 zelf al kiest ná de
deadline. Deze sectie neemt dat moment een half uur naar voren, naar het punt waarop de
deadline werkelijk onbereikbaar wordt in plaats van waarop hij formeel verloopt.

**De zin is voorwaardelijk en de severity is `info`, tot fase 3.** Dit is de belangrijkste
afwijking en de enige die ongedaan gemaakt moet worden.

Fase 2 heeft **geen signaal dat er werk te doen is**: `needs_ready_flag` is fase 3. Deze regel
kan een volle vaatwasser dus niet van een lege onderscheiden, en zou elke nacht opnieuw een
waarschuwing geven over een machine die misschien leeg is. Een waarschuwing die de helft van
de tijd onterecht is, leert mensen waarschuwingen negeren — en dat kost meer dan dit advies
oplevert.

Dus zegt de zin de voorwaarde die hij wél kent: *als* hij om die tijd klaar moet zijn. En de
severity wacht op de vlag die de bewering waarmaakt:

| | Fase 2 (nu) | Fase 3 (met de vlag) |
|---|---|---|
| Zin | *Start {naam} nu als hij om {tijd} klaar moet zijn.* | *Start {naam} nu om {tijd} te halen.* |
| Severity | `info` | `warning` |
| Voorwaarde | binnen het venster | binnen het venster **en** de vlag staat |

**Fase 3 mag deze regel dus niet alleen aanzetten, hij moet de zin en de severity terugzetten
naar wat §32.3 voorschrijft.** Dat staat hier zodat het niet vergeten wordt.

**Gedaan in fase 3, met één correctie op de derde rij van die tabel** (besluit Sven,
2026-08-11). De voorwaarde is niet *"de vlag staat"* maar *"weten we dat er werk is"*,
en de vlag is één van de antwoorden:

| Situatie | Zin | Severity |
|---|---|---|
| vlag-apparaat, vlag staat | *Start {naam} nu om {tijd} te halen.* | `warning` |
| vlag-apparaat, vlag staat niet | **geen advies** — dit is de lege machine van §32.5 | — |
| apparaat dat geen vlag nodig heeft | *Start {naam} nu als hij om {tijd} klaar moet zijn.* | `info` |

**Waarom die derde rij er moet zijn.** Letterlijk gelezen — "binnen het venster **en**
de vlag staat" — zou een laadpaal voorgoed zwijgen: die krijgt `needs_ready_flag`
per type niet, omdat hij via `status_entity` zelf kan zien of er een auto hangt
(§32.5). Alleen leest niets die entiteit tot §34. Voor zo'n apparaat is *"is er
werk"* dus oprecht onbekend, en een onbekend antwoord krijgt de zin die zijn eigen
voorwaarde noemt — niet stilte en niet een bewering. Dat is precies de regel die
deze sectie zelf oplegt: de zin mag alleen claimen wat de voorwaarde vaststelt.

### 43.3 Waarom dit advies niet kan pendelen

Vraag van Sven, en het antwoord is dat de hysterese hier niet het juiste gereedschap is.

**In fase 2 kán het niet pendelen, en dat is geen geluk.** De regel leest precies twee dingen:
de deadline en de duur. De deadline is een constante uit de configuratie; de duur is dat in
fase 2 ook. Er zit geen meting in, dus er is niets dat kan schommelen. **Het zonneoverschot
komt in deze regel niet voor** — dat was de zorg, en het is precies de reden dat hij er niet
in staat.

**Wat het overschot wél doet, is de volgorde beïnvloeden, en daar is al machinerie voor.**
`PrimaryAdviceGate` neemt een urgenter advies onmiddellijk over, dus een rang-3-advies
doorbreekt een vastgehouden rang-4-advies zonder op de dweltimer te wachten. En omgekeerd kan
een komend-en-gaand zonneadvies het urgentie-advies niet verdringen, want het rangeert lager.

**De echte pendelkans komt met de laadpaal, en dan is een ratel het gereedschap en geen
hysterese.** Zodra `required_duration_minutes` de laadtoestand leest, beweegt de laatste start
mee met een meting die ruist, en kan hij heen en weer over `nu + 30` kruipen. Een drempel met
een losmarge is daar het verkeerde antwoord: een deadline wordt één keer gepasseerd. Wat er
dan hoort te staan is een **ratel** — eenmaal gevuurd voor dit apparaat in dit venster, blijft
het staan tot het venster sluit.

**Die ratel wordt nu niet gebouwd.** Er is niets dat hem kan bewegen, en een mechanisme voor
een geval dat nog niet bestaat is precies het soort ongelezen machinerie dat §38 heeft
opgeruimd. Hij staat hier opgeschreven zodat er later niet opnieuw voor hysterese gekozen
wordt.

> **Bijgesteld door §44.8.** Hij hoort niet in de laadpaalronde maar in de
> aansturingsrelease, en hij is daar geen verfijning maar een **voorwaarde**: klappert het
> advies terwijl er aangestuurd wordt, dan schakelt de laadpaal mee met de ruis op een
> laadtoestandsmeting. Dat is hardware die aan- en uitgaat op meetruis, een andere orde van
> fout dan een zin die heen en weer springt.

### 43.4 Eén apparaat, één advies

Een vaatwasser binnen zijn urgentievenster terwijl de zon schijnt leverde twee items over
dezelfde machine: *start hem nu voor 07:00* en *er is zonneoverschot, gebruik hem nu*. Allebei
waar, allebei hetzelfde verzoek, en één ervan is ruis.

Dat is de les van het dubbele hoofdadvies (§42.1) één laag hoger: daar drukte het paneel één
item twee keer af, hier maakte de motor twee items over één onderwerp. De rang beslist welke
overblijft, dus de deadline wint van de zon en de zon van de prijs.

**Advies zonder apparaat wordt nooit samengevoegd.** Veiligheid, piek, prijs en de neutrale
situatie gaan over de woning, en twee daarvan kunnen tegelijk waar zijn.

### 43.5 De duur komt uit een functie, niet uit een property

`engine/scheduling.py`, met `required_duration_minutes` en `latest_start_minutes` — de vorm
die §34.8 vóór deze fase heeft vastgelegd. In fase 2 geeft de eerste gewoon
`device.duration_minutes` terug; het punt is dat het urgentie-advies zijn deadline dóór die
functie berekent, zodat de laadpaal later één tak in één functie is en geen verbouwing van het
advies.

**Eén afwijking: de tweede parameter is de metrics, waar §34.8 "snapshot" schreef.** De
advisor krijgt nooit een snapshot te zien — hij krijgt een `EnergyMetrics`, en daar staan de
metingen per apparaat al (`device_power_w`). Een laadtoestand landt daar ook. Een snapshot
door de coordinator heen trekken naar een pure functie die er verder niets mee doet, zou
betalen voor het verkeerde zelfstandig naamwoord.

### 43.6 Wat deze fase niet raakt

- **De vlag, de runtime-store en `set_ready`** — dat is fase 3 (§32.10).
- **De laadpaal** — `required_duration_minutes` heeft nog geen tak voor hem (§34.8).
- **De datakwaliteit en de energiescore.** Geen nieuw item, geen component. Een deadline is
  een adviesvraag.
- **Prognose.** Dit advies vereist er geen: je hoeft de toekomst niet te kennen om te weten
  dat later starten de deadline onhaalbaar maakt (§32.3).

## 44. De sturingsindeling: waar de knoppen komen te staan

**Status: ontwerp, alleen papier.** Er wordt in deze ronde niets gebouwd. De aansturing is een
eigen release met een eigen spec; dit legt vast **waar** de handelingen in het paneel landen,
zodat die release niet ook nog de indeling hoeft uit te vinden.

Nu geschreven omdat §33 en §34 vers zijn. De rolindeling en de laadpaal zijn precies de twee
stukken waarop dit rust, en die redenering opnieuw maken over drie ronden kost meer dan haar
nu opschrijven.

### 44.1 Eén regel waar de rest uit volgt

> **De handeling hoort bij de aanleiding.**

Een knop die iets doet, staat waar de reden staat om het te doen. Niet in een menu, niet op een
apart tabblad, niet in een lijst met alle apparaten die je zou kunnen bedienen.

Dat is dezelfde keuze als bij de zinnen: een tegel die zegt *waarom* er geen cijfer is, is
bruikbaar waar een streepje dat niet is (§35.9). Een knop volgt hetzelfde: *"Start Vaatwasser
nu als hij om 07:00 klaar moet zijn"* met de startknop eronder is één gedachte; dezelfde knop
op een bedieningspagina is een gedachte die de bewoner zelf moet afmaken.

### 44.2 Geen eigen tabblad

**De toestemming blijft op Apparaten, bij het apparaat waar zij over gaat.**

Een tabblad `Aansturing` zou een vierde plek maken waar iets over een apparaat staat — naast
Apparaten, het advies en de rij op het Overzicht — en het zou de indeling omdraaien: van "wat
weet ik over dit apparaat" naar "wat kan ik allemaal bedienen". Dat tweede is een dashboard, en
§8 heeft die vorm bewust afgewezen.

Het houdt ook de zes tabbladen op zes, voor beide rollen (§33.6). Dat is geen esthetiek maar de
telefoongesprekafspraak: *"ga naar Apparaten, open de vaatwasser"* moet één zin blijven die
voor de installateur en de bewoner hetzelfde betekent.

Op Apparaten staan dus, ongewijzigd: `control_mode` (bewoner), `capabilities` en
`control_forbidden` met zijn reden (installateur), met het veto uit §33.11 erop.

### 44.3 Waar de handelingen landen

> **Vervangen door §60.2** (0.24.0). Elke handeling landt in de ene sectie *Wat je
> nu kunt doen* op het Overzicht, plus — waar zij een aanleiding heeft — onder dat
> advies in de Energiecoach. De tabel hieronder staat er nog omdat de derde kolom
> uitlegt wáárom elke handeling daar hoort; de tweede kolom is achterhaald.

| Handeling | Waar (achterhaald) | Waarom daar |
|---|---|---|
| **Start nu** | onder het advies dat erom vraagt, op Overzicht én in Energiecoach | de aanleiding staat er al; de knop maakt hem afmaakbaar |
| **Klaar / vol** (`set_ready`) | ~~op Apparaten bij het apparaat~~ → de sectie op het Overzicht | twee momenten waarop een bewoner eraan denkt (§44.5) — maar het tweede moment vindt niet op een insteltabblad plaats |
| **Stop** | in `Nu aangestuurd` op het Overzicht | wie wil stoppen, zoekt niet in een apparaatlijst |
| **Goedkeuren** | onder het advies dat om goedkeuring vraagt | `approval_required` ís een advies met een knop (§44.6) |

**Een knop verschijnt nooit bij een apparaat waarvoor `control_forbidden` geldt.** Niet
uitgegrijsd, niet met een uitleg: helemaal niet. Uitgrijzen is voor iets dat later
beantwoordbaar wordt (§33.4a); dit is een afspraak met deze klant, en een zichtbare knop zou
suggereren dat er over te praten valt. De reden staat wél op Apparaten, waar de afspraak staat.

### 44.4 "Nu aangestuurd": een rijsoort, één knop per apparaat

> **Geen eigen sectie meer** (§60.2, 0.24.0): dit wordt een rijsoort binnen *Wat je nu
> kunt doen*. Alles hieronder blijft gelden — wat er staat, wanneer het er staat en wat
> `Stop` betekent — behalve de plaatsing. Een tweede sectie zou de bewoner opnieuw laten
> uitzoeken wélke sectie zijn handeling draagt.

Op het Overzicht, onder `Actuele situatie`. Per apparaat dat DomotiApp op dit moment
aanstuurt: **wat**, **sinds wanneer**, **waarom** (in de woorden van het advies dat het
veroorzaakte), en één **Stop**.

**De sectie bestaat op grond van de configuratie, niet van het moment** — dezelfde regel als
§39.3. Zij staat er zodra deze woning ten minste één apparaat in een aansturende modus heeft,
en zegt dan *"Er wordt op dit moment niets aangestuurd."* wanneer er niets loopt. Zou de sectie
pas verschijnen zodra er iets draait, dan is "waar zit de stopknop" een vraag die de bewoner
voor het eerst stelt op het moment dat hij hem nodig heeft.

Heeft de woning geen enkel aanstuurbaar apparaat, dan is er geen sectie. Dat is de andere helft
van dezelfde regel: geen tekortkoming tonen die deze woning niet kan opheffen.

### 44.5 Wat "stoppen" betekent — en dit is de beslissing die het meeste vastlegt

Drie dingen die het níét betekent, en één dat het wel betekent.

| Niet | Waarom niet |
|---|---|
| het apparaat uitzetten | het kan al gedraaid hebben voordat DomotiApp iets deed |
| de aansturing uitschakelen | dat is een instelling, en die staat op Apparaten |
| alles tegelijk stoppen | één knop voor meerdere apparaten is een knop waarvan je de gevolgen niet ziet |

**Wel: draai terug wat DomotiApp zelf heeft gedaan, en geef het apparaat terug aan de bewoner.**

Daaruit volgt een tweede vraag die makkelijk over het hoofd te zien is: **wat gebeurt er direct
daarna?** De situatie die de start veroorzaakte is nog steeds waar — er is nog overschot, de
deadline nadert nog — dus zonder verdere regel start DomotiApp het apparaat binnen één cyclus
opnieuw, en is de stopknop een knop die niets doet.

Dus: **stoppen onderdrukt de aansturing van dát apparaat**, tot het einde van zijn
gereed-venster, of vier uur wanneer het er geen heeft. Dezelfde soort houdbaarheidstermijn als
`READY_FLAG_MAX_AGE_HOURS` (§32.6) en om dezelfde reden: het is een uitspraak over een
*intentie* van nu, niet over de machine. Het paneel noemt het moment waarop de onderdrukking
afloopt, zodat niemand erdoor verrast wordt — net zoals bij de vlag.

### 44.6 `set_ready` op twee plekken, en `approval_required` op één

**`set_ready` staat op twee plekken en dat is bewust geen duplicatie.** Het zijn de twee
momenten waarop een bewoner erover nadenkt:

1. **onder het advies** — hij leest *"start nu om 07:00 te halen"* en denkt "hij is niet vol";
2. **op het Overzicht** — hij ruimt de keuken op en zet hem aan het einde vol.

> Het tweede punt stond hier eerst als *"op Apparaten, bij het apparaat"*. De
> redenering — twee momenten — klopte; de plaats niet. Een bewoner die de keuken
> opruimt slaat het Overzicht open en niet het tabblad waar een installateur zijn
> woning inricht (§60.3).

Dezelfde handeling, hetzelfde commando, twee aanleidingen. Eén ervan weglaten betekent dat de
bewoner op het verkeerde moment moet onthouden waar de andere staat.

**`approval_required` is geen aparte modus in de indeling maar een advies met een knop.** De
coach zegt wat hij wil doen en waarom, en de knop eronder zegt ja. Dat is precies de vorm die
er al staat, dus het kost geen nieuw scherm — en het houdt de belofte van §12 overeind dat de
drie waarheden (wat kan, wat gewild wordt, wat is afgesproken) gescheiden blijven: goedkeuren
verandert niets aan de configuratie.

### 44.7 Het logboek is vanaf de aansturing niet meer optioneel

Vandaag is het logboek prettig. Zodra DomotiApp een apparaat aanzet, is het het antwoord op
*"waarom draaide mijn droger om 03:00?"* — en dat is een vraag die één keer per klant komt en
dan meteen om een antwoord vraagt dat klopt.

Elke aansturing is een regel: wat, welk apparaat, welke reason code, welke gebruiker als er een
was, en of het gelukt is. **Ook een mislukte poging**, want een apparaat dat niet reageerde is
precies wat iemand komt navragen. De anti-spamregel uit §8 geldt hier niet: twee keer starten
is twee gebeurtenissen, geen herhaling.

### 44.8 De ratel hoort hier, en zij verandert van aard

§43.3 parkeerde de ratel als weergavevraag: zodra `required_duration_minutes` de laadtoestand
leest, beweegt de laatste start mee met een ruisende meting en kan het urgentie-advies gaan
klapperen. Een drempel met losmarge is daar het verkeerde gereedschap omdat een deadline één
keer gepasseerd wordt; wat er hoort is een ratel — eenmaal gevuurd voor dit apparaat in dit
venster, blijft staan tot het venster sluit.

**Met aansturing is dat geen weergavevraag meer.** Klappert het advies, dan klappert de
handeling: de laadpaal gaat aan en uit met de ruis op een laadtoestandsmeting mee. Dat is
hardware die schakelt op meetruis, en dat is een andere orde van fout dan een zin die
heen en weer springt.

Daarom hoort de ratel in deze sectie thuis: **hij is een voorwaarde voor aansturing, niet een
verfijning van het advies.** De aansturingsrelease bouwt hem, niet de laadpaalronde — en zeker
niet de hysterese-machinerie, die voor drempels is en niet voor klokken.

Concreet, als eis: *geen aansturing van een apparaat op grond van een deadline zonder een ratel
die de beslissing vasthoudt tot het venster sluit.*

### 44.9 Twee beslissingen die aan Sven zijn

**1. Wordt `control_level` op de woning de hoofdschakelaar?**

`control_mode` is een bewonersveld (§33.4) en dat is met reden zo besloten: het is zijn
apparaat en zijn uitknop. Zolang alles behalve `monitor_only` als `advice_only` behandeld wordt,
is dat onschadelijk — de bewoner kan *automatisch aansturen* kiezen en er gebeurt niets.

**Zodra er wél iets gebeurt, is die standaard consequent.** `control_forbidden` staat standaard
op `false`, dus op een verse installatie kan een bewoner zijn laadpaal op automatisch zetten
zonder dat de installateur ooit iets heeft gezegd.

Voorstel: **`control_level` op de woning is het plafond**, en de modus van een apparaat kan er
nooit boven uit. Het veld bestaat al, staat al uitgeschakeld in het formulier met uitleg, en
staat op de lijst "bewust leeg tot de aansturingsrelease" (§37.2) — dit geeft het zijn lezer.
Dan is de volgorde: de installateur opent de deur voor de woning, de bewoner kiest daarbinnen,
en `control_forbidden` blijft het veto per apparaat.

Het alternatief — `control_forbidden` standaard op `true` — doet hetzelfde maar per apparaat,
en dat is dertig vinkjes bij een woning waar de installateur één keer "nee" bedoelt.

**2. Hoe lang onderdrukt `Stop`?**

Voorgesteld: tot het einde van het gereed-venster, of vier uur zonder venster. Vier is een
gok van dezelfde soort als de vierentwintig uur van de vlag; als jij een ander getal
verdedigbaarder vindt, is dit de plek om het te kiezen.

### 44.10 Wat deze sectie niet vastlegt

- **Hoe er aangestuurd wordt.** Geen enkele `hass.services.async_call`, geen keuze van
  domeinen, geen retrybeleid. Eigen release, eigen spec.
- **Welke apparaten aanstuurbaar zijn.** Dat volgt uit `capabilities`, en die is al gevalideerd
  en nog nergens gelezen.
- **De aansturingslogica zelf** — wanneer iets aangaat, hoe lang, met welk vermogen. Dit gaat
  over waar de knop staat en wat hij belooft.
- **§43.2 blijft staan.** Fase 3 zet zin en severity van het urgentie-advies terug; dat is niet
  hier.

## 45. De achtste entiteit: `binary_sensor.domotiapp_energy_attention`

**Status: gebouwd in 0.11.0.** De aanleiding is een uitrolvraag, geen functionele: Sven zet
dit in twintig woningen neer en wil daar **één tegel** plakken, niet een template-sensor plus
een tegel. Een template-sensor die bij elke klant apart in `configuration.yaml` bestaat, is
een kopie van onze definitie buiten onze versiebeheer — en dus een plek waar drift ontstaat
zodra wij een reason code toevoegen of hernoemen.

Daarom hoort de definitie bij ons. De klantkant is dan één tegel die naar deze entiteit
wijst, en die tegel hoeft niets te weten.

### 45.1 Wat de entiteit is

| | |
|---|---|
| Entity-ID | `binary_sensor.domotiapp_energy_attention` (Engels en vast, zoals de zeven andere) |
| `device_class` | `problem` — daarmee kleurt elke kernkaart hem rood zonder styling |
| `on` | er is iets waar een mens nu iets aan kan doen |
| `off` | alles leesbaar en niets aan de hand |
| `unknown` | er is nog geen resultaat (§19: nooit `unavailable`) |

### 45.2 De vier codes, en waarom precies deze

**Dit is de kern van de sectie: de lijst mag niet stilletjes groeien.** Elke code die erbij
komt maakt de knop minder waard, want een tegel die vaak rood staat wordt een tegel die
niemand nog bekijkt. De vraag bij elke kandidaat is niet *"is dit erg"* maar:

> **Kan de bewoner of de installateur hier nú iets aan doen, en is het zeldzaam genoeg dat
> rood nog betekenis heeft?**

| Code | Waar hij vandaan komt | Waarom hij meetelt |
|---|---|---|
| `missing_required_data` | het advies | de installatie is niet af; de installateur kan hem afmaken |
| `high_grid_load` | het advies | de aansluiting zit tegen zijn grens; iemand kan iets uitzetten |
| `high_grid_export` | het advies | teruglevering tegen de grens; zelfde handeling, andere richting |

**Er stond hier een vierde reden, `invalid_entity_state`, en die is in 0.11.1
teruggedraaid. Waarom staat in §45.6.**

**Bewust níét in de lijst:**

| Code | Waarom niet |
|---|---|
| `high_energy_price` | severity `warning`, maar het is de markt twee keer per dag. Rood elke avond is rood dat niemand leest. |
| `solar_surplus`, `cheap_price_window`, `deadline_approaching` | kansen, geen problemen. Ze horen in het paneel, niet op een alarmknop. |
| `no_action_needed` | het tegendeel. |

**Een code toevoegen is een wijziging aan wat de knop betekent, niet aan een lijst.** Wie er
een aan toevoegt, zet de reden in deze tabel en beantwoordt de vraag hierboven; anders groeit
hij tot hij niets meer onderscheidt.

### 45.3 De attributen, en waarom er drie zijn

`state_content` van een `tile`-kaart accepteert een **attribuutnaam**. Dat is de hele reden
dat één tegel zowel de kleur als de zin kan dragen: zonder attribuut staat er `Probleem`, wat
waar is en niets zegt naast een woning die een concrete reden heeft.

| Attribuut | Wat erin staat |
|---|---|
| `advice_title` | de titel van het hoofdadvies — dit is wat `state_content` toont |
| `message` | de volledige zin, voor wie er een eigen kaart omheen bouwt |
| `reason_code` | de code, voor een automatisering die op één geval wil reageren |

`advice_title` bestaat alleen hier. De adviessensor draagt de titel in zijn *state*, en die is
op 255 tekens afgekapt (§19); een attribuut is dat niet, en een tegel leest een attribuut.

**De attributen zijn leeg zolang er geen advies is.** Geen lege sleutels met lege waarden: een
attribuut dat bestaat maar niets zegt, is een attribuut waar een dashboard toch op gaat
vertrouwen.

### 45.4 Waarom een tegel en geen dialoog

Geverifieerd tegen Home Assistant 2026.7, en twee bevindingen bepaalden de vorm:

- **De more-info-dialoog toont geen attributen.** Hij toont de state, de historie en het
  logboek. Attributen toevoegen om die dialoog informatief te maken werkt niet — ze worden
  niet gerenderd.
- **Een more-info-dialoog kan niet naar een paneel navigeren.** Er is geen kernactie voor.

Dus opent de tegel geen dialoog: **hij navigeert, en het paneel ís de detailweergave.** Dat
is het al, en geen dialoog ging dat verslaan. Op een wandtablet met Fully Kiosk blijft dat
binnen dezelfde pagina — geen nieuw venster, geen adresbalk.

**De weg terug is de zijbalk**, en dat is de valkuil van kiosk-modus: staat de zijbalk uit,
dan is er geen weg terug van het paneel naar het dashboard. De README zegt dat erbij.

Geen `browser_mod`, geen HACS-kaart, geen template-sensor: alles hierboven is kern-HA.

### 45.5 Wat deze entiteit niet is

- **Geen tweede advieskanaal.** Zij herhaalt het hoofdadvies; zij kiest niets zelf.
- **Geen alarm.** Geen notificatie, geen service, geen `hass.services.async_call` (regel 2).
- **Geen vervanging van `peak_risk`.** Die zegt "de piek dreigt" en is een meting;
  deze zegt "kijk hiernaar" en is een selectie.

### 45.6 Correctie in 0.11.1: de tegel mag zichzelf niet tegenspreken

**Gevonden door Sven op zijn eigen dashboard, 2026-08-09:** de tegel stond rood terwijl
er *"Geen actie nodig"* onder stond.

**Wat er misging, en het was niet de lijst.** `neutral_energy_situation` stond nooit
tussen de redenen. De entiteit las een *tweede* bron: elke `invalid_entity_state` in de
metrics zette hem aan, terwijl de attributen — en dus de zin op de tegel — uit het
hoofdadvies bleven komen. **De kleur kwam uit het ene object en de zin uit het andere**,
en zodra die twee het oneens waren, was het resultaat een `problem`-tegel die zijn eigen
tekst tegensprak.

Dat is precies het defect dat een knop waardeloos maakt. Bij `device_class: problem`
betekent `on` dat er iets aan de hand is; staat er dan "geen actie nodig" naast, dan leert
de bewoner binnen een week dat rood niets betekent.

**Daar kwam een tweede fout bovenop, en die was even erg.** `invalid_entity_state` dekt
twee heel verschillende gevallen, en `validators.py` zegt dat zelf al bij het eerste:

> *"Removed, renamed or gone quiet. All three are 'unavailable' rather than 'unreadable':
> nothing is wrong with how this source is configured, there is simply no current
> measurement behind it."*

Elke entiteit in Home Assistant is wel eens `unavailable` — bij een herstart, een
integratie die opnieuw laadt, een omvormer die uitvalt. Toetsen we die gebeurtenis aan de
eigen maatstaf van §45.2 — *kan iemand hier nu iets aan doen, en is het zeldzaam genoeg
dat rood nog betekenis heeft?* — dan zakt zij op beide helften.

**De regel die er nu staat, en die breder geldt dan deze entiteit:**

> **Wat de tegel aan zet, moet ook de zin leveren.**

Alleen het advies doet dat. Daarmee is de tegenspraak niet opgelost maar onmogelijk: de
kleur en de zin komen uit hetzelfde object, dus ze kunnen niet meer uiteenlopen. De
redenen zijn nu de drie uit §45.2 en verder niets.

**Wat dit kost, eerlijk opgeschreven.** Een bron die door geen enkel checklistitem
gevraagd wordt — een groepenkastmeter, een thuisbatterij — kan onleesbaar zijn zonder dat
de tegel rood wordt. Voor de bronnen die het advies wél dragen verandert er niets: die
leveren `missing_required_data`, en dat is een adviesreden mét zin. Het gat is dus smal,
en het is zichtbaar op de plek waar het thuishoort: de bronrij in het paneel, de
datakwaliteit en het logboek.

**Wil dat gat ooit dicht, dan langs de andere kant:** niet door de tegel een tweede bron
te geven, maar door de coach er iets over te laten zeggen. Dan heeft het een zin, en volgt
de tegel vanzelf. Dat is een eigen beslissing en staat hier alleen genoteerd.

**Testniveau.** `test_the_state_and_the_sentence_can_never_disagree` toetst de regel als
regel: voor een reeks situaties geldt dat `on` impliceert dat de geciteerde reden er een
is waar iemand iets aan kan doen. Een test per situatie zou dit defect niet gevangen
hebben — elke situatie die 0.11.0 toevallig toetste, had de twee het eens.


## 46. Een status zegt wat er uitkomt, niet of het formulier vol is

**Aanleiding: de eerste dag bij een vreemde woning, 2026-08-09.** De bronrij zei
*Compleet* terwijl het Overzicht zei dat er geen geldige netbron was, en de reden stond
alleen in het Home Assistant-logboek. De installateur zag twee schermen die elkaar
tegenspraken en geen enkele plek die het uitlegde.

Dat is dezelfde fout als bij de aandachtstegel (§45.6), één laag lager. Daar kwam de kleur
uit het ene object en de zin uit het andere; hier komt de status uit de *configuratie* en
de werkelijkheid uit de *meting*.

### 46.1 De regel

> **Een rij, tegel of scherm mag geen "compleet", "in orde" of "actief" heten wanneer er
> niets uitkomt. De status volgt wat er werkelijk uit de bron komt, niet of het formulier
> is ingevuld.**
>
> **En wat de status bepaalt, levert ook de uitleg.** Staat er een afwijking, dan staat de
> reden op hetzelfde scherm, in dezelfde woorden, uit dezelfde bron. Een reden die alleen
> in het logboek staat, bestaat niet voor de installateur.

Beide helften zijn nodig. De eerste voorkomt een geruststelling die niet klopt; de tweede
voorkomt dat de gebruiker met een probleem achterblijft dat hij niet kan plaatsen.

### 46.2 Dit geldt ook voor wat er nog niet is

Deze regel is met opzet niet geschreven als "de bronrij krijgt een derde toestand". Hij
geldt voor **elke status die dit product toont of nog gaat tonen**: de apparaatrij, de
sectie `Nu aangestuurd` uit §44.4, elke toekomstige tegel, en elke samenvatting die met
één woord over meerdere dingen oordeelt.

De toets bij het bouwen van zo'n status, in één vraag:

> **Kan dit woord waar zijn terwijl het onderliggende ding niets doet?** Zo ja, dan meet
> het de verkeerde zaak.

### 46.3 Wat de bronrij concreet toont

Drie toestanden, en de derde is nieuw:

| Toestand | Wanneer | Wat erbij staat |
|---|---|---|
| **Niet compleet** | de configuratie mist iets | welk veld ontbreekt |
| **Compleet, maar levert nu niets** | alles ingevuld, geen bruikbare waarde | de reden, in de woorden van de `SourceFailure` die nu al naar het logboek gaat |
| **Compleet** | er komt een waarde uit | — |

De reden komt uit dezelfde `SourceFailure` als de logboekregel. Eén bron, twee lezers.

## 47. Hoe lang een bron stil mag zijn

**Aanleiding: dezelfde avond.** Eén constante van vijftien minuten (`last_reported`)
weigerde een prijssensor die per uur publiceert en een terugleversensor die 's nachts
terecht op 0 staat. De regel deed exact wat er ontworpen was; het ontwerp nam iets over de
wereld aan dat niet voor alle bronnen geldt. Zie CLAUDE.md, achtste variant.

### 47.1 Drie vensters, elk met zijn reden

Het venster beantwoordt per soort bron één vraag: **hoe lang mag deze bron stil zijn
voordat stilte verdacht is?**

| Venster | Minuten | Voor | Waarom dit getal |
|---|---|---|---|
| **Meting** | 15 | netmeter, zonnepanelen, algemeen verbruik, apparaatvermogen | vermogen beweegt continu; een kwartier oud is geen meting van nu, en daarop handelen is precies het veiligheidsprobleem waarvoor deze regel bestaat |
| **Prijs** | 90 | actuele prijs, terugleververgoeding, prijsprognose, zonprognose | een marktprijs wordt per uur gepubliceerd en staat daarna stil; één uur plus een half uur marge voor een late publicatie. **Dit getal draagt een aanname — zie §47.5** |
| **Rustend** | 240 | thuisbatterij, en de terugleverhelft van een gescheiden meter | mag legitiem uren dezelfde waarde houden — een batterij die niets doet, een windstille nacht. Vier uur vangt een entiteit die echt gestorven is, zonder een rustige nacht een storing te noemen |

**Waarom niet één constante met uitzonderingen:** dan verdwijnt de reden. Het getal 15
was ooit gekozen voor een meter en werd stilzwijgend het antwoord voor een prijs. Drie
genoemde vensters met elk een verdediging maken zichtbaar wanneer een nieuwe bron bij geen
van drieën past.

### 47.2 De twee helften van een gescheiden meter worden apart gewogen

De **import**helft krijgt het metingsvenster, de **export**helft het rustende. Een woning
die niets teruglevert leest een constante nul, en een integratie die alleen bij verandering
schrijft laat die entiteit uren met rust. Samen gewogen trok die legitieme nul een
kerngezonde importmeting mee omlaag — en daarmee leek de hele metermodus dood, terwijl de
rij *Compleet* zei.

Wordt de exporthelft ná dat ruimere venster nog steeds geweigerd, dan noemt de melding
**de exportentiteit**: de helft die werkelijk stil is, niet degene die het goed doet.

### 47.3 Een nieuw brontype: verplicht kiezen

`SOURCE_STALE_MINUTES` dekt elk lid van `SOURCE_TYPES`, en
`test_every_source_type_has_a_staleness_window` faalt zodra dat niet meer zo is.

**Bij een nieuw brontype hoort dus één beslissing, met de reden ernaast in de mapping:**
past hij bij een meting, bij een prijs, of bij iets dat mag rusten? Past hij bij géén van
drieën, dan is dat het bewijs dat er een vierde venster nodig is — met zijn eigen
verdediging in de tabel hierboven. Wat níét mag: hem stil laten erven van een getal dat
voor iets anders gekozen is. Dat is precies hoe dit ontstond.

### 47.5 Welke aanname de negentig minuten draagt

**Verplicht op grond van §47.3 zelf**, en het stond er niet. Elk venster hoort te
zeggen *"dit geldt omdat …"* en niet *"dit is zo"*; bij de prijs stond het als
een definitie geformuleerd, en een definitie is niet te weerleggen.

> **De aanname: elke gekoppelde prijsbron schrijft haar entiteit minstens elke
> negentig minuten opnieuw.**

**Wat ervan gemeten is, en waar.** Op één woning, 2026-08-13:
`frank_energie` schrijft `sensor.current_electricity_price_all_in` precies op
het hele uur en verder niets — negen metingen over vijf minuten lieten
`last_reported` stilstaan, en tien dagen recorderhistorie bevat 257
wijzigingen, alle op minuut 0, zonder één `unknown` of `unavailable`.

**Zestig minuten stilte tegen een venster van negentig is dus dertig minuten
marge.** Een prijsintegratie die per twee uur schrijft — bijvoorbeeld omdat zij
de prijzen van morgen in blokken publiceert — loopt hier opnieuw tegenaan, op
exact dezelfde manier als de vijftien minuten dat deden: 103 logboekregels op
één klok, negentien uur achtereen, terwijl er niets aan de hand was.

**Waarom er geen semantische toets voor in de plaats komt.** Het lag voor de
hand: een prijsentiteit die de prijs van het *huidige uur* draagt is actueel,
hoe lang geleden zij ook geschreven is. Nagekeken op wat er werkelijk te zien
is:

| integratie | draagt een geldigheidsvenster? |
|---|---|
| `frank_energie` (custom) | ja — `prices: [{from, till, price}]`, 24 uurblokken, en het blok dat nu geldt draagt exact de state |
| `nordpool` (kern) | ja, maar elders — `block_prices` met `start`/`end`, plus een eigen `updated_at`-sensor |
| `tibber` (kern) | nee — alleen statistieken (`max_price`, `avg_price`, `min_price`, `peak`, `off_peak_1/2`) |
| ENTSO-e | niet te zeggen; die integratie draait hier niet en is niet ingezien |

Drie redenen om het niet te doen, en de derde is de zwaarste:

1. **De vorm verschilt per integratie** — een ander attribuut, andere sleutels,
   soms een andere entiteit. Erop lezen betekent een tabel per merk, en dat is
   precies wat `HARDWARE.md` regel 2 verbiedt.
2. **De installateur kan het niet aanwijzen.** De bronvorm kent wel
   `value_source: attribute`, maar dat wijst een *waarde* aan, geen
   geldigheidsvenster. Daar een vraag voor toevoegen vraagt iets wat de meeste
   installateurs niet weten.
3. **Het beantwoordt een andere vraag.** *"Dekt deze waarde het huidige uur?"*
   toetst of de **gegevens** het heden beschrijven; *"heeft deze entiteit
   recent iets gezegd?"* toetst of de **integratie** nog leeft. Een prijslijst
   die vandaag dekt maar waarvan de integratie om 03:00 gestorven is, komt
   glansrijk door de eerste toets. De semantische toets kan de veroudering dus
   niet vervangen — hooguit aanvullen, als extra reden om een waarde tóch te
   accepteren.

**Wat er daarom geldt:** de negentig blijft, met deze aanname erbij geschreven
zodat iemand haar kan tegenspreken. De eerste klant met een prijsbron die
minder vaak dan elk anderhalf uur schrijft, weerlegt haar.

### 47.4 Een prognose verloopt niet, maar toont zijn ouderdom

**Besluit van Sven, 2026-08-09.** De zonprognose krijgt geen venster. Voor een bewoner is
*de prognose van vanochtend* om acht uur 's avonds nog steeds de prognose van vandaag; hem
weigeren omdat hij oud is levert een lege rij op waar informatie hoort te staan.

**De voorwaarde die erbij hoort is niet optioneel:** wie de prognose toont, toont hoe oud
hij is. Zonder dat is "de zon levert vanmiddag 4 kWh" een bewering zonder houdbaarheid, en
dat is precies waar het verouderingsvenster tegen beschermde.

In `SOURCE_STALE_MINUTES` staat daarom `None` in plaats van een getal — een expliciete
keuze die de lezer dwingt te zien dat hier geen grens is, in plaats van een groot getal dat
op een grens lijkt.

## 48. Eén prijs, en het verschil tussen tonen en adviseren

**Aanleiding: Sven op zijn eigen productie-installatie, 2026-08-09.** Op het Overzicht
stond bij *Actuele energieprijs*: **"Niet van toepassing bij een vast contract"** — terwijl
hij zowel een ingevuld all-in tarief (€ 0,24171) als een werkende prijsbron had. Twee
antwoorden op de vraag "wat kost een kWh nu", en het paneel gaf er geen.

### 48.1 Eén predicaat, want het waren er vier

`import_price_now(home, snapshot)` is de enige plek die beslist welke prijs geldt. Daarvoor
stond dezelfde ternary op vier plekken: de marge in de calculator, de besparing in de
advisor, het checklistitem in de datakwaliteit, en de rij in het paneel. Dat laatste
exemplaar is wat een klant zag.

**De volgorde hangt af van het contract, en dat is de correctie van 0.13.1.** 0.13.0 liet
een meting overal winnen van een ingetypt getal, en bij een vast contract is dat verkeerd:
het Overzicht toonde € 0,306 uit een gekoppelde marktsensor aan een woning die € 0,24171
betaalt. Onschuldig voor wie weet dat het een testbron is, een onware prijs voor iedereen
daarna.

1. **Dynamisch contract: de bron, of niets.** De prijs verandert werkelijk per uur en
   alleen een meting kan dat weten. Geen terugval op het tariefveld, dat in dat formulier
   niet eens getoond wordt.
2. **Vast contract: het ingevulde tarief.** Een vast tarief is een *afspraak*, geen meting.
   Een bron kan om allerlei redenen gekoppeld zijn — de markt volgen, vergelijken, testen —
   en geen daarvan is wat deze woning betaalt.
3. **Vast contract met het veld leeg: alsnog de bron.** Een meting is beter dan een lege
   rij, en de rij zegt waar het bedrag vandaan komt.

**Wat dit kost, eerlijk:** een klant met een vast contract wiens bron werkelijk zijn eigen
tarief levert — actueler dan het ingetypte getal — krijgt toch het ingetypte getal te zien.
Dat is bewust: het product kan die bron niet onderscheiden van een marktfeed, en alleen de
bewoner weet welke van de twee het is. Zijn eigen opgave is dan het betrouwbaarste antwoord
dat er is, en zij verandert niet stilletjes. Vraagt een echte klant hierom, dan is dat een
veld op de bron ("dit is mijn werkelijke tarief") — en dat bouwen we wanneer die klant er
is, niet ervoor.

De metrics dragen naast de prijs ook `price_origin`, want een gemeten prijs houdt zichzelf
actueel en een ingetypt tarief niet — en alleen de klant weet dat zijn contract veranderd
is. De rij zegt daarom welke van de twee hij toont.

### 48.2 Tonen en adviseren zijn twee dingen

**De contractsoort zegt niets over of er een prijs is. Hij zegt iets over of die prijs
varieert.**

| | Vast contract | Dynamisch contract |
|---|---|---|
| Is er een prijs per kWh? | ja | ja |
| Wordt hij getoond? | **ja** | ja |
| Varieert hij? | nee | ja |
| Advies over goedkope/dure momenten? | **nee** | ja |
| Prijs-as in de energiescore? | **niet van toepassing** | ja |

De onderdrukking van het prijsadvies bij een vast contract blijft dus precies zoals hij
was, en om de goede reden: er is geen goedkoop moment om naartoe te schuiven. Maar dat is
een uitspraak over *variatie*, en de rij toont een *niveau*.

**De vraag die de twee uit elkaar houdt, bij elk toekomstig veld:** gaat dit over hoe hoog
iets is, of over of het verandert? Alleen het tweede hangt aan de contractsoort.

### 48.3 Wat het checklistitem nu vraagt

`_price_information_available` vroeg "een prijs, op de manier die dit contract nodig heeft"
en vraagt nu simpelweg of er een prijs is. Een woning met een prijsbron mist geen
prijsinformatie omdat zij het tariefveld leeg liet — dat was dezelfde fout als §16 over
niet-toepasselijke eisen: een gat tonen dat de klant niet kan dichten omdat het al dicht is.

### 48.4 Een bron die niets bepaalt, zegt dat

Een prijsbron bij een vast contract is compleet, wordt gelezen, en bepaalt de getoonde prijs
niet. Dat is precies het patroon van §38: iets dat om aandacht vraagt en niets doet — en
zonder tekst is het erger dan nutteloos, want het wekt de indruk dat het meetelt.

De prijsrij zegt het daarom zelf. **En de eerste formulering was te absoluut**, wat Sven
tegenhield vóór de merge: *"De gekoppelde prijsbron bepaalt dit bedrag niet"* laat een
installateur concluderen dat de rij dood gewicht is, en dan verwijdert hij haar — waarna de
volgende contractwijziging zonder prijs aankomt.

De zin draagt daarom beide helften:

> *"Vast leveringstarief, zoals ingevuld bij Woning. De gekoppelde prijsbron bepaalt dit
> bedrag niet, maar neemt het over zodra dit veld leeg is of het contract dynamisch wordt."*

Twee hele zinnen per situatie, niet één zin met een aangeplakte staart (§26); zonder
gekoppelde bron is de tweede zin er niet, in plaats van dat hij over een bron praat die er
niet is.

**Wat de zin bewust níet beweert.** Sven omschreef de bron als degene die "de prijs levert
waarmee de datakwaliteit klopt". Dat is alleen waar wanneer het tariefveld leeg is: met een
ingevuld tarief vraagt `_price_information_available` aan `import_price_now`, en die geeft
daar het tarief terug. Het checklistitem staat dan aan door het tarief, niet door de bron.
De zin claimt dus alleen wat waar is in élke situatie waarin hij verschijnt: de bron wordt
gelezen en staat klaar, meer niet.

**Het onderscheid dat hij draagt:** wat waar is over *dit bedrag* is niet waar over *deze
bron*. Een regel die één van de twee zegt terwijl de lezer de andere hoort, is precies de
faalvorm van §38.

**Nog open:** dezelfde mededeling hoort ook op de bronrij zelf te staan, waar de installateur
hem beheert. Dat wacht op de implementatie van §46.

### 48.5 De terugleverbron staat hier los van

**Leveren en terugleveren zijn losse contractdimensies.** Een woning met een vast
leveringstarief kan wel degelijk een variabele terugleververgoeding hebben — en omgekeerd.
De terugleverbron is daarom **geen informatieve bijkomstigheid** bij een vast contract: hij
is de enige manier om te weten wat een teruggeleverde kWh nu oplevert.

De regel van §48.1 gaat dus alleen over de *leveringsprijs*. `feed_in_price` houdt zijn
eigen weg: bron als die er is, anders het ingevulde bedrag, ongeacht de contractsoort.

## 49. Woning 2, tweede helft: apparaten, gereed-venster, bewonersweergave

**Bevindingenronde, 2026-08-10. Geen code in deze ronde** — dat is de afspraak van de
vreemde-woning-opzet, en zij bestaat omdat je anders gaandeweg repareert en het overzicht
verliest.

De opzet: de woning eerst in gewone taal beschrijven, met SPEC.md dicht, en pas daarna
inrichten. **Alles wat ik dan moet verzinnen is een bevinding.** De eerste helft (woning en
bronnen) leverde §47 op; dit is de tweede.

**Beukenlaan 14**, twee-onder-een-kap, driefase 25 A, veertien panelen, thuisaccu van
10 kWh, dynamisch contract. Vier apparaten: een vaatwasser die *"uiterlijk half acht"* klaar
moet zijn, een wasmachine tegen de slaapkamermuur van de kinderen die *"niet voor elf uur
's avonds en niet voor zeven uur 's ochtends"* mag draaien en klaar moet zijn *"voordat ze
om acht uur de deur uitgaan"*, een droger waar *"geen haast op zit"*, en een
warmtepompboiler waarvan de bewoner *"alleen wil kunnen zien hoeveel hij gebruikt"*.

De bevindingen staan hieronder in de volgorde waarin ik ze tegenkwam.

### 49.1 Het venster-predicaat draagt nog de betekenis van vóór de hernoeming

**De zwaarste bevinding van deze ronde, en zij raakt precies het apparaat waarvoor het
gereed-venster gebouwd is.**

De wasmachine kreeg `ready_from = 07:00`, `ready_before = 08:00`, `duration_minutes = 90`.
Dat is de woning letterlijk overgeschreven: de was mag niet vóór zevenen klaar zijn (dan
ligt hij te lang nat) en moet vóór achten klaar zijn (dan gaan ze weg). Het paneel meldt:

> *Het apparaat past niet binnen het opgegeven gereed-venster.* — severity `error`, op het
> veld `duration_minutes`.

**Die melding is onjuist, en het veld waar zij op landt is het enige getal waar de bewoner
zeker van is.** Het model rekent namelijk zelf anders:

| | Wat het model zegt (`models.py`) | Wat de validator toetst (`validators.py`) |
|---|---|---|
| `ready_before` | eindtijd; `latest_start` = `ready_before` − duur | bovengrens van een *draaivenster* |
| `ready_from` | eindtijd; `earliest_start` = `ready_from` − duur | ondergrens van datzelfde venster |
| Toets | — | `duration > ready_before − ready_from` → fout |

Onder de betekenis van het model loopt de wasmachine tussen 05:30 en 06:30 aan en is hij
tussen 07:00 en 08:00 klaar. **Dat klopt precies.** De draai-interval is
`[ready_from − duur, ready_before]`; er is niets dat ergens "in moet passen". De toets kan
onder de nieuwe betekenis nooit terecht aanslaan.

**Dit is de vierde variant uit CLAUDE.md — de hernoeming die een assertie stil omdraait —
maar nu in productiecode in plaats van in een test.** Dezelfde hernoeming
(`earliest_start`/`latest_finish` → `ready_from`/`ready_before`) waarvan CLAUDE.md al
vastlegt dat zij één assertie kantelde, heeft deze lezer óók gekanteld. Er is naar de
schrijvers gekeken en niet naar alle lezers.

**De testsuite bevestigt de oude betekenis in plaats van haar tegen te spreken**, met
docstrings die nog letterlijk in draaivenster-taal staan:

- `test_a_run_too_long_for_a_midnight_window_is_rejected`
- `test_a_run_that_does_not_fit_its_window_is_rejected` — *"A four hour cycle cannot run
  inside a two hour window"*
- `test_a_run_that_exactly_fills_its_window_is_accepted`

Alle drie groen, alle drie over een venster dat niet meer bestaat.

**De enige uitweg die de installateur heeft, is het venster oprekken** — bijvoorbeeld
`ready_from` naar 06:30 — en daarmee de eis van de bewoner veranderen om een onjuiste
controle tevreden te stellen.

### 49.2 Een tijd die niet te lezen is, wordt stil weggegooid

HA's `ha-base-time-input` zet een `<input type="number" max="23" maxlength="2">` neer voor
het uur. **`maxlength` doet niets op `type="number"`** — dat is HTML, geen fout van ons — dus
het uurvak accepteert `0730` zonder blikken of blozen. Dat is precies wat je typt wanneer je
"half acht" snel invult.

Wat er daarna gebeurt, is wél van ons. `models._as_time()` geeft bij een onmogelijk uur de
`default` terug, en dat is `None`:

```
devices/update  ready_before = "0730:00"   →   success: true, revision +1
config/get      ready_before = null
```

**Geaccepteerd, niet bewaard, niet gemeld.** De installateur vult een deadline in, het
paneel bevestigt de opslag, en het veld is leeg als hij terugkomt.

`_as_time` is een goede *round-trip*-verdediging: bij het laden van corrupte opslag is
terugvallen op niets juist. Maar hij staat óók op de **schrijfweg** vanuit de GUI, en daar
maakt hij van invoer stilte. Dat is dezelfde vraag als bij een onbekend brontype, met het
tegenovergestelde antwoord: dáár wordt in quarantaine gezet en gerapporteerd, hier
stilzwijgend gedegradeerd naar de default.

Merk op dat `_validate_time_window` een keurige melding *heeft* — *"Gebruik een geldige tijd
in de vorm uu:mm."* — maar die kan nooit afgaan, want tegen de tijd dat de validator kijkt is
de waarde al `None` en dus "niet ingevuld".

### 49.3 `home/update` met één veld wist het hele woningprofiel

Ik wilde één ontbrekend bedrag aanvullen, met de gedocumenteerde `--field`-interface:

```
domotiapp_energy/home/update  expected_revision=N  home.feed_in_markup_eur_kwh=0.02
```

`success: true`, revision +1, en **twaalf opgeslagen waarden weg**: naam, fasen,
hoofdzekering, maximaal netvermogen, contractsoort, energiebelasting, opslag, drempels. Alles
terug op default. Geen waarschuwing, geen melding, niets op het scherm behalve dat het
Overzicht ineens *"Percentage van maximum: Nog niet ingesteld"* toonde.

Het commando neemt een volledig `HomeProfile` en doet een vervanging; ontbrekende sleutels
krijgen hun default. Voor het paneel gaat dat goed omdat het paneel altijd alles meestuurt.
**Maar er is geen enkel onderscheid tussen "dit veld moet leeg worden" en "over dit veld zeg
ik niets"**, en dat is dezelfde regel als "een ontbrekende waarde is nooit een default", nu
op de schrijfweg toegepast en daar omgedraaid.

Dat ik hier inliep is geen toeval: `--field` is de gedocumenteerde interface uit CLAUDE.md
en nodigt uit om één ding te zetten. Wat voor mij geldt, geldt voor elke toekomstige client.

### 49.4 Een revisieconflict gooit een volledig ingevuld formulier weg

Ik had de vaatwasser helemaal ingevuld — naam, locatie, vermogen, energie per cyclus, duur,
gereed-venster — en drukte op Opslaan. Antwoord:

> *De configuratie is intussen ergens anders gewijzigd. Je wijzigingen zijn niet opgeslagen;
> de lijst is opnieuw geladen.*

Het dialoogvenster sloot en alles was weg. De oorzaak was terecht: ik had er zelf twee
bronnen bij gezet via de WebSocket, dus de revision was werkelijk verlopen.

**De bewaking deed haar werk; de afhandeling niet.** Een verlopen revision betekent *"jouw
basis is oud"*, niet *"jouw invoer deugt niet"*. De juiste afhandeling is: configuratie
herladen, dialoog open laten mét de ingevulde waarden, en opnieuw laten opslaan tegen de
nieuwe revision. Hoe langer het formulier, hoe duurder de huidige afhandeling — en het
apparaatformulier is het langste dat we hebben.

Dit treft elke installateur die het paneel op twee schermen open heeft, en dat is bij
DomotiTech eerder regel dan uitzondering.

### 49.5 De droger heeft geen deadline, en dat kost punten

De bewoner over de droger: *"hier zit geen haast op; als hij op woensdagmiddag draait
wanneer de zon schijnt, is dat prima."* Dus geen `ready_from`, geen `ready_before`.

`_flexible_devices_have_windows` eist minstens één grens van elk *advisable* apparaat, dus
het item `flexible_devices_have_time_window` zakt, en de datakwaliteit met tien punten —
voor een apparaat dat volledig beschreven is.

**Het formulier kan "ik heb geen eis" niet onderscheiden van "nog niet ingevuld".** Dat is de
vorm van §16: de bewoner kan dit item alleen afvinken door een deadline te verzinnen die hij
niet heeft.

**Dit ligt voor, het is niet beslist**, want er staat een goed tegenargument in de docstring
van dat predicaat zelf: het is bewust een *kwaliteits*-item, geen compleetheidseis — een
droger mét deadline krijgt beter advies. Dat is waar. De vraag is of "geen eis" een geldig
antwoord moet worden.

### 49.6 Het gereed-venster kent geen ondergrens aan de starttijd

De wasmachine mag niet draaien tussen 23:00 en 07:00 — kinderslaapkamer. Het gereed-venster
kan dat niet uitdrukken: beide velden begrenzen de **eindtijd**, geen van beide de starttijd.
Zet je `ready_from = 07:00` en `ready_before = 08:00`, dan is de vroegst toegestane start
05:30 — midden in de nacht die verboden is.

Dit is bekend terrein: de analyse bij de opzet van het gereed-venster zei al dat de vier
beperkingen **niet één mechanisme** zijn — *"mag nu niet draaien"* (geluid, aanwezigheid) is
een verbiedend venster, *"moet klaar zijn om"* is een deadline. Het gereed-venster
implementeert alleen de tweede.

**In de praktijk vangen de stille uren dit op**, en voor deze woning toevallig goed: alles
wat lawaai maakt mag 's nachts niet. Maar de stille uren staan op de **woning**, niet op het
apparaat, en de vaatwasser in deze woning mag 's nachts juist wél draaien. Dat is geen defect
maar een grens van het model; hij hoort opgeschreven te staan zodat een installateur hem niet
zelf hoeft te ontdekken.

### 49.7 Wat goed ging, en waarom dat hier staat

Een bevindingenlijst zonder dit deel geeft een vertekend beeld.

- **Het urgentie-advies wordt niet onderdrukt door de stille uren.** Getoetst vanuit de
  situatie: deadline om 15:00, duur twee uur, stille uren 12:00–14:00, het is 12:47. Het
  advies verscheen: *"Start Vaatwasser nu als hij om 15:00 klaar moet zijn."* De deadline
  wint van de voorkeur, en dat is juist.
- **Maar hij staat op `info` en onder een datakwaliteitsmelding.** Het enige tijdkritische
  ding in huis staat lager dan een aansporing om gegevens aan te vullen, en de zin geeft de
  eis terug aan de bewoner (*"als hij om 15:00 klaar moet zijn"* — dat had hij ons net
  verteld). **Fase 3 moet §43.2 terugdraaien**, en deze ronde bevestigt dat vanuit de stoel
  van de bewoner.
- **`_why_no_amount` doet precies waarvoor het gebouwd is.** Bij een vast contract zonder
  tarief zei de zin *"zonder het vaste leveringstarief — vul dat in bij Woning"*; na de
  overstap naar dynamisch met een ontbrekende terugleveropslag *"zolang de terugleverkosten
  niet zijn ingevuld — vul ze in bij Woning, of zet ze op 0 als deze aansluiting ze niet
  betaalt."* Twee redenen, twee zinnen, geen aanname.
- **De hulptekst bij *energie per cyclus* geeft een orde van grootte** (*"bijvoorbeeld 1,0
  tot 1,5 kWh"*). Dat is het verschil tussen een beantwoordbare en een onbeantwoordbare
  vraag: de bewoner kent watt en minuten, geen kWh, en vermogen × duur geeft hier ruim het
  dubbele van het juiste antwoord.
- **Het theoretisch maximum volgde de fasekeuze onmiddellijk** (17250 W bij 3 × 230 V × 25 A),
  terwijl het ingevulde maximum bleef staan. Dat is de goede kant op: het ene is een
  berekening, het andere een keuze.

### 49.8 Nog steeds open uit eerdere rondes, hier opnieuw tegengekomen

- **Het dialoogvenster scrollt niet met het wiel.** `.dialog-body` heeft `overflow-y: auto`
  en is aantoonbaar scrollbaar (`scrollHeight` 1114 tegen `clientHeight` 673), en
  programmatisch scrollen werkt; het wiel doet niets. Op het apparaatformulier is dat
  hinderlijk, want het gereed-venster staat onder de vouw.
- **De tabbalk scrollt mee weg.** Op het lange Installatie-formulier moet je eerst helemaal
  terug omhoog om van tabblad te wisselen.

### 49.9 Volgorde van afhandelen, voorgesteld

1. **§49.1** — een onjuiste `error` op de configuratie waarvoor de functie bestaat.
2. **§49.2** — stil gegevensverlies bij een normale typfout.
3. **§49.3** — stil gegevensverlies bij een normale API-aanroep.
4. **§49.4** — werk kwijt bij een conflict dat te herstellen is.
5. **§49.5 en §49.6** — beslissingen voor Sven, geen defecten.

### 49.10 De doodlopende weg bij een vast contract met een marktprijsbron

Gevonden op 2026-08-10 bij het beantwoorden van de vraag of `current_price` bij een vast
contract in de keuzelijst hoort (§48). Het antwoord is ja, en bij het uitzoeken bleek er één
combinatie te bestaan waarin die keuze nergens toe leidt:

> **Vast contract + prijsbron op marktbasis + leeg tariefveld = geen prijs, geen melding, en
> geen veld om het op te lossen.**

De drie samenstellingsvelden — energiebelasting, opslag, btw — werden op het
Woning-formulier gefilterd op *contractsoort*. Bij een vast contract stonden ze er dus niet.
Zonder die velden geeft `all_in_price_eur_kwh` `None`, dus is de bron onbruikbaar, dus is er
geen prijs. En `_validate_price_components` sloeg óók af op contractsoort, dus er kwam geen
melding.

De installateur las dan *"Nog geen prijs bekend — koppel een prijsbron of vul het vaste
leveringstarief in"* terwijl hij er één gekoppeld had.

**Dat was de stille weigering die `_validate_price_components` juist moest voorkomen**,
binnengekomen langs de andere kant: de scoping op `dynamic` was verantwoord met *"een vast
contract raadpleegt `current_price_eur_kwh` nooit"*, en dat is sinds 0.13.0 niet meer waar.

## 50. De reparatieronde van §49

**Gebouwd in 0.14.0.** De volgorde is die van Sven (2026-08-10): eerst de onterechte fout,
dan het stille gegevensverlies aan beide kanten, dan het weggegooide formulier, dan de
doodlopende weg.

### 50.1 Het venster-predicaat draagt nu de betekenis van het model (§49.1)

De toets *"past de cyclus in het venster"* is **verdwenen**, niet gecorrigeerd, want onder de
huidige betekenis kan zij nooit terecht aanslaan. Beide grenzen zijn eindtijden; het apparaat
draait over `[ready_from − duur, ready_before]` en er hoeft niets ergens in te passen.

**Wat ervoor in de plaats komt is de enige duur-versus-klok-regel die wél geldt:** een cyclus
van 24 uur of langer heeft geen starttijd op een 24-uursklok. `latest_start` trekt de duur
eraf modulo 1440, dus een programma van 25 uur met een deadline van 07:30 meldde een laatste
starttijd van 06:30 — een uur vóór het einde, zonder er iets over te zeggen. De regel wordt
alleen gesteld wanneer er een grens is om vanaf te rekenen (§16).

De drie tests die de oude betekenis vasthielden zijn vervangen. In hun plaats staat onder
meer `test_the_washing_machine_of_woning_2_validates_cleanly`, geschreven uit de woorden van
de bewoner: de was mag niet vóór 07:00 klaar zijn, moet vóór 08:00 klaar zijn, en het
programma duurt 90 minuten.

**De advisor werkte al naar de nieuwe betekenis** en zei het ook: zijn docstring merkte op
dat de validator *"checked that the duration fitted the window, not that there was still
enough of the window left"*. Er is dus omheen gewerkt in plaats van dat het is rechtgezet.
Dat is het waarschuwingsteken om te onthouden — een omweg in de ene laag is een melding over
de andere.

### 50.2 Een onleesbare tijd wordt bewaard en gemeld (§49.2)

`_as_time()` blijft wat hij is: hij gooit weg wat hij niet kan lezen, en dat is het juiste
antwoord waar een tijd *gelezen* wordt om mee te rekenen. Ernaast staat nu **`_kept_time()`**,
en die staat op de schrijfweg vanuit de GUI.

**Quarantaine in plaats van degradatie, toegepast op de schrijfweg.** Precies wat er met een
onbekend brontype gebeurt: de waarde blijft staan, en er komt een melding.

Dat maakt een zin bereikbaar die al bestond en nooit kon afgaan — *"Gebruik een geldige tijd
in de vorm uu:mm."* — omdat de waarde `None` was tegen de tijd dat de validator keek, en
`None` betekent "niet ingevuld". In de browser geverifieerd: `0730` in het uurvak levert nu
een rode regel op de rij (*"Nog niet compleet: Gebruik een geldige tijd in de vorm uu:mm."*)
en de fout op het veld zelf, waar eerst een lege deadline stond zonder één woord.

Niets stroomafwaarts loopt gevaar door de bewaarde waarde: elke lezer gaat door
`minutes_since_midnight`, die hem nog steeds weigert, dus het apparaat gedraagt zich als een
apparaat zonder die grens.

**`None` en de lege string blijven "afwezig"**, want een grens wissen moet uitdrukbaar
blijven (§32.2).

### 50.3 Een ontbrekende sleutel betekent "laat staan" (§49.3)

`home/update` en `preferences/update` **voegen nu samen**: een afwezige sleutel laat het veld
met rust, een expliciete `null` wist het.

De oude redenering — *"a partial update would silently keep a value the installer just
cleared"* — is getoetst aan wat het paneel werkelijk doet, en zij houdt geen stand. **Het
paneel wist niet door weglating.** `payload()` in zowel `home.js` als `preferences.js` bouwt
elk bewerkbaar veld op en schrijft een gewist veld als `null`, precies zodat de backend de
twee uit elkaar kan houden. Het gevaar dat voor vervanging pleitte bestond dus niet voor de
enige client die wij uitleveren, terwijl het omgekeerde gevaar echt was en een configuratie
vernietigde.

**`devices/update` en `sources/update` blijven vervangingen, en dat is geen inconsistentie.**
Het apparaatformulier wist *wél* door weglating: het laat een veld weg waar het gekozen type
geen antwoord op heeft, in plaats van een antwoord te bewaren op een vraag die nooit gesteld
is. Een test in `tests/frontend/devices.test.mjs` legt dat vast. De twee commando's
verschillen dus omdat hun formulieren verschillen, niet bij toeval.

**De testval die hier bijna toesloeg.** De eerste versie van de voorkeurentest toetste of
`quiet_hours_end` en `show_technical_explanation` overleefden — met hun *defaultwaarden*. Die
test is groen onder vervanging én onder samenvoegen, want een gewist veld komt als default
terug. Hij bevestigde het defect in plaats van het te vangen. De test zet die velden nu eerst
op niet-standaardwaarden.

### 50.4 Een revisieconflict gooit geen ingevuld formulier meer weg (§49.4)

**De revision telt de hele configuratie, niet één rij.** Een conflict zegt dus "er is iets
gewijzigd", en alle vier de formulieren lazen dat als "jouw rij is gewijzigd".

`conflictKind()` in `core/api.js` houdt de twee uit elkaar, en de drie uitkomsten krijgen elk
een eigen hele zin (§26):

| Uitkomst | Wat er gebeurt |
|---|---|
| `unrelated` | De rij is onaangeroerd, of er is nog geen rij. Invoer blijft, nieuwe revision wordt overgenomen, opnieuw opslaan werkt. |
| `same-row` | Deze rij is óók gewijzigd. Invoer blijft, en de zin zegt dat opslaan die andere wijziging vervangt. |
| `removed` | De rij is weg. Invoer blijft zichtbaar, en de zin zegt dat opslaan niet meer lukt. |

De twee inline-formulieren (Woning, Mijn voorkeuren) volgen dezelfde splitsing, met één
verschil dat uit hun vorm volgt: raakte de wijziging *deze* velden, dan laden zij wél opnieuw
— daar zou de draft bovenop de wijziging van iemand anders liggen en die verbergen.

In de browser geverifieerd met echte kliks: apparaatformulier ingevuld, van buitenaf een bron
toegevoegd, Opslaan → dialoog blijft staan met alle velden en de zin *"…maar niet aan dit
apparaat"*; tweede druk op Opslaan → *"Het apparaat 'Vaatwasser keuken' is bijgewerkt."*

### 50.5 De samenstellingsvelden volgen de marktprijs, niet het contract (§49.10)

Eén regel, op twee plekken hetzelfde:

> **Vraag de energiebelasting, de opslag en de btw precies wanneer er een marktprijs is om om
> te rekenen.**

`contractSchema()` in `home.js` toont de drie velden zodra er een `current_price`-bron op
marktbasis is, ongeacht de contractsoort; `_validate_price_components` meldt op dezelfde
voorwaarde. De twee zijn met opzet één en dezelfde vraag, want de bevinding van 2026-08-07
staat nog overeind: **een melding mag niet landen op een veld dat niet op het scherm staat.**

De melding komt ook wanneer het ingevulde tarief de bron overruled (§48.1). Dat is geen
vergissing: de bron wordt elke cyclus gelezen en is zonder deze velden niet om te rekenen,
dus zij wordt als onleesbaar gerapporteerd. Een rij die niet kan werken verdient een melding,
of haar waarde nu gewonnen zou hebben of niet.

### 50.6 Wat deze ronde bewust niet aanraakt

- **De stille uren kennen dezelfde vorm als §49.2 en zijn niet meegenomen.** Een onleesbare
  `quiet_hours_start` valt terug op de *default* (22:00), niet op `None`, en `validate_preferences`
  heeft dezelfde onbereikbare zin. De faalmodus is daar anders: het veld is verplicht en heeft
  een zinnige default, dus "bewaren en melden" zou betekenen dat de stille uren stoppen te
  gelden terwijl er een fout op het scherm staat. Dat is een keuze over wat er 's nachts
  gebeurt en die is aan Sven.
- **§49.5 en §49.6** wachten op een voorstel, op Sven's verzoek — hij wil dat zien voordat er
  gebouwd wordt.

## 51. Wanneer een apparaat helemaal niet mag draaien

**Gebouwd in 0.15.0**, uit §49.6. Sven's eigen scenario: de droger staat onder de
kinderkamer en mag 's nachts niet draaien.

### 51.1 Waarom de stille uren dit niet zijn

De stille uren dekten het geval **toevallig** af, en Sven zette de vinger op waarom dat
niet genoeg is:

> *"Dat de stille uren het toevallig opvangen is niet hetzelfde als dat ik het heb
> ingesteld. Als een bewoner zijn stille uren verkort, verdwijnt mijn bescherming."*

Dat is precies het verschil dat dit veld draagt:

| | Stille uren | Niet-draaien-venster |
|---|---|---|
| Van wie | de **bewoner** | de **installateur** |
| Wat het zegt | wanneer hij niet gestoord wil worden | wanneer dit apparaat niet mag draaien |
| Waarom | voorkeur | een eigenschap van de installatie |
| Waar | Mijn voorkeuren, één keer voor de hele woning | op het apparaat |
| Effect op advies | **stelt uit**, met een zin erbij (§42.2) | **onderdrukt**, met een zin erbij |

De laatste rij is geen detail. De stille uren zijn een *deferral*: er is een advies, en het
zegt "wacht tot na 07:00". Het verbod is harder — er komt geen advies, en de zin legt uit
waarom.

**En de rolafscherming volgt daaruit.** `no_run_from` en `no_run_until` staan bewust **niet**
in `DEVICE_OPERATION_FIELDS` en niet in `RESIDENT_FIELDS.device`. Kon de bewoner ze
verruimen, dan waren de stille uren — die hij wél mag inkorten — het enige dat nog tussen de
droger en het slapende kind stond, en dat is exact wat dit veld moet opheffen.

### 51.2 Twee grenzen, geen impliciete middernacht

Sven vroeg aanvankelijk om één grens (*"`not_before` op de starttijd"*). Dat is voorgelegd
en het is een venster geworden, om één reden: **één ondergrens vangt een nachtverbod niet.**
*"Niet starten vóór 07:00"* laat een start om 23:30 gewoon toe.

De derde optie — één grens, met een stilzwijgende bovengrens op middernacht — is afgewezen
omdat de regel dan nergens op het scherm staat. Dat is de onzichtbare aanname waar §47 over
gaat.

Een half ingevuld venster beperkt daarom **niets**, en de validator zegt het. Raden dat de
ontbrekende grens middernacht is, zou dezelfde fout zijn in het klein.

### 51.3 De hele draaitijd, niet het startmoment

**Dit is de kern van `may_run_at()` en de reden dat het een methode is en geen vergelijking.**

Een droger die 135 minuten draait en vanaf 23:00 verboden is, mag om 22:00 net zo min
starten: hij staat om kwart over twaalf nog te draaien, in de kamer waarvoor het verbod
getekend is. Alleen het startmoment toetsen zou precies het advies opleveren dat de
installateur wilde voorkomen.

Drie gevallen, en het derde is degene die je vergeet:

1. de **start** valt in het verbod;
2. de **laatste actieve minuut** valt in het verbod;
3. geen van beide, maar de draaitijd **stapt over het hele verbod heen** — start 22:00,
   verbod 23:00–07:00, tien uur lang.

**De draaitijd is `[start, start + duur)`, eind exclusief**, dezelfde afspraak die
`is_within_window` al hanteert. Een cyclus die om 23:00 *klaar* is, draait niet om 23:00.
Het eindpunt als bezet behandelen zou één minuut strenger zijn dan de waarheid, en niets op
het scherm zou dat verschil uitleggen. De tabel in
`test_when_the_dryer_may_run` zet 20:45 (mag) naast 20:46 (mag niet) om die grens vast te
leggen.

**Zonder duur wordt alleen het startmoment beoordeeld.** Dat is het veilige halve antwoord;
een lengte wordt nooit geraden (§12).

### 51.4 De categorie die hierdoor ontstaat: onmogelijk gevraagd

Een gereed-venster en een verbod kunnen elkaar uitsluiten. De wasmachine van woning 2 moet
klaar zijn tussen 07:00 en 08:00 en draait 90 minuten, dus zij moet starten tussen 05:30 en
06:30 — en elk van die minuten valt in een verbod dat tot 07:00 loopt.

Zonder melding zou dat apparaat **nooit advies krijgen** en zou niemand weten waarom. Dat is
dezelfde stille faalvorm als §49.1, en hij zou door dezelfde deur binnenkomen: een regel die
klopt met zichzelf en niet met de rest.

`_deadline_is_reachable()` loopt het startvenster minuut voor minuut af. Dat is bewust geen
gesloten formule: twee wikkelende intervallen die elkaar wel of niet raken is precies het
soort redenering dat er goed uitziet en fout is.

**Alleen een compleet gereed-venster wordt beoordeeld**, dezelfde grens die `_within_window`
in de advisor al trekt. Met alleen een deadline betekent *"klaar om 08:00"* de **volgende**
08:00, en welke dat is hangt af van wanneer je het vraagt; er is dan geen startvenster om
tegen te toetsen, en onmogelijkheid claimen zou een antwoord verzinnen op een vraag die
niemand kan beslechten (§32).

De melding noemt **beide** eisen, want de motor kan niet weten welke van de twee het
huishouden zou willen opgeven.

### 51.5 Het advies respecteert het venster en zegt waarom het zwijgt

Sven's derde eis: *"de reden zichtbaar wanneer hij een advies onderdrukt, zodat ik niet zoek
naar waarom er niets komt."*

Het normale advies **noemt het venster niet** — het filtert stil, zoals elke andere
voorwaarde. Pas wanneer er niets overblijft wordt gevraagd of het verbod de reden is, en dán
verschijnt er een eigen zin. De volgorde is die van de stille uren en om dezelfde reden:
**een verklaring mag nooit een advies verdringen waar de bewoner iets mee kan.**

De zin wijst bewust naar de installatie en niet naar Mijn voorkeuren:

> *"Er is momenteel zonneoverschot beschikbaar, maar Droger mag tussen 23:00 en 07:00 niet
> draaien. Dat is bij de installatie zo ingesteld en staat los van je stille uren. Na 07:00
> kan het weer."*

Zonder die laatste toevoeging gaat de bewoner in Mijn voorkeuren zoeken — waar de stille
uren staan — en vindt daar niets dat het verklaart.

**Geen bedrag eronder**, net als bij de stille uren: een euro naast "nu niet" leest als een
argument tegen het "niet".

### 51.6 Dit geeft `outside_allowed_window` zijn eerste lezer

`REASON_OUTSIDE_ALLOWED_WINDOW` stond sinds 0.1.0 in `REASON_CODES`, had een Nederlands
label in `labels.js`, en werd nooit uitgezonden — een van de vier codes uit die
inventarisatie. Hij beschrijft exact wat hier gebeurt, dus hij wordt gebruikt in plaats van
dat er een nieuwe bijkomt.

### 51.7 `is_within_window` is verhuisd naar `models.py`

`DeviceProfile.may_run_at` heeft hem nodig, en `validators.py` importeert al ván `models.py`.
De afhankelijkheid gaat maar één kant op, dus de klokrekenkunde hoort in de module die
onderaan ligt. `validators.py` exporteert de naam opnieuw, zodat elke bestaande aanroeper
hem vindt waar hij hem verwacht.

## 52. "Maakt niet uit" is een antwoord, geen gat

**Gebouwd in 0.16.0**, uit §49.5. De droger van woning 2, in de woorden van de bewoner:

> *"Hier zit geen haast op; als hij op woensdagmiddag draait wanneer de zon schijnt, is dat
> prima."*

Dat is een **volledige** beschrijving. Toch zakte de datakwaliteit er tien punten door, want
twee lege tijdvelden betekenden tegelijk *"ik heb geen eis"* en *"ik heb dit nog niet
ingevuld"*. De bewoner kon het item alleen afvinken door een deadline te verzinnen die hij
niet heeft — de vorm van §16, nu met een nieuw gezicht.

### 52.1 Waarom het geen bestaand veld kon zijn

Het eerste idee was `is_flexible` uitzetten — een veld dat er al staat en letterlijk *"hoeft
niet verplaatst te worden"* betekent. Dat is aantrekkelijk: lezen wat er al is in plaats van
iets toevoegen.

**Het werkt niet, en het zou de droger kapotmaken.** `is_flexible` voedt `is_advisable()`:

```python
return (device.is_usable
        and device.device_type not in NEVER_ADVISED_DEVICE_TYPES
        and device.is_flexible
        and device.effective_control_mode != CONTROL_MONITOR_ONLY)
```

Uitzetten haalt het apparaat uit het zonneoverschot-advies — precies wat de bewoner wél wil —
en uit `has_movable_load`, een voorwaarde op de **zonne-as van de energiescore**. Het cijfer
zou kunnen zakken omdat iemand een vinkje wilde halen.

**En dit project heeft die les één apparaattype eerder al geleerd.** §38.2: de thuisbatterij
is *flexibel* en heeft geen cyclus, dus die vlag kon het niet dragen en er kwam een eigen as.
*"Verplaatsbaar"* en *"heeft een deadline"* zijn onafhankelijk. De droger is dat geval
opnieuw.

### 52.2 Een schakelaar, geen derde toestand

`runs_any_time: bool`, standaard `False`, en de checklist vraagt:

> `has_ready_window or runs_any_time`

**Dat is met opzet geen enum met drie toestanden**, en de reden is migratie. Een
drietoestandsveld zou "onbeantwoord" moeten onderscheiden van "vast moment", en elk bestaand
apparaat draagt die derde toestand niet — dus zou elk apparaat mét gereed-venster ineens
incompleet zijn, of we zouden een antwoord moeten *afleiden* uit het bestaan van het venster.
Dat laatste is raden, en dit project raadt niet.

Met `or` is er niets te migreren: een apparaat met een venster slaagt zoals het altijd
slaagde, een apparaat met geen van beide zakt zoals het altijd zakte, en alleen een
expliciet antwoord is nieuw.

**Leegte telt nooit als antwoord.** Zou zij dat wel doen, dan scoort een half ingerichte
installatie vol — precies de faalvorm die de checklist moet vangen. `test_a_flexible_device_
with_no_bounds_still_misses_the_item` en `test_any_moment_is_fine_completes_the_item` staan
daarom als paar in de suite.

### 52.3 De twee tijdvelden gaan inactief, niet weg

Staat de schakelaar aan, dan worden *"Klaar uiterlijk om"* en *"Niet eerder klaar dan"*
uitgeschakeld en **hun waarden blijven bewaard**.

Verbergen zou de weg terug achter de schakelaar zetten die haar verborg — de eenrichtingsdeur
uit §38, en dezelfde regel die de contractvelden op Woning volgen: *een waarde vervalt wanneer
de nieuwe keuze haar betekenisloos maakt, en blijft wanneer zij slechts inactief is.*

### 52.4 Het is een bewonersveld

`runs_any_time` staat in `DEVICE_OPERATION_FIELDS` en in `RESIDENT_FIELDS.device`, naast
`ready_from` en `ready_before`.

**Dat moet ook wel**: de bewoner mag via `ready_before` een deadline zetten, dus hij moet ook
kunnen zeggen dat hij er geen heeft. Alleen de helft geven die een eis *toevoegt* zou "geen
eis" iets maken dat alleen de installateur kan uitdrukken — de spiegelhelft-regel.

**Het contrast met §51 is precies het punt.** `no_run_from` en `no_run_until` staan er
bewust níét in: die zeggen wanneer de machine niet mag draaien vanwege waar hij staat, en dat
is niet aan de bewoner om te verruimen. Twee velden die in hetzelfde vak staan en op de
tegenovergestelde manier beschermd zijn, omdat ze van verschillende mensen zijn.

### 52.5 Wat dit niet doet

Het apparaat blijft **volledig adviseerbaar**. Er verandert niets aan `is_advisable`, aan
`has_movable_load`, aan de energiescore of aan het overschot-advies. Er verdwijnt alleen een
deadline om naartoe te rekenen, en daarmee het urgentie-advies (§43) voor dit apparaat — wat
klopt, want er ís geen urgentie.

Het staat ook los van het niet-draaien-venster van §51: een droger kan geen deadline hebben
én 's nachts verboden zijn. Twee vragen, twee antwoorden.

## 53. Dezelfde regel, drie keer, en drie keer een andere reparatie

**Gebouwd in 0.17.0.** De opruimronde van §49.2: *een waarde die de gebruiker invulde en die
wij niet kunnen lezen, mag niet stil verdwijnen.*

De regel is één regel. **De reparatie is per veld anders, en dat is geen slordigheid maar het
gevolg van hoe het veld is opgeslagen.**

| Veld | Opgeslagen als | Wat er misging | Reparatie |
|---|---|---|---|
| `ready_from`, `ready_before` | `str` | stil `None` — leek "niet ingevuld" | **bewaren** en melden (§49.2) |
| `quiet_hours_start`, `quiet_hours_end` | `str`, verplicht | stil terug naar 22:00 — leek **beantwoord** | **bewaren** en melden |
| `net_metering_until` | `date` | stil `None` — betekent "saldeert niet" | **weigeren aan de grens** |

### 53.1 De stille uren waren erger dan het gereed-venster

Bij het gereed-venster werd een onleesbare tijd `None`, en dat oogt als een leeg veld — fout,
maar herkenbaar fout.

De stille uren vielen terug op **de default**. De bewoner typte iets, de opslag meldde succes,
en op het scherm stond `22:00` — een tijd die hij nooit heeft ingevoerd, die er volkomen
normaal uitziet, en die hij dus nooit als fout zou herkennen. Een verkeerde waarde die zich
voordoet als een antwoord is slechter dan een lege.

`_kept_time` staat daar nu, met één verschil ten opzichte van het gereed-venster: **afwezig
blijft de default.** Een bestand van vóór dit veld heeft niets gezegd, en dan is de default
juist. Alleen een waarde die er staat en niet te lezen is, blijft staan.

**Wat dat kost, en het is echt.** `_in_quiet_hours` leest een onleesbare tijd als "geen stille
uren", dus tot de typefout verholpen is kan er advies verschijnen in de uren die de bewoner
bedoelde stil te houden. Dat is bewust geaccepteerd: de fout staat op het scherm bij het veld
dat hem veroorzaakt, en deze integratie stuurt geen meldingen — het advies staat in een paneel
en een sensor, het maakt niemand wakker. De stille vervanging deed het omgekeerde: zij hield
het venster werkend en vertelde niemand dat het het verkeerde venster was.

### 53.2 Een datum kan niet in quarantaine

`net_metering_until` is opgeslagen als een `date`, geen string. Er is dus **geen plek om
"1-1-2027" te bewaren** zonder over het type te liegen, en dat is precies waarom de reparatie
hier een andere vorm heeft.

En het gat was ernstiger dan bij een tijd, want `None` betekent op dit veld niet "onbekend"
maar **"deze woning saldeert niet"**:

```python
if self.net_metering_until is None:
    return False        # geen saldering
```

Een onleesbare datum verlegde dus stilzwijgend de hele besparingsformule, met `success` en een
nieuwe revision.

**Daarom aan de grens geweigerd**, in het WebSocket-schema, met `invalid_format`. Dat kan hier
en het is eerlijk, omdat het paneel deze fout niet kán maken: zijn `selector: { date: {} }`
levert altijd ISO. Alleen een API-client kan het, en voor die client is een weigering met een
reden precies het goede antwoord.

**Op de laadweg blijft `_as_date` teruggeven wat hij kan** en `None` voor de rest. Daar is dat
juist: een corrupt bestand moet íets opleveren, en de grens die de schrijfweg bewaakt bestaat
op de laadweg niet.

> **De regel om te onthouden:** waar een veld als tekst wordt bewaard, kun je de rommel
> bewaren en melden. Waar het als een echt type wordt bewaard, moet je hem weigeren voordat
> hij binnenkomt. Dezelfde belofte aan de gebruiker, twee mechanismen.

### 53.3 `ha_check.py --merge`

Twee keer op één dag wiste dit script de helft van een rij, allebei op dezelfde manier:
`--field` nodigt uit om één ding te noemen, en `devices/update` en `sources/update`
**vervangen** de hele rij.

Dat vervangen is geen defect en blijft (§49.3): het apparaatformulier wist een veld juist
dóór het weg te laten, omdat een veld waar het gekozen type geen antwoord op heeft geen
opgeslagen antwoord mag houden. Het script hoort zich aan te passen, niet de API.

- **`--merge`** haalt de opgeslagen rij op, legt de genoemde velden erover en stuurt het
  geheel. Hij meldt hoeveel velden hij las en welke er veranderden, zodat je ziet dat er niets
  is weggevallen. Vindt hij de rij niet, dan weigert hij — per ongeluk een rij aanmaken uit een
  commando dat er één wilde wijzigen is erger dan een foutmelding.
- **Zonder `--merge`** waarschuwt hij, ook bij `--dry-run` — juist daar, want dat is wat je
  draait om een aanroep te controleren vóórdat je hem afvuurt.

`home/update` en `preferences/update` staan er niet bij: die voegen sinds §49.3 samen.

## 54. Woning 3: het rijtjeshuis met de laadpaal

**Bevindingenronde, 2026-08-10. Geen code in deze ronde.** Zelfde opzet als woning 2: de
woning eerst in gewone taal beschreven met SPEC.md dicht, en pas daarna ingericht. Alles wat
ik daarna moest verzinnen is een bevinding.

**Beukenhof 7**, rijtjeshuis 1998, eenfase 35 A (verzwaard voor de laadpaal), twaalf panelen
via een Growatt-cloudkoppeling, een **Easee-laadpaal** met een Volvo EX30, een dynamisch
contract bij Tibber, geen batterij. Wasmachine, droger en vaatwasser in de bijkeuken, en een
vijftien jaar oude vrieskist in de garage die alleen gemeten wordt.

**Deze woning stond als eerste op de lijst omdat zij het dichtst bij Sven's eerste klant
staat**, en omdat het laadpaalpad (§34) nog nooit op een echte installatie was gelopen. Die
verwachting is uitgekomen: er zitten **twee structurele gaten** in, en allebei raken zij de
manier waarop vrijwel iedereen met een auto en een baan laadt.

De entiteiten dragen de namen die de integraties zelf geven — `Easee home EH845213 power`,
`Growatt MIN 5000TL X output power`, `Tibber electricity price Beukenhof 7` — want een
installateur hernoemt die niet: "dan werkt de update niet meer".

### 54.1 De eerste instructie wijst naar een tabblad dat niet bestaat

Verse installatie, Overzicht, nog niets gekoppeld:

> *"Er zijn nog geen energiebronnen gekoppeld. Ga naar het tabblad
> **Energiebronnen** om je slimme meter of omvormer te koppelen."*

De tabbladen zijn Overzicht, Energiecoach, Apparaten, Mijn voorkeuren,
Installatie en Logboek. **Energiebronnen is een sectie binnen Installatie**,
geen tabblad.

Dit stond al op de lijst na de eerste productie-installatie en is blijven
staan. Wat de woningronde toevoegt is *waar* het staat: dit is de allereerste
zin die een nieuwe installateur leest, op een scherm waar verder niets te doen
is. De eerste aanwijzing van het product wijst naar iets dat er niet is.

### 54.2 De eerste klik na een herlaadbeurt registreert niet

Drie keer opgemerkt, ook in woning 2: na een `location.href` of een harde
herlaadbeurt doet de eerste klik op een tabblad niets, de tweede wel. Klein,
maar een installateur die het paneel voor het eerst opent doet precies dat.

### 54.3 De laadpaalvragen passen zich aan, en dat is goed

`nominal_power_w` heet hier *"Maximaal laadvermogen"*, `energy_per_cycle_kwh`
*"Energie per laadsessie"*, `duration_minutes` *"Duur van een laadsessie"*.
Het formulier spreekt de taal van het apparaat. Dat werkt.

### 54.4 De zin van de bewoner heeft geen plek in het formulier

**De zwaarste bevinding tot nu toe, en waarschijnlijk functie-groot.**

Wat de bewoner zegt:

> *"Laad hem vol als ik morgen weg moet, en anders alleen wanneer het gunstig
> is."*

Hij rijdt vier dagen per week en vertrekt dan om 06:15; op die dagen moet de
auto **vol**. Op de andere dagen mag de paal wachten op zon of een lage prijs,
en 60% is prima.

Wat het formulier kan:

| Wat hij wil | Wat er is | Past het? |
|---|---|---|
| deadline op werkdagen | `ready_before` | ja, maar **elke dag** |
| geen deadline op de andere dagen | `runs_any_time` | ja, maar **elke dag** |
| alleen op deze dagen adviseren | `days_of_week` | ja — maar dan krijgt hij op de overige dagen **helemaal geen advies** |

De drie sluiten elkaar uit. `days_of_week` beperkt wanneer het apparaat
überhaupt geadviseerd mag worden, dus "maandag t/m donderdag" betekent dat de
paal in het weekend **niets** meer zegt — terwijl de bewoner juist dan het
zonneadvies wil.

**Er is geen manier om te zeggen: op deze dagen een deadline, op die dagen
niet.** En dat is niet een randgeval van deze woning: het is hoe vrijwel
iedereen met een auto en een baan laadt.

### 54.5 "Energie per laadsessie" is voor een auto geen vast getal

Een vaatwasser gebruikt elke keer ongeveer evenveel. Een laadsessie is de ene
dag 8 kWh en de andere 45, afhankelijk van hoe leeg hij thuiskomt.

Het formulier vraagt één getal. Tegelijk is er een koppeling *Batterijniveau*
— en die staat hier op `input_number.volvo_ex30_battery_level`, dus het
systeem kán weten hoe leeg de auto is. Wat de installateur invult is dus een
schatting van iets dat live beschikbaar is.

Ik weet niet of die koppeling gelezen wordt; dat is precies het soort vraag
dat SPEC.md dicht houden oplevert. **Bevinding: als installateur kan ik niet
zien of dit getal nog nodig is wanneer ik het batterijniveau koppel.**

### 54.6 Twee plekken beantwoorden "in welke eenheid meet deze sensor?" verschillend

**De negende variant, in het wild, één dag nadat we hem opschreven.**

De Easee rapporteert in kW. Dat gaat goed — `_device_powers` in de calculator leest de
eenheid **van de entiteit** en accepteert alleen `W` of `kW`.

Maar een **bron** doet het omgekeerde, en zegt dat met zoveel woorden op het scherm:

> *"De eenheid waarin deze entiteit meet. Zoals jij hem vaststelt: de eenheid van de
> entiteit zelf wordt nooit gebruikt om te converteren."*

Dus:

| | Waar de eenheid vandaan komt |
|---|---|
| Energiebron (`grid_meter`, `solar`, …) | de installateur kiest hem; die van de entiteit wordt **nooit** gebruikt |
| Apparaatkoppeling (`power_entity`) | **van de entiteit**, en zonder eenheid wordt de sensor overgeslagen |

Beide zijn op zichzelf verdedigbaar — geen van tweeën raadt. Maar het is dezelfde vraag met
twee antwoorden, en dat is precies de vorm die geen enkele test kan zien: elke kant is groen
op zijn eigen voorwaarden.

**Waarom het uitmaakt voor deze woning:** de installateur die net bij Energiebronnen heeft
gelezen dat wij de eenheid van de entiteit nooit gebruiken, koppelt даarna een laadpaal die
in kW rapporteert — en moet maar aannemen dat het daar wél goed gaat. Er staat geen woord
over.

**Niet meteen repareren.** Welke van de twee regels de juiste is, is een ontwerpvraag: de
bronregel bestaat omdat meterintegraties liegen over hun eenheid, de apparaatregel omdat een
extra veld op elk apparaat te duur leek. Ze horen alleen niet zwijgend naast elkaar te staan.

### 54.7 Een laadpaal wordt behandeld als een vaatwasser: alles of niets

**De tweede structurele bevinding, en misschien de belangrijkste van deze woning.**

Situatie: 2100 W zonneoverschot, auto op 42%, bewoner wil laden "wanneer het gunstig is".

Wat het advies zegt:

> *"Er is momenteel zonneoverschot beschikbaar. Dit is een gunstig moment om **Wasmachine**
> te gebruiken."*

De laadpaal wordt niet genoemd. De reden staat in `_fits_in_surplus`:

```python
return device.nominal_power_w <= surplus     # 3680 > 2100 -> valt af
```

Voor een wasmachine klopt die regel volkomen: die draait op 2100 W of hij draait niet, en
hem adviseren op 600 W overschot zou 1500 W van het net "je eigen overschot" noemen. Dat is
precies het defect dat deze regel ooit repareerde.

**Maar een laadpaal moduleert.** Een Easee laadt op 6, 8, 10 of 16 ampère. Met 2100 W
overschot kun je uitstekend op ongeveer 9 A laden — dat is exact wat een zonneladende
installatie de hele dag doet. De installateur heeft de paal zelfs op 16 A begrensd, dus het
begrip "minder dan vol vermogen" zit al in deze woning.

Het gevolg: **in de meest voorkomende Nederlandse situatie — auto thuis, panelen leveren
minder dan het maximale laadvermogen — zwijgt de paal.** En dat is precies waar de bewoner
hem voor wil.

De regel is niet fout; hij is te grof voor één apparaattype. Een apparaat dat zijn vermogen
kan aanpassen hoort te worden beoordeeld op *een* bruikbaar vermogen, niet op zijn maximum.

**Ook dit is een ontwerpbeslissing en geen reparatie.** Hij raakt `_fits_in_surplus`, het
begrip "past dit apparaat", en waarschijnlijk een minimum-laadvermogen (onder ~6 A laadt een
auto niet). Niet in deze ronde bouwen.

### 54.8 "Apparaten die nu draaien: 1" is permanent de vrieskist

Het Overzicht toont een teller. In deze woning staat er `1`, en dat blijft zo — het is de
vrieskist in de garage, die per definitie altijd aanstaat.

De teller is technisch juist en vertelt de bewoner niets. Erger: hij ziet er informatief uit,
dus hij zal er een keer naar kijken en concluderen dat er iets draait wat hij kan uitzetten.

§37 zegt dat sluimerverbruik niet als draaiend telt, en 78 W is inderdaad geen sluimerstand.
Het onderscheid dat hier ontbreekt is een ander: **een continue last tegenover een cyclus.**
Een vrieskist "draait" niet in de zin waarin een wasmachine draait.

### 54.9 De rij van een alleen-gemeten apparaat zegt het twee keer

> *"Overig, alleen meten · Garage · Alleen monitoren"*

Het type zegt al "alleen meten", en het bedieningsniveau zegt daarna "alleen monitoren".
Twee formuleringen van hetzelfde, naast elkaar. §38.3 heeft deze regel al een keer opgeruimd
(toen stond er ook nog een prioriteit bij); dit is wat er van over is.

Klein, en het staat op de rij die een installateur het vaakst voorbij scrollt.

### 54.10 Wat goed ging

- **De laadpaalvragen spreken de taal van het apparaat**: "Maximaal laadvermogen", "Energie
  per laadsessie", "Duur van een laadsessie".
- **De Easee rapporteert in kW en dat gaat vanzelf goed** — `_device_powers` accepteert `W`
  en `kW` en rekent om. Dat het tegelijk een inconsistentie blootlegt (bevinding 6) doet daar
  niets aan af: dit pad werkt.
- **Lange, Engelse integratienamen zijn geen enkel probleem.** `Easee home EH845213 power`,
  `Growatt MIN 5000TL X output power`, `Tibber electricity price Beukenhof 7` — allemaal
  gevonden via de entiteitkiezer, geen enkele aanname over de naam.
- **De datakwaliteit haalde 100** zonder dat ik iets hoefde te verzinnen: `runs_any_time` op
  de drie huishoudelijke apparaten en een deadline op de laadpaal was genoeg. Dat is §52 die
  in de eerste vreemde woning na zijn bouw meteen zijn werk doet.
- **`monitor_only` op de vrieskist doet precies wat het moet**: geen advies, wel het
  vermogen op de rij.

## 55. Voorstel: een deadline die niet elke dag geldt

Uit bevinding §54.4. **Op papier, vóór er code komt** — Sven's voorwaarde, omdat dit het
datamodel raakt en dat duur is om terug te draaien. Zijn stand: een voorlopig ja.

Naar aanleiding van bevinding 4, woning 3. **Op papier, vóór er code komt.**

### 55.0 Eerst een correctie op de vraagstelling

> *"`days_of_week` doet nu twee dingen: wanneer mag hij draaien, en wanneer geldt de
> deadline."*

**Dat is niet wat het doet, en het verschil bepaalt de oplossing.**

`days_of_week` heeft precies één lezer, `_allowed_today`, en die wordt op twee plaatsen
aangeroepen: in de kandidatenfilter voor het zonne- en prijsadvies, én in het
urgentie-advies. Beide vragen hetzelfde: *doet dit apparaat vandaag mee?*

Het echte probleem zit een laag dieper:

> **De deadline heeft geen eigen dagdimensie, dus hij erft die van `days_of_week`.**

`ready_before` geldt op elke dag dat het apparaat meedoet. Meedoen impliceert de deadline;
er is geen manier om het ene te hebben zonder het andere. Dat is de aanname die je aanwees —
alleen zit zij niet in `days_of_week` maar in het **ontbreken** van een dagdimensie op het
gereed-venster.

Dat is goed nieuws: een ontbrekende dimensie is goedkoper te repareren dan een veld dat twee
banen heeft.

### 55.1 Optie A — meerdere vensters per apparaat

`DeviceProfile.schedules: list[Schedule]`, elk met eigen dagen, gereed-venster en
`runs_any_time`.

**Dit is de deur die niet meer dichtgaat, en ik raad hem af.**

| Wat het kost | Waarom het blijft kosten |
|---|---|
| Elke lezer wordt "welke regel geldt nu?" | `latest_start`, `earliest_start`, `has_ready_window`, `may_run_at`, `_within_window`, de checklist, het urgentie-advies, de validator |
| Overlappende regels worden mogelijk | nieuwe validatie, nieuwe zin, nieuwe randgevallen |
| Het formulier krijgt een herhaalbaar blok | een UI-patroon dat nergens anders in dit paneel bestaat |
| `devices/set_operation` moet een lijst toestaan | de rechtengrens is nu per veld; die wordt per regel-per-veld |
| Migratie van elk bestaand apparaat | naar een lijst van één |

En het permanente deel: **elke toekomstige vraag over een apparaat wordt "voor welke
regel?"**. De checklistvraag *"heeft dit apparaat een tijdvenster"* wordt *"hebben al zijn
regels er een"*. Dat is precies de soort betekenisverschuiving die §49.1 zo duur maakte.

Voor één woning met één laadpaal is dat een onevenredige prijs.

### 55.2 Optie B — een dagenlijst op de deadline (het voorstel)

Eén nieuw optioneel veld:

```
ready_days: list[int] | None = None      # None = elke dag dat het apparaat meedoet
```

De betekenis, en de twee blijven expliciet gescheiden:

| Veld | Vraag |
|---|---|
| `days_of_week` | Op welke dagen doet dit apparaat mee? |
| `ready_days` | Op welke van die dagen geldt de deadline? |

De zin van de bewoner wordt dan letterlijk invulbaar:

```
days_of_week = ma t/m zo        (de paal doet elke dag mee)
ready_before = 06:15            (dan moet hij vol zijn)
ready_days   = ma, di, wo, do   (maar alleen op werkdagen)
```

Op vrijdag t/m zondag is de paal gewoon kandidaat voor zonne- en prijsadvies, en er is geen
deadline — dus geen urgentie-advies en geen vensterbeperking. Dat is exact wat hij vroeg.

### Wat er verandert, en het is minder dan het lijkt

**Twee runtime-lezers**, en beide hebben de weekdag al bij de hand:

- `_within_window` in de advisor — heeft `context`;
- `latest_start_minutes` in `scheduling.py`, die het urgentie-advies voedt — idem.

**Twee statische lezers veranderen niet:**

- `has_ready_window` (checklist) vraagt *is er iets gezegd*, en dat is dagonafhankelijk;
- `_deadline_is_reachable` (validator) toetst interne consistentie, en die moet op elke dag
  waarop de deadline geldt kloppen — dus die redenering blijft staan.

**Geen migratie.** `None` betekent "elke dag dat het apparaat meedoet", wat exact het
huidige gedrag is. Elk bestaand apparaat blijft doen wat het deed.

### Wat er bewaakt moet worden

1. **`ready_days` buiten `days_of_week`** is een deadline op een dag dat het apparaat niet
   mag draaien. Eigen melding; niet stilzwijgend snijden.
2. **`ready_days` leeg.** `_as_days_of_week` maakt van een lege lijst "alle dagen" — hier zou
   dat het omgekeerde betekenen van wat de installateur aanklikte. Dit veld moet een lege
   lijst dus **niet** normaliseren maar weigeren, of `None` blijven. Let op: dit is precies
   de valkuil waar een gedeelde helper hem in trekt.
3. **Twee manieren om hetzelfde te zeggen.** `runs_any_time = true` en `ready_days = []`
   zouden allebei "nooit een deadline" betekenen. Voorstel: `runs_any_time` schakelt
   `ready_days` net zo uit als het de tijdvelden uitschakelt, zodat er één weg is.
4. **Bewonersveld**, naast `ready_before` — de spiegelhelft-regel van §52: hij mag een
   deadline zetten, dus hij mag zeggen wanneer die geldt.

### 55.3 Optie C — twee apparaatrijen voor één laadpaal

Geen modelwijziging: "Laadpaal werkdagen" en "Laadpaal weekend", beide aan dezelfde entiteit.

**Afgeraden.** Twee rijen voor één ding tellen twee keer in de datakwaliteit en in
`has_movable_load`, tonen allebei hetzelfde vermogen, en spreken de afspraak van §34 tegen
dat er één auto per paal is. Het is de goedkoopste optie in code en de duurste op het scherm.

### 55.4 Wat er sindsdien bij is gekomen

Dit voorstel is geschreven halverwege de laadpaal, en Sven hield het bewust op een
**voorlopig** ja tot de ronde af was — juist om niet twee keer over hetzelfde datamodel te
beslissen. Dat was de goede volgorde, want de tweede helft leverde §54.7 op: **een laadpaal
wordt beoordeeld op zijn maximale vermogen, terwijl hij moduleert.**

De twee gaten staan los van elkaar en raken verschillende code:

| | Waar het zit | Wat het is |
|---|---|---|
| §54.4 | het datamodel — de deadline mist een dagdimensie | `ready_days` |
| §54.7 | de adviesregel — `_fits_in_surplus` kent geen regelbaar apparaat | een eigen beslissing |

**Ze hoeven dus niet samen beslist te worden, en waarschijnlijk ook niet samen gebouwd.**
Maar ze komen wel samen uit bij dezelfde bewoner: hij wil dat de auto op werkdagen vol is
(§54.4) en dat de paal in het weekend meelift op de zon (§54.7). Wordt er maar één van de
twee gebouwd, dan is zijn zin nog steeds niet waar te maken.

**De valstrik uit §55.2 blijft gelden, en Sven vroeg hem expliciet vast te leggen:**
`_as_days_of_week` maakt van een lege lijst "alle dagen". Voor `days_of_week` is dat juist —
"geen enkele dag" zou een apparaat betekenen dat nooit mag draaien, en daar is uitschakelen
voor. Voor `ready_days` zou diezelfde normalisatie het **omgekeerde** betekenen van wat de
installateur aanklikte: hij vinkt alle dagen uit om te zeggen "nooit een deadline", en krijgt
"elke dag een deadline" terug. Die helper mag hier niet hergebruikt worden.

## 56. Ontwerp: de laadpaal die meebeweegt met de zon

**Ontwerp, nog niet gebouwd.** Sven's voorwaarde: eerst op papier. Het lost §54.4 en §54.7
samen op, want los van elkaar lossen ze niets op — met alleen `ready_days` kan de bewoner zijn
zin invullen en krijgt hij nog steeds geen advies; met alleen modulatie krijgt hij op zaterdag
advies over een deadline die er niet is.

### 56.1 Deel één: `ready_days`

Het voorstel van §55 ongewijzigd:

```
ready_days: list[int] | None = None      # None = elke dag dat het apparaat meedoet
```

| Veld | Vraag |
|---|---|
| `days_of_week` | Op welke dagen doet dit apparaat mee? |
| `ready_days` | Op welke van die dagen geldt de deadline? |

Twee runtime-lezers krijgen er een dagcontrole bij (`_within_window` en
`latest_start_minutes`, allebei met de weekdag al bij de hand); `has_ready_window` en
`_deadline_is_reachable` blijven ongewijzigd, want die vragen iets dagonafhankelijks. Geen
migratie: `None` is het huidige gedrag.

**De valstrik, en zij is de reden dat dit veld niet met `_as_days_of_week` gelezen mag
worden.** Die helper maakt van een lege lijst "alle dagen". Voor `days_of_week` is dat juist —
"geen enkele dag" zou een apparaat betekenen dat nooit mag draaien, en daar is uitschakelen
voor. Voor `ready_days` betekent diezelfde normalisatie **het omgekeerde van wat de
installateur aanklikte**: hij vinkt alles uit om te zeggen *"nooit een deadline"* en krijgt
*"elke dag een deadline"* terug.

Concreet: `ready_days` krijgt zijn eigen lezer die `None` teruggeeft bij afwezig, de gesorteerde
lijst bij een geldige, en **een lege lijst weigert** — dat laatste is `runs_any_time`, en dat
veld bestaat al.

### 56.2 Deel twee: welk veld zegt dat een apparaat moduleert

**Een eigenschap van het apparaat, met een standaard per type.** Dat is Sven's derde vraag, en
het antwoord volgt uit zijn eigen voorbeeld: een Easee moduleert, een oudere paal misschien
niet. Het type weet het meestal, het apparaat weet het zeker.

Dat patroon bestaat al twee keer in dit model — `is_noisy` en `is_flexible` staan op
`TYPE_DEFAULT` tot iemand kiest, en `__post_init__` lost ze op uit het type. Hetzelfde:

```
can_modulate: bool = TYPE_DEFAULT        # standaard True voor ev_charger
min_power_w:  float | None = None        # geen standaard, nooit geraden
```

**Waarom `min_power_w` géén standaard krijgt.** Voor een laadpaal is 6 ampère de norm
(IEC 61851 laat niet lager toe), maar dat is 1380 W op één fase en 4140 W op drie. Het hangt
dus aan de aansluiting, niet aan het type. Raden zou hier precies de fout zijn die §15 verbiedt.
De hulptekst noemt de 6 ampère en het rekensommetje; het getal komt van de installateur.

**En dat maakt de overgang vanzelf veilig.** `can_modulate` mag gerust standaard aan voor een
laadpaal, want zonder `min_power_w` verandert er niets: het apparaat wordt dan behandeld als
niet-modulerend. Een bestaande installatie ziet dus geen gedragsverandering tot de installateur
het minimum invult.

`min_power_w` wordt alleen gevraagd wanneer `can_modulate` aanstaat — dezelfde regel als de
prijssamenstelling die de marktprijs volgt (§49.10): vraag het waar het gebruikt wordt.

### 56.3 De regel die `nominal_power_w <= surplus` vervangt

```
niet-modulerend:   nominal_power_w <= surplus          (ongewijzigd)
modulerend:        min_power_w     <= surplus
```

en het vermogen waarmee stroomafwaarts gerekend wordt:

```
bruikbaar vermogen = min(nominal_power_w, surplus)     modulerend
                   = nominal_power_w                   niet-modulerend
```

**Klopt de oude regel nog voor de apparaten waarvoor zij juist was?** Ja, en dat is met opzet
de vorm van de wijziging: hij is *additief* en hangt aan een schakelaar die voor elk bestaand
apparaattype uit staat. Een wasmachine van 2100 W op 600 W overschot valt af zoals hij altijd
afviel — dat defect ("benut je zonneoverschot" op een netimport van 1500 W) blijft gerepareerd.

De reden dat het bij een laadpaal anders ligt, in één zin: **een wasmachine kan het overschot
niet aannemen, een laadpaal wel.**

### 56.4 De geschatte besparing: wat er in dat veld hoort te staan

`_solar_savings` rekent `energy_per_cycle_kwh × marge`. Er komt geen vermogen in voor — en
dat is precies het probleem, want de formule **blijft rekenen** over een cyclus die voor een
modulerende paal niet bestaat. `energy_per_cycle_kwh = 25` levert dan "€ 1,20" op voor een
advies dat over de eerstvolgende twintig minuten zon gaat. Een getal dat plausibel oogt en
iets belooft wat niet gebeurt, is gevaarlijker dan een fout die opvalt.

**Het antwoord is niet "welke van drie vormen leest het beste", maar volgt uit wie dat veld
leest.** `estimated_savings_eur` heeft een tweede lezer naast het scherm:

```python
# _filter_by_savings
if item.estimated_savings_eur is None
   or item.estimated_savings_eur <= 0
   or item.estimated_savings_eur >= minimum      # min_savings_eur
```

Het wordt vergeleken met de drempel `min_savings_eur`, die de bewoner instelt en die per
*advies* geldt. Een bedrag per uur in dat veld wordt dus tegen een drempel per cyclus gelegd,
en een paal die € 0,12 per uur oplevert verdwijnt bij een drempel van € 0,25 — **niet omdat
het de moeite niet waard is, maar omdat het getal op een andere schaal staat.** Dat is de
negende variant nog eens: één veld, twee betekenissen, en geen test die het ziet.

**Het besluit:**

| | `estimated_savings_eur` | Eigen veld | Zin |
|---|---|---|---|
| Niet-modulerend | de hele cyclus | — | *"levert ongeveer € 0,34 op"* |
| Modulerend | **leeg** | `savings_rate_eur_per_hour` | *"levert ongeveer € 0,12 per uur op zolang dit overschot er is"* |

Drie eigenschappen van dat besluit, en ze horen alle drie bij elkaar:

1. **Leeg is hier geen gebrek maar het juiste antwoord.** Het advies "laad nu op wat er over
   is" heeft geen begrensde omvang, dus er ís geen totaalbedrag. Dat veld leeg laten is
   dezelfde eerlijkheid als een terugleverkost die niet ingevuld is (§16): onbekend en nul
   zijn verschillende uitspraken.
2. **Het advies wordt daardoor nooit weggefilterd.** `_filter_by_savings` laat advies zonder
   berekenbare besparing met opzet staan, en dat is hier precies goed: een drempel per cyclus
   mag niet beslissen over een advies dat per uur loopt.
3. **Het tarief krijgt een eigen veld en een eigen hele zin** (§26), zodat de twee bedragen
   nooit in dezelfde regel of dezelfde vergelijking terechtkomen. € 1,20 en € 0,12 zijn
   allebei waar en beantwoorden een andere vraag.

De rekensom voor het tarief: `bruikbaar_vermogen_kW × marge`, met het bruikbare vermogen uit
§56.3. **Wat er níét verandert:** de marge zelf
(`self_consumption_margin_eur_kwh`) en alles wat §35.4d daarover zegt. Alleen de schaal en de
plaats veranderen.

### 56.5 De laadduur: die blijft, en dat is het goede antwoord

Sven's vierde vraag. De duur was al een schatting en hangt nu af van een vermogen dat varieert.

**Toch verandert er niets, en de reden is dat de twee adviezen verschillende vragen stellen:**

- Het **urgentie-advies** vraagt: *moet ik nu starten om om 06:15 vol te zijn?* Daar mag je niet
  op zon rekenen — het is drie uur 's nachts. De juiste aanname is **vol vermogen**, en dat is
  precies wat `duration_minutes` vandaag beschrijft. Modulatie hoort daar niet in.
- Het **overschot-advies** vraagt: *is dit een gunstig moment?* Dat advies heeft geen deadline
  en dus geen duur nodig.

Modulatie raakt dus alleen het tweede, en de duur alleen het eerste. Ze komen niet bij elkaar.

**Eén grens die hierdoor zichtbaar wordt en die ik niet dichtmaak.** Laadt de bewoner de hele
middag langzaam op zon, dan is de auto 's avonds voller dan het urgentie-advies denkt — dat
rekent met `duration_minutes` alsof er nog niets in zit. Dat is niet nieuw en niet van
modulatie: het is dat het systeem geen voortgang bijhoudt. Dat is fase 3 (de gereed-vlag) en
§34.8 (de duur als functie van de laadtoestand, met `battery_level_entity` als invoer).

**Dit ontwerp heeft dat niet nodig en leunt er niet op.** `required_duration_minutes` neemt de
metrics al aan, precies zodat die tak er later bij kan zonder dat het advies verbouwd wordt.

### 56.6 Wat dit verder raakt

- **`has_movable_load`** wordt vaker waar: een modulerende paal past op elk overschot boven
  zijn minimum. Dat is juist — de zonne-as van de energiescore hoort te tellen bij een woning
  die haar overschot werkelijk kan gebruiken.
- **De datakwaliteit** verandert niet. `min_power_w` is geen compleetheidseis; zonder dat getal
  werkt het apparaat zoals het altijd werkte.
- **De rechten:** `can_modulate` en `min_power_w` zijn **installateursvelden**. Ze beschrijven
  wat de hardware kan, niet wat de bewoner wil — dezelfde grens als bij `no_run_from` (§51), en
  het spiegelbeeld van `ready_days`, dat naast `ready_before` van de bewoner is.

### 56.7 Volgorde van bouwen, voorgesteld

1. **`ready_days`** — klein, geïsoleerd, geen nieuwe begrippen.
2. **`can_modulate` + `min_power_w` + de fit-regel** — de gedragswijziging, achter een
   schakelaar die zonder het tweede veld niets doet.
3. **Het bedrag per uur** — apart, want het voegt een tweede soort getal toe aan het scherm en
   dat verdient zijn eigen verificatie in de browser.

Drie stappen, elk apart te mergen en elk apart terug te draaien.

### 56.8 Het uurbedrag dat niet te berekenen is, legt uit waarom

**Gevonden bij 0.20.0, bewust daar niet opgelost** (besluit Sven, 2026-08-10),
**gebouwd in 0.22.0**.

Een modulerend apparaat waarvan `_solar_savings_rate` `None` teruggeeft — geen
leesbaar vermogen, of geen `self_consumption_margin_eur_kwh` omdat de
prijsinformatie ontbreekt — toonde sinds 0.20.0 geen van beide bedragrijen, en
`_surplus_message` zei er niets over. De niet-modulerende tak deed dat wél: die
noemt via `_why_no_amount` het veld dat de som stopte.

**Waarom dat gat niet met `_why_no_amount` gedicht mocht worden.** Die functie
begon bij `energy_per_cycle_kwh`, en dat is precies het veld dat een modulerende
paal niet gebruikt. Hem daar aanroepen levert de fout op die de docstring van
`_surplus_message` al beschrijft: een paal met een prima tarief die de
installateur naar een veld stuurt dat hij net had ingevuld. Dat is in 0.18.0 één
keer gebeurd en in de browser gevonden.

**Wat er gebouwd is.** `_why_no_amount` is gesplitst langs de scheidslijn die de
twee bedragen al hadden: de eigen term van het apparaat, en de marge die ze delen.

| Functie | Beantwoordt | Eigen term |
|---|---|---|
| `_why_no_amount` | waarom er geen totaal is | `energy_per_cycle_kwh` |
| `_why_no_rate` | waarom er geen bedrag per uur is | `usable_power_w` |
| `_why_no_margin` | waarom geen van beide te maken is | importprijs, terugleververgoeding, terugleverkosten |

De marge-zinnen zijn woord voor woord hergebruikt, en **dat is het punt van de
splitsing en geen kortere weg**: een ontbrekende importprijs stopt beide sommen om
dezelfde reden en wordt op dezelfde plek ingevuld, dus de schaal van het bedrag
verandert niets aan wat de installateur moet doen. Eén antwoord, zodat de twee
takken het nooit oneens kunnen worden over waar hij heen moet — de negende variant,
vooraf gesteld in plaats van achteraf gevonden.

De volgorde binnen `_why_no_margin` volgt `self_consumption_margin` in de
calculator, zodat de zin de term noemt die de samenstelling werkelijk stopte.

**Wat er onderweg bijkwam: het veld heet niet overal hetzelfde.** Het
apparaatformulier vraagt een laadpaal om *Energie per laadsessie* en *Maximaal
laadvermogen*, omdat een auto geen cyclus heeft; elk ander apparaat krijgt
*Energie per cyclus* en *Nominaal vermogen*. De advieszin verwees iedereen naar de
tweede vorm. Dat is dezelfde fout die deze hele familie zinnen moet voorkomen —
de installateur naar iets sturen dat niet op zijn scherm staat — dus
`_cycle_energy_field` en `_power_field` vragen nu het type in plaats van het aan te
nemen. Modulatie is niet tot laadpalen beperkt (de schakelaar staat op elk
adviseerbaar type), dus dat is een vraag en geen aanname.

### 56.9 Openstaand: het uurbedrag dat negatief is, krijgt een opgewekte zin

**Gevonden bij het bouwen van §56.8** (2026-08-11), niet daarin opgelost.

Zodra terugleveren meer oplevert dan zelf verbruiken is
`self_consumption_margin_eur_kwh` negatief, en dan is het bedrag per uur dat ook.
De per-cyclus-tak heeft daar een eigen zin voor — *"Zelf verbruiken levert nu
echter minder op dan terugleveren: … kost naar schatting € 0,34 …"* — maar de
modulerende tak zegt onverstoorbaar *"dit is een gunstig moment"* boven een bedrag
van € -0,12. Dat is precies de tegenspraak waarvoor `_surplus_message` bestaat, één
tak verderop.

**Waarom het nu geen blokkade is:** onder de salderingsregeling kán de marge niet
negatief worden — daar blijft alleen de vermeden terugleverkost over, en die is nul
of positief.

**En waarom het niet vergeten mag worden:** het wordt bereikbaar zodra de saldering
vervalt. Vanaf dat moment is een terugleververgoeding boven de importprijs een
gewone contractvorm, en dan zegt het paneel *"dit is een gunstig moment"* boven een
bedrag dat de klant geld kost. Dit hoort dus in de tekstronde, niet erna.

**Wat het nodig heeft:** een eigen hele zin met het tarief per uur, niet de
per-cyclus-zin met een andere eenheid erin (§26 en §56.4: de twee bedragen mogen
nooit in dezelfde vergelijking komen). Dat is een tekstbesluit, geen rekenwerk — de
waarde staat er al.

## 57. Twee regels over eenheden, en waarom ze verschillen

**Gebouwd in 0.19.0**, uit §54.6.

Twee plekken beantwoorden "in welke eenheid meet deze sensor?" verschillend:

| | Waar de eenheid vandaan komt |
|---|---|
| Energiebron (`grid_meter`, `solar`, `current_price`, …) | de **installateur** kiest hem; die van de entiteit wordt nooit gebruikt |
| Apparaatkoppeling (`power_entity`) | van de **entiteit**; alleen `W` en `kW` worden geaccepteerd |

### 57.1 Het verschil is terecht, en dat was de verrassing

De eerste neiging was ze gelijk te trekken. Bij het nalopen bleek dat verkeerd, en de reden
is het **gevolg**, niet de vorm:

- De eenheid van een **bron** bepaalt het netvermogen, het zonneoverschot, de energiescore en
  elke zin die daarop gebouwd is. Een meterintegratie die een kWh-stand levert waar een
  vermogen verwacht werd, zit er honderden keren naast — en niets op het scherm zou dat
  verraden. Daar is een expliciete uitspraak van de installateur op zijn plaats.
- De eenheid van een **apparaatkoppeling** bepaalt één getal op één rij en de teller
  *"apparaten die nu draaien"*. Zij raakt het overschot niet, de score niet en het advies
  niet. Daar is de eenheid die de entiteit zelf declareert goed genoeg — en wat níét
  declareert wordt geweigerd, nooit als watt aangenomen.

**Gelijktrekken zou dus het slechtste van twee werelden opleveren:** ofwel een veld op elk
apparaat dat nergens toe doet, ofwel een bron die de entiteit gelooft in precies het geval
waarin dat honderden keren misgaat.

### 57.2 Wat er dan wél mis was: het zwijgen

Twee dingen, en het tweede is het echte defect.

**Nergens stond welke regel waar geldt.** De installateur leest op Energiebronnen letterlijk
dat de eenheid van de entiteit nooit gebruikt wordt, koppelt daarna een vermogenssensor op
een apparaat, en moet maar aannemen dat het daar goed gaat. De hulptekst bij
*Vermogensentiteit* zegt het nu.

**En een geweigerde koppeling werd stil overgeslagen.** `_device_powers` deed `continue` bij
een eenheid buiten `W`/`kW`, en de rij toonde dan geen vermogensregel — ononderscheidbaar van
een apparaat waaraan niemand iets gekoppeld had. Een kWh-meterstand is precies de verkeerde
keuze waar het bronformulier voor waarschuwt, en juist die werd hier zonder één woord
genegeerd.

`EnergySnapshot.device_power_unusable` draagt nu de apparaten waarvan de koppeling niet
bruikbaar was, en de rij zegt het:

> *"De gekoppelde vermogenssensor is niet te gebruiken: hij moet in W of kW meten en een
> waarde melden."*

Dezelfde vorm als overal: **weigeren mag, zwijgen niet.**

### 57.3 Openstaande verificatie: een echte Easee

**Sven heeft zelf een Easee-laadpaal en toetst §54.7 op echte hardware zodra het uitkomt.**
Dat is nodig, want de simulatie van woning 3 gebruikte **verzonnen** Easee-entiteiten. Wat
zijn integratie werkelijk levert kan afwijken in namen, in eenheden en in wat de statussensor
meldt.

#### Wat er ingevuld moet worden

**`min_power_w` bij een driefasenaansluiting.** Zes ampère is de ondergrens waaronder niet
geladen wordt, maar het aantal fasen dat telt is dat van de **auto**, niet van de paal:

| Situatie | `min_power_w` |
|---|---|
| Auto laadt op drie fasen | 6 × 3 × 230 = **4140 W** |
| Auto laadt op één fase | 6 × 230 = **1380 W** |

**Beide komen voor, en welke van de twee het is, is niet te beredeneren.** Deze tabel stond
er eerst met "veel auto's, ook op een driefasenpaal" achter de eenfasige regel, alsof dat het
waarschijnlijke geval was. Dat is precies de aanname die het bij de eerste echte meting
begaf: Sven vulde op grond daarvan 1380 in, en zijn Transit Connect bleek driefasig te laden
— 7 A leverde 4765 W, wat 3 × 230 × 7 is en niet 230 × 7. Zijn werkelijke minimum is 4140 W,
een factor drie hoger dan wat er stond (gemeten 2026-08-11).

**Meten is dus geen tweede keus maar de enige route:** zet de paal op zijn laagste stand met
de auto eraan en lees af wat de vermogenssensor meldt. Dat getal is het antwoord, en het is
meteen de controle of de goede sensor gekoppeld is.

Meet je bij een hogere stand, dan geeft vermogen ÷ (230 × ampère) het aantal fasen: bij Sven
4765 ÷ (230 × 7) = 2,96, dus drie. Een uitkomst rond 1 is eenfasig. Reken van daaruit terug
naar zes ampère; dat is de ondergrens die telt.

**Dat het getal aan de auto hangt en niet aan de installatie, is de zwakke plek van dit veld.**
Bij een huishouden met twee auto's die verschillend laden klopt één vast getal per definitie
de helft van de tijd niet. Zie §59 voor de analyse daarvan.

Een te hoge waarde is de veilige kant: dan zwijgt het advies bij een overschot dat eigenlijk
genoeg was. Een te lage waarde adviseert laden waar de auto niets doet.

**Welke sensor de `power_entity` is.** De Easee-integratie levert er meerdere, en er is er
maar één die klopt:

| Sensor | Bruikbaar |
|---|---|
| het **actuele laadvermogen** (kW) | **ja** — dit is de juiste |
| `session_energy` / totaal geladen (kWh) | nee: een totaal, geen vermogen |
| laadstroom (A) | nee: alleen `W` en `kW` worden geaccepteerd |
| energie per uur (kWh/h) | nee |

Sinds §57.2 hoeft dat niet meer geraden te worden: een verkeerde keuze **zegt het** op de rij
in plaats van niets te tonen. Dat is de snelste controle die er is — koppel, kijk naar de rij.

#### Waar op te letten als het advies niet komt

In deze volgorde, want zo loopt de motor:

1. **Is `min_power_w` ingevuld?** Zonder dat getal doet `can_modulate` niets — dat is de
   bewuste veilige standaard van §56.2, en het is de meest waarschijnlijke oorzaak.
2. **Is het overschot groot genoeg?** Het moet boven `min_power_w` liggen **én** boven het
   *minimale zonneoverschot* bij Woning (standaard 500 W).
3. **Krijgt de paal überhaupt advies?** Ingeschakeld, *verplaatsbaar in de tijd* aan, en niet
   op *alleen meekijken*.
4. **Staat vandaag in de dagen?** `days_of_week`, niet te verwarren met `ready_days` — dat
   tweede onderdrukt alleen de deadline, niet het zonneadvies (§56.1).
5. **Een niet-draaien-venster?** Dan verschijnt er wél een zin die dat zegt (§51), dus dit is
   te herkennen aan wat er staat in plaats van aan wat er ontbreekt.
6. **Wint een ander apparaat?** Er is één advies per apparaat en de lijst is begrensd door
   *maximaal aantal adviezen*. Een vaatwasser die ook past kan voorgaan.
7. **Een thuisbatterij die niet te lezen is.** Dan wordt het overschot als mogelijk overschat
   beschouwd en blijft het zonneadvies helemaal weg (0.4.1). Dat is de enige oorzaak in deze
   lijst die niets met de laadpaal te maken heeft, en de makkelijkste om over het hoofd te
   zien.

**Wat er waarschijnlijk afwijkt van de simulatie:** de entiteitsnamen (die van Easee bevatten
het serienummer van de paal), en mogelijk de eenheid — de simulatie ging uit van kW, wat de
integratie ook levert, maar dat is precies het soort aanname dat een echte installatie hoort
te weerleggen of te bevestigen.

## 58. Woning 1: het rijtjeshuis zonder zon

**Bevindingenronde, 2026-08-10. Geen code in deze ronde.** De laatste van de drie, en
bewust als laatste: dit is de woning waar de energiescore het minst te zeggen heeft en waar
het vaakst "niet van toepassing" op het scherm staat.

**De vraag die Sven vooraf stelde**, en die deze ronde moest beantwoorden:

> *"Als een lege tegel ergens als gebrek gaat voelen in plaats van als informatie, is het
> daar. En dat is precies wat ik bij een klant niet wil."*
**Meidoornlaan 42**, rijtjeshuis 1972, eenfase 25 A. Geen zon, geen batterij,
geen auto, vast contract van € 0,289. Eén wasmachine, een diepvrieskast in de
schuur, en een slimme meter. Bewoner van 71 die vooral niet wil dat een scherm
haar elke dag vertelt wat er ontbreekt.

**De vraag van deze ronde:** leest een lege plek als informatie of als een
gebrek?

### 58.1 Het antwoord: als informatie, en dat is bewijs en geen geluk

Op het Overzicht, in plaats van een leeg cijfer:

> *"Het tarief is altijd gelijk en er zijn geen zonnepanelen, dus er is geen
> moment dat beter is dan een ander. Er valt daarom niets te optimaliseren. Het
> advies blijft gewoon werken."*

Informatieve toon, geen waarschuwingskleur, en de laatste zin doet het werk:
zij hoeft niet te concluderen dat het systeem stuk is.

Verder in dezelfde woning:

- **Datakwaliteit 100%**, met *"Niet van toepassing op deze woning, en dus niet
  meegeteld: een geldige zonnebron."* Zij kan een volle score halen zonder iets
  te bezitten wat zij niet wil.
- **De zonnerijen staan er niet**, in plaats van leeg. Een rij bestaat omdat de
  woning het ding heeft.
- **De prijsrij toont haar eigen tarief** met *"Vast leveringstarief, zoals
  ingevuld bij Woning"* — geen "niet van toepassing", wat het tot 0.13.0 zei.
- **De coach beantwoordt *"Hoe is mijn energiescore berekend?"*** met de reden
  dát er geen cijfer is, niet met een uitleg van een berekening die niet
  plaatsvond.

**Dit is de opbrengst van vijf eerdere rondes**, zichtbaar op één scherm: §16
(een eis die niet van toepassing is), §35.9 (waarom er geen cijfer is), §48
(een vast contract heeft ook een prijs) en §52 (*"maakt niet uit"* als
antwoord). Elk daarvan is ooit als klacht binnengekomen.

### 58.2 Twee dingen die nog wringen, allebei klein

#### 1. Een kop die een gebrek belooft en het dan ontkent

Op Energiecoach heet de sectie **"Ontbrekende gegevens"**, en de inhoud is:

> *"Alle gegevens voor een betrouwbaar advies zijn ingevuld."*

De kop stelt de vraag in de vorm van een tekort. Voor een woning waar niets
ontbreekt en niets zal gaan ontbreken, is dat de enige plek op het scherm die
nog naar een gebrek verwijst.

#### 2. "Geschatte besparing: Niet te berekenen"

Onder het hoofdadvies staat *Niet te berekenen*, met daaronder de reden *"De
situatie vraagt niet om een aanpassing"*.

De reden klopt, maar de eerste regel leest als een fout — alsof de som mislukte.
Er valt niets te besparen omdat er niets te veranderen is, en dat is een ander
soort niets dan een som die niet lukt. Dezelfde vorm als §56.4, waar het lege
totaal bij een modulerende laadpaal ook geen gebrek was maar het juiste antwoord.

### 58.3 Wat deze ronde niet opleverde

Geen blokkade, geen stille fout, geen zin die de toestand tegenspreekt. Dat is
opmerkelijk voor een woningronde en het is de eerste keer.

**De verklaring is niet dat deze woning eenvoudig is**, maar dat zij bestaat uit
precies de gevallen die de vijf eerdere rondes hebben opgeruimd. De "niet van
toepassing"-vorm is vijf keer als klacht binnengekomen en is nu het enige gedrag
dat deze woning te zien krijgt.

### 58.4 Wat er gebouwd is, en waarom het één regel werd

**0.20.0.** De twee punten van §58.2 bleken dezelfde vraag te stellen, en het
antwoord erop dekte een derde plek af die niemand gemeld had.

**De regel, in één zin:** *een rij of een kop bestaat omdat er iets te zeggen
is; ontbreekt dat, dan zwijgt zij in plaats van het gebrek te benoemen.*

#### 1. De kop heet nu "Gegevens voor je advies"

Hij noemt het onderwerp en niet het tekort, en is daarmee waar in beide
toestanden. Of er iets ontbreekt is een feit over dit moment, dus het staat
waar de feiten staan: **boven de lijst verschijnt "Nog ontbrekend:"**, en die
regel verdwijnt met de lijst mee. Dezelfde woorden waarmee de coach zelf de
vraag *"Welke gegevens ontbreken nog?"* beantwoordt (`engine/providers.py`), zodat
kaart en antwoord niet uiteenlopen.

**Overwogen en niet gedaan: de kop "Datakwaliteit" noemen**, zoals de tegel op
Overzicht en de checklist in de backend. Het verbindt de twee schermen
letterlijk — Overzicht stuurt de bewoner hierheen — maar het zet een meetterm
boven een lijst zonder cijfer, en dit is het tabblad dat de bewoner leest in
plaats van invult.

#### 2. Een bedrag dat niet bestaat is geen bedrag dat mislukte

*"Geschatte besparing: Niet te berekenen"* verdween niet door een betere zin
maar door de vraag *wie vult dit veld ooit?* **Alleen het zonneoverschot-advies
draagt ooit een bedrag.** Bij elk ander advies kondigde de rij dus een som aan
die nooit geprobeerd is — en bij *"de situatie vraagt niet om een aanpassing"*
is dat precies het geval dat Sven meldde.

De rij verschijnt nu wanneer er een bedrag is. Is er geen:

- **Werd er wél gerekend en lukte het niet**, dan staat de reden al in het
  advies zelf, mét het veld dat de som stopte (`_why_no_amount`). Dat is meer
  waard dan *"Niet te berekenen"* ooit was, en het staat één regel hoger.
- **Werd er niet gerekend**, dan valt er niets te melden.

#### 3. De derde plek: de laadpaal die zijn eigen bedrag niet te zien kreeg

Uit dezelfde vraag rolde een fout die in §58 niet gemeld was. Voor een
modulerende paal is het totaal met opzet leeg en is `savings_rate_eur_per_hour`
het antwoord (§56.4) — maar het hoofdadvies las alleen `estimated_savings_eur`.
De klant kreeg dus *"Niet te berekenen"* terwijl het bedrag ongebruikt in de
payload zat. De lijst met overige adviezen toont het sinds 0.18.0 wel; het
hoofdadvies had er geen plek voor.

Er is nu een tweede rij, **"Geschatte opbrengst per uur"**, met de kwalificatie
*"Zolang dit zonneoverschot er is."* eronder. Een eigen label en een eigen rij,
want § 56.4 eist dat de twee bedragen nooit in dezelfde regel of dezelfde
vergelijking komen: € 1,20 en € 0,12 zijn allebei waar en beantwoorden een
andere vraag.

#### Wat hiermee stil werd, en waarom dat mag

Een modulerend apparaat waarvan óók het uurbedrag niet te berekenen is — geen
leesbare prijs, dus geen marge — toont nu geen van beide rijen en het advies
zegt er niets over. Dat is bewust: de datakwaliteit meldt de ontbrekende
prijsinformatie al, en de coach noemt hem in zijn antwoord op *"welke gegevens
ontbreken nog?"*. Dezelfde afweging als bij de netmeting op Overzicht — een
gat dat de kaart elders al meldt, wordt niet twee keer gemeld.

**Wat dit niet oplost:** het advies zelf legt in dat geval niet uit waarom er
geen bedrag staat, terwijl de niet-modulerende tak dat wel doet. Dat is een
uitbreiding van `_surplus_message` en hoort bij §56, niet bij een tekstronde;
`_why_no_amount` mag er niet zomaar op losgelaten worden, want die begint met
de energie per cyclus en dat is precies het veld dat een modulerende paal niet
gebruikt.

**Opgelost in 0.22.0**, langs de splitsing van §56.8.

## 59. Analyse: het laadminimum hangt aan de auto, niet aan de paal

**Aanleiding: de meting van 2026-08-11.** Sven mat 7 A = 4765 W aan zijn Easee.
Dat is 3 × 230 × 7, dus zijn Transit Connect laadt driefasig en zijn werkelijke
minimum is ~4140 W — niet de 1380 W die hij had ingevuld op grond van "eenfasig
laden". Een factor drie, en niets in het product had het kunnen zeggen.

Dit is **geen invulfout maar een modelvraag**, en Sven stelt hem goed: het
product moet universeel zijn, niet afgestemd op één auto. §57.3 is bijgewerkt,
maar de tabel daar repareert alleen de aanname, niet de vorm van het veld.

### 59.1 Wat er werkelijk mis is: het veld hoort bij een paar, niet bij een ding

`min_power_w` staat op het apparaat, en het apparaat is de **paal**. De waarde
beschrijft de **auto**. Zolang er één auto is valt dat samen, en precies daarom
viel het niet op.

Dat is dezelfde vorm als twee dingen die dit project al eerder tegenkwam:

- **`energy_per_cycle_kwh`** bij een laadpaal is óók een eigenschap van de auto,
  en §16 heeft dat opgelost door de vraag te veranderen: niet "hoeveel gaat
  erin" maar "hoe ziet een *typische* laadsessie eruit", plus een plafond op de
  betrouwbaarheid van elk bedrag dat erop rust (`_surplus_confidence`).
- **De laadtoestand** (§34.8) is de grens waar het model expliciet stopt.

De vraag is dus niet "hoe meten we het minimum" maar **"welke van deze twee
vormen is dit"** — een vraag die anders gesteld moet worden, of een grens.

### 59.2 Kan het systeem het afleiden uit wat de paal meldt?

Rekenkundig ja: vermogen ÷ (230 × stroom) geeft het aantal fasen. Maar de
aanname eronder is precies het soort dat §47 (achtste variant) beschrijft, en
zij is bij een laadpaal aantoonbaar wankel:

| Aanname | Waar het misgaat |
|---|---|
| De stroomsensor meldt de stroom **per fase** | Meldt hij de som over drie fasen, dan geeft dezelfde som 1 fase in plaats van 3 — en er is niets in de waarde dat het verraadt |
| De netspanning is 230 V | In de praktijk 220–245 V; op zichzelf onschuldig (de uitkomst 2,96 rondt naar 3), maar het maakt een drempel nodig |
| De auto laadt symmetrisch over de fasen | Niet altijd waar bij het aftoppen door de paal |
| Er is een stroomsensor gekoppeld | Vandaag koppelt een apparaat alleen een **vermogens**entiteit (§57) |

De eerste is de ernstige: hij geeft **stil het verkeerde antwoord in de richting
die schaadt** (te laag minimum → advies waar de auto niets mee kan). En het is
niet op te lossen door beter te rekenen; het vraagt een uitspraak van de
installateur over zijn sensor — dus ruilt deze route één vraag in voor een
andere vraag plús een nieuwe koppeling.

**Daar komt bij dat het alleen tijdens het laden waarneembaar is**, en het advies
gaat juist over het moment dat de auto *niet* laadt. Onthouden zou het antwoord
zijn, maar afgeleide toestand terugschrijven naar de opslag is een harde regel
die dit project niet buigt (CLAUDE.md regel 9); in het geheugen van de
coordinator overleeft het geen herstart.

**Oordeel: niet afleiden.** Niet omdat het niet kan, maar omdat het een aanname
toevoegt die precies zo faalt als de aanname die we nu proberen te repareren.

### 59.3 Maar meten kan wél iets — en daar is geen stroomsensor voor nodig

De omkering die dit oplevert, en zij is goedkoper dan de berekening hierboven:

> **Laadt de paal aantoonbaar op minder vermogen dan het ingevulde minimum, dan
> is het ingevulde minimum te hoog.** Dat is af te lezen aan de
> vermogensentiteit die er al is.

Eén vergelijking, geen fasen, geen spanning, geen tweede koppeling. En hij vangt
precies de richting die je niet kunt zien:

| Fout in `min_power_w` | Gevolg | Zichtbaar? |
|---|---|---|
| Te **hoog** (Sven omgekeerd: 4140 ingevuld, auto laadt eenfasig) | het advies blijft weg bij een overschot dat genoeg was | **nee** — stilte, en stilte lijkt op "geen overschot" |
| Te **laag** (Sven's echte geval) | advies bij een overschot waar de auto niets mee kan | deels: de klant ziet dat er niets gebeurt |

De stille fout is dus de fout die gemeten kan worden, en de luidruchtige niet.
Dat is een gelukkige verdeling en geen toeval: te laag betekent dat de paal
*meer* trekt dan het minimum, en dat is niet te onderscheiden van een auto die
gewoon harder laadt.

**Vorm: waarnemen en tonen, nooit overrulen.** Op de apparaatrij het laagste
laadvermogen dat sinds de laatste herstart is gezien, als feit zonder oordeel —
dezelfde lijn als §57.2 (*weigeren mag, zwijgen niet*) en als §53 (de opslag
corrigeert nooit stilzwijgend wat iemand heeft ingevuld). De installateur ziet
dan het getal dat hij had moeten invullen, in plaats van een verwijt.

### 59.4 Een keuze eenfasig/driefasig in plaats van een watt-getal?

**Half goed, en de goede helft hoort in het formulier en niet in de opslag.**

Wat het oplost: de installateur hoeft geen 6 × 3 × 230 uit te rekenen, en dat is
een som die hij niet zou moeten doen.

Wat het níét oplost, en dat is de kern: **welke van de twee waar is, weet hij
nog steeds niet.** Sven wist het niet, en hij bouwt dit product. Een keuzelijst
maakt het foute antwoord even makkelijk als het goede, en geeft er de schijn van
een vaststaand feit bij.

Wat het kapotmaakt: sommige auto's laden niet onder 8 A, sommige palen hebben
een eigen vloer. Een watt-veld draagt dat allemaal; een fasenkeuze draagt alleen
het schoolvoorbeeld.

**Voorstel:** het formulier rekent het voor (zoals het theoretisch maximum bij
Woning: *"6 A × 3 fasen × 230 V = 4140 W"*), maar de opgeslagen waarde blijft
watt. Een opgeslagen fasenveld zou een veld zijn dat de motor nooit leest, en
dat is precies wat §16 verbiedt.

**En een naamsverwarring om vóór te zijn** (negende variant): `HomeProfile.phases`
bestaat al en beantwoordt *"hoeveel fasen heeft de aansluiting"*. Een fasenveld
op het apparaat zou daar als tweede antwoord naast staan met een ander onderwerp
— de auto in plaats van het huis — en dat is de vorm waarin §51 en §56.1 eerder
misgingen.

### 59.5 Twee auto's die verschillend laden

**Dat is de grens van het model, en zij ligt waar §34 hem al legde:** één auto
per paal. Twee auto's met verschillend fasegedrag is dezelfde grens één stap
verder, net als de laadtoestand (§34.8).

De drie vormen die overwogen zijn, en waarom geen van drie het draagt:

1. **Het laagste minimum van de twee** — adviseert bij een overschot waar de
   driefasige auto niets mee kan. Dat is het defect van §56.3 terug.
2. **Het hoogste minimum** — veilig maar stil: de eenfasige auto laadt dan de
   halve zomer niet op zon, en de klant ziet nooit waarom.
3. **De bewoner laten aanwijzen welke auto eraan hangt** — dat is een handeling
   per keer, en dit product maakt geen klusjes die het niet kan afdwingen. Het is
   bovendien de vorm die het dichtst bij aansturing komt.

**Wat wél kan zonder het model te verbouwen, en dit is de vorm die hier gekozen
is** (besluit Sven, 2026-08-11):

> **De waarneming maakt de grens zichtbaar in plaats van stil.**

Dat is precies wat er bij de laadtoestand ook gekozen is: het model stopt, en op
de plek waar het stopt staat een feit in plaats van niets. Bij twee auto's toont
de rij simpelweg het laagste gemeten vermogen van beide — een eerlijk antwoord op
de vraag die eronder ligt, en het maakt zichtbaar dát er twee zijn, want het
gemeten minimum ligt dan onder wat er is ingevuld.

Een grens die je kunt zien is iets anders dan een grens die zwijgt. Het model
draagt de tweede auto niet, maar de bewoner hoeft niet meer te raden waaróm zijn
advies uitblijft.

### 59.6 Gedrag zonder meting, en bij afwijking

- **Zonder meting verandert er niets.** Leeg `min_power_w` betekent nog steeds
  dat `can_modulate` niets doet (§56.2), en de waarneming toont niets tot de
  paal een keer geladen heeft. Geen enkel getal wordt afgeleid of ingevuld.
- **Bij afwijking wordt niets overruled.** De ingevulde waarde blijft leidend
  voor het advies; de meting staat ernaast als feit. Dat is dezelfde keuze als
  §53: corrigeren is aan de mens, melden is aan het product.

### 59.7 Wat er gebouwd is

**Alle vier akkoord bevonden door Sven op 2026-08-11, gebouwd in 0.22.0.**

1. **§57.3 bijgewerkt** — beide gevallen komen voor, alleen de meting
   geeft antwoord, en de terugrekening van fasen uit een meting bij een hogere
   stand staat erbij.
2. **De hulptekst bij `min_power_w`** zegt nu dat het getal aan de **auto** hangt
   en niet aan de paal, dat allebei de gevallen voorkomen, en dat meten met de
   auto aan de paal de enige route is. Geen van beide getallen wordt aangeprezen
   als het waarschijnlijke.
3. **De voorrekening** leest de ingevulde waarde terug in ampère: *"4140 W is
   ongeveer 18,0 A op één fase, of 6,0 A op drie fasen."* Ampère is het getal dat
   een paal toont, dus dit is meteen de controle — 18 A op één fase is geen stand
   die een paal heeft. **Geen opgeslagen fasenveld** (§59.4).
4. **Het laagst gemeten vermogen op de apparaatrij**, voor apparaten met *Kan op
   deelvermogen draaien* aan: *"Nu: 0 W · laagste meting sinds herstart: 4140 W"*.

#### Drie keuzes in punt 4 die niet vanzelf spreken

- **"Draaien" is `DEVICE_RUNNING_MIN_POWER_W`**, dezelfde drempel waarmee het
  Overzicht apparaten telt. Een eigen drempel hier zou een tweede antwoord zijn
  op *"staat dit ding aan"*, en die twee lopen uiteen.
- **De waarneming hoort bij de sensor waar zij vandaan komt.** Koppelt de
  installateur een andere vermogensentiteit, dan begint de meting opnieuw;
  anders zou de ene sensor de meting van de andere dragen.
- **"Sinds herstart" staat in de zin**, want dat is de hele waarheid over dit
  getal: het leeft in het geheugen van de coordinator en gaat nooit naar de
  opslag (CLAUDE.md regel 9). Zonder die woorden leest het als *"het laagste dat
  deze paal kan"* — een uitspraak over de hardware die dit product niet mag doen.

## 60. Bediening staat op het Overzicht, niet op een insteltabblad

> **De toets, en zij is breder bruikbaar dan dit geval: *waar staat iemand als hij
> dit doet?*** Bij de stille uren zit hij erbij te denken — dat mag een tabblad
> zijn. Bij *"hij is vol"* staat hij met zijn telefoon in de keuken, en dan telt
> elke tik.

**Akkoord bevonden en gebouwd in 0.24.0** (aanleiding: Sven, 2026-08-11, bij het
opleveren van fase 3).

De gereed-vlag kreeg zijn knop op twee plekken, zoals §44.6 voorschrijft: onder het
advies, en op Apparaten bij het apparaat. Die tweede plek is fout, en de reden is
niet de knop maar het tabblad:

> **Apparaten is waar een installateur iets inricht. Een bewoner met een volle
> vaatwasser gaat daar niet heen.**

Het scherm dat hij openslaat is het Overzicht. Daar hoort dus alles wat hij op een
moment *doet* — en dat is breder dan deze ene knop.

### 60.1 De regel die eruit volgt

> **Wat de bewoner instelt staat waar het hoort te staan. Wat hij op een moment
> doet, staat op het Overzicht.**

Dat is een andere as dan §33.3 (*de installateur bezit wat de woning is, de bewoner
wat zij moet doen*), en de twee vullen elkaar aan. §33.3 verdeelt **velden** over
eigenaren; deze regel verdeelt **handelingen en instellingen** over schermen. Een
bewoner bezit zijn stille uren én de gereed-vlag, maar het eerste stelt hij één keer
in en het tweede doet hij twee keer per dag.

Toets: *waar staat iemand als hij dit doet?* Bij de stille uren zit hij erbij te
denken — dat mag een tabblad zijn. Bij "hij is vol" staat hij met zijn telefoon in de
keuken, en dan telt elke tik.

### 60.2 Eén sectie, en waarom niet twee

Op het Overzicht, onder `Advies`: **"Wat je nu kunt doen"**.

De verleiding is om per soort handeling een sectie te maken — de vlag bij de
apparaten, `Nu aangestuurd` (§44.4) voor de aansturing, goedkeuringen bij het advies.
Dat levert bij de aansturingsrelease opnieuw het probleem op dat deze sectie oplost:
de bewoner moet weten wélke sectie zijn handeling draagt.

Dus: **één sectie, met rijen van verschillende soort.** `Nu aangestuurd` uit §44.4
wordt een rijsoort binnen deze sectie in plaats van een sectie ernaast.

| Rijsoort | Wanneer zichtbaar | Wat er staat | Knop |
|---|---|---|---|
| **gereed-vlag** | apparaat met `needs_ready_flag` | leeg, of *"Staat vol. Dit vervalt vandaag om 20:35, of eerder zodra hij klaar is."* | *Klaar / vol* of *Toch niet vol* |
| **aangestuurd** (§44) | DomotiApp stuurt dit apparaat nu aan | wat, sinds wanneer, en waarom in de woorden van het advies | *Stop* |
| **goedkeuring** (§44.6) | een advies vraagt erom | wat de coach wil doen en waarom | *Goedkeuren* |
| **start nu** (§44.3) | een advies vraagt erom | de zin van dat advies | *Start nu* |

**De sectie bestaat op grond van de configuratie, de rijen volgen het moment.**
Dezelfde regel als §39.3 en §44.4, en om dezelfde reden: *"waar zit die knop"* is een
vraag die je niet voor het eerst wilt stellen op het moment dat je hem nodig hebt.
Heeft de woning geen enkel apparaat dat de bewoner bedient, dan is er geen sectie —
geen tekortkoming tonen die deze woning niet kan opheffen.

#### De lege staat, bewust gekozen

Vraag van Sven bij het bouwen: *wat staat er als er wél bedienbare apparaten zijn maar
op dit moment niets te doen?* Een lege sectie is precies de vorm die dit project vijf
keer heeft opgeruimd (§16).

**Het antwoord is dat die staat met de gereed-vlag niet kan bestaan**, en dat is geen
geluk maar de vorm van de rij: *"hij is vol"* zeggen of terugnemen kan altijd. Een rij
is dus altijd een aanbod, nooit een mededeling dat er niets is. En bestaat er geen
enkele bedienbare rij, dan bestaat de sectie niet.

Er staat toch een zin klaar — *"Er is op dit moment niets te doen."* — en die is voor
de aansturingsrelease. Zodra `Nu aangestuurd` een rijsoort wordt (§60.5) hangt die rij
wél aan het moment, en dan is dit precies het geval dat §44.4 al besloot: zeg dat er
niets loopt, in plaats van de sectie te laten verdwijnen op het moment dat iemand de
stopknop zoekt.

**Toepasselijkheid gaat verder dan het bestaan van de rij.** Een apparaat krijgt alleen
een rij wanneer de vlag ook gelézen wordt: hij voedt uitsluitend het urgentie-advies,
dus een vaatwasser op *Alleen meekijken* krijgt geen knop. Dat is dezelfde regel als
bij het tijdvenster en het apparaatprofiel — een vraag hangt aan waar haar antwoord
voor gebruikt wordt (§16).

### 60.3 Wat er op Apparaten overblijft, en waarom de knop daar weg moet

Apparaten houdt wat het apparaat **is**: type, vermogen, venster, koppelingen, de
bedieningsafspraak. De gereed-knop verdwijnt daar, en niet alleen omdat hij elders
beter staat:

- **een knop op een configuratierij nodigt uit tot de verkeerde lezing** — dat het
  iets *instelt* in plaats van iets doet;
- **twee plekken zijn alleen te verdedigen als het twee momenten zijn** (§44.6). Onder
  het advies en op het Overzicht zijn dat: "ik lees dit advies" en "ik sta in de
  keuken". Apparaten is geen moment dat een bewoner heeft.

**Wat we ervoor opgeven, eerlijk genoemd:** een installateur die een verse installatie
test, kan de vlag niet meer aanzetten op het tabblad waar hij toch al is. Dat is
gemak bij het testen, geen behoefte van een klant, en `ha_check --ws
domotiapp_energy/devices/set_ready` doet het.

### 60.4 De volgorde op het Overzicht

Nu drie kaarten: `Op dit moment`, `Actuele situatie`, `Advies`. Dit voorstel voegt er
één toe, en het historisch overzicht komt daarna. De volgorde die daaruit volgt:

1. **Op dit moment** — hoe staat het ervoor
2. **Actuele situatie** — de cijfers eronder
3. **Advies** — wat zou ik doen
4. **Wat je nu kunt doen** — en hier doe je het
5. *(later)* **de geschiedenis** — hoe het liep

Vier boven vijf, want handelen gaat over nu en de geschiedenis over gisteren. Drie en
vier grenzen aan elkaar met opzet: de aanleiding en de handeling staan onder elkaar op
het scherm dat de bewoner opent, en dát is wat §44.6 met *"de handeling hoort bij de
aanleiding"* bedoelt.

### 60.5 Gevolgen voor de aansturingsrelease

- **§44.3** (de tabel "waar de handelingen landen") wordt vervangen door §60.2. Elke
  handeling landt in de sectie op het Overzicht, plus — waar zij een aanleiding heeft
  — onder dat advies in de Energiecoach.
- **§44.4** (`Nu aangestuurd` als eigen sectie) vervalt als sectie en blijft als
  rijsoort. De inhoud verandert niet: wat, sinds wanneer, waarom, en één *Stop*.
- **§44.6** blijft overeind, met de tweede plek verlegd van Apparaten naar het
  Overzicht. De redenering was altijd al "twee momenten", en dit corrigeert alleen
  wáár het tweede moment plaatsvindt.
- **`control_forbidden`**: een knop verschijnt nooit, ook niet uitgegrijsd (§44.3).
  Ongewijzigd, en in één sectie is dat makkelijker vol te houden dan in vier.

### 60.6 Wat deze ronde niet doet

- **De Energiecoach houdt zijn knop onder het advies.** Dat is de aanleiding zelf, en
  wie doorklikt naar het waarom moet daar kunnen handelen.
- **Geen rolafscherming op de sectie.** Een installateur ziet hem ook; hij woont
  alleen niet in deze woning. Verbergen zou een handeling verstoppen voor iemand die
  hem legitiem kan doen.
- **De teller *Apparaten die nu draaien* blijft een feit** op `Actuele situatie`. Dat
  is geen handeling.

## 61. Het historisch overzicht

> **De val waar iemand anders wel in loopt** (Sven, 2026-08-11, over §61.3):
> **het gemiddelde van een verhouding is niet de verhouding van de sommen.** Een
> daggemiddelde zelfbenutting uit uurgemiddelden valt structureel te hoog uit bij
> zon in de ochtend en verbruik in de avond — en het is precies het soort getal
> dat plausibel oogt en in elke test klopt. Lees §61.3 vóór je aan een dagwaarde
> begint, welke dan ook.

**Status: gebouwd. Het blok in 0.25.0, het logboek als tijdlijn in 0.27.0.**

### 61.1 De vraag die het beantwoordt, en de vraag die het weigert

Een klant die "historie" hoort, verwacht meestal twee dingen: *hoeveel heb ik
verbruikt* en *hoeveel heeft dit opgeleverd*. Dit voorstel beantwoordt geen van
beide, en dat is de belangrijkste keuze erin.

**Verbruik is er al, en beter.** Home Assistant heeft een eigen Energie-dashboard
dat kWh in, uit, opgewekt en zelf verbruikt toont, rechtstreeks uit de meters van
de klant. Wat wij zouden bouwen is een slechtere kopie van iets dat hij al heeft,
gemaakt uit vermogensgemiddelden in plaats van uit energie.

**Opbrengst kunnen we niet meten.** De coach adviseert; hij stuurt niet aan
(tot §44), en niets weet of de bewoner het advies opvolgde. *"Je hebt deze week
€ 12 bespaard"* zou een getal zijn dat wij verzinnen — precies wat dit project
nergens doet. Ook ná de aansturingsrelease blijft dat waar: besparing vraagt om
een tegenfeitelijke wereld waarin je het niet gedaan had, en die is er niet.

> **Wat alleen wij weten: wat de coach zag, wat hij zei, en wat er daarna
> gebeurde.** Dat is het historisch overzicht.

Vier dingen die daaronder vallen, en die het Energie-dashboard niet kan tonen:

1. **wat de coach adviseerde**, en wanneer;
2. **wat de bewoner deed** — de gereed-vlag, en straks de aansturing;
3. **hoe de energiescore liep** — onze eigen indicator;
4. **of de installatie gezond was** — datakwaliteit, bronnen die wegvielen.

### 61.2 Geen nieuwe opslag

**Home Assistant bewaart onze eigen sensoren al.** Vijf van de acht entiteiten
hebben `state_class: measurement`, dus de recorder houdt er statistieken van bij,
en het paneel kan die opvragen over dezelfde geauthenticeerde verbinding waar het
alles over doet. Er komt dus **geen derde store** en er wordt niets afgeleids
weggeschreven (CLAUDE.md regel 9).

Het logboek dat we al hebben levert de gebeurtenissen: piekrisico, zonneoverschot,
bronnen die wegvielen, configuratiewijzigingen.

**Twee aannames over Home Assistant, geverifieerd in de bron van 2026.8.1** — de
versie die de klant draait — en niet in de documentatie:

| Aanname | Uitkomst |
|---|---|
| de recorder bewaart uurstatistieken langer dan de ruwe states (standaard 10 dagen) | **klopt** |
| het paneel mag `recorder/statistics_during_period` aanroepen | **klopt**, en zonder adminrecht |

**Wat er precies gelezen is.** `recorder/purge.py` verwijdert states, events,
attributen, eventtypes, recorder-runs, `statistics_runs` en de rijen van
`statistics_short_term`. De lange-termijntabel `statistics` — de uurwaarden —
komt in dat pad niet voor; de enige functie die haar leegt is `clear_statistics`,
en dat is een expliciete handeling via een eigen WebSocket-commando.

> **Gevolg voor het ontwerp:** de uurgeschiedenis van onze vijf meetsensoren
> overleeft `purge_keep_days`. De ruwe states niet, dus alles wat fijner is dan een
> uur bestaat alleen binnen het purge-venster.

`recorder/statistics_during_period` staat geregistreerd zonder `require_admin`,
net als `coach/recalculate` bij ons: elke ingelogde gebruiker mag het opvragen. Dat
is precies wat een paneel nodig heeft dat ook een bewoner opent.

**Wat hier níét uit volgt:** dat elke klant statistieken *heeft*. De recorder kan
uitgeschakeld of ingeperkt zijn, en een woning die net geïnstalleerd is heeft
niets. Het overzicht toont dus wat er is en zegt het wanneer er minder is (§61.6).

### 61.3 De valkuil die dit ontwerp bijna insloop

**Het gemiddelde van een verhouding is niet de verhouding van de sommen.**

Zelfbenutting is een percentage: *zelf gebruikte opwek ÷ totale opwek*. De
verleiding is om er een daggemiddelde van te tonen. Dat getal is fout, en het is
fout in een richting die niemand opmerkt: een uur met 200 W opwek waarvan je alles
gebruikt telt in het gemiddelde even zwaar als een middaguur met 4 kW waarvan je de
helft terugleverde. Een woning met zon in de ochtend en verbruik in de avond scoort
daardoor structureel te hoog.

De juiste dagwaarde vraagt om **energie**, dus om sommen van kWh — en die hebben we
niet, want onze sensoren meten vermogen. Het Energie-dashboard heeft ze wel.

**Gevolg:** dit overzicht toont géén dagelijkse zelfbenutting. Dat is een getal dat
alleen goed te maken is met gegevens die HA al beter presenteert.

### 61.4 Wat er dan wel staat

Op het **Overzicht**, onder de bedieningssectie (§60.4), één blok met ten hoogste
drie feiten over gisteren. Elk feit moet los verdedigbaar zijn:

| Feit | Waar het vandaan komt | Wat het níét beweert |
|---|---|---|
| *"4,5 uur zonneoverschot"* | uren waarin het gemiddelde overschot boven `min_solar_surplus_w` lag | niet dat je het gebruikt hebt |
| *"3 keer advies"* | het logboek | niet dat je het opvolgde |
| *"installatie compleet"* | datakwaliteit | niet dat het advies goed was |

**Ten hoogste vier, en dat is een grens en geen richtlijn.** Het waren er drie;
§61.7 voegde er één toe met een reden die de grens niet oprekt maar verplaatst.
Een blok dat verder groeit wordt een dashboard, en dan zijn we alsnog bezig het
Energie-dashboard na te bouwen.

**En het blok wijst zelf naar waar "hoeveel" staat.** Een klant die kWh, kosten of
zelf verbruikte energie zoekt en hier niets vindt, concludeert dat het ontbreekt —
niet dat het ergens anders beter staat. De verwijzing hoort dus in het blok en niet
alleen in de README (besluit Sven, 2026-08-11).

**Elk feit zegt over hoeveel uur het iets weet, wanneer dat niet de hele dag is.**
Gevonden in de browser: op de testinstance had de datakwaliteit vierentwintig
uurwaarden en de netmeting zeven, en *"hoogste netvermogen 800 W"* rustte dus op
zeven uur terwijl de dag volledig was vastgelegd. Per feit en niet per dag — een
bron kan stil vallen terwijl de rest doorloopt.

Het **Logboek** wordt de diepte. Dat tabblad bestaat al en is nu een technische
lijst; het wordt een tijdlijn per dag, in de woorden van de klant. Geen zevende
tabblad: de tabbalk loopt op een telefoon al over twee regels.

### 61.5 Besloten: zelfbenutting wordt een eigen entiteit

**Ja** (Sven, 2026-08-11), met twee voorwaarden die bij het besluit horen:

1. **Geen daggemiddelde erop.** Om de reden van §61.3, en die geldt voor elke
   dagwaarde die uit dit percentage wordt afgeleid.
2. **De belofte staat in de README.** Een entiteit die klanten in dashboards en
   langetermijnstatistieken zetten kan daarna niet meer weg — dezelfde afspraak
   als bij de bestaande ID's (CLAUDE.md regel 11), en zij hoort te staan waar de
   klant hem leest en niet alleen in een commit.

De reden om het te doen: **het is de enige van de vier die iets zegt over wat de
bewoner deed.** Zonder geschiedenis van dat getal mist het product zijn eigen
onderwerp — de energiescore is erop gebouwd.

De afweging zoals zij lag:

Het is het getal waar dit product over gaat — de energiescore is erop gebouwd —
en het is het enige van de vier dat iets zegt over wat de *bewoner* deed. Maar het
wordt nergens vastgelegd, dus er is geen geschiedenis van.

| | Wel een entiteit | Niet |
|---|---|---|
| Winst | de klant kan er zelf een grafiek van maken, en wij later ook | geen achtste entiteit om te onderhouden |
| Kosten | historie begint pas bij installatie; het paneel moet dat zeggen in plaats van een lege grafiek te tekenen | de belangrijkste uitkomst blijft onzichtbaar in de tijd |
| Risico | het uitnodigt tot precies de daggemiddelden van §61.3 | — |

**Toevoegen is niet brekend** (regel 11 gaat over het *wijzigen* van bestaande
ID's), maar het is wel een belofte.

Wat dat praktisch betekent: de klant krijgt het getal in HA's eigen grafieken,
waar hij zelf kan zien wat het doet — en ons blok houdt zich bij de drie feiten
van §61.4, die los verdedigbaar zijn.

### 61.7 Week, maand en jaar: één uitzondering, en verder niets

**Analyse op verzoek van Sven** (2026-08-11), en het antwoord is grotendeels
*"hier voegen we niets toe wat Home Assistant niet beter doet"*.

**De val van §61.3 geldt in het kwadraat.** Bij een dag is het gemiddelde van
uurgemiddelden al scheef; bij een maand komt er een tweede middeling overheen die
de eerste verbergt. Een maandgemiddelde van daggemiddelden weegt een bewolkte
zondag even zwaar als een zonnige woensdag. Het getal wordt gladder naarmate het
minder betekent, en gladde getallen ogen betrouwbaar.

Een langere periode vraagt dus om **sommen, maxima of tellingen** — nooit om
gemiddelden. Sommen waarvan? Van kWh. Die hebben wij niet en het
Energie-dashboard wel.

| Feit | Over een langere periode |
|---|---|
| uren zonneoverschot | schaalt, als **som** van uren |
| hoogste netvermogen | schaalt en wordt **beter**: een maximum middelt niets weg |
| installatie compleet | schaalt als **telling** van dagen |
| zelfbenutting | wordt betekenislozer als gemiddelde, en is in de juiste vorm (kWh ÷ kWh) het Energie-dashboard |

**Wat Home Assistant al beter doet:** verbruik, opwek, teruglevering, zelf
verbruikt en de kosten, per dag, week, maand en jaar, uit de meters. Daar is niets
aan toe te voegen.

**Wat zij niet heeft, en wij wel:** het maximum van het netvermogen afgezet tegen
`max_grid_power_w`. Zij kent dat maximum niet, want het staat in onze configuratie.

> **Daarom precies één uitzondering: het hoogste netvermogen van de afgelopen
> dertig dagen, met het aantal dagen boven de waarschuwingsgrens erbij.**

De telling hoort erbij omdat de installateur een andere vraag stelt dan *"hoe
hoog"*: bij een klant die belt over een gesprongen zekering wil hij weten of de
woning er structureel tegenaan zit of dat het één keer gebeurde. Een maximum
alleen beantwoordt dat niet, en het is het bruikbaarste getal van het blok
(Sven, 2026-08-11).

**Dertig dagen en geen kalendermaand**, want een storingsmelding gaat over de
laatste tijd en niet over augustus.

#### En dus geen eigen scherm

Het Logboek blijft de tijdlijn (§61.4): dat beantwoordt *"wat gebeurde er"*. Een
periode beantwoordt *"hoe stond het ervoor"*, en dat zijn twee vormen die je niet
in één tabblad moet persen.

Maar na aftrek van wat het Energie-dashboard beter doet, blijft er van "hoe stond
het ervoor" één regel over. **Drie regels zijn geen scherm**, dus er komt geen
zevende tabblad — de uitzondering staat gewoon in het blok.

### 61.6 Wat dit overzicht niet doet

- **Geen prognose.** Vooruitkijken is een eigen onderwerp (§32.8) en heeft niets
  met historie te maken.
- **Geen export.** Een CSV-knop is een aparte vraag, en pas zinvol als iemand hem
  vraagt.
- **Geen bewaartermijn van onszelf.** Wat HA bewaart, bewaart HA; wij tonen wat er
  is en zeggen het wanneer er minder is.

## 62. Navigatie uit het paneel, en de wandtablet

**Status: akkoord bevonden en gebouwd in 0.26.0** (Sven, 2026-08-11, na §61).

> **De regel die het zwaarst weegt, en die iemand later niet stelt als hij "even
> een linkje" toevoegt:**
>
> **Op een wandtablet is elke navigatie uit dit paneel eenrichtingsverkeer.**
>
> Fully Kiosk zonder zijbalk betekent: wie hier wegklikt, komt niet terug. Elke
> verwijzing die het paneel verlaat moet die vraag beantwoorden vóór zij bestaat.

### 62.1 De aanleiding

Twee gevallen bij klanten van DomotiTech, allebei op een wandtablet zonder
zijbalk:

1. **De link naar `/energy`** die §61 toevoegde is een navigatie. Wie hem volgt,
   kan niet meer terug.
2. **Er is geen weg terug naar het hoofddashboard.** De installateur navigeert
   er met een tegel naartoe; het paneel zelf heeft geen knop terug.

En beide bestemmingen verschillen per klant: niet elke woning heeft haar
hoofddashboard op dezelfde URL, en het energiedashboard kan een eigen dashboard
zijn.

### 62.2 Een pop-up kan, en juist daarom is de vraag interessant

**Geverifieerd in de bron van HA 2026.8.1**, `components/http/headers.py`:

```python
added_headers[X_FRAME_OPTIONS] = "SAMEORIGIN"
```

`SAMEORIGIN` **staat toe** dat een pagina van dezelfde origin ons in een iframe
zet. Het paneel en `/energy` komen van dezelfde origin, dus een eigen dialoog met
`<iframe src="/energy">` mag — zonder browser_mod en zonder interne API's.

**En toch doen we het niet.** Wat je krijgt is de hele HA-frontend een tweede
keer, mét eigen zijbalk en werkbalk, in een venster op een wandtablet: een pagina
in een pagina, en de zwaarste die HA heeft. Netjes maken vraagt om HA's interne
`hui-*`-elementen, en dat is dezelfde val als `ha-dialog` (§49.6).

> **Modaal tonen we alleen onze eigen inhoud.**

**Wat daaruit volgt en niet vanzelf spreekt:** een terugknop lost geval 1 *niet*
op. Wie eenmaal op `/energy` staat, is uit ons paneel weg en heeft niets meer aan
een knop die hier hangt. De twee gevallen lijken hetzelfde en zijn het niet.

Er blijven dus drie eerlijke mogelijkheden voor die link: geen link, een link die
strandt, of een iframe. Dit voorstel kiest de eerste — voorwaardelijk.

### 62.3 Twee velden bij Installatie, en één regel

| Veld | Wat het is |
|---|---|
| `home_dashboard_path` | waar *terug* heen gaat |
| `energy_dashboard_path` | waar het verbruik van déze klant staat |

Twee velden en geen "veld per link": ze verschillen niet in soort maar in
onderwerp. Het eerste is een eigenschap van de navigatie van deze installatie,
het tweede van wat deze klant heeft.

> **De regel: leeg is geen knop en geen link.**

Geen `/lovelace/0` gokken — dat is precies wat §2.1 verbiedt. En `/energy` als
stille standaard is subtieler fout: dat pad is niet verzonnen, het is HA's eigen
adres, maar of *deze* klant daar iets heeft staan weten we niet. Een link naar
een leeg dashboard is erger dan geen link.

#### En daarom komt er geen kiosk-instelling

Dit is het deel dat expliciet vastgelegd moet worden (Sven, 2026-08-11).

**Een leeg veld betekent "hier mag niet genavigeerd worden".** De installateur die
een wandtablet oplevert vult niets in en de bewoner krijgt een zin; de installateur
van een woning mét zijbalk vult het in en de bewoner krijgt een link.

De kiosksituatie wordt dus gecodeerd **door te doen wat de installateur toch al
doet** — een bestemming invullen of niet — in plaats van door een tweede vraag te
stellen die hetzelfde nog eens zegt. Een aparte schakelaar *"deze woning heeft
geen zijbalk"* zou een tweede antwoord zijn op dezelfde vraag, en die twee lopen
uiteen zodra iemand er één verandert (§60.2, negende variant).

### 62.4 Wat er op het scherm staat bij een leeg energieveld

**De zin blijft, alleen de link verdwijnt.**

Die zin bestaat niet om te navigeren maar om te zeggen *waar het antwoord woont*:
zonder hem concludeert een klant die kWh zoekt dat het bij ons ontbreekt in plaats
van dat het ergens anders beter staat (§61.1). Dat doel overleeft het wegvallen
van de link volledig.

> *"Voor kWh, kosten en wat je zelf verbruikte: het Energie-dashboard van Home
> Assistant."*

Met een ingevuld veld is de staart een link; zonder is het dezelfde zin als tekst.
Eén zin, twee weergaven — geen tweede zin, want er is niets anders te zeggen.

**De afweging die daaronder ligt.** Op een tablet waar de bewoner er niet heen
kan, vertelt die zin over een scherm dat hij niet bereikt. Dat is mild vervelend.
De omgekeerde fout — de zin weglaten — is erger en structureler: dan ontstaat
precies het misverstand dat §61 wegnam, en het treft ook elke woning mét zijbalk
waar de installateur het veld gewoon nog niet had ingevuld.

### 62.5 Waar de terugknop staat

**Linksboven, op dezelfde regel als de tabbalk, met een scheiding ertussen.**

- **niet in de tabbalk**, want het paneel verlaten is geen tabblad;
- **niet onderaan**, want dan moet een bewoner scrollen om weg te kunnen;
- **linksboven**, omdat daar op touch een terugaffordantie verwacht wordt.

De tabbalk wikkelt op smalle schermen al naar een tweede regel (§10); de knop
blijft op de eerste staan.

### 62.6 Hoe de installateur weet dat hij dit moet invullen

Sven's vraag, en het antwoord is deels een nee.

**Niet in de datakwaliteit.** Dat is de fout die dit project vijf keer heeft
opgeruimd: een eis stellen die een woning niet kan afvinken. Een woning met een
zijbalk heeft geen terugknop nodig, en er is — met opzet, §62.3 — geen veld dat
zegt dat deze woning een wandtablet is. De checklist kan dus niet weten of het
item van toepassing is, en zou het cijfer laten zakken voor een installatie waar
niets mis mee is.

**Wel op twee plekken waar een installateur toch al kijkt:**

1. **De hulptekst bij het veld**, die het gevolg noemt in plaats van de vorm:
   *"Zonder dit adres verschijnt er geen terugknop. Op een wandtablet zonder
   zijbalk kan de bewoner dit paneel dan niet verlaten."*
2. **Een neutrale regel op Installatie** wanneer het leeg is — geen
   waarschuwingstoon, want bij de meeste woningen is het geen gebrek:
   *"Geen terugknop ingesteld. Nodig bij een wandtablet zonder zijbalk."*

En bij de eerste installatie hoort het in de README, onder *Setting up your first
home*, want dat is waar iemand kijkt die dit voor het eerst doet.

### 62.7 Wat dit voorstel niet doet

- **Geen instelbare lijst van verwijzingen.** Dan wordt het paneel een launcher,
  en dat vraagt om een beheerscherm dat niemand gevraagd heeft.
- **Geen iframe**, om de reden van §62.2.
- **Geen tweede vraag over de kiosk** (§62.3).
## 63. Een leesfout tijdens het opstarten is geen leesfout

**Gevonden op productie, 2026-08-11**, door Sven bij zijn eigen installatie.

Zijn logboek stond vol met *"Bron niet beschikbaar"* voor alle drie zijn bronnen
— prijs, omvormer en slimme meter — met reden `invalid_entity_state`, terwijl die
sensoren in Ontwikkelhulpmiddelen gewoon een waarde gaven.

### 63.1 Wat het werkelijk was

**Drie integraties die op precies hetzelfde moment stilvallen, is geen eigenschap
van die integraties.** Het waren herstartmomenten.

Wij worden opgezet zodra onze eigen afhankelijkheden klaar zijn — `http`,
`frontend`, `panel_custom`, `websocket_api` en sinds 0.25.0 `recorder` — en Home
Assistant zet integraties parallel op. Op dat moment bestaan `sensor.solaredge_…`,
de prijssensor en de P1-meter nog niet. `async_config_entry_first_refresh()` leest
dan een wereld die nog niet af is, alle bronnen falen tegelijk, en drie regels
gaan het logboek in.

**Feitelijk juist en praktisch onzin**: een seconde later bestaan ze wel.

De aanname die dit blootlegt, in de vorm van §47:

> **"Als ik lees, bestaat de wereld al."** Waar bij elke herberekening behalve de
> allereerste.

### 63.2 Twee dwaalsporen die de diagnose kostten, en wat ze leren

**De verouderingsregel (§47) leek de dader** — drie bronnen die stilvallen terwijl
hun waarde klopt, is precies wat een te krap venster doet. Wat het uitsloot was
één rekensom: `last_reported` loopt altijd gelijk of vóór op de *laatst
bijgewerkt* die Ontwikkelhulpmiddelen toont. Was die vier minuten oud, dan kon de
meting niet ouder zijn — en de vensters zijn vijftien minuten en vier uur.

**"Na 21:38 niets meer in het log" leek te bewijzen dat de coordinator stilstond.**
Dat bewijst niets: die regel komt uit `storage.py`, en daar zit de anti-spam. Een
mislukte bron wordt per onderwerp één keer gemeld en daarna niet meer. Zowel *"hij
draait en faalt nog steeds"* als *"hij draait niet"* zien er identiek uit.

Wat het wél besliste was *Laatste berekening* op het Overzicht: die liep mee, dus
de motor draaide gewoon door.

**En de ontbrekende energiescore was geen storing maar het ontwerp** (§35): 's
avonds levert de zonne-as niets en bij een vast contract vervalt de prijs-as, dus
er is geen cijfer. De tegel zei het ook.

> Alle drie de dwaalsporen hadden dezelfde vorm: een waarneming die klopte, en een
> gevolgtrekking over een ander onderwerp dan de waarneming ging (de tiende
> variant in CLAUDE.md).

### 63.3 Wat er gebouwd is

1. **Tijdens het opstarten wordt een bronfout niet gemeld.** Zij gaat naar het
   debuglog, waar zij een ontwikkelaar wel iets zegt, en niet naar het logboek van
   de klant. Een fout die alleen over timing gaat is geen uitspraak over de
   installatie.
2. **Een herberekening op `async_at_started`.** Dat is het moment waarop de
   bronnen van een klant bestaan.
3. **Pas daarna** beoordeelt de motor een bron als niet beschikbaar.

De eerste berekening bij het opzetten blijft staan: zonder haar hebben onze
entiteiten geen waarde tot HA klaar is met starten, en dat kan bij een grote
installatie minuten duren.

**Waarom `async_at_started` en niet alleen de state-listener.** Die listener vangt
het gewone geval al — verschijnt een bron later, dan is dat een statuswijziging.
Maar dan hangt het herstel af van de vraag óf er nog iets verandert, en een
prijsbron die per uur schrijft verandert een uur lang niet. Tot dan zou de klant
een oordeel over zijn installatie krijgen dat op een halve wereld rust.

### 63.4 Wat er met opzet niet gebeurt

**De bronintegraties komen niet in `after_dependencies`.** Dat zou betekenen dat
wij moeten weten welke integraties een klant gebruikt — SolarEdge, Frank Energie,
een P1-lezer — en dat is precies de discovery die regel 1 van CLAUDE.md verbiedt.
De volgorde is een probleem van het moment, niet van de configuratie, en zij wordt
op het moment opgelost.

### 63.5 De reparatie deugde niet, en waarom niet

**Gevonden op productie, 2026-08-12**, door Sven in zijn eigen logboek van de dag
ervoor. §63.3 is gebouwd en heeft **acht herstarts op één dag laten passeren**.

Op 11 augustus staan acht expliciete `homeassistant.restart`-aanroepen: 15:41:33,
16:02:30, 17:12:55, 18:42:06, 20:51:01, 20:53:33, 21:38:02 en 23:32:45. Elk
meervoudig bronincident in het logboek valt binnen enkele seconden na een van die
acht. Bij vier ervan staat er bovendien een losse melding vlak **vóór** de afbraak.

#### Wat er misging in §63.3

De poort was één toestandsvergelijking: `hass.state is CoreState.running`. Geen
venster, geen drempel, geen getal — en dus ook niets om te verruimen.

> **`CoreState.running` betekent "Home Assistant is klaar met opstarten". De
> logboekregel beweert "deze bron is stuk". Dat zijn twee verschillende
> onderwerpen, en ze lopen uiteen in precies de seconden na elke herstart.**

Want de entiteiten *bestaan* dan wel. `sensor.slimme_meter` staat bij elke
herstart op `unknown`: de integratie is opgezet, de entiteit is geregistreerd, en
het eerste telegram is nog niet binnen. §63.1 beschreef alleen het geval dat de
entiteit er nog niet is, en heeft daarmee de helft van de werkelijkheid gemist.

De aanname die dit blootlegt, opnieuw in de vorm van §47:

> **"Zodra Home Assistant gestart is, heeft elke bron een waarde."** Waar voor
> alles wat bij het opzetten al een meting meekrijgt. Onwaar voor een
> Modbus-poller, een P1-lezer vóór zijn eerste telegram, MQTT zonder retain en een
> uurlijkse prijsbron.

#### De werkelijke oorzaak zat één regel eerder

`read_entity_value` gaf **vier verschillende werelden dezelfde uitkomst** —
`unavailable=True`, reden `invalid_entity_state`:

1. de entiteit staat niet in de state machine;
2. de entiteit is er en staat op `unavailable`;
3. de entiteit is er en staat op `unknown`;
4. de entiteit is er, heeft een waarde, en die is te oud (§47).

Twee daarvan zijn een uitspraak over de installatie en twee niet, en dat verschil
werd weggegooid door `UNUSABLE_ENTITY_STATES`, één verzameling met één lezer.

**Home Assistant maakt het onderscheid zelf.** Een entiteit wordt `unavailable`
geschreven wanneer haar integratie `available = False` zet — een uitspraak dat het
apparaat niet bereikbaar is. Zij wordt `unknown` wanneer de entiteit beschikbaar
is en haar waarde `None` is: levend, nog geen meting.

#### 63.5.1 Wat er gebouwd is

**Vijf reden-codes waar er één was.** `entity_missing`, `entity_without_value`,
`entity_unavailable`, `entity_stale`, en `invalid_entity_state` voor wat overblijft
— aanwezig en rapporteert iets onbruikbaars.

**Eén predicaat beslist wat het melden waard is**, in de coordinator, en er staat
geen tweede poort meer naast. Het houdt drie dingen tegen:

1. Home Assistant draait niet (uit §63, nu ingesloten in plaats van ernaast);
2. de entiteit is er niet of heeft nog geen waarde — geen fout maar een
   onbeantwoorde vraag;
3. deze bron is in dit proces nog nooit met succes gelezen. *"Deze installatie
   heeft een kapotte bron"* veronderstelt dat je weet dat hij ooit werkte.

Al het overige wordt onmiddellijk gemeld. Dat geldt met nadruk voor een verkeerd
gekoppelde entiteit — verkeerde eenheid, verkeerd attribuut — want dat is een
staande configuratiefout en geen moment.

**Het "eerder levend gezien"-geheugen** staat in het geheugen van het proces, naast
de latches, en gaat nooit naar de storage (regel 9). Het wordt gewist bij een
configuratiewijziging, omdat een bewerking de entiteit achter een bron kan
veranderen en de gezondheid van de oude dan voor de nieuwe zou tekenen.

#### 63.5.2 Wat er met opzet níét gebouwd is

**Geen melddrempel, geen wachttijd, geen aantal pogingen.** De acht herstarts
werden beslist door 0,2 tot 4,3 seconden en bij de achtste wonnen de bronnen de
race. Elk getal verschuift zo'n race in plaats van haar op te heffen, het zou een
constante zijn zonder eerlijk *"dit geldt omdat…"*, en het zou de enige echte
storing in de dataset — de SolarEdge-uitval van 23:00 — verbergen.

**Geen herkenning van "wij gaan zo uit".** Vier meldingen staan vlak vóór de
afbraak, waarvan één 3,1 seconde vóór de service-aanroep. `CoreState.stopping`
wordt pas binnen `async_stop()` gezet, ná de configuratiecontrole van de
`homeassistant.restart`-service, dus alles daarvóór is van buiten niet van normaal
draaien te onderscheiden. Een machine weet niet dat zij herstart gaat worden, en
een ontwerp dat dat moment probeert te herkennen gokt. Wat de afbraakkant wél dekt
is de classificatie zelf: een entiteit die verdwijnt of naar `unknown` gaat is
voortaan stil, een entiteit die naar `unavailable` gaat niet — en die grens trekt
de eis dat 23:00 gemeld moet blijven, niet een keuze van ons.

#### 63.5.3 De grens tussen 23:00 en 21:38

| Situatie | Toestandswoord | Eerder levend gezien | Uitkomst |
|---|---|---|---|
| 23:00, omvormer valt uit na een avond leveren | `unavailable` | ja | **melden** |
| 21:38, P1 na een herstart | `unknown` | nee | stil |
| 21:38, een bron die zich na een herstart onbereikbaar meldt | `unavailable` | nee | stil |
| afbraak, entiteit verdwijnt | — | ja | stil |
| installateur koppelt een verkeerde eenheid | waarde | n.v.t. | **melden** |
| §47, bron valt stil bij vol daglicht | waarde, te oud | ja | **melden** |

Twee criteria houden die rijen uit elkaar, en allebei zijn ze tijdloos: **welk
woord de integratie schreef**, en **of wij deze bron ooit hebben zien werken**.
`tests/test_coordinator.py::test_which_failed_reads_reach_the_logbook` is die
tabel, één rij per situatie.

#### 63.5.4 De assertie die het defect vastlegde

`test_the_same_source_is_reported_once_home_assistant_has_started` eiste dat een
onleesbare bron gemeld werd op het moment dat Home Assistant op `running` sprong.
Onder het oude model was dat juist. In Svens huis is dat precies het moment waarop
de P1 nog niets gestuurd heeft, dus de test verifieerde actief het gedrag dat de
klant acht keer op één dag trof. Hij is vervangen door de tabel hierboven.

**Wat een unittest hier principieel niet kan**: hij schrijft de state een moment
voordat hij hem leest, dus elke entiteit is altijd vers en er is nooit een
herstart. Het bewijs voor deze reparatie komt uit een productielogboek, niet uit
de suite (achtste variant in CLAUDE.md).

#### 63.5.5 Wat hier niet bij hoort

**De SolarEdge-uitval van 23:00 is een eigen spoor.** Vijf nachten op rij, altijd
alleen de omvormer, pymodbus `[Errno 111]` naar `192.168.1.51:1502` terwijl de rest
van de woning op `192.168.3.x` zit. Dat is een echte storing en de enige legitieme
bronmelding in de dataset; zij hoort gemeld te blijven en wordt apart onderzocht.

### 63.6 Het logboek spreekt niet meer over nu

**Gevonden op productie, 2026-08-12**, door Sven bij het natrekken van de
SolarEdge die 's nachts zijn modbus-server uitzet.

Zijn logboek zei om negen uur 's ochtends nog steeds:

> *"De energiebron 'Solaredge' is niet bereikbaar … er is **op dit moment** geen
> meting."* — geschreven om 23:00, gelezen om 09:00, met de omvormer alweer twee
> uur aan het leveren.

**Een blijvend register dat in de tegenwoordige tijd spreekt, veroudert tot een
onwaarheid.** Dat is geen ruis maar een onware mededeling, elke ochtend opnieuw,
en het was de zwaarste kostenpost van de hele afweging rond de nachtelijke
meldingen.

#### 63.6.1 Wat er gebouwd is

**Een logboekregel kan afgesloten worden.** `LogEntry` krijgt `resolved_at`: het
moment waarop de situatie voorbij was. Geen nieuwe gebeurtenis, geen tweede
regel — het paneel zet er één zin bij, *"Opgelost om 07:02."*

**De tegenwoordige tijd gaat uit de tekst.** De regel draagt haar tijdstip al;
de zin gaat over het moment waarop zij geschreven werd.

#### 63.6.2 Waarom afsluiten en geen eigen `source_recovered`

Een eigen gebeurtenis is append-only en op het eerste gezicht zuiverder, maar
zij kost drie dingen: zij verdubbelt het aantal regels tegen een logboek dat op
`MAX_LOG_ENTRIES` staat, zij dwingt de lezer twee regels te koppelen die uren
uit elkaar liggen, en een flikkerende bron levert er 2N in plaats van N.

**En de belofte waar dit tegenaan leek te lopen, is smaller dan zij klinkt.**
De README zegt *"the last 200 events, with identical consecutive events
collapsed"* — en dat samenvouwen ís het bijwerken van een bestaande regel:
`_collapse_into_recent` verhoogt haar teller, zet haar timestamp op nu en
verplaatst haar naar voren. Een einde toevoegen is dezelfde handeling met een
ander veld. Geen tekst wordt herschreven, geen regel verdwijnt.

#### 63.6.3 Drie dingen die het ontwerp bijna verkeerd deden

**Geen tijdvak.** Een samengevouwen regel draagt het tijdstip van haar
*laatste* keer, niet van haar eerste; er is nergens een begin opgeslagen. "23:00
tot 07:02" zou dus een verzonnen duur zijn voor elke regel met een teller boven
één. Het paneel toont daarom een moment en geen span.

**Een afgesloten regel mag wél opnieuw samenvouwen.** De eerste versie van dit
ontwerp verbood dat, zodat een vastgelegd einde niet gewist kon worden. Loop het
door: storing, herstel, storing → de tweede storing kan niet samenvouwen in de
afgesloten regel en schrijft er een nieuwe. Een bron die elke minuut flikkert
krijgt dan één regel per cyclus, wat precies de schrijfamplificatie is waarvoor
het samenvouwen bestaat. Binnen het venster is het één situatie met een teller,
en het einde van de vorige keer is geen regel per flikkering waard.

**Geen tijdstip in de opgeslagen berichttekst.** De tegenwoordige tijd gaat
eruit zonder dat er een klok voor in de plaats komt.

> **Correctie, 0.30.0.** Hier stond dat het samenvouwen "onder meer op de tekst"
> matcht en dat een zin met een klok erin daarom nooit meer zou samenvallen. Dat
> is onjuist: `_collapse_into_recent` vergelijkt **alleen** `event_type` en
> `subject`, en overschrijft titel en bericht juist met die van de nieuwe
> gebeurtenis. De regel blijft staan, de reden was verkeerd.
>
> De juiste reden is dat de regel haar moment al als gegeven draagt
> (`timestamp`, en sinds 0.29.0 `resolved_at`). Een klok in de zin bakken slaat
> hetzelfde feit een tweede keer op, in de opmaak en de tijdzone van de
> *backend*, terwijl het paneel de tijdstempel opmaakt voor wie hem leest. Twee
> kopieën van één feit lopen uiteen; welke van de twee dan waar is, valt niet
> meer uit te maken.
>
> **En daarom mag het paneel het wél.** Wat het paneel uit `timestamp` en
> `resolved_at` opmaakt is geen opgeslagen zin. Deze paragraaf verbood
> onbedoeld de reparatie van §63.6.4, waar de dag erbij hoort zodra de sluiting
> op een andere dag valt.

#### 63.6.4 Het afsluiten hangt aan de gebeurtenis, niet aan de ledger

De anti-spamledger staat in het geheugen. Zou het afsluiten daarvan afhangen,
dan laat een herstart om drie uur 's nachts — met de omvormer weg — een regel
achter die niemand meer kan sluiten: **voor altijd open, een nieuw soort
liegende regel in plaats van het oude.**

Daarom sluit een bron die schoon leest haar open regels, of dit proces ze nu
heeft zien ontstaan of niet.

##### Álle open regels van dat onderwerp, niet alleen de nieuwste (0.30.0)

Hier stond: *"alleen de nieuwste per onderwerp: een oudere beschrijft een
eerdere episode die haar eigen einde had, vastgelegd of niet."* **Die premisse
wordt door de schrijfkant niet waargemaakt.** `_mark_reported` sleutelt op
onderwerp én reden, dus er komt een tweede regel bij zonder dat er iets
hersteld is. Twee routes, allebei bereikbaar:

- **de storing verandert van karakter** — stilgevallen naar onbereikbaar, of
  onbereikbaar naar een niet-numerieke waarde, meer dan
  `LOG_DEDUPE_WINDOW_MINUTES` uit elkaar. Binnen dat venster vouwen ze samen tot
  één regel met een teller, dus **het samenvouwvenster is letterlijk de grens
  tussen één eerlijke regel en twee waarvan er één gaat liegen**;
- **een herstart terwijl een verkeerd gekoppelde bron blijft falen** — de ledger
  is leeg, `invalid_measurement` heeft geen eerdere geslaagde lezing nodig, en er
  is nooit een schone lezing om iets te sluiten. Die stapel groeit zonder
  bovengrens, en sloot een reparatie er dan één van, dan bleven de andere voor
  altijd beweren dat de bron stuk was — precies de liegende regel waarvoor dit
  afsluiten bestaat.

Dit is de negende variant: twee plekken beantwoordden *"wat is één episode?"*
verschillend, en elke test toetste zijn eigen kant.

**Gemeten op een klantinstallatie, 2026-08-12:** 112 regels gingen dicht met één
per herberekening, tien minuten lang, elk met een eigen stempel en geen enkele
een herstel. Onder de dagkop van het paneel las een regel van 23:32 daardoor
*"Opgelost om 12:49"* — elf uur vóór zichzelf, want die 12:49 was de dag erna.

##### Het stempel is wat wij zagen, niet wat er gebeurde

Wij weten niet wanneer een bron het weer deed; wij weten wanneer een
herberekening haar schoon las. Dat scheelt tot vijf minuten via het
veiligheidsinterval, en over een herstart of een upgrade heen willekeurig veel.
Voor elke regel behalve de nieuwste van een stapel is het stempel dus een
**bovengrens** en geen meting.

Daarom zegt het paneel **"Weer uitgelezen"** en niet "Opgelost", met hetzelfde
werkwoord als de storingszin ernaast (*"kon niet worden uitgelezen"*), en staat
de dag erbij zodra de sluiting op een andere dag valt dan de regel zelf. Dat
laatste is geen opgeslagen tekst maar opmaak van twee tijdstempels — zie de
correctie in §63.6.3.

Eén schone lezing sluit de hele stapel in één pas, dus ook met één schrijfactie
in plaats van één per regel.

#### 63.6.5 De regressie van 0.28.0, meegenomen

**§63.5 introduceerde een fout die in 0.28.0 is uitgeleverd.** Sinds die versie
filtert de coordinator de stille meldingen weg vóórdat de storage ze ziet, en de
vergeet-lus daar verwijdert elk onderwerp dat niet in `still_invalid` zit. Een
gefilterde melding was dus niet te onderscheiden van een herstel: een bron die
van `unavailable` naar `unknown` ging en uren later terugviel, kreeg een tweede
regel voor dezelfde storing.

Met het afsluiten erbij zou het erger worden — er kwam dan *"opgelost"* te staan
op het moment dat de bron juist stiller werd. Daarom hoort de reparatie in
dezelfde ronde.

De coordinator geeft de storage nu drie dingen in plaats van één: wat het melden
waard is, **wat nog steeds faalt of het nu gemeld werd of niet**, en wat schoon
leest. Alle drie op één plek berekend, dus er komt geen tweede oordeel bij.

**En één bug die er al in zat kwam mee.** De verzameling "bronnen die
antwoordden" was *alle* rijen min de ongeldige, terwijl de calculator een
uitgeschakelde of onvoltooide rij helemaal overslaat — die telde dus als
zojuist met succes gelezen. Onschadelijk zolang het antwoord alleen het
eerder-levend-geheugen voedde, want een uitgeschakelde rij levert geen fouten
op. Niet onschadelijk zodra diezelfde verzameling logboekregels afsluit, want
dan leest "uitgezet" als "gerepareerd". De vijfde variant: een waarde die niets
las tot er gedrag aan hing.

#### 63.6.6 Wat hier niet in zit

Het nachtelijke zwijgen zelf. Een omvormer die 's nachts **onbereikbaar wordt**
levert nog steeds een melding op, en de datakwaliteit zakt er vijftien punten
van — vijftien wanneer alle zes checklistitems van toepassing zijn, en meer
wanneer er minder items meetellen (bij vier is het twintig).

> **Voorwaardelijk gemaakt op 2026-08-13, en dat is een correctie op de vorm van
> deze zin.** Hier stond dit als een eigenschap van de nacht. Het is een
> eigenschap van *sommige omvormers*.
>
> **Gemeten, één woning:** een SolarEdge via `solaredge_modbus_multi` houdt zijn
> modbuspoort 's nachts open en meldt gewoon 0 W. Een geldige nul vinkt het
> zonne-item af — het item is `snapshot.solar_power_w is not None` — dus daar
> zakt er niets. Vastgelegd in
> `test_a_nightly_zero_still_ticks_the_solar_item`.
>
> **Ongemeten:** een omvormer die zijn poort wél sluit. Die klant bestaat
> vermoedelijk en wij hebben hem niet gezien. Voor hem geldt de zin hierboven
> onverkort, elke nacht opnieuw.
>
> **Daarom is `sun.is_up` geen opgelost punt maar een onbekende**, en staat het
> niet meer in de eerstvolgende ronde. Het wachten is op een installatie die het
> verschijnsel werkelijk vertoont; een mechanisme bouwen voor een geval dat
> niemand heeft gezien is wat §38 hier heeft opgeruimd. Zie `HARDWARE.md` voor
> wat er per merk wél waargenomen is.

### 63.7 Een meting die één tel lang onmogelijk is, en waar zij kantelt

Vastgelegd op 2026-08-13. **Dit is een aantekening, geen bouwopdracht**: er komt
geen drempel en geen filter, om de reden in HARDWARE.md regel 2.

Een vermogensbron kan één meting lang een waarde melden die fysiek niet kan
(waargenomen bij een SolarEdge, kort na de eerste opwek van de dag). Er is
nergens in de motor een plausibiliteitsgrens: alleen NaN en oneindig worden
geweigerd, en voor zon geldt `SOLAR_COMPONENT_MIN_PRODUCTION_W = 0.0`, dus één
watt telt als opwek.

**Wat er dan misgaat hangt af van de woning, en die grenzen volgen uit de
formules — er is geen tweede woning voor nodig.**

#### Score-inflatie, woning mét netmeter

`zelfbenutting = (opwek − teruglevering) / opwek`, waarbij de **teruglevering van
de netmeter** komt en de **opwek van de zonnesensor**. De spookwaarde zit dus
alleen in de noemer.

- Levert de woning op dat moment niets terug, dan is teller gelijk aan noemer en
  is de uitkomst **100%, wat de piek ook doet**. Er beweegt niets.
- Levert zij wél terug — dus echte opwek *b* > huisverbruik *V* — dan is de ware
  waarde `V/b` en de vervuilde `(P − (b − V)) / P`, die naar 100% loopt naarmate
  *P* groeit. **De richting is altijd omhoog.**

**Kantelpunt: `V < b` op het moment van de piek.** Omdat een piek juist zichtbaar
is bij een kleine basislijn, vraagt dit een woning die op dat moment onder enkele
tientallen watt trekt.

#### Vals zonneadvies, woning zónder netmeter

Daar is `overschot = opwek − verbruik`, dus de spookwaarde komt er rechtstreeks
in. Vier dingen moeten samenvallen:

1. `P_piek − V ≥ min_solar_surplus_w` (standaard 500 W);
2. een apparaat past — `nominal_power_w ≤ overschot`, of `min_power_w ≤ overschot`
   bij modulatie, **of het vermogen is onbekend en dan passeert het ongetoetst**;
3. `prefer_solar` aan, en geen batterij die het overschot onbetrouwbaar maakt;
4. de herberekening moet die ene seconde raken.

**Kantelpunt: `P_piek ≥ V + min_solar_surplus_w`.**

#### Wat dit is en wat niet

Op de enige woning waar dit gemeten is, wordt geen van beide grenzen gehaald: de
piek van 499 W ligt onder het huisverbruik van ~520 W, en er is een netmeter.
**Dat is een meting aan één woning, geen weerlegging.** Voor een woning zonder
netmeter, met een lagere overschotdrempel, met laag sluipverbruik of met een
apparaat zonder ingevuld vermogen is dit **ongemeten**.

## 64. Compleet ingevuld is niet hetzelfde als bruikbaar

Twee plekken zeiden dat het goed zat terwijl de motor de bron zojuist geweigerd
had. Eén payload, twee lezers, en beide lazen alleen de configuratie.

### 64.1 Wat er te zien was

**De bronrij zei "Compleet."** `statusOf()` liep de configuratie langs — type
bekend, ingeschakeld, geen veldfouten — en concludeerde daaruit dat de rij in
orde was. Of de motor de entiteit een seconde eerder had kunnen lezen, kwam er
niet in voor. Dus stond er *"Compleet."* op een rij waarover het logboek op
datzelfde moment een waarschuwing schreef.

**En het Overzicht zei "Alle gegevens zijn ingevuld."** De checklist telt
*onderdelen*, en niet elke bron is er een. Een thuisbatterij, een tweede
verbruiksmeter of een terugleverprijs die geweigerd wordt laat het cijfer op 100
staan: geen enkel item ontbreekt, en toch doet er een rij niet mee.

### 64.2 De twee zinnen claimen met opzet niet hetzelfde

**Het Overzicht claimt het minst:** *dát* er een bron buiten het cijfer valt.
Meer kan het niet dragen, want `invalid_items` bevat zowel een onvoltooide rij
als een onbereikbare, en die vragen om verschillende dingen van de lezer.

**De bronrij claimt het precieze**, en kan dat omdat zij per rij oordeelt en
haar volgorde dat afdwingt: onbekend type, uitgeschakeld, vervallen type en
veldfouten komen eerst. Wie die zeef passeert en tóch geweigerd is, is compleet
ingevuld en op dit moment niet uit te lezen.

**De volgorde is het hele mechanisme.** Een onvoltooide rij wordt door de motor
óók geweigerd en staat dus óók in `invalid_items`. Zou de nieuwe tak vóór de
veldfouten komen, dan kreeg een installateur *"niet uit te lezen"* te zien op
een rij waar hij domweg nog een veld moet invullen — een tekortkoming die niet
van toepassing is, gepresenteerd als storing, voor de zesde keer.

### 64.3 Waarom niet één van de twee volstaat

Het scherm toont een feit over het moment, het logboek legt een oordeel vast
(§63.5). Deze ronde voegt daar niets aan toe; zij haalt alleen weg dat het
scherm het feit **tegensprak**. Het Overzicht wijst door naar Energiebronnen, en
daar staat per rij wat eraan schort — zodat de vraag *"welke dan?"* een antwoord
heeft op de plek waar hij gesteld wordt.

Zolang er nog geen berekening is geweest, zwijgen beide: er is dan niets
waargenomen, en "in orde" of "kapot" beweren zou allebei een gok zijn.
