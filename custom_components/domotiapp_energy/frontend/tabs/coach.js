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
  formatMoment,
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
    // **No empty text on either amount, because neither row is ever empty**
    // (SPEC.md §58.2). A row here appears because there is a figure to put in
    // it; see `update()` for why an absent amount hides the row instead of
    // reporting a sum that failed.
    const savingRow = statRow('Geschatte besparing');
    // **A second amount, never on the same line and never under the same
    // label** (SPEC.md §56.4). An appliance that takes whatever is spare has no
    // cycle to price, so what it earns is a rate; "€ 1,20" and "€ 0,12" are
    // both true and answer different questions.
    const savingRateRow = statRow('Geschatte opbrengst per uur');
    const reasonRow = statRow('Reden', { empty: 'Onbekend' });
    const calculatedRow = statRow('Laatste berekening', { empty: 'Nog niet berekend' });

    const recalculateButton = button('Opnieuw berekenen', { primary: true });
    // **The second of the two places this button belongs** (SPEC.md §44.6).
    // The other is on Apparaten, where a resident is tidying the kitchen; this
    // one is the moment he reads "start nu om 07:00 te halen" and thinks "hij
    // is niet vol". Leaving either out means remembering, at the wrong moment,
    // where the other one is.
    const readyButton = button('Klaar / vol');
    const readyLine = el('p', { class: 'advice-message' });
    const recalculateNotice = notice('mdi:refresh');
    // Which appliance the primary advice is about, when that appliance waits
    // to be told there is work in it, and what its flag currently says.
    let readyDevice = null;
    let readyFlags = {};

    mainCard.body.append(
      adviceTitle,
      adviceMessage,
      savingRow.element,
      savingRateRow.element,
      reasonRow.element,
      calculatedRow.element,
      readyLine,
      el('div', { class: 'actions' }, [recalculateButton, readyButton]),
      recalculateNotice.element,
    );

    // --- The further advice --------------------------------------------------
    const listCard = card('Overige adviezen');
    const adviceList = createRowList({
      emptyText: 'Er is op dit moment geen aanvullend advies.',
      createRow: () => createAdviceRow(),
    });
    listCard.body.appendChild(adviceList.element);

    // --- The data the advice rests on ---------------------------------------
    // **The heading names the subject, not a shortfall** (SPEC.md §58.2). It
    // read "Ontbrekende gegevens" above the sentence "Alle gegevens voor een
    // betrouwbaar advies zijn ingevuld" — chrome promising a deficiency and
    // then denying it, and for a home where nothing is missing and nothing
    // ever will be it was the last place on the screen still pointing at a
    // gap.
    //
    // Whether anything is missing is a fact about this moment, so it is stated
    // where the facts are: the lead line appears only when there is a list
    // under it, in the same words the coach answers the question with
    // ("Nog ontbrekend: …", engine/providers.py).
    const missingCard = card('Gegevens voor je advies');
    const missingLead = el('p', { class: 'advice-message', text: 'Nog ontbrekend:' });
    const missingList = el('ul', { class: 'plain-list' });
    const missingNotice = notice('mdi:check-circle-outline');
    missingCard.body.append(missingLead, missingList, missingNotice.element);

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
      // **Its own sentence, never the same one with another unit** (SPEC.md
      // §56.4). An appliance that takes whatever is spare has no cycle to
      // price, so what it earns is a rate — and "€ 1,20" next to "€ 0,12" would
      // be two true numbers answering different questions.
      if (
        prefs.show_estimated_savings !== false &&
        item.savings_rate_eur_per_hour !== null &&
        item.savings_rate_eur_per_hour !== undefined
      ) {
        parts.push(
          `levert ongeveer € ${formatNumber(item.savings_rate_eur_per_hour, {
            decimals: 2,
          })} per uur op zolang dit overschot er is`,
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

    /**
     * Say how long "hij is vol" stays true, in the words somebody would use.
     *
     * The same two sentences the appliance row uses, for the same reason
     * (SPEC.md §32.6): where nothing is linked, expiring is the only way the
     * flag ever goes out, and that belongs in the sentence at the moment the
     * button is pressed.
     */
    function describeReady(flag) {
      if (!flag) {
        return '';
      }
      const until = formatMoment(flag.expires_at);
      if (flag.auto_clears) {
        return `Staat vol. Dit vervalt ${until}, of eerder zodra hij klaar is.`;
      }
      return (
        `Staat vol. We kunnen niet zien wanneer hij klaar is, dus dit blijft ` +
        `staan tot ${until}. Zet het eerder uit als er niets meer in zit.`
      );
    }

    /**
     * Say the appliance this advice is about has work in it, or take it back.
     *
     * The appliance comes from the advice itself (`related_device_ids`), so
     * the button can never be about something else than the sentence above it.
     */
    async function toggleReady() {
      if (!readyDevice) {
        return;
      }
      const wasSet = Boolean(readyFlags[readyDevice.id]);
      try {
        const api = createApi(getHass());
        await api.setDeviceReady(readyDevice.id, !wasSet);
        state.setLive(await api.getCoach());
      } catch (error) {
        recalculateNotice.set(describeError(error), { tone: 'warning' });
      }
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

    onTap(readyButton, () => toggleReady());

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
      // The flag belongs to the appliance this advice is about, and the button
      // only appears where that appliance waits to be told there is work in it
      // (SPEC.md §32.5). Anywhere else it would be a button without meaning.
      readyFlags = live.ready_devices || {};
      const devices = panelState.config?.devices || [];
      const subject = (primary?.related_device_ids || [])[0];
      readyDevice =
        devices.find((row) => row.id === subject && row.needs_ready_flag) || null;
      const readyState = readyDevice ? readyFlags[readyDevice.id] : null;
      setVisible(readyButton, Boolean(readyDevice));
      readyButton.textContent = readyState ? 'Toch niet vol' : 'Klaar / vol';
      readyLine.textContent = describeReady(readyState);
      setVisible(readyLine, Boolean(readyState));

      adviceTitle.textContent = primary?.title || 'Nog geen advies berekend';
      adviceMessage.textContent =
        primary?.message ||
        'Zodra er een energiebron gekoppeld is, verschijnt hier het hoofdadvies.';

      /*
       * **An amount that does not exist is not an amount that failed**
       * (SPEC.md §58.2). This row said "Niet te berekenen" for every advice
       * without a figure, and only the surplus advice ever carries one — so
       * under "de situatie vraagt niet om een aanpassing" the card reported a
       * sum that was never attempted. There is nothing to save because there
       * is nothing to change, and that is a different kind of nothing.
       *
       * So the row exists because there is a figure to put in it. Where a sum
       * *was* attempted and could not be made, the advice message above
       * already names the field that stopped it (engine/advisor.py
       * `_why_no_amount` for the total, `_why_no_rate` for the hourly amount),
       * which is more use than "Niet te berekenen" was.
       */
      const showAmounts = prefs.show_estimated_savings !== false;

      const saving = primary?.estimated_savings_eur;
      const hasSaving = typeof saving === 'number' && !Number.isNaN(saving);
      setVisible(savingRow.element, showAmounts && hasSaving);
      if (hasSaving) {
        savingRow.set(`€ ${formatNumber(saving, { decimals: 2 })}`);
      }

      // The modulating half of the same figure, which this card had nowhere to
      // put: for a charger that takes whatever is spare the total is empty on
      // purpose (SPEC.md §56.4) and the rate is the answer, so the primary
      // advice showed "Niet te berekenen" while the amount sat unused in the
      // payload. The further advice below has shown it since 0.18.0.
      const rate = primary?.savings_rate_eur_per_hour;
      const hasRate = typeof rate === 'number' && !Number.isNaN(rate);
      setVisible(savingRateRow.element, showAmounts && hasRate);
      if (hasRate) {
        savingRateRow.set(`€ ${formatNumber(rate, { decimals: 2 })}`, {
          hint: 'Zolang dit zonneoverschot er is.',
        });
      }

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
      // The lead line goes with the list it introduces: a heading that no
      // longer promises a shortfall may not leave a bare list of nouns behind
      // when there is one.
      setVisible(missingLead, named.length > 0);

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
