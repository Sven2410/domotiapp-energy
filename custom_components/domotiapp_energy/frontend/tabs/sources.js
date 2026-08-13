/**
 * The Energiebronnen tab (SPEC.md §8, §9, §11, §22 and §23).
 *
 * The first tab with a full CRUD cycle, and therefore the first user of the
 * dialog and the keyed row list. Three rules shape it:
 *
 * * **The form shows only the fields that apply.** A meter mode on a solar
 *   source, or an attribute name on a source that reads the state, is a
 *   question with no answer. The schema is rebuilt from the draft on every
 *   change and pushed into the same `ha-form` instance, which keeps the element
 *   and whatever was being typed (SPEC.md §8 and §9).
 * * **What is not asked is not sent.** The payload holds exactly the fields the
 *   current schema shows, so a source that used to be a grid meter does not
 *   keep a stale `meter_mode`, and a cleared field travels as `null` rather
 *   than as an empty string (SPEC.md §8).
 * * **Nothing claims success before the backend confirms it** (SPEC.md §22),
 *   including the delete, which asks first (SPEC.md §11).
 *
 * Validation issues come back with every answer and are placed per field. Only
 * one thing is ever refused — control that was ruled out for this installation
 * — because an installer in a meter cupboard fills a row in gradually and a
 * half-finished source has to be savable as a work in progress.
 */

import {
  conflictKind,
  createApi,
  describeError,
  fieldErrors,
  isRevisionConflict,
  warningMessages,
} from '../core/api.js';
import { createConfirmDialog, createDialog } from '../core/dialog.js';
import { button, card, el, notice, section, setVisible } from '../core/dom.js';
import { createForm, describeOrphanedErrors, splitFieldErrors } from '../core/forms.js';
import { createRowList } from '../core/rows.js';
import { MANAGED_NOTICE, applyRole, messageForRole } from '../core/roles.js';
import { onTap } from '../core/tap.js';

/** The key this tab stores its unsaved edits under. */
const DRAFT = 'source';

const TYPE_LABELS = {
  grid_meter: 'Netmeter',
  solar: 'Zonnepanelen',
  current_price: 'Actuele energieprijs',
  feed_in_price: 'Actuele terugleververgoeding',
  price_forecast: 'Prijsverwachting',
  solar_forecast: 'Zonverwachting',
  home_battery: 'Thuisbatterij',
  general_consumption: 'Algemeen verbruik',
};

/**
 * The types that report a price per kWh and therefore need a basis.
 *
 * Two types rather than one flag on `current_price`, because a home can have a
 * dynamic import price and a fixed feed-in tariff, or the reverse — and the two
 * are converted by different formulas (SPEC.md §16).
 */
const PRICED_TYPES = ['current_price', 'feed_in_price'];

/**
 * The Dutch label of a field, including ones the current type does not render.
 *
 * A message about the meter mode has to name it even when the row is no longer
 * a grid meter and the field is gone from the form — otherwise the notice reads
 * as an error about nothing (core/forms.js).
 */
const FIELD_LABELS = {
  name: 'Naam',
  type: 'Soort bron',
  enabled: 'Ingeschakeld',
  entity_id: 'Entiteit',
  import_entity_id: 'Entiteit voor afname',
  export_entity_id: 'Entiteit voor teruglevering',
  meter_mode: 'Hoe meet deze meter?',
  positive_means: 'Wat betekent een positieve waarde?',
  price_basis: 'Wat levert deze bron?',
  value_source: 'Waarde uitlezen uit',
  attribute_name: 'Naam van het attribuut',
  unit: 'Eenheid',
  scale_factor: 'Schaalfactor',
  invert_value: 'Teken omdraaien',
  capabilities: 'Wat kan deze bron?',
  control_forbidden: 'Aansturing uitsluiten',
  control_forbidden_reason: 'Reden',
  notes: 'Notities',
};

function labelOf(name) {
  return FIELD_LABELS[name] ?? null;
}

/**
 * The two types the engine has never read (SPEC.md §28, §38.1).
 *
 * They are gone from the dropdown and **kept everywhere else**: still a valid
 * type in the model, still labelled here, still stored. Removing them from
 * `SOURCE_TYPES` would quarantine the rows of anyone who linked one — the row
 * would go to "Onbekend brontype" and stop being used, which is a harsher
 * answer than the situation deserves and one the installer cannot undo.
 *
 * Offering them was the real fault. A choice in a list, with a helper inviting
 * you to link an entity ("De entiteit met de verwachte opbrengst"), that then
 * counts for nothing anywhere: the most expensive kind of empty field, because
 * it costs the installer a decision and a link before it costs him trust.
 */
const RETIRED_TYPES = ['price_forecast', 'solar_forecast'];

