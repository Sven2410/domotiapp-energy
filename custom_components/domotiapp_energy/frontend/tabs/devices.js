/**
 * The Apparaten tab (SPEC.md §8, §9, §11, §22 and §23).
 *
 * The second CRUD tab, on the machinery 8a built. What is different about a
 * device, as opposed to a source:
 *
 * * it carries an **intention** — `control_mode` — next to what the hardware
 *   can do and what was agreed. Those three are deliberately not merged
 *   (SPEC.md §12), and the one combination that cannot stand is refused by the
 *   backend: an agreement not to control this installation outranks a mode
 *   somebody picks from a dropdown later;
 * * two flags follow from the device type unless the installer says otherwise
 *   — a dishwasher is noisy, a heat pump is not flexible (SPEC.md §8). The form
 *   follows the type only for a field nobody has touched yet;
 * * a time window that may cross midnight, which is the normal case for a
 *   dishwasher and not an error (SPEC.md §16).
 *
 * Two rules govern which questions appear, and they are different in kind:
 *
 * 1. **What the type can answer.** A battery level on a dishwasher is a
 *    question with no answer, and leaving it on screen invites a wrong link.
 * 2. **What the installer decided.** The time window follows `is_flexible`
 *    rather than the type, because that is what the data quality checklist
 *    actually asks about — a window is required of every flexible device.
 *
 * **Hiding is never deleting.** A value that scrolls out of view with a type
 * change stays in the draft, so switching back restores it, and the dialog says
 * out loud what saving would drop. Silently discarding it would be the same
 * class of mistake as the shared-draft bug of phase 7b.
 */

import {
  conflictKind,
  createApi,
  describeError,
  fieldErrors,
  isRevisionConflict,
  warningMessages,
} from '../core/api.js';
import { createConfirmDialog, createDialog } from '../core/dialog.js';
import {
  button,
  card,
  el,
  formatMoment,
  formatNumber,
  notice,
  section,
  setVisible,
} from '../core/dom.js';
import {
  createForm,
  describeOrphanedErrors,
  splitFieldErrors,
} from '../core/forms.js';
import { createRowList } from '../core/rows.js';
import {
  MANAGED_NOTICE,
  applyRole,
  messageForRole,
  residentOwns,
} from '../core/roles.js';
import { onTap } from '../core/tap.js';

/** The key this tab stores its unsaved edits under. */
const DRAFT = 'device';

const TYPE_LABELS = {
  ev_charger: 'Laadpaal',
  home_battery: 'Thuisbatterij',
  heat_pump: 'Warmtepomp',
  electric_boiler: 'Elektrische boiler',
  dishwasher: 'Vaatwasser',
  washing_machine: 'Wasmachine',
  dryer: 'Droger',
  air_conditioning: 'Airconditioning',
  pool_pump: 'Zwembadpomp',
  generic_schedulable: 'Overig, inplanbaar',
  generic_monitor: 'Overig, alleen meten',
};

const TYPE_OPTIONS = Object.entries(TYPE_LABELS).map(([value, label]) => ({
  value,
  label,
}));

/** Types that are noisy unless the installer says otherwise (SPEC.md §8). */
const NOISY_BY_DEFAULT = new Set([
  'washing_machine',
  'dryer',
  'dishwasher',
  'pool_pump',
]);

/** Types that are not flexible unless the installer says otherwise. */
const INFLEXIBLE_BY_DEFAULT = new Set(['generic_monitor', 'heat_pump']);

/**
 * Types somebody loads by hand, so the coach waits to be told (SPEC.md §32.5).
 *
 * A charger is deliberately absent: it can see through its status entity
 * whether a car is attached, and a flag somebody has to flip while the system
 * can see the answer is the busywork this round removes.
 */
const NEEDS_READY_FLAG_BY_DEFAULT = new Set([
  'dishwasher',
  'washing_machine',
  'dryer',
]);

const PRIORITY_LABELS = {
  low: 'Laag',
  normal: 'Normaal',
  high: 'Hoog',
  critical: 'Kritiek',
};

const CONTROL_MODE_LABELS = {
  monitor_only: 'Alleen monitoren',
  advice_only: 'Alleen adviseren',
  approval_required: 'Vragen om goedkeuring',
  automatic: 'Automatisch aansturen',
};

const CAPABILITY_OPTIONS = [
  { value: 'read', label: 'Uitlezen' },
  { value: 'switch', label: 'Aan- en uitschakelen' },
  { value: 'set_power_limit', label: 'Vermogensgrens instellen' },
  { value: 'set_current', label: 'Laadstroom instellen' },
];

/**
 * The weekdays, with **string** values.
 *
 * Verified in the browser, and the reason this list does not carry the integers
 * the backend stores: with seven options `ha-selector-select` renders a
 * combobox rather than checkboxes, and that combobox works in strings. A
 * numeric option value never matches what it hands back, so the selection is
 * dropped without a word — the field simply does nothing, which is exactly how
 * it was reported. The four-option capability list next to it kept working
 * because it renders as checkboxes.
 *
 * The conversion to the integers of `datetime.weekday()` happens on the way to
 * the backend, in `payloadFrom`, and back again in `draftFrom`.
 */
const DAY_OPTIONS = [
  { value: '0', label: 'Maandag' },
  { value: '1', label: 'Dinsdag' },
  { value: '2', label: 'Woensdag' },
  { value: '3', label: 'Donderdag' },
  { value: '4', label: 'Vrijdag' },
  { value: '5', label: 'Zaterdag' },
  { value: '6', label: 'Zondag' },
];

/**
 * The optional entity links, and which types each one means something for.
 *
 * `types: null` means every type. The three that are restricted are the ones
 * that are actively misleading elsewhere: a battery level on a dishwasher, or
 * a remaining time on a heat pump, is an invitation to link the wrong entity.
 */
const ENTITY_LINKS = [
  {
    name: 'status_entity',
    label: 'Statusentiteit',
    types: null,
    helper: 'De entiteit die zegt of het apparaat aan staat of draait.',
  },
  {
    name: 'power_entity',
    label: 'Vermogensentiteit',
    types: null,
    // **Says which of the two unit rules applies here** (SPEC.md §57). On
    // Energiebronnen the installer picks the unit himself and reads that the
    // entity's own unit is never used; here it is exactly the other way round,
    // and without a word about it he has to guess which he is looking at.
    helper:
      'Het actuele vermogen van dit apparaat. Anders dan bij een energiebron ' +
      'wordt de eenheid hier van de entiteit zelf overgenomen: hij moet in W ' +
      'of kW meten. Een meterstand in kWh is een totaal en geen vermogen, en ' +
      'wordt geweigerd — de rij zegt dat dan ook.',
  },
  {
    name: 'energy_entity',
    label: 'Energieverbruikentiteit',
    types: null,
    helper: 'De meterstand of het verbruik van dit apparaat.',
  },
  {
    name: 'remaining_time_entity',
    label: 'Resterende tijd',
    types: ['dishwasher', 'washing_machine', 'dryer', 'ev_charger'],
    helper: 'Hoe lang de lopende cyclus nog duurt.',
  },
  {
    name: 'temperature_entity',
    label: 'Temperatuursensor',
    types: ['heat_pump', 'electric_boiler', 'air_conditioning'],
    helpers: {
      heat_pump: 'De aanvoertemperatuur van de warmtepomp.',
      electric_boiler: 'De watertemperatuur in de boiler.',
      air_conditioning: 'De ruimtetemperatuur die deze airco regelt.',
    },
  },
  {
    name: 'battery_level_entity',
    label: 'Batterijniveau',
    types: ['home_battery', 'ev_charger'],
    helpers: {
      home_battery: 'De laadtoestand van de thuisbatterij, in procenten.',
      ev_charger: 'De laadtoestand van de auto, als de laadpaal die meldt.',
    },
  },
];

const NEW_DEVICE = {
  name: '',
  device_type: 'dishwasher',
  enabled: true,
  priority: 'normal',
  control_mode: 'advice_only',
  // Strings, because that is what the draft speaks; see DAY_OPTIONS.
  days_of_week: ['0', '1', '2', '3', '4', '5', '6'],
  capabilities: [],
  control_forbidden: false,
};

/** Whether this type is noisy by default (SPEC.md §8). */
function noisyByDefault(deviceType) {
  return NOISY_BY_DEFAULT.has(deviceType);
}

/** Whether this type is flexible by default (SPEC.md §8). */
function flexibleByDefault(deviceType) {
  return !INFLEXIBLE_BY_DEFAULT.has(deviceType);
}

/** Whether this type waits to be told there is work in it (SPEC.md §32.5). */
function needsReadyFlagByDefault(deviceType) {
  return NEEDS_READY_FLAG_BY_DEFAULT.has(deviceType);
}

