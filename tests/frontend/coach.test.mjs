/**
 * Tests for the Energiecoach tab (SPEC.md §8 "Energiecoach", §17 and §23).
 *
 * The promise this tab makes is narrower than it looks: it shows what the
 * backend produced and nothing else. So these tests are mostly about restraint
 * — an unanswered question stays unanswered, a saving that could not be
 * calculated is not rendered as zero, and the three display preferences are
 * obeyed rather than treated as suggestions.
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

/** A coach result with every question answered. */
function answeredCoach(overrides = {}) {
  return sampleCoach({
    explanations: {
      why_advice: 'Omdat de netbelasting hoog is.',
      use_device_now: 'Nu is geen gunstig moment.',
      peak_risk: 'Ja. De woning gebruikt 87% van het maximum.',
      missing_data: 'Nog ontbrekend: een geldige zonnebron.',
      score_breakdown: 'De score is 46, opgebouwd uit: datakwaliteit 60.',
    },
    missing_data: ['solar_source_valid'],
    ...overrides,
  });
}

async function openCoachTab(hass = fakeHass({ coach: answeredCoach() })) {
  const panel = await mountPanel(hass);
  clickTab(panel, 'Energiecoach');
  await settle();
  const tab = tabPanels(panel).find((node) => node.id === 'panel-coach');
  return { panel, tab, hass };
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

function rowFor(tab, label) {
  const row = [...tab.querySelectorAll('.stat-row')].find((node) =>
    node.querySelector('.stat-label').textContent.includes(label),
  );
  return row
    ? { value: row.querySelector('.stat-value').textContent, visible: isVisible(row) }
    : null;
}

describe('the primary advice', () => {
  it('shows what the backend said, with its reason', async () => {
    const { tab } = await openCoachTab();

    assert.match(visibleText(tab), /Aanvullende gegevens nodig/);
    assert.match(visibleText(tab), /Vul de ontbrekende energiegegevens aan/);
    // The reason is a machine identifier, and this row used to print it: a
    // customer read "missing_required_data" where a sentence belonged.
    assert.equal(rowFor(tab, 'Reden').value, 'Er ontbreken gegevens');
    // No confidence row since 0.4.1: it graded the customer's own data on an
    // axis he could not act on. See the notice on the Overzicht for the one
    // case that carried information.
    assert.equal(rowFor(tab, 'Betrouwbaarheid'), null);
  });

  it('never shows a raw code, whatever the backend sends', async () => {
    const coach = answeredCoach();
    coach.primary_advice = {
      ...coach.primary_advice,
      reason_code: 'some_future_code',
      confidence: 'extremely_high',
      measurements: { unknown_reading: 42 },
    };
    coach.advice = [coach.primary_advice];
    coach.missing_data = ['a_new_checklist_item'];
    const { tab } = await openCoachTab(fakeHass({ coach }));

    // Every one of these is an identifier the panel has no words for. A missing
    // line is a gap; a raw code is a defect the customer can see.
    assert.doesNotMatch(tab.textContent, /some_future_code/);
    assert.doesNotMatch(tab.textContent, /extremely_high/);
    assert.doesNotMatch(tab.textContent, /unknown_reading/);
    assert.doesNotMatch(tab.textContent, /a_new_checklist_item/);
    assert.equal(rowFor(tab, 'Reden').visible, false);
  });
});

/** The surplus advice: the only kind that ever carries an amount. */
function surplusAdvice(overrides = {}) {
  return {
    id: 'solar_surplus_available',
    title: 'Zonneoverschot beschikbaar',
    message: 'Dit is een gunstig moment om Vaatwasser te gebruiken.',
    severity: 'info',
    reason_code: 'solar_surplus_available',
    confidence: 'high',
    ...overrides,
  };
}

/**
 * Which amount belongs under the primary advice, per situation.
 *
 * **Written from the situation and not from the branch** (CLAUDE.md, the sixth
 * variant). Asking "which state gets me this row on screen" would have
 * confirmed the defect these tests exist for: the row read "Niet te berekenen"
 * under advice that has no amount to begin with, and every earlier test agreed
 * with it because the sample advice happened to be exactly that case.
 *
 * One row per situation, with the verdict beside it. `null` means the row may
 * not be on the screen at all — there is nothing to say, and "Niet te
 * berekenen" says something: that a sum was attempted and failed.
 */
describe('the amount under the primary advice', () => {
  const situations = [
    {
      name: 'a surplus whose saving was calculated: the amount',
      advice: surplusAdvice({ estimated_savings_eur: 0.34 }),
      saving: /0,34/,
      rate: null,
    },
    {
      name: 'a surplus that earns nothing extra: zero is an answer',
      // Under net metering this is the normal case (SPEC.md §16).
      advice: surplusAdvice({ estimated_savings_eur: 0 }),
      saving: /0,00/,
      rate: null,
    },
    {
      name: 'a surplus that currently costs money: the negative amount',
      advice: surplusAdvice({ estimated_savings_eur: -0.05 }),
      saving: /0,05/,
      rate: null,
    },
    {
      name: 'a modulating appliance: a rate per hour, and no total',
      // The total is empty on purpose — there is no cycle to price — and the
      // rate is the answer (SPEC.md §56.4). This card used to show neither.
      advice: surplusAdvice({
        estimated_savings_eur: null,
        savings_rate_eur_per_hour: 0.12,
      }),
      saving: null,
      rate: /0,12/,
    },
    {
      name: 'a surplus whose sum could not be made: nothing, the message says why',
      advice: surplusAdvice({
        message:
          'Hoeveel dit oplevert is niet te berekenen zonder de energie per ' +
          'cyclus van Vaatwasser — vul die in bij Apparaten.',
      }),
      saving: null,
      rate: null,
    },
    {
      name: 'nothing to change, so nothing to save: no amount at all',
      advice: {
        id: 'neutral_energy_situation',
        title: 'Geen actie nodig',
        message: 'De actuele energiesituatie vraagt niet om een aanpassing.',
        severity: 'info',
        reason_code: 'neutral_energy_situation',
        confidence: 'medium',
      },
      saving: null,
      rate: null,
    },
    {
      name: 'a warning about peak load: no amount either',
      advice: {
        id: 'high_grid_load',
        title: 'Hoge netbelasting',
        message: 'Stel zwaar verbruik uit tot de belasting daalt.',
        severity: 'warning',
        reason_code: 'high_grid_load',
        confidence: 'high',
      },
      saving: null,
      rate: null,
    },
  ];

  for (const situation of situations) {
    it(situation.name, async () => {
      const coach = answeredCoach({ primary_advice: situation.advice });
      coach.advice = [situation.advice];
      const { tab } = await openCoachTab(fakeHass({ coach }));

      for (const [label, expected] of [
        ['Geschatte besparing', situation.saving],
        ['Geschatte opbrengst per uur', situation.rate],
      ]) {
        const row = rowFor(tab, label);
        if (expected === null) {
          assert.equal(row.visible, false, `${label} may not be on screen here`);
        } else {
          assert.equal(row.visible, true, `${label} belongs on screen here`);
          assert.match(row.value, expected);
        }
      }
      // Whatever the situation, no reading the customer can see reports a sum
      // that failed. The phrase is guarded literally so it cannot come back as
      // an empty text on either row.
      const visibleValues = [...tab.querySelectorAll('.stat-row')]
        .filter(isVisible)
        .map((node) => node.querySelector('.stat-value').textContent);
      assert.ok(!visibleValues.some((text) => text.includes('Niet te berekenen')));
    });
  }
});

describe('the display preferences', () => {
  /**
   * The preference, over both shapes an amount can take.
   *
   * **Each case uses advice that actually carries the figure it is hiding.**
   * The earlier version of this test used the sample advice, which has no
   * amount at all — so it passed whatever the preference did, and would have
   * gone on passing if the preference had stopped working entirely (CLAUDE.md,
   * a fixture that codifies the behaviour that happens to be there).
   *
   * The two never occur together: a total is empty exactly when the appliance
   * modulates, and the rate exists only then (SPEC.md §56.4).
   */
  for (const [label, advice] of [
    ['Geschatte besparing', surplusAdvice({ estimated_savings_eur: 0.34 })],
    [
      'Geschatte opbrengst per uur',
      surplusAdvice({
        estimated_savings_eur: null,
        savings_rate_eur_per_hour: 0.12,
      }),
    ],
  ]) {
    it(`shows "${label}" only when the customer wants amounts`, async () => {
      const coach = answeredCoach({ primary_advice: advice });

      const shown = await openCoachTab(fakeHass({ coach }));
      assert.equal(rowFor(shown.tab, label).visible, true);

      const hidden = await openCoachTab(
        fakeHass({
          config: sampleConfig({
            preferences: { max_advice_count: 3, show_estimated_savings: false },
          }),
          coach: answeredCoach({ primary_advice: advice }),
        }),
      );
      assert.equal(rowFor(hidden.tab, label).visible, false);
      // The neighbouring rows are unaffected by this one preference.
      assert.equal(rowFor(hidden.tab, 'Reden').visible, true);
    });
  }

  it('hides the technical reason when the customer does not want it', async () => {
    const hass = fakeHass({
      config: sampleConfig({
        preferences: { max_advice_count: 3, show_technical_explanation: false },
      }),
      coach: answeredCoach(),
    });
    const { tab } = await openCoachTab(hass);

    assert.equal(rowFor(tab, 'Reden').visible, false);
  });

  it('never shows a confidence row at all', async () => {
    // The preference that used to switch this went with the label (0.4.1), so
    // the row may not come back for any configuration.
    const { tab } = await openCoachTab();

    assert.equal(rowFor(tab, 'Betrouwbaarheid'), null);
    assert.doesNotMatch(tab.textContent, /etrouwbaarheid/);
  });
});

describe('the further advice', () => {
  it('lists everything after the primary one, without repeating it', async () => {
    const coach = answeredCoach();
    coach.advice = [
      coach.primary_advice,
      {
        id: 'solar_surplus_available',
        title: 'Zonneoverschot beschikbaar',
        message: 'Dit is een gunstig moment om Vaatwasser te gebruiken.',
        severity: 'info',
        reason_code: 'solar_surplus_available',
        confidence: 'medium',
        estimated_savings_eur: 0.36,
        measurements: { zonneoverschot_w: 1500 },
      },
    ];
    const { tab } = await openCoachTab(fakeHass({ coach }));

    const rows = [...tab.querySelectorAll('.row-item')];
    assert.equal(rows.length, 1);
    assert.match(visibleText(rows[0]), /Zonneoverschot beschikbaar/);
    // Measurement and saving, in readable Dutch.
    assert.match(visibleText(rows[0]), /zonneoverschot in W: 1\.500/);
    assert.match(visibleText(rows[0]), /geschatte besparing € 0,36/);
    assert.doesNotMatch(rows[0].textContent, /etrouwbaarheid/);
  });

  it('says so when there is nothing further to advise', async () => {
    const { tab } = await openCoachTab();

    assert.match(tab.querySelector('.empty-text').textContent, /geen aanvullend advies/);
  });
});

/** The dialog the coach answers in, whatever else is on screen. */
function answerDialog(panel) {
  return [...panel.shadowRoot.querySelectorAll('.dialog')].at(-1);
}

describe('the question selector', () => {
  it('offers the five fixed questions from SPEC.md §8', async () => {
    const { tab } = await openCoachTab();

    const labels = [...tab.querySelectorAll('.question-bar button')].map((node) =>
      node.textContent.trim(),
    );

    assert.deepEqual(labels, [
      'Waarom krijg ik dit advies?',
      'Kan ik nu het beste een apparaat gebruiken?',
      'Is er risico op piekbelasting?',
      'Welke gegevens ontbreken nog?',
      'Hoe is mijn energiescore berekend?',
    ]);
  });

  it('opens the answer in a dialog, with the question as its heading', async () => {
    // Inline, the answer landed below whatever had been read last and had to be
    // hunted for; on a phone it was off-screen entirely.
    const { panel, tab } = await openCoachTab();

    assert.equal(isVisible(answerDialog(panel)), false);

    buttonIn(tab, 'Is er risico op piekbelasting?').click();
    await settle();

    const dialog = answerDialog(panel);
    assert.equal(isVisible(dialog), true);
    assert.equal(
      dialog.querySelector('.dialog-title').textContent,
      'Is er risico op piekbelasting?',
    );
    assert.match(visibleText(dialog), /De woning gebruikt 87% van het maximum/);
  });

  it('answers only with what the backend produced', async () => {
    const { panel, tab } = await openCoachTab();

    buttonIn(tab, 'Waarom krijg ik dit advies?').click();
    await settle();
    assert.match(visibleText(answerDialog(panel)), /Omdat de netbelasting hoog is/);

    answerDialog(panel).querySelector('.dialog-close').click();
    buttonIn(tab, 'Is er risico op piekbelasting?').click();
    await settle();

    const dialog = answerDialog(panel);
    assert.match(visibleText(dialog), /De woning gebruikt 87% van het maximum/);
    assert.ok(!dialog.textContent.includes('Omdat de netbelasting hoog is'));
  });

  it('closes without asking, because there is nothing to lose', async () => {
    const { panel, tab } = await openCoachTab();

    buttonIn(tab, 'Waarom krijg ik dit advies?').click();
    await settle();

    // No input, so no confirmation on the way out: the backdrop just closes it.
    answerDialog(panel).querySelector('.dialog-scrim').click();
    await settle();

    assert.equal(isVisible(answerDialog(panel)), false);
  });

  it('reports an unanswered question as unanswered, never invents one', async () => {
    const { panel, tab } = await openCoachTab(
      fakeHass({ coach: sampleCoach({ explanations: {} }) }),
    );

    buttonIn(tab, 'Waarom krijg ik dit advies?').click();
    await settle();

    // The frontend draws no conclusions of its own (SPEC.md §8 and §17).
    assert.match(visibleText(answerDialog(panel)), /nog niet beantwoord/);
  });
});

describe('missing data and recalculating', () => {
  it('names what is still missing in Dutch, not as a key', async () => {
    const { tab } = await openCoachTab();

    const items = [...tab.querySelectorAll('.plain-item')].map((n) => n.textContent);
    assert.deepEqual(items, ['een geldige zonnebron']);
  });

  it('says so when nothing is missing', async () => {
    const { tab } = await openCoachTab(
      fakeHass({ coach: answeredCoach({ missing_data: [] }) }),
    );

    assert.ok(noticeTexts(tab).some((t) => t.includes('zijn ingevuld')));
  });

  it('does not promise a shortfall in the heading and then deny it', async () => {
    // For a home where nothing is missing, "Ontbrekende gegevens" was the last
    // heading on the screen still pointing at a gap — above the sentence that
    // says there is none (SPEC.md §58.2).
    const { tab } = await openCoachTab(
      fakeHass({ coach: answeredCoach({ missing_data: [] }) }),
    );

    const headings = [...tab.querySelectorAll('.card-title')].map((n) => n.textContent);
    assert.ok(headings.includes('Gegevens voor je advies'));
    assert.ok(!headings.some((text) => text.toLowerCase().includes('ontbrekende')));
  });

  it('introduces the list, so a neutral heading leaves no bare nouns', async () => {
    // The framing moved from the chrome into the state: it is said only when
    // there is a list under it, in the words the coach itself uses.
    const { tab } = await openCoachTab();

    const lead = [...tab.querySelectorAll('.advice-message')]
      .filter(isVisible)
      .map((node) => node.textContent);
    assert.ok(lead.includes('Nog ontbrekend:'));
  });

  it('drops the lead line together with the list', async () => {
    const { tab } = await openCoachTab(
      fakeHass({ coach: answeredCoach({ missing_data: [] }) }),
    );

    const lead = [...tab.querySelectorAll('.advice-message')]
      .filter(isVisible)
      .map((node) => node.textContent);
    assert.ok(!lead.includes('Nog ontbrekend:'));
  });

  it('recalculates on request and shows the fresh result', async () => {
    const hass = fakeHass({ coach: answeredCoach() });
    const original = hass.callWS;
    hass.callWS = async (message) => {
      if (message.type === 'domotiapp_energy/coach/recalculate') {
        return answeredCoach({
          primary_advice: {
            id: 'neutral_energy_situation',
            title: 'Geen actie nodig',
            message: 'De actuele energiesituatie vraagt niet om een aanpassing.',
            severity: 'info',
            reason_code: 'neutral_energy_situation',
            confidence: 'medium',
          },
        });
      }
      return original(message);
    };
    const { tab } = await openCoachTab(hass);

    buttonIn(tab, 'Opnieuw berekenen').click();
    await settle();

    assert.match(visibleText(tab), /Geen actie nodig/);
    assert.ok(noticeTexts(tab).some((t) => t.includes('opnieuw berekend')));
  });

  it('shows a refusal in Dutch instead of a stale claim of success', async () => {
    const hass = fakeHass({ coach: answeredCoach() });
    const original = hass.callWS;
    hass.callWS = async (message) => {
      if (message.type === 'domotiapp_energy/coach/recalculate') {
        throw { code: 'not_found', message: 'not loaded' };
      }
      return original(message);
    };
    const { tab } = await openCoachTab(hass);

    buttonIn(tab, 'Opnieuw berekenen').click();
    await settle();

    assert.ok(noticeTexts(tab).some((t) => t.includes('niet geladen')));
  });
});

describe('measurements as a customer reads them', () => {
  it('does not put a six-decimal calculation in a sentence', async () => {
    const coach = answeredCoach();
    coach.advice = [
      coach.primary_advice,
      {
        id: 'low_energy_price',
        title: 'Lage energieprijs',
        message: 'De actuele energieprijs is relatief laag.',
        severity: 'info',
        reason_code: 'low_energy_price',
        confidence: 'high',
        // What the backend stores: normalised to six decimals so no precision
        // is lost on the way (SPEC.md §16).
        measurements: { prijs_eur_kwh: 0.095348, netvermogen_w: 1234.5 },
      },
    ];
    const { tab } = await openCoachTab(fakeHass({ coach }));

    const text = [...tab.querySelectorAll('.row-item')][0].textContent;
    assert.match(text, /all-in prijs in €\/kWh: 0,095/);
    assert.ok(!text.includes('0.095348'));
    // Watts to the tenth are noise as well.
    assert.match(text, /netvermogen in W: 1\.235/);
  });
});

describe('a checklist item this home cannot answer', () => {
  it('names what is not counted, so a short checklist is not a silent one', async () => {
    // A home with no appliances is judged on four items, not six. Without this
    // sentence the checklist would appear to have quietly skipped something,
    // and the customer cannot see the source rows that decided it
    // (round B, finding 6).
    const coach = answeredCoach({
      missing_data: [],
      metrics: {
        ...sampleCoach().metrics,
        data_quality: {
          score: 100,
          completed_items: [
            'home_profile_complete',
            'grid_source_valid',
            'solar_source_valid',
            'price_information_available',
          ],
          missing_items: [],
          not_applicable_items: [
            'device_profile_complete',
            'flexible_devices_have_time_window',
          ],
        },
      },
    });
    const { tab } = await openCoachTab(fakeHass({ coach }));

    const notices = noticeTexts(tab);
    assert.ok(
      notices.some((t) => t.includes('Niet van toepassing op deze woning')),
      'the items that were skipped have to be named',
    );
    assert.ok(
      notices.some((t) => t.includes('een compleet apparaatprofiel')),
      'and named in Dutch, never as a checklist key',
    );
  });

  it('says nothing extra when every item applies', async () => {
    const coach = answeredCoach({
      missing_data: [],
      metrics: {
        ...sampleCoach().metrics,
        data_quality: {
          score: 100,
          completed_items: ['home_profile_complete'],
          missing_items: [],
          not_applicable_items: [],
        },
      },
    });
    const { tab } = await openCoachTab(fakeHass({ coach }));

    assert.ok(!noticeTexts(tab).some((t) => t.includes('Niet van toepassing')));
  });
});
