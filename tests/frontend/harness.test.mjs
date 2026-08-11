/**
 * Het meetgereedschap zelf (SPEC.md §9).
 *
 * Deze tests bestaan omdat een assertie op `textContent` slaagt op een zin die
 * op het scherm nul hoogte heeft — dezelfde blinde vlek als de cascadebug van
 * fase 7a, nu in de meting in plaats van in de code. Als `visibleText` dat
 * onderscheid niet maakt, is elke test die hem gebruikt stil waardeloos.
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { JSDOM } from 'jsdom';

import { visibleText } from './harness.mjs';

function build(html) {
  return new JSDOM(`<div id="root">${html}</div>`).window.document.getElementById(
    'root',
  );
}

describe('visibleText', () => {
  it('leest wat er staat', () => {
    assert.equal(visibleText(build('<p>Staat vol.</p>')).trim(), 'Staat vol.');
  });

  it('slaat over wat het paneel verborgen heeft', () => {
    // De klasse is het contract van dit paneel (core/dom.js `setVisible`).
    const root = build('<p class="is-hidden">Er is niets te doen.</p><p>Vaatwasser</p>');

    assert.match(root.textContent, /Er is niets te doen/);
    assert.doesNotMatch(visibleText(root), /Er is niets te doen/);
    assert.match(visibleText(root), /Vaatwasser/);
  });

  it('slaat een hele verborgen tak over, niet alleen het element zelf', () => {
    // Verbergen gebeurt op de kaart of de rij; de zin eronder erft dat.
    const root = build('<div class="is-hidden"><p>Staat vol.</p></div>');

    assert.doesNotMatch(visibleText(root), /Staat vol/);
  });

  it('leest ook het hidden-attribuut, dat setVisible ernaast zet', () => {
    const root = build('<p hidden>Staat vol.</p>');

    assert.doesNotMatch(visibleText(root), /Staat vol/);
  });
});