/**
 * The fields the data quality checklist actually asks of a device.
 *
 * This mirrors `engine/completeness.py`, which is the real source of truth:
 * `_has_complete_device_profile` wants a power **and** an energy per cycle —
 * **of an appliance the coach can advise about**.
 *
 * Nothing is asked of an appliance that will never be advised about, because
 * both fields exist to produce advice: the energy per cycle becomes the saving,
 * the power decides whether a surplus can carry it. A `generic_monitor` says
 * "measure this, do not move it", and a resident who set "alleen meekijken"
 * said the same thing on the other axis. Marking those fields required there
 * is a requirement that does not apply, shown as a shortcoming — the tablet
 * charger that was told its cycle was missing (production, 2026-08-09).
 *
 * **The time window is deliberately not marked.** It used to be, on a flexible
 * device, and the asterisk then sat directly above a helper reading "laat beide
 * tijden leeg als er geen venster is" — the form contradicting itself in two
 * adjacent lines. The helper is right: a device with no window is allowed at any
 * hour, which makes it *more* available for advice, not less. A window is worth
 * points on the quality checklist because it sharpens the advice, and that is a
 * different claim from "this field must be filled in".
 */
function requiredFields(draft) {
  if (!isAdvisable(draft)) {
    return [];
  }
  // Filtered through the same question the form asks, so a field this type
  // never shows can never be marked required — an asterisk on a field that is
  // not on screen is a completeness the installer cannot reach.
  return ['nominal_power_w', 'energy_per_cycle_kwh'].filter((name) =>
    asksSomething(name, draft),
  );
}

/**
 * Whether the coach can ever say anything about this appliance.
 *
 * The panel's copy of `engine/completeness.py:is_advisable`. Both axes matter:
 * the type decides the default flexibility, the resident's control mode is his
 * own off switch.
 */
function isAdvisable(draft) {
  if (NEVER_ADVISED_TYPES.includes(draft.device_type)) {
    return false;
  }
  const flexible =
    draft.is_flexible === undefined || draft.is_flexible === null
      ? flexibleByDefault(draft.device_type)
      : draft.is_flexible;
  return Boolean(flexible) && draft.control_mode !== 'monitor_only';
}

/**
 * Types the coach can never address (`const.NEVER_ADVISED_DEVICE_TYPES`).
 *
 * A home battery is flexible — moving energy through time is what it does — so
 * the flag says yes and the appliance became advisable, and the checklist asked
 * it for an energy per cycle. It has none: nobody starts a battery, it follows
 * the surplus by itself. Same defect as the tablet charger of 0.6.1, one type
 * further along, and it needed an axis of its own because calling a battery
 * inflexible would have been untrue (SPEC.md §38.2).
 */
const NEVER_ADVISED_TYPES = ['home_battery'];

/**
 * Advice concepts: they order, time or silence advice, and do nothing else.
 *
 * The priority ranks candidates for advice; the noise flag keeps one quiet
 * during the quiet hours. On an appliance the coach will never mention, both
 * are questions with no reader — "Normaal" as a priority among nothing, next to
 * a noise rule that will never be applied (SPEC.md §38.3). The days are already
 * tied to `is_flexible` and follow the same logic.
 */
const ADVICE_CONCEPTS = ['priority', 'is_noisy'];

/**
 * Fields with no true answer for this type, however anything else is set.
 *
 * - a `generic_monitor` is a smart plug. It has no power of its own — it
 *   measures whatever is plugged into it — and no cycle. All three questions
 *   are about the appliance behind the plug, which this row is not.
 * - a `home_battery` has a power worth stating and **no cycle at all**. Its
 *   power stays asked; only the two cycle fields go.
 *
 * Deliberately *not* extended to the heat pump, whose nominal power describes
 * something real even though nothing reads it yet. Whether we should be asking
 * for that at all is a separate open question (SPEC.md §37.2), and answering it
 * by hiding the field here would be deciding it in passing.
 */
const MEANINGLESS_BY_TYPE = {
  generic_monitor: [
    'nominal_power_w',
    'energy_per_cycle_kwh',
    'duration_minutes',
  ],
  home_battery: ['energy_per_cycle_kwh', 'duration_minutes'],
};

/**
 * The two switches that decide whether advice happens at all.
 *
 * **These are never hidden for being switched off.** `control_mode =
 * monitor_only` is what makes a dishwasher unadvisable, and `is_flexible` is
 * what makes a smart plug advisable — so hiding either one because of the state
 * it produced would be a door that only opens one way: the resident who
 * switched his dishwasher to "alleen meekijken" could never switch it back, and
 * the five fields he owns beside it are already gone in that state, leaving him
 * a dialog with nothing he may touch (SPEC.md §38.3).
 *
 * They go only where they can switch nothing — a type the coach can never
 * address, whatever anybody ticks. On a `home_battery` neither moves
 * `is_advisable` and neither moves `has_movable_load`; both are choices with no
 * consequence, and the row has never shown them.
 */
const ADVICE_SWITCHES = ['control_mode', 'is_flexible'];

/**
 * Whether this field is a question about the appliance in front of us.
 *
 * Three rules, in the order they decide:
 *
 * 1. **A switch that can switch nothing.** Only on a never-advised type, and
 *    then permanently: nothing in this form brings it back, because nothing in
 *    this form can make such an appliance advisable.
 * 2. **An advice concept** — it orders, times or silences advice.
 * 3. **A field with no true answer for this type.**
 *
 * Rules 2 and 3 are released the moment the appliance becomes advisable, and
 * that is what keeps the override from being a dead end: tick "verplaatsbaar in
 * de tijd" on a smart plug and somebody has said advice should follow, so the
 * appliance behind the plug is exactly what the power and the cycle describe.
 * Hiding those by type alone would have left a required field that could not be
 * filled in — the shape of defect this round exists to remove.
 *
 * **Hidden, not shown-and-disabled.** That is the other agreement in this
 * project (the control level on Woning, §33.4a), and it is for a field that
 * becomes answerable in a later release. This is not that: the question is
 * wrong for this appliance, not early. A hidden field with a value in it is
 * named out loud before it is dropped, by the same orphan notice that handles
 * every other type change.
 */
function asksSomething(name, draft) {
  if (
    ADVICE_SWITCHES.includes(name) &&
    NEVER_ADVISED_TYPES.includes(draft.device_type)
  ) {
    return false;
  }
  if (isAdvisable(draft)) {
    return true;
  }
  return (
    !ADVICE_CONCEPTS.includes(name) &&
    !(MEANINGLESS_BY_TYPE[draft.device_type] || []).includes(name)
  );
}

/**
 * Mark a field the way Home Assistant marks its own required fields.
 *
 * `ha-form` passes `required` straight through to the selector
 * (`.required=${e.required || false}`), and the inputs render the marker from
 * `--ha-input-required-marker`, which is `*` by default. So this looks like
 * every other required field an installer meets in Home Assistant, and it
 * inherits that styling's contrast and screen-reader treatment instead of
 * imitating them with a suffix of our own.
 *
 * It does **not** block saving, here or anywhere: a half-filled device has to
 * be storable as a work in progress (SPEC.md §12). The asterisk says "this is
 * what the device needs to be complete", and the summary above the form says it
 * in words, because one character in a form this long is easy to miss.
 */
function markRequired(field, required) {
  if (!required.includes(field.name)) {
    return field;
  }
  return { ...field, required: true };
}

/**
 * The Dutch name of a field, for the sentence about what is still missing.
 *
 * **Two names per field, because the form has two** (SPEC.md §59). A charger is
 * asked for *Maximaal laadvermogen* and *Energie per laadsessie* — a car has no
 * cycle — and this row told its installer that "nominaal vermogen" and "energie
 * per cyclus" were missing, neither of which is on his screen.
 *
 * Found in the browser, one layer below the same mistake in the advice
 * sentences one layer up repaired. Two places naming one field differently is
 * only ever noticed from the outside, which is what that check is for.
 */
const REQUIRED_LABELS = {
  nominal_power_w: 'nominaal vermogen',
  energy_per_cycle_kwh: 'energie per cyclus',
};

const CHARGER_REQUIRED_LABELS = {
  nominal_power_w: 'maximaal laadvermogen',
  energy_per_cycle_kwh: 'energie per laadsessie',
};

/** What to call this field on a row of this type. */
function requiredLabel(name, device) {
  const labels =
    device.device_type === 'ev_charger'
      ? CHARGER_REQUIRED_LABELS
      : REQUIRED_LABELS;
  return labels[name];
}

/** Which of the checklist's fields this draft has not filled in yet. */
function missingRequired(draft) {
  return requiredFields(draft).filter((name) => {
    const value = draft[name];
    return value === undefined || value === null || value === '';
  });
}

/**
 * Build the schema for one draft.
 *
 * Every branch answers "does this question mean anything for what the installer
 * has chosen so far". Nothing is hidden that could still be answered, and
 * nothing is asked that could not.
 */
function schemaFor(draft) {
  const required = requiredFields(draft);
  const fields = [
    { name: 'name', label: 'Naam', selector: { text: {} } },
    {
      name: 'device_type',
      label: 'Soort apparaat',
      selector: { select: { mode: 'dropdown', options: TYPE_OPTIONS } },
    },
    {
      name: 'enabled',
      label: 'Ingeschakeld',
      helper: 'Een uitgeschakeld apparaat krijgt geen advies.',
      selector: { boolean: {} },
    },
    {
      name: 'location',
      label: 'Locatie',
      helper: 'Waar staat het? Alleen om het terug te herkennen.',
      selector: { text: {} },
    },
    {
      name: 'priority',
      label: 'Prioriteit',
      helper: 'Bij meerdere kandidaten wint de hoogste prioriteit.',
      selector: {
        select: {
          mode: 'dropdown',
          options: Object.entries(PRIORITY_LABELS).map(([value, label]) => ({
            value,
            label,
          })),
        },
      },
    },
    ...powerFields(draft),
    ...behaviourFields(draft),
    ...windowFields(draft),
    ...controlFields(draft),
    ...entityLinkFields(draft),
    {
      name: 'notes',
      label: 'Notities',
      selector: { text: { multiline: true } },
    },
  ];

  // One filter over the finished list rather than a guard in each builder, so
  // a field added later cannot slip past it by being defined somewhere else.
  return fields
    .filter((field) => asksSomething(field.name, draft))
    .map((field) => markRequired(field, required));
}