const RETIRED_TYPE_NOTICE =
  'Dit brontype is nog niet in gebruik. DomotiApp Energy rekent alleen met ' +
  'het huidige moment en leest geen verwachtingen. De koppeling blijft ' +
  'bewaard, maar er wordt op dit moment niets mee gedaan.';

const TYPE_OPTIONS = Object.entries(TYPE_LABELS)
  .filter(([value]) => !RETIRED_TYPES.includes(value))
  .map(([value, label]) => ({ value, label }));

/**
 * The type options for one row, which is not always the list above.
 *
 * A row that already carries a retired type keeps it as an option. Without
 * that the select renders with nothing selected, and the first save silently
 * rewrites the row to whatever the installer happened to pick — a dropdown
 * quietly changing stored data because we removed its current value.
 */
function typeOptionsFor(draft) {
  if (!RETIRED_TYPES.includes(draft.type)) {
    return TYPE_OPTIONS;
  }
  return [
    ...TYPE_OPTIONS,
    { value: draft.type, label: TYPE_LABELS[draft.type] || draft.type },
  ];
}

const UNIT_OPTIONS = [
  { value: 'W', label: 'W — watt' },
  { value: 'kW', label: 'kW — kilowatt' },
  { value: 'A', label: 'A — ampère' },
  { value: 'Wh', label: 'Wh — wattuur' },
  { value: 'kWh', label: 'kWh — kilowattuur' },
  { value: 'EUR/kWh', label: '€/kWh — euro per kilowattuur' },
  { value: 'ct/kWh', label: 'ct/kWh — cent per kilowattuur' },
  { value: '%', label: '% — procent' },
  { value: 'none', label: 'Geen eenheid' },
];

const CAPABILITY_OPTIONS = [
  { value: 'read', label: 'Uitlezen' },
  { value: 'switch', label: 'Aan- en uitschakelen' },
  { value: 'set_power_limit', label: 'Vermogensgrens instellen' },
  { value: 'set_current', label: 'Laadstroom instellen' },
];

/** What a new source starts as. Every strict enum is deliberately absent. */
const NEW_SOURCE = {
  name: '',
  type: 'grid_meter',
  enabled: true,
  value_source: 'state',
  unit: 'W',
  scale_factor: 1,
  invert_value: false,
  capabilities: [],
  control_forbidden: false,
};

/**
 * Build the schema for one draft.
 *
 * Every branch answers "does this question mean anything for what the installer
 * has chosen so far". Nothing is hidden that could still be answered, and
 * nothing is asked that could not.
 */
function schemaFor(draft) {
  const schema = [
    { name: 'name', label: 'Naam', selector: { text: {} } },
    {
      name: 'type',
      label: 'Soort bron',
      helper: RETIRED_TYPES.includes(draft.type) ? RETIRED_TYPE_NOTICE : undefined,
      selector: {
        select: { mode: 'dropdown', options: typeOptionsFor(draft) },
      },
    },
    {
      name: 'enabled',
      label: 'Ingeschakeld',
      helper: 'Een uitgeschakelde bron wordt nergens in meegerekend.',
      selector: { boolean: {} },
    },
  ];

  if (draft.type === 'grid_meter') {
    schema.push(...gridMeterFields(draft));
  } else {
    schema.push({
      name: 'entity_id',
      label: 'Entiteit',
      helper: entityHelper(draft.type),
      selector: { entity: {} },
    });
  }

  if (PRICED_TYPES.includes(draft.type)) {
    const feedIn = draft.type === 'feed_in_price';
    schema.push({
      name: 'price_basis',
      label: 'Wat levert deze bron?',
      // No default anywhere in the chain: unstated means unusable, because the
      // two answers are a factor of about three apart (SPEC.md §16).
      //
      // The same field on both price types, and deliberately so: the question
      // is identical, only the conversion behind it differs. Import adds tax
      // and VAT; feed-in subtracts what the supplier keeps.
      helper: feedIn
        ? 'Kies expliciet. Zonder deze keuze wordt de vergoeding niet ' +
          'gebruikt. Een kale marktprijs wordt omgerekend met de inhouding ' +
          'die je bij Woning invult; er komt geen energiebelasting of btw bij.'
        : 'Kies expliciet. Zonder deze keuze wordt de prijs niet gebruikt, omdat ' +
          'een kale marktprijs en een all-in prijs sterk verschillen.',
      selector: {
        select: {
          mode: 'dropdown',
          options: [
            {
              value: 'all_in',
              label: feedIn
                ? 'De vergoeding die de klant werkelijk krijgt'
                : 'De all-in prijs die de klant betaalt',
            },
            {
              value: 'market',
              label: feedIn
                ? 'De kale marktprijs, vóór inhouding van de leverancier'
                : 'De kale marktprijs, exclusief belasting en opslag',
            },
          ],
        },
      },
    });
  }

  schema.push(...readingFields(draft), ...controlFields(draft), {
    name: 'notes',
    label: 'Notities',
    selector: { text: { multiline: true } },
  });

  return schema;
}

