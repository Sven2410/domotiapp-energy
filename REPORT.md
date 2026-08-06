# DomotiApp Energy 0.1.0 — implementation report

Written at the end of the initial implementation (2026-08-06), as SPEC.md §31 asks for.
It records what was built, which choices were made and why, what does **not** work, and
what was deliberately left for a later release.

---

## 1. What was built

A Home Assistant custom integration (`domotiapp_energy`) that acts as a manually
configured energy coach. It reads the entities an installer links by hand, normalises
them to one internal convention per quantity, derives two scores and a set of advice, and
shows all of it in a Dutch side panel.

It is complete against the twenty acceptance criteria of SPEC.md §29 (see §5 below), and
it is feature-complete for 0.1.0.

**The backend** consists of typed models with defensive round-tripping, a `Store`-backed
configuration with optimistic concurrency, a validation layer, a four-part calculation
engine (calculator, completeness, advisor, coach provider), a coordinator, six entities,
two services and sixteen WebSocket commands.

**The frontend** is a custom panel of seven tabs, built with native ES modules and Home
Assistant's own components — no build step, no dependencies, no CDN.

**What it does not do:** it controls nothing. Not a single `hass.services.async_call`
exists in the codebase.

---

## 2. Architecture choices, and where they deviate from the spec

Each deviation was raised at the time and approved; this is the consolidated list.

### 2.1 Choices that shaped the whole

**One convention per quantity, applied once, on reading.** Grid power becomes "positive
means import", battery power "positive means charging", and a price becomes an all-in
price — all in the calculator, at the moment the entity is read. Nothing downstream has
to know what the customer's sensor reported. The alternative — carrying the unit question
into every comparison, every text and every number in the panel — is the kind of
scattered assumption this project was bitten by three times.

**A missing value is never a default.** A grid meter without a stated meter mode, a price
source without a stated basis, a market price without the energy tax: each is refused
with `missing_required_data` rather than guessed. The row stays visible and says what is
missing. A plausible-looking wrong number is worse than an honest gap.

**Quarantine rather than degrade.** A stored source or device with an unrecognised type
keeps that type, is disabled and is reported (SPEC.md §12). Degrading a corrupt
`grid_meter` to `general_consumption` would feed household consumption into the solar
surplus formula — invisibly.

**Three kinds of truth about control never merge** (SPEC.md §12): `capabilities` is what
the hardware can do, `control_mode` what the installer wants, `control_forbidden` what
was agreed with this customer. Only the last one blocks a write.

### 2.2 Deviations from SPEC.md, with reason

| Deviation | Reason |
|---|---|
| A ninth logbook event type, `invalid_configuration` | A row with an unknown type is a configuration problem, not an availability problem or a bad reading. Approved 2026-08-05. |
| A twelfth reason code, `high_grid_export` | Overload by export needs the *opposite* advice of overload by import. One shared text would tell an exporting home to make it worse. |
| The revision only moves on an explicit user action | SPEC.md §13 says "+1 on every change". Logbook writes and `async_load` therefore leave it alone: otherwise a background event expires the panel's `expected_revision` mid-edit. CLAUDE.md rule 9. |
| `issues` travels with every WebSocket answer | SPEC.md §14 fixes the write answer at `{revision, item}`. Adding a third key is a superset; the alternative — a `validate` command — costs a round trip after every save. |
| A write is refused **only** for forbidden control | Everything else validation finds is stored and reported. An installer in a meter cupboard fills a row in gradually; a grid meter without a meter mode has to be savable as a work in progress. SPEC.md §12. |
| `price_basis`, the price components and the all-in normalisation | Not in the original spec at all. A price sensor can report a bare market price or an all-in one, differing by a factor of three in the Netherlands, and nothing said which. SPEC.md §8 and §16 now carry it. |
| `flexibility_component` requires a *complete* device | "Usable and flexible" let a row with only a name earn ten points, so adding an empty appliance raised the score. SPEC.md §16. |
| The device in the registry is fixed to `DomotiApp Energy` | Contrary to the literal text of §6, but §19 requires fixed entity IDs, which are derived from the device name. |
| `entity.py` and two extra test files were added | Not in the §4 file list. `entity.py` is the shared entity base, so `binary_sensor.py` need not import from `sensor.py`. |
| Panel texts stay in the frontend, not in `translations/` | They are sentences that carry the reasoning, and they belong next to the field they explain. SPEC.md §26 records the condition under which this changes. |

### 2.3 Two components built ourselves, against the instinct to reuse

