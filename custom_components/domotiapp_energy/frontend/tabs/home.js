/**
 * The Woning tab (SPEC.md §8 "Woning", §9 and §22).
 *
 * The first real form in this panel, and therefore the first user of
 * `core/forms.js`. Three `ha-form` instances, one per card, each with a schema
 * and a single `value-changed` listener that lives as long as the form does.
 * Nothing here builds an input by hand: `ha-form` already gives every field a
 * label, keyboard operation and a visible focus state, which is most of
 * SPEC.md §23 for free.
 *
 * The save cycle follows SPEC.md §22. Edits go into `draft` and never into
 * `config`; what is on screen as the saved configuration only changes once the
 * backend has confirmed it. While a save is in flight every field is disabled.
 * A stale `expected_revision` is not something to shrug at — the form is
 * reloaded from the configuration the backend returned with the refusal, and
 * the installer is told in plain Dutch that their changes were not saved.
 */

import { createApi, describeError, isRevisionConflict } from '../core/api.js';
import { button, card, el, notice, setVisible } from '../core/dom.js';
import { createForm } from '../core/forms.js';
import { onTap } from '../core/tap.js';

/** The key this tab stores its unsaved edits under. */
const DRAFT = 'home';

/** Volts per phase, for the theoretical maximum hint (SPEC.md §8). */
const VOLTAGE_PER_PHASE = 230;

const CONNECTION_SCHEMA = [
  { name: 'home_name', label: 'Naam van de woning', selector: { text: {} } },
  {
    name: 'phases',
    label: 'Aantal fasen',
    selector: {
      select: {
        mode: 'dropdown',
        options: [
          { value: 1, label: '1 fase' },
          { value: 3, label: '3 fasen' },
        ],
      },
    },
  },
  {
    name: 'main_fuse_a',
    label: 'Hoofdzekering per fase',
    helper: 'In ampère, zoals op de zekering staat.',
    selector: { number: { min: 1, max: 100, step: 1, unit_of_measurement: 'A' } },
  },
  {
    name: 'max_grid_power_w',
    label: 'Maximaal netvermogen',
    helper: 'Het vermogen waarboven DomotiApp Energy waarschuwt.',
    selector: { number: { min: 0, step: 10, unit_of_measurement: 'W' } },
  },
  {
    name: 'peak_warning_percent',
    label: 'Waarschuwen vanaf',
    helper: 'Percentage van het maximale netvermogen.',
    selector: { number: { min: 0, max: 100, step: 1, unit_of_measurement: '%' } },
  },
];

