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
import { el } from './core/dom.js';
import { createState } from './core/state.js';
import { onTap } from './core/tap.js';
import { coachTab } from './tabs/coach.js';
import { devicesTab } from './tabs/devices.js';
import { homeTab } from './tabs/home.js';
import { logbookTab } from './tabs/logbook.js';
import { overviewTab } from './tabs/overview.js';
import { preferencesTab } from './tabs/preferences.js';
import { sourcesTab } from './tabs/sources.js';

const VERSION = '0.1.0';

/** Tab order as SPEC.md §8 lists it. */
const TABS = [
  overviewTab,
  homeTab,
  sourcesTab,
  devicesTab,
  preferencesTab,
  coachTab,
  logbookTab,
];

/**
 * The sensor whose `last_calculated` attribute tells the panel that a new
 * calculation happened. Reading it is a *signal*, never a data source: the
 * numbers themselves come from coach/get.
 */
const ADVICE_ENTITY = 'sensor.domotiapp_energy_current_advice';

const STYLES = `
  :host {
    display: block;
    padding: 16px;
    padding-bottom: calc(16px + env(safe-area-inset-bottom));
    box-sizing: border-box;
    color: var(--primary-text-color);
    touch-action: manipulation;
    -webkit-tap-highlight-color: transparent;
  }
  .layout {
    max-width: 1400px;
    margin: 0 auto;
  }
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 16px;
    border-bottom: 1px solid var(--divider-color);
    padding-bottom: 8px;
  }
  .tab-button {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 44px;
    padding: 0 16px;
    border: none;
    border-radius: 8px;
    background: var(--secondary-background-color);
    color: var(--primary-text-color);
    font: inherit;
    font-size: 0.95rem;
    cursor: pointer;
  }
  .tab-button[aria-selected='true'] {
    background: var(--primary-color);
    color: var(--text-primary-color);
    font-weight: 600;
  }
  .tab-button:focus-visible {
    outline: 2px solid var(--primary-color);
    outline-offset: 2px;
  }
  .tab-content {
    display: grid;
    gap: 16px;
    grid-template-columns: 1fr;
  }
  @media (min-width: 900px) {
    .tab-content {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
  }
  .card-title {
    margin: 0;
    padding: 16px 16px 0;
    font-size: 1.05rem;
    font-weight: 600;
  }
  .card-body {
    padding: 8px 16px 16px;
  }
  .subheading {
    margin: 16px 0 4px;
    font-size: 0.95rem;
    font-weight: 600;
  }
  .stat-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: baseline;
    gap: 8px;
    padding: 8px 0;
    border-bottom: 1px solid var(--divider-color);
  }
  .stat-row:last-of-type {
    border-bottom: none;
  }
  .stat-label {
    color: var(--secondary-text-color);
  }
  .stat-value-wrap {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    text-align: right;
  }
  .stat-value {
    font-weight: 600;
    overflow-wrap: anywhere;
  }
  .stat-value.is-empty {
    font-weight: 400;
    color: var(--secondary-text-color);
    font-style: italic;
  }
  .stat-hint {
    font-size: 0.8rem;
    color: var(--secondary-text-color);
  }
  .notice {
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-top: 12px;
    color: var(--secondary-text-color);
  }
  .notice[data-tone='warning'] {
    color: var(--warning-color);
  }
  .notice[data-tone='success'] {
    color: var(--success-color);
  }
  .notice ha-icon {
    flex: none;
    --mdc-icon-size: 20px;
  }
  .advice-title {
    margin: 8px 0 4px;
    font-size: 1.1rem;
    font-weight: 600;
  }
  .advice-message {
    margin: 0 0 8px;
    color: var(--secondary-text-color);
  }
  .warning-list {
    margin: 0;
    padding-left: 20px;
  }
  .warning-item {
    margin-bottom: 4px;
    color: var(--warning-color);
  }
  .placeholder-text {
    margin: 8px 0;
    color: var(--secondary-text-color);
  }
  .banner {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    padding: 12px 16px;
    border-radius: 8px;
    background: var(--secondary-background-color);
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
    this._banner.hidden = true;
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

    const layout = el('div', { class: 'layout' }, [
      this._banner,
      this._tabBar,
      this._tabHost,
    ]);

    this.shadowRoot.append(style, layout);
  }

  /** Build one tab the first time it is opened, then reuse it. */
  _ensureTab(id) {
    if (this._tabs.has(id)) {
      return this._tabs.get(id);
    }
    const definition = TABS.find((tab) => tab.id === id);
    const instance = definition.create();
    instance.element.id = `panel-${id}`;
    instance.element.setAttribute('role', 'tabpanel');
    instance.element.setAttribute('aria-labelledby', `tab-${id}`);
    instance.element.hidden = true;
    this._tabHost.appendChild(instance.element);
    this._tabs.set(id, instance);
    return instance;
  }

  _selectTab(id) {
    this._activeTab = id;
    this._update();
  }

  // --- Updating -------------------------------------------------------------

  _update() {
    if (!this._built) {
      return;
    }
    const state = this._state.get();

    // Configuration tabs are hidden for non-admins. This is visibility only:
    // the backend refuses their writes regardless (SPEC.md §14).
    for (const tab of TABS) {
      const visible = state.isAdmin || !tab.adminOnly;
      this._tabButtons.get(tab.id).hidden = !visible;
      if (!visible && this._activeTab === tab.id) {
        this._activeTab = TABS[0].id;
      }
    }

    for (const tab of TABS) {
      this._tabButtons
        .get(tab.id)
        .setAttribute('aria-selected', String(tab.id === this._activeTab));
    }

    const active = this._ensureTab(this._activeTab);
    for (const [id, instance] of this._tabs) {
      instance.element.hidden = id !== this._activeTab;
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
    this._banner.hidden = !text;
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
