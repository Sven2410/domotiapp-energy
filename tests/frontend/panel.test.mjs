/**
 * Tests for the panel's visibility contract (SPEC.md §7, §9 and §23).
 *
 * These exist because phase 7a shipped three bugs that every check at the time
 * was structurally blind to: parsing the files, importing the modules and
 * fetching them over HTTP all passed while tab panels stacked up, the
 * configuration tabs stayed visible for a non-admin, and icons were left on
 * screen without their sentence. Nothing in that verification ever built a DOM.
 *
 * The rule these tests encode: **hiding is the panel's own contract**, carried
 * by the `is-hidden` class, never by the bare `hidden` attribute and never by
 * the browser's cascade.
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
  tabButtons,
  tabPanels,
} from './harness.mjs';

const ALL_TABS = [
  'Overzicht',
  'Woning',
  'Energiebronnen',
  'Apparaten',
  'Voorkeuren',
  'Energiecoach',
  'Logboek',
];

const READ_ONLY_TABS = ['Overzicht', 'Energiecoach', 'Logboek'];

describe('tab navigation', () => {
  it('shows exactly one panel and hides the other six', async () => {
    const panel = await mountPanel();

    // Open every tab once, so all seven panels exist and the assertion below
    // really covers six hidden ones rather than however many happen to be built.
    for (const label of ALL_TABS) {
      clickTab(panel, label);
      await settle();
    }
    assert.equal(tabPanels(panel).length, ALL_TABS.length);

    for (const label of ALL_TABS) {
      clickTab(panel, label);
      await settle();

      const visible = tabPanels(panel).filter(isVisible);
      assert.equal(
        visible.length,
        1,
        `${label}: expected one visible panel, found ${visible.length}`,
      );
      const hidden = tabPanels(panel).filter((node) => !isVisible(node));
      assert.equal(hidden.length, ALL_TABS.length - 1);
    }
  });

  it('marks the opened tab as selected and no other', async () => {
    const panel = await mountPanel();

    clickTab(panel, 'Voorkeuren');
    await settle();

    const selected = tabButtons(panel).filter(
      (button) => button.getAttribute('aria-selected') === 'true',
    );
    assert.equal(selected.length, 1);
    assert.match(selected[0].textContent, /Voorkeuren/);
  });

  it('builds a tab once and reuses it', async () => {
    const panel = await mountPanel();

    clickTab(panel, 'Logboek');
    await settle();
    clickTab(panel, 'Overzicht');
    await settle();
    clickTab(panel, 'Logboek');
    await settle();

    assert.equal(tabPanels(panel).length, 2);
  });
});

describe('permissions', () => {
  it('shows an admin all seven tabs', async () => {
    const panel = await mountPanel(fakeHass({ isAdmin: true }));

    const visible = tabButtons(panel).filter(isVisible);

    assert.equal(visible.length, 7);
  });

  it('shows a non-admin only the three read-only tabs', async () => {
    const panel = await mountPanel(fakeHass({ isAdmin: false }));

    const visible = tabButtons(panel).filter(isVisible);
    const labels = visible.map((button) => button.textContent.trim());

    assert.equal(visible.length, 3);
    for (const label of READ_ONLY_TABS) {
      assert.ok(
        labels.some((text) => text.includes(label)),
        `${label} should be visible for a non-admin`,
      );
    }
    for (const label of ['Woning', 'Energiebronnen', 'Apparaten', 'Voorkeuren']) {
      assert.ok(
        !labels.some((text) => text.includes(label)),
        `${label} must be hidden for a non-admin`,
      );
    }
  });

  it('keeps a non-admin on a tab they may see', async () => {
    const panel = await mountPanel(fakeHass({ isAdmin: false }));

    // The button is hidden, but a stale click must not strand them either.
    clickTab(panel, 'Overzicht');
    await settle();

    const visible = tabPanels(panel).filter(isVisible);
    assert.equal(visible.length, 1);
    assert.equal(visible[0].id, 'panel-overview');
  });
});

describe('notices and the banner', () => {
  it('hides every notice whose sentence is empty', async () => {
    // Sources configured, no peak risk, and a warning present: three of the
    // four notices on the Overzicht have nothing to say.
    const panel = await mountPanel(
      fakeHass({
        coach: sampleCoach({ metrics: { peak_risk: false } }),
      }),
    );

    const notices = [...panel.shadowRoot.querySelectorAll('.notice')];
    assert.equal(notices.length, 4);

    for (const node of notices.filter(isVisible)) {
      assert.notEqual(
        node.querySelector('.notice-text').textContent.trim(),
        '',
        'a visible notice must carry text, never an icon on its own',
      );
    }
    assert.equal(notices.filter(isVisible).length, 1);
  });

  it('shows the peak notice again when the risk returns', async () => {
    const panel = await mountPanel(
      fakeHass({ coach: sampleCoach({ metrics: { peak_risk: true } }) }),
    );

    const texts = [...panel.shadowRoot.querySelectorAll('.notice')]
      .filter(isVisible)
      .map((node) => node.querySelector('.notice-text').textContent);

    assert.ok(texts.some((text) => text.includes('Piekrisico')));
  });

  it('hides the status banner once loading succeeded', async () => {
    const panel = await mountPanel();

    const banner = panel.shadowRoot.querySelector('.banner');

    assert.ok(!isVisible(banner));
  });

  it('shows the banner with a Dutch message when loading fails', async () => {
    const hass = fakeHass();
    hass.callWS = async () => {
      throw { code: 'not_found', message: 'nope' };
    };

    const panel = await mountPanel(hass);
    const banner = panel.shadowRoot.querySelector('.banner');

    assert.ok(isVisible(banner));
    assert.match(banner.textContent, /niet geladen/);
  });
});

describe('empty and populated configurations', () => {
  it('renders an empty configuration without throwing', async () => {
    const panel = await mountPanel(
      fakeHass({
        config: sampleConfig({ sources: [], devices: [] }),
        coach: sampleCoach({
          primary_advice: null,
          advice: [],
          metrics: {
            grid_power_w: null,
            solar_surplus_w: null,
            grid_load_percent: null,
            peak_risk: false,
            energy_score: 8,
            data_quality: { score: 0, missing_items: ['a', 'b', 'c'] },
          },
        }),
      }),
    );

    const text = panel.shadowRoot.textContent;

    // Empty states have to read as instructions, not as blank rows.
    assert.match(text, /Nog niet ingesteld/);
    assert.match(text, /nog geen energiebronnen gekoppeld/);
  });

  it('shows the configured values on the Overzicht', async () => {
    const panel = await mountPanel();

    const text = panel.shadowRoot.textContent;

    assert.match(text, /Mijn woning/);
    assert.match(text, /Aanvullende gegevens nodig/);
  });

  it('gives the score its own headline figure, apart from its label', async () => {
    // The house style asks the number to dominate; a score and its label at
    // the same weight read as two equal facts. Structure is what carries that,
    // so this asserts the structure rather than the font size.
    const panel = await mountPanel();
    const [score] = [...panel.shadowRoot.querySelectorAll('.display-metric')];

    assert.equal(score.querySelector('.label').textContent, 'Energiescore');
    assert.equal(score.querySelector('.display-value').textContent, '46');
    // "van 100" read as a report card on the household. The score is a reading
    // of this moment: at night components drop out because there is nothing to
    // measure, not because anything is wrong.
    assert.equal(
      score.querySelector('.display-suffix').textContent,
      'op dit moment',
    );
  });

  it('shows a warning as a block with a marker, not as a bullet', async () => {
    const panel = await mountPanel();
    const items = [...panel.shadowRoot.querySelectorAll('.advice-item')];

    assert.equal(items.length, 1);
    assert.equal(items[0].querySelector('.label').textContent, 'Waarschuwing');
    assert.match(
      items[0].querySelector('.advice-item-title').textContent,
      /Aanvullende gegevens nodig/,
    );
    // A bullet list is what made these read as an error log.
    assert.equal(panel.shadowRoot.querySelectorAll('.advice-list ul').length, 0);
  });

  it('shows an empty score as words, not as a dash or a blank', async () => {
    const panel = await mountPanel(
      fakeHass({
        coach: sampleCoach({ metrics: { energy_score: null } }),
      }),
    );
    const [score] = [...panel.shadowRoot.querySelectorAll('.display-metric')];

    assert.ok(!isVisible(score.querySelector('.display-value')));
    assert.equal(score.querySelector('.display-empty').textContent, 'Nog niet berekend');
  });

  it('does not rebuild the DOM when the state changes', async () => {
    const panel = await mountPanel();
    const overview = tabPanels(panel)[0];
    const firstCard = overview.querySelector('ha-card');

    clickTab(panel, 'Logboek');
    await settle();
    clickTab(panel, 'Overzicht');
    await settle();

    // Same node, not a replacement: a rebuild would lose focus and scroll
    // position, which SPEC.md §9 forbids.
    assert.equal(overview.querySelector('ha-card'), firstCard);
  });
});

describe('the actual energy price on the Overzicht', () => {
  /** The row labelled "Actuele energieprijs", whatever its position. */
  function priceRow(panel) {
    const row = [...panel.shadowRoot.querySelectorAll('.stat-row')].find((node) =>
      node.querySelector('.stat-label').textContent.includes('Actuele energieprijs'),
    );
    if (!row) {
      throw new Error('No price row on the Overzicht');
    }
    return {
      value: row.querySelector('.stat-value').textContent,
      hint: row.querySelector('.stat-hint').textContent,
      hintVisible: isVisible(row.querySelector('.stat-hint')),
    };
  }

  function withPrice(metrics, home = {}) {
    return fakeHass({
      config: sampleConfig({
        home: { ...sampleConfig().home, contract_type: 'dynamic', ...home },
      }),
      coach: sampleCoach({ metrics }),
    });
  }

  it('shows the all-in price the engine calculates with', async () => {
    const panel = await mountPanel(
      withPrice({ current_price_eur_kwh: 0.2526, market_price_eur_kwh: null }),
    );

    // The all-in price is the only kind that exists past the calculator.
    assert.match(priceRow(panel).value, /0,253/);
    assert.match(priceRow(panel).value, /per kWh/);
    assert.equal(priceRow(panel).hintVisible, false);
  });

  it('names the market price it was derived from', async () => {
    const panel = await mountPanel(
      withPrice({ current_price_eur_kwh: 0.2526, market_price_eur_kwh: 0.08 }),
    );

    // Without this the installer has to take a multiplication on faith that
    // they cannot check against the sensor in front of them (SPEC.md §8).
    assert.equal(priceRow(panel).hintVisible, true);
    assert.match(priceRow(panel).hint, /marktprijs/);
    assert.match(priceRow(panel).hint, /0,080/);
  });

  it('says a fixed contract has no hourly price rather than leaving it blank', async () => {
    const panel = await mountPanel(
      fakeHass({
        coach: sampleCoach({ metrics: { current_price_eur_kwh: 0.3 } }),
      }),
    );

    // The sample configuration is on a fixed contract.
    assert.match(priceRow(panel).value, /Niet van toepassing bij een vast contract/);
  });

  it('tells a missing price source apart from a fixed contract', async () => {
    const panel = await mountPanel(
      withPrice({ current_price_eur_kwh: null, market_price_eur_kwh: null }),
    );

    // One of the two is something to go and fix; the other never will be.
    assert.match(priceRow(panel).value, /Geen bruikbare prijsbron/);
  });
});