**The dialog is ours, not `ha-dialog`.** `ha-dialog` exists and is even defined in a
custom panel, but it is internal to the Home Assistant frontend and its shape changed
underneath us: in HA 2026.7 it wraps `wa-dialog`, ignores the `heading` property and has
no `close()` method, while the MWC form every custom card uses is what our own minimum
version (2025.6) ships. One call cannot satisfy both, and we cannot pin the frontend. Our
dialog is about a hundred lines we control.

**The frontend version lives in the URL path.** `?v=` busts only the entry point,
because a relative import does not inherit the query string. Home Assistant's service
worker caches by exact URL and was observed serving the previous release's tab modules to
a browser that had just loaded the new entry point — a half-old, half-new panel. The
version is therefore part of the base path, so a release moves every module at once.

---

## 3. Files

75 tracked files. The integration itself:

```text
custom_components/domotiapp_energy/
  __init__.py            entry setup, teardown, services
  config_flow.py         the UI flow, single instance
  const.py               every shared constant
  models.py              typed models, defensive from_dict/to_dict
  storage.py             Store subclass, revisions, logbook
  validators.py          reading entity values, validating configuration
  coordinator.py         state listeners, debounce, safety interval
  entity.py              shared entity base, fixed object ids
  sensor.py              five sensors
  binary_sensor.py       the peak risk sensor
  panel.py               static path and panel registration
  websocket_api.py       sixteen commands
  services.yaml
  manifest.json
  engine/
    calculator.py        reading and deriving; the three normalisations
    completeness.py      the data quality checklist, is_complete_device_profile
    advisor.py           the advice rules and the savings formula
    providers.py         the Dutch phrasing, and the inactive extension point
    reason_codes.py      twelve stable codes
  frontend/
    domotiapp-energy-panel.js   the panel shell and the whole stylesheet
    core/  api.js dialog.js dom.js forms.js rows.js state.js tap.js
    tabs/  overview.js home.js sources.js devices.js preferences.js coach.js logbook.js
  translations/  nl.json en.json
```

Supporting:

```text
tests/            12 Python test files
tests/frontend/   7 files: the jsdom harness and six suites
scripts/          test.ps1, ha_check.py, install_frontend_requirement.py
.github/workflows/ tests.yml, validate.yml
SPEC.md CLAUDE.md README.md CHANGELOG.md REPORT.md LICENSE hacs.json pyproject.toml package.json
```

---

## 4. Tests and results

| Suite | Count | Result |
|---|---|---|
| `pytest` (in the test container) | 449 | all pass |
| `npm test` (jsdom + `node --test`) | 157 | all pass |
| `ruff check` / `ruff format --check` | — | clean |
| GitHub Actions **Tests** and **Validate** (hassfest + HACS) | — | green on every push |

**Backend coverage: 98%** (2060 statements, 26 missed; 540 branches, 25 partial).

```text
advisor.py 100%   completeness.py 100%   providers.py 100%   sensor.py 100%
binary_sensor.py 100%   config_flow.py 100%   const.py 100%   entity.py 100%
calculator.py 99%   coordinator.py 99%   validators.py 99%
models.py 97%   panel.py 97%   __init__.py 96%   storage.py 96%   websocket_api.py 95%
```

The uncovered lines are defensive branches: coercion paths for values that the WebSocket
schema already rejects, and error handlers for storage failures.

**Two things the test layers cannot do, and what fills the gap:**

- jsdom stubs `ha-form` entirely. No test there can prove a control accepts a click —
  that is how the weekday selector shipped broken with a green suite. Invariants the stub
  *can* check were added (no `select` option may carry a non-string value), and every
  frontend change is now verified in a real browser with real clicks before delivery.
- A frontend fix counts as verified only when its test demonstrably fails against the
  code from before the fix. That was done for every fix in phases 7 through 9.

---

## 5. Acceptance criteria (SPEC.md §29)

All twenty are met.

