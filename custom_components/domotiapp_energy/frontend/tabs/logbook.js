/**
 * The Logboek tab (SPEC.md §8, §11, §14 and §23).
 *
 * A read-only view, open to every logged-in user, with one action that is not:
 * emptying it. The button is hidden for a non-admin, and the backend refuses
 * the command regardless — a hidden button is not a permission check
 * (SPEC.md §14).
 *
 * The logbook is deliberately not part of the configuration payload: it can
 * hold 200 entries and would dominate every read. So this tab fetches it
 * itself, when it is first shown and again after a recalculation, rather than
 * on every panel update.
 *
 * The anti-spam counter is shown wherever it is above one. Without it a
 * collapsed run of identical events reads as a single occurrence, and "the
 * source dropped out once" is a different story from "the source dropped out
 * forty times" (SPEC.md §8).
 *
 * **Een tijdlijn en geen tabel** (SPEC.md §61.4). Wat hier stond was een lijst
 * met per regel een volledige datumstempel en het soort gebeurtenis erachter —
 * technisch juist, en te lezen als een export. Nu draagt elke dag een kop en
 * elke rij alleen nog het tijdstip: *"Vandaag · 14:32"* in plaats van
 * *"11-08-2026, 14:32:07 · Advies herberekend"*.
 *
 * De kop hangt aan de eerste rij van zijn dag in plaats van aan een eigen
 * element. Dat houdt één gesleutelde lijst overeind — de rijen worden
 * toegevoegd en verwijderd zoals overal in dit paneel — en de kop verhuist
 * vanzelf mee wanneer de rij erboven verdwijnt.
 */

import { createApi, describeError } from '../core/api.js';
import { createConfirmDialog } from '../core/dialog.js';
import {
  button,
  card,
  el,
  formatDayHeading,
  formatTimeAgainstDay,
  formatTimeOfDay,
  notice,
  setVisible,
} from '../core/dom.js';
import { createRowList } from '../core/rows.js';
import { onTap } from '../core/tap.js';

const EVENT_LABELS = {
  config_changed: 'Configuratie gewijzigd',
  device_added: 'Apparaat toegevoegd',
  device_removed: 'Apparaat verwijderd',
  advice_recalculated: 'Advies herberekend',
  source_unavailable: 'Bron niet beschikbaar',
  invalid_measurement: 'Ongeldige meting',
  peak_risk_detected: 'Piekrisico gesignaleerd',
  solar_surplus_detected: 'Zonneoverschot gesignaleerd',
  invalid_configuration: 'Configuratieprobleem',
};

/**
 * Severity as an icon **and** a word.
 *
 * Never colour alone: the tone only tints what the text already says
 * (SPEC.md §23).
 */
const SEVERITY = {
  info: { icon: 'mdi:information-outline', tone: 'info', label: 'Info' },
  success: { icon: 'mdi:check-circle-outline', tone: 'info', label: 'Gelukt' },
  warning: { icon: 'mdi:alert-outline', tone: 'warning', label: 'Waarschuwing' },
  error: { icon: 'mdi:alert-circle-outline', tone: 'error', label: 'Fout' },
};

