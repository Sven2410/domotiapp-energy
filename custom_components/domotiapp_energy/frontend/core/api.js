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
  };
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
