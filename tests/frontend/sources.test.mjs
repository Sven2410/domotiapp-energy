/**
 * Tests for the Energiebronnen tab (SPEC.md §8, §9, §11, §22 and §23).
 *
 * The promises worth pinning are the ones an installer leans on in a meter
 * cupboard: a question is only asked when it has a meaning, what is not asked
 * is not stored, nothing says "saved" before the backend agrees, deleting is
 * confirmed first, and an edit is never thrown away without being told.
 *
 * As everywhere in this panel, visibility is asserted through the `is-hidden`
 * class rather than through jsdom's computed styles.
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
  visibleText,
} from './harness.mjs';

/**
 * Open the Energiebronnen section and hand back everything a test needs.
 *
 * It is a section of the Installatie tab since round 1 (SPEC.md §33.6); the
 * module itself is untouched.
 */
async function openSourcesTab(hass = fakeHass()) {
  const panel = await mountPanel(hass);
  clickTab(panel, 'Installatie');
  await settle();
  const tab = tabPanels(panel)
    .find((node) => node.id === 'panel-installation')
    .querySelector('#section-sources');
  return { panel, tab, hass };
}

/** The two dialogs this tab owns, in the order it creates them. */
function dialogs(panel) {
  return [...panel.shadowRoot.querySelectorAll('.dialog')];
}

function formDialog(panel) {
  return dialogs(panel)[0];
}

function confirmDialog(panel) {
  return dialogs(panel)[1];
}

/** Every form in the dialog, one per folding section. */
function forms(panel) {
  return [...formDialog(panel).querySelectorAll('ha-form')];
}

function schema(panel) {
  return forms(panel).flatMap((node) => node.schema || []);
}

function formData(panel) {
  return forms(panel).reduce((all, node) => ({ ...all, ...(node.data || {}) }), {});
}

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
 * Each `ha-form` emits its own data object, so sending everything through one
 * of them would not exercise what the panel actually receives.
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

async function openDialogFor(panel, tab, label = 'Bron toevoegen') {
  buttonIn(label === 'Bron toevoegen' ? tab : tab, label).click();
  await settle();
}

/** The last command of this type that reached the backend. */
function lastSent(hass, type) {
  return [...hass.sent].reverse().find((message) => message.type === type);
}

describe('the list of sources', () => {
  it('shows each configured source with a status in words', async () => {
    const { tab } = await openSourcesTab();

    assert.equal(rows(tab).length, 1);
    assert.match(visibleText(rows(tab)[0]), /Netmeter/);
    // Never a bare colour or icon: the meaning is in the text (SPEC.md §23).
    assert.ok(rows(tab)[0].querySelector('.row-status span').textContent.length > 0);
  });

  it('says what to do when there is nothing yet', async () => {
    const hass = fakeHass({ config: sampleConfig({ sources: [] }) });
    const { tab } = await openSourcesTab(hass);

    assert.equal(rows(tab).length, 0);
    assert.match(
      tab.querySelector('.empty-text').textContent,
      /Nog geen energiebronnen/,
    );
  });

  it('names an unknown type as unusable instead of hiding it', async () => {
    // A quarantined row stays visible and says why (SPEC.md §12). The backend
    // computes invalid_reason from the type on every read and sends it with
    // the row; the panel repeats that judgement rather than making its own.
    const hass = fakeHass({
      config: sampleConfig({
        sources: [
          {
            id: 'x',
            name: 'Oude bron',
            type: 'grid_metre',
            enabled: false,
            invalid_reason: 'unknown_type',
          },
        ],
      }),
    });
    const { tab } = await openSourcesTab(hass);

    assert.match(visibleText(rows(tab)[0]), /Onbekend brontype/);
    assert.equal(rows(tab)[0].querySelector('.row-status').dataset.tone, 'error');
  });

  it('shows the agreement not to control a source, with its reason', async () => {
    const hass = fakeHass({
      config: sampleConfig({
        sources: [
          {
            id: 'pv',
            name: 'Omvormer',
            type: 'solar',
            enabled: true,
            entity_id: 'sensor.pv',
            control_forbidden: true,
            control_forbidden_reason: 'Omvormer van de installateur',
          },
        ],
      }),
    });
    const { tab } = await openSourcesTab(hass);

    assert.match(visibleText(rows(tab)[0]), /Aansturing uitgesloten/);
    assert.match(visibleText(rows(tab)[0]), /Omvormer van de installateur/);
  });

  it('updates a row in place rather than rebuilding the list', async () => {
    const { panel, tab } = await openSourcesTab();
    const before = rows(tab)[0];
    assert.ok(before, 'there has to be a row for this to mean anything');

    clickTab(panel, 'Overzicht');
    await settle();
    clickTab(panel, 'Installatie');
    await settle();

    // Rebuilding would throw away focus and scroll position on the very screen
    // where the installer is working through a row at a time (SPEC.md §9).
    assert.equal(rows(tab)[0], before);
  });
});

