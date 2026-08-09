/**
 * The DomotiApp Energy panel (SPEC.md §7, §9, §10, §11, §22 and §23).
 *
 * Home Assistant hands this element four properties — `hass`, `narrow`, `route`
 * and `panel` — and expects it to render itself. The rules it follows:
 *
 * * the DOM is built once in `_buildDOM()`; everything after that goes through
 *   `_update()`, which only sets values and visibility. `innerHTML` is never
 *   assigned a second time (SPEC.md §9);
 * * `hass` is set on nearly every state change in the whole instance, so the
 *   setter is a filter, not a renderer: it re-fetches the coach result only
 *   when the advice sensor reports a new calculation;
 * * all data comes from the integration's own WebSocket API. There is no
 *   `fetch`, and no `localStorage`, `sessionStorage`, `IndexedDB` or cookie
 *   anywhere in this panel — the backend storage is the only truth
 *   (SPEC.md §9);
 * * every colour is a Home Assistant theme variable. `ha-card` gets no
 *   background, radius or shadow of its own, so the user's own theme keeps
 *   styling it (SPEC.md §10).
 */

import { createApi, describeError } from './core/api.js';
import { el, setVisible } from './core/dom.js';
import { createState } from './core/state.js';
import { onTap } from './core/tap.js';
import { coachTab } from './tabs/coach.js';
import { devicesTab } from './tabs/devices.js';
import { installationTab } from './tabs/installation.js';
import { logbookTab } from './tabs/logbook.js';
import { overviewTab } from './tabs/overview.js';
import { preferencesTab } from './tabs/preferences.js';

const VERSION = '0.7.2';

/**
 * Tab order as SPEC.md §33.6 lists it.
 *
 * Six tabs, and **the same six for an installer and a resident**. There is no
 * tab a resident does not see; what he does not own is greyed out where he can
 * read it (`core/roles.js`).
 *
 * That is a choice against the alternative of two tab sets, one per role. The
 * reason is the phone call this whole round exists for: a resident rings about
 * his main fuse, and with two sets the two of them are looking at different
 * screens, so "ga naar Installatie, wat staat er bij Hoofdzekering?" is not a
 * usable sentence. One set is one mental model, one code path and one test
 * matrix — and one tab fewer for the installer as well.
 */
const TABS = [
  overviewTab,
  coachTab,
  devicesTab,
  preferencesTab,
  installationTab,
  logbookTab,
];

/**
 * The sensor whose `last_calculated` attribute tells the panel that a new
 * calculation happened. Reading it is a *signal*, never a data source: the
 * numbers themselves come from coach/get.
 */
const ADVICE_ENTITY = 'sensor.domotiapp_energy_current_advice';

