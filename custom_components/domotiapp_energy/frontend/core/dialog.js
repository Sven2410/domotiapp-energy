/**
 * A modal dialog, built here rather than taken from Home Assistant
 * (SPEC.md §11, §22 and §23).
 *
 * **Why not `ha-dialog`.** It exists, and in a custom panel it is even defined,
 * but it is an internal component of the Home Assistant frontend and its shape
 * changed underneath us: in the instance this was verified against it is a thin
 * wrapper around `wa-dialog` that ignores the `heading` property and has no
 * `close()` method, while the form every custom card uses — `heading`, `close()`,
 * an `mdc-dialog__surface` — is what our own minimum version ships. One call
 * cannot satisfy both, we cannot pin the frontend, and it is not public API. So
 * the dialog is ours: about a hundred lines we control, against a component
 * that can change again in any release.
 *
 * What it does provide, which is the part that matters:
 *
 * * a desktop `max-width` and a full-height sheet on a phone (SPEC.md §11);
 * * `role="dialog"`, `aria-modal` and a heading that labels it (SPEC.md §23);
 * * focus into the dialog on open and back to the opener on close;
 * * `inert` on everything behind it, so Tab cannot wander into the form
 *   underneath — the browser's own mechanism, rather than a hand-written focus
 *   trap that would have to enumerate the inputs inside `ha-form`'s shadow root
 *   and could not;
 * * one place that decides whether closing is allowed, so Escape, the close
 *   button and a click on the backdrop all go through the same question about
 *   unsaved changes (SPEC.md §22).
 *
 * It is deliberately *not* a top-level modal: focus can still reach the Home
 * Assistant sidebar behind the panel, because a panel cannot inert the page it
 * lives in. Everything inside our own panel is unreachable, which is where the
 * form and the data are.
 */

import { button, el, setVisible } from './dom.js';
import { onTap } from './tap.js';

/** Unique ids, so a heading can label its own dialog via aria-labelledby. */
let dialogCount = 0;

/**
 * Create a dialog.
 *
 * @param title the heading, which also labels the dialog for a screen reader
 * @param overlay the panel's overlay host: `{ mount, setBackgroundInert }`
 */
export function createDialog({ title = '', overlay }) {
  dialogCount += 1;
  const titleId = `dialog-title-${dialogCount}`;

  const titleNode = el('h2', {
    class: 'dialog-title',
    text: title,
    attrs: { id: titleId },
  });

  const closeButton = el('button', {
    class: 'dialog-close',
    type: 'button',
    // The icon carries no meaning on its own (SPEC.md §23).
    attrs: { 'aria-label': 'Sluiten' },
  });
  closeButton.appendChild(
    el('ha-icon', { attrs: { icon: 'mdi:close', 'aria-hidden': 'true' } }),
  );

  const body = el('div', { class: 'dialog-body' });
  const actions = el('div', { class: 'dialog-actions' });

  const surface = el('div', {
    class: 'dialog-surface',
    attrs: {
      role: 'dialog',
      'aria-modal': 'true',
      'aria-labelledby': titleId,
      tabindex: '-1',
    },
  }, [
    el('div', { class: 'dialog-header' }, [titleNode, closeButton]),
    body,
    actions,
  ]);

  const scrim = el('div', { class: 'dialog-scrim' });
  const element = el('div', { class: 'dialog' }, [scrim, surface]);
  setVisible(element, false);
  overlay.mount(element);

  let open = false;
  let returnFocusTo = null;
  /** A dialog underneath this one, unreachable while this one is up. */
  let blocked = null;
  /** Asked before every close; returning false keeps the dialog open. */
  let mayClose = () => true;

  function requestClose() {
    if (mayClose()) {
      close();
    }
  }

  function close() {
    if (!open) {
      return;
    }
    open = false;
    setVisible(element, false);
    overlay.setBackgroundInert(false);
    // Released before focus moves, or focus would be handed to an element the
    // browser still considers unreachable.
    if (blocked) {
      blocked.inert = false;
      blocked = null;
    }
    // Focus goes back where it came from, so a keyboard user is not dropped at
    // the top of the page after saving (SPEC.md §23).
    returnFocusTo?.focus?.();
    returnFocusTo = null;
  }

  // Through the central tap helper, so a drag that ends on the backdrop does
  // not count as a tap and throw away a form (SPEC.md §11).
  onTap(scrim, requestClose);
  onTap(closeButton, requestClose);
  element.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.stopPropagation();
      requestClose();
    }
  });

  return {
    element,
    body,
    actions,

    /** Whether the dialog is currently on screen. */
    isOpen: () => open,

    setTitle(text) {
      titleNode.textContent = text;
    },

    /**
     * Decide whether a close request is honoured.
     *
     * The dialog asks this for Escape, the close button and the backdrop alike,
     * so unsaved changes are caught on every route out (SPEC.md §22).
     */
    onCloseRequest(callback) {
      mayClose = callback;
    },

    /**
     * Show the dialog and move focus into it.
     *
     * `inertWhileOpen` is for a dialog that opens on top of another one: the
     * dialog underneath is made unreachable for as long as this one is up, and
     * released again *before* focus goes back to it.
     */
    show({ focusReturnsTo = null, inertWhileOpen = null } = {}) {
      if (open) {
        return;
      }
      open = true;
      returnFocusTo = focusReturnsTo;
      blocked = inertWhileOpen;
      if (blocked) {
        blocked.inert = true;
      }
      setVisible(element, true);
      overlay.setBackgroundInert(true);
      surface.focus();
    },

    /** Close without asking; the caller has already decided. */
    close,
  };
}

/**
 * A confirmation dialog with a message and two buttons.
 *
 * SPEC.md §11 requires a confirmation before deleting a source or an appliance.
 * It is built on the same dialog rather than on `window.confirm()`, which is a
 * modal we neither control nor style, and which reads as a browser error in the
 * middle of a form.
 *
 * The confirming button is not the primary one: the primary style is reserved
 * for the safe action, so the destructive choice never becomes the thing a
 * hurried hand hits by default.
 */
export function createConfirmDialog({ overlay }) {
  const dialog = createDialog({ title: '', overlay });
  const message = el('p', { class: 'dialog-message' });
  dialog.body.appendChild(message);

  const confirmButton = button('Verwijderen');
  confirmButton.classList.add('button-danger');
  const cancelButton = button('Annuleren', { primary: true });
  dialog.actions.append(cancelButton, confirmButton);

  let onConfirm = null;

  onTap(cancelButton, () => dialog.close());
  onTap(confirmButton, () => {
    const confirmed = onConfirm;
    onConfirm = null;
    dialog.close();
    confirmed?.();
  });

  return {
    element: dialog.element,
    isOpen: dialog.isOpen,

    /**
     * Ask the question; `callback` runs only when the installer confirms.
     *
     * `cancelLabel` matters when this sits on top of a form: "Annuleren" is
     * ambiguous there — it could mean cancelling the question or cancelling the
     * edit — so the caller says what going back means.
     */
    ask(
      {
        title,
        text,
        confirmLabel = 'Verwijderen',
        cancelLabel = 'Annuleren',
        focusReturnsTo = null,
        inertWhileOpen = null,
      },
      callback,
    ) {
      dialog.setTitle(title);
      message.textContent = text;
      confirmButton.textContent = confirmLabel;
      cancelButton.textContent = cancelLabel;
      onConfirm = callback;
      dialog.show({ focusReturnsTo, inertWhileOpen });
    },

    close: dialog.close,
  };
}