/** The extra fields a grid meter needs; never derived from what is filled in. */
function gridMeterFields(draft) {
  const fields = [
    {
      name: 'meter_mode',
      label: 'Hoe meet deze meter?',
      helper: 'Zonder deze keuze wordt de netmeter niet gebruikt.',
      selector: {
        select: {
          mode: 'dropdown',
          options: [
            {
              value: 'single_signed',
              label: 'Eén waarde met een plus- en minteken',
            },
            {
              value: 'separate_import_export',
              label: 'Gescheiden afname en teruglevering',
            },
          ],
        },
      },
    },
  ];

  if (draft.meter_mode === 'single_signed') {
    fields.push(
      { name: 'entity_id', label: 'Entiteit', selector: { entity: {} } },
      {
        name: 'positive_means',
        label: 'Een positieve waarde betekent',
        selector: {
          select: {
            mode: 'dropdown',
            options: [
              { value: 'import', label: 'Afname van het net' },
              { value: 'export', label: 'Teruglevering aan het net' },
            ],
          },
        },
      },
    );
  } else if (draft.meter_mode === 'separate_import_export') {
    fields.push(
      {
        name: 'import_entity_id',
        label: 'Entiteit voor afname',
        selector: { entity: {} },
      },
      {
        name: 'export_entity_id',
        label: 'Entiteit voor teruglevering',
        selector: { entity: {} },
      },
    );
  }

  return fields;
}

/** How the value is read and converted (SPEC.md §15). */
function readingFields(draft) {
  const fields = [
    {
      name: 'value_source',
      label: 'Waarde uitlezen uit',
      selector: {
        select: {
          mode: 'dropdown',
          options: [
            { value: 'state', label: 'De status van de entiteit' },
            { value: 'attribute', label: 'Een attribuut van de entiteit' },
          ],
        },
      },
    },
  ];

  if (draft.value_source === 'attribute') {
    fields.push({
      name: 'attribute_name',
      label: 'Naam van het attribuut',
      selector: { text: {} },
    });
  }

  fields.push(
    {
      name: 'unit',
      label: 'Eenheid',
      // The conversion follows this choice and the scale factor only, never the
      // entity's own unit_of_measurement or its name (SPEC.md §15).
      helper: unitHelper(draft.type),
      selector: { select: { mode: 'dropdown', options: UNIT_OPTIONS } },
    },
    {
      name: 'scale_factor',
      label: 'Schaalfactor',
      helper: 'Vermenigvuldiger vóór de eenheidsconversie. Standaard 1.',
      selector: { number: { min: 0.000001, step: 0.001, mode: 'box' } },
    },
    {
      name: 'invert_value',
      label: 'Teken omdraaien',
      helper: invertHelper(draft),
      selector: { boolean: {} },
    },
  );

  return fields;
}

/**
 * What this source's entity is expected to report.
 *
 * A generic "link an entity" is the same mistake as a generic unit: correct for
 * every type and useful for none. What a solar source needs is not what a price
 * source needs, and saying so here is cheaper than a support call.
 */
function entityHelper(sourceType) {
  const perType = {
    solar: 'De entiteit die de actuele zonneproductie meldt, niet de dagopbrengst.',
    current_price:
      'De entiteit met de prijs van dit moment. Hieronder geef je aan of dat ' +
      'de kale marktprijs of de all-in prijs is.',
    feed_in_price:
      'De entiteit met de terugleververgoeding van dit moment. Gebruik dit ' +
      'alleen bij een dynamisch teruglevercontract; bij een vast bedrag vul ' +
      'je dat in bij Woning.',
    price_forecast: 'De entiteit met de prijzen van de komende uren.',
    solar_forecast: 'De entiteit met de verwachte opbrengst.',
    home_battery:
      'De entiteit die het laad- of ontlaadvermogen meldt, niet de laadtoestand.',
    general_consumption: 'De entiteit die het totale huishoudelijke verbruik meldt.',
  };
  return perType[sourceType] || 'De entiteit waar deze bron uit gelezen wordt.';
}

/** Which units make sense here, which differs sharply per type. */
function unitHelper(sourceType) {
  const perType = {
    current_price: 'Voor een prijs: EUR/kWh of ct/kWh.',
    price_forecast: 'Voor een prijs: EUR/kWh of ct/kWh.',
    solar: 'Voor een vermogen: W of kW.',
    home_battery: 'Voor een vermogen: W of kW.',
    general_consumption: 'Voor een vermogen: W of kW.',
    solar_forecast: 'Voor een verwachte opbrengst meestal Wh of kWh.',
  };
  return (
    (perType[sourceType] || 'De eenheid waarin deze entiteit meet.') +
    ' Zoals jij hem vaststelt: de eenheid van de entiteit zelf wordt nooit ' +
    'gebruikt om te converteren.'
  );
}

