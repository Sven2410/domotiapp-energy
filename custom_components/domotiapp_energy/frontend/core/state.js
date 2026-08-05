/**
 * The single panel state (SPEC.md §22).
 *
 * Three strictly separated parts, and the separation is enforced by there
 * being no generic setter:
 *
 *   config — the backend truth, replaced only by what the backend returned;
 *   live   — the coach result and metrics, replaced on every recalculation;
 *   draft  — temporary form data, per form, never read as if it were saved.
 *
 * A tab that wants to change something puts it in `draft`, sends it, and waits
 * for the backend to answer. Writing into `config` locally would make the panel
 * claim a save succeeded before it did, which SPEC.md §22 forbids.
 */

/** @typedef {'loading' | 'ready' | 'error'} PanelStatus */

export function createState() {
  const listeners = new Set();

  const state = {
    /** @type {PanelStatus} */
    status: 'loading',
    /** Dutch message shown to the user, or null. */
    error: null,
    /** True while a write is in flight; controls are disabled meanwhile. */
    saving: false,
    /** Backend truth: home, sources, devices, preferences, revision. */
    config: null,
    /** Runtime truth: the latest coach result including its metrics. */
    live: null,
    /** Unsaved form data, keyed by form name. */
    draft: {},
    /** Whether the logged-in user may change the configuration. */
    isAdmin: false,
  };

  function notify() {
    for (const listener of listeners) {
      listener(state);
    }
  }

  return {
    /** Read the current state. Treat the result as read-only. */
    get() {
      return state;
    },

    /** Subscribe to every change; returns the unsubscribe function. */
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },

    setStatus(status, error = null) {
      state.status = status;
      state.error = error;
      notify();
    },

    setSaving(saving) {
      state.saving = saving;
      notify();
    },

    /** Replace the backend truth. Only ever called with a backend answer. */
    setConfig(config) {
      state.config = config;
      notify();
    },

    /** Replace the runtime truth. */
    setLive(live) {
      state.live = live;
      notify();
    },

    setAdmin(isAdmin) {
      state.isAdmin = isAdmin;
      notify();
    },

    /** Store unsaved form data under a name, without touching config. */
    setDraft(name, value) {
      state.draft = { ...state.draft, [name]: value };
      notify();
    },

    /** Forget a draft, after a successful save or a cancelled dialog. */
    clearDraft(name) {
      const { [name]: _removed, ...rest } = state.draft;
      state.draft = rest;
      notify();
    },

    /** Whether anything is waiting to be saved (SPEC.md §22). */
    hasUnsavedChanges() {
      return Object.keys(state.draft).length > 0;
    },
  };
}