const CONTRACT_SCHEMA = [
  {
    name: 'contract_type',
    label: 'Contractsoort',
    selector: {
      select: {
        mode: 'dropdown',
        options: [
          { value: 'fixed', label: 'Vast tarief' },
          { value: 'dynamic', label: 'Dynamisch tarief' },
        ],
      },
    },
  },
  {
    name: 'fixed_import_price_eur_kwh',
    label: 'Vast leveringstarief (all-in)',
    helper:
      'Alleen nodig bij een vast contract. Het all-in bedrag per kWh, ' +
      'inclusief energiebelasting en btw — dus wat de klant werkelijk betaalt.',
    selector: { number: { min: 0, step: 0.001, unit_of_measurement: '€/kWh' } },
  },
  {
    name: 'energy_tax_eur_kwh',
    label: 'Energiebelasting',
    helper:
      'Een bedrag per kWh, exclusief btw. Nodig zodra een prijsbron de kale ' +
      'marktprijs levert; die wordt hiermee naar een all-in prijs omgerekend.',
    selector: { number: { min: 0, step: 0.0001, unit_of_measurement: '€/kWh' } },
  },
  {
    name: 'supplier_markup_eur_kwh',
    label: 'Opslag leverancier',
    // The same trap as the feed-in cost: several contracts bill a fixed
    // monthly amount, and entering that here would be wrong by orders of
    // magnitude (SPEC.md §8).
    helper:
      'Een bedrag per kWh, exclusief btw — géén vast maandbedrag. Reken een ' +
      'maandbedrag niet om: alleen de opslag per kWh hoort hier.',
    selector: { number: { step: 0.0001, unit_of_measurement: '€/kWh' } },
  },
  {
    name: 'vat_percent',
    label: 'Btw',
    helper: 'Het btw-percentage over de leveringsprijs. In Nederland 21%.',
    selector: { number: { min: 0, max: 100, step: 1, unit_of_measurement: '%' } },
  },
  {
    name: 'feed_in_price_eur_kwh',
    label: 'Terugleververgoeding (all-in)',
    // Unambiguous on purpose: this field is never converted, unlike the price
    // source. Whatever ends up on the invoice per fed-in kWh is what goes here.
    helper:
      'Het vaste bedrag dat de klant per teruggeleverde kWh daadwerkelijk ' +
      'vergoed krijgt. Geen marktprijs en geen percentage: dit veld wordt ' +
      'niet omgerekend.',
    selector: { number: { min: 0, step: 0.001, unit_of_measurement: '€/kWh' } },
  },
  {
    name: 'feed_in_cost_eur_kwh',
    label: 'Terugleverkosten',
    // The warning that matters: several suppliers bill a fixed monthly amount
    // per band, and entering that here would be wrong by two orders of
    // magnitude (SPEC.md §8).
    helper:
      'Een bedrag per teruggeleverde kWh — géén vast maandbedrag. Reken een ' +
      'maandstaffel om, of laat dit leeg.',
    selector: { number: { min: 0, step: 0.001, unit_of_measurement: '€/kWh' } },
  },
  {
    name: 'net_metering_until',
    label: 'Saldering geldt tot',
    helper:
      'De salderingsregeling stopt landelijk op 1 januari 2027. Laat leeg als ' +
      'deze woning niet saldeert; de omslag gaat daarna vanzelf.',
    selector: { date: {} },
  },
  {
    name: 'low_price_threshold_eur_kwh',
    label: 'Lage prijsgrens (all-in)',
    // The consequence of normalising on reading: everything downstream compares
    // all-in prices, so an installer who enters what their market-price sensor
    // shows would set the threshold about three times too low (SPEC.md §16).
    helper:
      'Alleen bij een dynamisch contract. Vergelijk met de all-in prijs, niet ' +
      'met de kale marktprijs van je prijsbron.',
    selector: { number: { min: 0, step: 0.001, unit_of_measurement: '€/kWh' } },
  },
  {
    name: 'high_price_threshold_eur_kwh',
    label: 'Hoge prijsgrens (all-in)',
    helper:
      'Alleen bij een dynamisch contract. Vergelijk met de all-in prijs, niet ' +
      'met de kale marktprijs van je prijsbron.',
    selector: { number: { min: 0, step: 0.001, unit_of_measurement: '€/kWh' } },
  },
];

const ADVICE_SCHEMA = [
  {
    name: 'min_solar_surplus_w',
    label: 'Minimaal zonneoverschot',
    helper: 'Vanaf dit overschot adviseert DomotiApp Energy een apparaat.',
    selector: { number: { min: 0, step: 50, unit_of_measurement: 'W' } },
  },
  {
    name: 'default_strategy',
    label: 'Standaardstrategie',
    selector: {
      select: {
        mode: 'dropdown',
        options: [
          { value: 'comfort', label: 'Comfort' },
          { value: 'balanced', label: 'Gebalanceerd' },
          { value: 'save', label: 'Besparen' },
          { value: 'max_self_consumption', label: 'Maximaal zelf verbruiken' },
        ],
      },
    },
  },
];

/** Every field this tab owns, so anything else in the profile is left alone. */
const EDITED_FIELDS = [
  ...CONNECTION_SCHEMA.map((field) => field.name),
  ...CONTRACT_SCHEMA.map((field) => field.name),
  ...ADVICE_SCHEMA.map((field) => field.name),
];

/** Read the editable fields out of a stored home profile. */
function formDataFrom(home) {
  const data = {};
  for (const name of EDITED_FIELDS) {
    const value = home?.[name];
    if (value !== null && value !== undefined) {
      data[name] = value;
    }
  }
  return data;
}

