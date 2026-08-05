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
