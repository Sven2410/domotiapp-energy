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
import {
  MANAGED_NOTICE,
  applyRole,
  messageForRole,
} from '../core/roles.js';
import { onTap } from '../core/tap.js';

/** The key this tab stores its unsaved edits under. */
const DRAFT = 'home';

/** Volts per phase, for the theoretical maximum hint (SPEC.md §8). */
const VOLTAGE_PER_PHASE = 230;

/**
 * The number selector every price field uses.
 *
 * One step for all of them, and fine enough for what a real tariff looks like.
 * They used to disagree — 0,001 on some fields and 0,0001 on others, for the
 * same unit on the same card — and both were coarser than the six decimals the
 * backend keeps and a supplier actually bills: 0,241710 is a real figure from a
 * real contract. A `step` reaches the browser's own number validation, so a
 * coarse one is not merely a hint about the arrows; it is a rule about which
 * prices may be typed at all.
 *
 * Note that `step` is the only part of this that is locale-independent. Whether
 * the field accepts "0,24" or "0.24" is decided by the browser's language, not
 * by us — see the README.
 */
const PRICE_SELECTOR = {
  number: { min: 0, step: 0.000001, unit_of_measurement: '€/kWh' },
};

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

/**
 * The contract fields, filtered by the contract that is actually in force.
 *
 * A fixed tariff on a dynamic contract with "alleen nodig bij een vast
 * contract" underneath is the same fault as a battery level on a dishwasher:
 * a question with no answer, kept on screen.
 *
 * **The value is kept, and still sent.** This is the opposite of what the
 * device form does with an orphaned field, and the difference is deliberate: a
 * device type says what the thing *is*, so a battery level on a dishwasher is
 * meaningless and is dropped. A contract type is a mode that flips back and
 * forth — a customer who moves to a dynamic contract for a year has not stopped
 * having a fixed tariff on file. Dropping it would mean retyping it on the way
 * back, and there is nothing to gain by forgetting it.
 *
 * The rule, for both forms: a value is dropped when the new choice makes it
 * meaningless, and kept when it is merely inactive.
 */
function contractSchema(draft, config) {
  const dynamic = draft.contract_type === 'dynamic';
  const onlyFor = {
    fixed_import_price_eur_kwh: 'fixed',
    low_price_threshold_eur_kwh: 'dynamic',
    high_price_threshold_eur_kwh: 'dynamic',
    energy_tax_eur_kwh: 'dynamic',
    supplier_markup_eur_kwh: 'dynamic',
    vat_percent: 'dynamic',
  };
  const allIn = allInPriceSource(config);
  const feedInSource = feedInPriceSource(config);
  // **The composition fields follow the market price, not the contract.** They
  // exist to convert a bare market reading, so they belong on screen wherever
  // there is one to convert — including a fixed contract, which was a dead end
  // until SPEC.md §49.10: with a market-basis source and an empty tariff field
  // there was no price, no way to reach these three, and no message saying why.
  const convertible = marketPriceSource(config);
  return CONTRACT_SCHEMA.filter((field) => {
    const needs = onlyFor[field.name];
    if (convertible && COMPOSITION_FIELDS.includes(field.name)) {
      return true;
    }
    return !needs || needs === (dynamic ? 'dynamic' : 'fixed');
  }).map((field) => {
    if (allIn && COMPOSITION_FIELDS.includes(field.name)) {
      return { ...field, disabled: true };
    }
    // The fixed feed-in tariff is what a linked feed-in source replaces, so it
    // goes inactive the moment one exists — the same rule as the composition
    // fields above, and the value is kept so removing the source restores it.
    if (feedInSource && field.name === 'feed_in_price_eur_kwh') {
      return { ...field, disabled: true };
    }
    // The markup only converts a *market* feed-in reading. With no source, or
    // one that already reports the net rate, it has nothing to convert.
    if (
      field.name === 'feed_in_markup_eur_kwh' &&
      feedInSource?.price_basis !== 'market'
    ) {
      return { ...field, disabled: true };
    }
    return field;
  });
}