/**
 * What the device uses, which is what a saving can be calculated from.
 *
 * The **labels** move with the type, not only the helpers. "Nominaal vermogen"
 * on a charger reads as a rating plate figure, and a charger has no such thing
 * that matters here — what the calculation needs is the maximum it can deliver
 * to the car. "Energie per cyclus" and "duur van een cyclus" are worse: a
 * charger has no cycle whose size anyone can state, because that depends on how
 * empty the car is, and nothing in this release knows that. The state of charge
 * arrives with the vehicle of a later release (SPEC.md §30); until then the
 * honest question is what a *typical* session looks like, and the field has to
 * ask that in so many words rather than demand a number that does not exist.
 *
 * The advice built on it is capped at medium confidence for exactly this
 * reason; see `_surplus_confidence` in `engine/advisor.py`.
 */
function powerFields(draft) {
  const charger = draft.device_type === 'ev_charger';
  return [
    {
      name: 'nominal_power_w',
      label: charger ? 'Maximaal laadvermogen' : 'Nominaal vermogen',
      helper: powerHelper(draft.device_type),
      selector: { number: { min: 0, step: 10, unit_of_measurement: 'W' } },
    },
    {
      name: 'energy_per_cycle_kwh',
      label: charger ? 'Energie per laadsessie' : 'Energie per cyclus',
      // Without this there is no saving to calculate, so the advice can only
      // say "now is a good moment" and never what it is worth (SPEC.md §16).
      helper: energyHelper(draft.device_type),
      selector: { number: { min: 0, step: 0.1, unit_of_measurement: 'kWh' } },
    },
    {
      name: 'duration_minutes',
      label: charger ? 'Duur van een laadsessie' : 'Duur van een cyclus',
      helper: durationHelper(draft.device_type),
      selector: { number: { min: 0, step: 5, unit_of_measurement: 'min' } },
    },
  ];
}

/** What "a cycle" means differs enough per type to be worth saying. */
function powerHelper(deviceType) {
  const perType = {
    ev_charger:
      'Het hoogste vermogen waarmee deze paal kan laden — niet wat de auto ' +
      'er vandaag van afneemt.',
    home_battery: 'Het laad- of ontlaadvermogen van de batterij.',
    heat_pump: 'Het elektrische opgenomen vermogen, niet het thermische.',
    electric_boiler: 'Het vermogen van het verwarmingselement.',
  };
  return perType[deviceType] || 'Het vermogen tijdens gebruik.';
}

function energyHelper(deviceType) {
  const perType = {
    ev_charger:
      'Een schatting van een typische laadbeurt, bijvoorbeeld 10 kWh voor ' +
      'een dagelijkse rit. Exact kan niet: DomotiApp Energy weet niet hoe ' +
      'leeg de auto is, dus het advies rekent met dit getal en houdt zijn ' +
      'betrouwbaarheid daarom op "gemiddeld".',
    dishwasher: 'De energie van één programma, bijvoorbeeld 1,0 tot 1,5 kWh.',
    washing_machine: 'De energie van één wasbeurt.',
    dryer: 'De energie van één droogbeurt.',
    heat_pump: 'De energie van een gemiddelde draaiperiode.',
  };
  return (
    (perType[deviceType] || 'De energie van één cyclus.') +
    ' Zonder dit getal is er geen besparing te berekenen.'
  );
}

function durationHelper(deviceType) {
  if (deviceType === 'ev_charger') {
    return (
      'In minuten, voor een typische laadbeurt. Wordt getoetst aan het ' +
      'tijdvenster hieronder.'
    );
  }
  return 'In minuten. Wordt getoetst aan het tijdvenster hieronder.';
}

/**
 * The allowed time window, shown only for a device that may be moved.
 *
 * Tied to `is_flexible` and not to the type, because that is exactly what the
 * data quality checklist asks: every *usable flexible* device needs a window.
 * A device the installer marked as not flexible is never moved, so a window
 * would be a question about something that will not happen.
 */
/**
 * What the deadline means for this device, given what else is filled in.
 *
 * The duration is what turns a deadline into a start time, so its absence
 * changes what the field does — and saying so is cheaper than letting an
 * installer wonder why nothing is being planned (SPEC.md §32.2).
 */
function readyBeforeHelper(draft) {
  const base =
    'Laat beide tijden leeg als er geen venster is; het apparaat mag dan op ' +
    'elk uur. Een venster telt wel mee voor de datakwaliteit, omdat het advies ' +
    'er gerichter van wordt. ';
  return draft.duration_minutes
    ? base +
        'DomotiApp Energy rekent zelf terug wanneer het apparaat uiterlijk ' +
        'moet starten om dit te halen.'
    : base +
        'Vul hierboven een duur in, dan rekent DomotiApp Energy terug wanneer ' +
        'het apparaat uiterlijk moet starten. Zonder duur geldt dit alleen als ' +
        '"mag hierna niet meer draaien".';
}

function windowFields(draft) {
  // `isAdvisable` rather than `is_flexible` alone, which is strictly narrower:
  // a window says when advice may be given, so an appliance that gets none has
  // no use for one. The data quality checklist already reads it that way — the
  // time-window item stopped applying to a monitor-only appliance in 0.6.1 —
  // and a home battery made the gap visible: flexible by nature, advised about
  // never, and still asked on which days it was allowed to run (SPEC.md §38.3).
  if (!isAdvisable(draft)) {
    return [];
  }
  // **"Maakt niet uit" has to be an answer, not two empty boxes** (SPEC.md
  // §52). The dryer of woning 2 is the case: no deadline at all is a complete
  // description, and the checklist could not tell it from an unanswered
  // question, so its owner lost points for being accurate.
  //
  // The two time fields go **inactive rather than away**, and their values are
  // kept. Hiding them would put the way back behind the very switch that hid
  // them — the one-way door this project already ruled out once, and the same
  // treatment the contract fields get on the Woning tab.
  const anyTime = draft.runs_any_time === true;
  const deadline = (fieldDefinition) =>
    anyTime ? { ...fieldDefinition, disabled: true } : fieldDefinition;
  return [
    {
      name: 'runs_any_time',
      label: 'Maakt niet uit wanneer hij klaar is',
      helper:
        'Zet dit aan als elk moment goed is. De coach adviseert dit apparaat ' +
        'dan gewoon op een gunstig moment, alleen zonder deadline om naartoe ' +
        'te rekenen — en de datakwaliteit rekent het als beantwoord in plaats ' +
        'van als ontbrekend.',
      selector: { boolean: {} },
    },
    deadline({
      name: 'ready_before',
      label: 'Klaar uiterlijk om',
      // The deadline, and the field a resident actually has an answer for. The
      // start time is derived from this and the duration, so it is never asked
      // (SPEC.md §32).
      //
      // No asterisk here or on the next field; see requiredFields(). The helper
      // says what leaving it empty costs, which is the honest version of what
      // the asterisk was trying to convey.
      helper: readyBeforeHelper(draft),
      // Seconds are meaningless for a window a dishwasher runs in.
      selector: { time: { no_second: true } },
    }),
    deadline({
      name: 'ready_days',
      label: 'Op welke dagen geldt dit',
      // The dimension the deadline was missing (SPEC.md §56.1). Leaving it
      // empty means every day the appliance runs on, which is what the ready
      // window did before this existed — so an installer who never touches it
      // sees no change.
      helper:
        'Laat leeg als de deadline elke dag geldt. Voor een laadpaal is dit ' +
        'meestal de werkweek: op die dagen moet de auto vol zijn, en op de ' +
        'andere dagen mag hij gewoon wachten op zon of een lage prijs — hij ' +
        'krijgt dan nog steeds advies, alleen zonder deadline.',
      selector: { select: { multiple: true, options: DAY_OPTIONS } },
    }),
    deadline({
      name: 'ready_from',
      label: 'Niet eerder klaar dan',
      // The bound that has no equivalent in a start window: washing that is
      // done at 03:00 sits wet until 07:00, which is a spoilage problem and not
      // a noise problem (SPEC.md §32).
      helper:
        'Optioneel. Handig voor was die niet uren nat mag blijven liggen: ' +
        'zet hier bijvoorbeeld 06:00 als je hem om 07:00 uithaalt. Ligt deze ' +
        'tijd ná "klaar uiterlijk om", dan loopt het venster door tot de ' +
        'volgende dag — 22:00 tot 06:00 is het normale geval.',
      selector: { time: { no_second: true } },
    }),
    {
      name: 'no_run_from',
      label: 'Niet draaien vanaf',
      // A different question from both fields above it, and from the quiet
      // hours. Those two say when it must be *finished*; the quiet hours are
      // the resident's preference about being disturbed. This is a property of
      // the installation — the dryer against the children's bedroom wall — and
      // it must survive a resident who shortens his quiet hours (SPEC.md §51).
      helper:
        'Uren waarin dit apparaat helemaal niet mag draaien, bijvoorbeeld ' +
        'omdat het onder een slaapkamer staat. Laat beide leeg als er geen ' +
        'verbod is. Een cyclus die het venster in zou lopen wordt ook niet ' +
        'geadviseerd, dus een droger van ruim twee uur krijgt bij een verbod ' +
        'vanaf 23:00 al vanaf 20:45 geen advies meer.',
      selector: { time: { no_second: true } },
    },
    {
      name: 'no_run_until',
      label: 'Weer toegestaan vanaf',
      helper:
        'Ligt deze tijd vóór "niet draaien vanaf", dan loopt het verbod door ' +
        'tot de volgende dag — 23:00 tot 07:00 is het normale geval.',
      selector: { time: { no_second: true } },
    },
    {
      name: 'days_of_week',
      label: 'Dagen',
      helper: 'Op welke dagen dit apparaat mag draaien.',
      selector: { select: { multiple: true, options: DAY_OPTIONS } },
    },
  ];
}