| # | Criterion | Evidence |
|---|---|---|
| 1 | Addable through the UI | `config_flow.py`, 8 tests |
| 2 | At most one config entry | `single_instance_allowed` abort, tested |
| 3 | Panel appears in the sidebar | `panel.py`, `test_panel.py`, seen in the live instance |
| 4 | Home data enterable | Woning tab, verified in the browser |
| 5 | Energy sources addable | A price source was created through the GUI |
| 6 | Appliances addable | Created and removed through the GUI |
| 7 | No matching or discovery anywhere | Grep clean; `tracked_entity_ids()` reads stored config only |
| 8 | Configuration survives a restart | `test_configuration_survives_a_reload`, plus repeated container restarts |
| 9 | Linked entities read safely | `read_entity_value`, 40+ tests |
| 10 | Data quality score calculated | `completeness.py`, seen live |
| 11 | Energy score calculated | `calculator.py`, seen live |
| 12 | Solar, price, peak and missing-data advice | `test_advisor.py`; all three price levels seen live |
| 13 | Frontend renders the structured advice | Energiecoach tab, 17 tests, browser verification |
| 14 | The exact entity IDs of §19 | `test_entities.py` in `en` and `nl`; confirmed live by `ha_check.py` |
| 15 | Non-admins cannot change configuration, WebSocket included | `require_admin`, tested with a read-only token |
| 16 | Works without internet | No network code, `requirements: []` |
| 17 | Controls nothing | Zero `async_call` in the codebase |
| 18 | Tests for the critical logic | 449 + 157, 98% coverage |
| 19 | README and CHANGELOG present | Both written |
| 20 | Ready for HACS; `validate.yml` passes | Green on every push |

---

## 6. Technical limitations

- **Nothing is controlled.** The `capabilities`, `control_mode` and `control_forbidden`
  fields are recorded only; everything except `monitor_only` behaves as `advice_only`.
- **No forecasts are used.** `price_forecast` and `solar_forecast` can be configured; the
  engine does not read them.
- **No history.** Every calculation looks at the present moment. No trends, no totals, no
  "what did yesterday cost".
- **Advice is not a schedule.** It says what is favourable now; it does not plan ahead.
- **The feed-in payment is a fixed all-in amount**, not a source. It cannot be normalised
  with the import formula: feed-in generally returns the market price and possibly VAT,
  but no energy tax.
- **A price source that cannot be normalised is refused**, which means a customer who
  fills in nothing else sees no price at all. That is intended.
- **The panel is Dutch only.** See SPEC.md §26 for the decision and its condition.
- **`ha-dialog` is not used**, so the dialog does not inherit future Home Assistant
  dialog behaviour. It is also not a top-level modal: focus can still reach the Home
  Assistant sidebar behind the panel, because a panel cannot inert the page it lives in.
  Everything inside our own panel is unreachable while a dialog is open.

---

## 7. Open points

Honest list. None of these block the release; each has a reason for being open.

### 7.1 A browser test before the first customer rollout

SPEC.md §30 recommends a headless-browser check (Playwright) as the last control before
the first rollout, deliberately outside the phasing. It is **not built**.

Why it matters here more than usual: three bugs in phase 7a came from one CSS cascade
rule while every other check was green, and the weekday selector shipped broken because
jsdom stubs `ha-form`. Manual browser verification with real clicks now covers each
change, but it is manual and it is mine — it does not run in CI.

### 7.2 Hysteresis on the peak warning

`peak_risk` flips the moment the load crosses the threshold, in both directions. A grid
power hovering around the warning level will toggle the binary sensor repeatedly, and
every flip is an automation trigger for whoever built one on it. A fixed hysteresis band
— on above the threshold, off only below a lower one — is the fix. **Not built.** Any
constant must be fixed in `const.py`, not another setting.

### 7.3 A staleness check on readings

An entity that keeps its last value forever is read as current. A sensor that stopped
updating an hour ago is treated exactly like one that reported a second ago. A maximum
age, after which a reading counts as unusable with `invalid_entity_state`, is the fix.
**Not built.** Same rule about the constant.

### 7.4 The version gap between the test route and the minimum version

| | Python | Home Assistant |
|---|---|---|
| Test container and CI | 3.13 | 2026.2.3 |
| Sven's test instance | 3.14.6 | 2026.7.4 |
| **Minimum supported** | **3.13** | **2025.6.0** |

`pytest-homeassistant-custom-component` pins the HA version; we do not choose it. So the
suite runs against 2026.2, the live verification against 2026.7, and **nothing is
verified against 2025.6.0**, the version `hacs.json` and the README promise.

Every API in the SPEC.md §0 table was checked to exist in 2025.6 by reading the source,
and no API newer than that is used. But "checked by reading" is not "run against". The
practical risk sits in the frontend, where `ha-form` and its selectors have moved most —
the `no_second` option on the time selector, for instance, is verified on 2026.7 only.

Decided 2026-08-05 to stay on Python 3.13, because moving pulls in a Home Assistant beta.
Reconsider once HA 2026.8 is stable. Raising the minimum version to something the suite
actually runs against is the other honest option.

### 7.5 Smaller open items

- `price_forecast` and `solar_forecast` are storable but unused; a customer can configure
  a source that does nothing. The row does not say so.
- `EnergySource` has no `control_mode`, so the forbidden-control block can never fire on
  a source. Sven decided a source is a measuring point and should keep no intent; the
  check is written for both models and starts working if that ever changes.