/**
 * The helper text under "teken omdraaien".
 *
 * For a home battery this is not a nicety but a requirement of SPEC.md §8:
 * battery sensors differ per brand, several report charging as negative, and a
 * wrong sign silently pulls the solar surplus apart. So the convention is
 * stated where the switch is, not in a manual nobody opens in a meter cupboard.
 */
function invertHelper(draft) {
  if (draft.type === 'home_battery') {
    return (
      'Let op de tekenconventie: positief betekent hier laden — de woning ' +
      'verbruikt — en negatief ontladen. Meldt deze sensor het andersom, zet ' +
      'deze schakelaar dan aan.'
    );
  }
  if (draft.type === 'grid_meter') {
    return 'Meestal niet nodig: gebruik hierboven "een positieve waarde betekent".';
  }
  return 'Zet aan wanneer deze sensor het tegenovergestelde teken rapporteert.';
}

/** What the hardware can do, and what was agreed about it (SPEC.md §12). */
function controlFields(draft) {
  const fields = [
    {
      name: 'capabilities',
      // A source is a measuring point, not an appliance. The hardware behind it
      // may well be able to do more — a SolarEdge inverter can be read *and*
      // limited, and that is why these fields are on a source at all
      // (SPEC.md §8) — but the row the installer is looking at is a source.
      label: 'Wat kan deze bron behalve uitlezen?',
      helper:
        'Alleen registreren: DomotiApp Energy stuurt in deze versie niets aan. ' +
        'Niets aanvinken betekent "niet opgegeven", niet "kan niets".',
      selector: { select: { multiple: true, options: CAPABILITY_OPTIONS } },
    },
    {
      name: 'control_forbidden',
      label: 'Aansturing uitgesloten voor deze installatie',
      helper: 'Een afspraak met de klant, los van wat deze bron zou kunnen.',
      selector: { boolean: {} },
    },
  ];

  if (draft.control_forbidden) {
    fields.push({
      name: 'control_forbidden_reason',
      label: 'Reden',
      // Without the reason the flag is unreadable in two years, which is the
      // whole point of recording it (SPEC.md §12).
      helper: 'Noteer waarom, zodat dit later terug te vinden is.',
      selector: { text: {} },
    });
  }

  return fields;
}

/** Read the editable fields out of a stored source. */
function draftFrom(source) {
  const draft = { ...NEW_SOURCE, ...source };
  for (const [key, value] of Object.entries(draft)) {
    if (value === null) {
      delete draft[key];
    }
  }
  return draft;
}

/**
 * The payload to send.
 *
 * Exactly the fields the current schema asks about, plus the identity. A field
 * the installer cleared travels as `null`; an empty string is never stored
 * (SPEC.md §8), and a field that no longer applies is left out so the backend
 * clears it rather than keeping a stale answer to a question nobody asked.
 */
function payloadFrom(draft, schema) {
  const payload = { type: draft.type };
  if (draft.id) {
    payload.id = draft.id;
  }
  for (const field of schema) {
    if (field.name === 'type') {
      continue;
    }
    const value = draft[field.name];
    payload[field.name] = value === undefined || value === '' ? null : value;
  }
  return payload;
}

/** Whether two draft values differ, treating the one array field properly. */
function differs(left, right) {
  if (Array.isArray(left) || Array.isArray(right)) {
    return (left || []).join('|') !== (right || []).join('|');
  }
  return (left ?? null) !== (right ?? null);
}

/**
 * How the questions are grouped in the dialog.
 *
 * Same reasoning as the device dialog: what an installer touches on every visit
 * is open, the agreement about control and the notes are folded away. The
 * fields come from one `schemaFor`; this list only groups them.
 */
const SECTIONS = [
  { title: 'Bron', open: true, fields: ['name', 'type', 'enabled'] },
  {
    title: 'Wat er gemeten wordt',
    open: true,
    fields: [
      'meter_mode',
      'entity_id',
      'positive_means',
      'import_entity_id',
      'export_entity_id',
      'price_basis',
      'value_source',
      'attribute_name',
      'unit',
      'scale_factor',
      'invert_value',
    ],
  },
  {
    title: 'Aansturing',
    open: false,
    fields: ['capabilities', 'control_forbidden', 'control_forbidden_reason'],
  },
  { title: 'Notities', open: false, fields: ['notes'] },
];

