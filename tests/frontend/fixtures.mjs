/**
 * The fixtures both browserless and browser tests are handed.
 *
 * Split out of `harness.mjs` when the Playwright layer arrived, and the split
 * is the point: a fixture that describes the home twice describes it
 * differently within a week, and this project has already been bitten by a
 * default that quietly encoded the defect (CLAUDE.md, "Een fixture kan de bug
 * vastleggen"). One home, two runners.
 *
 * Nothing here may import jsdom or touch `globalThis`: this module is served to
 * a real browser as-is, over http, by `tests/browser/server.mjs`.
 */

const ADVICE_ENTITY = 'sensor.domotiapp_energy_current_advice';

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
/**
 * Gisteren, zoals `history/get` het teruggeeft (SPEC.md §61).
 *
 * Standaard een dag zonder geschiedenis: dat is wat een verse installatie ziet,
 * en het is de toestand waarin het blok zich stil moet houden.
 */
export function sampleHistory(overrides = {}) {
  return {
    date: '2026-08-10',
    surplus_hours: null,
    peak_grid_power_w: null,
    peak_grid_load_percent: null,
    complete_all_day: null,
    has_data: false,
    ...overrides,
  };
}

export function fakeHass({
  isAdmin = true,
  config,
  coach,
  history,
  issues = {},
} = {}) {
  const stored = config ?? sampleConfig();
  const answers = {
    'domotiapp_energy/config/get': stored,
    'domotiapp_energy/coach/get': coach ?? sampleCoach(),
    'domotiapp_energy/history/get': history ?? sampleHistory(),
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
