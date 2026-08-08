/**
 * The Overzicht tab (SPEC.md §8, §10, §11 and §23).
 *
 * Shows everything SPEC.md §8 lists for this tab: integration status, data
 * quality, energy score, current grid power, solar production, solar surplus,
 * the percentage of the configured maximum, the primary advice, warnings, the
 * number of configured appliances and the time of the last calculation.
 *
 * The layout follows the DomotiTech house style rather than a dashboard grid:
 * one narrow column, a great deal of white space, a headline figure that
 * dominates its label, and hairline rules instead of boxed-in blocks. SPEC.md
 * §11 allows several columns "waar nuttig"; here it is not — two columns left
 * one half empty and made neighbouring cards look mismatched.
 *
 * The DOM is built once in `create()`; `update()` only ever calls the setters
 * that `create()` closed over. Nothing here reads an entity: the panel gets its
 * numbers from the backend over the WebSocket API.
 */

import {
  adviceBlock,
  card,
  displayMetric,
  el,
  formatNumber,
  formatPrice,
  formatTimestamp,
  notice,
  setVisible,
  statRow,
} from '../core/dom.js';

const EMPTY_NOT_CONFIGURED = 'Nog niet ingesteld';
const EMPTY_NOT_AVAILABLE = 'Niet beschikbaar';

/**
 * Why there is no energy score, in a sentence (SPEC.md §35.9).
 *
 * A tile with a dash reads as a fault. Two of these are faults — an incomplete
 * installation and unset price thresholds — and only those carry a warning
 * tone. The rest describe a home doing nothing wrong with nothing to optimise
 * at this moment, and they say *why*.
 *
 * **Every variant is written out in full rather than assembled from clauses.**
 * `nothing_right_now` used to be one catch-all sentence claiming both "geen
 * opwek" and "geen duur moment", which told a fixed-tariff home about
 * expensive hours it never has. Splitting it means each sentence can be read
 * and rewritten as the thing a customer actually sees.
 *
 * Keyed by the backend's reason code, which travels in English like every other
 * identifier in this project. The sentences live here rather than in
 * `translations/` because they carry the reasoning (SPEC.md §26).
 */
const SCORE_UNAVAILABLE_TEXT = {
  incomplete_setup: {
    text:
      'Er is nog geen cijfer, omdat de installatie nog niet compleet is. ' +
      'Het tabblad Energiecoach laat zien wat er ontbreekt.',
    tone: 'warning',
    icon: 'mdi:clipboard-alert-outline',
  },
  price_thresholds_missing: {
    text:
      'Zolang de lage en de hoge prijsdrempel niet zijn ingevuld, is niet te ' +
      'bepalen of dit een duur moment is. Vul ze in bij Installatie.',
    tone: 'warning',
    icon: 'mdi:clipboard-alert-outline',
  },
  no_variable_signal: {
    text:
      'Het tarief is altijd gelijk en er zijn geen zonnepanelen, dus er is ' +
      'geen moment dat beter is dan een ander. Er valt daarom niets te ' +
      'optimaliseren. Het advies blijft gewoon werken.',
    tone: 'info',
    icon: 'mdi:information-outline',
  },
  nothing_movable: {
    text:
      'Er is nu opwek, maar geen apparaat of batterij die verbruik kan ' +
      'verplaatsen. Er valt daarom niets te benutten dat nu niet al gebeurt.',
    tone: 'info',
    icon: 'mdi:information-outline',
  },
  no_sun_cheap_price: {
    text:
      'Je panelen leveren op dit moment niets en de stroomprijs is laag. Er ' +
      'is nu dus geen overschot om te benutten en geen duur verbruik om te ' +
      'vermijden.',
    tone: 'info',
    icon: 'mdi:information-outline',
  },
  no_sun_fixed_tariff: {
    text:
      'Je panelen leveren op dit moment niets, en bij een vast tarief is het ' +
      'ene moment niet beter dan het andere. Er is nu dus niets te verbeteren.',
    tone: 'info',
    icon: 'mdi:information-outline',
  },
  cheap_price: {
    text:
      'De stroomprijs is op dit moment laag, dus er is geen duur verbruik om ' +
      'te vermijden.',
    tone: 'info',
    icon: 'mdi:information-outline',
  },
};

