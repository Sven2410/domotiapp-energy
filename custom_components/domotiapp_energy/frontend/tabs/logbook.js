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
 */

import { createApi, describeError } from '../core/api.js';
import { createConfirmDialog } from '../core/dialog.js';
import {
  button,
  card,
  el,
  formatTimestamp,
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
  adminOnly: false,

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
      const title = el('p', { class: 'row-name' });
      const meta = el('p', { class: 'row-meta' });
      const message = el('p', { class: 'row-meta' });
      const status = el('div', { class: 'row-status' });
      const statusIcon = el('ha-icon', { attrs: { 'aria-hidden': 'true' } });
      const statusText = el('span');
      status.append(statusIcon, statusText);

      const row = el('div', { class: 'row-item' }, [
        el('div', { class: 'row-main' }, [title, meta, message, status]),
      ]);

      return {
        element: row,
        update(entry) {
          title.textContent = entry.title || EVENT_LABELS[entry.event_type] || '';
          meta.textContent = [
            formatTimestamp(entry.timestamp) || '',
            EVENT_LABELS[entry.event_type] || entry.event_type,
          ]
            .filter(Boolean)
            .join(' · ');
          message.textContent = entry.message || '';

          const severity = SEVERITY[entry.severity] || SEVERITY.info;
          statusIcon.setAttribute('icon', severity.icon);
          status.dataset.tone = severity.tone;
          // The count is the whole point of the anti-spam rule: a run that was
          // collapsed has to say how often it happened (SPEC.md §8).
          statusText.textContent =
            entry.count > 1
              ? `${severity.label} · ${entry.count} keer samengevoegd`
              : severity.label;
        },
      };
    }

    function show(list) {
      entries = list;
      // The backend gives every entry a uuid4; the index is only a fallback so
      // a damaged row can still be listed rather than dropped.
      rowList.sync(
        entries.map((entry, index) => ({ ...entry, id: entry.id || `row-${index}` })),
      );
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
