/**
 * A DOM to run the panel in, without a browser.
 *
 * jsdom gives real elements, real events and a real custom-element registry,
 * which is enough to answer "what did the panel do to the DOM". What it does
 * **not** give is a trustworthy cascade: its `getComputedStyle` implements only
 * part of CSS, so it cannot settle a question like "does an author `display`
 * rule beat the user-agent's `[hidden]`". That is exactly the question that
 * broke phase 7a.
 *
 * So these tests never ask jsdom about computed styles. They assert the panel's
 * *own* contract instead: `setVisible()` toggles the `is-hidden` class, and the
 * stylesheet backs that class with `display: none !important`. The class is
 * ours and is testable here; the rule behind it is one line that a browser
 * cannot misread.
 */

import { JSDOM } from 'jsdom';

const PANEL_URL = new URL(
  '../../custom_components/domotiapp_energy/frontend/domotiapp-energy-panel.js',
  import.meta.url,
);

/** The six entity ids are fixed; the panel watches this one for a new result. */
const ADVICE_ENTITY = 'sensor.domotiapp_energy_current_advice';

let panelModuleLoaded = false;

/** Install a DOM into the global scope and load the panel module once. */
export async function loadPanelModule() {
  if (panelModuleLoaded) {
    return;
  }
  const dom = new JSDOM('<!doctype html><html><body></body></html>', {
    pretendToBeVisual: true,
  });

  for (const name of [
    'window',
    'document',
    'HTMLElement',
    'customElements',
    'Element',
    'Node',
    'Event',
    'CustomEvent',
    'getComputedStyle',
  ]) {
    globalThis[name] = dom.window[name];
  }

  await import(PANEL_URL.href);
  panelModuleLoaded = true;
}

/** A configuration with one usable source, as config/get returns it. */
export function sampleConfig(overrides = {}) {
  return {
    schema_version: 1,
    revision: 7,
    home: {
      home_name: 'Mijn woning',
      phases: 1,
      main_fuse_a: 25,
      max_grid_power_w: 5750,
      peak_warning_percent: 80,
      contract_type: 'fixed',
      feed_in_cost_eur_kwh: null,
      net_metering_until: '2027-01-01',
      min_solar_surplus_w: 500,
    },
    sources: [{ id: 'grid', name: 'Netmeter', type: 'grid_meter', enabled: true }],
    devices: [],
    preferences: { max_advice_count: 3 },
    // Validation issues ride along with every read and write answer, keyed by
    // subject, so a form can place each message per field (SPEC.md §14).
    issues: {},
    ...overrides,
  };
}

/** A coach result, as coach/get returns it. */
export function sampleCoach(overrides = {}) {
  const metrics = {
    grid_power_w: -5700,
    solar_power_w: null,
    solar_surplus_w: 5700,
    solar_surplus_confidence: 'high',
    grid_load_percent: 99.1,
    peak_risk: true,
    data_quality: { score: 60, missing_items: ['solar_source_valid'] },
    energy_score: 46,
    score_components: {},
    reason_codes: [],
    ...(overrides.metrics || {}),
  };
  return {
    generated_at: '2026-08-05T16:00:00+00:00',
    primary_advice: {
      id: 'missing_required_data',
      title: 'Aanvullende gegevens nodig',
      message: 'Vul de ontbrekende energiegegevens aan.',
      severity: 'warning',
      reason_code: 'missing_required_data',
      confidence: 'high',
    },
    advice: [
      {
        id: 'missing_required_data',
        title: 'Aanvullende gegevens nodig',
        message: 'Vul de ontbrekende energiegegevens aan.',
        severity: 'warning',
        reason_code: 'missing_required_data',
        confidence: 'high',
      },
    ],
    explanations: {},
    missing_data: [],
    ...overrides,
    metrics,
  };
}

/**
 * A stand-in for the Home Assistant object the panel is handed.
 *
 * `sent` records every command, so a test can assert what actually went over
 * the wire — which is the only place the panel's promises about saving can be
 * checked. The write commands answer in the real shape: `revision`, `item` and
 * `issues` (SPEC.md §14).
 */
export function fakeHass({ isAdmin = true, config, coach, issues = {} } = {}) {
  const stored = config ?? sampleConfig();
  const answers = {
    'domotiapp_energy/config/get': stored,
    'domotiapp_energy/coach/get': coach ?? sampleCoach(),
  };
  const sent = [];
  let revision = stored.revision;

  const hass = {
    user: { is_admin: isAdmin },
    sent,
    states: {
      [ADVICE_ENTITY]: {
        entity_id: ADVICE_ENTITY,
        state: 'Aanvullende gegevens nodig',
        attributes: { last_calculated: '2026-08-05T16:00:00+00:00' },
      },
    },
    callWS: async (message) => {
      sent.push(message);
      if (message.type in answers) {
        return answers[message.type];
      }
      const write = writeAnswer(message, () => (revision += 1), issues);
      if (write) {
        return write;
      }
      throw { code: 'unknown_command', message: message.type };
    },
  };
  return hass;
}

/** Answer a write command the way the backend does, or return null. */
function writeAnswer(message, nextRevision, issues) {
  const shapes = {
    'domotiapp_energy/sources/create': () => message.source,
    'domotiapp_energy/sources/update': () => message.source,
    'domotiapp_energy/sources/delete': () => null,
    'domotiapp_energy/devices/create': () => message.device,
    'domotiapp_energy/devices/update': () => message.device,
    'domotiapp_energy/devices/delete': () => null,
    // The resident's write. It answers with the merged row, the way the
    // backend does — only the fields it was sent, folded into what was there.
    'domotiapp_energy/devices/set_operation': () => ({
      id: message.device_id,
      ...message.operation,
    }),
    'domotiapp_energy/home/update': () => message.home,
    'domotiapp_energy/preferences/update': () => message.preferences,
    'domotiapp_energy/logs/clear': () => null,
  };
  const shape = shapes[message.type];
  if (!shape) {
    return null;
  }
  const item = shape();
  return {
    revision: nextRevision(),
    // A created row gets its id from the backend when the panel did not send
    // one, exactly as uuid4 does there.
    item: item ? { id: item.id ?? 'nieuw-id', ...item } : null,
    issues,
  };
}

/**
 * Create the panel, hand it a hass object and wait until it has loaded.
 *
 * The panel fetches over two awaits, so a couple of microtask turns are enough;
 * there are no timers involved.
 */
export async function mountPanel(hass = fakeHass()) {
  await loadPanelModule();

  const element = document.createElement('domotiapp-energy-panel');
  element.hass = hass;
  document.body.appendChild(element);

  await settle();
  return element;
}

/** Let the panel's pending promises resolve. */
export async function settle() {
  for (let index = 0; index < 5; index += 1) {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
}

/** Whether an element is visible according to the panel's own contract. */
export function isVisible(element) {
  return !element.classList.contains('is-hidden');
}

/** Every tab button, in the order the panel renders them. */
export function tabButtons(panel) {
  return [...panel.shadowRoot.querySelectorAll('.tab-button')];
}

/** Every tab panel that has been built so far. */
export function tabPanels(panel) {
  return [...panel.shadowRoot.querySelectorAll('.tab-host > *')];
}

/** Click a tab button by its visible label. */
export function clickTab(panel, label) {
  const button = tabButtons(panel).find((node) =>
    node.textContent.includes(label),
  );
  if (!button) {
    throw new Error(`No tab button labelled ${label}`);
  }
  button.click();
  return button;
}
