/**
 * The Dutch words for every code the backend sends (SPEC.md §12 and §26).
 *
 * A reason code and a checklist key are machine identifiers.
 * They belong in the sensor attributes, where an automation reads them, and
 * nowhere a customer can see. The panel used to print them anyway — "REDEN:
 * missing_required_data" under the headline advice, "Betrouwbaarheid: high"
 * beside the surplus — because the code was rendered directly and, where a table
 * did exist, it fell back to the key whenever it had no entry.
 *
 * That fallback is the part worth naming: `LABELS[key] || key` turns "we forgot
 * a word" into "show the customer an identifier", and it does so exactly when
 * something is missing. So every lookup here returns `null` for a key it does
 * not know, and each caller hides the row instead. A missing line is a gap; a
 * raw code is a defect the customer can see.
 *
 * The tables live in the frontend and not in `translations/`, for the reason
 * SPEC.md §26 gives: these are the sentences that carry the reasoning, and they
 * belong beside the field they explain. `tests/test_panel.py` checks this file
 * against the constants in `const.py`, so a new code cannot ship without a word
 * to go with it.
 */

/** Why the engine reached this conclusion (engine/reason_codes.py). */
const REASON_LABELS = {
  missing_required_data: 'Er ontbreken gegevens',
  invalid_entity_state: 'Een gekoppelde entiteit levert geen bruikbare waarde',
  entity_missing: 'Een gekoppelde entiteit bestaat niet',
  entity_without_value: 'Een gekoppelde entiteit heeft nog geen waarde',
  entity_unavailable: 'Een gekoppelde entiteit is niet bereikbaar',
  entity_stale: 'Een gekoppelde entiteit is stilgevallen',
  solar_surplus_available: 'Er is zonneoverschot',
  high_grid_load: 'De netbelasting is hoog',
  high_grid_export: 'De teruglevering is hoog',
  low_energy_price: 'De energieprijs is laag',
  high_energy_price: 'De energieprijs is hoog',
  flexible_device_available: 'Er is een verplaatsbaar apparaat beschikbaar',
  outside_allowed_window: 'Buiten het toegestane tijdvenster',
  quiet_hours_active: 'Het is nu stille uren',
  deadline_approaching: 'De uiterste starttijd komt in zicht',
  insufficient_savings: 'De besparing is te klein om te melden',
  neutral_energy_situation: 'De situatie vraagt niet om een aanpassing',
};

/** The six items of the data quality checklist (engine/completeness.py). */
const CHECKLIST_LABELS = {
  home_profile_complete: 'de woninggegevens',
  grid_source_valid: 'een geldige netbron',
  solar_source_valid: 'een geldige zonnebron',
  price_information_available: 'prijsinformatie',
  device_profile_complete: 'een compleet apparaatprofiel',
  flexible_devices_have_time_window: 'tijdvensters voor flexibele apparaten',
};

/**
 * The measurements an advice carries, with the unit in the label.
 *
 * The price says "all-in" because that is what the number is: the calculator
 * normalises a market price on reading (SPEC.md §16), and a reader who assumed
 * otherwise would think the coach was quoting a figure three times too high.
 */
const MEASUREMENT_LABELS = {
  prijs_eur_kwh: 'all-in prijs in €/kWh',
  netbelasting_procent: 'netbelasting in %',
  netvermogen_w: 'netvermogen in W',
  zonneoverschot_w: 'zonneoverschot in W',
  ontbrekende_onderdelen: 'ontbrekende onderdelen',
};

/** Look a key up, returning null rather than the key itself. */
function lookup(table, key) {
  if (typeof key !== 'string') {
    return null;
  }
  return table[key] ?? null;
}

export function reasonLabel(code) {
  return lookup(REASON_LABELS, code);
}

export function checklistLabel(key) {
  return lookup(CHECKLIST_LABELS, key);
}

export function measurementLabel(key) {
  return lookup(MEASUREMENT_LABELS, key);
}

/** The tables themselves, for the test that checks them against const.py. */
export const LABEL_TABLES = {
  reason: REASON_LABELS,
  checklist: CHECKLIST_LABELS,
  measurement: MEASUREMENT_LABELS,
};
