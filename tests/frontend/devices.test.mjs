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

function form(panel) {
  return formDialog(panel).querySelector('ha-form');
}

function fieldNames(panel) {
  return form(panel).schema.map((field) => field.name);
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

function change(panel, values) {
  const node = form(panel);
  node.data = { ...node.data, ...values };
  node.dispatchEvent(
    new node.ownerDocument.defaultView.CustomEvent('value-changed', {
      detail: { value: node.data },
    }),
  );
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

  it('names a device without energy per cycle as unable to show a saving', async () => {
    const hass = fakeHass({
      config: sampleConfig({
        devices: [dishwasher({ energy_per_cycle_kwh: null })],
      }),
    });
    const { tab } = await openDevicesTab(hass);

    assert.match(rows(tab)[0].textContent, /geen besparing te berekenen/);
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
      earliest_start: '22:00',
      latest_finish: '06:00',
    });
    buttonIn(formDialog(panel), 'Opslaan').click();
    await settle();

    const sent = lastSent(hass, 'domotiapp_energy/devices/create');
    assert.equal(sent.expected_revision, 7);
    assert.equal(sent.device.device_type, 'dishwasher');
    assert.equal(sent.device.energy_per_cycle_kwh, 1.2);
    // A window that crosses midnight is the normal case, not an error.
    assert.equal(sent.device.earliest_start, '22:00');
    assert.equal(sent.device.latest_finish, '06:00');
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
    assert.equal(sent.device.temperature_entity, null);
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
        devices: [dishwasher({ latest_finish: '09:00', earliest_start: '09:00' })],
        issues: {
          d1: [
            {
              field: 'latest_finish',
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
      latest_finish: 'De starttijd en eindtijd mogen niet gelijk zijn.',
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
  it('refuses the first close and explains, then discards on the second', async () => {
    const { panel, tab } = await openDevicesTab();
    buttonIn(tab, 'Apparaat toevoegen').click();
    await settle();
    change(panel, { name: 'Halverwege' });

    buttonIn(formDialog(panel), 'Annuleren').click();
    await settle();
    assert.equal(isVisible(formDialog(panel)), true);

    buttonIn(formDialog(panel), 'Annuleren').click();
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
  });
});
