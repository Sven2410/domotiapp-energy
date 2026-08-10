/**
 * Who owns which field (SPEC.md §33.4).
 *
 * There are two kinds of user, and one criterion divides them:
 *
 *   the installer owns what the home **is**   — physical, contractual, metered;
 *   the resident owns what the home must **do** — deadlines, noise, intent.
 *
 * A mistake in the first kind is something a resident should be able to
 * **report**, not repair. That is why nothing is hidden from him: he sees the
 * main fuse standing at 25 A while there is a 40 in the meter cupboard, and he
 * rings DomotiTech. An invisible mistake stays a mistake.
 *
 * **A field that is not named here belongs to the installer.** Listing what a
 * resident owns rather than what he does not means a newly added field is
 * protected by default instead of exposed by default — the safe direction for
 * the mistake that will eventually be made.
 *
 * This is presentation only. The backend decides what may actually be written
 * (`websocket_api.py`, SPEC.md §33.9); greying a field out is a courtesy, not a
 * permission check.
 */

/**
 * The fields a resident owns, per form.
 *
 * The keys are the form names the tabs use for their drafts, so a tab asks
 * about its own form and does not have to know about the others.
 */
const RESIDENT_FIELDS = {
  /**
   * Nothing. The whole Installatie tab describes what the home is: the
   * connection, the meters, the contract. Even the price thresholds stay here —
   * "what do I call expensive" is a matter of taste, but the field is an all-in
   * amount per kWh whose helper text assumes a technical reader (SPEC.md §16).
   * That is the most likely candidate to move in a later round.
   */
  home: [],
  source: [],

  /**
   * The split runs *through* an appliance rather than around it. A dishwasher
   * carries installer work (power, energy per cycle, entity links) and resident
   * work (when it has to be finished, on which days, may it be noisy) at the
   * same time.
   *
   * `enabled` is deliberately absent: the resident's off switch is
   * `control_mode = monitor_only`, which is what that field is for, where
   * `enabled` takes the row out of the data quality and the engine entirely.
   * `is_flexible` is absent for a related reason — it is a statement about the
   * machine, where `is_noisy` is one about the household.
   *
   * **`no_run_from` and `no_run_until` are absent on purpose** (SPEC.md §51).
   * They look like the ready window and they are the opposite kind of thing: a
   * property of the installation, set once because the dryer stands under a
   * bedroom. Letting the resident edit them would put his convenience in charge
   * of the neighbour's night, and the whole reason the field exists is that the
   * quiet hours — which he *does* own — must not be the only protection.
   *
   * Keep this in step with `DEVICE_OPERATION_FIELDS` in `const.py`: that tuple
   * is the backend allow-list for `devices/set_operation`, and a field greyed
   * in here but missing there is a control that refuses its own save.
   */
  device: [
    'control_mode',
    'ready_from',
    'ready_before',
    'days_of_week',
    'is_noisy',
    'priority',
  ],

  /**
   * Everything. Every field on this tab is a statement about what the resident
   * wants from the advice, not about what the home is — which is exactly why
   * having it behind the admin lock was the defect that opened this round.
   */
  preferences: null,
};

/** Whether this form is owned by the resident in its entirety. */
function ownsEverything(form) {
  return RESIDENT_FIELDS[form] === null;
}

/**
 * Whether a resident owns this field, and may therefore edit it.
 *
 * An unknown form name yields false: a form nobody has classified is installer
 * territory until someone decides otherwise.
 */
export function residentOwns(form, field) {
  if (ownsEverything(form)) {
    return true;
  }
  return (RESIDENT_FIELDS[form] || []).includes(field);
}

/**
 * Return the schema with every field this user may not edit disabled.
 *
 * No second, read-only variant of any form: `ha-form` carries a per-field
 * `disabled` through to a real disabled control and keeps the value, which was
 * verified with real clicks in round B. Building a separate read-only path
 * would mean two renderings of the same truth that can drift apart.
 *
 * The schema is copied rather than mutated, because the module-level schema
 * constants are shared between every instance of a form.
 */
export function applyRole(schema, form, isAdmin) {
  if (isAdmin) {
    return schema;
  }
  return schema.map((field) =>
    residentOwns(form, field.name) ? field : { ...field, disabled: true },
  );
}

/** What the panel says next to a form a resident cannot change. */
export const MANAGED_NOTICE = 'Deze gegevens worden beheerd door DomotiTech.';

/**
 * Turn a backend message into one a resident can act on.
 *
 * `ha-form` hangs each message on its field, so a message about a field he
 * cannot touch still lands — and then reads as an instruction he cannot carry
 * out. "Vul de energiebelasting aan" is useless to someone whose only move is
 * to pick up the phone. Same failure as an error against a field that is not
 * rendered (`splitFieldErrors`), one step later.
 *
 * A message about a field he *does* own is returned unchanged: that one he can
 * actually fix.
 */
export function messageForRole(form, field, message, isAdmin) {
  if (isAdmin || residentOwns(form, field)) {
    return message;
  }
  return `${message} Dit veld wordt beheerd door DomotiTech; geef het aan hen door.`;
}
