# Changelog

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
