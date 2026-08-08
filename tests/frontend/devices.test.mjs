/**
 * Tests for the Apparaten tab (SPEC.md §8, §11, §12, §22 and §23).
 *
 * The CRUD cycle itself is the same machinery the Energiebronnen tab proved, so
 * these tests concentrate on what is different about a device: the two flags
 * that follow from the type, the three kinds of truth about control and the one
 * combination the backend refuses, and the agreement that has to be readable
 * from the list two years later.
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  clickTab,
  fakeHass,
  isVisible,
  mountPanel,
  sampleCoach,
  sampleConfig,
  settle,
  tabPanels,
} from './harness.mjs';

async function openDevicesTab(hass = fakeHass()) {
  const panel = await mountPanel(hass);
  clickTab(panel, 'Apparaten');
  await settle();
  const tab = tabPanels(panel).find((node) => node.id === 'panel-devices');
  return { panel, tab, hass };
}

function dialogs(panel) {
  return [...panel.shadowRoot.querySelectorAll('.dialog')];
}

/** The tab builds its form dialog first and its confirmation second. */
function formDialog(panel) {
  return dialogs(panel)[0];
}

function confirmDialog(panel) {
  return dialogs(panel)[1];
}

/**
 * Every form in the dialog, one per folding section.
 *
 * The dialog is split so it fits a phone; the tests treat the sections as one
 * form again, because what an installer is promised is about the questions and
 * not about which fold they sit in.
 */
function forms(panel) {
  return [...formDialog(panel).querySelectorAll('ha-form')];
}

/** The whole schema, in the order the sections present it. */
function schema(panel) {
  return forms(panel).flatMap((node) => node.schema || []);
}

/** The merged data of every section. */
function formData(panel) {
  return forms(panel).reduce((all, node) => ({ ...all, ...(node.data || {}) }), {});
}

/** The merged per-field errors of every section. */
function formErrors(panel) {
  const merged = forms(panel).reduce(
    (all, node) => ({ ...all, ...(node.error || {}) }),
    {},
  );
  return Object.keys(merged).length ? merged : undefined;
}

/** A stand-in for the single form the tests used before the split. */
function form(panel) {
  return { schema: schema(panel), data: formData(panel), error: formErrors(panel) };
}

function fieldNames(panel) {
  return schema(panel).map((field) => field.name);
}

/** The sections, by their visible heading. */
function sectionTitles(panel) {
  return [...formDialog(panel).querySelectorAll('.section')]
    .filter(isVisible)
    .map((node) => node.querySelector('.section-title').textContent);
}

function buttonIn(root, label) {
  const found = [...root.querySelectorAll('button')].find((node) =>
    node.textContent.includes(label),
  );
  if (!found) {
    throw new Error(`No button labelled ${label}`);
  }
  return found;
}

function rows(tab) {
  return [...tab.querySelectorAll('.row-item')];
}

function noticeTexts(root) {
  return [...root.querySelectorAll('.notice')]
    .filter(isVisible)
    .map((node) => node.querySelector('.notice-text').textContent);
}

/**
 * Change fields the way the installer does: in the section that owns them.
 *
 * Each `ha-form` emits its **own** data object, so a test that sent everything
 * through one of them would not exercise what the panel actually receives.
 */
function change(panel, values) {
  for (const node of forms(panel)) {
    const names = (node.schema || []).map((field) => field.name);
    const mine = Object.fromEntries(
      Object.entries(values).filter(([key]) => names.includes(key)),
    );
    if (!Object.keys(mine).length) {
      continue;
    }
    node.data = { ...node.data, ...mine };
    node.dispatchEvent(
      new node.ownerDocument.defaultView.CustomEvent('value-changed', {
        detail: { value: node.data },
      }),
    );
  }
}

function lastSent(hass, type) {
  return [...hass.sent].reverse().find((message) => message.type === type);
}