const STYLES = `
  /*
   * Hiding, and the reason this rule is not the browser's own.
   *
   * The user-agent sheet has [hidden] { display: none }, but every rule below
   * that sets display is an author declaration and therefore wins in the
   * cascade. Setting .hidden alone left tab panels, tab buttons, notices and
   * the banner permanently on screen in phase 7a. Both selectors are listed so
   * a Home Assistant component that sets the attribute itself is hidden too.
   */
  [hidden],
  .is-hidden {
    display: none !important;
  }

  :host {
    /*
     * Typography for the DomotiTech house style.
     *
     * Headings are meant to be an elegant serif. Home Assistant offers the
     * seam for it: --ha-font-family-heading exists and points at the body
     * font by default, so overriding it here is using their system rather
     * than fighting it. It is still pointing at the Home Assistant font until
     * that choice is confirmed; switching it is this one declaration.
     *
     * The intended value, with no web font and therefore no CDN:
     *   ui-serif, Georgia, 'Iowan Old Style', 'Palatino Linotype',
     *   'Times New Roman', 'Noto Serif', 'Liberation Serif', serif
     */
    --domotiapp-font-heading: var(--ha-font-family-heading, inherit);

    /* Rhythm. Generous by design: this style breathes, and a crowded card
       turns muddy under the customer's Liquid Glass theme. */
    --domotiapp-space-row: 20px;
    --domotiapp-space-section: 40px;

    display: block;
    padding: 32px 16px;
    padding-bottom: calc(32px + env(safe-area-inset-bottom));
    box-sizing: border-box;
    color: var(--primary-text-color);
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }

  .layout {
    max-width: 1400px;
    margin: 0 auto;
  }

  /*
   * Small capitals with wide letterspacing, for every label and button. The
   * house style uses these as its quiet structural voice.
   */
  .label,
  .tab-button,
  .button,
  .stat-label {
    font-size: 0.7rem;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--secondary-text-color);
  }

  /* --- Tab bar: hairline and text, no boxed-in buttons ------------------- */

  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 24px;
    max-width: 760px;
    margin: 0 auto var(--domotiapp-space-section);
    border-bottom: 1px solid var(--divider-color);
  }
  .tab-button {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    padding: 0 2px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    background: none;
    cursor: pointer;
  }
  .tab-button ha-icon {
    --mdc-icon-size: 18px;
  }
  .tab-button[aria-selected='true'] {
    color: var(--primary-color);
    border-bottom-color: var(--primary-color);
  }
  .tab-button:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 4px;
  }

  /* --- One narrow column, with air between the sections ------------------ */

  .tab-content {
    display: grid;
    grid-template-columns: minmax(0, 760px);
    justify-content: center;
    gap: var(--domotiapp-space-section);
  }

  .card-title {
    margin: 0;
    padding: 32px 32px 0;
    font-family: var(--domotiapp-font-heading);
    font-size: 1.5rem;
    font-weight: 400;
    letter-spacing: 0.01em;
  }
  .card-body {
    padding: 24px 32px 32px;
  }
  .subheading {
    margin: var(--domotiapp-space-section) 0 12px;
    font-family: var(--domotiapp-font-heading);
    font-size: 1.1rem;
    font-weight: 400;
    /* Blue is reserved for headings, links and the one primary button. */
    color: var(--primary-color);
  }

  /* --- Headline figures --------------------------------------------------- */

  .display-row {
    display: flex;
    flex-wrap: wrap;
    gap: 40px;
    margin-bottom: var(--domotiapp-space-section);
  }
  .display-metric {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-width: 120px;
  }
  .display-figure {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }
  .display-value {
    font-size: 3rem;
    font-weight: 300;
    line-height: 1;
    font-variant-numeric: lining-nums tabular-nums;
  }
  .display-suffix,
  .display-empty {
    font-size: 0.85rem;
    color: var(--secondary-text-color);
  }

  /* --- Rows: hairlines, not boxes ---------------------------------------- */

  .stat-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
    padding: var(--domotiapp-space-row) 0;
    border-top: 1px solid var(--divider-color);
  }
  .stat-value-wrap {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    text-align: right;
  }
  .stat-value {
    font-size: 1.05rem;
    font-variant-numeric: lining-nums tabular-nums;
    overflow-wrap: anywhere;
  }
  .stat-value.is-empty {
    color: var(--secondary-text-color);
    font-style: italic;
  }
  .stat-hint {
    margin-top: 4px;
    font-size: 0.8rem;
    color: var(--secondary-text-color);
  }

  /* --- Notices ------------------------------------------------------------ */

  .notice {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    margin-top: var(--domotiapp-space-row);
    padding-top: var(--domotiapp-space-row);
    border-top: 1px solid var(--divider-color);
    font-size: 0.9rem;
    color: var(--secondary-text-color);
  }
  .notice[data-tone='warning'] {
    color: var(--warning-color);
  }
  .notice ha-icon {
    flex: none;
    --mdc-icon-size: 20px;
  }

  /* --- Advice ------------------------------------------------------------- */

  .advice-title {
    margin: 0 0 8px;
    font-family: var(--domotiapp-font-heading);
    font-size: 1.25rem;
    font-weight: 400;
  }
  .advice-message {
    margin: 0 0 var(--domotiapp-space-row);
    max-width: 58ch;
    line-height: 1.6;
    color: var(--secondary-text-color);
  }
  .advice-list {
    display: flex;
    flex-direction: column;
  }
  .advice-item {
    padding: var(--domotiapp-space-row) 0;
    border-top: 1px solid var(--divider-color);
  }
  .advice-item-title {
    margin: 6px 0 4px;
    font-size: 1rem;
  }
  .advice-item-message {
    margin: 0;
    max-width: 58ch;
    line-height: 1.6;
    color: var(--secondary-text-color);
  }

  /* --- Forms and buttons -------------------------------------------------- */

  ha-form {
    display: block;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    margin-top: var(--domotiapp-space-section);
    padding-top: var(--domotiapp-space-row);
    border-top: 1px solid var(--divider-color);
  }
  .button {
    min-height: 44px;
    padding: 0 20px;
    border: 1px solid var(--divider-color);
    border-radius: 4px;
    background: none;
    color: var(--primary-text-color);
    cursor: pointer;
  }
  /* Blue is reserved for headings, links and the one primary button. */
  .button-primary {
    border-color: var(--primary-color);
    background: var(--primary-color);
    color: var(--text-primary-color);
  }
  .button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .button:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }

  /* --- Lists of configured rows ------------------------------------------- */

  .row-list {
    display: flex;
    flex-direction: column;
  }
  .row-item {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px 16px;
    padding: var(--domotiapp-space-row) 0;
    border-top: 1px solid var(--divider-color);
  }
  .row-main {
    flex: 1 1 220px;
    min-width: 0;
  }
  .row-name {
    margin: 0 0 4px;
    font-size: 1.05rem;
    overflow-wrap: anywhere;
  }
  .row-meta {
    margin: 0;
    font-size: 0.85rem;
    color: var(--secondary-text-color);
  }
  /*
   * A status marker is text, never a coloured dot: colour alone may not carry
   * meaning (SPEC.md §23). The colour is an extra for those who can see it.
   */
  .row-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 6px;
    font-size: 0.8rem;
    color: var(--secondary-text-color);
  }
  .row-status[data-tone='warning'] {
    color: var(--warning-color);
  }
  .row-status[data-tone='error'] {
    color: var(--error-color);
  }
  .row-status ha-icon {
    --mdc-icon-size: 16px;
  }
  .row-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .empty-text {
    margin: var(--domotiapp-space-row) 0 0;
    max-width: 58ch;
    line-height: 1.6;
    color: var(--secondary-text-color);
  }

  /*
   * The actions of a whole tab, after its cards rather than inside the last
   * one: a save button under a topic heading reads as if it saved that topic.
   */
  .tab-actions .actions {
    margin-top: 0;
    padding-top: 0;
    border-top: none;
  }

  /* --- Folding sections inside a dialog ----------------------------------- */

  .section + .section {
    border-top: 1px solid var(--divider-color);
  }
  .section-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    width: 100%;
    /* The 44 px tap target SPEC.md §11 asks for, on the full width. */
    min-height: 44px;
    padding: 12px 0;
    border: none;
    background: none;
    color: var(--primary-text-color);
    text-align: left;
    cursor: pointer;
  }
  .section-toggle:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .section-title {
    font-size: 0.7rem;
    font-weight: 500;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--secondary-text-color);
  }
  .section-chevron {
    flex: none;
    --mdc-icon-size: 20px;
    color: var(--secondary-text-color);
  }
  .section-body {
    padding-bottom: var(--domotiapp-space-row);
  }

  /* --- The coach's question selector -------------------------------------- */

  .question-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: var(--domotiapp-space-row);
  }
  /*
   * A list of missing items, without the bullets: a long Dutch sentence behind
   * a bullet reads as an error list rather than as a to-do (SPEC.md §8).
   */
  .plain-list {
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .plain-item {
    padding: 12px 0;
    border-top: 1px solid var(--divider-color);
  }

  /* --- Dialogs ------------------------------------------------------------ */

  .dialog {
    position: fixed;
    inset: 0;
    z-index: 10;
    display: flex;
    align-items: center;
    justify-content: center;
    /* On a phone the sheet fills the screen; the padding only bites on desktop. */
    padding: 16px;
    padding-bottom: calc(16px + env(safe-area-inset-bottom));
    box-sizing: border-box;
  }
  /*
   * The backdrop takes Home Assistant's own scrim colour, so a theme that
   * changes it changes ours too. The fallback is the only colour literal in
   * this stylesheet and it is deliberately neutral: a scrim has to be *some*
   * darkening even when no theme defines one, and reaching for the brand
   * colour there would be worse than a neutral black (SPEC.md §10).
   */
  .dialog-scrim {
    position: absolute;
    inset: 0;
    background: var(--mdc-dialog-scrim-color, rgba(0, 0, 0, 0.5));
    backdrop-filter: var(--ha-dialog-scrim-backdrop-filter, none);
  }
  .dialog-surface {
    position: relative;
    display: flex;
    flex-direction: column;
    width: 100%;
    /* The desktop maximum SPEC.md §11 asks for. */
    max-width: 640px;
    max-height: 100%;
    border-radius: 8px;
    background: var(--card-background-color);
    color: var(--primary-text-color);
    /* The theme's own card shadow, so the sheet lifts the way its cards do. */
    box-shadow: var(--ha-card-box-shadow, none);
    overflow: hidden;
  }
  .dialog-surface:focus {
    outline: none;
  }
  .dialog-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    padding: 24px 24px 0;
  }
  .dialog-title {
    margin: 0;
    font-family: var(--domotiapp-font-heading);
    font-size: 1.35rem;
    font-weight: 400;
  }
  .dialog-close {
    flex: none;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    margin: -10px -10px 0 0;
    border: none;
    background: none;
    color: var(--secondary-text-color);
    cursor: pointer;
  }
  .dialog-close:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .dialog-body {
    padding: 16px 24px 0;
    /* The form scrolls, the dialog itself never does, so the actions stay put. */
    overflow-y: auto;
  }
  .dialog-message {
    margin: 0 0 8px;
    max-width: 58ch;
    line-height: 1.6;
  }
  .dialog-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 12px;
    padding: 24px;
  }
  /*
   * The destructive button is outlined in the error colour and says what it
   * does; the safe choice keeps the primary fill, so the dangerous one is never
   * the default target of a hurried hand.
   */
  .button-danger {
    border-color: var(--error-color);
    color: var(--error-color);
  }

  /* --- Narrow screens ------------------------------------------------------ */

  /*
   * The desktop rhythm is deliberately generous, and on a phone it is simply in
   * the way: 32 px of card padding on a 358 px column leaves little for the
   * content, and the tab bar took a fifth of the screen before anything was
   * read. Nothing is hidden here — the tabs still wrap and every target keeps
   * its 44 px — the air is only taken in (SPEC.md §11).
   *
   * A **container** query rather than a media query, because the question is
   * how wide *this panel* is, not how wide the screen is: with the Home
   * Assistant sidebar open on a tablet the viewport is roomy while the panel is
   * not. It also makes the rule testable without resizing a browser window.
   *
   * The containment sits on .layout and not on :host on purpose. A
   * container-type of inline-size applies layout containment, which makes the
   * element a containing block for fixed-position descendants — on the host
   * that would pull the dialog's backdrop in from the viewport to the panel,
   * the exact failure that was checked for when the dialog was built. The
   * dialog lives outside .layout, so it keeps the viewport.
   *
   * No backticks in this stylesheet: it is a template literal, and one closes
   * it. That cost a load of the whole panel once.
   */
  .layout {
    container-type: inline-size;
    container-name: panel;
  }

  @container panel (max-width: 600px) {
    .tabs {
      gap: 0 16px;
      margin-bottom: var(--domotiapp-space-row);
    }
    .tab-content {
      gap: var(--domotiapp-space-row);
    }
    .card-title {
      padding: 20px 20px 0;
      font-size: 1.3rem;
    }
    .card-body {
      padding: 16px 20px 24px;
    }
    .display-row {
      gap: 24px;
    }
    .display-value {
      font-size: 2.4rem;
    }
  }

  /*
   * The dialog is not inside that container, so its phone behaviour is a media
   * query: on a narrow screen it is a full sheet, because the frame around it
   * is wasted space in a meter cupboard.
   */
  @media (max-width: 600px) {
    :host {
      padding: 16px 12px;
      padding-bottom: calc(16px + env(safe-area-inset-bottom));
    }
    .dialog {
      padding: 0;
    }
    .dialog-surface {
      max-width: none;
      height: 100%;
      border-radius: 0;
      padding-bottom: env(safe-area-inset-bottom);
    }
  }

  /* --- Status banner ------------------------------------------------------ */

  .banner {
    display: flex;
    align-items: center;
    gap: 8px;
    max-width: 760px;
    margin: 0 auto var(--domotiapp-space-row);
    font-size: 0.9rem;
    color: var(--secondary-text-color);
  }
  .banner[data-tone='error'] {
    color: var(--error-color);
  }
`;

class DomotiAppEnergyPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._state = createState();
    this._built = false;
    this._activeTab = TABS[0].id;
    /** Built tab instances, keyed by id; each is created at most once. */
    this._tabs = new Map();
    this._tabButtons = new Map();
    this._lastCalculated = null;
    this._unsubscribe = null;
    this._loading = false;
    /** How many dialogs are holding the page behind them inert. */
    this._inertDepth = 0;
  }

  /**
   * Home Assistant assigns this on nearly every state change, so it must stay
   * cheap. It only re-fetches when our own advice sensor reports a newer
   * calculation than the one already on screen.
   */
  set hass(hass) {
    const first = this._hass === null;
    this._hass = hass;
    this._state.setAdmin(Boolean(hass?.user?.is_admin));

    if (first) {
      this._load();
      return;
    }
    this._refreshLiveIfChanged();
  }

  set narrow(value) {
    this._narrow = value;
  }

  set route(value) {
    this._route = value;
  }

  set panel(value) {
    this._panel = value;
  }

  connectedCallback() {
    this._buildDOM();
    this._unsubscribe = this._state.subscribe(() => this._update());
    this._update();
    if (this._hass && !this._state.get().config) {
      this._load();
    }
  }

  disconnectedCallback() {
    // Only the state subscription is released. The tap listeners stay: Home
    // Assistant disconnects and reconnects this element when the user
    // navigates away and back, and removing them here would leave the tabs
    // dead on the second visit. They live inside our own shadow root and go
    // when the element does.
    if (this._unsubscribe) {
      this._unsubscribe();
      this._unsubscribe = null;
    }
  }

  // --- Building -------------------------------------------------------------

  _buildDOM() {
    if (this._built) {
      return;
    }
    this._built = true;

    const style = document.createElement('style');
    style.textContent = STYLES;

    this._banner = el('div', { class: 'banner' });
    setVisible(this._banner, false);
    this._bannerText = el('span');
    this._banner.appendChild(this._bannerText);

    this._tabBar = el('nav', {
      class: 'tabs',
      attrs: { role: 'tablist', 'aria-label': 'DomotiApp Energy tabbladen' },
    });

    for (const tab of TABS) {
      const tabButton = el('button', {
        class: 'tab-button',
        type: 'button',
        attrs: {
          role: 'tab',
          'aria-selected': String(tab.id === this._activeTab),
          'aria-controls': `panel-${tab.id}`,
          id: `tab-${tab.id}`,
        },
      });
      tabButton.append(
        el('ha-icon', { attrs: { icon: tab.icon, 'aria-hidden': 'true' } }),
        el('span', { text: tab.label }),
      );
      // The unsubscribe is not kept: these listeners must outlive a
      // disconnect, see disconnectedCallback().
      onTap(tabButton, () => this._selectTab(tab.id));
      this._tabBar.appendChild(tabButton);
      this._tabButtons.set(tab.id, tabButton);
    }

    this._tabHost = el('div', { class: 'tab-host' });

    this._layout = el('div', { class: 'layout' }, [
      this._banner,
      this._tabBar,
      this._tabHost,
    ]);

    // Dialogs live here, outside the layout, for one reason: a dialog makes
    // everything behind it `inert`, and an element cannot make its own ancestor
    // inert without disabling itself.
    this._overlayHost = el('div', { class: 'overlay-host' });

    this.shadowRoot.append(style, this._layout, this._overlayHost);
  }

  /**
   * What a tab is given to put a dialog on screen.
   *
   * Narrow on purpose, like the rest of the tab context: a tab may add an
   * overlay and say whether the page behind it is reachable, and nothing else.
   */
  _overlay() {
    return {
      mount: (node) => this._overlayHost.appendChild(node),
      /**
       * Counted rather than set, because dialogs stack.
       *
       * A confirmation opens on top of a form dialog and closes again first.
       * With a plain boolean its close would hand the page behind *both* of
       * them back to the keyboard while the form is still open.
       */
      setBackgroundInert: (inert) => {
        this._inertDepth = Math.max(0, this._inertDepth + (inert ? 1 : -1));
        this._layout.inert = this._inertDepth > 0;
      },
    };
  }

  /** Build one tab the first time it is opened, then reuse it. */
  _ensureTab(id) {
    if (this._tabs.has(id)) {
      return this._tabs.get(id);
    }
    const definition = TABS.find((tab) => tab.id === id);
    // The context is deliberately narrow: a tab may read the current hass and
    // the shared state, and nothing else of the panel.
    const instance = definition.create({
      getHass: () => this._hass,
      state: this._state,
      overlay: this._overlay(),
    });
    instance.element.id = `panel-${id}`;
    instance.element.setAttribute('role', 'tabpanel');
    instance.element.setAttribute('aria-labelledby', `tab-${id}`);
    setVisible(instance.element, false);
    this._tabHost.appendChild(instance.element);
    this._tabs.set(id, instance);
    return instance;
  }

  _selectTab(id) {
    if (id === this._activeTab) {
      return;
    }
    // A tab with unsaved changes may refuse, and asks the question itself
    // (SPEC.md §22). The callback is how it says "go ahead" afterwards.
    const current = this._tabs.get(this._activeTab);
    if (current?.canLeave && !current.canLeave(() => this._switchTo(id))) {
      return;
    }
    this._switchTo(id);
  }

  _switchTo(id) {
    this._activeTab = id;
    this._update();
  }

  // --- Updating -------------------------------------------------------------

  _update() {
    if (!this._built) {
      return;
    }
    const state = this._state.get();

    // No tab is hidden any more. Four of them used to disappear for a
    // non-admin, which meant a resident could not see that his main fuse was
    // wrong — and could not set his own quiet hours either, on a tab made
    // entirely of his own preferences. Each form now greys out what he does not
    // own (SPEC.md §33.6), and the backend still refuses the write regardless: a
    // disabled field is not a permission check.
    for (const tab of TABS) {
      this._tabButtons
        .get(tab.id)
        .setAttribute('aria-selected', String(tab.id === this._activeTab));
    }

    const active = this._ensureTab(this._activeTab);
    for (const [id, instance] of this._tabs) {
      setVisible(instance.element, id === this._activeTab);
    }
    active.update(state);

    if (state.status === 'error') {
      this._showBanner(state.error, 'error');
    } else if (state.status === 'loading') {
      this._showBanner('Gegevens laden…', 'info');
    } else {
      this._showBanner(null);
    }
  }

  _showBanner(text, tone = 'info') {
    this._bannerText.textContent = text || '';
    this._banner.dataset.tone = tone;
    setVisible(this._banner, Boolean(text));
  }

  // --- Loading --------------------------------------------------------------

  async _load() {
    // hass can be assigned before the element is connected, so both paths can
    // reach this. Loading twice would fire two identical round trips.
    if (!this._hass || this._loading) {
      return;
    }
    this._loading = true;
    const api = createApi(this._hass);
    this._state.setStatus('loading');
    try {
      const [config, live] = await Promise.all([api.getConfig(), api.getCoach()]);
      this._state.setConfig(config);
      this._state.setLive(live);
      this._lastCalculated = this._currentCalculatedAt();
      this._state.setStatus('ready');
    } catch (error) {
      this._state.setStatus('error', describeError(error));
    } finally {
      this._loading = false;
    }
  }

  /**
   * Re-fetch the coach result when a new calculation has been made.
   *
   * The advice sensor publishes the moment of the last calculation, so this
   * costs one attribute read per `hass` assignment and a WebSocket round trip
   * only when something actually changed.
   */
  async _refreshLiveIfChanged() {
    const calculatedAt = this._currentCalculatedAt();
    if (!calculatedAt || calculatedAt === this._lastCalculated) {
      return;
    }
    this._lastCalculated = calculatedAt;

    try {
      this._state.setLive(await createApi(this._hass).getCoach());
    } catch (error) {
      this._state.setStatus('error', describeError(error));
    }
  }

  _currentCalculatedAt() {
    return this._hass?.states?.[ADVICE_ENTITY]?.attributes?.last_calculated ?? null;
  }
}

if (!customElements.get('domotiapp-energy-panel')) {
  customElements.define('domotiapp-energy-panel', DomotiAppEnergyPanel);
}

console.info(
  `%c DOMOTIAPP ENERGY %c v${VERSION} `,
  'background: var(--primary-color); color: white; font-weight: bold;',
  'background: transparent; color: inherit;',
);