export const sourcesTab = {
  id: 'sources',
  label: 'Energiebronnen',
  icon: 'mdi:transmission-tower',

  create({ getHass, state, overlay }) {
    const element = el('div', { class: 'tab-content' });
    const sources = card('Energiebronnen');

    const listNotice = notice('mdi:information-outline');
    const addButton = button('Bron toevoegen', { primary: true });

    /** The stored source being edited, or null while adding a new one. */
    let editing = null;
    let draft = {};
    let saved = {};
    let revision = null;
    /** The schema currently on the form, so it is only replaced when it moves. */
    let schemaKey = '';
    /**
     * Whether this user may change anything here.
     *
     * A source is entirely installer territory (SPEC.md §33.4): nobody but the
     * person who linked the meter can judge a meter mode or a price basis. A
     * resident may still open a row and read it — seeing that a source is
     * broken is exactly what lets him ring us about it.
     */
    let isAdmin = true;

    const rowList = createRowList({
      emptyText:
        'Nog geen energiebronnen. Koppel je slimme meter, omvormer, prijsbron ' +
        'of thuisbatterij om DomotiApp Energy iets te laten meten.',
      createRow: () => createSourceRow(),
    });

    const addActions = el('div', { class: 'actions' }, [addButton]);
    const managedNotice = notice('mdi:shield-account-outline');

    sources.body.append(
      rowList.element,
      addActions,
      managedNotice.element,
      listNotice.element,
    );
    element.appendChild(sources.element);

    // --- The dialog ---------------------------------------------------------

    const dialog = createDialog({ title: 'Energiebron', overlay });
    const batteryNotice = notice('mdi:battery-charging-outline');
    const warningNotice = notice('mdi:alert-outline');
    // Validation messages whose field this source type does not render.
    const orphanNotice = notice('mdi:alert-circle-outline');
    const dialogNotice = notice('mdi:content-save-outline');

    /**
     * One form per section, each handed only its own fields.
     *
     * Never the whole payload it emits: a form holding a stale copy of another
     * section's values would quietly undo an edit made elsewhere, which is the
     * bug phase 7b was fixed for.
     */
    function changeHandler(names) {
      return (part) => {
        const mine = {};
        for (const name of names) {
          mine[name] = part[name];
        }
        draft = { ...draft, ...mine };
        state.setDraft(DRAFT, draft);
        refreshDialog();
      };
    }

    const forms = SECTIONS.map((definition) => {
      const host = section(definition.title, { open: definition.open });
      const form = createForm(getHass(), [], changeHandler(definition.fields));
      host.body.appendChild(form.element);
      return { definition, host, form };
    });

    dialog.body.append(
      batteryNotice.element,
      ...forms.map(({ host }) => host.element),
      orphanNotice.element,
      warningNotice.element,
      dialogNotice.element,
    );

    const saveButton = button('Opslaan', { primary: true });
    const cancelButton = button('Annuleren');
    dialog.actions.append(cancelButton, saveButton);

    const confirmDialog = createConfirmDialog({ overlay });

    // --- Rows ---------------------------------------------------------------

    function createSourceRow() {
      const name = el('p', { class: 'row-name' });
      const meta = el('p', { class: 'row-meta' });
      const status = el('div', { class: 'row-status' });
      const statusIcon = el('ha-icon', { attrs: { 'aria-hidden': 'true' } });
      const statusText = el('span');
      status.append(statusIcon, statusText);

      const editButton = button('Bewerken');
      const deleteButton = button('Verwijderen');
      deleteButton.classList.add('button-danger');

      const row = el('div', { class: 'row-item' }, [
        el('div', { class: 'row-main' }, [name, meta, status]),
        el('div', { class: 'row-buttons' }, [editButton, deleteButton]),
      ]);

      let current = null;
      onTap(editButton, () => current && openDialog(current, editButton));
      onTap(deleteButton, () => current && askDelete(current, deleteButton));

      return {
        element: row,
        update(source) {
          current = source;
          name.textContent = source.name || 'Naamloze bron';
          meta.textContent = describeSource(source);
          // A resident opens the same dialog, so the button says what it will
          // actually do rather than promising an edit it cannot make.
          editButton.textContent = isAdmin ? 'Bewerken' : 'Bekijken';
          setVisible(deleteButton, isAdmin);

          const shown = statusOf(source);
          statusIcon.setAttribute('icon', shown.icon);
          statusText.textContent = shown.text;
          status.dataset.tone = shown.tone;
        },
      };
    }

    function describeSource(source) {
      const type = TYPE_LABELS[source.type] || source.type;
      const entity = source.entity_id || source.import_entity_id;
      return entity ? `${type} · ${entity}` : type;
    }

    /**
     * The one line under a row that says where it stands.
     *
     * Always an icon **and** words: neither a colour nor a symbol may carry the
     * meaning on its own (SPEC.md §23). An agreement not to control this
     * hardware is shown with its reason, because that is what someone reads two
     * years later (SPEC.md §12).
     */
    function statusOf(source) {
      if (source.invalid_reason === 'unknown_type') {
        return {
          icon: 'mdi:alert-circle-outline',
          tone: 'error',
          text: `Onbekend brontype '${source.type}'. Deze bron wordt niet gebruikt.`,
        };
      }
      if (!source.enabled) {
        return {
          icon: 'mdi:pause-circle-outline',
          tone: 'info',
          text: 'Uitgeschakeld — wordt niet meegerekend.',
        };
      }
      // Before the completeness check on purpose: telling an installer which
      // field to fill in on a row that is read by nothing would send him to
      // finish work that has no effect. Informative and not a warning — the
      // row is not broken, it is simply not used yet (SPEC.md §38.1).
      if (RETIRED_TYPES.includes(source.type)) {
        return {
          icon: 'mdi:information-outline',
          tone: 'info',
          text: RETIRED_TYPE_NOTICE,
        };
      }
      const errors = fieldErrors(currentIssues(), source.id);
      if (errors) {
        return {
          icon: 'mdi:progress-wrench',
          tone: 'warning',
          text: `Nog niet compleet: ${Object.values(errors)[0]}`,
        };
      }
      // **Compleet ingevuld is niet hetzelfde als bruikbaar** (SPEC.md §64).
      // Alles hierboven leest de configuratie; dit leest wat de motor er zojuist
      // mee kon. Een bron waarvan de entiteit onbereikbaar is of te lang zweeg
      // stond hier "Compleet." te zeggen op het moment dat zij geweigerd werd —
      // terwijl het logboek er een waarschuwing over schreef en het cijfer zakte.
      //
      // **Ná de veldfouten, en dat is de volgorde die telt.** Een onvoltooide rij
      // wordt door de motor óók geweigerd en staat dus óók in `invalid_items`;
      // zou deze tak eerder komen, dan kreeg een installateur "niet uit te lezen"
      // te zien op een rij waar hij simpelweg nog een veld moet invullen.
      //
      // **En geen verwijzing naar het logboek** (0.31.1). Hier stond "Het logboek
      // zegt sinds wanneer": geen Nederlandse zin — een bijzin met "sinds
      // wanneer" heeft een werkwoord nodig — en bovendien een belofte die vaak
      // niet waar is. Een ontbrekende entiteit en een entiteit zonder waarde
      // schrijven per §63.5 juist géén logboekregel, en `unavailable` en `stale`
      // pas nadat die bron ooit gelezen is. De rij zegt nu wat zij ziet en
      // verwijst niet naar iets dat er niet hoeft te staan.
      if (unusableNow().includes(source.id)) {
        return {
          icon: 'mdi:alert-outline',
          tone: 'warning',
          text: 'Compleet ingevuld, maar op dit moment niet uit te lezen.',
        };
      }
      if (source.control_forbidden) {
        return {
          icon: 'mdi:lock-outline',
          tone: 'info',
          text: `Aansturing uitgesloten — ${
            source.control_forbidden_reason || 'geen reden genoteerd'
          }`,
        };
      }
      return { icon: 'mdi:check-circle-outline', tone: 'info', text: 'Compleet.' };
    }

    /**
     * De rijen die de motor bij de laatste berekening niet heeft gebruikt.
     *
     * Leeg zolang er nog geen berekening is: dan is er niets waargenomen, en
     * zwijgen is dan juister dan "in orde" of "kapot" beweren.
     */
    function unusableNow() {
      return state.get().live?.metrics?.data_quality?.invalid_items || [];
    }

    function currentIssues() {
      return state.get().config?.issues || {};
    }

    // --- The dialog cycle ---------------------------------------------------

    function openDialog(source, opener) {
      editing = source || null;
      draft = draftFrom(source || {});
      saved = { ...draft };
      revision = state.get().config?.revision ?? null;
      schemaKey = '';

      dialog.setTitle(source ? 'Energiebron bewerken' : 'Energiebron toevoegen');
      dialogNotice.set('');
      for (const { definition, host } of forms) {
        host.setOpen(definition.open);
      }
      refreshDialog();
      showErrors();
      dialog.show({ focusReturnsTo: opener });
    }

    function refreshDialog() {
      const schema = applyRole(schemaFor(draft), DRAFT, isAdmin);
      // Only when the questions actually changed. Handing `ha-form` a fresh
      // schema on every keystroke makes it rebuild every field, which throws
      // away whatever control the installer had open.
      const key = JSON.stringify(schema);
      const schemaMoved = key !== schemaKey;
      schemaKey = key;

      for (const { definition, host, form } of forms) {
        const mine = schema.filter((field) => definition.fields.includes(field.name));
        if (schemaMoved) {
          form.setSchema(mine);
        }
        const data = {};
        for (const field of mine) {
          data[field.name] = draft[field.name];
        }
        form.setData(data);
        setVisible(host.element, mine.length > 0);
      }

      batteryNotice.set(
        draft.type === 'home_battery'
          ? 'Intern geldt voor een thuisbatterij: positief is laden — de woning ' +
              'verbruikt — en negatief is ontladen. Controleer wat deze sensor ' +
              'rapporteert en gebruik zo nodig "teken omdraaien".'
          : '',
        { tone: 'info' },
      );

      const warnings = editing ? warningMessages(currentIssues(), editing.id) : [];
      warningNotice.set(warnings.join(' '), { tone: 'warning' });
      saveButton.disabled = !isDirty();
    }

    /**
     * Put every section's own errors on its own form.
     *
     * A message for a field this source type does not render — a meter mode on
     * something that is no longer a grid meter, say — would otherwise vanish,
     * so it lands in a notice instead (core/forms.js).
     */
    function showErrors() {
      const errors = editing ? fieldErrors(currentIssues(), editing.id) : null;
      const rendered = forms.flatMap(({ form }) =>
        (form.element.schema || []).map((field) => field.name),
      );
      const { shown, orphaned } = splitFieldErrors(errors, rendered);

      for (const { definition, form } of forms) {
        const mine = {};
        for (const name of definition.fields) {
          if (name in shown) {
            mine[name] = messageForRole(DRAFT, name, shown[name], isAdmin);
          }
        }
        form.setErrors(Object.keys(mine).length ? mine : null);
      }

      orphanNotice.set(describeOrphanedErrors(orphaned, labelOf), {
        tone: 'warning',
      });
    }

    /** Push the current role into the list and the dialog. */
    function applyRoleToTab() {
      setVisible(addActions, isAdmin);
      setVisible(saveButton, isAdmin);
      cancelButton.textContent = isAdmin ? 'Annuleren' : 'Sluiten';
      managedNotice.set(isAdmin ? '' : MANAGED_NOTICE, { tone: 'info' });
      // The rows carry their own buttons, and the dialog its own schema.
      rowList.sync(state.get().config?.sources || []);
      if (dialog.isOpen()) {
        schemaKey = '';
        refreshDialog();
      }
    }

    function isDirty() {
      const names = new Set([...Object.keys(draft), ...Object.keys(saved)]);
      return [...names].some((name) => differs(draft[name], saved[name]));
    }

    function setBusy(busy) {
      for (const { form } of forms) {
        form.setDisabled(busy);
      }
      saveButton.disabled = busy || !isDirty();
      cancelButton.disabled = busy;
    }

    /**
     * What to tell the installer when the configuration moved under him.
     *
     * One whole sentence per situation (SPEC.md §26 and §49.4). The wording is
     * this tab's own rather than shared with Apparaten: these sentences name
     * the thing they are about, and "deze bron" is not "dit apparaat".
     */
    function conflictSentence(kind) {
      if (kind === 'removed') {
        return (
          'Deze energiebron is intussen ergens anders verwijderd. Je invoer ' +
          'staat hier nog, maar opslaan lukt niet meer; maak hem opnieuw aan ' +
          'als je hem terug wilt.'
        );
      }
      if (kind === 'same-row') {
        return (
          'Deze energiebron is intussen ook ergens anders gewijzigd. Je invoer ' +
          'staat er nog; als je nu opslaat, vervangt hij die andere wijziging.'
        );
      }
      return (
        'Er is intussen ergens anders iets aan de configuratie gewijzigd, maar ' +
        'niet aan deze bron. Je invoer staat er nog; druk opnieuw op Opslaan ' +
        'om hem te bewaren.'
      );
    }

    async function save() {
      // Nothing may claim success before the backend confirms it (SPEC.md §22).
      state.setSaving(true);
      setBusy(true);
      dialogNotice.set('Bezig met opslaan…', { tone: 'info' });

      const api = createApi(getHass());
      const payload = payloadFrom(draft, schemaFor(draft));

      try {
        const result = editing
          ? await api.updateSource(revision, { ...payload, id: editing.id })
          : await api.createSource(revision, payload);
        applyWrite(result, editing ? 'update' : 'create');
        const name = result.item?.name || 'zonder naam';
        state.clearDraft(DRAFT);
        dialog.close();
        listNotice.set(
          editing
            ? `De energiebron '${name}' is bijgewerkt.`
            : `De energiebron '${name}' is toegevoegd.`,
          { tone: 'success' },
        );
      } catch (error) {
        if (isRevisionConflict(error)) {
          // The dialog stays open and keeps every field (SPEC.md §49.4). The
          // revision counts the whole configuration, so a conflict usually
          // means something else moved — and throwing this form away for that
          // is a loss with nothing gained.
          state.setConfig(error.config);
          revision = error.config?.revision ?? revision;
          dialogNotice.set(
            conflictSentence(
              conflictKind(error.config?.sources, editing?.id ?? null, editing),
            ),
            { tone: 'warning' },
          );
        } else {
          dialogNotice.set(describeError(error), { tone: 'warning' });
        }
      } finally {
        state.setSaving(false);
        setBusy(false);
      }
    }

    /**
     * Fold one write answer into the panel state.
     *
     * The answer carries the row, the new revision and the issues, which is
     * everything that changed — re-reading the whole configuration after each
     * save would be a second round trip for data we already hold.
     */
    function applyWrite(result, kind, removedId = null) {
      const config = state.get().config;
      const rows = [...(config.sources || [])];
      if (kind === 'create') {
        rows.push(result.item);
      } else if (kind === 'update') {
        const index = rows.findIndex((row) => row.id === result.item.id);
        rows[index >= 0 ? index : rows.length] = result.item;
      } else {
        const index = rows.findIndex((row) => row.id === removedId);
        if (index >= 0) {
          rows.splice(index, 1);
        }
      }
      state.setConfig({
        ...config,
        sources: rows,
        revision: result.revision,
        issues: result.issues ?? config.issues,
      });
    }

    async function remove(source) {
      state.setSaving(true);
      listNotice.set('Bezig met verwijderen…', { tone: 'info' });
      try {
        const result = await createApi(getHass()).deleteSource(
          state.get().config?.revision ?? null,
          source.id,
        );
        applyWrite(result, 'delete', source.id);
        listNotice.set(
          `De energiebron '${source.name || 'zonder naam'}' is verwijderd.`,
          { tone: 'success' },
        );
      } catch (error) {
        if (isRevisionConflict(error)) {
          state.setConfig(error.config);
          listNotice.set(
            'De configuratie is intussen ergens anders gewijzigd. Er is niets ' +
              'verwijderd; de lijst is opnieuw geladen.',
            { tone: 'warning' },
          );
        } else {
          listNotice.set(describeError(error), { tone: 'warning' });
        }
      } finally {
        state.setSaving(false);
      }
    }

    /** Deleting asks first, and says what disappears (SPEC.md §11). */
    function askDelete(source, opener) {
      confirmDialog.ask(
        {
          title: 'Energiebron verwijderen',
          text:
            `Weet je zeker dat je '${source.name || 'deze bron'}' wilt ` +
            'verwijderen? De metingen van deze bron tellen daarna nergens meer mee.',
          focusReturnsTo: opener,
        },
        () => remove(source),
      );
    }

    // --- Leaving with unsaved changes ---------------------------------------

    /**
     * Closing a dialog that holds changes asks first, visibly (SPEC.md §22).
     *
     * A notice at the bottom of a long form is not a question: it can sit below
     * the fold while the installer clicks the backdrop a second time and loses
     * the lot. So the question is a dialog of its own, and Escape, the close
     * button, the backdrop and Annuleren all reach it through here.
     */
    function mayClose() {
      if (!isDirty()) {
        state.clearDraft(DRAFT);
        return true;
      }
      askDiscard();
      return false;
    }

    function askDiscard(afterDiscard = null) {
      confirmDialog.ask(
        {
          title: 'Wijzigingen verwerpen?',
          text:
            'Je hebt wijzigingen die nog niet zijn opgeslagen. Verwerp je ze, ' +
            'dan zijn ze weg.',
          confirmLabel: 'Verwerpen',
          cancelLabel: 'Terug naar het formulier',
          // Nothing behind this question is reachable while it stands, not even
          // the form it is about.
          inertWhileOpen: dialog.element,
        },
        () => {
          state.clearDraft(DRAFT);
          draft = { ...saved };
          dialog.close();
          afterDiscard?.();
        },
      );
    }

    dialog.onCloseRequest(mayClose);
    onTap(cancelButton, () => {
      if (mayClose()) {
        dialog.close();
      }
    });
    onTap(saveButton, () => {
      if (!saveButton.disabled) {
        save();
      }
    });
    onTap(addButton, () => openDialog(null, addButton));

    // --- Panel plumbing -----------------------------------------------------

    function update(panelState) {
      const config = panelState.config;
      if (!config) {
        return;
      }
      if (panelState.isAdmin !== isAdmin) {
        isAdmin = panelState.isAdmin;
        applyRoleToTab();
      }
      rowList.sync(config.sources || []);
      for (const { form } of forms) {
        form.setHass(getHass());
      }
      if (dialog.isOpen() && editing) {
        showErrors();
      }
    }

    /** The tab may not be left while a dialog holds unsaved changes. */
    function canLeave(proceed) {
      if (confirmDialog.isOpen()) {
        return false;
      }
      if (!dialog.isOpen()) {
        return true;
      }
      if (!isDirty()) {
        dialog.close();
        return true;
      }
      askDiscard(proceed);
      return false;
    }

    return { element, update, canLeave };
  },
};
