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
| 3 | `power_entity` | zakt onder een drempel en blijft daar N minuten |

Methode 3 is de zwakste: een pauze midden in een programma lijkt erop. Drempel en
wachttijd zijn vaste constanten, afgeleid van `nominal_power_w`, en de detectie is
**edge-triggered** — van "draait" naar "klaar" — zodat er niet elke seconde een
schrijfactie volgt.

De statenlijst bij methode 1 is vast en wordt gedocumenteerd. Meldt de entiteit iets
anders, dan is er geen detectie; er wordt niet geraden welke toestand "klaar" zou kunnen
betekenen.

**Is er geen enkele entiteit gekoppeld, dan wordt er niet gegokt.** Het paneel zegt erbij
dat we niet kunnen zien wanneer het apparaat klaar is, en de bewoner zet de vlag zelf uit.

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
| brontype `price_forecast` | keuzelijst Energiebronnen | een volledig brontype dat niets doet |
| brontype `solar_forecast` | keuzelijst Energiebronnen | idem |

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
| `validators.has_errors` | **dood.** Bestaat, wordt getest, en wordt door niets gebruikt — noch door de motor, noch door de WebSocket-API, noch door het paneel. Kan weg. |
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