/** Volts per phase, for the ampere hint under the minimum power. */
const VOLTAGE_PER_PHASE = 230;

/** The lowest current a charger will hand a car; below it, nothing charges. */
const CHARGER_MIN_CURRENT_A = 6;

/**
 * What to say under *Minimaal vermogen*, and it is more than a unit.
 *
 * **The number describes the car, not the charger** (SPEC.md §59). Six ampere
 * is the floor below which no car charges, but whether that is 1380 W or 4140 W
 * depends on how many phases the car takes — and nothing about the installation
 * shows it. The old helper listed both figures without saying that, which reads
 * as "pick the likely one"; §57.3 went one worse and called single-phase the
 * common case. Sven filled in 1380 on that basis and measured 4140.
 *
 * So the text says where the answer comes from — a measurement with the car
 * plugged in — and the sum below turns whatever was entered back into ampere,
 * because ampere is the number a charger actually shows. 4140 W reads back as
 * "18,0 A op één fase, of 6,0 A op drie fasen", and only one of those is a
 * setting a charger has.
 *
 * **No stored phase field**, deliberately: it would be a value the engine never
 * reads, and it would sit next to `HomeProfile.phases`, which answers the same
 * sounding question about the house instead of the car.
 */
function minPowerHelper(draft) {
  const charger = draft.device_type === 'ev_charger';
  const single = CHARGER_MIN_CURRENT_A * VOLTAGE_PER_PHASE;
  const three = single * 3;

  const opening = charger
    ? `Het minste waarmee de paal nog laadt. Dit hangt af van de auto en niet ` +
      `van de paal: onder ${CHARGER_MIN_CURRENT_A} ampère laadt geen enkele ` +
      `auto, en dat is ongeveer ${single} W voor een auto die op één fase laadt ` +
      `en ${three} W voor een auto die op drie fasen laadt. Allebei komen ze ` +
      `voor, en aan de installatie is het niet te zien — meet het met de auto ` +
      `aan de paal.`
    : 'Het minste waarmee het apparaat nog iets doet.';

  const entered = Number(draft.min_power_w);
  if (!entered || entered <= 0) {
    return `${opening} Zonder dit getal wordt het apparaat op zijn volle vermogen beoordeeld.`;
  }

  const perPhase = entered / VOLTAGE_PER_PHASE;
  return (
    `${opening} ${formatNumber(entered)} W is ongeveer ` +
    `${formatNumber(perPhase, { decimals: 1 })} A op één fase, of ` +
    `${formatNumber(perPhase / 3, { decimals: 1 })} A op drie fasen.`
  );
}

/** The two flags that follow from the type unless someone says otherwise. */
function behaviourFields(draft) {
  return [
    {
      name: 'is_noisy',
      label: 'Maakt geluid',
      helper: `Standaard voor dit type: ${
        noisyByDefault(draft.device_type) ? 'ja' : 'nee'
      }. Lawaaiige apparaten worden tijdens de stille uren niet geadviseerd.`,
      selector: { boolean: {} },
    },
    {
      name: 'can_modulate',
      label: 'Kan op deelvermogen draaien',
      // A charger takes whatever it is given between its minimum and its
      // maximum; almost everything else runs at one power or not at all
      // (SPEC.md §56.2). Nothing changes until the minimum below is filled in.
      helper:
        'Zet dit aan voor apparatuur die minder dan haar maximum kan ' +
        'gebruiken, zoals de meeste laadpalen. Zonder het minimum hieronder ' +
        'verandert er niets.',
      selector: { boolean: {} },
    },
    {
      name: 'min_power_w',
      label: 'Minimaal vermogen',
      helper: minPowerHelper(draft),
      selector: { number: { min: 0, step: 10, unit_of_measurement: 'W' } },
    },
    {
      name: 'needs_ready_flag',
      label: 'Moet gemeld worden dat er werk in zit',
      // A dishwasher starts when the door closes and nothing here knows
      // whether there is anything in it (SPEC.md §32.5). A charger can see a
      // car for itself, so it is off by type — but an installer may switch it
      // on where that link is missing.
      helper:
        `Standaard voor dit type: ${
          needsReadyFlagByDefault(draft.device_type) ? 'ja' : 'nee'
        }. Staat dit aan, dan adviseert de coach dit apparaat pas te starten ` +
        'nadat iemand op "Klaar / vol" heeft gedrukt. Zo wordt er nooit een ' +
        'lege machine geadviseerd.',
      selector: { boolean: {} },
    },
    {
      name: 'is_flexible',
      label: 'Verplaatsbaar in de tijd',
      helper:
        `Standaard voor dit type: ${
          flexibleByDefault(draft.device_type) ? 'ja' : 'nee'
        }. Alleen verplaatsbare apparaten krijgen een verplaatsingsadvies, en ` +
        'alleen die hebben een tijdvenster nodig.',
      selector: { boolean: {} },
    },
  ];
}

/**
 * The three kinds of truth about control, which never merge (SPEC.md §12).
 *
 * `control_mode` is what the installer wants, `capabilities` is what the
 * hardware can do, `control_forbidden` is what was agreed with this customer.
 * The two controlling modes stay selectable even though 0.1.0 drives nothing:
 * the agreement can only be contradicted — and therefore only be defended — if
 * the contradiction can be expressed.
 */
/**
 * What choosing a level does for *this* appliance, in three whole sentences.
 *
 * One sentence per situation, selected by the situation, the same contract the
 * tile texts follow (SPEC.md §35.9). Assembling one sentence that switches its
 * halves on and off would put a sentence on screen that exists nowhere in the
 * source.
 *
 * The middle one is why the field stays visible on an appliance nobody is
 * advised about. "Alles behalve alleen monitoren wordt als adviseren
 * behandeld" is true of the product and says nothing here, where nothing is
 * behandeld either way — it reads as a choice with no consequence, which is
 * exactly what it was reported as. Said properly it is a standing statement:
 * it decides what happens the day somebody does tick "verplaatsbaar".
 *
 * The last one is the way back, in words. A resident who switched his
 * dishwasher off is the one person who needs to read how to switch it on.
 */
function controlModeHelper(draft) {
  if (draft.control_mode === 'monitor_only') {
    return (
      'Op "alleen monitoren" krijgt dit apparaat geen advies. Zet het op ' +
      '"alleen adviseren" om het weer mee te laten doen.'
    );
  }
  if (!isAdvisable(draft)) {
    return (
      'Dit apparaat krijgt geen advies zolang het niet verplaatsbaar is. ' +
      '"Alleen monitoren" legt vast dat dat zo moet blijven, ook als dat ' +
      'later verandert.'
    );
  }
  return (
    'DomotiApp Energy adviseert in deze versie alleen; alles behalve ' +
    '"alleen monitoren" wordt als adviseren behandeld.'
  );
}

function controlFields(draft) {
  const fields = [
    {
      name: 'control_mode',
      label: 'Bedieningsniveau',
      helper: controlModeHelper(draft),
      selector: {
        select: {
          mode: 'dropdown',
          options: Object.entries(CONTROL_MODE_LABELS).map(
            ([value, label]) => ({
              value,
              label,
            }),
          ),
        },
      },
    },
    {
      name: 'capabilities',
      label: 'Wat kan dit apparaat?',
      helper:
        'Alleen registreren: er wordt niets aangestuurd. Niets aanvinken ' +
        'betekent "niet opgegeven", niet "kan niets".',
      selector: { select: { multiple: true, options: CAPABILITY_OPTIONS } },
    },
    {
      name: 'control_forbidden',
      label: 'Aansturing uitgesloten voor deze installatie',
      helper: 'Een afspraak met de klant, los van wat dit apparaat kan.',
      selector: { boolean: {} },
    },
  ];

  if (draft.control_forbidden) {
    fields.push({
      name: 'control_forbidden_reason',
      label: 'Reden',
      helper: 'Noteer waarom, zodat dit later terug te vinden is.',
      selector: { text: {} },
    });
  }

  return fields;
}

