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
  createApi,
  describeError,
  fieldErrors,
  isRevisionConflict,
  warningMessages,
} from '../core/api.js';
import { createConfirmDialog, createDialog } from '../core/dialog.js';
import { button, card, el, notice } from '../core/dom.js';
import { createForm } from '../core/forms.js';
import { createRowList } from '../core/rows.js';
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
    helper: 'Het actuele vermogen van dit apparaat.',
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

/**
 * The fields the data quality checklist actually asks of a device.
 *
 * This mirrors `engine/completeness.py`, which is the real source of truth:
 * `_has_complete_device_profile` wants a power **and** an energy per cycle, and
 * `_flexible_devices_have_windows` wants both ends of a window on every usable
 * flexible device. `tests/test_calculator.py` pins those two rules, so a change
 * there fails a test rather than quietly leaving this marking behind.
 */
function requiredFields(draft) {
  const required = ['nominal_power_w', 'energy_per_cycle_kwh'];
  if (draft.is_flexible) {
    required.push('earliest_start', 'latest_finish');
  }
  return required;
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

/** The Dutch name of a field, for the sentence about what is still missing. */
const REQUIRED_LABELS = {
  nominal_power_w: 'nominaal vermogen',
  energy_per_cycle_kwh: 'energie per cyclus',
  earliest_start: 'vroegste start',
  latest_finish: 'laatste eindtijd',
};

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
    { name: 'notes', label: 'Notities', selector: { text: { multiline: true } } },
  ];

  return fields.map((field) => markRequired(field, required));
}

/** What the device uses, which is what a saving can be calculated from. */
function powerFields(draft) {
  return [
    {
      name: 'nominal_power_w',
      label: 'Nominaal vermogen',
      helper: powerHelper(draft.device_type),
      selector: { number: { min: 0, step: 10, unit_of_measurement: 'W' } },
    },
    {
      name: 'energy_per_cycle_kwh',
      label: 'Energie per cyclus',
      // Without this there is no saving to calculate, so the advice can only
      // say "now is a good moment" and never what it is worth (SPEC.md §16).
      helper: energyHelper(draft.device_type),
      selector: { number: { min: 0, step: 0.1, unit_of_measurement: 'kWh' } },
    },
    {
      name: 'duration_minutes',
      label: 'Duur van een cyclus',
      helper: 'In minuten. Wordt getoetst aan het tijdvenster hieronder.',
      selector: { number: { min: 0, step: 5, unit_of_measurement: 'min' } },
    },
  ];
}

/** What "a cycle" means differs enough per type to be worth saying. */
function powerHelper(deviceType) {
  const perType = {
    ev_charger: 'Het laadvermogen waarmee deze paal levert.',
    home_battery: 'Het laad- of ontlaadvermogen van de batterij.',
    heat_pump: 'Het elektrische opgenomen vermogen, niet het thermische.',
    electric_boiler: 'Het vermogen van het verwarmingselement.',
  };
  return perType[deviceType] || 'Het vermogen tijdens gebruik.';
}

