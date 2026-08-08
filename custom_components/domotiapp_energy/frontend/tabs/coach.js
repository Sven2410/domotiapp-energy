/**
 * The Energiecoach tab (SPEC.md §8 "Energiecoach", §17 and §23).
 *
 * The one tab the customer reads rather than fills in. It shows the current
 * situation, the primary advice, up to five further ones with their reason and
 * measurements, what is still missing, and a button to recalculate now.
 *
 * **The frontend draws no conclusions.** Every sentence here comes from the
 * backend: the advice texts from the advisor, the answers to the five fixed
 * questions from `CoachResult.explanations`, which the coach provider filled
 * (SPEC.md §8 and §17). There is no free chat and no reasoning of our own —
 * this file arranges text, it does not produce it.
 *
 * Two preferences decide how much of it is shown at all
 * (`show_technical_explanation`, `show_estimated_savings`), so a customer who
 * does not want the machinery does not get it.
 */

import { createApi, describeError } from '../core/api.js';
import { createDialog } from '../core/dialog.js';
import {
  adviceBlock,
  button,
  card,
  el,
  formatNumber,
  formatTimestamp,
  notice,
  setVisible,
  statRow,
} from '../core/dom.js';
import {
  checklistLabel,
  measurementLabel,
  reasonLabel,
} from '../core/labels.js';
import { createRowList } from '../core/rows.js';
import { onTap } from '../core/tap.js';

/** The five questions of SPEC.md §8, in the order they are listed there. */
const QUESTIONS = [
  { key: 'why_advice', label: 'Waarom krijg ik dit advies?' },
  { key: 'use_device_now', label: 'Kan ik nu het beste een apparaat gebruiken?' },
  { key: 'peak_risk', label: 'Is er risico op piekbelasting?' },
  { key: 'missing_data', label: 'Welke gegevens ontbreken nog?' },
  { key: 'score_breakdown', label: 'Hoe is mijn energiescore berekend?' },
];

const SEVERITY_MARKERS = {
  info: 'Advies',
  success: 'Advies',
  warning: 'Waarschuwing',
  error: 'Probleem',
};

/**
 * How many decimals a measurement is worth showing.
 *
 * The backend keeps a normalised price to six decimals so a conversion never
 * loses precision (SPEC.md §16). Six decimals with a dot for a separator is a
 * calculation, not a price, and it has no business in a sentence a customer
 * reads.
 */
const MEASUREMENT_DECIMALS = {
  prijs_eur_kwh: 3,
  netbelasting_procent: 1,
  netvermogen_w: 0,
  zonneoverschot_w: 0,
  ontbrekende_onderdelen: 0,
};

function measurementValue(key, value) {
  if (typeof value !== 'number') {
    return value;
  }
  return formatNumber(value, { decimals: MEASUREMENT_DECIMALS[key] ?? 2 });
}

