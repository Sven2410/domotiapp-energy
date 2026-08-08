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

    assert.match(tab.textContent, /Aanvullende gegevens nodig/);
    assert.match(tab.textContent, /Vul de ontbrekende energiegegevens aan/);
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

  it('says a saving could not be calculated instead of showing zero', async () => {
    const { tab } = await openCoachTab();

    // "No saving" and "a saving of nothing" are different statements, and only
    // one of them is true here (SPEC.md §16).
    assert.equal(rowFor(tab, 'Geschatte besparing').value, 'Niet te berekenen');
  });

  it('shows a calculated saving of zero as zero', async () => {
    const coach = answeredCoach();
    coach.primary_advice = { ...coach.primary_advice, estimated_savings_eur: 0 };
    const { tab } = await openCoachTab(fakeHass({ coach }));

    // Under net metering this is the normal case, and it is an answer.
    assert.match(rowFor(tab, 'Geschatte besparing').value, /0,00/);
  });
});

describe('the display preferences', () => {
  it('hides the saving when the customer does not want it', async () => {
    const hass = fakeHass({
      config: sampleConfig({
        preferences: { max_advice_count: 3, show_estimated_savings: false },
      }),
      coach: answeredCoach(),
    });
    const { tab } = await openCoachTab(hass);

    assert.equal(rowFor(tab, 'Geschatte besparing').visible, false);
    // The neighbouring rows are unaffected by this one preference.
    assert.equal(rowFor(tab, 'Reden').visible, true);
  });

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
    assert.match(rows[0].textContent, /Zonneoverschot beschikbaar/);
    // Measurement and saving, in readable Dutch.
    assert.match(rows[0].textContent, /zonneoverschot in W: 1\.500/);
    assert.match(rows[0].textContent, /geschatte besparing € 0,36/);
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
    assert.match(dialog.textContent, /De woning gebruikt 87% van het maximum/);
  });

  it('answers only with what the backend produced', async () => {
    const { panel, tab } = await openCoachTab();

    buttonIn(tab, 'Waarom krijg ik dit advies?').click();
    await settle();
    assert.match(answerDialog(panel).textContent, /Omdat de netbelasting hoog is/);

    answerDialog(panel).querySelector('.dialog-close').click();
    buttonIn(tab, 'Is er risico op piekbelasting?').click();
    await settle();

    const dialog = answerDialog(panel);
    assert.match(dialog.textContent, /De woning gebruikt 87% van het maximum/);
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
    assert.match(answerDialog(panel).textContent, /nog niet beantwoord/);
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

    assert.match(tab.textContent, /Geen actie nodig/);
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
