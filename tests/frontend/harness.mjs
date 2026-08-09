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

import { fakeHass, sampleCoach, sampleConfig } from './fixtures.mjs';

// Re-exported so every existing test keeps importing its fixtures from the
// harness; the move is an internal one.
export { fakeHass, sampleCoach, sampleConfig };

const PANEL_URL = new URL(
  '../../custom_components/domotiapp_energy/frontend/domotiapp-energy-panel.js',
  import.meta.url,
);

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
