/**
 * The Apparaten tab (SPEC.md §8, §9, §11, §22 and §23).
 *
 * The second CRUD tab, on the machinery 8a built: the same dialog, the same
 * keyed list, the same save cycle and the same issues-per-field. What is new
 * here is what a device *is*, as opposed to a source:
 *
 * * it carries an **intention** — `control_mode` — next to what the hardware
 *   can do and what was agreed. Those three are deliberately not merged
 *   (SPEC.md §12), and the one combination that cannot stand is refused by the
 *   backend: an agreement not to control this installation outranks a mode
 *   somebody picks from a dropdown later;
 * * two flags follow from the device type unless the installer says otherwise
 *   — a dishwasher is noisy, a heat pump is not flexible (SPEC.md §8). The form
 *   follows the type only for a field nobody has touched yet, so a deliberate
 *   choice is never quietly overwritten by picking a different type;
 * * a time window that may cross midnight, which is the normal case for a
 *   dishwasher and not an error (SPEC.md §16).
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

const DAY_OPTIONS = [
  { value: 0, label: 'Maandag' },
  { value: 1, label: 'Dinsdag' },
  { value: 2, label: 'Woensdag' },
  { value: 3, label: 'Donderdag' },
  { value: 4, label: 'Vrijdag' },
  { value: 5, label: 'Zaterdag' },
  { value: 6, label: 'Zondag' },
];

/** The optional entity links, all six of them (SPEC.md §8). */
const ENTITY_LINKS = [
  { name: 'status_entity', label: 'Statusentiteit' },
  { name: 'power_entity', label: 'Vermogensentiteit' },
  { name: 'energy_entity', label: 'Energieverbruikentiteit' },
  { name: 'remaining_time_entity', label: 'Resterende tijd' },
  { name: 'temperature_entity', label: 'Temperatuur' },
  { name: 'battery_level_entity', label: 'Batterijniveau' },
];

const NEW_DEVICE = {
  name: '',
  device_type: 'dishwasher',
  enabled: true,
  priority: 'normal',
  control_mode: 'advice_only',
  days_of_week: [0, 1, 2, 3, 4, 5, 6],
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

/** Build the schema for one draft. */
function schemaFor(draft) {
  return [
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
    ...powerFields(),
    ...windowFields(),
    ...behaviourFields(draft),
    ...controlFields(draft),
    ...ENTITY_LINKS.map((link) => ({
      name: link.name,
      label: link.label,
      selector: { entity: {} },
    })),
    { name: 'notes', label: 'Notities', selector: { text: { multiline: true } } },
  ];
}

/** What the device uses, which is what a saving can be calculated from. */
function powerFields() {
  return [
    {
      name: 'nominal_power_w',
      label: 'Nominaal vermogen',
      helper: 'Het vermogen tijdens gebruik.',
      selector: { number: { min: 0, step: 10, unit_of_measurement: 'W' } },
    },
    {
      name: 'energy_per_cycle_kwh',
      label: 'Energie per cyclus',
      // Without this there is no saving to calculate, so the advice can only
      // say "now is a good moment" and never what it is worth (SPEC.md §16).
      helper: 'Nodig om een besparing te kunnen berekenen.',
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

/** The allowed time window, which may cross midnight (SPEC.md §16). */
function windowFields() {
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
      }. Alleen verplaatsbare apparaten krijgen een verplaatsingsadvies.`,
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

/** Read the editable fields out of a stored device. */
function draftFrom(device) {
  const draft = { ...NEW_DEVICE, ...device };
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
    payload[field.name] = value === undefined || value === '' ? null : value;
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
    let discardArmed = false;
    /**
     * The fields the installer changed by hand in this dialog.
     *
     * Only these survive a change of device type. Without it, picking a
     * different type would silently overwrite a deliberate "this dishwasher is
     * not noisy" with the default for the new type.
     */
    let touched = new Set();

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
    const warningNotice = notice('mdi:alert-outline');
    const dialogNotice = notice('mdi:content-save-outline');
    const unsavedNotice = notice('mdi:alert-outline');

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
      form.element,
      warningNotice.element,
      dialogNotice.element,
      unsavedNotice.element,
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
     * what Sven or his successor reads two years later — which is the whole
     * point of writing it down (SPEC.md §12).
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
      if (device.control_forbidden) {
        return {
          icon: 'mdi:lock-outline',
          tone: 'info',
          text: `Aansturing uitgesloten — ${
            device.control_forbidden_reason || 'geen reden genoteerd'
          }`,
        };
      }
      if (device.energy_per_cycle_kwh === null || device.nominal_power_w === null) {
        return {
          icon: 'mdi:information-outline',
          tone: 'info',
          text: 'Compleet, maar zonder vermogen of energie per cyclus is er geen besparing te berekenen.',
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
      discardArmed = false;
      // A stored device already has its flags; only a fresh dialog starts with
      // nothing touched.
      touched = new Set();

      dialog.setTitle(device ? 'Apparaat bewerken' : 'Apparaat toevoegen');
      dialogNotice.set('');
      unsavedNotice.set('');
      refreshDialog();
      form.setErrors(editing ? fieldErrors(currentIssues(), editing.id) : null);
      dialog.show({ focusReturnsTo: opener });
    }

    function refreshDialog() {
      form.setSchema(schemaFor(draft));
      form.setData(draft);

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
          // The one refusal the backend makes is this one, and it has to read
          // as an instruction rather than as a failure (SPEC.md §12).
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

    function mayClose() {
      if (!isDirty() || discardArmed) {
        discardArmed = false;
        state.clearDraft(DRAFT);
        return true;
      }
      discardArmed = true;
      unsavedNotice.set(
        'Je hebt wijzigingen die nog niet zijn opgeslagen. Sla ze op, of kies ' +
          'nogmaals sluiten om ze te verwerpen.',
        { tone: 'warning' },
      );
      return false;
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

    function canLeave() {
      if (confirmDialog.isOpen()) {
        confirmDialog.close();
      }
      if (!dialog.isOpen()) {
        return true;
      }
      if (mayClose()) {
        dialog.close();
        return true;
      }
      return false;
    }

    return { element, update, canLeave };
  },
};
