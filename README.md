# DomotiApp Energy

A manually configured energy coach for Home Assistant.

DomotiApp Energy turns the energy sources and appliances you connect **by hand** into an
energy summary, a data completeness score, an energy score, advice, and grid peak
warnings. Everything is calculated locally: no cloud service, no external API, no
account, and no AI provider.

> DomotiApp Energy does not automatically discover, select, or control devices in version 0.1.0.

> The DomotiApp Energy Score is a local advisory indicator and not a certified energy-efficiency rating.

The user interface is in Dutch; the code, entity IDs and this README are in English.

## What it does in 0.1.0

- **Reads what you link.** A grid meter, solar production, a price source, a home
  battery, general consumption — each one an entity you pick, with a unit you state.
- **Derives what your home is actually using.** Grid power is a *net* figure, not
  consumption: a home exporting 2400 W while producing 3000 is using 600. That figure is
  now on screen, from `grid + production − battery`, and it is absent rather than guessed
  when a configured source cannot be read.
- **Normalises it.** Grid power to "positive means import", battery power to "positive
  means charging", a bare market price to an all-in price. One convention per quantity,
  applied once, on reading.
- **Scores two things.** A data completeness score (how much of the picture is
  configured, `SPEC.md` §16) and an energy score (how much of what this home could have
  used well at this moment, it actually used — `SPEC.md` §35). Both are transparent and
  documented; the energy score deliberately shows no number when there is nothing to
  measure, and says why.
- **Advises.** Missing data, grid peak load in either direction, solar surplus, and a
  high or low dynamic price — each with a stable reason code, the measurements behind
  it, and an estimated saving where one can be calculated. No advice is given on a
  measurement known to be unreliable: a home battery whose power cannot be read could be
  consuming the whole solar surplus, so the panel names that gap instead of advising on it.
- **Warns about peaks.** Import *and* export: the main fuse limits both directions.
- **Keeps a logbook.** The last 200 events, with identical consecutive events collapsed
  into a counter rather than repeated.

## The strict manual configuration principle

Nothing is guessed. The integration never searches the entity or device registry, never
matches on a name, never scores a candidate and never offers a suggestion. Every link
between this integration and your system is a choice you made in the panel.

Where a value is missing, the answer is "not available" rather than a default. A grid
meter without a stated meter mode is unusable; a price source that does not say whether
it reports the bare market price or the all-in price is unusable. That is deliberate: a
plausible-looking wrong number is worse than an honest gap.

## Privacy and local processing

- No network access of any kind. No external API, cloud service, telemetry, analytics or
  AI provider, and no API key.
- No browser storage. The panel uses no `localStorage`, `sessionStorage`, `IndexedDB` or
  cookies; the backend storage is the only source of truth.
- The logbook stores an event type, a title, a short message, a severity, a subject id
  and, for a source that could not be read, the moment the situation was over. It never
  stores a Home Assistant state object, a location or personal data.
- Home Assistant log lines carry no entity states, home name or location.

## Requirements

- Home Assistant 2025.6 or newer
- Python 3.13 or newer (whatever your Home Assistant runs on)
- No runtime dependencies — `manifest.json` lists `"requirements": []`

## Installation

### Via HACS as a custom repository

1. Open **HACS** in Home Assistant.
2. Open the three-dot menu, top right, and choose **Custom repositories**.
3. Paste `https://github.com/Sven2410/domotiapp-energy` as the repository, choose
   **Integration** as the type, and confirm.
4. Search HACS for **DomotiApp Energy** and download it.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration** and search for
   **DomotiApp Energy**.

### Manually

1. Copy the folder `custom_components/domotiapp_energy` into the `custom_components`
   directory of your Home Assistant configuration. Create that directory if it does not
   exist.
2. Restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and search for
   **DomotiApp Energy**.

The configuration flow asks for a home name and one confirmation: that you understand
the integration configures nothing by itself. Only one instance can be added.

## Setting up your first home

The panel appears in the sidebar as **DomotiApp Energy**. Work through it in this order:

1. **Installatie → Woning** — the number of phases, the main fuse per phase, the maximum grid power
   the integration should warn about, and the contract. On a dynamic contract you also
   fill in the energy tax, the supplier markup and the VAT rate, because a price source
   that reports a bare market price is completed with those three.