/**
 * The three fields that only exist to convert a bare market price.
 *
 * They are the price composition of SPEC.md §16 —
 * `(markt + opslag + belasting) x (1 + btw)` — and they have a job only when
 * something has to be converted.
 */
const COMPOSITION_FIELDS = [
  'energy_tax_eur_kwh',
  'supplier_markup_eur_kwh',
  'vat_percent',
];

/**
 * The linked price source that already reports an all-in price, if any.
 *
 * When one exists the three composition fields have nothing to do: the price
 * arrives finished and is used unchanged, so an energy tax entered here would
 * be applied to nothing. Asking for it anyway invites the installer to fill in
 * three numbers that will never be read, and then to wonder why the price on
 * the Overzicht does not match them.
 *
 * They are **disabled rather than hidden**, and their values are kept. An
 * installer has to be able to see what a market-price source would need, and a
 * source that changes from all-in to market must not find its composition
 * wiped (SPEC.md §16). This is the same rule the contract fields follow: drop a
 * value when the choice makes it meaningless, keep it when it is merely
 * inactive.
 */
function allInPriceSource(config) {
  return (config?.sources || []).find(
    (source) =>
      source.type === 'current_price' &&
      source.enabled !== false &&
      source.price_basis === 'all_in',
  );
}

/**
 * The linked price source that reports a bare market price, if any.
 *
 * The counterpart of :func:`allInPriceSource`, and the reason the composition
 * fields appear at all: a market reading is unusable until the energy tax, the
 * supplier markup and the VAT turn it into what the customer pays (SPEC.md §16).
 *
 * **Deliberately not filtered by contract type.** Leaving the tariff field
 * empty on a fixed contract makes this source the price (SPEC.md §48.1), and
 * even with a tariff filled in the source is still read and still has to be
 * convertible or it is reported as unreadable. Both are true regardless of what
 * the contract is called.
 */
function marketPriceSource(config) {
  return (config?.sources || []).find(
    (source) =>
      source.type === 'current_price' &&
      source.enabled !== false &&
      source.price_basis === 'market',
  );
}

/**
 * The linked feed-in price source, if any.
 *
 * Its existence is the statement that this home's feed-in tariff varies, so it
 * takes over from the fixed amount — the same reading a source row gets
 * everywhere else. Whether it reports a market or a net rate then decides
 * whether the markup is needed.
 */
function feedInPriceSource(config) {
  return (config?.sources || []).find(
    (source) => source.type === 'feed_in_price' && source.enabled !== false,
  );
}

/**
 * Whether net metering still applies, judged from the draft.
 *
 * Read from the draft rather than the backend so the notice follows the date
 * the installer is typing: clearing the field has to change the explanation
 * straight away, not after a save.
 *
 * Mirrors `HomeProfile.is_net_metering_active`: an empty date means this home
 * does not net-meter at all.
 */
