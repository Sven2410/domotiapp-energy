/**
 * The Overzicht tab (SPEC.md §8).
 *
 * Shows everything SPEC.md §8 lists for this tab: integration status, data
 * quality, energy score, current grid power, solar production, solar surplus,
 * the percentage of the configured maximum, the primary advice, warnings, the
 * number of configured appliances and the time of the last calculation.
 *
 * The DOM is built once in `create()`; `update()` only ever calls the setters
 * that `create()` closed over. Nothing here reads an entity: the panel gets its
 * numbers from the backend over the WebSocket API, so the tab keeps working
 * regardless of what the entities are named.
 */

import {
  card,
  el,
  formatNumber,
  formatTimestamp,
  notice,
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

    // --- Status -------------------------------------------------------------
    const statusCard = card('Status');
    const statusRow = statRow('Integratie', { empty: EMPTY_NOT_AVAILABLE });
    const calculatedRow = statRow('Laatste berekening', {
      empty: 'Nog niet berekend',
    });
    const setupNotice = notice('mdi:information-outline');
    statusCard.body.append(
      statusRow.element,
      calculatedRow.element,
      setupNotice.element,
    );

    // --- Scores -------------------------------------------------------------
    const scoreCard = card('Scores');
    const energyScoreRow = statRow('Energiescore', {
      empty: 'Nog niet berekend',
    });
    const dataQualityRow = statRow('Datakwaliteit', {
      unit: '%',
      empty: 'Nog niet berekend',
    });
    const missingNotice = notice('mdi:clipboard-alert-outline');
    scoreCard.body.append(
      energyScoreRow.element,
      dataQualityRow.element,
      missingNotice.element,
    );

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
    const adviceCard = card('Hoofdadvies');
    const adviceTitle = el('p', { class: 'advice-title' });
    const adviceMessage = el('p', { class: 'advice-message' });
    const adviceConfidence = statRow('Betrouwbaarheid', {
      empty: EMPTY_NOT_AVAILABLE,
    });
    const warningsTitle = el('h3', {
      class: 'subheading',
      text: 'Waarschuwingen',
    });
    const warningsList = el('ul', { class: 'warning-list' });
    const noWarnings = notice('mdi:check-circle-outline');
    adviceCard.body.append(
      adviceTitle,
      adviceMessage,
      adviceConfidence.element,
      warningsTitle,
      warningsList,
      noWarnings.element,
    );

    // --- Configuration ------------------------------------------------------
    const configCard = card('Configuratie');
    const sourceCountRow = statRow('Energiebronnen', { empty: '0' });
    const deviceCountRow = statRow('Apparaten', { empty: '0' });
    const homeNameRow = statRow('Woning', { empty: EMPTY_NOT_CONFIGURED });
    configCard.body.append(
      homeNameRow.element,
      sourceCountRow.element,
      deviceCountRow.element,
    );

    element.append(
      statusCard.element,
      scoreCard.element,
      powerCard.element,
      adviceCard.element,
      configCard.element,
    );

    /** Keyed by advice id, so warnings are added and removed, never rebuilt. */
    const warningNodes = new Map();

    function updateWarnings(advice) {
      const warnings = advice.filter((item) => item.severity === 'warning');
      const seen = new Set();

      for (const item of warnings) {
        seen.add(item.id);
        let node = warningNodes.get(item.id);
        if (!node) {
          node = el('li', { class: 'warning-item' });
          warningNodes.set(item.id, node);
          warningsList.appendChild(node);
        }
        node.textContent = `${item.title} — ${item.message}`;
      }

      for (const [id, node] of warningNodes) {
        if (!seen.has(id)) {
          node.remove();
          warningNodes.delete(id);
        }
      }

      warningsList.hidden = warnings.length === 0;
      noWarnings.set(
        warnings.length === 0 ? 'Er zijn op dit moment geen waarschuwingen.' : '',
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
      // show six empty rows (SPEC.md §8).
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

      energyScoreRow.set(
        metrics.energy_score === null || metrics.energy_score === undefined
          ? null
          : `${metrics.energy_score} / 100`,
      );
      dataQualityRow.set(metrics.data_quality?.score ?? null);

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
