/**
 * The Voorkeuren tab (SPEC.md §8, §9 and §22).
 *
 * The simplest of the configuration tabs: one profile, one form, no rows and no
 * dialog. It follows the Woning tab exactly — a draft that never touches the
 * saved configuration, fields locked while a save is in flight, and nothing
 * claiming success before the backend confirms it (SPEC.md §22).
 *
 * The three cards are the three questions these settings answer: when may we
 * speak, what do we weigh, and how much do we show.
 */

import {
  createApi,
  describeError,
  fieldErrors,
  isRevisionConflict,
} from '../core/api.js';
import { button, card, el, notice, setVisible } from '../core/dom.js';
import {
  createForm,
  describeOrphanedErrors,
  splitFieldErrors,
} from '../core/forms.js';
import { onTap } from '../core/tap.js';

/** The key this tab stores its unsaved edits under. */
const DRAFT = 'preferences';

const QUIET_SCHEMA = [
  {
    name: 'quiet_hours_start',
    label: 'Stille uren van',
    // The old wording — "krijgen lawaaiige apparaten geen advies" — described
    // what the quiet hours did until 0.9.0: they suppressed the advice. They
    // defer it now, and the sentence has to follow the behaviour or it teaches
    // the installer something that is no longer true (SPEC.md §42.2).
    helper:
      'Tussen deze tijden raadt DomotiApp Energy aan om te wachten met ' +
      'lawaaiige apparaten. Het advies verdwijnt niet, het zegt tot hoe laat. ' +
      'Een venster over middernacht is het normale geval: 22:00 tot 07:00.',
    // Home Assistant's own time selector takes no_second, and uses it in its
    // own schemas. Quiet hours to the second is a precision nobody has.
    selector: { time: { no_second: true } },
  },
  {
    name: 'quiet_hours_end',
    label: 'Stille uren tot',
    selector: { time: { no_second: true } },
  },
];

const WEIGHING_SCHEMA = [
  {
    name: 'prefer_solar',
    label: 'Zonneoverschot benutten',
    helper: 'Adviseer een apparaat wanneer er genoeg eigen opwek is.',
    selector: { boolean: {} },
  },
  {
    name: 'prefer_low_price',
    label: 'Op prijs adviseren',
    helper:
      'Alleen van toepassing bij een dynamisch contract; bij een vast tarief ' +
      'wordt er nooit op prijs geadviseerd.',
    selector: { boolean: {} },
  },
];

/**
 * The savings threshold, alone in its own card.
 *
 * It is a filter and not a weight, and it renders as a boxed number between
 * three switches, which made it read as an appendix of the switch above it.
 * Its own card says what it is, and gives its long explanation room.
 */
const THRESHOLD_SCHEMA = [
  {
    name: 'min_savings_eur',
    label: 'Minimale besparing',
    // The threshold filters exactly one situation, and saying which one is the
    // difference between a useful setting and a silent one (SPEC.md §8).
    helper:
      'Advies met een berekende besparing bóven nul maar onder dit bedrag ' +
      'wordt niet getoond. Advies zonder berekenbare besparing — veiligheid, ' +
      'piek, ontbrekende gegevens — blijft altijd staan, net als advies dat op ' +
      'nul uitkomt zolang de saldering loopt.',
    selector: { number: { min: 0, step: 0.01, unit_of_measurement: '€' } },
  },
];

const DISPLAY_SCHEMA = [
  // First in its card on purpose: a boxed number between switches reads as an
  // appendix of the switch above it, which is what happened here.
  {
    name: 'max_advice_count',
    label: 'Aantal adviezen',
    helper: 'Hoeveel adviezen er hoogstens tegelijk getoond worden.',
    selector: { number: { min: 1, max: 5, step: 1, mode: 'box' } },
  },
  {
    name: 'show_technical_explanation',
    label: 'Technische onderbouwing tonen',
    selector: { boolean: {} },
  },
  {
    name: 'show_estimated_savings',
    label: 'Geschatte besparing tonen',
    selector: { boolean: {} },
  },
  // "Betrouwbaarheid tonen" was removed in 0.4.1 together with the label it
  // switched: a setting for something nobody should have been reading.
];

/** Every field this tab owns, so anything else is left alone. */
const EDITED_FIELDS = [
  ...QUIET_SCHEMA.map((field) => field.name),
  ...WEIGHING_SCHEMA.map((field) => field.name),
  ...THRESHOLD_SCHEMA.map((field) => field.name),
  ...DISPLAY_SCHEMA.map((field) => field.name),
];