describe('the two forecast types nothing reads', () => {
  it('does not offer them when adding a source', async () => {
    // A choice in a list, with a helper inviting you to link an entity, that
    // then counts for nothing anywhere. Offering it was the fault (SPEC.md
    // §38.1).
    const { panel, tab } = await openSourcesTab();
    buttonIn(tab, 'Bron toevoegen').click();
    await settle();

    const type = schema(panel).find((field) => field.name === 'type');
    const offered = type.selector.select.options.map((option) => option.value);

    assert.ok(!offered.includes('price_forecast'));
    assert.ok(!offered.includes('solar_forecast'));
    // The types that do something are untouched.
    assert.ok(offered.includes('grid_meter'));
    assert.ok(offered.includes('solar'));
  });

  it('leaves an existing row usable, and says what it does', async () => {
    // Removing the type from the model would quarantine the row instead —
    // "Onbekend brontype", not used, and nothing the installer can undo. This
    // is the softer answer the situation deserves.
    const hass = fakeHass({
      config: sampleConfig({
        sources: [
          {
            id: 'f1',
            name: 'Verwachting',
            type: 'solar_forecast',
            enabled: true,
            entity_id: 'sensor.forecast',
            invalid_reason: null,
          },
        ],
      }),
    });
    const { tab } = await openSourcesTab(hass);

    const row = rows(tab)[0];

    assert.match(visibleText(row), /Zonverwachting/);
    assert.doesNotMatch(row.textContent, /Onbekend brontype/);
    assert.match(visibleText(row), /nog niet in gebruik/);
    // Not a fault: the row is not broken, it is simply not read yet.
    assert.equal(row.querySelector('.row-status').dataset.tone, 'info');
  });

  it('keeps the current type selectable so a save cannot rewrite it', async () => {
    // With its own value missing from the options the select renders empty,
    // and the first save silently turns the row into whatever was picked.
    const hass = fakeHass({
      config: sampleConfig({
        sources: [
          {
            id: 'f1',
            name: 'Verwachting',
            type: 'price_forecast',
            enabled: true,
            entity_id: 'sensor.forecast',
            invalid_reason: null,
          },
        ],
      }),
    });
    const { panel, tab } = await openSourcesTab(hass);
    buttonIn(rows(tab)[0], 'Bewerken').click();
    await settle();

    const type = schema(panel).find((field) => field.name === 'type');

    assert.equal(form(panel).data.type, 'price_forecast');
    assert.ok(
      type.selector.select.options.some((option) => option.value === 'price_forecast'),
    );
    assert.match(type.helper, /nog niet in gebruik/);
  });
});

describe('the dialog', () => {
  it('is closed until something opens it, and is labelled when it opens', async () => {
    const { panel, tab } = await openSourcesTab();

    assert.equal(isVisible(formDialog(panel)), false);

    await openDialogFor(panel, tab);

    assert.equal(isVisible(formDialog(panel)), true);
    const surface = formDialog(panel).querySelector('.dialog-surface');
    assert.equal(surface.getAttribute('role'), 'dialog');
    assert.equal(surface.getAttribute('aria-modal'), 'true');
    // The heading labels the dialog rather than an invented aria-label.
    const labelledBy = surface.getAttribute('aria-labelledby');
    assert.equal(
      formDialog(panel).querySelector(`#${labelledBy}`).textContent,
      'Energiebron toevoegen',
    );
  });

  it('makes the page behind it unreachable while it is open', async () => {
    const { panel, tab } = await openSourcesTab();
    const layout = panel.shadowRoot.querySelector('.layout');

    await openDialogFor(panel, tab);
    assert.equal(layout.inert, true);

    buttonIn(formDialog(panel), 'Annuleren').click();
    await settle();
    assert.equal(layout.inert, false);
  });
});