/**
 * Return only the given field names, dropping the rest.
 *
 * A name that is present but `undefined` is kept, not skipped: that is exactly
 * what a field the installer just cleared looks like, and skipping it would
 * silently restore the previous value.
 */
function only(data, names) {
  const picked = {};
  for (const name of names) {
    picked[name] = data[name];
  }
  return picked;
}

export const homeTab = {
  id: 'home',
  label: 'Woning',
  icon: 'mdi:home-outline',
  adminOnly: true,

  create({ getHass, state }) {
    const element = el('div', { class: 'tab-content' });

    const connection = card('Woning en aansluiting');
    const contract = card('Contract en prijzen');
    const advice = card('Advies');
    const control = card('Bedieningsniveau');

    /** What is on screen. Never written into config (SPEC.md §22). */
    let draft = {};
    /** What the form was last loaded from, to tell "changed" from "same". */
    let saved = {};
    /** The revision the form was filled in against. */
    let revision = null;
    /** What to do once the installer resolves their unsaved changes. */
    let leaveRequested = null;
    let loadedRevision = null;

    /**
     * Merge one card's fields back into the draft.
     *
     * Only that card's own fields, never the whole payload it emits. `ha-form`
     * hands back the complete `data` object it was given with one field
     * changed, so a form that was handed the *shared* draft would re-emit its
     * snapshot of every other card's fields as well — and a card touched later
     * would quietly undo an edit made in a card touched earlier. That reverted
     * the saved profile, not only the hint on screen.
     */
    function changeHandler(names) {
      return (part) => {
        draft = { ...draft, ...only(part, names) };
        state.setDraft(DRAFT, draft);
        refreshDirty();
      };
    }

    const forms = [CONNECTION_SCHEMA, CONTRACT_SCHEMA, ADVICE_SCHEMA].map(
      (schema, index) => {
        const names = schema.map((field) => field.name);
        return {
          names,
          form: createForm(getHass(), schema, changeHandler(names)),
          host: [connection, contract, advice][index],
        };
      },
    );
    for (const { form, host } of forms) {
      host.body.appendChild(form.element);
    }

    const maxPowerNotice = notice('mdi:calculator-variant-outline');
    connection.body.appendChild(maxPowerNotice.element);

    // The one place the whole price composition is stated in plain Dutch. Every
    // number below and every threshold above is an all-in amount, and an
    // installer who does not know that enters the wrong figure without any
    // error to warn them (SPEC.md §16).
    const priceNotice = notice('mdi:cash-multiple');
    priceNotice.set(
      'DomotiApp Energy rekent overal met de all-in prijs: ' +
        '(marktprijs + opslag + energiebelasting) × (1 + btw). Een prijsbron ' +
        'die de kale marktprijs levert wordt daarmee omgerekend; een bron die ' +
        'al all-in is, wordt ongewijzigd gebruikt. Bij de bron zelf geef je aan ' +
        'welke van de twee het is.',
      { tone: 'info' },
    );
    contract.body.appendChild(priceNotice.element);

    // --- The control level, fixed in 0.1.0 ----------------------------------
    const controlForm = createForm(
      getHass(),
      [
        {
          name: 'control_level',
          label: 'Bedieningsniveau',
          selector: {
            select: {
              mode: 'dropdown',
              options: [
                { value: 'advice_only', label: 'Alleen adviseren' },
                { value: 'approval_required', label: 'Vragen om goedkeuring' },
                { value: 'automatic', label: 'Automatisch aansturen' },
              ],
            },
          },
        },
      ],
      () => {},
    );
    controlForm.setData({ control_level: 'advice_only' });
    controlForm.setDisabled(true);
    const controlNotice = notice('mdi:lock-outline');
    controlNotice.set(
      'DomotiApp Energy meet, rekent en adviseert; het stuurt in deze versie ' +
        'geen enkel apparaat aan. De andere bedieningsniveaus staan hier al wel, ' +
        'maar zijn nog niet beschikbaar.',
      { tone: 'info' },
    );
    control.body.append(controlForm.element, controlNotice.element);

    // --- Actions ------------------------------------------------------------
    const saveButton = button('Opslaan', { primary: true });
    const resetButton = button('Wijzigingen verwerpen');
    const saveNotice = notice('mdi:content-save-outline');
    const leaveNotice = notice('mdi:alert-outline');
    const leaveDiscard = button('Verwerpen en verdergaan');
    const leaveStay = button('Hier blijven');
    const leaveActions = el('div', { class: 'actions' }, [leaveDiscard, leaveStay]);
    setVisible(leaveActions, false);

    advice.body.append(
      el('div', { class: 'actions' }, [saveButton, resetButton]),
      saveNotice.element,
      leaveNotice.element,
      leaveActions,
    );

    element.append(
      connection.element,
      contract.element,
      advice.element,
      control.element,
    );

    // --- Behaviour ----------------------------------------------------------

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
      updateMaxPowerHint();
    }

    function updateMaxPowerHint() {
      const phases = Number(draft.phases) || 0;
      const fuse = Number(draft.main_fuse_a) || 0;
      if (!phases || !fuse) {
        maxPowerNotice.set('');
        return;
      }
      const theoretical = phases * VOLTAGE_PER_PHASE * fuse;
      const above = (Number(draft.max_grid_power_w) || 0) > theoretical;
      // A warning, never a block: the installer may knowingly enter a value
      // above the theoretical maximum (SPEC.md §8).
      maxPowerNotice.set(
        above
          ? `Het ingevulde netvermogen ligt boven het theoretische maximum van ` +
              `${theoretical} W (${phases} × 230 V × ${fuse} A). Controleer de ` +
              `hoofdzekering.`
          : `Theoretisch maximum: ${theoretical} W (${phases} × 230 V × ${fuse} A).`,
        { tone: above ? 'warning' : 'info' },
      );
    }

    function loadFrom(config) {
      saved = formDataFrom(config?.home);
      draft = { ...saved };
      revision = config?.revision ?? null;
      loadedRevision = revision;
      // Each card is handed only its own fields, so it cannot carry a stale
      // copy of another card's values.
      for (const { form, names } of forms) {
        form.setData(only(draft, names));
      }
      state.clearDraft(DRAFT);
      refreshDirty();
    }

    /**
     * The home profile to send.
     *
     * Every editable field is present, with an explicitly cleared one as
     * `null` rather than absent. The backend tells the two apart on purpose:
     * an absent `net_metering_until` means "an older file, take the default"
     * while an explicit null means "this home does not net-meter". Leaving the
     * key out would silently hand the default back (SPEC.md §16).
     */
    function payload() {
      const home = {};
      for (const name of EDITED_FIELDS) {
        home[name] = draft[name] ?? null;
      }
      return home;
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
        const result = await createApi(getHass()).updateHome(revision, payload());
        const updated = {
          ...state.get().config,
          home: result.item,
          revision: result.revision,
        };
        state.setConfig(updated);
        loadFrom(updated);
        saveNotice.set('De woninggegevens zijn opgeslagen.', { tone: 'success' });
      } catch (error) {
        if (isRevisionConflict(error)) {
          // Someone else changed the configuration while this form was open.
          // Reloading is the safe answer: keeping the draft would invite
          // overwriting a change nobody here has seen.
          state.setConfig(error.config);
          loadFrom(error.config);
          saveNotice.set(
            'De configuratie is intussen ergens anders gewijzigd. Je wijzigingen ' +
              'zijn niet opgeslagen; het formulier is opnieuw geladen met de ' +
              'actuele gegevens.',
            { tone: 'warning' },
          );
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
      // edit in progress: an unrelated update must not wipe the form.
      if (config.revision !== loadedRevision && !isDirty()) {
        loadFrom(config);
      }
      for (const { form } of forms) {
        form.setHass(getHass());
      }
      controlForm.setHass(getHass());
    }

    /**
     * Refuse to leave with unsaved changes, and ask inside the tab itself.
     *
     * A browser `confirm()` would be shorter, but it is a modal the panel
     * neither controls nor styles. This keeps the question next to the changes
     * it is about (SPEC.md §22).
     */
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