function energyHelper(deviceType) {
  const perType = {
    ev_charger: 'De energie van een gemiddelde laadbeurt.',
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

/**
 * The allowed time window, shown only for a device that may be moved.
 *
 * Tied to `is_flexible` and not to the type, because that is exactly what the
 * data quality checklist asks: every *usable flexible* device needs a window.
 * A device the installer marked as not flexible is never moved, so a window
 * would be a question about something that will not happen.
 */
function windowFields(draft) {
  if (!draft.is_flexible) {
    return [];
  }
  return [
    {
      name: 'earliest_start',
      label: 'Vroegste start',
      helper:
        'Laat beide tijden leeg als er geen venster is. Een eindtijd vóór de ' +
        'starttijd loopt door tot de volgende dag — 22:00 tot 06:00 is het ' +
        'normale geval.',
      selector: { time: {} },
    },
    { name: 'latest_finish', label: 'Laatste eindtijd', selector: { time: {} } },
    {
      name: 'days_of_week',
      label: 'Dagen',
      helper: 'Op welke dagen dit apparaat mag draaien.',
      selector: { select: { multiple: true, options: DAY_OPTIONS } },
    },
  ];
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
      name: 'is_flexible',
      label: 'Verplaatsbaar in de tijd',
      helper: `Standaard voor dit type: ${
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
function controlFields(draft) {
  const fields = [
    {
      name: 'control_mode',
      label: 'Bedieningsniveau',
      helper:
        'DomotiApp Energy adviseert in deze versie alleen; alles behalve ' +
        '"alleen monitoren" wordt als adviseren behandeld.',
      selector: {
        select: {
          mode: 'dropdown',
          options: Object.entries(CONTROL_MODE_LABELS).map(([value, label]) => ({
            value,
            label,
          })),
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
      draft[name] !== '',
  );
}

/** The Dutch label of a field, for the sentence about what would be dropped. */
function labelOf(name) {
  const link = ENTITY_LINKS.find((entry) => entry.name === name);
  if (link) {
    return link.label;
  }
  const known = {
    earliest_start: 'Vroegste start',
    latest_finish: 'Laatste eindtijd',
    days_of_week: 'Dagen',
    control_forbidden_reason: 'Reden',
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
        : (value === undefined || value === '' ? null : value);
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

export const devicesTab = {
  id: 'devices',
  label: 'Apparaten',
  icon: 'mdi:washing-machine',
  adminOnly: true,

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

    const rowList = createRowList({
      emptyText:
        'Nog geen apparaten. Voeg de apparaten toe waarover DomotiApp Energy ' +
        'mag adviseren, met hun vermogen, verbruik per cyclus en tijdvenster.',
      createRow: () => createDeviceRow(),
    });

    devices.body.append(
      rowList.element,
      el('div', { class: 'actions' }, [addButton]),
      listNotice.element,
    );
    element.appendChild(devices.element);

    // --- The dialog ---------------------------------------------------------

    const dialog = createDialog({ title: 'Apparaat', overlay });
    const requiredNotice = notice('mdi:asterisk');
    const orphanNotice = notice('mdi:eye-off-outline');
    const warningNotice = notice('mdi:alert-outline');
    const dialogNotice = notice('mdi:content-save-outline');

    const form = createForm(getHass(), schemaFor(NEW_DEVICE), (part) => {
      const previousType = draft.device_type;
      for (const [key, value] of Object.entries(part)) {
        if (differs(value, draft[key])) {
          touched.add(key);
        }
      }
      draft = { ...draft, ...part };
      if (draft.device_type !== previousType) {
        applyTypeDefaults();
      }
      state.setDraft(DRAFT, draft);
      refreshDialog();
    });

    dialog.body.append(
      requiredNotice.element,
      form.element,
      orphanNotice.element,
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
    }

    // --- Rows ---------------------------------------------------------------

    function createDeviceRow() {
      const name = el('p', { class: 'row-name' });
      const meta = el('p', { class: 'row-meta' });
      const status = el('div', { class: 'row-status' });
      const statusIcon = el('ha-icon', { attrs: { 'aria-hidden': 'true' } });
      const statusText = el('span');
      status.append(statusIcon, statusText);

      const editButton = button('Bewerken');
      const deleteButton = button('Verwijderen');
      deleteButton.classList.add('button-danger');

      const row = el('div', { class: 'row-item' }, [
        el('div', { class: 'row-main' }, [name, meta, status]),
        el('div', { class: 'row-buttons' }, [editButton, deleteButton]),
      ]);

      let current = null;
      onTap(editButton, () => current && openDialog(current, editButton));
      onTap(deleteButton, () => current && askDelete(current, deleteButton));

      return {
        element: row,
        update(device) {
          current = device;
          name.textContent = device.name || 'Naamloos apparaat';
          meta.textContent = describeDevice(device);

          const shown = statusOf(device);
          statusIcon.setAttribute('icon', shown.icon);
          statusText.textContent = shown.text;
          status.dataset.tone = shown.tone;
        },
      };
    }

    function describeDevice(device) {
      const parts = [TYPE_LABELS[device.device_type] || device.device_type];
      if (device.location) {
        parts.push(device.location);
      }
      parts.push(PRIORITY_LABELS[device.priority] || device.priority);
      parts.push(CONTROL_MODE_LABELS[device.control_mode] || device.control_mode);
      return parts.join(' · ');
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

      if (missing.length) {
        return {
          icon: 'mdi:progress-wrench',
          tone: 'warning',
          text:
            `Nog niet compleet: ${missing
              .map((name) => REQUIRED_LABELS[name])
              .join(', ')} ${missing.length > 1 ? 'ontbreken' : 'ontbreekt'}. ` +
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
      return { icon: 'mdi:check-circle-outline', tone: 'info', text: 'Compleet.' };
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
      refreshDialog();
      form.setErrors(editing ? fieldErrors(currentIssues(), editing.id) : null);
      dialog.show({ focusReturnsTo: opener });
    }

    function refreshDialog() {
      const schema = schemaFor(draft);
      // Only when the questions actually changed. Handing `ha-form` a fresh
      // schema on every keystroke makes it rebuild every field, which throws
      // away whatever control the installer had open — a multi-select loses the
      // choice they were in the middle of making.
      const key = JSON.stringify(schema);
      if (key !== schemaKey) {
        schemaKey = key;
        form.setSchema(schema);
      }
      form.setData(draft);

      // The marker on a field only helps someone already looking at it. In a
      // form of twenty questions the useful answer to "what is missing" is a
      // list at the top that names it, and shrinks as the fields are filled.
      const missing = missingRequired(draft);
      requiredNotice.set(
        missing.length
          ? 'Nog nodig voor een compleet apparaat: ' +
              `${missing.map((name) => REQUIRED_LABELS[name]).join(', ')}. ` +
              'Opslaan mag ook zonder — het apparaat telt dan alleen nog niet ' +
              'mee voor de datakwaliteit.'
          : 'Dit apparaat is compleet: alles wat de datakwaliteit vraagt is ingevuld.',
        { tone: missing.length ? 'warning' : 'success', icon: missing.length ? 'mdi:asterisk' : 'mdi:check-circle-outline' },
      );

      const orphans = orphanedFields(draft, schema);
      orphanNotice.set(
        orphans.length
          ? 'Deze ingevulde gegevens horen niet bij dit apparaattype en ' +
              `verdwijnen bij opslaan: ${orphans.map(labelOf).join(', ')}. ` +
              'Zet het type terug om ze te behouden.'
          : '',
        { tone: 'warning' },
      );

      const warnings = editing ? warningMessages(currentIssues(), editing.id) : [];
      warningNotice.set(warnings.join(' '), { tone: 'warning' });
      saveButton.disabled = !isDirty();
    }

    function isDirty() {
      const names = new Set([...Object.keys(draft), ...Object.keys(saved)]);
      return [...names].some((name) => differs(draft[name], saved[name]));
    }

    function setBusy(busy) {
      form.setDisabled(busy);
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
        const result = editing
          ? await api.updateDevice(revision, { ...payload, id: editing.id })
          : await api.createDevice(revision, payload);
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
          state.setConfig(error.config);
          dialog.close();
          listNotice.set(
            'De configuratie is intussen ergens anders gewijzigd. Je wijzigingen ' +
              'zijn niet opgeslagen; de lijst is opnieuw geladen.',
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
      rowList.sync(config.devices || []);
      form.setHass(getHass());
      if (dialog.isOpen() && editing) {
        form.setErrors(fieldErrors(currentIssues(), editing.id));
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
