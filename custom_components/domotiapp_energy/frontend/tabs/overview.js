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
import { confidenceLabel } from '../core/labels.js';

const EMPTY_NOT_CONFIGURED = 'Nog niet ingesteld';
const EMPTY_NOT_AVAILABLE = 'Niet beschikbaar';

/**
 * Why there is no energy score, in a sentence (SPEC.md §35.9).
 *
 * A tile with a dash reads as a fault. Only `incomplete_setup` is one; the
 * other three describe a home that is doing nothing wrong and has nothing to
 * optimise at this moment, so they say *why* there is nothing to measure and
 * carry no warning tone.
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
  no_variable_signal: {
    text:
      'Het tarief is altijd gelijk en er is geen eigen opwek, dus er is geen ' +
      'moment dat beter is dan een ander. Er valt op dit moment niets te ' +
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
  nothing_right_now: {
    text:
      'Er is nu geen opwek om zelf te gebruiken en geen duur moment om te ' +
      'vermijden. Er is op dit moment niets te verbeteren.',
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
    powerCard.body.append(
      gridPowerRow.element,
      solarPowerRow.element,
      surplusRow.element,
      loadRow.element,
      priceRow.element,
      peakNotice.element,
    );

    // --- Advice -------------------------------------------------------------
    const adviceCard = card('Advies');
    const adviceTitle = el('p', { class: 'advice-title' });
    const adviceMessage = el('p', { class: 'advice-message' });
    const adviceConfidence = statRow('Betrouwbaarheid', {
      empty: EMPTY_NOT_AVAILABLE,
    });
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
      adviceConfidence.element,
      warningsTitle,
      warningsHost,
      noWarnings.element,
    );

    // --- Configuration ------------------------------------------------------
    const configCard = card('Configuratie');
    const homeNameRow = statRow('Woning', { empty: EMPTY_NOT_CONFIGURED });
    const sourceCountRow = statRow('Energiebronnen', { empty: '0' });
    const deviceCountRow = statRow('Apparaten', { empty: '0' });
    const setupNotice = notice('mdi:information-outline');
    configCard.body.append(
      homeNameRow.element,
      sourceCountRow.element,
      deviceCountRow.element,
      setupNotice.element,
    );

    element.append(
      scoreCard.element,
      powerCard.element,
      adviceCard.element,
      configCard.element,
    );

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
      const devices = config?.devices ?? [];
      sourceCountRow.set(String(sources.length));
      deviceCountRow.set(String(devices.length));
      homeNameRow.set(config?.home?.home_name || null);

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

      gridPowerRow.set(formatNumber(metrics.grid_power_w), {
        hint:
          metrics.grid_power_w < 0
            ? 'Negatief betekent teruglevering aan het net.'
            : null,
      });
      solarPowerRow.set(formatNumber(metrics.solar_power_w));
      // "Betrouwbaarheid: high" is what this used to read: the level travels as
      // an English identifier and was printed as it arrived (core/labels.js).
      const surplusConfidence = confidenceLabel(metrics.solar_surplus_confidence);
      surplusRow.set(formatNumber(metrics.solar_surplus_w), {
        hint:
          metrics.solar_surplus_w && surplusConfidence
            ? `Betrouwbaarheid: ${surplusConfidence}`
            : null,
      });
      loadRow.set(formatNumber(metrics.grid_load_percent, { decimals: 1 }));
      updatePrice(config, metrics);

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
      adviceConfidence.set(confidenceLabel(primary?.confidence));

      updateWarnings(live.advice || []);
    }

    return { element, update };
  },
};
