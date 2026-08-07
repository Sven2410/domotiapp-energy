/**
 * The one way this panel builds an input form (SPEC.md §9).
 *
 * Every form is an `ha-form` with a schema. No loose `ha-entity-picker`,
 * `ha-select`, `ha-textfield` or `ha-switch` as a primary control: `ha-form`
 * already gives every field a label, keyboard operation, a visible focus state
 * and the theme's own styling, which is most of SPEC.md §23 for free.
 *
 * One instance keeps one `value-changed` listener for its whole life. The form
 * is never re-created on a `hass` update — doing that mid-edit throws away what
 * the installer was typing.
 *
 * Created here for the tabs of phase 7b (Woning, Energiebronnen, Apparaten,
 * Voorkeuren), which are the first forms in the panel; the Overzicht of 7a
 * shows values and has nothing to fill in.
 */

/**
 * Wrap one ha-form.
 *
 * @param hass the Home Assistant object the form needs for entity pickers
 * @param schema the ha-form schema
 * @param onChange called with the complete form data on every change
 */
export function createForm(hass, schema, onChange) {
  const element = document.createElement('ha-form');
  element.hass = hass;
  element.schema = schema;
  element.data = {};
  // Label and helper text travel in the schema itself, so a field and the words
  // that explain it are never in two places that can drift apart.
  element.computeLabel = (field) => field.label || field.name;
  element.computeHelper = (field) => field.helper ?? null;

  // One listener for the life of this form. Re-creating the element on a hass
  // update would throw away whatever the installer was halfway through typing.
  element.addEventListener('value-changed', (event) => {
    event.stopPropagation();
    onChange(event.detail.value);
  });

  return {
    element,

    /** Push new form data in without re-creating the form. */
    setData(data) {
      element.data = data;
    },

    /**
     * Replace the schema, for a form whose fields depend on what was chosen.
     *
     * A source shows its meter mode only when it is a grid meter, and its
     * attribute name only when it reads an attribute (SPEC.md §8). Assigning a
     * new schema is **not** the same as re-creating the form: the element, its
     * listener and its focus survive, and `ha-form` rebuilds only the fields
     * that actually changed.
     */
    setSchema(schema) {
      element.schema = schema;
    },

    /** Keep the form's Home Assistant reference current for entity pickers. */
    setHass(nextHass) {
      element.hass = nextHass;
    },

    /** Disable every field, which the panel does while a save is in flight. */
    setDisabled(disabled) {
      element.disabled = disabled;
    },

    /** Show per-field errors returned by the backend. */
    setErrors(errors) {
      element.error = errors || undefined;
    },
  };
}

/**
 * Split backend field errors into the ones a form can show and the ones it cannot.
 *
 * **An error against a field that is not rendered disappears without trace.**
 * `ha-form` hangs each message on its field, so a message for a field the
 * current schema leaves out is handed over and then silently dropped. Every
 * form in this panel filters its schema on something — the contract type, the
 * source type, whether a device is flexible — so this is not a quirk of one
 * card but a property of conditional forms in general.
 *
 * It happened for real: on a fixed contract the backend asked for the energy
 * tax, the panel hid that field for exactly the same reason the value was
 * unused, and the installer was left with a price source that did not work and
 * nothing on screen to say why (production finding, 2026-08-07).
 *
 * The caller shows `orphaned` as a notice, so a message always lands somewhere.
 * Both halves are plain objects keyed by field name, ready for `setErrors`.
 */
export function splitFieldErrors(errors, renderedNames) {
  const rendered = new Set(renderedNames);
  const shown = {};
  const orphaned = {};
  for (const [name, message] of Object.entries(errors || {})) {
    if (rendered.has(name)) {
      shown[name] = message;
    } else {
      orphaned[name] = message;
    }
  }
  return { shown, orphaned };
}

/**
 * Turn orphaned errors into one sentence for a notice.
 *
 * The field label is prefixed when we have one, because "Energiebelasting: ..."
 * tells the reader which question the message is about when the question itself
 * is off screen. A field we have no label for contributes its message alone —
 * never its identifier, for the reason `core/labels.js` gives.
 */
export function describeOrphanedErrors(orphaned, labelOf) {
  return Object.entries(orphaned)
    .map(([name, message]) => {
      const label = labelOf?.(name);
      return label ? `${label}: ${message}` : message;
    })
    .join(' ');
}