/** A stored dishwasher, in the shape the backend sends one. */
function dishwasher(overrides = {}) {
  return {
    id: 'd1',
    name: 'Vaatwasser',
    device_type: 'dishwasher',
    enabled: true,
    priority: 'normal',
    control_mode: 'advice_only',
    nominal_power_w: 2000,
    energy_per_cycle_kwh: 1.2,
    is_noisy: true,
    is_flexible: true,
    capabilities: [],
    control_forbidden: false,
    control_forbidden_reason: null,
    invalid_reason: null,
    days_of_week: [0, 1, 2, 3, 4, 5, 6],
    ...overrides,
  };
}

describe('the list of devices', () => {
  it('says what to do when there is nothing yet', async () => {
    const { tab } = await openDevicesTab();

    assert.equal(rows(tab).length, 0);
    assert.match(tab.querySelector('.empty-text').textContent, /Nog geen apparaten/);
  });

  it('shows type, location, priority and control level per device', async () => {
    const hass = fakeHass({
      config: sampleConfig({
        devices: [dishwasher({ location: 'Keuken', priority: 'high' })],
      }),
    });
    const { tab } = await openDevicesTab(hass);

    const text = rows(tab)[0].textContent;
    assert.match(text, /Vaatwasser/);
    assert.match(text, /Keuken/);
    assert.match(text, /Hoog/);
    assert.match(text, /Alleen adviseren/);
  });

  it('shows the agreement not to control, with the reason, in the list', async () => {
    // What Sven or his successor reads two years later, which is the whole
    // point of writing the reason down (SPEC.md §12).
    const hass = fakeHass({
      config: sampleConfig({
        devices: [
          dishwasher({
            control_forbidden: true,
            control_forbidden_reason: 'Medische apparatuur in de woning',
          }),
        ],
      }),
    });
    const { tab } = await openDevicesTab(hass);

    assert.match(rows(tab)[0].textContent, /Aansturing uitgesloten/);
    assert.match(rows(tab)[0].textContent, /Medische apparatuur in de woning/);
  });

  it('marks a half-filled device as not complete, naming what is missing', async () => {
    const hass = fakeHass({
      config: sampleConfig({
        // A window, so exactly one field is missing and the sentence about it
        // has to read as one.
        devices: [
          dishwasher({
            energy_per_cycle_kwh: null,
            ready_from: '22:00',
            ready_before: '06:00',
          }),
        ],
      }),
    });
    const { tab } = await openDevicesTab(hass);

    // Savable, but never silently counted as finished: the row says which
    // field is missing and that this device does not count towards the score.
    assert.match(rows(tab)[0].textContent, /Nog niet compleet/);
    assert.match(rows(tab)[0].textContent, /energie per cyclus/);
    assert.match(rows(tab)[0].textContent, /Telt niet mee voor de datakwaliteit/);
    assert.equal(rows(tab)[0].querySelector('.row-status').dataset.tone, 'warning');
    // One missing field reads as one, not as a list of one.
    assert.match(rows(tab)[0].textContent, /energie per cyclus ontbreekt/);
  });

  it('does not call a missing time window incomplete', async () => {
    // The form's own helper says both times may be left empty, so a device
    // without a window is finished, not half-filled. It used to be listed as
    // missing and marked with an asterisk at the same time — the form
    // contradicting itself in two adjacent lines (round B, finding 8).
    const hass = fakeHass({
      config: sampleConfig({
        devices: [
          dishwasher({
            ready_from: null,
            ready_before: null,
            nominal_power_w: 2000,
            energy_per_cycle_kwh: 1.2,
          }),
        ],
      }),
    });
    const { tab } = await openDevicesTab(hass);

    assert.doesNotMatch(rows(tab)[0].textContent, /vroegste start/);
    assert.doesNotMatch(rows(tab)[0].textContent, /laatste eindtijd/);
    assert.match(rows(tab)[0].textContent, /Compleet/);
  });

  it('keeps the agreement about control readable on an incomplete device', async () => {
    const hass = fakeHass({
      config: sampleConfig({
        devices: [
          dishwasher({
            energy_per_cycle_kwh: null,
            control_forbidden: true,
            control_forbidden_reason: 'Medische apparatuur in de woning',
          }),
        ],
      }),
    });
    const { tab } = await openDevicesTab(hass);

    // Both truths at once: what is unfinished and what was agreed.
    assert.match(rows(tab)[0].textContent, /Nog niet compleet/);
    assert.match(rows(tab)[0].textContent, /Medische apparatuur in de woning/);
  });
});