2. **Installatie → Energiebronnen** — add your grid meter. Say explicitly how it measures: one signed
   value (and what a positive value means) or separate import and export entities. Add
   solar, a price source, a battery or general consumption as you have them. A price
   source must state whether it reports the all-in price or the bare market price.
3. **Apparaten** — add the appliances you want advice about. The fields marked with an
   asterisk are what the data completeness score asks for: a nominal power and an energy
   per cycle, plus both ends of a time window for anything you marked as flexible.
   A half-filled appliance can be saved; it simply does not count as complete yet.
4. **Mijn voorkeuren** — quiet hours, what may weigh in the advice, the savings threshold
   and how much detail you want to see. This tab belongs to the resident, not to you.
5. **Energiecoach** — the advice, and five fixed questions you can ask about it.
6. **Logboek** — what the integration has signalled.

### On a wall tablet, set the way back

A tablet running Fully Kiosk usually has no sidebar, and then **every link out of this panel
is one-way**: whoever leaves cannot come back.

Fill in **Woning → Navigatie → Terug naar dashboard** with the address of that home's own
dashboard, for example `/lovelace/0`. A back button then appears at the top left of the
panel. Leave it empty and there is no button — which is the right answer for an installation
with a sidebar, where the button would be redundant.

The second field, **Energiedashboard**, does the same for the link to consumption in kWh on
the Overzicht: filled in it is a link, empty it is a sentence that still says where to look.

Nothing is guessed here. `/lovelace/0` would be a claim about how this home is laid out, and
the integration does not make those (see "The strict manual configuration principle").

## The tabs

Six tabs, and **the same six for everybody**. Nothing is hidden from a resident; what he
does not own is shown greyed out, with a line saying who manages it.

| Tab | What it is for |
|---|---|
| Overzicht | **Home consumption** as the headline figure, with the energy score and the data quality beside it; then current grid power, solar production and surplus, self-consumption, percentage of the configured maximum, the current all-in price, the primary advice and any warnings. |
| Energiecoach | The primary advice, further advice with their reasons and measurements, what data is still missing, and the five fixed questions. |
| Apparaten | Add, edit and remove appliances, with their power, energy per cycle, ready window, behaviour flags and optional entity links. A resident sets how each appliance should behave; the rest is the installer's. |
| Mijn voorkeuren | Quiet hours, what weighs in the advice, the savings threshold and what is displayed. Entirely the resident's. |
| Installatie | Two sections. **Woning**: phases, fuse, maximum grid power, contract and prices, net metering and the minimum solar surplus. **Energiebronnen**: add, edit and remove energy sources; only the questions a source type can answer are asked. Read-only for a resident. |
| Logboek | The last 200 events. Read-only for everyone; only an administrator can empty it. |

## Who may change what

The integration is installed by an installer and lived in by a resident, and they own
different things: the installer owns what the home **is**, the resident owns what it must
**do**. A mistake in the first kind is something a resident should be able to *report* —
which is why he can see the main fuse rather than being shown nothing at all.

| | Installer (Home Assistant administrator) | Resident (any logged-in user) |
|---|---|---|
| Installatie | everything | nothing |
| Apparaten | the appliance itself: type, power, energy per cycle, duration, entity links, capabilities, the agreement not to control it | how it behaves: control mode, ready window, days of the week, whether it may be noisy, priority |
| Mijn voorkeuren | — | everything |

An administrator may do everything a resident may.

## Supported source types

| Type | Notes |
|---|---|
| `grid_meter` | At most one enabled. Requires an explicit meter mode: `single_signed` (plus what a positive value means) or `separate_import_export`. |
| `solar` | Current production. Several may be configured; they add up. |
| `current_price` | At most one enabled. Must state `price_basis`: `all_in` or `market`. |
| `price_forecast` | Registered in 0.1.0; not yet used by the engine. |
| `solar_forecast` | Registered in 0.1.0; not yet used by the engine. |
| `home_battery` | Positive means charging. Several may be configured; they add up. |
| `general_consumption` | Household consumption. Several may be configured; they add up. |

Each source states its own unit — `W`, `kW`, `A`, `Wh`, `kWh`, `EUR/kWh`, `ct/kWh`, `%`
or none — and its own scale factor. Conversion follows that choice and nothing else:
never the entity's `unit_of_measurement`, its device class or its name.

## Supported appliance types