describe('fields that only apply sometimes', () => {
  it('asks a grid meter how it measures, and nothing that follows from it', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);

    // A new source starts as a grid meter: the mode is asked, the fields that
    // depend on it are not, because there is no answer to them yet.
    assert.ok(fieldNames(panel).includes('meter_mode'));
    assert.ok(!fieldNames(panel).includes('positive_means'));
    assert.ok(!fieldNames(panel).includes('import_entity_id'));

    change(panel, { meter_mode: 'single_signed' });
    assert.ok(fieldNames(panel).includes('positive_means'));
    assert.ok(fieldNames(panel).includes('entity_id'));
    assert.ok(!fieldNames(panel).includes('import_entity_id'));

    change(panel, { meter_mode: 'separate_import_export' });
    assert.ok(fieldNames(panel).includes('import_entity_id'));
    assert.ok(fieldNames(panel).includes('export_entity_id'));
    assert.ok(!fieldNames(panel).includes('positive_means'));
  });

  it('asks a price source what kind of price it reports', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);

    assert.ok(!fieldNames(panel).includes('price_basis'));

    change(panel, { type: 'current_price' });

    assert.ok(fieldNames(panel).includes('price_basis'));
    // No default: an unstated basis makes the source unusable rather than
    // assumed, because the two answers differ threefold (SPEC.md §16).
    assert.equal(form(panel).data.price_basis, undefined);
    const field = form(panel).schema.find((entry) => entry.name === 'price_basis');
    assert.match(field.helper, /kale marktprijs/);
    // A grid meter's questions are gone with the type they belonged to.
    assert.ok(!fieldNames(panel).includes('meter_mode'));
  });

  it('asks for an attribute name only when reading an attribute', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);

    assert.ok(!fieldNames(panel).includes('attribute_name'));

    change(panel, { value_source: 'attribute' });

    assert.ok(fieldNames(panel).includes('attribute_name'));
  });

  it('asks for a reason only once control is ruled out', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);

    assert.ok(!fieldNames(panel).includes('control_forbidden_reason'));

    change(panel, { control_forbidden: true });

    assert.ok(fieldNames(panel).includes('control_forbidden_reason'));
  });

  it('states the battery sign convention where the switch is', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);

    change(panel, { type: 'home_battery' });

    // SPEC.md §8 requires this text: brands disagree about the sign, and a
    // wrong one pulls the solar surplus apart without any error.
    const invert = form(panel).schema.find((field) => field.name === 'invert_value');
    assert.match(invert.helper, /positief betekent hier laden/);
    assert.ok(
      noticeTexts(formDialog(panel)).some((text) => text.includes('positief is laden')),
    );
  });

  it('keeps the same form elements while the fields change', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);
    const before = forms(panel);

    change(panel, { type: 'solar' });
    change(panel, { value_source: 'attribute' });

    // Re-creating a form mid-edit would throw away what was being typed
    // (SPEC.md §9). The sections only get a new schema, never a new element.
    assert.deepEqual(forms(panel), before);
  });
});