/** The Dutch label of any field this tab knows, rendered or not. */
function labelForField(name) {
  const field = [
    ...QUIET_SCHEMA,
    ...WEIGHING_SCHEMA,
    ...THRESHOLD_SCHEMA,
    ...DISPLAY_SCHEMA,
  ].find((entry) => entry.name === name);
  return field?.label ?? null;
}

/** Read the editable fields out of the stored preferences. */
function formDataFrom(preferences) {
  const data = {};
  for (const name of EDITED_FIELDS) {
    const value = preferences?.[name];
    if (value !== null && value !== undefined) {
      data[name] = value;
    }
  }
  return data;
}

/**
 * Return only the given field names, dropping the rest.
 *
 * A name that is present but `undefined` is kept, not skipped: that is what a
 * field the installer just cleared looks like, and skipping it would silently
 * restore the previous value.
 */
function only(data, names) {
  const picked = {};
  for (const name of names) {
    picked[name] = data[name];
  }
  return picked;
}

export const preferencesTab = {
  id: 'preferences',
  label: 'Mijn voorkeuren',
  icon: 'mdi:tune',

  create({ getHass, state }) {
    const element = el('div', { class: 'tab-content' });

    const quiet = card('Stille uren');
    const weighing = card('Wat weegt mee');
    const threshold = card('Wanneer een advies de moeite waard is');
    const display = card('Wat je te zien krijgt');

    let draft = {};
    let saved = {};
    let revision = null;
    let loadedRevision = null;
    let leaveRequested = null;

    /**
     * Merge one card's fields back into the draft.
     *
     * Only that card's own fields, never the whole payload it emits — the
     * mistake that made one card undo another in phase 7b.
     */
    function changeHandler(names) {
      return (part) => {
        draft = { ...draft, ...only(part, names) };
        state.setDraft(DRAFT, draft);
        refreshDirty();
      };
    }

    const forms = [
      QUIET_SCHEMA,
      WEIGHING_SCHEMA,
      THRESHOLD_SCHEMA,
      DISPLAY_SCHEMA,
    ].map((schema, index) => {
      const names = schema.map((field) => field.name);
      return {
        names,
        form: createForm(getHass(), schema, changeHandler(names)),
        host: [quiet, weighing, threshold, display][index],
      };
    });
    for (const { form, host } of forms) {
      host.body.appendChild(form.element);
    }

    const saveButton = button('Opslaan', { primary: true });
    const resetButton = button('Wijzigingen verwerpen');
    const saveNotice = notice('mdi:content-save-outline');
    const orphanNotice = notice('mdi:alert-circle-outline');
    const leaveNotice = notice('mdi:alert-outline');
    const leaveDiscard = button('Verwerpen en verdergaan');
    const leaveStay = button('Hier blijven');
    const leaveActions = el('div', { class: 'actions' }, [leaveDiscard, leaveStay]);
    setVisible(leaveActions, false);

    const actions = el('div', { class: 'tab-actions' }, [
      el('div', { class: 'actions' }, [saveButton, resetButton]),
      orphanNotice.element,
      saveNotice.element,
      leaveNotice.element,
      leaveActions,
    ]);

    element.append(
      quiet.element,
      weighing.element,
      threshold.element,
      display.element,
      actions,
    );

    function isDirty() {
      return EDITED_FIELDS.some(
        (name) => (draft[name] ?? null) !== (saved[name] ?? null),
      );
    }

    function refreshDirty() {
      const dirty = isDirty();
      saveButton.disabled = !dirty;
      resetButton.disabled = !dirty;
      if (!dirty) {
        setVisible(leaveNotice.element, false);
        setVisible(leaveActions, false);
      }
    }

    /**
     * Put each backend validation message next to the field it is about.
     *
     * This tab renders every field it has, so today nothing can be orphaned.
     * It goes through the same split anyway: the moment a preference becomes
     * conditional, the message keeps landing instead of quietly disappearing
     * (core/forms.js).
     */
    function showIssues(config) {
      const errors = fieldErrors(config?.issues, 'preferences') || {};
      const rendered = forms.flatMap(({ form }) =>
        (form.element.schema || []).map((field) => field.name),
      );
      const { shown, orphaned } = splitFieldErrors(errors, rendered);

      for (const { form, names } of forms) {
        const mine = {};
        for (const name of names) {
          if (name in shown) {
            mine[name] = shown[name];
          }
        }
        form.setErrors(Object.keys(mine).length ? mine : null);
      }

      orphanNotice.set(describeOrphanedErrors(orphaned, labelForField), {
        tone: 'warning',
      });
    }

    function loadFrom(config) {
      saved = formDataFrom(config?.preferences);
      draft = { ...saved };
      revision = config?.revision ?? null;
      loadedRevision = revision;
      for (const { form, names } of forms) {
        form.setData(only(draft, names));
      }
      showIssues(config);
      state.clearDraft(DRAFT);
      refreshDirty();
    }

    /** Every editable field, with a cleared one as null rather than absent. */
    function payload() {
      const preferences = {};
      for (const name of EDITED_FIELDS) {
        preferences[name] = draft[name] ?? null;
      }
      return preferences;
    }

    function setBusy(busy) {
      for (const { form } of forms) {
        form.setDisabled(busy);
      }
      saveButton.disabled = busy || !isDirty();
      resetButton.disabled = busy || !isDirty();
    }

    async function save() {
      // Nothing may claim success before the backend confirms it (SPEC.md §22).
      state.setSaving(true);
      setBusy(true);
      saveNotice.set('Bezig met opslaan…', { tone: 'info' });

      try {
        const result = await createApi(getHass()).updatePreferences(
          revision,
          payload(),
        );
        const updated = {
          ...state.get().config,
          preferences: result.item,
          revision: result.revision,
          issues: result.issues ?? state.get().config?.issues,
        };
        state.setConfig(updated);
        loadFrom(updated);
        saveNotice.set('De voorkeuren zijn opgeslagen.', { tone: 'success' });
      } catch (error) {
        if (isRevisionConflict(error)) {
          // The same split as the other three forms (SPEC.md §49.4): reload
          // only when the change was in *these* fields, because that is the
          // only case where keeping the draft would hide someone else's work.
          const alsoHere =
            JSON.stringify(formDataFrom(error.config?.preferences)) !==
            JSON.stringify(saved);
          state.setConfig(error.config);
          revision = error.config?.revision ?? revision;
          if (alsoHere) {
            loadFrom(error.config);
            saveNotice.set(
              'De voorkeuren zijn intussen ergens anders gewijzigd. Het ' +
                'formulier is opnieuw geladen met de actuele gegevens, zodat je ' +
                'niet overschrijft wat je niet gezien hebt.',
              { tone: 'warning' },
            );
          } else {
            saveNotice.set(
              'Er is intussen ergens anders iets aan de configuratie gewijzigd, ' +
                'maar niet aan je voorkeuren. Je invoer staat er nog; druk ' +
                'opnieuw op Opslaan om hem te bewaren.',
              { tone: 'warning' },
            );
          }
        } else {
          saveNotice.set(describeError(error), { tone: 'warning' });
        }
      } finally {
        state.setSaving(false);
        setBusy(false);
      }
    }

    onTap(saveButton, () => {
      if (!saveButton.disabled) {
        save();
      }
    });
    onTap(resetButton, () => {
      loadFrom(state.get().config);
      saveNotice.set('');
    });
    onTap(leaveDiscard, () => {
      const proceed = leaveRequested;
      leaveRequested = null;
      loadFrom(state.get().config);
      saveNotice.set('');
      proceed?.();
    });
    onTap(leaveStay, () => {
      leaveRequested = null;
      setVisible(leaveNotice.element, false);
      setVisible(leaveActions, false);
    });

    function update(panelState) {
      const config = panelState.config;
      if (!config) {
        return;
      }
      // Reload only when the backend truth actually moved, and never over an
      // edit in progress.
      if (config.revision !== loadedRevision && !isDirty()) {
        loadFrom(config);
      }
      for (const { form } of forms) {
        form.setHass(getHass());
      }
    }

    /** Refuse to leave with unsaved changes, and ask inside the tab itself. */
    function canLeave(proceed) {
      if (!isDirty()) {
        return true;
      }
      leaveRequested = proceed;
      leaveNotice.set(
        'Je hebt wijzigingen die nog niet zijn opgeslagen. Sla ze op, of verwerp ' +
          'ze om verder te gaan.',
        { tone: 'warning' },
      );
      setVisible(leaveActions, true);
      return false;
    }

    return { element, update, canLeave };
  },
};