/** The optional entity links that mean something for this type. */
function entityLinkFields(draft) {
  return ENTITY_LINKS.filter(
    (link) => link.types === null || link.types.includes(draft.device_type),
  ).map((link) => ({
    name: link.name,
    label: link.label,
    helper: link.helpers?.[draft.device_type] ?? link.helper,
    selector: { entity: {} },
  }));
}

/** Read the editable fields out of a stored device. */
function draftFrom(device) {
  const draft = { ...NEW_DEVICE, ...device };
  if (Array.isArray(draft.days_of_week)) {
    draft.days_of_week = daysToForm(draft.days_of_week);
  }
  if (draft.is_noisy === undefined) {
    draft.is_noisy = noisyByDefault(draft.device_type);
  }
  if (draft.is_flexible === undefined) {
    draft.is_flexible = flexibleByDefault(draft.device_type);
  }
  for (const [key, value] of Object.entries(draft)) {
    if (value === null) {
      delete draft[key];
    }
  }
  return draft;
}

/** The names of every field this form can ever ask about. */
const ALL_FIELD_NAMES = new Set(
  [
    ...schemaFor({ ...NEW_DEVICE, is_flexible: true, control_forbidden: true }),
    ...ENTITY_LINKS.map((link) => ({ name: link.name })),
  ].map((field) => field.name),
);

/**
 * Values that are filled in but no longer asked for.
 *
 * These are what a type change would drop on save. They stay in the draft while
 * the dialog is open, so switching the type back restores them without
 * retyping, and the dialog names them out loud before the irreversible step.
 */
function orphanedFields(draft, schema) {
  const asked = new Set(schema.map((field) => field.name));
  return [...ALL_FIELD_NAMES].filter(
    (name) =>
      !asked.has(name) &&
      draft[name] !== undefined &&
      draft[name] !== null &&
      draft[name] !== '' &&
      !isDefaultValue(name, draft),
  );
}

/**
 * Whether this value is only what the form itself would have filled in.
 *
 * Dropping such a value loses nothing — the backend resolves an absent
 * `is_noisy` or `is_flexible` back to the same type default (`TYPE_DEFAULT` in
 * `models.py`), and an absent priority back to "normaal" — so warning about it
 * would name a loss that does not happen.
 *
 * It matters from 0.7.1, when the advice fields stopped being asked of an
 * appliance nobody is advised about. Without this, opening a fresh
 * `generic_monitor` would announce that its priority and its noise flag are
 * about to be thrown away, for two values the installer never typed.
 */
function isDefaultValue(name, draft) {
  const defaults = {
    priority: 'normal',
    is_noisy: noisyByDefault(draft.device_type),
    is_flexible: flexibleByDefault(draft.device_type),
    control_mode: 'advice_only',
    days_of_week: ['0', '1', '2', '3', '4', '5', '6'],
    capabilities: [],
    control_forbidden: false,
  };
  if (!(name in defaults)) {
    return false;
  }
  return !differs(draft[name], defaults[name]);
}

/** The Dutch label of a field, for the sentence about what would be dropped. */
function labelOf(name) {
  const link = ENTITY_LINKS.find((entry) => entry.name === name);
  if (link) {
    return link.label;
  }
  const known = {
    ready_before: 'Klaar uiterlijk om',
    ready_from: 'Niet eerder klaar dan',
    ready_days: 'Op welke dagen geldt dit',
    runs_any_time: 'Maakt niet uit wanneer hij klaar is',
    no_run_from: 'Niet draaien vanaf',
    no_run_until: 'Weer toegestaan vanaf',
    days_of_week: 'Dagen',
    control_forbidden_reason: 'Reden',
    // The five that stop being asked once an appliance is only measured. They
    // need names here for the same reason the window fields do: the notice that
    // says what a save would drop has to say it in words the installer typed.
    nominal_power_w: 'Nominaal vermogen',
    energy_per_cycle_kwh: 'Energie per cyclus',
    duration_minutes: 'Duur van een cyclus',
    priority: 'Prioriteit',
    is_noisy: 'Maakt geluid',
    // The two switches, which only ever go on a type that can never be
    // advised. A stored "alleen monitoren" on such an appliance changes
    // nothing, but it is still something somebody chose, so dropping it is
    // announced like any other value.
    control_mode: 'Bedieningsniveau',
    is_flexible: 'Verplaatsbaar in de tijd',
    can_modulate: 'Kan op deelvermogen draaien',
    needs_ready_flag: 'Moet gemeld worden dat er werk in zit',
    min_power_w: 'Minimaal vermogen',
  };
  return known[name] || name;
}

/** The payload to send: the schema's fields, cleared ones as null. */
function payloadFrom(draft, schema) {
  const payload = { device_type: draft.device_type };
  if (draft.id) {
    payload.id = draft.id;
  }
  for (const field of schema) {
    if (field.name === 'device_type') {
      continue;
    }
    const value = draft[field.name];
    payload[field.name] =
      field.name === 'days_of_week'
        ? daysToStorage(value)
        : value === undefined || value === ''
          ? null
          : value;
  }
  return payload;
}

/** Whether two draft values differ, treating the array fields properly. */
function differs(left, right) {
  if (Array.isArray(left) || Array.isArray(right)) {
    return (left || []).join('|') !== (right || []).join('|');
  }
  return (left ?? null) !== (right ?? null);
}

/**
 * Weekdays as the form speaks them: strings.
 *
 * The draft holds strings for this one field, so what is stored as `[0, 6]`
 * still shows as Monday and Sunday selected. Handing the select the integers
 * would leave every chip unselected, because the option values are strings.
 */
function daysToForm(value) {
  if (!Array.isArray(value)) {
    return value;
  }
  return value.map((day) => String(day));
}

/** Weekdays as the backend stores them: integers, Monday = 0 (SPEC.md §8). */
function daysToStorage(value) {
  if (!Array.isArray(value)) {
    return value;
  }
  return value
    .map((day) => Number(day))
    .filter((day) => Number.isInteger(day) && day >= 0 && day <= 6);
}

/**
 * How the questions are grouped in the dialog.
 *
 * The three sections an installer needs on every visit are open; the agreement
 * about control and the optional entity links are folded away, because most
 * visits do not touch them. Together that turns a scroll of twenty-odd fields
 * into a form that fits a phone with two things left to open (SPEC.md §11).
 *
 * The fields themselves still come from one `schemaFor`, so this list groups
 * and never defines: a field that is not mentioned here would simply not be
 * shown, which the test at the bottom of the device tests guards against.
 */
/**
 * The folding sections, in the order an installer fills them in.
 *
 * **Only the first two open.** They were three, and on a phone in a meter
 * cupboard that is most of the screen before anything is typed: naming the
 * appliance and stating what it uses is the whole of a first pass, and the
 * checklist asks for nothing outside those two. What comes after is a second
 * visit — the resident says when it may run, the installer links the sensors —
 * so those start folded and cost one tap when they are wanted.
 *
 * "Wanneer het mag draaien" moved with them and that is the contestable half of
 * this: it holds the ready window, which is worth a point on the data quality.
 * It is not worth a point on *completeness* though (SPEC.md §16), and it is the
 * one section a resident opens on his own screen rather than the installer at
 * hand-over.
 */
const SECTIONS = [
  {
    title: 'Apparaat',
    open: true,
    fields: ['name', 'device_type', 'enabled', 'location', 'priority'],
  },
  {
    title: 'Verbruik',
    open: true,
    fields: [
      'nominal_power_w',
      'can_modulate',
      'min_power_w',
      'energy_per_cycle_kwh',
      'duration_minutes',
    ],
  },
  {
    title: 'Wanneer het mag draaien',
    open: false,
    fields: [
      'is_flexible',
      'is_noisy',
      'needs_ready_flag',
      'runs_any_time',
      'ready_before',
      'ready_days',
      'ready_from',
      'no_run_from',
      'no_run_until',
      'days_of_week',
    ],
  },
  {
    title: 'Koppelingen',
    open: false,
    fields: ENTITY_LINKS.map((link) => link.name),
  },
  {
    title: 'Aansturing',
    open: false,
    fields: [
      'control_mode',
      'capabilities',
      'control_forbidden',
      'control_forbidden_reason',
    ],
  },
  { title: 'Notities', open: false, fields: ['notes'] },
];