- The `issues` map is computed on every read. It is a handful of pure comparisons over
  data already in memory, but it is not cached.

---

## 8. What deliberately waits for the control release

These are not omissions. They are recorded now so nothing has to be revisited at every
customer later.

- **Actual control.** `capabilities` (`read`, `switch`, `set_power_limit`,
  `set_current`), `control_mode` and `control_forbidden` with its reason are already
  stored and shown per row. The one hard block — an agreement not to control, contradicted
  by a controlling mode — is already enforced.
- **The energy score gets no control term.** Answered and recorded on 2026-08-06: the
  score measures the *possibility* of using energy smartly, which is the same in a home
  that can be switched and one that cannot. Automation raises the chance the opportunity
  is *taken*, which is realisation, needs history, and belongs in a separate clearly named
  indicator — not in this score.
- **`ExtensionCoachProvider`** is the deliberately inactive extension point of SPEC.md
  §17. It holds no provider, no client and no API key, and raises when used.
- **A feed-in price source**, instead of the fixed amount 0.1.0 asks for.

---

## 9. Installing by hand

For a Home Assistant that is not managed through HACS, or to test a working copy.

1. Copy `custom_components/domotiapp_energy` into the `custom_components` directory of
   your Home Assistant configuration. Create that directory if it does not exist.
2. Restart Home Assistant. Copying alone is not enough — the integration is discovered at
   startup.
3. **Settings → Devices & services → Add integration**, search for **DomotiApp Energy**.
4. Fill in a home name and tick the confirmation that you configure everything by hand.
5. The panel appears in the sidebar as **DomotiApp Energy**.

To update by hand: replace the folder and restart. Because the frontend is served from a
versioned path, the browser picks up the new panel by itself; only a change *within* the
same version needs a hard reload (developer tools, right-click the reload button, "Empty
cache and hard reload").

---

## 10. Configuring the first home

The order matters: each step makes the next one meaningful.

1. **Woning**
   - number of phases and the main fuse per phase;
   - the maximum grid power to warn about, and the percentage to warn from;
   - the contract. On **dynamic**, also fill in the energy tax per kWh, the supplier
     markup per kWh and the VAT rate — a price source reporting a bare market price is
     completed with those three. On **fixed**, fill in the all-in tariff per kWh.
   - the feed-in payment and feed-in cost, both per kWh, both all-in;
   - net metering until (default 1 January 2027; clear it if this home does not
     net-meter);
   - the minimum solar surplus from which an appliance is advised.
2. **Energiebronnen → Bron toevoegen**
   - the grid meter first: state explicitly whether it reports one signed value (and what
     a positive value means) or separate import and export entities;
   - the unit is your statement, not the entity's: the integration never reads
     `unit_of_measurement`;
   - a price source must state whether it reports the **all-in** price or the **bare
     market price**. Without that it is not used.
3. **Apparaten → Apparaat toevoegen**
   - the fields marked with an asterisk are what the data quality score asks for: nominal
     power, energy per cycle, and both ends of a time window for anything flexible;
   - a half-filled appliance saves fine — it simply does not count as complete.
4. **Voorkeuren** — quiet hours, what may weigh in, the savings threshold, how much
   detail to show.
5. **Energiecoach** — press **Opnieuw berekenen** and read the advice. The five fixed
   questions each open their answer in a dialog.

A first sanity check: the Overzicht should show a grid power, a percentage of the
maximum, and — on a dynamic contract with a working price source — an all-in price with
the market price it was derived from underneath.

---

## 11. Logical phase-2 extensions

In no fixed order, and each with a reason to exist:

1. **Control**, on the fields 0.1.0 already records.
2. **Forecasts**, and advice that plans instead of describing now: "start the dishwasher
   at 02:00" rather than "now is favourable".
3. **History**: what the advice was worth, daily and monthly totals, and a realisation
   indicator that measures whether the opportunity was taken.
4. **Repairs and persistent notifications** for a source that has been unavailable for a
   while (SPEC.md §21 already marks these as phase 2).
5. **Hysteresis and staleness** — see §7.2 and §7.3; small, and the first things to do.
6. **A Playwright check in CI**, so the browser is not only checked by hand.
7. **A feed-in price source.**
8. **Translations for the panel**, if and only if a customer outside the Dutch language
   area appears (SPEC.md §26).

---

## 12. In short

0.1.0 does what it promises, refuses what it cannot know, and controls nothing. The
places where it is weakest are named in §7: no automated browser test, a peak warning
without hysteresis, no staleness check on readings, and a test route that runs against a
newer Home Assistant than the minimum the README promises.