describe('the flags that follow from the type', () => {
  it('starts a new device with the defaults of its type', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    // A dishwasher is noisy and flexible by default (SPEC.md §8).
    assert.equal(form(panel).data.is_noisy, true);
    assert.equal(form(panel).data.is_flexible, true);
  });

  it('follows the type when the installer has not touched the flags', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { device_type: 'heat_pump' });

    // A heat pump is neither noisy nor flexible by default.
    assert.equal(form(panel).data.is_noisy, false);
    assert.equal(form(panel).data.is_flexible, false);
  });

  it('never overwrites a flag the installer set by hand', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    // "This dishwasher is in the garage, it does not bother anyone."
    change(panel, { is_noisy: false });
    change(panel, { device_type: 'washing_machine' });

    // washing_machine is noisy by default, but the deliberate choice stands.
    assert.equal(form(panel).data.is_noisy, false);
    // is_flexible was never touched, so it may follow the type.
    assert.equal(form(panel).data.is_flexible, true);
  });

  it('says in the helper what the default for this type is', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { device_type: 'generic_monitor' });

    const flexible = form(panel).schema.find((f) => f.name === 'is_flexible');
    assert.match(flexible.helper, /Standaard voor dit type: nee/);
  });
});

describe('control, and the one thing that is refused', () => {
  it('offers the controlling modes, so the agreement can be contradicted', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    const mode = form(panel).schema.find((f) => f.name === 'control_mode');
    const values = mode.selector.select.options.map((option) => option.value);
    // Without these two selectable, the backend's one hard block could never
    // fire and the agreement would never actually be defended.
    assert.ok(values.includes('approval_required'));
    assert.ok(values.includes('automatic'));
  });

  it('asks for a reason only once control is ruled out', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    assert.ok(!fieldNames(panel).includes('control_forbidden_reason'));

    change(panel, { control_forbidden: true });

    assert.ok(fieldNames(panel).includes('control_forbidden_reason'));
  });

  it('shows the backend refusal as an instruction and keeps the edit', async () => {
    const hass = fakeHass();
    const original = hass.callWS;
    hass.callWS = async (message) => {
      if (message.type === 'domotiapp_energy/devices/create') {
        throw {
          code: 'invalid_format',
          message:
            "Voor deze installatie is aansturing uitgesloten. Kies 'alleen " +
            "monitoren' of 'alleen adviseren'.",
        };
      }
      return original(message);
    };

    const { panel, tab } = await openDevicesTab(hass);
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();
    change(panel, {
      name: 'Laadpaal',
      control_mode: 'automatic',
      control_forbidden: true,
      control_forbidden_reason: 'Afgesproken met de klant',
    });
    buttonIn(formDialog(panel), 'Opslaan').click();
    await settle();

    assert.equal(isVisible(formDialog(panel)), true);
    assert.ok(
      noticeTexts(formDialog(panel)).some((t) => t.includes('aansturing uitgesloten')),
    );
    // The edit is still there to correct rather than to type again.
    assert.equal(form(panel).data.name, 'Laadpaal');
  });
});