export const devicesTab = {
  id: 'devices',
  label: 'Apparaten',
  icon: 'mdi:washing-machine',

  create({ getHass, state, overlay }) {
    const element = el('div', { class: 'tab-content' });
    const devices = card('Apparaten');

    const listNotice = notice('mdi:information-outline');
    const addButton = button('Apparaat toevoegen', { primary: true });

    let editing = null;
    let draft = {};
    let saved = {};
    let revision = null;
    /**
     * The fields the installer changed by hand in this dialog.
     *
     * Only these survive a change of device type. Without it, picking a
     * different type would silently overwrite a deliberate "this dishwasher is
     * not noisy" with the default for the new type.
     */
    let touched = new Set();
    /** The schema currently on the form, so it is only replaced when it moves. */
    let schemaKey = '';
    /**
     * Whether this user owns the whole appliance or only how it should behave.
     *
     * This is the tab where the split runs *through* a row rather than around
     * it (SPEC.md §33.4). A dishwasher carries the installer's work — power,
     * energy per cycle, entity links — and the resident's at the same time:
     * when it has to be finished, on which days, whether it may be noisy, and
     * whether it may be steered at all.
     */
    let isAdmin = true;
    // Live power per appliance id, refreshed before every sync. Only the
    // appliances that link a power entity appear in it, which is what keeps an
    // unlinked one from getting an empty line (SPEC.md §37).
    let devicePower = {};
    let powerUnusable = [];
    // The lowest running power per appliance id, kept in the coordinator's
    // memory since the last restart (SPEC.md §59.3). Only the appliances that
    // have actually been seen running appear in it.
    let deviceLowest = {};
    // Which appliances a resident has said there is work in, with the moment
    // each flag expires (SPEC.md §32.5). Live state, so it arrives with the
    // coach result rather than with the device rows.
    let readyFlags = {};

    const rowList = createRowList({
      emptyText:
        'Nog geen apparaten. Voeg de apparaten toe waarover DomotiApp Energy ' +
        'mag adviseren, met hun vermogen, verbruik per cyclus en tijdvenster.',
      createRow: () => createDeviceRow(),
    });

    const addActions = el('div', { class: 'actions' }, [addButton]);
    const managedNotice = notice('mdi:shield-account-outline');

    devices.body.append(
      rowList.element,
      addActions,
      managedNotice.element,
      listNotice.element,
    );
    element.appendChild(devices.element);

    // --- The dialog ---------------------------------------------------------

    const dialog = createDialog({ title: 'Apparaat', overlay });
    const requiredNotice = notice('mdi:asterisk');
    const orphanNotice = notice('mdi:eye-off-outline');
    // Distinct from orphanNotice above, which is about *values* that will be
    // dropped. This one is about *messages* whose field is not on screen, and
    // both can be true at once — sharing one notice would let each overwrite
    // the other depending on which refresh ran last.
    const hiddenErrorNotice = notice('mdi:alert-circle-outline');
    const warningNotice = notice('mdi:alert-outline');
    const dialogNotice = notice('mdi:content-save-outline');

    /**
     * One form per section, each handed only its own fields.
     *
     * Never the whole payload it emits: `ha-form` hands back the complete data
     * object it was given with one field changed, so a form holding a stale
     * copy of another section's values would quietly undo an edit made
     * elsewhere. That is the bug phase 7b was fixed for.
     */
    function changeHandler(names) {
      return (part) => {
        const previousType = draft.device_type;
        // A section owns the fields it *declares*, but only renders the ones
        // that mean something for this draft. Copying back the whole declared
        // list would read `undefined` for every hidden one and wipe it from
        // the draft — so changing "verplaatsbaar in de tijd" would silently
        // throw away the noise flag sitting behind it, and switching the flag
        // back would not bring it back. Only what is on screen answers here.
        const rendered = new Set(schemaFor(draft).map((field) => field.name));
        const owned = names.filter((name) => rendered.has(name));
        for (const name of owned) {
          if (differs(part[name], draft[name])) {
            touched.add(name);
          }
        }
        const mine = {};
        for (const name of owned) {
          mine[name] = part[name];
        }
        draft = { ...draft, ...mine };
        if (draft.device_type !== previousType) {
          applyTypeDefaults();
        }
        state.setDraft(DRAFT, draft);
        refreshDialog();
      };
    }

    const forms = SECTIONS.map((definition) => {
      const host = section(definition.title, { open: definition.open });
      const form = createForm(getHass(), [], changeHandler(definition.fields));
      host.body.appendChild(form.element);
      return { definition, host, form };
    });

    dialog.body.append(
      requiredNotice.element,
      ...forms.map(({ host }) => host.element),
      orphanNotice.element,
      hiddenErrorNotice.element,
      warningNotice.element,
      dialogNotice.element,
    );

    const saveButton = button('Opslaan', { primary: true });
    const cancelButton = button('Annuleren');
    dialog.actions.append(cancelButton, saveButton);

    const confirmDialog = createConfirmDialog({ overlay });

    /** Follow the type for the two flags nobody has touched (SPEC.md §8). */
    function applyTypeDefaults() {
      if (!touched.has('is_noisy')) {
        draft.is_noisy = noisyByDefault(draft.device_type);
      }
      if (!touched.has('is_flexible')) {
        draft.is_flexible = flexibleByDefault(draft.device_type);
      }
      if (!touched.has('needs_ready_flag')) {
        draft.needs_ready_flag = needsReadyFlagByDefault(draft.device_type);
      }
    }

    // --- Rows ---------------------------------------------------------------

    function createDeviceRow() {
      const name = el('p', { class: 'row-name' });
      const meta = el('p', { class: 'row-meta' });
      const power = el('p', { class: 'row-meta' });
      const status = el('div', { class: 'row-status' });
      const statusIcon = el('ha-icon', { attrs: { 'aria-hidden': 'true' } });
      const statusText = el('span');
      status.append(statusIcon, statusText);

      // **One of the two places this button belongs** (SPEC.md §44.6): here,
      // where a resident is tidying the kitchen and fills the machine at the
      // end of it. The other is under the advice that asks about it, which is
      // the other moment he thinks of it — the same command, two occasions.
      const readyButton = button('Klaar / vol');
      const readyLine = el('p', { class: 'row-meta' });
      const editButton = button('Bewerken');
      const deleteButton = button('Verwijderen');
      deleteButton.classList.add('button-danger');

      const row = el('div', { class: 'row-item' }, [
        el('div', { class: 'row-main' }, [
          name,
          meta,
          power,
          readyLine,
          status,
        ]),
        el('div', { class: 'row-buttons' }, [
          readyButton,
          editButton,
          deleteButton,
        ]),
      ]);

      let current = null;
      onTap(editButton, () => current && openDialog(current, editButton));
      onTap(deleteButton, () => current && askDelete(current, deleteButton));
      onTap(readyButton, () => current && toggleReady(current));

      return {
        element: row,
        update(device) {
          current = device;
          name.textContent = device.name || 'Naamloos apparaat';
          meta.textContent = describeDevice(device);

          // No line at all without a reading. An appliance nobody linked is
          // not a gap, so "onbekend" next to every one of them would report a
          // fault where there is none — the same rule the tile texts follow.
          const watts = devicePower[device.id];
          const hasReading = typeof watts === 'number';
          // **A refused link is not the same as no link** (SPEC.md §57). A
          // power entity that reports a kWh total — the classic wrong pick — is
          // refused rather than read as watts, and until now that looked
          // exactly like an appliance nobody had linked anything to.
          const refused = !hasReading && powerUnusable.includes(device.id);
          power.textContent = hasReading
            ? `Nu: ${formatNumber(watts)} W${describeLowest(device)}`
            : refused
              ? 'De gekoppelde vermogenssensor is niet te gebruiken: hij moet ' +
                'in W of kW meten en een waarde melden.'
              : '';
          power.dataset.tone = refused ? 'warning' : '';
          setVisible(power, hasReading || refused);

          // The flag, and the sentence that goes with it. Only for appliances
          // that need one at all: a charger is not asked whether somebody
          // loaded it (SPEC.md §32.5).
          const flag = readyFlags[device.id];
          setVisible(readyButton, Boolean(device.needs_ready_flag));
          readyButton.textContent = flag ? 'Toch niet vol' : 'Klaar / vol';
          readyLine.textContent = describeReady(flag);
          setVisible(readyLine, Boolean(device.needs_ready_flag && flag));
          // A resident opens the same dialog and can change six fields in it,
          // so "Instellen" rather than "Bewerken" or "Bekijken": he is not
          // editing the appliance, and he is not only looking either.
          editButton.textContent = isAdmin ? 'Bewerken' : 'Instellen';
          setVisible(deleteButton, isAdmin);

          const shown = statusOf(device);
          statusIcon.setAttribute('icon', shown.icon);
          statusText.textContent = shown.text;
          status.dataset.tone = shown.tone;
        },
      };
    }

    /**
     * The one line that says what this appliance is.
     *
     * **An appliance nobody is advised about drops the advice words.** It read
     * "Overig, alleen meten · Normaal · Alleen adviseren": a priority that
     * orders nothing, next to a control level that says "adviseren" about an
     * appliance that gets no advice. Three of the four words were noise, and
     * the two that were left contradicted the first (SPEC.md §38.3).
     *
     * What stays is what identifies it — type, where it is, what it draws. The
     * status line underneath already says it is only measured, so nothing is
     * lost by leaving that out here.
     */
    function describeDevice(device) {
      const parts = [TYPE_LABELS[device.device_type] || device.device_type];
      if (device.location) {
        parts.push(device.location);
      }
      if (!isAdvisable(draftFrom(device))) {
        if (typeof device.nominal_power_w === 'number') {
          parts.push(`${formatNumber(device.nominal_power_w)} W`);
        }
        // The level is shown exactly where it is the *reason* there is no
        // advice. Dropping it wholesale in 0.7.1 fixed one lie and made a
        // worse one: a dishwasher the resident had switched to "alleen
        // meekijken" read "Vaatwasser · Keuken · 2.000 W" and "Compleet.",
        // with his own instruction nowhere on the row. The status line does
        // not cover it — that sentence only appears while no power sensor is
        // linked (SPEC.md §38.3).
        if (device.control_mode === 'monitor_only') {
          parts.push(CONTROL_MODE_LABELS.monitor_only);
        }
        return parts.join(' · ');
      }
      parts.push(PRIORITY_LABELS[device.priority] || device.priority);
      parts.push(
        CONTROL_MODE_LABELS[device.control_mode] || device.control_mode,
      );
      return parts.join(' · ');
    }

    /**
     * Say how long "hij is vol" stays true, in the words somebody would use.
     *
     * **Two whole sentences, and which one you get is not a detail** (SPEC.md
     * §32.6). Where a status or remaining-time entity is linked the flag goes
     * out by itself when the programme ends, and the expiry is a backstop.
     * Where nothing is linked it is the *only* way the flag ever goes out, and
     * the resident has to know that at the moment he presses the button —
     * not when he wonders why nothing happened.
     *
     * The moment is named either way, because a resident who fills the
     * dishwasher at ten in the evening needs to know it still counts tomorrow
     * morning.
     */
    function describeReady(flag) {
      if (!flag) {
        return '';
      }
      const until = formatMoment(flag.expires_at);
      if (flag.auto_clears) {
        return `Staat vol. Dit vervalt ${until}, of eerder zodra hij klaar is.`;
      }
      return (
        `Staat vol. We kunnen niet zien wanneer hij klaar is, dus dit blijft ` +
        `staan tot ${until}. Zet het eerder uit als er niets meer in zit.`
      );
    }

    /** Say it, or take it back. The panel state refreshes with the answer. */
    async function toggleReady(device) {
      const wasSet = Boolean(readyFlags[device.id]);
      try {
        await createApi(getHass()).setDeviceReady(device.id, !wasSet);
        state.setLive(await createApi(getHass()).getCoach());
      } catch (error) {
        listNotice.set(describeError(error), { tone: 'warning' });
      }
    }

    /**
     * The lowest power this appliance has been seen running at, if it matters.
     *
     * **Only where somebody has to fill in a minimum** — an appliance with
     * *Kan op deelvermogen draaien* switched on. Everywhere else it is a true
     * fact that answers no question, and a row that reports everything reports
     * nothing (SPEC.md §59.3).
     *
     * *Sinds herstart* is in the sentence because it is the whole truth about
     * this figure: it lives in the coordinator's memory and never in storage,
     * so a restart starts the observation over. Leaving that out would let it
     * read as "the lowest this charger can do", which is precisely the claim
     * this product must not make on the customer's behalf.
     */
    function describeLowest(device) {
      if (!device.can_modulate) {
        return '';
      }
      const lowest = deviceLowest[device.id];
      if (typeof lowest !== 'number') {
        return '';
      }
      return ` · laagste meting sinds herstart: ${formatNumber(lowest)} W`;
    }

    /**
     * The one line under a row that says where this device stands.
     *
     * The agreement not to control it comes with its reason, because that is
     * what someone reads two years later — which is the whole point of writing
     * it down (SPEC.md §12).
     */
    function statusOf(device) {
      if (device.invalid_reason === 'unknown_type') {
        return {
          icon: 'mdi:alert-circle-outline',
          tone: 'error',
          text: `Onbekend apparaattype '${device.device_type}'. Dit apparaat wordt niet gebruikt.`,
        };
      }
      if (!device.enabled) {
        return {
          icon: 'mdi:pause-circle-outline',
          tone: 'info',
          text: 'Uitgeschakeld — krijgt geen advies.',
        };
      }
      const errors = fieldErrors(currentIssues(), device.id);
      if (errors) {
        return {
          icon: 'mdi:progress-wrench',
          tone: 'warning',
          text: `Nog niet compleet: ${Object.values(errors)[0]}`,
        };
      }
      // Incompleteness first, because it is the one thing to act on. The
      // agreement about control is appended rather than replaced: it has to
      // stay readable whatever else is true of this row (SPEC.md §12).
      const missing = missingRequired(draftFrom(device));
      const agreement = device.control_forbidden
        ? ` · Aansturing uitgesloten — ${
            device.control_forbidden_reason || 'geen reden genoteerd'
          }`
        : '';

      // An appliance that only measures owes exactly one thing: the sensor to
      // measure with. Said as a plain line and never as an incompleteness —
      // it carries no weight in the data quality, so the resident's number
      // does not move (Sven, 2026-08-09).
      if (!isAdvisable(draftFrom(device)) && !device.power_entity) {
        return {
          icon: 'mdi:gauge-empty',
          tone: 'info',
          text:
            'Nog geen vermogenssensor gekoppeld — dit apparaat wordt alleen ' +
            'gemeten, en er valt nu niets te meten.' +
            agreement,
        };
      }

      if (missing.length) {
        return {
          icon: 'mdi:progress-wrench',
          tone: 'warning',
          text:
            `Nog niet compleet: ${missing
              .map((name) => requiredLabel(name, device))
              .join(
                ', ',
              )} ${missing.length > 1 ? 'ontbreken' : 'ontbreekt'}. ` +
            'Telt niet mee voor de datakwaliteit.' +
            agreement,
        };
      }
      if (device.control_forbidden) {
        return {
          icon: 'mdi:lock-outline',
          tone: 'info',
          text: agreement.replace(' · ', ''),
        };
      }
      return {
        icon: 'mdi:check-circle-outline',
        tone: 'info',
        text: 'Compleet.',
      };
    }

    function currentIssues() {
      return state.get().config?.issues || {};
    }

    // --- The dialog cycle ---------------------------------------------------

    function openDialog(device, opener) {
      editing = device || null;
      draft = draftFrom(device || {});
      saved = { ...draft };
      revision = state.get().config?.revision ?? null;
      touched = new Set();
      schemaKey = '';

      dialog.setTitle(device ? 'Apparaat bewerken' : 'Apparaat toevoegen');
      dialogNotice.set('');
      // Every visit starts with the same three sections open, so the dialog
      // looks the same each time rather than remembering a previous mood.
      for (const { definition, host } of forms) {
        host.setOpen(definition.open);
      }
      refreshDialog();
      showErrors();
      dialog.show({ focusReturnsTo: opener });
    }

    function refreshDialog() {
      const schema = applyRole(schemaFor(draft), DRAFT, isAdmin);
      // Only when the questions actually changed. Handing `ha-form` a fresh
      // schema on every keystroke makes it rebuild every field, which throws
      // away whatever control the installer had open — a multi-select loses the
      // choice they were in the middle of making.
      const key = JSON.stringify(schema);
      const schemaMoved = key !== schemaKey;
      schemaKey = key;

      for (const { definition, host, form } of forms) {
        const mine = schema.filter((field) =>
          definition.fields.includes(field.name),
        );
        if (schemaMoved) {
          form.setSchema(mine);
        }
        const data = {};
        for (const field of mine) {
          data[field.name] = draft[field.name];
        }
        form.setData(data);
        // A section with nothing left to ask disappears rather than standing
        // there as an empty heading.
        setVisible(host.element, mine.length > 0);
      }

      // The marker on a field only helps someone already looking at it. In a
      // form of twenty questions the useful answer to "what is missing" is a
      // list at the top that names it, and shrinks as the fields are filled.
      const missing = missingRequired(draft);
      requiredNotice.set(
        missing.length
          ? 'Nog nodig voor een compleet apparaat: ' +
              `${missing.map((name) => requiredLabel(name, draft)).join(', ')}. ` +
              'Opslaan mag ook zonder — het apparaat telt dan alleen nog niet ' +
              'mee voor de datakwaliteit.'
          : 'Dit apparaat is compleet: alles wat de datakwaliteit vraagt is ingevuld.',
        {
          tone: missing.length ? 'warning' : 'success',
          icon: missing.length ? 'mdi:asterisk' : 'mdi:check-circle-outline',
        },
      );

      const orphans = orphanedFields(draft, schema);
      orphanNotice.set(
        orphans.length
          ? 'Deze ingevulde gegevens worden voor dit apparaat niet meer ' +
              `gevraagd en verdwijnen bij opslaan: ${orphans.map(labelOf).join(', ')}. ` +
              'Zet het apparaattype, "verplaatsbaar in de tijd" of het ' +
              'bedieningsniveau terug om ze te behouden.'
          : '',
        { tone: 'warning' },
      );

      const warnings = editing
        ? warningMessages(currentIssues(), editing.id)
        : [];
      warningNotice.set(warnings.join(' '), { tone: 'warning' });
      saveButton.disabled = !isDirty();
    }

    /**
     * Put every section's own errors on its own form.
     *
     * The window fields are the live case here: `_validate_time_window` reports
     * an invalid window whether or not the device is flexible, while the form
     * only asks for those fields when it is. Untick "verplaatsbaar in de tijd"
     * on a device with a broken window and the message had nowhere to go
     * (core/forms.js).
     */
    function showErrors() {
      const errors = editing ? fieldErrors(currentIssues(), editing.id) : null;
      const rendered = forms.flatMap(({ form }) =>
        (form.element.schema || []).map((field) => field.name),
      );
      const { shown, orphaned } = splitFieldErrors(errors, rendered);

      for (const { definition, form } of forms) {
        const mine = {};
        for (const name of definition.fields) {
          if (name in shown) {
            mine[name] = messageForRole(DRAFT, name, shown[name], isAdmin);
          }
        }
        form.setErrors(Object.keys(mine).length ? mine : null);
      }

      hiddenErrorNotice.set(describeOrphanedErrors(orphaned, labelOf), {
        tone: 'warning',
      });
    }

    /** Push the current role into the list and the dialog. */
    function applyRoleToTab() {
      setVisible(addActions, isAdmin);
      managedNotice.set(isAdmin ? '' : MANAGED_NOTICE, { tone: 'info' });
      rowList.sync(state.get().config?.devices || []);
      if (dialog.isOpen()) {
        schemaKey = '';
        refreshDialog();
      }
    }

    function isDirty() {
      const names = new Set([...Object.keys(draft), ...Object.keys(saved)]);
      return [...names].some((name) => differs(draft[name], saved[name]));
    }

    /**
     * What a resident changed, as the allow-list of `devices/set_operation`.
     *
     * Built from what actually differs rather than from everything he owns, so
     * an untouched field is not resent — and never from `touched`, which also
     * collects the type defaults a change of device type writes.
     */
    function operationFrom() {
      const operation = {};
      for (const name of Object.keys(draft)) {
        if (residentOwns(DRAFT, name) && differs(draft[name], saved[name])) {
          operation[name] = draft[name] ?? null;
        }
      }
      return operation;
    }

    function setBusy(busy) {
      for (const { form } of forms) {
        form.setDisabled(busy);
      }
      saveButton.disabled = busy || !isDirty();
      cancelButton.disabled = busy;
    }

    async function save() {
      state.setSaving(true);
      setBusy(true);
      dialogNotice.set('Bezig met opslaan…', { tone: 'info' });

      const api = createApi(getHass());
      const payload = payloadFrom(draft, schemaFor(draft));

      try {
        // Two paths, because they are two different acts. An installer edits
        // the whole appliance and saves it whole; a resident changes how it
        // should behave and sends only the fields he owns. Sending his edit
        // through `devices/update` would be sending the whole row — and that
        // command has no field filter, on purpose (SPEC.md §33.10).
        let result;
        if (!isAdmin && editing) {
          result = await api.setDeviceOperation(
            revision,
            editing.id,
            operationFrom(),
          );
        } else if (editing) {
          result = await api.updateDevice(revision, {
            ...payload,
            id: editing.id,
          });
        } else {
          result = await api.createDevice(revision, payload);
        }
        applyWrite(result, editing ? 'update' : 'create');
        const name = result.item?.name || 'zonder naam';
        state.clearDraft(DRAFT);
        dialog.close();
        listNotice.set(
          editing
            ? `Het apparaat '${name}' is bijgewerkt.`
            : `Het apparaat '${name}' is toegevoegd.`,
          { tone: 'success' },
        );
      } catch (error) {
        if (isRevisionConflict(error)) {
          // The dialog stays open and keeps every field (SPEC.md §49.4). A
          // stale revision means "your base is old", not "your input is
          // wrong", and this is the longest form in the panel.
          state.setConfig(error.config);
          revision = error.config?.revision ?? revision;
          dialogNotice.set(
            conflictSentence(
              conflictKind(error.config?.devices, editing?.id ?? null, editing),
            ),
            { tone: 'warning' },
          );
        } else {
          // The one refusal the backend makes has to read as an instruction
          // rather than as a failure (SPEC.md §12).
          dialogNotice.set(describeError(error), { tone: 'warning' });
        }
      } finally {
        state.setSaving(false);
        setBusy(false);
      }
    }

    /**
     * What to tell the installer when the configuration moved under him.
     *
     * One whole sentence per situation rather than one sentence with a tail,
     * because the three situations ask him to do three different things
     * (SPEC.md §26 and §49.4).
     */
    function conflictSentence(kind) {
      if (kind === 'removed') {
        return (
          'Dit apparaat is intussen ergens anders verwijderd. Je invoer staat ' +
          'hier nog, maar opslaan lukt niet meer; maak het opnieuw aan als je ' +
          'het terug wilt.'
        );
      }
      if (kind === 'same-row') {
        return (
          'Dit apparaat is intussen ook ergens anders gewijzigd. Je invoer ' +
          'staat er nog; als je nu opslaat, vervangt hij die andere wijziging.'
        );
      }
      return (
        'Er is intussen ergens anders iets aan de configuratie gewijzigd, maar ' +
        'niet aan dit apparaat. Je invoer staat er nog; druk opnieuw op ' +
        'Opslaan om hem te bewaren.'
      );
    }

    /** Fold one write answer into the panel state, without re-reading. */
    function applyWrite(result, kind, removedId = null) {
      const config = state.get().config;
      const rows = [...(config.devices || [])];
      if (kind === 'create') {
        rows.push(result.item);
      } else if (kind === 'update') {
        const index = rows.findIndex((row) => row.id === result.item.id);
        rows[index >= 0 ? index : rows.length] = result.item;
      } else {
        const index = rows.findIndex((row) => row.id === removedId);
        if (index >= 0) {
          rows.splice(index, 1);
        }
      }
      state.setConfig({
        ...config,
        devices: rows,
        revision: result.revision,
        issues: result.issues ?? config.issues,
      });
    }

    async function remove(device) {
      state.setSaving(true);
      listNotice.set('Bezig met verwijderen…', { tone: 'info' });
      try {
        const result = await createApi(getHass()).deleteDevice(
          state.get().config?.revision ?? null,
          device.id,
        );
        applyWrite(result, 'delete', device.id);
        listNotice.set(
          `Het apparaat '${device.name || 'zonder naam'}' is verwijderd.`,
          { tone: 'success' },
        );
      } catch (error) {
        if (isRevisionConflict(error)) {
          state.setConfig(error.config);
          listNotice.set(
            'De configuratie is intussen ergens anders gewijzigd. Er is niets ' +
              'verwijderd; de lijst is opnieuw geladen.',
            { tone: 'warning' },
          );
        } else {
          listNotice.set(describeError(error), { tone: 'warning' });
        }
      } finally {
        state.setSaving(false);
      }
    }

    function askDelete(device, opener) {
      confirmDialog.ask(
        {
          title: 'Apparaat verwijderen',
          text:
            `Weet je zeker dat je '${device.name || 'dit apparaat'}' wilt ` +
            'verwijderen? Er wordt daarna niet meer over geadviseerd.',
          focusReturnsTo: opener,
        },
        () => remove(device),
      );
    }

    // --- Leaving with unsaved changes ---------------------------------------

    /**
     * Closing a dialog that holds changes asks first, visibly (SPEC.md §22).
     *
     * A notice at the bottom of a long form is not a question: it can sit below
     * the fold while the installer clicks the backdrop a second time and loses
     * the lot. So the question is a dialog of its own, and Escape, the close
     * button, the backdrop and Annuleren all reach it through here.
     */
    function mayClose() {
      if (!isDirty()) {
        state.clearDraft(DRAFT);
        return true;
      }
      askDiscard();
      return false;
    }

    function askDiscard(afterDiscard = null) {
      confirmDialog.ask(
        {
          title: 'Wijzigingen verwerpen?',
          text:
            'Je hebt wijzigingen die nog niet zijn opgeslagen. Verwerp je ze, ' +
            'dan zijn ze weg.',
          confirmLabel: 'Verwerpen',
          cancelLabel: 'Terug naar het formulier',
          // Nothing behind this question is reachable while it stands, not even
          // the form it is about.
          inertWhileOpen: dialog.element,
        },
        () => {
          state.clearDraft(DRAFT);
          draft = { ...saved };
          dialog.close();
          afterDiscard?.();
        },
      );
    }

    dialog.onCloseRequest(mayClose);
    onTap(cancelButton, () => {
      if (mayClose()) {
        dialog.close();
      }
    });
    onTap(saveButton, () => {
      if (!saveButton.disabled) {
        save();
      }
    });
    onTap(addButton, () => openDialog(null, addButton));

    // --- Panel plumbing -----------------------------------------------------

    function update(panelState) {
      const config = panelState.config;
      if (!config) {
        return;
      }
      if (panelState.isAdmin !== isAdmin) {
        isAdmin = panelState.isAdmin;
        applyRoleToTab();
      }
      devicePower = panelState.live?.metrics?.device_power_w || {};
      powerUnusable = panelState.live?.metrics?.device_power_unusable || [];
      deviceLowest = panelState.live?.metrics?.device_power_lowest_w || {};
      readyFlags = panelState.live?.ready_devices || {};
      rowList.sync(config.devices || []);
      for (const { form } of forms) {
        form.setHass(getHass());
      }
      if (dialog.isOpen() && editing) {
        showErrors();
      }
    }

    function canLeave(proceed) {
      if (confirmDialog.isOpen()) {
        return false;
      }
      if (!dialog.isOpen()) {
        return true;
      }
      if (!isDirty()) {
        dialog.close();
        return true;
      }
      // The same question, and leaving continues once it is answered.
      askDiscard(proceed);
      return false;
    }

    return { element, update, canLeave };
  },
};
