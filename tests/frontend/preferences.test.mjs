/**
 * Tests for the Voorkeuren and Logboek tabs (SPEC.md §8, §11, §14 and §22).
 *
 * Voorkeuren repeats the save cycle the Woning tab established, so the tests
 * here pin what is specific: the fields exist, the threshold explains which
 * advice it actually filters, and a backend message lands on its own field.
 *
 * Logboek is read-only with one action that is not, and the tests concentrate
 * on exactly that seam: who may empty it, that it asks first, and that a
 * collapsed run of events says how often it happened.
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

async function openTab(label, id, hass = fakeHass()) {
  const panel = await mountPanel(hass);
  clickTab(panel, label);
  await settle();
  const tab = tabPanels(panel).find((node) => node.id === `panel-${id}`);
  return { panel, tab, hass };
}

function forms(tab) {
  return [...tab.querySelectorAll('ha-form')];
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

function noticeTexts(root) {
  return [...root.querySelectorAll('.notice')]
    .filter(isVisible)
    .map((node) => node.querySelector('.notice-text').textContent);
}

function change(tab, values, formIndex = 0) {
  const node = forms(tab)[formIndex];
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

describe('the Voorkeuren tab', () => {
  it('carries every preference SPEC.md §8 lists', async () => {
    const { tab } = await openTab('Voorkeuren', 'preferences');

    const names = forms(tab).flatMap((form) =>
      form.schema.map((field) => field.name),
    );

    assert.deepEqual(names.sort(), [
      'allow_advice_during_quiet_hours',
      'max_advice_count',
      'min_savings_eur',
      'prefer_low_price',
      'prefer_solar',
      'quiet_hours_end',
      'quiet_hours_start',
      'respect_max_grid_load',
      'show_confidence',
      'show_estimated_savings',
      'show_technical_explanation',
    ]);
  });

  it('says which advice the savings threshold does not filter', async () => {
    const { tab } = await openTab('Voorkeuren', 'preferences');
    const field = forms(tab)
      .flatMap((form) => form.schema)
      .find((entry) => entry.name === 'min_savings_eur');

    // Under net metering a saving of zero is the normal case, and filtering it
    // would leave the panel almost silent for a year (SPEC.md §8).
    assert.match(field.helper, /b[oó]ven nul/i);
    assert.match(field.helper, /blijft altijd staan/);
  });

  it('sends the whole profile with the revision it was filled in against', async () => {
    const { tab, hass } = await openTab('Voorkeuren', 'preferences');

    change(tab, { quiet_hours_start: '23:00' });
    buttonIn(tab, 'Opslaan').click();
    await settle();

    const sent = lastSent(hass, 'domotiapp_energy/preferences/update');
    assert.equal(sent.expected_revision, 7);
    assert.equal(sent.preferences.quiet_hours_start, '23:00');
    // Untouched fields travel along: the backend replaces the whole profile.
    assert.ok('max_advice_count' in sent.preferences);
  });

  it('keeps the save button disabled until something changed', async () => {
    const { tab } = await openTab('Voorkeuren', 'preferences');

    assert.equal(buttonIn(tab, 'Opslaan').disabled, true);

    change(tab, { quiet_hours_start: '23:00' });

    assert.equal(buttonIn(tab, 'Opslaan').disabled, false);
  });

  it('puts a backend validation message on the field it belongs to', async () => {
    const hass = fakeHass({
      config: sampleConfig({
        issues: {
          preferences: [
            {
              field: 'max_advice_count',
              code: 'out_of_range',
              message: 'Toon minimaal 1 en maximaal 5 adviezen.',
              severity: 'error',
            },
          ],
        },
      }),
    });
    const { tab } = await openTab('Voorkeuren', 'preferences', hass);

    // The display card is the fourth: quiet hours, weighing, threshold, display.
    assert.deepEqual(forms(tab)[3].error, {
      max_advice_count: 'Toon minimaal 1 en maximaal 5 adviezen.',
    });
    assert.equal(forms(tab)[0].error, undefined);
  });

  it('refuses to leave with unsaved changes', async () => {
    const { panel, tab } = await openTab('Voorkeuren', 'preferences');
    change(tab, { quiet_hours_start: '23:00' });

    clickTab(panel, 'Overzicht');
    await settle();

    assert.equal(tabPanels(panel).filter(isVisible)[0].id, 'panel-preferences');
    assert.ok(noticeTexts(tab).some((t) => t.includes('nog niet zijn opgeslagen')));
  });
});

/** A logbook answer, in the shape logs/list returns one. */
function logs(...overrides) {
  return {
    logs: overrides.map((entry, index) => ({
      id: `log-${index}`,
      timestamp: '2026-08-06T10:00:00+00:00',
      event_type: 'source_unavailable',
      title: 'Bron niet beschikbaar',
      message: 'De netmeter kon niet worden gelezen.',
      severity: 'warning',
      subject: 'grid',
      count: 1,
      ...entry,
    })),
  };
}

