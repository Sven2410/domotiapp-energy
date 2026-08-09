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
  'Energiecoach',
  'Apparaten',
  'Mijn voorkeuren',
  'Installatie',
  'Logboek',
];

describe('tab navigation', () => {
  it('shows exactly one panel and hides the other five', async () => {
    const panel = await mountPanel();

    // Open every tab once, so all six panels exist and the assertion below
    // really covers five hidden ones rather than however many happen to be
    // built.
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

    clickTab(panel, 'Mijn voorkeuren');
    await settle();

    const selected = tabButtons(panel).filter(
      (button) => button.getAttribute('aria-selected') === 'true',
    );
    assert.equal(selected.length, 1);
    assert.match(selected[0].textContent, /Mijn voorkeuren/);
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
  /**
   * The whole point of SPEC.md §33.6, and the reverse of what this suite used
   * to assert: four tabs disappeared for a non-admin, so a resident could not
   * see that his main fuse was wrong and could not set his own quiet hours
   * either. Both roles now get the same six tabs; what he does not own is
   * greyed out where he can read it.
   */
  for (const isAdmin of [true, false]) {
    it(`shows the same six tabs (isAdmin=${isAdmin})`, async () => {
      const panel = await mountPanel(fakeHass({ isAdmin }));

      const labels = tabButtons(panel)
        .filter(isVisible)
        .map((button) => button.textContent.trim());

      assert.equal(labels.length, ALL_TABS.length);
      for (const label of ALL_TABS) {
        assert.ok(
          labels.some((text) => text.includes(label)),
          `${label} should be visible for isAdmin=${isAdmin}`,
        );
      }
    });
  }

  it('lets a resident open the Installatie tab', async () => {
    const panel = await mountPanel(fakeHass({ isAdmin: false }));

    clickTab(panel, 'Installatie');
    await settle();

    const visible = tabPanels(panel).filter(isVisible);
    assert.equal(visible.length, 1);
    assert.equal(visible[0].id, 'panel-installation');
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
    assert.equal(notices.length, 8);

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

  it('shows the live situation on the Overzicht', async () => {
    const panel = await mountPanel();

    const text = panel.shadowRoot.textContent;

    assert.match(text, /Aanvullende gegevens nodig/);
    // The home name and the row counts went with the Configuratie card in
    // 0.4.1: they restate two other tabs and are not a reading of this moment.
    assert.doesNotMatch(text, /Mijn woning/);
    assert.doesNotMatch(text, /Configuratie/);
  });

  /** The headline figure carrying this label, by label rather than by index. */
  const headline = (panel, label) =>
    [...panel.shadowRoot.querySelectorAll('.display-metric')].find(
      (node) => node.querySelector('.label').textContent === label,
    );

  it('leads with the home consumption, not with the score', async () => {
    // SPEC.md §35.8b. The score may be absent by design, so the largest place
    // on the screen cannot belong to it. The home consumption is there
    // whenever the meters can be read, which is exactly when the score is not.
    const panel = await mountPanel(
      fakeHass({
        coach: sampleCoach({
          metrics: { energy_score: null, home_consumption_w: 1635 },
        }),
      }),
    );

    const [first] = [...panel.shadowRoot.querySelectorAll('.display-metric')];

    assert.equal(first.querySelector('.label').textContent, 'Thuisverbruik');
    assert.equal(first.querySelector('.display-value').textContent, '1.635');
    assert.ok(isVisible(first.querySelector('.display-value')));
  });

  it('gives the score its own headline figure, apart from its label', async () => {
    // The house style asks the number to dominate; a score and its label at
    // the same weight read as two equal facts. Structure is what carries that,
    // so this asserts the structure rather than the font size.
    const panel = await mountPanel();
    const score = headline(panel, 'Energiescore');

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
    const score = headline(panel, 'Energiescore');

    assert.ok(!isVisible(score.querySelector('.display-value')));
    assert.equal(score.querySelector('.display-empty').textContent, 'Geen cijfer');
  });

  // SPEC.md §35.9. A tile with a dash reads as a fault; three of these four
  // describe a home that is doing nothing wrong, so the sentence has to say
  // *why* there is nothing to measure and not merely that there is no number.
  const SCORE_REASONS = [
    ['no_variable_signal', 'geen zonnepanelen', 'info'],
    ['nothing_movable', 'Er is nu opwek', 'info'],
    ['no_sun_cheap_price', 'panelen leveren op dit moment niets', 'info'],
    ['no_sun_fixed_tariff', 'bij een vast tarief', 'info'],
    ['cheap_price', 'stroomprijs is op dit moment laag', 'info'],
    // SPEC.md §35.4d. Informative and not a warning: this resident is earning
    // money, and a warning colour would turn that into a problem.
    ['feed_in_pays_better', 'terugleveren levert je meer op', 'info'],
    ['incomplete_setup', 'installatie nog niet compleet', 'warning'],
    ['price_thresholds_missing', 'prijsdrempel', 'warning'],
  ];

  // The sentence for a home with no panels may not mention panels, and the one
  // for a fixed tariff may not mention expensive hours. That confusion is what
  // the old catch-all sentence shipped (0.4.1).
  const FORBIDDEN_IN = {
    cheap_price: /panelen|opwek/,
    no_sun_fixed_tariff: /duur (moment|verbruik)|stroomprijs/,
    no_variable_signal: /op dit moment/,
  };

  for (const [reason, fragment, tone] of SCORE_REASONS) {
    it(`explains why there is no score: ${reason}`, async () => {
      const panel = await mountPanel(
        fakeHass({
          coach: sampleCoach({
            metrics: { energy_score: null, score_unavailable_reason: reason },
          }),
        }),
      );

      const visible = [...panel.shadowRoot.querySelectorAll('.notice')]
        .filter(isVisible)
        .map((node) => node.querySelector('.notice-text').textContent);
      const sentence = visible.find((text) => text.includes(fragment));

      assert.ok(sentence, `expected a sentence explaining ${reason}`);
      const forbidden = FORBIDDEN_IN[reason];
      if (forbidden) {
        assert.doesNotMatch(sentence, forbidden);
      }
      // Only the incomplete installation is a shortcoming. The others may not
      // shout at a resident who has done nothing wrong.
      const node = [...panel.shadowRoot.querySelectorAll('.notice')].find(
        (candidate) =>
          candidate.querySelector('.notice-text').textContent === sentence,
      );
      assert.equal(node.dataset.tone, tone);
    });
  }

  // SPEC.md §35.9b. The mirror case: there *is* a number, reached over one
  // axis instead of two, and until now nothing on the screen said so. Reading
  // 88 with the solar axis excluded because feeding in pays better is not the
  // same as reading 88 with everything counted, and the resident could not
  // tell the two apart.
  const COMPONENT_REASONS = [
    ['solar_no_panels', 'geen zonnepanelen'],
    ['solar_no_production', 'panelen leveren op dit moment niets'],
    ['solar_no_grid_reading', 'zonder netmeting'],
    ['solar_nothing_movable', 'geen apparaat of batterij'],
    ['solar_feed_in_pays_better', 'terugleveren levert je op dit moment meer op'],
    ['price_fixed_tariff', 'bij een vast tarief'],
    ['price_thresholds_missing', 'prijsdrempel'],
    ['price_no_reading', 'niet uit te lezen'],
    ['price_cheap', 'de stroom is nu goedkoop'],
  ];

  for (const [reason, fragment] of COMPONENT_REASONS) {
    it(`says why an axis did not count: ${reason}`, async () => {
      const component = reason.startsWith('solar')
        ? 'solar_component'
        : 'price_component';
      const panel = await mountPanel(
        fakeHass({
          coach: sampleCoach({
            metrics: {
              energy_score: 88,
              not_applicable_components: [component],
              component_unavailable_reasons: { [component]: reason },
            },
          }),
        }),
      );

      const visible = [...panel.shadowRoot.querySelectorAll('.notice')]
        .filter(isVisible)
        .map((node) => node.querySelector('.notice-text').textContent);

      assert.ok(
        visible.some((text) => text.includes(fragment)),
        `expected a sentence explaining ${reason}`,
      );
    });
  }

  it('does not explain an axis when there is no score to qualify', async () => {
    // Without a number the tile's own sentence already covers the ground, and
    // two explanations of the same silence read as a fault.
    const panel = await mountPanel(
      fakeHass({
        coach: sampleCoach({
          metrics: {
            energy_score: null,
            score_unavailable_reason: 'cheap_price',
            not_applicable_components: ['solar_component'],
            component_unavailable_reasons: { solar_component: 'solar_no_panels' },
          },
        }),
      }),
    );

    const visible = [...panel.shadowRoot.querySelectorAll('.notice')]
      .filter(isVisible)
      .map((node) => node.querySelector('.notice-text').textContent);

    assert.ok(!visible.some((text) => text.includes('telt niet mee')));
  });

  it('shows the self-consumption as a measurement, without a score', async () => {
    // SPEC.md §35.8b: a measurement has no direction, so it belongs among the
    // meter readings and is there whenever it can be read — including when the
    // verdict over it is not.
    const panel = await mountPanel(
      fakeHass({
        coach: sampleCoach({
          metrics: { energy_score: null, self_consumption_percent: 35.1 },
        }),
      }),
    );

    const row = [...panel.shadowRoot.querySelectorAll('.stat-row')].find((node) =>
      node.querySelector('.stat-label').textContent.includes('Zelfbenutting'),
    );

    assert.ok(row, 'expected a Zelfbenutting row');
    assert.equal(row.querySelector('.stat-value').textContent, '35%');
  });

  // SPEC.md §16 and the 0.4.1 decision: the surplus figure no longer carries a
  // confidence grade. The one level that meant something became this sentence,
  // which names the cause and the fix instead of grading the customer's data.
  it('counts the running appliances without listing them', async () => {
    // A count is a fact about the home; the appliances live on Apparaten.
    const panel = await mountPanel(
      fakeHass({
        coach: sampleCoach({
          metrics: { device_power_w: { d1: 1150, d2: 3 }, running_device_count: 1 },
        }),
      }),
    );

    const rows = [...panel.shadowRoot.querySelectorAll('.stat-row')];
    const running = rows.find((node) =>
      node.querySelector('.stat-label').textContent.includes('nu draaien'),
    );

    assert.ok(running, 'expected a running-appliances row');
    assert.equal(running.querySelector('.stat-value').textContent, '1');
  });

  it('drops the running count when nothing links a power entity', async () => {
    // "0 draaien" would claim a measurement of every appliance in the house,
    // and a permanently empty row reports a shortcoming that does not exist:
    // nobody linked a power sensor, so there is nothing here this home could
    // ever show (SPEC.md §39.3).
    const panel = await mountPanel(
      fakeHass({ coach: sampleCoach({ metrics: { device_power_w: {} } }) }),
    );

    const running = [...panel.shadowRoot.querySelectorAll('.stat-row')].find((node) =>
      node.querySelector('.stat-label').textContent.includes('nu draaien'),
    );

    assert.ok(!isVisible(running));
  });

  it('keeps every tap target at 44 px, at a phone-sized panel width', async () => {
    // Measured rather than assumed, and at the width the container query
    // actually keys on: with the Home Assistant sidebar open on a tablet the
    // screen is roomy while the panel is not (SPEC.md §39.5).
    const panel = await mountPanel();

    const small = [...panel.shadowRoot.querySelectorAll('button')]
      .map((node) => node.className)
      .filter((name) => name.includes('button') || name.includes('toggle'));

    // jsdom does not lay out, so the guard here is the declaration: every
    // interactive class carries its own min-height in the stylesheet. The
    // measurement is the browser check; this keeps the rule from being
    // deleted by accident.
    const styles = panel.shadowRoot.querySelector('style').textContent;
    for (const selector of ['.tab-button', '.button', '.section-toggle']) {
      const block = styles.split(`${selector} {`)[1].split('}')[0];
      assert.match(block, /min-height: 44px/, `${selector} lost its tap target`);
    }
    assert.ok(small.length > 0);
  });

  it('drops the solar rows from a home without panels', async () => {
    // Three lines about equipment the installer already said is not there:
    // "Zonneproductie — Nog niet ingesteld", and two more reading "Niet
    // beschikbaar". A shortcoming nobody can close (SPEC.md §39.3).
    const panel = await mountPanel(
      fakeHass({
        config: sampleConfig({
          sources: [{ id: 'grid', name: 'Netmeter', type: 'grid_meter', enabled: true }],
        }),
      }),
    );

    const labels = [...panel.shadowRoot.querySelectorAll('.stat-row')]
      .filter(isVisible)
      .map((node) => node.querySelector('.stat-label').textContent);

    assert.ok(!labels.includes('Zonneproductie'));
    assert.ok(!labels.includes('Zonneoverschot'));
    assert.ok(!labels.includes('Zelfbenutting'));
    // The rows about the connection stay: those are unconditional, and an
    // empty one there is a fault worth seeing.
    assert.ok(labels.includes('Netvermogen'));
  });

  it('keeps them for a home that has panels but no reading right now', async () => {
    // The other half of the rule, and the reason existence follows the
    // configuration rather than the value: hide a row because it is empty at
    // this moment and an unreadable inverter disappears with it.
    const panel = await mountPanel(
      fakeHass({
        config: sampleConfig({
          sources: [
            { id: 'grid', name: 'Netmeter', type: 'grid_meter', enabled: true },
            { id: 'pv', name: 'Omvormer', type: 'solar', enabled: true },
          ],
        }),
        coach: sampleCoach({ metrics: { solar_power_w: null, solar_surplus_w: null } }),
      }),
    );

    const rows = [...panel.shadowRoot.querySelectorAll('.stat-row')].filter(isVisible);
    const labels = rows.map((node) => node.querySelector('.stat-label').textContent);

    assert.ok(labels.includes('Zonneproductie'));
    assert.ok(labels.includes('Zonneoverschot'));
  });

  it('shows the home consumption once, as the headline and not as a row', async () => {
    // It was the first row of Actuele situatie (SPEC.md §36.5) and became the
    // headline figure in §35.8b. Moved, not repeated: the same number twice on
    // one screen invites the question which of the two is the real one.
    const panel = await mountPanel(
      fakeHass({ coach: sampleCoach({ metrics: { home_consumption_w: 600 } }) }),
    );

    const labels = [...panel.shadowRoot.querySelectorAll('.stat-row .stat-label')]
      .map((node) => node.textContent);

    assert.equal(labels.indexOf('Thuisverbruik'), -1);
    assert.ok(headline(panel, 'Thuisverbruik'), 'expected a Thuisverbruik figure');
  });

  it('explains an unreadable inverter instead of leaving the row blank', async () => {
    const panel = await mountPanel(
      fakeHass({
        coach: sampleCoach({
          metrics: {
            home_consumption_w: null,
            home_consumption_unavailable_reason: 'solar_unreadable',
          },
        }),
      }),
    );

    const texts = [...panel.shadowRoot.querySelectorAll('.notice')]
      .filter(isVisible)
      .map((node) => node.querySelector('.notice-text').textContent);

    assert.ok(texts.some((text) => text.includes('omvormer')));
  });

  it('says nothing extra when the grid reading is what is missing', async () => {
    // The checklist already reports the grid source; a second line about it
    // would say the same thing twice on one card.
    const panel = await mountPanel(
      fakeHass({
        coach: sampleCoach({
          metrics: {
            home_consumption_w: null,
            home_consumption_unavailable_reason: 'no_grid_reading',
          },
        }),
      }),
    );

    const texts = [...panel.shadowRoot.querySelectorAll('.notice')]
      .filter(isVisible)
      .map((node) => node.querySelector('.notice-text').textContent);

    assert.ok(!texts.some((text) => text.includes('omvormer')));
    assert.ok(!texts.some((text) => text.includes('thuisbatterij')));
  });

  it('uses one battery sentence for both figures it touches', async () => {
    // Two near-identical warnings on one card is worse than one naming both
    // (SPEC.md §36.6).
    const panel = await mountPanel(
      fakeHass({
        coach: sampleCoach({
          metrics: {
            home_consumption_w: null,
            home_consumption_unavailable_reason: 'battery_unreadable',
            solar_surplus_may_be_overstated: true,
          },
        }),
      }),
    );

    const texts = [...panel.shadowRoot.querySelectorAll('.notice')]
      .filter(isVisible)
      .map((node) => node.querySelector('.notice-text').textContent);
    const battery = texts.filter((text) => text.includes('thuisbatterij'));

    assert.equal(battery.length, 1);
    assert.match(battery[0], /thuisverbruik is niet te berekenen/);
    assert.match(battery[0], /zonneoverschot kan te hoog zijn/);
  });

  it('warns that an unreadable battery may inflate the surplus', async () => {
    const panel = await mountPanel(
      fakeHass({
        coach: sampleCoach({
          metrics: { solar_surplus_w: 1900, solar_surplus_may_be_overstated: true },
        }),
      }),
    );

    const texts = [...panel.shadowRoot.querySelectorAll('.notice')]
      .filter(isVisible)
      .map((node) => node.querySelector('.notice-text').textContent);
    const sentence = texts.find((text) => text.includes('thuisbatterij'));

    assert.ok(sentence, 'expected the unreadable-battery sentence');
    assert.match(sentence, /Koppel de vermogenssensor/);
  });

  it('says nothing about the battery when the surplus is sound', async () => {
    const panel = await mountPanel(
      fakeHass({
        coach: sampleCoach({
          metrics: { solar_surplus_w: 1900, solar_surplus_may_be_overstated: false },
        }),
      }),
    );

    const texts = [...panel.shadowRoot.querySelectorAll('.notice')]
      .filter(isVisible)
      .map((node) => node.querySelector('.notice-text').textContent);

    assert.ok(!texts.some((text) => text.includes('thuisbatterij')));
  });

  it('never grades the surplus with a confidence level', async () => {
    const panel = await mountPanel();

    assert.doesNotMatch(panel.shadowRoot.textContent, /etrouwbaarheid/);
  });

  it('says nothing about a missing score when there is one', async () => {
    const panel = await mountPanel(
      fakeHass({
        coach: sampleCoach({
          metrics: { energy_score: 46, score_unavailable_reason: null },
        }),
      }),
    );

    const texts = [...panel.shadowRoot.querySelectorAll('.notice')]
      .filter(isVisible)
      .map((node) => node.querySelector('.notice-text').textContent);

    assert.ok(!texts.some((text) => text.includes('Geen cijfer')));
    assert.ok(!texts.some((text) => text.includes('niets te verbeteren')));
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