describe('saving', () => {
  it('keeps the save button disabled until something changed', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);

    assert.equal(buttonIn(formDialog(panel), 'Opslaan').disabled, true);

    change(panel, { name: 'Slimme meter' });

    assert.equal(buttonIn(formDialog(panel), 'Opslaan').disabled, false);
  });

  it('sends only the fields that were asked, with the right revision', async () => {
    const { panel, tab, hass } = await openSourcesTab();
    await openDialogFor(panel, tab);

    // Two steps, because that is the only order a real installer can work in:
    // positive_means does not exist until the meter mode says it should.
    change(panel, { name: 'Slimme meter', meter_mode: 'single_signed' });
    change(panel, { positive_means: 'import', entity_id: 'sensor.p1' });
    buttonIn(formDialog(panel), 'Opslaan').click();
    await settle();

    const sent = lastSent(hass, 'domotiapp_energy/sources/create');
    assert.equal(sent.expected_revision, 7);
    assert.equal(sent.source.name, 'Slimme meter');
    assert.equal(sent.source.positive_means, 'import');
    // Never asked, so never sent: the backend would otherwise store an answer
    // to a question this source does not have.
    assert.ok(!('import_entity_id' in sent.source));
    assert.ok(!('price_basis' in sent.source));
    assert.ok(!('attribute_name' in sent.source));
  });

  it('drops the fields of a type the installer moved away from', async () => {
    const { panel, tab, hass } = await openSourcesTab();
    await openDialogFor(panel, tab);

    change(panel, { meter_mode: 'single_signed' });
    change(panel, { positive_means: 'import' });
    change(panel, { type: 'current_price' });
    change(panel, { price_basis: 'all_in' });
    buttonIn(formDialog(panel), 'Opslaan').click();
    await settle();

    const sent = lastSent(hass, 'domotiapp_energy/sources/create');
    assert.equal(sent.source.type, 'current_price');
    assert.equal(sent.source.price_basis, 'all_in');
    // A stale meter mode on a price source would be stored verbatim.
    assert.ok(!('meter_mode' in sent.source));
    assert.ok(!('positive_means' in sent.source));
  });

  it('sends a cleared field as null, never as an empty string', async () => {
    const { panel, tab, hass } = await openSourcesTab();
    await openDialogFor(panel, tab);

    change(panel, { name: 'Tijdelijk' });
    change(panel, { name: '' });
    change(panel, { meter_mode: 'single_signed' });
    buttonIn(formDialog(panel), 'Opslaan').click();
    await settle();

    const sent = lastSent(hass, 'domotiapp_energy/sources/create');
    assert.equal(sent.source.name, null);
  });

  it('confirms only after the backend answers, and closes the dialog', async () => {
    let release;
    const hass = fakeHass();
    const original = hass.callWS;
    hass.callWS = async (message) => {
      if (message.type === 'domotiapp_energy/sources/create') {
        await new Promise((resolve) => {
          release = resolve;
        });
      }
      return original(message);
    };

    const { panel, tab } = await openSourcesTab(hass);
    await openDialogFor(panel, tab);
    change(panel, { name: 'Slimme meter' });
    buttonIn(formDialog(panel), 'Opslaan').click();
    await settle();

    // In flight: locked, and nothing claiming success yet (SPEC.md §22).
    assert.ok(forms(panel).every((node) => node.disabled));
    assert.ok(
      noticeTexts(formDialog(panel)).some((t) => t.includes('Bezig met opslaan')),
    );
    assert.ok(!noticeTexts(tab).some((t) => t.includes('toegevoegd')));

    release();
    await settle();

    assert.equal(isVisible(formDialog(panel)), false);
    assert.ok(noticeTexts(tab).some((t) => t.includes('is toegevoegd')));
    assert.equal(rows(tab).length, 2);
  });

  it('shows a backend refusal in Dutch and keeps the edit to retry with', async () => {
    const hass = fakeHass();
    const original = hass.callWS;
    hass.callWS = async (message) => {
      if (message.type === 'domotiapp_energy/sources/create') {
        throw { code: 'invalid_format', message: 'Aansturing is uitgesloten.' };
      }
      return original(message);
    };

    const { panel, tab } = await openSourcesTab(hass);
    await openDialogFor(panel, tab);
    change(panel, { name: 'Slimme meter' });
    buttonIn(formDialog(panel), 'Opslaan').click();
    await settle();

    assert.equal(isVisible(formDialog(panel)), true);
    assert.ok(
      noticeTexts(formDialog(panel)).some((t) =>
        t.includes('Aansturing is uitgesloten'),
      ),
    );
    assert.equal(form(panel).data.name, 'Slimme meter');
  });

  it('keeps a new source on screen when another row changed', async () => {
    // This used to close the dialog and discard the input (SPEC.md §49.4). The
    // conflict is about `grid`; nothing about the row being created is stale,
    // so there is nothing to protect by throwing it away.
    const theirs = sampleConfig({
      revision: 9,
      sources: [
        { id: 'grid', name: 'Door iemand anders hernoemd', type: 'grid_meter' },
      ],
    });
    const hass = fakeHass();
    const original = hass.callWS;
    hass.callWS = async (message) => {
      if (message.type === 'domotiapp_energy/sources/create') {
        throw {
          code: 'revision_conflict',
          message: 'stale',
          revision: 9,
          config: theirs,
        };
      }
      return original(message);
    };

    const { panel, tab } = await openSourcesTab(hass);
    await openDialogFor(panel, tab);
    change(panel, { name: 'Mijn bron' });
    buttonIn(formDialog(panel), 'Opslaan').click();
    await settle();

    assert.equal(isVisible(formDialog(panel)), true);
    assert.equal(form(panel).data.name, 'Mijn bron');
    assert.ok(
      noticeTexts(formDialog(panel)).some((t) => t.includes('niet aan deze bron')),
    );
    // The other change is adopted underneath, so the list is current.
    assert.match(visibleText(rows(tab)[0]), /Door iemand anders hernoemd/);
  });

  it('places a backend validation issue on the field it is about', async () => {
    const hass = fakeHass({
      config: sampleConfig({
        sources: [{ id: 'prijs', name: 'Prijs', type: 'current_price', enabled: true }],
        issues: {
          prijs: [
            {
              field: 'price_basis',
              code: 'required',
              message: 'Geef aan wat deze bron levert.',
              severity: 'error',
            },
          ],
        },
      }),
    });
    const { panel, tab } = await openSourcesTab(hass);

    // Visible on the row without opening anything...
    assert.match(visibleText(rows(tab)[0]), /Nog niet compleet/);

    buttonIn(rows(tab)[0], 'Bewerken').click();
    await settle();

    // ...and next to the field itself once the dialog is open (SPEC.md §14).
    assert.deepEqual(form(panel).error, {
      price_basis: 'Geef aan wat deze bron levert.',
    });
  });
});