/** A hass whose logs/list answers with these entries. */
function hassWithLogs(answer, { isAdmin = true } = {}) {
  const hass = fakeHass({ isAdmin });
  const original = hass.callWS;
  hass.callWS = async (message) => {
    if (message.type === 'domotiapp_energy/logs/list') {
      hass.sent.push(message);
      return answer;
    }
    return original(message);
  };
  return hass;
}

describe('the Logboek tab', () => {
  it('shows each event with its time, type and severity in words', async () => {
    const { tab } = await openTab('Logboek', 'logbook', hassWithLogs(logs({})));
    await settle();

    const row = tab.querySelector('.row-item');
    assert.match(row.textContent, /Bron niet beschikbaar/);
    assert.match(row.textContent, /De netmeter kon niet worden gelezen/);
    // Icon and colour are additions; the meaning is in the word.
    assert.match(row.querySelector('.row-status span').textContent, /Waarschuwing/);
  });

  it('says how often a collapsed run happened', async () => {
    const { tab } = await openTab(
      'Logboek',
      'logbook',
      hassWithLogs(logs({ count: 40 })),
    );
    await settle();

    // Without this, forty dropouts read as one (SPEC.md §8).
    assert.match(tab.querySelector('.row-status span').textContent, /40 keer/);
  });

  it('says what will appear when the logbook is still empty', async () => {
    const { tab } = await openTab('Logboek', 'logbook', hassWithLogs(logs()));
    await settle();

    assert.match(tab.querySelector('.empty-text').textContent, /logboek is leeg/i);
  });

  it('offers the clear button to an admin only', async () => {
    const { tab } = await openTab('Logboek', 'logbook', hassWithLogs(logs({})));
    await settle();
    assert.equal(isVisible(buttonIn(tab, 'Logboek wissen').parentElement), true);

    const readOnly = await openTab(
      'Logboek',
      'logbook',
      hassWithLogs(logs({}), { isAdmin: false }),
    );
    await settle();
    assert.equal(
      isVisible(buttonIn(readOnly.tab, 'Logboek wissen').parentElement),
      false,
    );
  });

  it('asks before emptying it, and does nothing when the answer is no', async () => {
    const hass = hassWithLogs(logs({}));
    const { panel, tab } = await openTab('Logboek', 'logbook', hass);
    await settle();

    buttonIn(tab, 'Logboek wissen').click();
    await settle();

    const confirm = [...panel.shadowRoot.querySelectorAll('.dialog')].find(isVisible);
    assert.ok(confirm, 'emptying the logbook has to ask first');
    buttonIn(confirm, 'Annuleren').click();
    await settle();

    assert.equal(lastSent(hass, 'domotiapp_energy/logs/clear'), undefined);
    assert.equal(tab.querySelectorAll('.row-item').length, 1);
  });

  it('empties it once that is confirmed', async () => {
    const hass = hassWithLogs(logs({}));
    const { panel, tab } = await openTab('Logboek', 'logbook', hass);
    await settle();

    buttonIn(tab, 'Logboek wissen').click();
    await settle();
    const confirm = [...panel.shadowRoot.querySelectorAll('.dialog')].find(isVisible);
    buttonIn(confirm, 'Wissen').click();
    await settle();

    assert.ok(lastSent(hass, 'domotiapp_energy/logs/clear'));
    assert.equal(tab.querySelectorAll('.row-item').length, 0);
    assert.ok(noticeTexts(tab).some((t) => t.includes('gewist')));
  });

  it('reports a refusal in Dutch instead of emptying the list', async () => {
    const hass = hassWithLogs(logs({}));
    const original = hass.callWS;
    hass.callWS = async (message) => {
      if (message.type === 'domotiapp_energy/logs/clear') {
        throw { code: 'unauthorized', message: 'Unauthorized' };
      }
      return original(message);
    };
    const { panel, tab } = await openTab('Logboek', 'logbook', hass);
    await settle();

    buttonIn(tab, 'Logboek wissen').click();
    await settle();
    const confirm = [...panel.shadowRoot.querySelectorAll('.dialog')].find(isVisible);
    buttonIn(confirm, 'Wissen').click();
    await settle();

    assert.ok(
      noticeTexts(tab).some((t) => t.includes('geen rechten')),
      `notices were: ${JSON.stringify(noticeTexts(tab))}`,
    );
    // The entry is still there: nothing may claim success the backend refused.
    assert.equal(tab.querySelectorAll('.row-item').length, 1);
  });
});
