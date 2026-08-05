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