describe('saving a device', () => {
  it('sends the whole profile with the revision it was filled in against', async () => {
    const { panel, tab, hass } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, {
      name: 'Vaatwasser',
      nominal_power_w: 2000,
      energy_per_cycle_kwh: 1.2,
      ready_from: '22:00',
      ready_before: '06:00',
    });
    buttonIn(formDialog(panel), 'Opslaan').click();
    await settle();

    const sent = lastSent(hass, 'domotiapp_energy/devices/create');
    assert.equal(sent.expected_revision, 7);
    assert.equal(sent.device.device_type, 'dishwasher');
    assert.equal(sent.device.energy_per_cycle_kwh, 1.2);
    // A window that crosses midnight is the normal case, not an error.
    assert.equal(sent.device.ready_from, '22:00');
    assert.equal(sent.device.ready_before, '06:00');
    // The flags travel explicitly, so what the form showed is what is stored.
    assert.equal(sent.device.is_noisy, true);
  });

  it('sends an untouched optional link as null, never as an empty string', async () => {
    const { panel, tab, hass } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { name: 'Vaatwasser' });
    buttonIn(formDialog(panel), 'Opslaan').click();
    await settle();

    const sent = lastSent(hass, 'domotiapp_energy/devices/create');
    assert.equal(sent.device.status_entity, null);
    // A temperature on a dishwasher is not asked, and therefore not sent: the
    // backend clears it rather than storing an answer to a missing question.
    assert.ok(!('temperature_entity' in sent.device));
  });

  it('confirms only after the backend answers', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();
    change(panel, { name: 'Vaatwasser' });
    buttonIn(formDialog(panel), 'Opslaan').click();
    await settle();

    assert.equal(isVisible(formDialog(panel)), false);
    assert.ok(noticeTexts(tab).some((t) => t.includes('is toegevoegd')));
    assert.equal(rows(tab).length, 1);
  });

  it('places a backend validation issue on the field it is about', async () => {
    const hass = fakeHass({
      config: sampleConfig({
        devices: [dishwasher({ ready_before: '09:00', ready_from: '09:00' })],
        issues: {
          d1: [
            {
              field: 'ready_before',
              code: 'invalid_time_window',
              message: 'De starttijd en eindtijd mogen niet gelijk zijn.',
              severity: 'error',
            },
          ],
        },
      }),
    });
    const { panel, tab } = await openDevicesTab(hass);

    assert.match(rows(tab)[0].textContent, /Nog niet compleet/);

    buttonIn(rows(tab)[0], 'Bewerken').click();
    await settle();

    assert.deepEqual(form(panel).error, {
      ready_before: 'De starttijd en eindtijd mogen niet gelijk zijn.',
    });
  });
});

describe('deleting a device', () => {
  it('asks first and does nothing when the answer is no', async () => {
    const hass = fakeHass({ config: sampleConfig({ devices: [dishwasher()] }) });
    const { panel, tab } = await openDevicesTab(hass);

    buttonIn(rows(tab)[0], 'Verwijderen').click();
    await settle();
    assert.equal(isVisible(confirmDialog(panel)), true);

    buttonIn(confirmDialog(panel), 'Annuleren').click();
    await settle();

    assert.equal(lastSent(hass, 'domotiapp_energy/devices/delete'), undefined);
    assert.equal(rows(tab).length, 1);
  });

  it('deletes once it is confirmed', async () => {
    const hass = fakeHass({ config: sampleConfig({ devices: [dishwasher()] }) });
    const { panel, tab } = await openDevicesTab(hass);

    buttonIn(rows(tab)[0], 'Verwijderen').click();
    await settle();
    buttonIn(confirmDialog(panel), 'Verwijderen').click();
    await settle();

    assert.equal(lastSent(hass, 'domotiapp_energy/devices/delete').device_id, 'd1');
    assert.equal(rows(tab).length, 0);
  });
});

describe('unsaved changes in the device dialog', () => {
  it('asks a visible question instead of arming a second click', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();
    change(panel, { name: 'Halverwege' });

    buttonIn(formDialog(panel), 'Annuleren').click();
    await settle();

    // A notice under a 23-field form can sit below the fold; a dialog cannot.
    assert.equal(isVisible(formDialog(panel)), true);
    assert.equal(isVisible(confirmDialog(panel)), true);
    assert.match(confirmDialog(panel).textContent, /verwerpen/i);
  });

  it('goes back to the form with the edit intact', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();
    change(panel, { name: 'Halverwege' });

    buttonIn(formDialog(panel), 'Annuleren').click();
    await settle();
    buttonIn(confirmDialog(panel), 'Terug naar het formulier').click();
    await settle();

    assert.equal(isVisible(confirmDialog(panel)), false);
    assert.equal(isVisible(formDialog(panel)), true);
    assert.equal(form(panel).data.name, 'Halverwege');
  });

  it('closes only once the discard is confirmed', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();
    change(panel, { name: 'Halverwege' });

    buttonIn(formDialog(panel), 'Annuleren').click();
    await settle();
    buttonIn(confirmDialog(panel), 'Verwerpen').click();
    await settle();

    assert.equal(isVisible(formDialog(panel)), false);
  });

  it('keeps the installer on the tab while the dialog holds an edit', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();
    change(panel, { name: 'Halverwege' });

    clickTab(panel, 'Overzicht');
    await settle();

    assert.equal(tabPanels(panel).filter(isVisible)[0].id, 'panel-devices');
    assert.equal(isVisible(confirmDialog(panel)), true);
  });

  it('continues to the other tab once the discard is confirmed', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();
    change(panel, { name: 'Halverwege' });

    clickTab(panel, 'Overzicht');
    await settle();
    buttonIn(confirmDialog(panel), 'Verwerpen').click();
    await settle();

    assert.equal(tabPanels(panel).filter(isVisible)[0].id, 'panel-overview');
  });
});


