# Changelog

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
