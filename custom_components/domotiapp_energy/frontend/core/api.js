/**
 * Talking to the integration's own WebSocket API (SPEC.md §9 and §14).
 *
 * Everything goes through `hass.callWS`. There is deliberately no `fetch` here
 * and nowhere else in this panel: the WebSocket connection is already
 * authenticated, already open, and already the channel Home Assistant expects
 * a panel to use.
 *
 * Only the commands phase 7a needs are wrapped. The write commands exist in the
 * backend since phase 6 and get their wrappers when the tabs that use them are
 * built, so that nothing here is unreachable.
 */

const DOMAIN = 'domotiapp_energy';

/** The error code the backend returns when a write was based on stale data. */
export const ERROR_REVISION_CONFLICT = 'revision_conflict';

export function createApi(hass) {
  /**
   * Send one command. Rejects with the backend's error object, which carries
   * `code` and `message`, and for a revision conflict also `revision` and
   * `config`.
   */
  function call(type, payload = {}) {
    return hass.callWS({ type: `${DOMAIN}/${type}`, ...payload });
  }

  return {
    call,
    /** The whole configuration except the logbook. */
    getConfig: () => call('config/get'),
    /** The latest coach result, including the metrics the Overzicht shows. */
    getCoach: () => call('coach/get'),
    /**
     * Replace the home profile.
     *
     * `expectedRevision` is what the form was filled in against. If the stored
     * configuration moved on meanwhile the backend refuses with
     * `revision_conflict` and sends the current configuration along in the
     * error, so the caller can reload instead of overwriting someone else's
     * change (SPEC.md §14 and §22).
     */
    updateHome: (expectedRevision, home) =>
      call('home/update', { expected_revision: expectedRevision, home }),

    /**
     * Add, replace or remove one energy source.
     *
     * Each answer carries `revision`, `item` and `issues` — the last one a map
     * of subject id to validation issues, so a form can put every message next
     * to the field it is about without a second round trip (SPEC.md §14).
     */
    createSource: (expectedRevision, source) =>
      call('sources/create', { expected_revision: expectedRevision, source }),
    updateSource: (expectedRevision, source) =>
      call('sources/update', { expected_revision: expectedRevision, source }),
    deleteSource: (expectedRevision, sourceId) =>
      call('sources/delete', {
        expected_revision: expectedRevision,
        source_id: sourceId,
      }),

    /** The same three for an appliance. */
    createDevice: (expectedRevision, device) =>
      call('devices/create', { expected_revision: expectedRevision, device }),
    updateDevice: (expectedRevision, device) =>
      call('devices/update', { expected_revision: expectedRevision, device }),
    deleteDevice: (expectedRevision, deviceId) =>
      call('devices/delete', {
        expected_revision: expectedRevision,
        device_id: deviceId,
      }),

    /**
     * Change only the operating fields a resident owns (SPEC.md §33.10).
     *
     * Not a narrower `updateDevice`: it is a different command with a strict
     * allow-list, and that allow-list is the permission boundary. `updateDevice`
     * requires an admin and filters nothing, so sending a resident's edit
     * through it would be sending the whole row.
     *
     * Which of the two the dialog uses follows from the role: an installer
     * edits the whole appliance and saves it whole, a resident edits his six
     * fields and sends only those.
     */
    setDeviceOperation: (expectedRevision, deviceId, operation) =>
      call('devices/set_operation', {
        expected_revision: expectedRevision,
        device_id: deviceId,
        operation,
      }),

    /** Replace the advice preferences. */
    updatePreferences: (expectedRevision, preferences) =>
      call('preferences/update', {
        expected_revision: expectedRevision,
        preferences,
      }),

    /** The logbook, and emptying it. */
    getLogs: () => call('logs/list'),
    clearLogs: (expectedRevision) =>
      call('logs/clear', { expected_revision: expectedRevision }),

    /**
     * Say that an appliance has work in it, or that it no longer has.
     *
     * **No `expected_revision`, and that is not an oversight** (SPEC.md §32.5).
     * The flag lives in its own store, which has no revision at all — tying a
     * button a resident presses in the kitchen to a form an installer happens
     * to have open is exactly what that second store avoids.
     *
     * Open to every user, like `recalculate`: this is operation, not
     * configuration.
     */
    setDeviceReady: (deviceId, ready) =>
      call('devices/set_ready', { device_id: deviceId, ready }),

    /** Recalculate now. Open to every user: it changes no configuration. */
    recalculate: () => call('coach/recalculate'),
  };
}

