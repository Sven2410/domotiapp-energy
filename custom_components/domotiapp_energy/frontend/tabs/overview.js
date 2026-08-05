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
  formatTimestamp,
  notice,
  setVisible,
  statRow,
} from '../core/dom.js';

const EMPTY_NOT_CONFIGURED = 'Nog niet ingesteld';
const EMPTY_NOT_AVAILABLE = 'Niet beschikbaar';

export const overviewTab = {
  // English and fixed like every other identifier here; only the label the
  // customer reads is Dutch.
  id: 'overview',
  label: 'Overzicht',
  icon: 'mdi:view-dashboard-outline',
  adminOnly: false,

  create() {
    const element = el('div', { class: 'tab-content' });

    // --- Headline figures ---------------------------------------------------
    const scoreCard = card('Energiescore');
    const energyScore = displayMetric('Energiescore', {
      suffix: 'van 100',
    });
    const dataQuality = displayMetric('Datakwaliteit', { suffix: 'procent' });
    const missingNotice = notice('mdi:clipboard-alert-outline');
    scoreCard.body.append(
      el('div', { class: 'display-row' }, [
        energyScore.element,
        dataQuality.element,
      ]),
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
    const peakNotice = notice('mdi:flash-alert-outline');
    powerCard.body.append(
      gridPowerRow.element,
      solarPowerRow.element,
      surplusRow.element,
      loadRow.element,
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

      const missingCount = metrics.data_quality?.missing_items?.length ?? 0;
      missingNotice.set(
        missingCount > 0
          ? `${missingCount} van de zes onderdelen van de datakwaliteit is nog ` +
              'niet compleet. Het tabblad Energiecoach laat zien welke.'
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
      surplusRow.set(formatNumber(metrics.solar_surplus_w), {
        hint: metrics.solar_surplus_w
          ? `Betrouwbaarheid: ${metrics.solar_surplus_confidence}`
          : null,
      });
      loadRow.set(formatNumber(metrics.grid_load_percent, { decimals: 1 }));

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
      adviceConfidence.set(primary?.confidence ?? null);

      updateWarnings(live.advice || []);
    }

    return { element, update };
  },
};