describe('the schema is only replaced when the questions change', () => {
  /** Count how often the form is handed a new schema. */
  function watchSchema(panel) {
    const counter = { sets: 0 };
    for (const node of forms(panel)) {
      let current = node.schema;
      Object.defineProperty(node, 'schema', {
        configurable: true,
        get: () => current,
        set: (value) => {
          counter.sets += 1;
          current = value;
        },
      });
    }
    return counter;
  }

  it('leaves the form alone when only a value changed', async () => {
    // This is the days bug. `ha-form` rebuilds every field when it is handed a
    // schema, and rebuilding while a multi-select is open throws away the
    // choice being made: emptying the days and then picking one did nothing at
    // all, because the pick landed on a control that no longer existed.
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();
    const watcher = watchSchema(panel);

    change(panel, { name: 'Vaatwasser' });
    change(panel, { days_of_week: [] });
    change(panel, { days_of_week: ['2'] });

    assert.equal(watcher.sets, 0);
  });

  it('does replace it when the type changes what is asked', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();
    const watcher = watchSchema(panel);

    change(panel, { device_type: 'heat_pump' });

    assert.ok(watcher.sets > 0);
  });

  it('keeps a day chosen after the list was emptied', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { days_of_week: [] });
    change(panel, { days_of_week: ['2'] });

    assert.deepEqual(form(panel).data.days_of_week, ['2']);
  });

  it('speaks strings to the form and integers to the backend', async () => {
    // The days field went dead in the browser because its option values were
    // numbers. With seven options `ha-selector-select` renders a combobox, and
    // that combobox works in strings: a numeric option never matches what it
    // hands back, so the pick was dropped without a word. The draft therefore
    // holds strings and the payload converts to the integers the backend
    // stores (Monday = 0, SPEC.md §8).
    const { panel, tab, hass } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { name: 'Vaatwasser', days_of_week: ['0', '6'] });
    buttonIn(formDialog(panel), 'Opslaan').click();
    await settle();

    assert.deepEqual(
      lastSent(hass, 'domotiapp_energy/devices/create').device.days_of_week,
      [0, 6],
    );
  });

  it('shows a stored device its days as selected', async () => {
    // The mirror image: integers out of storage have to reach the form as the
    // strings its options use, or every chip renders unselected.
    const hass = fakeHass({
      config: sampleConfig({ devices: [dishwasher({ days_of_week: [0, 6] })] }),
    });
    const { panel, tab } = await openDevicesTab(hass);
    buttonIn(rows(tab)[0], 'Bewerken').click();
    await settle();

    assert.deepEqual(form(panel).data.days_of_week, ['0', '6']);
  });

  it('never offers a select option whose value is not a string', async () => {
    // The invariant that would have caught the days bug before a browser did.
    // jsdom cannot run `ha-form`, so no test here can prove a control accepts a
    // click; what it can prove is that we never hand one a value of the kind
    // that silently does not match.
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    for (const type of ['dishwasher', 'home_battery', 'ev_charger', 'heat_pump']) {
      change(panel, { device_type: type });
      for (const field of form(panel).schema) {
        for (const option of field.selector?.select?.options ?? []) {
          assert.equal(
            typeof option.value,
            'string',
            `${field.name} offers ${JSON.stringify(option.value)}`,
          );
        }
      }
    }
  });
});