`ev_charger`, `home_battery`, `heat_pump`, `electric_boiler`, `dishwasher`,
`washing_machine`, `dryer`, `air_conditioning`, `pool_pump`, `generic_schedulable`,
`generic_monitor`.

Two flags follow from the type unless you say otherwise: `is_noisy` (true for a
dishwasher, washing machine, dryer and pool pump) and `is_flexible` (false for a heat
pump and a generic monitor).

## When the energy score shows a number

The energy score answers one question: **of what this home could have used well at this
moment, how much did it use?** It is not a measure of frugality, not a judgement of the
installation, and not a report card on the household. Switching on the oven at 18:00 is
not a mistake.

That means it needs a signal to measure against, and not every home has one. Rather than
print a number that claims something untrue, the panel shows a sentence saying why there
is nothing to measure.

| What the home has | Which axis applies | When there is a number |
|---|---|---|
| A dynamic contract | price | whenever the price is above the low threshold |
| Panels **and** at least one usable, flexible appliance with a power and an energy per cycle | solar | whenever there is production |
| Panels **and** a home battery | solar | whenever there is production |
| Panels without anything movable | none | never, until something movable is added |
| Panels, but feeding in currently pays better than self-consumption | solar switches off | not from the sun while that lasts; from the price axis if it applies |
| A fixed contract and no panels | none | never |

**An axis switches off when the advice points the other way.** If the feed-in tariff plus
the avoided feed-in cost exceeds the import price, every kWh this home uses itself costs
it money, and the coach says to wait. The solar axis then drops out rather than being
inverted: an inverted axis would score self-consumption of *all* load, including the oven
nobody can move, so raising it would come down to using less electricity — which is
exactly what this score refuses to measure.

The axis is only removed when that margin is **known** to be negative. With a feed-in
tariff or feed-in cost missing the sum cannot be completed, and the axis stays on rather
than a blank field on the installer's form taking the resident's number away.

**Self-consumption is shown either way.** What share of this moment's production the home
uses itself is a measurement, not a verdict, so it appears among the meter readings on
`Overzicht` whenever the grid meter and the inverter can be read — including on the
evenings and in the situations where the score itself is absent.

**The cheapest route to a score is usually not to buy anything.** A dynamic contract
switches the price axis on without changing a thing in the house. Completing an appliance
that is already there — its power, its energy per cycle, marked flexible — switches the
solar axis on for a home with panels, and that is configuration work rather than a
purchase. Hardware comes after that, and for what it does rather than for what it does to
the number.

All advice keeps working in every one of these cases. The score is an extra, not a
precondition.

## Generated entity IDs

These nine are fixed. They do **not** change with the language your Home Assistant runs
in, so dashboards, automations and long-term statistics built on them keep working:

```text
sensor.domotiapp_energy_score
sensor.domotiapp_energy_data_quality
sensor.domotiapp_energy_grid_power
sensor.domotiapp_energy_home_consumption
sensor.domotiapp_energy_solar_surplus
sensor.domotiapp_energy_self_consumption
sensor.domotiapp_energy_current_advice
binary_sensor.domotiapp_energy_peak_risk
binary_sensor.domotiapp_energy_attention
```

**An entity here is a promise.** Customers build dashboards, automations and long-term
statistics on these IDs, so one that ships cannot be taken away again — which is why a new
one is added deliberately rather than because it happened to be available. `state_class`
means Home Assistant keeps its history, and that history is the point of adding one.