describe('deleting', () => {
  it('asks first and does nothing when the answer is no', async () => {
    const { panel, tab, hass } = await openSourcesTab();

    buttonIn(rows(tab)[0], 'Verwijderen').click();
    await settle();

    assert.equal(isVisible(confirmDialog(panel)), true);
    assert.match(visibleText(confirmDialog(panel)), /Weet je zeker/);

    buttonIn(confirmDialog(panel), 'Annuleren').click();
    await settle();

    assert.equal(isVisible(confirmDialog(panel)), false);
    assert.equal(lastSent(hass, 'domotiapp_energy/sources/delete'), undefined);
    assert.equal(rows(tab).length, 1);
  });

  it('deletes once it is confirmed', async () => {
    const { panel, tab, hass } = await openSourcesTab();

    buttonIn(rows(tab)[0], 'Verwijderen').click();
    await settle();
    buttonIn(confirmDialog(panel), 'Verwijderen').click();
    await settle();

    const sent = lastSent(hass, 'domotiapp_energy/sources/delete');
    assert.equal(sent.source_id, 'grid');
    assert.equal(sent.expected_revision, 7);
    assert.equal(rows(tab).length, 0);
    assert.ok(noticeTexts(tab).some((t) => t.includes('is verwijderd')));
  });
});

describe('unsaved changes', () => {
  it('asks a visible question before throwing an edit away', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);
    change(panel, { name: 'Halverwege' });

    buttonIn(formDialog(panel), 'Annuleren').click();
    await settle();

    assert.equal(isVisible(formDialog(panel)), true);
    assert.equal(isVisible(confirmDialog(panel)), true);

    buttonIn(confirmDialog(panel), 'Verwerpen').click();
    await settle();

    assert.equal(isVisible(formDialog(panel)), false);
  });

  it('asks the same question for a click beside the dialog', async () => {
    // The click that cost an almost-finished form: the backdrop went through a
    // different route than the close button and closed without asking.
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);
    change(panel, { name: 'Bijna klaar' });

    formDialog(panel).querySelector('.dialog-scrim').click();
    await settle();

    assert.equal(isVisible(formDialog(panel)), true);
    assert.equal(isVisible(confirmDialog(panel)), true);
    assert.equal(form(panel).data.name, 'Bijna klaar');
  });

  it('asks the same question for Escape', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);
    change(panel, { name: 'Bijna klaar' });

    const view = formDialog(panel).ownerDocument.defaultView;
    formDialog(panel).dispatchEvent(
      new view.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }),
    );
    await settle();

    assert.equal(isVisible(formDialog(panel)), true);
    assert.equal(isVisible(confirmDialog(panel)), true);
  });

  it('closes without a question when nothing was changed', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);

    buttonIn(formDialog(panel), 'Annuleren').click();
    await settle();

    assert.equal(isVisible(formDialog(panel)), false);
  });

  it('keeps the installer on the tab while the dialog holds an edit', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);
    change(panel, { name: 'Halverwege' });

    clickTab(panel, 'Overzicht');
    await settle();

    assert.equal(tabPanels(panel).filter(isVisible)[0].id, 'panel-installation');
    assert.equal(isVisible(confirmDialog(panel)), true);
  });

  it('lets the installer leave once the dialog is clean', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);

    clickTab(panel, 'Overzicht');
    await settle();

    assert.equal(tabPanels(panel).filter(isVisible)[0].id, 'panel-overview');
    assert.equal(isVisible(formDialog(panel)), false);
  });
});