export const logbookTab = {
  id: 'logbook',
  label: 'Logboek',
  icon: 'mdi:format-list-bulleted',

  create({ getHass, state, overlay }) {
    const element = el('div', { class: 'tab-content' });
    const logbook = card('Logboek');

    const listNotice = notice('mdi:information-outline');
    const clearButton = button('Logboek wissen');
    clearButton.classList.add('button-danger');
    const actions = el('div', { class: 'actions' }, [clearButton]);
    setVisible(actions, false);

    /** What was fetched last, so a re-render needs no round trip. */
    let entries = [];
    let loading = false;
    let loaded = false;
    let lastCalculated = null;

    const rowList = createRowList({
      emptyText:
        'Het logboek is leeg. Hier komt te staan wat DomotiApp Energy ' +
        'signaleert: configuratiewijzigingen, bronnen die wegvallen en ' +
        'piekmomenten.',
      createRow: () => createLogRow(),
    });

    logbook.body.append(rowList.element, actions, listNotice.element);
    element.appendChild(logbook.element);

    const confirmDialog = createConfirmDialog({ overlay });

    function createLogRow() {
      // De dagkop hoort bij de rij die hem opent, niet bij een eigen element:
      // zo blijft het één gesleutelde lijst en verhuist de kop mee wanneer de
      // rij eronder verdwijnt.
      const heading = el('h3', { class: 'day-heading' });
      const title = el('p', { class: 'row-name' });
      const meta = el('p', { class: 'row-meta' });
      const message = el('p', { class: 'row-meta' });
      const resolved = el('p', { class: 'row-meta' });
      const status = el('div', { class: 'row-status' });
      const statusIcon = el('ha-icon', { attrs: { 'aria-hidden': 'true' } });
      const statusText = el('span');
      status.append(statusIcon, statusText);

      const row = el('div', { class: 'row-item' }, [
        heading,
        el('div', { class: 'row-main' }, [title, meta, message, resolved, status]),
      ]);

      return {
        element: row,
        update(entry) {
          heading.textContent = entry.dayHeading || '';
          setVisible(heading, Boolean(entry.dayHeading));

          title.textContent = entry.title || EVENT_LABELS[entry.event_type] || '';
          // Alleen het tijdstip: de dag staat in de kop erboven. En de
          // hoeveelheid ernaast, want een samengevoegde reeks die zich als één
          // gebeurtenis voordoet vertelt het verkeerde verhaal (SPEC.md §8).
          meta.textContent = [
            formatTimeOfDay(entry.timestamp) || '',
            entry.count > 1 ? `${entry.count} keer` : '',
          ]
            .filter(Boolean)
            .join(' · ');
          message.textContent = entry.message || '';

          // **Drie toestanden, geen twee** (SPEC.md §63.6). Een tijdstip betekent
          // "het was toen voorbij"; leeg betekent óf "nog gaande" óf "van vóór
          // 0.29.0, en toen legden we geen einde vast". Die laatste twee zijn
          // niet uit elkaar te houden, dus zegt het paneel alleen iets wanneer
          // het iets weet — een regel zonder einde krijgt geen woord, want
          // "nog gaande" beweren over een oude regel is precies de onwaarheid
          // die deze ronde wegneemt.
          //
          // En geen tijdvak: een samengevouwen regel draagt het tijdstip van
          // haar *laatste* keer, dus "23:00 tot 07:02" zou een duur zijn die
          // niemand gemeten heeft.
          // **"Weer uitgelezen", niet "opgelost"** (SPEC.md §63.6.4). Wij weten
          // niet wanneer de bron het weer deed; wij weten wanneer een
          // herberekening haar schoon las. Dat scheelt tot vijf minuten via het
          // veiligheidsinterval, en over een herstart of een upgrade heen
          // willekeurig veel: op een klantinstallatie stond er "opgelost" boven
          // regels die dagen eerder geschreven waren. Het werkwoord is dat van
          // de storingszin ernaast — "kon niet worden uitgelezen" — zodat de
          // twee over hetzelfde gaan.
          //
          // Sinds 0.30.0 sluit één schone lezing álle open regels van een bron,
          // dus deze zin staat ook onder regels waarvan het einde niet gezien
          // is. Juist daarom mag hij niet meer beweren dat iets opgelost is:
          // voor alles behalve de nieuwste regel is dit een bovengrens.
          const gelezen = entry.resolved_at
            ? formatTimeAgainstDay(entry.resolved_at, entry.timestamp)
            : null;
          const opgelost = gelezen ? `Weer uitgelezen ${gelezen}.` : '';
          resolved.textContent = opgelost;
          setVisible(resolved, Boolean(opgelost));

          const severity = SEVERITY[entry.severity] || SEVERITY.info;
          statusIcon.setAttribute('icon', severity.icon);
          status.dataset.tone = severity.tone;
          // **Het woord blijft staan waar de kleur iets zegt** (SPEC.md §23):
          // een waarschuwing of een fout mag nooit alleen aan een tint te zien
          // zijn. Bij `info` zegt de tint niets, en dan is "Info" op elke regel
          // ruis die de zin eronder wegdrukt.
          statusText.textContent = entry.severity === 'info' ? '' : severity.label;
          setVisible(status, entry.severity !== 'info');
        },
      };
    }

    function show(list) {
      entries = list;
      // De kop komt op de eerste rij van elke dag. Berekend bij het tonen en
      // niet in de rij zelf, want een rij weet niet wat er boven haar staat.
      let vorigeKop = null;
      const items = entries.map((entry, index) => {
        const kop = formatDayHeading(entry.timestamp);
        const opent = kop !== null && kop !== vorigeKop;
        vorigeKop = kop ?? vorigeKop;
        return {
          ...entry,
          // The backend gives every entry a uuid4; the index is only a fallback
          // so a damaged row can still be listed rather than dropped.
          id: entry.id || `row-${index}`,
          dayHeading: opent ? kop : null,
        };
      });
      rowList.sync(items);
    }

    async function load() {
      if (loading) {
        return;
      }
      loading = true;
      try {
        const result = await createApi(getHass()).getLogs();
        show(result.logs || []);
        loaded = true;
      } catch (error) {
        listNotice.set(describeError(error), { tone: 'warning' });
      } finally {
        loading = false;
      }
    }

    async function clear() {
      state.setSaving(true);
      listNotice.set('Bezig met wissen…', { tone: 'info' });
      try {
        await createApi(getHass()).clearLogs(state.get().config?.revision ?? null);
        show([]);
        listNotice.set('Het logboek is gewist.', { tone: 'success' });
      } catch (error) {
        listNotice.set(describeError(error), { tone: 'warning' });
      } finally {
        state.setSaving(false);
      }
    }

    /** Emptying the logbook asks first, like every other deletion (§11). */
    onTap(clearButton, () => {
      confirmDialog.ask(
        {
          title: 'Logboek wissen',
          text:
            'Weet je zeker dat je het logboek wilt wissen? De gebeurtenissen ' +
            'zijn daarna weg. De configuratie zelf verandert niet.',
          confirmLabel: 'Wissen',
          focusReturnsTo: clearButton,
        },
        clear,
      );
    });

    function update(panelState) {
      // Only an admin may empty it, and only the backend actually enforces it.
      setVisible(actions, panelState.isAdmin);

      // Never fetch over a write of our own. That reload lands on top of
      // whatever the write was about to say, and it cost the message of a
      // refused "wissen" — precisely the one the installer needs to read.
      if (panelState.saving) {
        return;
      }

      const calculatedAt = panelState.live?.generated_at ?? null;
      if (!loaded && !loading) {
        // Remembered here and not after the answer, so the first load counts as
        // having seen this calculation; otherwise the very next update fetches
        // the same list again — and right after a clear it would put the
        // entries straight back on screen.
        lastCalculated = calculatedAt;
        load();
        return;
      }

      // A recalculation writes logbook entries, so the list is stale after one.
      if (loaded && calculatedAt && calculatedAt !== lastCalculated) {
        lastCalculated = calculatedAt;
        load();
      }
    }

    return { element, update };
  },
};
