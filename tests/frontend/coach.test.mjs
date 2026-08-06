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
  it('shows what the backend said, with its reason and confidence', async () => {
    const { tab } = await openCoachTab();

    assert.match(tab.textContent, /Aanvullende gegevens nodig/);
    assert.match(tab.textContent, /Vul de ontbrekende energiegegevens aan/);
    assert.equal(rowFor(tab, 'Reden').value, 'missing_required_data');
    assert.equal(rowFor(tab, 'Betrouwbaarheid').value, 'hoog');
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
    assert.equal(rowFor(tab, 'Betrouwbaarheid').visible, true);
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

  it('hides the confidence when the customer does not want it', async () => {
    const hass = fakeHass({
      config: sampleConfig({
        preferences: { max_advice_count: 3, show_confidence: false },
      }),
      coach: answeredCoach(),
    });
    const { tab } = await openCoachTab(hass);

    assert.equal(rowFor(tab, 'Betrouwbaarheid').visible, false);
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
    // Measurement, saving and confidence, in readable Dutch.
    assert.match(rows[0].textContent, /zonneoverschot in W: 1500/);
    assert.match(rows[0].textContent, /geschatte besparing € 0,36/);
    assert.match(rows[0].textContent, /betrouwbaarheid gemiddeld/);
  });

  it('says so when there is nothing further to advise', async () => {
    const { tab } = await openCoachTab();

    assert.match(tab.querySelector('.empty-text').textContent, /geen aanvullend advies/);
  });
});

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

  it('answers only with what the backend produced', async () => {
    const { tab } = await openCoachTab();

    assert.match(tab.textContent, /Omdat de netbelasting hoog is/);

    buttonIn(tab, 'Is er risico op piekbelasting?').click();
    await settle();

    assert.match(tab.textContent, /De woning gebruikt 87% van het maximum/);
    assert.ok(!tab.textContent.includes('Omdat de netbelasting hoog is'));
  });

  it('marks the selected question for a screen reader as well', async () => {
    const { tab } = await openCoachTab();

    buttonIn(tab, 'Welke gegevens ontbreken nog?').click();
    await settle();

    const pressed = [...tab.querySelectorAll('.question-bar button')]
      .filter((node) => node.getAttribute('aria-pressed') === 'true')
      .map((node) => node.textContent.trim());
    // Never colour alone: the state is in the attribute too (SPEC.md §23).
    assert.deepEqual(pressed, ['Welke gegevens ontbreken nog?']);
  });

  it('reports an unanswered question as unanswered, never invents one', async () => {
    const { tab } = await openCoachTab(
      fakeHass({ coach: sampleCoach({ explanations: {} }) }),
    );

    // The frontend draws no conclusions of its own (SPEC.md §8 and §17).
    assert.ok(noticeTexts(tab).some((t) => t.includes('nog niet beantwoord')));
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