export const overviewTab = {
  // English and fixed like every other identifier here; only the label the
  // customer reads is Dutch.
  id: 'overview',
  label: 'Overzicht',
  icon: 'mdi:view-dashboard-outline',

  create() {
    const element = el('div', { class: 'tab-content' });

    // --- Headline figures ---------------------------------------------------
    const scoreCard = card('Energiescore');
    // "van 100" read as a report card on the household. It is a reading of this
    // moment: components drop out because there is nothing to measure, not
    // because anything is wrong (SPEC.md §35).
    //
    // The empty text is "Geen cijfer" and not "Nog niet berekend", because for
    // a home with a fixed contract and no panels there is nothing to calculate
    // — not something still pending. The sentence underneath says which of the
    // four reasons it is.
    const energyScore = displayMetric('Energiescore', {
      suffix: 'op dit moment',
      empty: 'Geen cijfer',
    });
    const dataQuality = displayMetric('Datakwaliteit', { suffix: 'procent' });
    const scoreNotice = notice('mdi:information-outline');
    const missingNotice = notice('mdi:clipboard-alert-outline');
    scoreCard.body.append(
      el('div', { class: 'display-row' }, [
        energyScore.element,
        dataQuality.element,
      ]),
      scoreNotice.element,
      missingNotice.element,
    );

    const statusRow = statRow('Status', { empty: EMPTY_NOT_AVAILABLE });
    const calculatedRow = statRow('Laatste berekening', {
      empty: 'Nog niet berekend',
    });
    scoreCard.body.append(statusRow.element, calculatedRow.element);

    // --- Measurements -------------------------------------------------------
    const powerCard = card('Actuele situatie');
    // First, and above the grid power on purpose: this is the only row that
    // answers "what is my home doing", and the grid power is a *consequence*
    // of it minus production, so it used to sit above its own causes. It also
    // needs no footnote, where the signed grid figure does (SPEC.md §36.5).
    const homeConsumptionRow = statRow('Thuisverbruik', {
      unit: ' W',
      empty: EMPTY_NOT_AVAILABLE,
    });
    const gridPowerRow = statRow('Netvermogen', {
      unit: ' W',
      empty: EMPTY_NOT_CONFIGURED,
    });
    const solarPowerRow = statRow('Zonneproductie', {
      unit: ' W',
      empty: EMPTY_NOT_CONFIGURED,
    });
    const surplusRow = statRow('Zonneoverschot', {
      unit: ' W',
      empty: EMPTY_NOT_AVAILABLE,
    });
    const loadRow = statRow('Percentage van maximum', {
      unit: '%',
      empty: EMPTY_NOT_CONFIGURED,
    });
    // The all-in price, with the market price it was derived from underneath.
    // Showing only the derived figure would ask the installer to trust a
    // conversion they cannot check against the sensor in front of them.
    const priceRow = statRow('Actuele energieprijs', {
      empty: EMPTY_NOT_AVAILABLE,
    });
    const peakNotice = notice('mdi:flash-alert-outline');
    // The one thing the old confidence label was about, next to the figure it
    // qualifies rather than as a grade on it.
    const surplusNotice = notice('mdi:battery-alert-variant-outline');
    const consumptionNotice = notice('mdi:solar-power-variant-outline');
    // Kept from the removed Configuratie card: an installation with nothing
    // linked has to say what to do, and this is where the empty readings are.
    const setupNotice = notice('mdi:information-outline');
    powerCard.body.append(
      homeConsumptionRow.element,
      gridPowerRow.element,
      solarPowerRow.element,
      surplusRow.element,
      loadRow.element,
      priceRow.element,
      consumptionNotice.element,
      surplusNotice.element,
      peakNotice.element,
      setupNotice.element,
    );

    // --- Advice -------------------------------------------------------------
    const adviceCard = card('Advies');
    const adviceTitle = el('p', { class: 'advice-title' });
    const adviceMessage = el('p', { class: 'advice-message' });
    const warningsTitle = el('h3', {
      class: 'subheading',
      text: 'Waarschuwingen',
    });
    const warningsHost = el('div', { class: 'advice-list' });
    const noWarnings = notice('mdi:check-circle-outline');
    setVisible(warningsTitle, false);
    setVisible(warningsHost, false);
    adviceCard.body.append(
      adviceTitle,
      adviceMessage,
      warningsTitle,
      warningsHost,
      noWarnings.element,
    );

    // The "Configuratie" card was removed in 0.4.1. It restated the home name
    // and counted the rows two tabs away, which is not a reading of this
    // moment and cost a screenful on a phone.
    element.append(scoreCard.element, powerCard.element, adviceCard.element);

    /** Keyed by advice id, so warnings are added and removed, never rebuilt. */
    const warningBlocks = new Map();

    function updateWarnings(advice) {
      const warnings = advice.filter((item) => item.severity === 'warning');
      const seen = new Set();

      for (const item of warnings) {
        seen.add(item.id);
        let block = warningBlocks.get(item.id);
        if (!block) {
          block = adviceBlock();
          warningBlocks.set(item.id, block);
          warningsHost.appendChild(block.element);
        }
        block.set({
          marker: 'Waarschuwing',
          title: item.title,
          message: item.message,
        });
      }

      for (const [id, block] of warningBlocks) {
        if (!seen.has(id)) {
          block.element.remove();
          warningBlocks.delete(id);
        }
      }

      const hasWarnings = warnings.length > 0;
      setVisible(warningsTitle, hasWarnings);
      setVisible(warningsHost, hasWarnings);
      noWarnings.set(
        hasWarnings ? '' : 'Er zijn op dit moment geen waarschuwingen.',
        { tone: 'success' },
      );
    }

    /**
     * Show the price the engine actually calculates with.
     *
     * Always the all-in price, because that is the only kind that exists past
     * the calculator (SPEC.md §16). When it was derived from a bare market
     * price the hint names that reading, so the conversion can be checked
     * against the sensor rather than believed.
     *
     * The two empty cases are told apart on purpose: a fixed contract has no
     * hourly price to show and never will, while a missing one is something to
     * go and fix.
     */
    function updatePrice(config, metrics) {
      if (config?.home?.contract_type !== 'dynamic') {
        priceRow.set(null, {
          empty: 'Niet van toepassing bij een vast contract',
        });
        return;
      }

      const allIn = metrics.current_price_eur_kwh;
      if (allIn === null || allIn === undefined) {
        priceRow.set(null, {
          empty: 'Geen bruikbare prijsbron',
        });
        return;
      }

      const market = metrics.market_price_eur_kwh;
      priceRow.set(`${formatPrice(allIn)} per kWh`, {
        hint:
          market === null || market === undefined
            ? null
            : `All-in, afgeleid van een marktprijs van ${formatPrice(market)}.`,
      });
    }

    function update(state) {
      const { config, live, status } = state;

      statusRow.set(
        status === 'ready' ? 'Actief' : status === 'loading' ? 'Laden…' : 'Fout',
      );

      const sources = config?.sources ?? [];

      // An installation with nothing linked yet has to say what to do, not
      // show a column of empty rows (SPEC.md §8).
      setupNotice.set(
        sources.length === 0
          ? 'Er zijn nog geen energiebronnen gekoppeld. Ga naar het tabblad ' +
              'Energiebronnen om je slimme meter of omvormer te koppelen.'
          : '',
        { tone: 'info' },
      );

      if (!live) {
        return;
      }

      const metrics = live.metrics || {};
      calculatedRow.set(formatTimestamp(live.generated_at));

      energyScore.set(metrics.energy_score ?? null);
      dataQuality.set(metrics.data_quality?.score ?? null);

      // Only when there is no number: with a score on screen the sentence
      // would explain an absence that is not there.
      const unavailable =
        metrics.energy_score === null || metrics.energy_score === undefined
          ? SCORE_UNAVAILABLE_TEXT[metrics.score_unavailable_reason]
          : null;
      scoreNotice.set(unavailable ? unavailable.text : '', {
        tone: unavailable ? unavailable.tone : 'info',
        icon: unavailable ? unavailable.icon : null,
      });

      // "van de zes" was a constant, and it was wrong for any home that does
      // not own all six things — a home with solar and a smart meter but no
      // smart appliances was told two of six were incomplete and could never
      // fix either. The checklist now drops what does not apply, so the total
      // is counted rather than assumed (engine/completeness.py).
      const quality = metrics.data_quality || {};
      const missingCount = quality.missing_items?.length ?? 0;
      const applicable = missingCount + (quality.completed_items?.length ?? 0);
      missingNotice.set(
        missingCount > 0
          ? `${missingCount} van de ${applicable} onderdelen van de ` +
              'datakwaliteit is nog niet compleet. Het tabblad Energiecoach ' +
              'laat zien welke.'
          : 'Alle gegevens voor een betrouwbaar advies zijn ingevuld.',
        { tone: missingCount > 0 ? 'warning' : 'success' },
      );

      homeConsumptionRow.set(formatNumber(metrics.home_consumption_w));
      gridPowerRow.set(formatNumber(metrics.grid_power_w), {
        hint:
          metrics.grid_power_w < 0
            ? 'Negatief betekent teruglevering aan het net.'
            : null,
      });
      solarPowerRow.set(formatNumber(metrics.solar_power_w));
      // No confidence label here any more. It read "Betrouwbaarheid: gemiddeld"
      // beside a number that was perfectly correct — the level said which route
      // the engine took, not how good the figure was, and a customer cannot act
      // on either. The one level that did carry information is the notice below.
      surplusRow.set(formatNumber(metrics.solar_surplus_w));
      loadRow.set(formatNumber(metrics.grid_load_percent, { decimals: 1 }));
      updatePrice(config, metrics);

      // Cause and fix, not a grade. One sentence covers both figures the
      // blind spot touches: two near-identical warnings on one card is worse
      // than one that names both (SPEC.md §36.6). The same sentence is in
      // `engine/providers.py` (UNREADABLE_BATTERY_SENTENCE) for the coach's
      // answer to "welke gegevens ontbreken nog?"; the two must stay in step.
      const batteryUnreadable =
        metrics.solar_surplus_may_be_overstated ||
        metrics.home_consumption_unavailable_reason === 'battery_unreadable';
      surplusNotice.set(
        batteryUnreadable
          ? 'Het vermogen van je thuisbatterij kan niet uitgelezen worden. Een ' +
              'batterij die laadt of ontlaadt verschuift wat er van het net ' +
              'komt, dus het thuisverbruik is niet te berekenen en het ' +
              'zonneoverschot kan te hoog zijn. Koppel de vermogenssensor van ' +
              'de batterij om dit op te lossen.'
          : '',
        { tone: 'warning' },
      );

      // Only the inverter case gets its own sentence. A missing grid reading
      // leaves the row empty and is already reported by the checklist, so a
      // second line about it would say what the card says twice.
      consumptionNotice.set(
        metrics.home_consumption_unavailable_reason === 'solar_unreadable'
          ? 'Je omvormer levert op dit moment geen waarde, dus het ' +
              'thuisverbruik is niet te berekenen. Controleer de zonnebron ' +
              'bij Energiebronnen.'
          : '',
        { tone: 'warning' },
      );

      // Text plus icon, never colour alone (SPEC.md §23).
      peakNotice.set(
        metrics.peak_risk
          ? 'Piekrisico: de netbelasting ligt op of boven de ingestelde ' +
              'waarschuwingsgrens.'
          : '',
        { tone: 'warning' },
      );

      const primary = live.primary_advice;
      adviceTitle.textContent = primary?.title || 'Nog geen advies berekend';
      adviceMessage.textContent =
        primary?.message ||
        'Zodra er een energiebron gekoppeld is, verschijnt hier het hoofdadvies.';

      updateWarnings(live.advice || []);
    }

    return { element, update };
  },
};