The displayed names *do* follow the interface language. `sensor.domotiapp_energy_current_advice`
carries the advice message, reason code, confidence, severity, measurements, the full
advice list and the time of the last calculation as attributes; its state is the advice
title, truncated to what Home Assistant allows.
`binary_sensor.domotiapp_energy_attention` is on when something needs a person — see
[A button on your own dashboard](#a-button-on-your-own-dashboard).

## A button on your own dashboard

One tile that colours when something needs attention, says why, and opens the panel when you
tap it. Core Home Assistant only — no HACS card, no `browser_mod`, no template sensor,
nothing to install alongside.

Paste this into any dashboard:

```yaml
type: tile
entity: binary_sensor.domotiapp_energy_attention
name: Energie
icon: mdi:home-lightning-bolt
state_content: advice_title
tap_action:
  action: navigate
  navigation_path: /domotiapp-energy
```

That is the whole thing. Grey with the current advice underneath when all is well, red with
the reason when something needs you, and one tap into the panel either way.

### What makes it work

`binary_sensor.domotiapp_energy_attention` carries `device_class: problem`, and every core
card colours a `problem` sensor red when it is on — no template, no styling, no card-mod.

It turns on for exactly three reasons, and the shortness of that list is the point: a tile
that is red every evening is a tile nobody looks at.

| Reason | What it means |
|---|---|
| `missing_required_data` | the setup is not finished |
| `high_grid_load` | the connection is near its limit |
| `high_grid_export` | export is near its limit |

A high price is deliberately **not** among them. It is a warning, but it is also the market
twice a day, and nobody can do anything about it at that moment.

All three come from the advice, and that is a rule rather than a coincidence: **whatever
turns the tile on also supplies the sentence beside it.** 0.11.0 also turned it on when a
source could not be read at that moment, while the text kept quoting the advice — so the
tile could go red beside "Geen actie nodig". A `problem` tile that contradicts its own text
is worse than no tile.

The cost is stated plainly: a source that no checklist item asks for — a submeter, a home
battery — can be unreadable without turning the tile red. The panel's own source row, the
data quality figure and the logbook are where that shows.

Three attributes come along for a dashboard to use:

| Attribute | Contents |
|---|---|
| `advice_title` | the advice title — this is what `state_content` puts on the second line |
| `message` | the full sentence |
| `reason_code` | the code, if you want an automation to react to one specific case |

`state_content` accepts an attribute name, which is what lets a single tile carry both the
colour and the sentence. Without it the tile reads "Probleem", which is true and tells you
nothing.

### Kiosk mode: leave the sidebar on

The tile **navigates**; it does not open a dialog. On a wall tablet running Fully Kiosk that
stays inside the same page — no new window, no address bar.

**The way back is the sidebar.** If your kiosk dashboard hides it, there is no route from the
panel to your dashboard, and the tablet is stuck on the energy panel until someone restarts
the app. Either leave the sidebar visible, or put a tile on your dashboard *and* accept that
the trip is one-way.

### Why not the other shapes

Verified against Home Assistant 2026.7:

| Shape | Why not |
|---|---|
| `button` card with `state_color: true` | works and colours, but shows "Probleem" rather than the advice |
| `conditional` card around two tiles | works, needs two cards for one button, and the colour is the only difference |
| more-info as the detail view | does not render entity attributes at all, and cannot navigate onward |
| `browser_mod` pop-up | a dependency on every installation, for a view the panel already is |
| a `template` binary sensor in `configuration.yaml` | worked, but put a copy of our definition in every customer's config — which is where drift starts |

## The logo in Home Assistant and HACS

Artwork goes in **`custom_components/domotiapp_energy/brand/`** — that folder has a README
listing the files and sizes. Home Assistant serves whatever is there and prefers it over
the brands CDN; no manifest entry and no configuration are involved.

**There is no pull request to submit.** Since Home Assistant 2026.3 a custom integration
carries its own brand images, and `home-assistant/brands` no longer accepts pull requests
for custom integrations — its own pull request template says so, and recent
custom-integration submissions there are closed unmerged. That is also why
`.github/workflows/validate.yml` keeps `ignore: brands`: the HACS action checks for a
domain in that repository, and ours will never be there.

Verified against Home Assistant 2026.7.4: with `brand/icon.png` in place,
`/api/brands/integration/domotiapp_energy/icon.png` returned that exact file and the
artwork appeared on the integration page.

**One caveat, and it is not ours to fix.** The HACS dashboard still reads icons from
`data-v2.hacs.xyz` and shows a blank tile for integrations that only ship local brand
images — an open HACS issue
([hacs/integration#5171](https://github.com/hacs/integration/issues/5171)) with a fix
proposed. Everywhere inside Home Assistant itself the local file is used.

## Services

| Service | What it does |
|---|---|
| `domotiapp_energy.recalculate` | Recalculates the advice immediately. Controls nothing. |
| `domotiapp_energy.clear_log` | Empties the internal logbook. Changes no configuration. |

Both are available to administrators. A call without a user — from an automation or a
script — is allowed.

## Limitations

- **Nothing is controlled.** The integration measures, calculates, advises and warns.
  The `capabilities`, `control_mode` and `control_forbidden` fields are recorded for a
  later release; in 0.1.0 everything except `monitor_only` behaves as `advice_only`.
- **No forecasts are used yet.** `price_forecast` and `solar_forecast` can be
  configured, but the engine does not read them.
- **History is three facts about yesterday, and it will never claim what you saved.** Every calculation looks at
  the present moment only. A historical overview is planned, and two things are settled
  about it in advance because they are what people ask first:

  - **Consumption stays with Home Assistant's own Energy dashboard.** It reads your
    meters directly, in kWh. Anything built here from power readings would be a worse
    copy of a screen you already have.
  - **It will never say what this integration saved you.** The coach advises; it does not
    control, and nothing here knows whether you followed the advice. A euro figure would
    need a version of last week in which you did not — and that version does not exist.
    What it can show is what the coach saw, what it said, and what happened next.
- **The energy score jumps, and is often absent.** It reads one moment, so a component
  stepping in or out moves the number without anybody doing anything: a home whose solar
  axis reads 30 in the afternoon can read 90 in the evening on the price axis alone. A
  score over a window is the real answer and needs its own design. Absence is deliberate
  and explained in the panel — see "When the energy score shows a number".
- **`sensor.domotiapp_energy_score` is `unknown` whenever there is no number**, which
  leaves gaps in the long-term statistics. A daily average over this sensor is not
  meaningful; use the data quality sensor for "is this installation complete".
- **Peak risk is measured across the whole connection, not per phase.** The maximum grid
  power is one figure for the house and the grid reading is the sum over the phases. On a
  three-phase connection the real overload is almost always on a single phase — 25 A on L2
  while the total sits at 40% does not raise a warning. This matters most in exactly the
  installation it is most likely to occur in: three phases with an EV charger, where the
  charger causes the imbalance. Per-phase bindings are planned for a later release; until
  then, size `max_grid_power_w` with this in mind.
- **One instance.** A second configuration entry is refused.
- **A price source is refused when it cannot be normalised.** No basis, or a market
  price without the energy tax and supplier markup, means no price rather than a guess.
- **Advice is not a schedule.** It says what is favourable now; it does not plan.
- **A reading older than 15 minutes is refused.** Home Assistant keeps the last state of
  an entity forever, so a meter that stops reporting would otherwise look current. The
  source is reported as unavailable instead, which is the honest answer.
- **Answers are deliberately slow to change.** Thresholds switch on at their configured
  level and off only once the measurement has moved back past a margin, and the headline
  advice stays put for at least a minute unless something more urgent arrives. A smart
  meter reports every second, and without this the warnings and the estimated saving
  flickered on and off continuously. The margins are fixed and not configurable.

## Troubleshooting

### Removing the integration keeps the energy configuration

Deleting DomotiApp Energy from *Settings → Devices & services* removes the entities and
the device, but **not** the home profile, energy sources, appliances, preferences and
logbook. Those live in `.storage/domotiapp_energy.config` inside your Home Assistant
configuration directory, and adding the integration again picks them straight back up.

That is deliberate: an accidental removal, or a reinstall, should not cost you a full
re-entry of every source and appliance. Home Assistant does not let an integration put a
message in the removal dialog, so the only notice is a line in the Home Assistant log
when you remove it.

To start over with an empty configuration:

1. remove the integration in *Settings → Devices & services*;
2. stop Home Assistant;
3. delete `.storage/domotiapp_energy.config` from the configuration directory;
4. start Home Assistant and add the integration again.

Stopping first matters: Home Assistant caches `.storage` files in memory and can write
the old contents back over your deletion.

### The panel shows an old version after an update

The panel is served from a versioned path, so an update changes the URL of every module.
If you still see the previous version, your browser's service worker is serving its own
copy: open the developer tools (F12), right-click the reload button and choose **Empty
cache and hard reload**. A plain Ctrl+F5 is not always enough.

### A source shows "Nog niet compleet"

The row names the field that is missing. A source is stored either way, so you can
finish it later; it is simply not used in any calculation until it is complete.

### There is no price on the Overzicht

Either the contract is fixed — then there is no hourly price and the row says so — or
the price source cannot be used. A price source needs an entity, a unit, and an explicit
statement of whether it reports the all-in price or the bare market price. A market
price additionally needs the energy tax and the supplier markup on the Woning tab.

### What changes on 1 January 2027, when net metering ends

Until that date a fed-in kWh is worth exactly what an imported one costs, so the
savings formula cancels out to `energie × terugleverkosten`. Three things are stored,
shown, and **not used** in the meantime:

| Field | Used before 2027 | Used after |
|---|---|---|
| `Terugleververgoeding (all-in)` | no | yes |
| A `feed_in_price` source | no | yes |
| `Inhouding leverancier op teruglevering` | no | yes |
| `Terugleverkosten` | **yes** | yes |

The feed-in cost is the exception: under net metering it is the *only* term left in
the formula, so it is the one that decides today's figure. The Woning tab says this
next to the fields.

**What will visibly change for a customer on the changeover:**

- Savings amounts start moving with the feed-in tariff instead of only the feed-in
  cost, and generally become larger.
- The sentence "Zolang de salderingsregeling geldt levert dit geen extra besparing
  op" disappears from the advice.
- **A home that never filled in a feed-in tariff loses its savings amount**: the
  calculation needs it from that date, and rather than guess, the coach says which
  field would answer it. Filling it in beforehand avoids this entirely.

The date is per home (`Saldering geldt tot`), so this can be tried early by setting it
to a past date.

### Energiebelasting, opslag and btw are greyed out

The linked price source already reports an all-in price, so there is nothing to
convert and those three fields would never be read. Set the source to the bare market
price if you want to use them, or remove the price source to fill everything in
yourself. The values you already entered are kept either way.

### A price field will not take a comma (or will not take a full stop)

Which decimal separator a number field accepts is decided by **the browser's
language**, not by Home Assistant and not by this integration. A number input parses
according to the browser locale: a Dutch-language Chrome takes `0,241710`, an
English-language Chrome takes `0.241710` and silently rejects the comma. If a tariff
will not go in, this is almost always why — try the other separator before assuming
the field is broken.

The step is not the cause. Every €/kWh field accepts six decimals, which is what a
supplier bills; a figure like 0,241710 goes in exactly.

## Development

```bash
# Linting, in a local virtualenv
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install ruff
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format .

# Python tests, in the test container
.\scripts\test.ps1
.\scripts\test.ps1 tests/test_storage.py -k revision
.\scripts\test.ps1 --cov=custom_components/domotiapp_energy --cov-report=term-missing

# Frontend tests (jsdom + node --test)
npm install
npm test
```

`scripts/ha_check.py` verifies a running Home Assistant over its REST and WebSocket
APIs: it reads the six entities and can send `domotiapp_energy/*` commands. It uses the
standard library only and adds nothing to the integration.

The panel has no build step and ships no JavaScript dependencies. `package.json` exists
solely for the frontend test layer.

## Security notes

- **`require_admin` guards installer fields, not every write.** The commands that change
  the home profile, the sources, a whole appliance row or the logbook require an
  administrator. `preferences/update` and `devices/set_operation` do not, because every
  field they can reach belongs to the resident — see "Who may change what" above. Both do
  change the configuration and do raise the revision; the line is drawn by whose data
  changes, not by whether something changes.
- **`devices/set_operation` carries a strict allow-list**, and it is the only schema in
  the API that refuses unknown keys instead of ignoring them: it is open to every
  logged-in user, so the absence of a key *is* the boundary. `devices/update` has no field
  filter and stays administrator-only for exactly that reason.
- The panel greys out what a resident does not own, but the backend is what enforces it —
  a disabled field is not a permission check.
- Recalculating is open to every logged-in user: it produces a result, never a
  configuration change.
- Every write carries the revision it was based on. A write based on stale data is
  refused with `revision_conflict` and the current configuration travels back with the
  refusal, so nothing is overwritten blind.
- Values from the panel are validated with Voluptuous and then coerced defensively by
  the model layer. Unknown keys are ignored, never stored.
- The integration calls no service in any other domain.

## Roadmap

Phase 2 candidates, in no fixed order:

- Actual control, with the capability and agreement fields that 0.1.0 already records.
- Price and solar forecasts, and advice that plans ahead rather than describing now.
- History: what the advice was worth, and daily or monthly totals.
- Repairs and persistent notifications for a source that has been unavailable for a
  while.
- Hysteresis on the peak warning and a staleness check on entity readings.
- A feed-in price source, instead of the fixed all-in amount 0.1.0 asks for.

## License

MIT — see [LICENSE](LICENSE).