describe('only the questions this type can answer', () => {
  it('does not offer a battery level on a dishwasher', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    // A battery level here is an invitation to link the wrong entity.
    assert.ok(!fieldNames(panel).includes('battery_level_entity'));
    assert.ok(!fieldNames(panel).includes('temperature_entity'));
    // A remaining time does mean something for a dishwasher.
    assert.ok(fieldNames(panel).includes('remaining_time_entity'));
  });

  it('offers a battery level on the two types that have one', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { device_type: 'home_battery' });
    assert.ok(fieldNames(panel).includes('battery_level_entity'));
    assert.ok(!fieldNames(panel).includes('remaining_time_entity'));

    change(panel, { device_type: 'ev_charger' });
    assert.ok(fieldNames(panel).includes('battery_level_entity'));
    assert.ok(fieldNames(panel).includes('remaining_time_entity'));
  });

  it('asks for a time window only where one will be used', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    assert.ok(fieldNames(panel).includes('ready_from'));

    // Tied to is_flexible, not to the type: that is exactly what the data
    // quality checklist asks about.
    change(panel, { is_flexible: false });

    assert.ok(!fieldNames(panel).includes('ready_from'));
    assert.ok(!fieldNames(panel).includes('days_of_week'));
  });

  it('keeps a hidden value in the draft, so switching back restores it', async () => {
    // Hiding is not deleting. This is the same class of mistake as the shared
    // draft of phase 7b: work disappearing without anybody being told.
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { device_type: 'home_battery' });
    change(panel, { battery_level_entity: 'sensor.accu' });
    change(panel, { device_type: 'dishwasher' });

    assert.ok(!fieldNames(panel).includes('battery_level_entity'));

    change(panel, { device_type: 'home_battery' });

    assert.equal(form(panel).data.battery_level_entity, 'sensor.accu');
  });

  it('says out loud what saving would drop', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { device_type: 'home_battery' });
    change(panel, { battery_level_entity: 'sensor.accu' });
    change(panel, { device_type: 'dishwasher' });

    const warning = noticeTexts(formDialog(panel)).find((t) =>
      t.includes('verdwijnen bij opslaan'),
    );
    assert.ok(warning, 'the dialog has to name what would be lost');
    assert.match(warning, /Batterijniveau/);
  });

  it('drops it on save, which is what the warning announced', async () => {
    const { panel, tab, hass } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { device_type: 'home_battery' });
    change(panel, { battery_level_entity: 'sensor.accu', name: 'Accu' });
    change(panel, { device_type: 'dishwasher' });
    buttonIn(formDialog(panel), 'Opslaan').click();
    await settle();

    const sent = lastSent(hass, 'domotiapp_energy/devices/create');
    assert.ok(!('battery_level_entity' in sent.device));
  });
});