describe('what the form hands to a selector', () => {
  it('never offers a select option whose value is not a string', async () => {
    // Same invariant as the device form: a numeric option value is dropped by
    // the combobox without a word, and jsdom cannot see it happen.
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);

    for (const type of ['grid_meter', 'current_price', 'home_battery', 'solar']) {
      change(panel, { type });
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

describe('helper texts that know what kind of source this is', () => {
  it('explains the entity differently per source type', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);

    change(panel, { type: 'solar' });
    assert.match(
      form(panel).schema.find((f) => f.name === 'entity_id').helper,
      /actuele zonneproductie/,
    );

    change(panel, { type: 'home_battery' });
    assert.match(
      form(panel).schema.find((f) => f.name === 'entity_id').helper,
      /laad- of ontlaadvermogen/,
    );
  });

  it('names the units that make sense for this type', async () => {
    const { panel, tab } = await openSourcesTab();
    await openDialogFor(panel, tab);

    change(panel, { type: 'current_price' });
    assert.match(
      form(panel).schema.find((f) => f.name === 'unit').helper,
      /EUR\/kWh of ct\/kWh/,
    );

    change(panel, { type: 'solar' });
    assert.match(form(panel).schema.find((f) => f.name === 'unit').helper, /W of kW/);
  });
});

describe('een bron die compleet is en toch niet gebruikt wordt (SPEC.md §64)', () => {
  const geweigerd = (invalidItems, extra = {}) =>
    fakeHass({
      coach: sampleCoach({
        metrics: {
          data_quality: {
            score: 100,
            missing_items: [],
            completed_items: [],
            invalid_items: invalidItems,
          },
        },
      }),
      ...extra,
    });

  it('zegt niet langer "Compleet." over een rij die de motor zojuist weigerde', async () => {
    // De rij was compleet ingevuld en het logboek schreef er een waarschuwing
    // over; het scherm sprak dat tegen.
    const { tab } = await openSourcesTab(geweigerd(['grid']));
    await settle();

    const rij = visibleText(tab);

    assert.match(rij, /op dit moment niet uit te lezen/);
    assert.doesNotMatch(rij, /Compleet\.$/m);
  });

  it('zwijgt zolang er nog geen berekening is', async () => {
    const { tab } = await openSourcesTab(geweigerd([]));
    await settle();

    const rij = visibleText(tab);

    assert.match(rij, /Compleet\./);
    assert.doesNotMatch(rij, /niet uit te lezen/);
  });

  it('laat een onvoltooide rij zijn eigen boodschap houden', async () => {
    // **De volgorde is het mechanisme** (SPEC.md §64.2). Een onvoltooide rij
    // wordt door de motor óók geweigerd en staat dus óók in `invalid_items`.
    // Kwam de nieuwe tak eerder, dan kreeg de installateur "niet uit te lezen"
    // te zien op een rij waar hij nog een veld moet invullen.
    const { tab } = await openSourcesTab(
      geweigerd(['grid'], {
        config: sampleConfig({
          issues: {
            grid: [
              {
                field: 'meter_mode',
                message: 'Kies een metermodus.',
                severity: 'error',
              },
            ],
          },
        }),
      }),
    );
    await settle();

    const rij = visibleText(tab);

    assert.match(rij, /Nog niet compleet: Kies een metermodus\./);
    assert.doesNotMatch(rij, /niet uit te lezen/);
  });
});