/**
 * Turn the backend's issue map into what `form.setErrors()` expects.
 *
 * The map is keyed by subject — a row id, `"home"` or `"preferences"` — and
 * `ha-form` wants `{ fieldName: message }`. Only errors are handed over;
 * warnings are shown as a notice instead, because `ha-form` renders everything
 * it is given as an error and a warning that looks like an error is a warning
 * nobody believes twice.
 */
export function fieldErrors(issues, subject) {
  const forSubject = issues?.[subject] || [];
  const errors = {};
  for (const issue of forSubject) {
    if (issue.severity === 'error' && !(issue.field in errors)) {
      errors[issue.field] = issue.message;
    }
  }
  return Object.keys(errors).length ? errors : null;
}

/** The warnings for one subject, which are shown as text rather than per field. */
export function warningMessages(issues, subject) {
  return (issues?.[subject] || [])
    .filter((issue) => issue.severity !== 'error')
    .map((issue) => issue.message);
}

/** Whether a rejected call was refused because the form held stale data. */
export function isRevisionConflict(error) {
  return error?.code === ERROR_REVISION_CONFLICT;
}

/**
 * What a revision conflict actually means for the row being edited.
 *
 * **The revision counts the whole configuration, not one row.** A conflict
 * therefore says "something changed", and until SPEC.md §49.4 every form read
 * it as "your row changed" and threw the filled-in dialog away. An installer
 * lost a complete appliance — name, location, power, energy per cycle,
 * duration, ready window — because a source was added on another screen.
 *
 * Reloading was justified with "keeping the draft would invite overwriting a
 * change nobody here has seen". That is true only when the change touched
 * *this* row, and that is what this tells apart:
 *
 * - `'unrelated'` — the row is untouched, or there is no row yet because this
 *   is a new one. Adopting the new revision and saving again overwrites
 *   nothing, so the input can stay.
 * - `'same-row'` — this row changed too. The input stays, because throwing it
 *   away helps nobody, but saving now replaces what the other change made and
 *   the form has to say so.
 * - `'removed'` — the row is gone. Saving cannot succeed.
 *
 * `rows` is the list from the config that came back with the error; `id` is
 * null for a row being created.
 */
export function conflictKind(rows, id, opened) {
  if (id == null) {
    return 'unrelated';
  }
  const current = (rows || []).find((row) => row.id === id);
  if (!current) {
    return 'removed';
  }
  // A shallow comparison of the stored representation. Both sides come from
  // the backend as plain JSON, so this asks exactly the right question: does
  // what is stored still look like what this dialog was opened on?
  return JSON.stringify(current) === JSON.stringify(opened)
    ? 'unrelated'
    : 'same-row';
}

/** Turn any thrown value into a readable Dutch sentence (SPEC.md §21). */
export function describeError(error) {
  if (!error) {
    return 'Er is een onbekende fout opgetreden.';
  }
  if (typeof error === 'string') {
    return error;
  }
  if (error.code === 'not_found') {
    return 'DomotiApp Energy is niet geladen. Controleer de integratie in Instellingen.';
  }
  if (error.code === 'unauthorized') {
    return 'Je hebt geen rechten voor deze actie.';
  }
  return error.message || 'Er is een onbekende fout opgetreden.';
}
