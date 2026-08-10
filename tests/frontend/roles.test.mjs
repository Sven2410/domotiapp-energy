/**
 * Tests for the role split (SPEC.md §33).
 *
 * **What this layer can and cannot prove.** jsdom's `ha-form` is a stub: it
 * stores `.schema`, `.data` and `.disabled` as properties and renders no
 * control at all. So nothing here shows that a greyed-out field refuses a
 * click — that is a browser question, and it is answered in a browser, as a
 * second non-admin account (SPEC.md §33.7).
 *
 * What is provable here is the wiring, and the wiring is what drifts: that
 * every field a resident does not own carries `disabled: true`, that the
 * fields he does own do not, that the buttons which would write installer data
 * are gone, and that his save goes out over `devices/set_operation` carrying
 * only his own fields. Those are the mistakes someone makes when they add a
 * field six months from now.
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

/** The appliance a resident is allowed to have opinions about. */
const DISHWASHER = {
  id: 'dishwasher',
  name: 'Vaatwasser',
  device_type: 'dishwasher',
  enabled: true,
  priority: 'normal',
  control_mode: 'advice_only',
  nominal_power_w: 2000,
  energy_per_cycle_kwh: 1,
  duration_minutes: 180,
  days_of_week: [0, 1, 2, 3, 4, 5, 6],
  is_noisy: true,
  is_flexible: true,
  capabilities: [],
  control_forbidden: false,
};

/**
 * The fields SPEC.md §33.4 gives the resident on an appliance.
 *
 * `runs_any_time` joined them in §52 and had to: he may set a deadline through
 * `ready_before`, so he must be able to say he has none. Handing him only the
 * half that adds a requirement would make "geen eis" something only the
 * installer can express.
 */
const RESIDENT_DEVICE_FIELDS = [
  'control_mode',
  'ready_from',
  'ready_before',
  'runs_any_time',
  'ready_days',
  'days_of_week',
  'is_noisy',
  'priority',
];

function hassFor(isAdmin) {
  return fakeHass({
    isAdmin,
    config: sampleConfig({ devices: [DISHWASHER] }),
  });
}

async function openTab(label, id, isAdmin) {
  const hass = hassFor(isAdmin);
  const panel = await mountPanel(hass);
  clickTab(panel, label);
  await settle();
  const tab = tabPanels(panel).find((node) => node.id === id);
  return { panel, tab, hass };
}

/**
 * Every field of every ha-form under this element, with its effective state.
 *
 * A field is uneditable either through its own `disabled` in the schema or
 * through the form-level `disabled` the panel uses while a save is in flight —
 * and the control level card, which is disabled for everybody because 0.1.0
 * steers nothing. Both reach the same rendered control, so both count.
 */
function fields(root) {
  return [...root.querySelectorAll('ha-form')].flatMap((form) =>
    (form.schema || []).map((field) => ({
      ...field,
      disabled: Boolean(field.disabled || form.disabled),
    })),
  );
}

function findButton(root, label) {
  return [...root.querySelectorAll('button')].find((node) =>
    node.textContent.includes(label),
  );
}

/**
 * Whether a button can actually be reached, ancestors included.
 *
 * `isVisible` asks about one element, and that is not the question here: the
 * panel hides a save button by hiding the row it sits in, so the button itself
 * carries no class while being just as unreachable. Asking only about the node
 * would have passed on a button the user can see and press.
 */
function isShown(node, root) {
  for (let current = node; current && current !== root; current = current.parentElement) {
    if (!isVisible(current)) {
      return false;
    }
  }
  return true;
}

function noticeTexts(root) {
  return [...root.querySelectorAll('.notice')]
    .filter(isVisible)
    .map((node) => node.textContent);
}

describe('the Installatie tab is installer territory', () => {
  it('greys out every field for a resident', async () => {
    const { tab } = await openTab('Installatie', 'panel-installation', false);

    const enabled = fields(tab).filter((field) => !field.disabled);

    assert.deepEqual(
      enabled.map((field) => field.name),
      [],
      'a resident owns nothing on this tab (SPEC.md §33.4)',
    );
  });

  it('leaves every field editable for an installer', async () => {
    const { tab } = await openTab('Installatie', 'panel-installation', true);

    // The control level is the one field disabled for everybody: 0.1.0 steers
    // nothing, and the other levels are shown as not yet available.
    const disabled = fields(tab)
      .filter((field) => field.disabled)
      .map((field) => field.name);

    assert.ok(!disabled.includes('main_fuse_a'));
    assert.ok(!disabled.includes('phases'));
    assert.ok(!disabled.includes('contract_type'));
  });

  it('shows the fields rather than hiding them', async () => {
    // The whole point: an invisible wrong main fuse stays wrong, where a
    // visible one gets a phone call (SPEC.md §33.1).
    const { tab } = await openTab('Installatie', 'panel-installation', false);

    const names = fields(tab).map((field) => field.name);

    assert.ok(names.includes('main_fuse_a'));
    assert.ok(names.includes('max_grid_power_w'));
  });

  it('says who manages them, and drops the save button', async () => {
    const { tab } = await openTab('Installatie', 'panel-installation', false);

    assert.ok(
      noticeTexts(tab).some((text) => text.includes('beheerd door DomotiTech')),
    );
    assert.equal(isShown(findButton(tab, 'Opslaan'), tab), false);
    assert.equal(isShown(findButton(tab, 'Bron toevoegen'), tab), false);
  });

  it('keeps the save button for an installer', async () => {
    const { tab } = await openTab('Installatie', 'panel-installation', true);

    assert.equal(isShown(findButton(tab, 'Opslaan'), tab), true);
    assert.equal(isShown(findButton(tab, 'Bron toevoegen'), tab), true);
    assert.equal(
      noticeTexts(tab).some((text) => text.includes('beheerd door DomotiTech')),
      false,
    );
  });
});

