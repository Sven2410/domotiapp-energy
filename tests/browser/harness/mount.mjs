/**
 * Mount the real panel in a real browser, with the same fixtures the
 * browserless tests use.
 *
 * Everything a test needs hangs off `window.harness`, so the specs stay
 * readable: they resize, they call `harness.remount(...)`, they measure. No
 * test reaches into the panel's internals from the spec file.
 */

import { fakeHass, sampleCoach, sampleConfig } from '/tests/frontend/fixtures.mjs';

await import('/custom_components/domotiapp_energy/frontend/domotiapp-energy-panel.js');

/** Let the panel's two awaits resolve; there are no timers in its load path. */
async function settle() {
  for (let index = 0; index < 5; index += 1) {
    await Promise.resolve();
    await new Promise((resolve) => requestAnimationFrame(resolve));
  }
}

/**
 * Replace whatever is on the page with a freshly loaded panel.
 *
 * `isAdmin` decides which tabs exist at all, so a layout measured as the
 * installer is not the layout the resident sees — six tabs against four is
 * exactly the kind of difference a width test has to be able to ask for.
 */
async function remount({ isAdmin = true, config, coach } = {}) {
  document.body.textContent = '';
  const panel = document.createElement('domotiapp-energy-panel');
  panel.hass = fakeHass({
    isAdmin,
    config: config ?? sampleConfig(),
    coach: coach ?? sampleCoach(),
  });
  document.body.appendChild(panel);
  await settle();
  window.harness.panel = panel;
  return panel;
}

/**
 * Fake the four safe-area insets.
 *
 * `env(safe-area-inset-*)` cannot be written from script or from a stylesheet,
 * so the behaviour it drives would otherwise only be observable on a device
 * with a notch. The panel reads the four values through custom properties for
 * this reason (SPEC.md §40.2); setting them inline on the host overrides the
 * `:host` declaration and gives any browser, at any size, the phone's geometry.
 *
 * This fakes the *inputs*, not the layout: every rule under test is the rule
 * that ships.
 */
function setInsets({ top = 0, right = 0, bottom = 0, left = 0 } = {}) {
  const panel = window.harness.panel;
  panel.style.setProperty('--domotiapp-safe-top', `${top}px`);
  panel.style.setProperty('--domotiapp-safe-right', `${right}px`);
  panel.style.setProperty('--domotiapp-safe-bottom', `${bottom}px`);
  panel.style.setProperty('--domotiapp-safe-left', `${left}px`);
}

/** Query inside the panel's shadow root. */
function find(selector) {
  return window.harness.panel.shadowRoot.querySelector(selector);
}

/** Query all inside the panel's shadow root. */
function findAll(selector) {
  return [...window.harness.panel.shadowRoot.querySelectorAll(selector)];
}

window.harness = {
  panel: null,
  remount,
  setInsets,
  settle,
  find,
  findAll,
  sampleConfig,
  sampleCoach,
};

await remount();
window.harnessReady = true;
