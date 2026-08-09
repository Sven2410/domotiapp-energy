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
  feed_in_pays_better: {
    text:
      'Je panelen leveren op dit moment, maar terugleveren levert je meer op ' +
      'dan de stroom je kost. Zelf verbruiken zou je nu geld kosten, dus er ' +
      'valt aan je opwek niets te benutten. De coach zegt hetzelfde: wachten ' +
      'is voordeliger.',
    // Deliberately not a warning. The resident is earning money; a warning
    // colour would turn that into a problem (SPEC.md §35.9).
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

/**
 * Why one axis sat this one out, while the other one still produced a number.
 *
 * The sentences above only appear when there is *no* score. That was enough
 * while a missing axis meant nothing was worth saying, and SPEC.md §35.4d ends
 * that: a home in the sun whose feed-in tariff beats its import price gets a
 * score from the price axis alone. Reading 88 there, nothing on the screen says
 * the solar half was excluded, let alone why.
 *
 * `not_applicable_components` has named the axes since 0.4.0 and nothing here
 * read it. Naming them was never enough anyway — "zonnebenutting telt niet mee"
 * only raises the question these answer.
 *
 * Same contract as the block above: one code, one whole sentence, each claiming
 * only what its branch established. `solar_no_panels` is separate from
 * `solar_no_production` for exactly that reason.
 */
const COMPONENT_UNAVAILABLE_TEXT = {
  solar_no_panels:
    'Zonnebenutting telt niet mee, want deze woning heeft geen zonnepanelen.',
  solar_no_production:
    'Zonnebenutting telt niet mee, want je panelen leveren op dit moment niets.',
  solar_no_grid_reading:
    'Zonnebenutting telt niet mee, want zonder netmeting is niet te zien ' +
    'hoeveel van je opwek je zelf gebruikt.',
  solar_nothing_movable:
    'Zonnebenutting telt niet mee, want er is geen apparaat of batterij die ' +
    'verbruik naar dit moment kan verplaatsen.',
  solar_feed_in_pays_better:
    'Zonnebenutting telt niet mee: terugleveren levert je op dit moment meer ' +
    'op dan de stroom je kost, dus je opwek zelf gebruiken zou je geld kosten.',
  price_fixed_tariff:
    'Het prijsmoment telt niet mee, want bij een vast tarief is het ene ' +
    'moment niet duurder dan het andere.',
  price_thresholds_missing:
    'Het prijsmoment telt niet mee zolang de lage en de hoge prijsdrempel ' +
    'niet zijn ingevuld. Vul ze in bij Installatie.',
  price_no_reading:
    'Het prijsmoment telt niet mee, want de actuele prijs is op dit moment ' +
    'niet uit te lezen.',
  price_cheap:
    'Het prijsmoment telt niet mee, want de stroom is nu goedkoop en er is ' +
    'dus geen duur verbruik om te vermijden.',
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
    // Titled for the moment rather than for the score, because the score is no
    // longer the figure this card leads with. It may be absent — that is the
    // design (SPEC.md §35.9) — and the largest place on the screen cannot
    // belong to something that is regularly not there.
    const scoreCard = card('Op dit moment');
    // First and largest: the one figure that answers "what is my house doing",
    // present whenever the grid meter and the inverter can be read, and
    // therefore present on the evenings and nights when the score is not
    // (SPEC.md §35.8b). It moved up from `Actuele situatie` rather than being
    // repeated here — the same number twice on one screen invites the question
    // which of the two is the real one.
    const homeConsumption = displayMetric('Thuisverbruik', {
      suffix: 'watt',
      empty: EMPTY_NOT_AVAILABLE,
    });
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
    // Why an axis was left out while the other one still gave a number
    // (SPEC.md §35.9b). Its own notice rather than an extension of the one
    // above: that one explains an absent score, this one qualifies a present
    // score, and they are never both filled.
    const componentNotice = notice('mdi:scale-balance');
    const missingNotice = notice('mdi:clipboard-alert-outline');
    // Moved up with the figure it explains: without it, "Niet beschikbaar"
    // stands under the largest number on the page with no reason next to it.
    const consumptionNotice = notice('mdi:solar-power-variant-outline');
    scoreCard.body.append(
      el('div', { class: 'display-row' }, [
        homeConsumption.element,
        energyScore.element,
        dataQuality.element,
      ]),
      consumptionNotice.element,
      scoreNotice.element,
      componentNotice.element,
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
    // A measurement with no direction attached, and therefore here among the
    // meter readings rather than in the score tile (SPEC.md §35.8b). It is
    // present whenever production and grid power can be read — including when
    // the score is not, which is the whole reason it exists as its own row.
    //
    // *Zelfbenutting*, not *zelfvoorziening*: this is the share of production
    // consumed on site. The other fraction — own production over own
    // consumption — is a different number that can read 100% in the same
    // minute, so the label is doing real work here.
    const selfConsumptionRow = statRow('Zelfbenutting', {
      unit: '%',
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
    // A count is a fact about the home; the appliances themselves live on
    // Apparaten, where they are described. Listing them here too would turn
    // the overview into a dashboard (SPEC.md §37).
    const runningRow = statRow('Apparaten die nu draaien', {
      empty: EMPTY_NOT_AVAILABLE,
    });
    const peakNotice = notice('mdi:flash-alert-outline');
    // The one thing the old confidence label was about, next to the figure it
    // qualifies rather than as a grade on it.
    const surplusNotice = notice('mdi:battery-alert-variant-outline');
    // Kept from the removed Configuratie card: an installation with nothing
    // linked has to say what to do, and this is where the empty readings are.
    const setupNotice = notice('mdi:information-outline');
    powerCard.body.append(
      gridPowerRow.element,
      solarPowerRow.element,
      surplusRow.element,
      selfConsumptionRow.element,
      loadRow.element,
      priceRow.element,
      runningRow.element,
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

      homeConsumption.set(formatNumber(metrics.home_consumption_w));
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

      // The mirror case, and the one that had nowhere to be said: there *is* a
      // number, and it was reached over one axis instead of two. Only when
      // there is a score — without one the sentence above already covers the
      // ground, and two explanations of the same silence read as a fault.
      //
      // Both axes out means no score, so this is at most one sentence.
      const scored =
        metrics.energy_score !== null && metrics.energy_score !== undefined;
      const componentReasons = scored
        ? (metrics.not_applicable_components || [])
            .map((key) => (metrics.component_unavailable_reasons || {})[key])
            .map((code) => COMPONENT_UNAVAILABLE_TEXT[code])
            .filter(Boolean)
        : [];
      componentNotice.set(componentReasons.join(' '), { tone: 'info' });

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
      // No confidence label here any more. It read "Betrouwbaarheid: gemiddeld"
      // beside a number that was perfectly correct — the level said which route
      // the engine took, not how good the figure was, and a customer cannot act
      // on either. The one level that did carry information is the notice below.
      surplusRow.set(formatNumber(metrics.solar_surplus_w));
      selfConsumptionRow.set(
        formatNumber(metrics.self_consumption_percent, { decimals: 0 }),
      );
      loadRow.set(formatNumber(metrics.grid_load_percent, { decimals: 1 }));
      // Absent, not zero, when no appliance links a power entity: "0 draaien"
      // would claim a measurement of every appliance in the house.
      const linked = Object.keys(metrics.device_power_w || {}).length;
      runningRow.set(linked ? String(metrics.running_device_count ?? 0) : null);
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
