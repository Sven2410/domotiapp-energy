/**
 * De bedieningssectie op het Overzicht (SPEC.md §60).
 *
 * Wat de bewoner instelt staat waar het hoort; wat hij op een moment *doet*
 * staat op het scherm dat hij openslaat. Deze tests toetsen de twee vragen
 * waar dat op neerkomt: wanneer bestaat de sectie, en wat staat erin.
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { fakeHass, sampleCoach, sampleConfig } from './fixtures.mjs';
import { clickTab, isVisible, mountPanel, settle, tabPanels , visibleText } from './harness.mjs';

async function openOverview(hass = fakeHass()) {
  const panel = await mountPanel(hass);
  clickTab(panel, 'Overzicht');
  await settle();
  const tab = tabPanels(panel).find((node) => node.id === 'panel-overview');
  return { panel, tab, hass };
}

/** Een vaatwasser: een van de drie die iemand met de hand vult. */
function dishwasher(overrides = {}) {
  return {
    id: 'd1',
    name: 'Vaatwasser',
    device_type: 'dishwasher',
    enabled: true,
    priority: 'normal',
    control_mode: 'advice_only',
    needs_ready_flag: true,
    is_flexible: true,
    capabilities: [],
    days_of_week: [0, 1, 2, 3, 4, 5, 6],
    ...overrides,
  };
}

function flag(overrides = {}) {
  return {
    set_at: '2026-08-11T20:00:00+00:00',
    expires_at: '2026-08-12T05:00:00+00:00',
    auto_clears: false,
    ...overrides,
  };
}

function card(tab, title) {
  return [...tab.querySelectorAll('ha-card')].find((node) =>
    node.querySelector('.card-title')?.textContent.includes(title),
  );
}

describe('de sectie bestaat op grond van de configuratie', () => {
  it('staat er zodra er iets te bedienen is', async () => {
    const { tab } = await openOverview(
      fakeHass({ config: sampleConfig({ devices: [dishwasher()] }) }),
    );

    assert.equal(isVisible(card(tab, 'Wat je nu kunt doen')), true);
  });

  it('bestaat niet in een woning die niets te bedienen heeft', async () => {
    // Geen lege sectie die een tekortkoming aankondigt die deze woning nooit
    // kan opheffen — dezelfde regel als §39.3.
    const { tab } = await openOverview();

    assert.equal(isVisible(card(tab, 'Wat je nu kunt doen')), false);
  });

  it('vraagt niets over een apparaat waar de coach niets over zegt', async () => {
    // *Alleen meekijken* is de eigen uitknop van de bewoner. De vlag voedt
    // alleen het urgentie-advies, dus zonder advies leest niemand het antwoord.
    const { tab } = await openOverview(
      fakeHass({
        config: sampleConfig({
          devices: [dishwasher({ control_mode: 'monitor_only' })],
        }),
      }),
    );

    assert.equal(isVisible(card(tab, 'Wat je nu kunt doen')), false);
  });

  it('vraagt niets over een laadpaal, die het zelf kan zien', async () => {
    const { tab } = await openOverview(
      fakeHass({
        config: sampleConfig({
          devices: [
            dishwasher({ device_type: 'ev_charger', needs_ready_flag: false }),
          ],
        }),
      }),
    );

    assert.equal(isVisible(card(tab, 'Wat je nu kunt doen')), false);
  });
});

describe('wat er in de sectie staat', () => {
  it('noemt het apparaat en biedt de knop aan', async () => {
    const { tab } = await openOverview(
      fakeHass({ config: sampleConfig({ devices: [dishwasher()] }) }),
    );
    const section = card(tab, 'Wat je nu kunt doen');

    assert.match(visibleText(section), /Vaatwasser/);
    assert.match(visibleText(section), /Klaar \/ vol/);
  });

  it('zegt hoelang het geldt zodra de vlag staat', async () => {
    const { tab } = await openOverview(
      fakeHass({
        config: sampleConfig({ devices: [dishwasher()] }),
        coach: sampleCoach({ ready_devices: { d1: flag() } }),
      }),
    );
    const section = card(tab, 'Wat je nu kunt doen');

    assert.match(visibleText(section), /Staat vol\./);
    assert.match(visibleText(section), /We kunnen niet zien wanneer hij klaar is/);
    assert.match(visibleText(section), /Toch niet vol/);
  });

  it('stuurt het commando zonder revision', async () => {
    const hass = fakeHass({ config: sampleConfig({ devices: [dishwasher()] }) });
    const { tab } = await openOverview(hass);
    const button = [...card(tab, 'Wat je nu kunt doen').querySelectorAll('button')].find(
      (node) => node.textContent.includes('Klaar / vol'),
    );

    button.click();
    await settle();

    assert.deepEqual(
      hass.sent.find((m) => m.type.endsWith('devices/set_ready')),
      {
        type: 'domotiapp_energy/devices/set_ready',
        device_id: 'd1',
        ready: true,
      },
    );
  });
});