describe('what the data quality checklist needs', () => {
  it("marks the fields the checklist asks for, the way Home Assistant does", async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    const marked = form(panel)
      .schema.filter((field) => field.required)
      .map((field) => field.name);

    // `required` is what ha-form hands to the selector, which renders the
    // marker from --ha-input-required-marker. Our own text suffix imitated
    // that styling instead of inheriting it.
    //
    // The two window fields are deliberately absent: their helper says they may
    // be left empty, and an asterisk over that sentence was the defect
    // (round B, finding 8).
    assert.deepEqual(marked.sort(), ['energy_per_cycle_kwh', 'nominal_power_w']);
    // And it stays a marking, not a gate: a half-filled device is savable.
    assert.equal(buttonIn(formDialog(panel), 'Opslaan').disabled, true);
    change(panel, { name: 'Vaatwasser' });
    assert.equal(buttonIn(formDialog(panel), 'Opslaan').disabled, false);
  });

  it('marks nothing on an appliance that will never be advised about', async () => {
    // Both fields exist to produce advice: the energy per cycle becomes the
    // saving, the power decides whether a surplus can carry it. Marking them
    // required on an appliance that is only measured is a requirement that
    // does not apply, shown as a shortcoming (0.6.1).
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { is_flexible: false });

    const marked = form(panel)
      .schema.filter((field) => field.required)
      .map((field) => field.name);

    assert.deepEqual(marked, []);
    assert.ok(!fieldNames(panel).includes('ready_from'));
  });

  it('marks both fields again once the appliance can be advised about', async () => {
    // The other half: without this the suite would stay green if the marking
    // disappeared altogether.
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { is_flexible: true });

    const marked = form(panel)
      .schema.filter((field) => field.required)
      .map((field) => field.name);

    assert.deepEqual(marked.sort(), ['energy_per_cycle_kwh', 'nominal_power_w']);
  });

  it('drops the marking when the resident switches to alleen meekijken', async () => {
    // His own off switch, on the other axis from the type (SPEC.md §33).
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { is_flexible: true, control_mode: 'monitor_only' });

    const marked = form(panel)
      .schema.filter((field) => field.required)
      .map((field) => field.name);

    assert.deepEqual(marked, []);
  });

  it('lists what is still missing, and shortens the list as it is filled', async () => {
    // One character in a form this long is easy to miss — which is exactly how
    // it was reported. The summary is what can be read at a glance.
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    const first = noticeTexts(formDialog(panel)).find((t) => t.includes('Nog nodig'));
    assert.match(first, /nominaal vermogen/);
    assert.match(first, /energie per cyclus/);
    assert.match(first, /Opslaan mag ook zonder/);

    change(panel, { nominal_power_w: 2000 });

    const second = noticeTexts(formDialog(panel)).find((t) => t.includes('Nog nodig'));
    assert.ok(!second.includes('nominaal vermogen'));
    assert.match(second, /energie per cyclus/);
  });

  it('says so when nothing is missing any more', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, {
      nominal_power_w: 2000,
      energy_per_cycle_kwh: 1.2,
      ready_from: '22:00',
      ready_before: '06:00',
    });

    assert.ok(
      noticeTexts(formDialog(panel)).some((t) => t.includes('Dit apparaat is compleet')),
    );
  });
});

describe('helper texts that know what type this is', () => {
  it('explains a temperature sensor differently per type', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { device_type: 'heat_pump' });
    const heatPump = form(panel).schema.find((f) => f.name === 'temperature_entity');
    assert.match(heatPump.helper, /aanvoertemperatuur/);

    change(panel, { device_type: 'electric_boiler' });
    const boiler = form(panel).schema.find((f) => f.name === 'temperature_entity');
    assert.match(boiler.helper, /watertemperatuur/);
  });

  it('explains a battery level differently for a car and for a house', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { device_type: 'home_battery' });
    assert.match(
      form(panel).schema.find((f) => f.name === 'battery_level_entity').helper,
      /thuisbatterij/,
    );

    change(panel, { device_type: 'ev_charger' });
    assert.match(
      form(panel).schema.find((f) => f.name === 'battery_level_entity').helper,
      /auto/,
    );
  });

  it('says what a nominal power means for this type', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { device_type: 'heat_pump' });

    // The distinction that costs a factor of three or four when missed.
    assert.match(
      form(panel).schema.find((f) => f.name === 'nominal_power_w').helper,
      /elektrische opgenomen vermogen, niet het thermische/,
    );
  });
});