function netMeteringActive(draft) {
  const until = draft?.net_metering_until;
  if (!until) {
    return false;
  }
  const ends = new Date(`${until}T00:00:00`);
  if (Number.isNaN(ends.getTime())) {
    return false;
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return today < ends;
}

/** A stored ISO date as Dutch day-month-year, for use inside a sentence. */
function formatDate(value) {
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString('nl-NL', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

/** Contract fields that are filled in but not in force right now. */
function inactiveContractFields(draft, config) {
  const shown = new Set(contractSchema(draft, config).map((field) => field.name));
  return CONTRACT_SCHEMA.filter(
    (field) =>
      !shown.has(field.name) &&
      draft[field.name] !== undefined &&
      draft[field.name] !== null &&
      draft[field.name] !== '',
  ).map((field) => field.label);
}

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
      'Het all-in bedrag per kWh, inclusief energiebelasting en btw — dus wat ' +
      'de klant werkelijk betaalt.',
    selector: PRICE_SELECTOR,
  },
  {
    name: 'energy_tax_eur_kwh',
    label: 'Energiebelasting',
    helper:
      'Een bedrag per kWh, exclusief btw. Nodig zodra een prijsbron de kale ' +
      'marktprijs levert; die wordt hiermee naar een all-in prijs omgerekend.',
    selector: PRICE_SELECTOR,
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
    // No minimum, unlike every other price field: a supplier markup can be
    // negative when the contract gives a discount per kWh.
    selector: { number: { step: 0.000001, unit_of_measurement: '€/kWh' } },
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
    selector: PRICE_SELECTOR,
  },
  {
    name: 'feed_in_markup_eur_kwh',
    label: 'Inhouding leverancier op teruglevering',
    // The feed-in mirror of the supplier markup, and the only term its formula
    // needs: no energy tax and no VAT enter it (SPEC.md §16).
    helper:
      'Wat de leverancier per teruggeleverde kWh inhoudt op de marktprijs. ' +
      'Alleen nodig als je terugleverprijsbron de kale marktprijs levert. ' +
      'Vul 0 in als er niets wordt ingehouden.',
    // No minimum: a supplier could in principle pay above the market price.
    selector: { number: { step: 0.000001, unit_of_measurement: '€/kWh' } },
  },
  {
    name: 'feed_in_cost_eur_kwh',
    label: 'Terugleverkosten',
    // Two warnings in one field. Several suppliers bill a fixed monthly amount
    // per band, and entering that here would be wrong by two orders of
    // magnitude (SPEC.md §8). And empty is not zero: under net metering the
    // avoided feed-in cost is the *entire* saving, so a blank field is the
    // difference between "we cannot work this out" and "it saves nothing".
    helper:
      'Een bedrag per teruggeleverde kWh — géén vast maandbedrag. Reken een ' +
      'maandstaffel om. Vul 0 in als deze aansluiting geen terugleverkosten ' +
      'betaalt; laat het leeg als je het niet weet, dan toont de coach geen ' +
      'geschatte besparing in plaats van een bedrag dat op een aanname rust.',
    selector: PRICE_SELECTOR,
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
      'Vergelijk met de all-in prijs, niet met de kale marktprijs van je ' +
      'prijsbron.',
    selector: PRICE_SELECTOR,
  },
  {
    name: 'high_price_threshold_eur_kwh',
    label: 'Hoge prijsgrens (all-in)',
    helper:
      'Vergelijk met de all-in prijs, niet met de kale marktprijs van je ' +
      'prijsbron.',
    selector: PRICE_SELECTOR,
  },
];

/**
 * Waar het paneel naartoe mag navigeren (SPEC.md §62).
 *
 * **De hulpteksten noemen het gevolg en niet de vorm.** "Dit veld is optioneel"
 * zegt een installateur niets; "de bewoner kan dit paneel dan niet verlaten"
 * zegt hem precies wanneer hij het moet invullen — en dat is het enige moment
 * waarop hij het weet, want er is met opzet geen vraag "is dit een wandtablet".
 */
const NAVIGATION_SCHEMA = [
  {
    name: 'home_dashboard_path',
    label: 'Terug naar dashboard',
    helper:
      'Het adres van het hoofddashboard van deze woning, bijvoorbeeld ' +
      '/lovelace/0. Zonder dit adres verschijnt er geen terugknop. Op een ' +
      'wandtablet zonder zijbalk kan de bewoner dit paneel dan niet verlaten.',
    selector: { text: {} },
  },
  {
    name: 'energy_dashboard_path',
    label: 'Energiedashboard',
    helper:
      'Waar het verbruik in kWh van deze woning staat, meestal /energy. ' +
      'Zonder dit adres noemt het Overzicht het dashboard wel, maar zonder ' +
      'link — zodat niemand op een wandtablet ergens belandt waar hij niet ' +
      'meer wegkomt.',
    selector: { text: {} },
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
  ...NAVIGATION_SCHEMA.map((field) => field.name),
];

/**
 * The Dutch label of any field this tab knows, rendered or not.
 *
 * Needed precisely for the fields that are *not* rendered: a message about the
 * energy tax has to name it, because the question itself is off screen.
 */
function labelForField(name) {
  const field = [
    ...CONNECTION_SCHEMA,
    ...CONTRACT_SCHEMA,
    ...ADVICE_SCHEMA,
    ...NAVIGATION_SCHEMA,
  ].find(
    (entry) => entry.name === name,
  );
  return field?.label ?? null;
}

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

  create({ getHass, state }) {
    const element = el('div', { class: 'tab-content' });

    const connection = card('Woning en aansluiting');
    const contract = card('Contract en prijzen');
    const advice = card('Adviesinstellingen');
    const navigation = card('Navigatie');
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
    /** The contract fields currently on screen, so they only move when needed. */
    let contractKey = '';
    /**
     * The contract field names that are on screen right now.
     *
     * The merge below has to know this, and knowing it *at the moment of the
     * event* is the whole point. `only()` deliberately writes `undefined` for a
     * name that is absent from the payload, because that is what a field the
     * installer just cleared looks like. The contract card is handed only the
     * fields of the contract in force, so every field of the *other* contract is
     * absent from everything it emits — and merging against the full schema
     * therefore cleared them, before they had ever been on screen. One switch of
     * the contract type wiped the fixed tariff, the energy tax, the supplier
     * markup, the VAT and both price thresholds from the draft, and `payload()`
     * sends `null` for a missing field, so saving wrote that loss to storage
     * while the notice underneath claimed the values were kept.
     */
    let visibleContractNames = CONTRACT_SCHEMA.map((field) => field.name);

    /**
     * Merge one card's fields back into the draft.
     *
     * Only that card's own fields, never the whole payload it emits. `ha-form`
     * hands back the complete `data` object it was given with one field
     * changed, so a form that was handed the *shared* draft would re-emit its
     * snapshot of every other card's fields as well — and a card touched later
     * would quietly undo an edit made in a card touched earlier. That reverted
     * the saved profile, not only the hint on screen.
     *
     * `namesNow` is a function rather than a list because the contract card's
     * set of fields moves: it has to be read when the event fires, not when the
     * handler was built.
     */
    function changeHandler(namesNow) {
      return (part) => {
        draft = { ...draft, ...only(part, namesNow()) };
        state.setDraft(DRAFT, draft);
        refreshDirty();
      };
    }

    const forms = [
      CONNECTION_SCHEMA,
      CONTRACT_SCHEMA,
      ADVICE_SCHEMA,
      NAVIGATION_SCHEMA,
    ].map(
      (schema, index) => {
        const names = schema.map((field) => field.name);
        // The contract card asks a different set per contract type, so it is
        // the one whose schema moves; the other two are fixed.
        const conditional = index === 1;
        return {
          names,
          conditional,
          form: createForm(
            getHass(),
            schema,
            changeHandler(conditional ? () => visibleContractNames : () => names),
          ),
          host: [connection, contract, advice, navigation][index],
        };
      },
    );
    for (const { form, host } of forms) {
      host.body.appendChild(form.element);
    }

    const maxPowerNotice = notice('mdi:calculator-variant-outline');
    connection.body.appendChild(maxPowerNotice.element);

    // **Een mededeling, geen gebrek** (SPEC.md §62.6). Bij een woning met een
    // zijbalk is een terugknop overbodig, dus dit hoort geen waarschuwing te
    // zijn en het hoort al helemaal niet in de datakwaliteit: die zou een eis
    // stellen die zo'n woning niet kan afvinken.
    const navigationNotice = notice('mdi:tablet-dashboard');
    navigation.body.appendChild(navigationNotice.element);

    const inactiveNotice = notice('mdi:archive-outline');

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
    // Why three fields are greyed out. Without it the installer sees inputs
    // that refuse to be filled in and no reason given (SPEC.md §16).
    const compositionNotice = notice('mdi:database-arrow-right-outline');
    // The feed-in side has its own conversion and therefore its own
    // explanation: saying "all-in" here would be exactly wrong.
    const feedInNotice = notice('mdi:transmission-tower-export');
    // Why the feed-in amounts are inert until net metering ends.
    const netMeteringNotice = notice('mdi:calendar-clock');
    contract.body.append(
      priceNotice.element,
      compositionNotice.element,
      netMeteringNotice.element,
      feedInNotice.element,
      inactiveNotice.element,
    );

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
    // The catch-all for validation messages whose field is not on screen. It
    // sits with the actions rather than in a card, because a hidden field
    // belongs to no card the installer can see.
    const orphanNotice = notice('mdi:alert-circle-outline');
    const leaveNotice = notice('mdi:alert-outline');
    const leaveDiscard = button('Verwerpen en verdergaan');
    const leaveStay = button('Hier blijven');
    const leaveActions = el('div', { class: 'actions' }, [leaveDiscard, leaveStay]);
    setVisible(leaveActions, false);

    // The actions belong to the tab, not to the card they happen to sit under.
    // Inside "Adviesinstellingen" they read as if they saved that card alone.
    // The save row is hidden for a resident, but the notices below it are not:
    // he has to be able to read what is wrong even though the fix is a phone
    // call (SPEC.md §33.8).
    const saveActions = el('div', { class: 'actions' }, [saveButton, resetButton]);
    // Who manages these fields, for a resident looking at a form full of
    // greyed-out inputs with no explanation (SPEC.md §33.7).
    const managedNotice = notice('mdi:shield-account-outline');

    const actions = el('div', { class: 'tab-actions' }, [
      saveActions,
      managedNotice.element,
      orphanNotice.element,
      saveNotice.element,
      leaveNotice.element,
      leaveActions,
    ]);

    element.append(
      connection.element,
      contract.element,
      advice.element,
      navigation.element,
      control.element,
      actions,
    );

    // --- Behaviour ----------------------------------------------------------

    /**
     * Whether this user may edit anything here.
     *
     * The whole tab is installer territory (SPEC.md §33.4): this describes what
     * the home *is*, and a resident who spots a wrong main fuse rings us rather
     * than correcting it himself. Starting at `true` and being corrected on the
     * first `update()` is safe because nothing can be saved before the backend
     * has answered anyway, and the backend refuses regardless.
     */
    let isAdmin = true;

    /** Push the current role into every form, the schema included. */
    function applyRoleToForms() {
      forms[0].form.setSchema(applyRole(CONNECTION_SCHEMA, DRAFT, isAdmin));
      forms[2].form.setSchema(applyRole(ADVICE_SCHEMA, DRAFT, isAdmin));
      forms[3].form.setSchema(applyRole(NAVIGATION_SCHEMA, DRAFT, isAdmin));
      // The contract card builds its own schema per contract type, so it is
      // rebuilt rather than assigned here; clearing the key forces that.
      contractKey = '';
      refreshContractFields();
      setVisible(saveActions, isAdmin);
      managedNotice.set(isAdmin ? '' : MANAGED_NOTICE, { tone: 'info' });
    }

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
      updateNavigationHint();
      refreshContractFields();
      // After the schema, never before: which fields are rendered decides where
      // each message lands. Switching the contract type re-runs this, so an
      // error that becomes invisible moves to the notice at that moment.
      showIssues(state.get().config);
    }

    /**
     * Show the contract fields that are in force, and say what is kept.
     *
     * The values of the other contract stay in the draft and are still sent, so
     * switching back restores them; the notice is what keeps that from being
     * invisible.
     */
    function refreshContractFields() {
      const config = state.get().config;
      const schema = applyRole(contractSchema(draft, config), DRAFT, isAdmin);
      const names = schema.map((field) => field.name);
      // The disabled flags belong in the key as well: linking an all-in price
      // source changes no field name, only whether three of them accept input,
      // and a key built from names alone would leave the old schema in place.
      const key = JSON.stringify(schema.map((field) => [field.name, !!field.disabled]));
      if (key !== contractKey) {
        contractKey = key;
        // Update this together with the schema and never apart from it: the
        // merge in changeHandler reads it, and a stale list there is exactly
        // how the other contract's values used to disappear.
        visibleContractNames = names;
        const entry = forms.find((item) => item.conditional);
        entry.form.setSchema(schema);
        entry.form.setData(only(draft, names));
      }

      const inactive = inactiveContractFields(draft, config);
      inactiveNotice.set(
        inactive.length
          ? `Deze gegevens horen bij het andere contracttype en worden nu niet ` +
              `gebruikt, maar blijven bewaard: ${inactive.join(', ')}.`
          : '',
        { tone: 'info' },
      );

      const allIn = allInPriceSource(config);
      compositionNotice.set(
        allIn
          ? `De prijsbron "${allIn.name || 'zonder naam'}" levert de all-in ` +
              `prijs, dus die wordt ongewijzigd gebruikt. Energiebelasting, ` +
              `opslag leverancier en btw zijn daarom uitgeschakeld: ze rekenen ` +
              `alleen een kale marktprijs om. Zet de prijsbron op "kale ` +
              `marktprijs" als je ze wél wilt gebruiken, of verwijder de bron ` +
              `om alles zelf in te vullen.`
          : '',
        { tone: 'info' },
      );

      // Why none of the feed-in amounts move anything today. This surprised the
      // installer who reported it: the tariff was filled in, correct, and had
      // no effect anywhere — because under net metering a fed-in kWh is worth
      // the retail price and the tariff is never consulted (SPEC.md §16).
      netMeteringNotice.set(
        netMeteringActive(draft)
          ? `Zolang de salderingsregeling geldt — tot ${formatDate(
              draft.net_metering_until,
            )} — telt de terugleververgoeding niet mee in de berekening: een ` +
              `teruggeleverde kWh is dan evenveel waard als een afgenomen kWh. ` +
              `Vul hem nu al in, dan klopt de besparing zodra de saldering ` +
              `stopt. De terugleverkosten tellen wél mee, ook vandaag.`
          : '',
        { tone: 'info' },
      );

      const feedIn = feedInPriceSource(config);
      feedInNotice.set(
        feedIn
          ? `De terugleverprijsbron "${feedIn.name || 'zonder naam'}" bepaalt de ` +
              `vergoeding, dus het vaste bedrag hierboven is uitgeschakeld en ` +
              `blijft bewaard. ` +
              (feedIn.price_basis === 'market'
                ? `De bron levert de kale marktprijs; de inhouding hieronder ` +
                  `wordt daarvan afgetrokken. Er komt geen energiebelasting of ` +
                  `btw bij — dat geldt alleen voor stroom die je afneemt.`
                : `De bron levert de vergoeding zelf, dus de inhouding wordt ` +
                  `niet gebruikt.`)
          : '',
        { tone: 'info' },
      );
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

    /**
     * Zeg wanneer er geen weg terug is, zonder er een gebrek van te maken.
     *
     * Bij de meeste woningen is dit geen tekortkoming: met een zijbalk is een
     * terugknop overbodig. Vandaar `info` en geen waarschuwing — en vandaar dat
     * dit niet in de datakwaliteit staat (SPEC.md §62.6).
     */
    function updateNavigationHint() {
      navigationNotice.set(
        draft.home_dashboard_path
          ? ''
          : 'Geen terugknop ingesteld. Nodig bij een wandtablet zonder zijbalk.',
        { tone: 'info' },
      );
    }

    function loadFrom(config) {
      saved = formDataFrom(config?.home);
      draft = { ...saved };
      revision = config?.revision ?? null;
      loadedRevision = revision;
      // Each card is handed only its own fields, so it cannot carry a stale
      // copy of another card's values.
      contractKey = '';
      visibleContractNames = contractSchema(draft, config).map((field) => field.name);
      for (const { form, names, conditional } of forms) {
        form.setData(only(draft, conditional ? visibleContractNames : names));
      }
      state.clearDraft(DRAFT);
      // `refreshDirty` ends in `showIssues`, and the order matters: the errors
      // can only be split into shown and orphaned once the contract card has
      // the schema it is actually going to render. Calling it here, before
      // `refreshContractFields`, judged them against the full schema and found
      // nothing orphaned — which is how a hidden message stayed hidden even
      // after the notice existed to carry it.
      refreshDirty();
    }

    /**
     * Put each backend validation message next to the field it is about.
     *
     * The issues arrive with every answer, keyed by subject (SPEC.md §14). Each
     * card gets only the errors for the fields it owns; handing all of them to
     * every form would light up three cards for one mistake. Some of these are
     * about a field on this tab but caused by something elsewhere — a price
     * source that reports the bare market price is what makes the energy tax
     * required — which is exactly why the message travels rather than being
     * re-derived here.
     */
    function showIssues(config) {
      const errors = fieldErrors(config?.issues, 'home') || {};
      // What is *rendered*, not what the schema could contain. The contract
      // card drops fields per contract type, and an error against one of those
      // used to be handed to `ha-form` and dropped on the floor.
      const rendered = forms.flatMap(({ form }) =>
        (form.element.schema || []).map((field) => field.name),
      );
      const { shown, orphaned } = splitFieldErrors(errors, rendered);

      for (const { form, names } of forms) {
        const mine = {};
        for (const name of names) {
          if (name in shown) {
            // "Vul de energiebelasting aan" is not an instruction a resident
            // can carry out; for him it becomes something to pass on.
            mine[name] = messageForRole(DRAFT, name, shown[name], isAdmin);
          }
        }
        form.setErrors(Object.keys(mine).length ? mine : null);
      }

      orphanNotice.set(describeOrphanedErrors(orphaned, labelForField), {
        tone: 'warning',
      });
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
          issues: result.issues ?? state.get().config?.issues,
        };
        state.setConfig(updated);
        loadFrom(updated);
        saveNotice.set('De woninggegevens zijn opgeslagen.', { tone: 'success' });
      } catch (error) {
        if (isRevisionConflict(error)) {
          // The form keeps what was typed (SPEC.md §49.4). Reloading was
          // justified with "keeping the draft would invite overwriting a
          // change nobody here has seen" — true only when the change touched
          // the home profile, and the revision counts the whole configuration.
          const alsoHere =
            JSON.stringify(formDataFrom(error.config?.home)) !==
            JSON.stringify(saved);
          state.setConfig(error.config);
          revision = error.config?.revision ?? revision;
          if (alsoHere) {
            // The stored profile really did move. Reload, because here the
            // other change is *in these fields*: leaving the draft on top of
            // it would hide what somebody else just set.
            loadFrom(error.config);
            saveNotice.set(
              'De woninggegevens zijn intussen ergens anders gewijzigd. Het ' +
                'formulier is opnieuw geladen met de actuele gegevens, zodat je ' +
                'niet overschrijft wat je niet gezien hebt.',
              { tone: 'warning' },
            );
          } else {
            saveNotice.set(
              'Er is intussen ergens anders iets aan de configuratie gewijzigd, ' +
                'maar niet aan de woninggegevens. Je invoer staat er nog; druk ' +
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
      // edit in progress: an unrelated update must not wipe the form.
      if (config.revision !== loadedRevision && !isDirty()) {
        loadFrom(config);
      }
      if (panelState.isAdmin !== isAdmin) {
        isAdmin = panelState.isAdmin;
        applyRoleToForms();
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
