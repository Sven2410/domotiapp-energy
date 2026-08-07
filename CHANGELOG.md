# Changelog

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