describe('the dialog folds into sections a phone can hold', () => {
  it('opens the three sections an installer needs on every visit', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    assert.deepEqual(sectionTitles(panel), [
      'Apparaat',
      'Verbruik',
      'Wanneer het mag draaien',
      'Aansturing',
      'Koppelingen en notities',
    ]);

    const open = [...formDialog(panel).querySelectorAll('.section-toggle')]
      .filter((node) => node.getAttribute('aria-expanded') === 'true')
      .map((node) => node.querySelector('.section-title').textContent);
    // The agreement about control and the optional links stay folded: most
    // visits do not touch them, and the scroll is what made this unusable.
    assert.deepEqual(open, ['Apparaat', 'Verbruik', 'Wanneer het mag draaien']);
  });

  it('folds a section open and shut from the keyboard', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    const toggle = [...formDialog(panel).querySelectorAll('.section-toggle')].find(
      (node) => node.querySelector('.section-title').textContent === 'Aansturing',
    );
    const body = formDialog(panel).querySelector(
      `#${toggle.getAttribute('aria-controls')}`,
    );

    assert.equal(isVisible(body), false);

    // A semantic button: a click is what a keyboard press produces too, and
    // the state travels in aria-expanded rather than in the chevron alone.
    toggle.click();

    assert.equal(toggle.getAttribute('aria-expanded'), 'true');
    assert.equal(isVisible(body), true);
  });

  it('shows every field the schema asks for, in some section', async () => {
    // The sections group; they never define. A field nobody assigned would
    // simply disappear from the form, and only this test would notice.
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    for (const type of ['dishwasher', 'home_battery', 'ev_charger', 'heat_pump']) {
      change(panel, { device_type: type });
      change(panel, { control_forbidden: true });

      const shown = new Set(fieldNames(panel));
      for (const name of [
        'name',
        'device_type',
        'enabled',
        'location',
        'priority',
        'nominal_power_w',
        'energy_per_cycle_kwh',
        'duration_minutes',
        'is_noisy',
        'is_flexible',
        'control_mode',
        'capabilities',
        'control_forbidden',
        'control_forbidden_reason',
        'notes',
      ]) {
        assert.ok(shown.has(name), `${name} is in no section for ${type}`);
      }
    }
  });

  it('hides a section that has nothing left to ask', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    // A monitor-only device has no links of its own beyond the three every
    // type has, so the section stays; the window section is what empties.
    change(panel, { is_flexible: false, device_type: 'generic_monitor' });

    assert.ok(fieldNames(panel).includes('is_flexible'));
    assert.ok(!fieldNames(panel).includes('ready_from'));
  });
});

describe('what a charger is actually asked', () => {
  /** The schema of the open device form, keyed by field name. */
  function fields(panel) {
    return Object.fromEntries(form(panel).schema.map((f) => [f.name, f]));
  }

  it('names the charger fields after what a charger has', async () => {
    // "Nominaal vermogen" on a charger reads as a rating plate figure, and
    // "energie per cyclus" asks for a number nobody can state: it depends on
    // how empty the car is (round B, finding 7).
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { device_type: 'ev_charger' });
    const charger = fields(panel);

    assert.equal(charger.nominal_power_w.label, 'Maximaal laadvermogen');
    assert.equal(charger.energy_per_cycle_kwh.label, 'Energie per laadsessie');
    assert.equal(charger.duration_minutes.label, 'Duur van een laadsessie');
  });

  it('says in so many words that the charge figure is an estimate', async () => {
    // The honest version of a question that cannot be answered exactly, and it
    // names the consequence rather than leaving the installer to wonder.
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { device_type: 'ev_charger' });
    const helper = fields(panel).energy_per_cycle_kwh.helper;

    assert.match(helper, /schatting/);
    assert.match(helper, /hoe leeg de auto is/);
  });

  it('leaves the labels alone for everything that does have a cycle', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();

    change(panel, { device_type: 'dishwasher' });
    const dishwasher = fields(panel);

    assert.equal(dishwasher.nominal_power_w.label, 'Nominaal vermogen');
    assert.equal(dishwasher.energy_per_cycle_kwh.label, 'Energie per cyclus');
    assert.equal(dishwasher.duration_minutes.label, 'Duur van een cyclus');
  });
})

describe('the live power per appliance', () => {
  it('shows a reading for a linked appliance', async () => {
    const { tab } = await openDevicesTab(
      fakeHass({
        config: sampleConfig({ devices: [dishwasher()] }),
        coach: sampleCoach({ metrics: { device_power_w: { d1: 1150 } } }),
      }),
    );

    assert.match(tab.textContent, /Nu: 1\.150 W/);
  });

  it('gives an unlinked appliance no line at all', async () => {
    // Not "onbekend" and not "0 W": an appliance nobody linked is not a gap,
    // and a column of blanks reports a fault where there is none.
    const { tab } = await openDevicesTab(
      fakeHass({
        config: sampleConfig({ devices: [dishwasher()] }),
        coach: sampleCoach({ metrics: { device_power_w: {} } }),
      }),
    );

    assert.doesNotMatch(tab.textContent, /Nu:/);
  });
});
;