export const coachTab = {
  id: 'coach',
  label: 'Energiecoach',
  icon: 'mdi:lightbulb-on-outline',

  create({ getHass, state, overlay }) {
    const element = el('div', { class: 'tab-content' });

    // --- The primary advice --------------------------------------------------
    const mainCard = card('Hoofdadvies');
    const adviceTitle = el('p', { class: 'advice-title' });
    const adviceMessage = el('p', { class: 'advice-message' });
    const savingRow = statRow('Geschatte besparing', { empty: 'Niet te berekenen' });
    const reasonRow = statRow('Reden', { empty: 'Onbekend' });
    const calculatedRow = statRow('Laatste berekening', { empty: 'Nog niet berekend' });

    const recalculateButton = button('Opnieuw berekenen', { primary: true });
    const recalculateNotice = notice('mdi:refresh');

    mainCard.body.append(
      adviceTitle,
      adviceMessage,
      savingRow.element,
      reasonRow.element,
      calculatedRow.element,
      el('div', { class: 'actions' }, [recalculateButton]),
      recalculateNotice.element,
    );

    // --- The further advice --------------------------------------------------
    const listCard = card('Overige adviezen');
    const adviceList = createRowList({
      emptyText: 'Er is op dit moment geen aanvullend advies.',
      createRow: () => createAdviceRow(),
    });
    listCard.body.appendChild(adviceList.element);

    // --- What is still missing ----------------------------------------------
    const missingCard = card('Ontbrekende gegevens');
    const missingList = el('ul', { class: 'plain-list' });
    const missingNotice = notice('mdi:check-circle-outline');
    missingCard.body.append(missingList, missingNotice.element);

    // --- The question selector ----------------------------------------------
    const questionCard = card('Vraag het de coach');
    const questionBar = el('div', { class: 'question-bar' });
    const questionIntro = el('p', {
      class: 'advice-message',
      text: 'Kies een vraag; het antwoord verschijnt in beeld.',
    });

    /**
     * The answer opens in a dialog rather than under the buttons.
     *
     * Inline, the answer landed somewhere below whatever had been read last and
     * had to be hunted for; on a phone it was off-screen entirely. A dialog
     * gives it the attention it is for, and puts the question above it as the
     * heading so the pair can be read as one thing.
     *
     * It holds no input, so there is nothing to confirm on the way out: the
     * backdrop, Escape and the close button simply close it (SPEC.md §22).
     */
    const answerDialog = createDialog({ title: '', overlay });
    const answerText = el('p', { class: 'dialog-message' });
    answerDialog.body.appendChild(answerText);

    for (const question of QUESTIONS) {
      const node = button(question.label);
      onTap(node, () => showAnswer(question, node));
      questionBar.appendChild(node);
    }
    questionCard.body.append(questionIntro, questionBar);

    element.append(
      mainCard.element,
      listCard.element,
      missingCard.element,
      questionCard.element,
    );

    function createAdviceRow() {
      const title = el('p', { class: 'row-name' });
      const marker = el('span', { class: 'label' });
      const message = el('p', { class: 'row-meta' });
      const details = el('p', { class: 'row-meta' });

      const row = el('div', { class: 'row-item' }, [
        el('div', { class: 'row-main' }, [marker, title, message, details]),
      ]);

      return {
        element: row,
        update(item) {
          marker.textContent = SEVERITY_MARKERS[item.severity] || 'Advies';
          title.textContent = item.title;
          message.textContent = item.message;
          details.textContent = describeAdvice(item, preferences());
          setVisible(details, Boolean(details.textContent));
        },
      };
    }

    function preferences() {
      return state.get().config?.preferences || {};
    }

    /**
     * The line under one advice: its measurements and the saving.
     *
     * Each of the three is a preference, because a customer who does not want
     * the machinery should not be shown it (SPEC.md §8). Nothing is invented
     * when a value is absent — the part is simply left out.
     */
    function describeAdvice(item, prefs) {
      const parts = [];

      if (prefs.show_technical_explanation !== false && item.measurements) {
        // A measurement we have no words for is left out rather than shown
        // under its key: an identifier in a sentence is worse than a shorter
        // sentence (core/labels.js).
        const readings = Object.entries(item.measurements)
          .map(([key, value]) => [measurementLabel(key), measurementValue(key, value)])
          .filter(([label]) => label !== null)
          .map(([label, value]) => `${label}: ${value}`);
        if (readings.length) {
          parts.push(readings.join(', '));
        }
      }
      if (
        prefs.show_estimated_savings !== false &&
        item.estimated_savings_eur !== null &&
        item.estimated_savings_eur !== undefined
      ) {
        parts.push(
          `geschatte besparing € ${formatNumber(item.estimated_savings_eur, {
            decimals: 2,
          })}`,
        );
      }
      return parts.join(' · ');
    }

    /**
     * Show the backend's answer to one question.
     *
     * The text comes from `CoachResult.explanations` and nowhere else. An
     * answer the backend did not produce is reported as absent rather than
     * filled in here (SPEC.md §8 and §17).
     */
    function showAnswer(question, opener) {
      const explanations = state.get().live?.explanations || {};
      const text = explanations[question.key];
      answerDialog.setTitle(question.label);
      answerText.textContent =
        text ||
        'Deze vraag is nog niet beantwoord. Bereken opnieuw zodra er gegevens ' +
          'gekoppeld zijn.';
      answerDialog.show({ focusReturnsTo: opener });
    }

    async function recalculate() {
      state.setSaving(true);
      recalculateButton.disabled = true;
      recalculateNotice.set('Bezig met berekenen…', { tone: 'info' });
      try {
        // Open to every user: a recalculation produces a result, never a
        // configuration change (SPEC.md §14).
        state.setLive(await createApi(getHass()).recalculate());
        recalculateNotice.set('Het advies is opnieuw berekend.', { tone: 'success' });
      } catch (error) {
        recalculateNotice.set(describeError(error), { tone: 'warning' });
      } finally {
        state.setSaving(false);
        recalculateButton.disabled = false;
      }
    }

    onTap(recalculateButton, () => {
      if (!recalculateButton.disabled) {
        recalculate();
      }
    });

    function update(panelState) {
      const live = panelState.live;
      if (!live) {
        return;
      }
      const prefs = preferences();

      const primary = live.primary_advice;
      adviceTitle.textContent = primary?.title || 'Nog geen advies berekend';
      adviceMessage.textContent =
        primary?.message ||
        'Zodra er een energiebron gekoppeld is, verschijnt hier het hoofdadvies.';

      setVisible(savingRow.element, prefs.show_estimated_savings !== false);
      savingRow.set(
        primary?.estimated_savings_eur === null ||
          primary?.estimated_savings_eur === undefined
          ? null
          : `€ ${formatNumber(primary.estimated_savings_eur, { decimals: 2 })}`,
      );

      // The reason is a machine identifier. Showing it was the defect: the
      // customer read "missing_required_data" where a sentence belonged. A code
      // we have no words for hides the row altogether (core/labels.js).
      const reason = reasonLabel(primary?.reason_code);
      setVisible(
        reasonRow.element,
        prefs.show_technical_explanation !== false && reason !== null,
      );
      reasonRow.set(reason);

      calculatedRow.set(formatTimestamp(live.generated_at));

      // The primary advice is the first of the list, so it is not repeated.
      const rest = (live.advice || []).slice(1);
      adviceList.sync(rest.map((item, index) => ({ ...item, id: item.id || index })));

      const missing = live.missing_data || live.metrics?.data_quality?.missing_items;
      renderMissing(
        missing || [],
        live.metrics?.data_quality?.not_applicable_items || [],
      );
    }

    function renderMissing(items, notApplicable) {
      // A checklist key with no words behind it is left off the list. The
      // customer is told what is missing, never in what identifier it is missing.
      const named = items.map(checklistLabel).filter((label) => label !== null);
      missingList.replaceChildren(
        ...named.map((label) => el('li', { class: 'plain-item', text: label })),
      );
      setVisible(missingList, named.length > 0);

      // What this home is not judged on is named too. A checklist that silently
      // shrank from six items to four would look like it had skipped something,
      // and the customer cannot see the source rows that decided it.
      const skipped = notApplicable.map(checklistLabel).filter((l) => l !== null);
      const skippedSentence = skipped.length
        ? `Niet van toepassing op deze woning, en dus niet meegeteld: ${skipped.join(
            ', ',
          )}.`
        : '';
      missingNotice.set(
        items.length
          ? skippedSentence
          : [
              'Alle gegevens voor een betrouwbaar advies zijn ingevuld.',
              skippedSentence,
            ]
              .filter(Boolean)
              .join(' '),
        { tone: items.length ? 'info' : 'success' },
      );
    }

    return { element, update };
  },
};