describe('Mijn voorkeuren is resident territory', () => {
  it('leaves every field editable for a resident', async () => {
    const { tab } = await openTab('Mijn voorkeuren', 'panel-preferences', false);

    const disabled = fields(tab).filter((field) => field.disabled);

    assert.deepEqual(
      disabled.map((field) => field.name),
      [],
      'every preference is a statement about what he wants (SPEC.md §33.4)',
    );
  });

  it('keeps the save button, because he can actually save', async () => {
    const { tab } = await openTab('Mijn voorkeuren', 'panel-preferences', false);

    assert.equal(isShown(findButton(tab, 'Opslaan'), tab), true);
  });
});

describe('an appliance is split down the middle', () => {
  /** Open the dialog on the one stored appliance. */
  async function openDialog(isAdmin) {
    const { panel, tab, hass } = await openTab('Apparaten', 'panel-devices', isAdmin);
    findButton(tab, isAdmin ? 'Bewerken' : 'Instellen').click();
    await settle();
    const dialog = panel.shadowRoot.querySelector('.dialog');
    return { panel, tab, dialog, hass };
  }

  it('leaves exactly the resident fields editable and nothing else', async () => {
    const { dialog } = await openDialog(false);

    const editable = fields(dialog)
      .filter((field) => !field.disabled)
      .map((field) => field.name)
      .sort();

    assert.deepEqual(editable, [...RESIDENT_DEVICE_FIELDS].sort());
  });

  it('greys out the installer fields without hiding them', async () => {
    const { dialog } = await openDialog(false);

    const byName = new Map(fields(dialog).map((field) => [field.name, field]));

    for (const name of ['nominal_power_w', 'energy_per_cycle_kwh', 'device_type']) {
      assert.ok(byName.has(name), `${name} should still be on screen`);
      assert.equal(byName.get(name).disabled, true, `${name} should be disabled`);
    }
  });

  it('keeps the no-run window out of the resident hands', async () => {
    // It sits between the two ready-window fields he *does* own and looks just
    // like them, which is exactly why this is worth pinning (SPEC.md §51). The
    // ready window says when he wants it finished; this says when the machine
    // may not run at all, because of where it stands. If he could widen it, the
    // quiet hours would be the only thing left between the dryer and the child
    // asleep above it — and those are his to shorten.
    const { dialog } = await openDialog(false);
    const byName = new Map(fields(dialog).map((field) => [field.name, field]));

    for (const name of ['no_run_from', 'no_run_until']) {
      assert.ok(byName.has(name), `${name} should still be on screen`);
      assert.equal(byName.get(name).disabled, true, `${name} should be disabled`);
    }
    // And editable for the person who installed it.
    const installer = await openDialog(true);
    const theirs = new Map(fields(installer.dialog).map((f) => [f.name, f]));
    assert.notEqual(theirs.get('no_run_from').disabled, true);
    assert.notEqual(theirs.get('no_run_until').disabled, true);
  });

  it('drops adding and deleting for a resident', async () => {
    const { tab } = await openTab('Apparaten', 'panel-devices', false);

    assert.equal(isShown(findButton(tab, 'Apparaat toevoegen'), tab), false);
    assert.equal(isShown(findButton(tab, 'Verwijderen'), tab), false);
  });

  it('sends only his own fields, over set_operation', async () => {
    const { panel, dialog, hass } = await openDialog(false);

    const form = [...dialog.querySelectorAll('ha-form')].find((node) =>
      (node.schema || []).some((field) => field.name === 'ready_before'),
    );
    form.dispatchEvent(
      new CustomEvent('value-changed', {
        detail: { value: { ...form.data, ready_before: '07:00' } },
      }),
    );
    await settle();
    findButton(dialog, 'Opslaan').click();
    await settle();

    const write = hass.sent.find((message) =>
      message.type.endsWith('/devices/set_operation'),
    );
    assert.ok(write, 'a resident saves over devices/set_operation');
    assert.equal(write.device_id, 'dishwasher');
    // Only what he changed. Not the whole row, and not every field he owns:
    // devices/update has no field filter, which is exactly why he must not use
    // it (SPEC.md §33.10).
    assert.deepEqual(write.operation, { ready_before: '07:00' });
    assert.equal(
      hass.sent.some((message) => message.type.endsWith('/devices/update')),
      false,
      'the whole-row command must not be used by a resident',
    );
    assert.ok(panel);
  });

  it('sends the whole row for an installer', async () => {
    const { dialog, hass } = await openDialog(true);

    const form = [...dialog.querySelectorAll('ha-form')].find((node) =>
      (node.schema || []).some((field) => field.name === 'nominal_power_w'),
    );
    form.dispatchEvent(
      new CustomEvent('value-changed', {
        detail: { value: { ...form.data, nominal_power_w: 2200 } },
      }),
    );
    await settle();
    findButton(dialog, 'Opslaan').click();
    await settle();

    assert.ok(
      hass.sent.some((message) => message.type.endsWith('/devices/update')),
      'an installer edits the appliance itself',
    );
    assert.equal(
      hass.sent.some((message) => message.type.endsWith('/devices/set_operation')),
      false,
    );
  });
});
