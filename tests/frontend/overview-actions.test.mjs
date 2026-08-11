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

describe('hoe het gisteren ging', () => {
  function historyCard(tab) {
    return card(tab, 'Hoe het gisteren ging');
  }

  it('zwijgt met één zin zolang er geen dag geweest is', async () => {
    // Een woning die vannacht is opgeleverd hoort geen drie lege regels te
    // zien: dat is geen storing maar een dag die nog niet bestond (§61.2).
    const { tab } = await openOverview();

    assert.match(visibleText(historyCard(tab)), /nog geen geschiedenis van gisteren/);
    assert.doesNotMatch(visibleText(historyCard(tab)), /Zonneoverschot/);
  });

  it('zet de drie feiten neer zodra er een dag is', async () => {
    const { tab } = await openOverview(
      fakeHass({
        history: {
          date: '2026-08-10',
          surplus_hours: 4,
          peak_grid_power_w: 4600,
          peak_grid_load_percent: 80,
          complete_all_day: true,
          has_data: true,
        },
      }),
    );
    const tekst = visibleText(historyCard(tab));

    assert.match(tekst, /ongeveer 4 uur/);
    assert.match(tekst, /4\.600 W/);
    assert.match(tekst, /80% van je maximum/);
    assert.match(tekst, /De hele dag compleet/);
  });

  it('zegt per feit over hoeveel uur het iets weet', async () => {
    // **Per feit en niet per dag.** Gisteren had de datakwaliteit vierentwintig
    // uur en de netmeting zeven: de dag was compleet vastgelegd terwijl het
    // hoogste netvermogen op zeven uur rustte.
    const { tab } = await openOverview(
      fakeHass({
        history: {
          surplus_hours: 6,
          surplus_hours_known: 7,
          peak_grid_power_w: 800,
          peak_grid_load_percent: 14,
          peak_hours_known: 7,
          complete_all_day: false,
          quality_hours_known: 24,
          has_data: true,
        },
      }),
    );
    const tekst = visibleText(historyCard(tab));

    assert.match(tekst, /Gemeten over 7 van de 24 uur/);
    // De datakwaliteit kende de dag wél helemaal, dus die rij zwijgt erover.
    assert.equal(tekst.match(/Gemeten over/g).length, 2);
  });

  it('zwijgt over de uren zodra een feit de hele dag kent', async () => {
    const { tab } = await openOverview(
      fakeHass({
        history: {
          surplus_hours: 6,
          surplus_hours_known: 24,
          peak_grid_power_w: 800,
          peak_hours_known: 24,
          complete_all_day: true,
          quality_hours_known: 24,
          has_data: true,
        },
      }),
    );

    assert.doesNotMatch(visibleText(historyCard(tab)), /Gemeten over/);
  });

  it('zegt "ongeveer", want een uurgemiddelde is grof', async () => {
    // Precisie suggereren die er niet is, is erger dan afronden: een uur met
    // een half uur dubbel overschot en een half uur niets telt hier mee.
    const { tab } = await openOverview(
      fakeHass({ history: { surplus_hours: 6, has_data: true } }),
    );

    assert.match(visibleText(historyCard(tab)), /ongeveer 6 uur/);
  });

  it('meldt geen piek op een dag waarop de woning alleen terugleverde', async () => {
    const { tab } = await openOverview(
      fakeHass({
        history: { surplus_hours: 7, peak_grid_power_w: null, has_data: true },
      }),
    );

    assert.match(visibleText(historyCard(tab)), /Geen afname gemeten/);
  });

  it('toont de dertig dagen als maximum met een telling erbij', async () => {
    // **De vraag van de installateur** (§61.7): bij een gesprongen zekering wil
    // hij weten of de woning er structureel tegenaan zit of dat het één keer
    // gebeurde. Een maximum alleen zegt dat niet.
    const { tab } = await openOverview(
      fakeHass({
        history: {
          peak_month_w: 5100,
          peak_month_percent: 88.7,
          days_over_warning: 2,
          days_known: 30,
          has_data: true,
        },
      }),
    );
    const tekst = visibleText(historyCard(tab));

    assert.match(tekst, /Hoogste in 30 dagen/);
    assert.match(tekst, /5\.100 W/);
    // Het percentage hoort erbij: 89% zegt in één blik meer dan 5.100 W, en het
    // is het getal waarmee een installateur uitlegt of een aansluiting te krap
    // is. Het werd berekend en nergens gelezen tot de browsercontrole erop viel.
    assert.match(tekst, /89% van je maximum/);
    assert.match(tekst, /Op 2 van de 30 gemeten dagen boven je waarschuwingsgrens/);
  });

  it('wijst naar het Energie-dashboard voor "hoeveel"', async () => {
    // Zonder deze regel zoekt een klant kWh en kosten hier, en concludeert hij
    // dat het ontbreekt (§61.1). Ook op de eerste dag, dus zonder geschiedenis.
    //
    // Of het een link is hangt sinds §62 af van wat de installateur invulde;
    // de zin staat er hoe dan ook.
    const { tab } = await openOverview();

    assert.match(visibleText(historyCard(tab)), /Energie-dashboard van Home Assistant/);
  });

  it('belooft nergens wat het opgeleverd heeft', async () => {
    // **De grens van dit blok** (§61.1). De coach adviseert; of het advies is
    // opgevolgd weet niemand, dus een euro of een besparing hoort hier niet.
    const { tab } = await openOverview(
      fakeHass({
        history: {
          surplus_hours: 4,
          peak_grid_power_w: 4600,
          peak_grid_load_percent: 80,
          complete_all_day: true,
          has_data: true,
        },
      }),
    );
    const tekst = visibleText(historyCard(tab));

    assert.doesNotMatch(tekst, /bespaar|opgeleverd|€/i);
  });
});

describe('navigatie uit het paneel (SPEC.md §62)', () => {
  function huis(overrides = {}) {
    return sampleConfig({
      home: { ...sampleConfig().home, ...overrides },
    });
  }

  it('maakt er een link van zodra de installateur een adres invulde', async () => {
    const { tab } = await openOverview(
      fakeHass({ config: huis({ energy_dashboard_path: '/energie-thuis' }) }),
    );
    const kaart = card(tab, 'Hoe het gisteren ging');

    assert.equal(kaart.querySelector('a')?.getAttribute('href'), '/energie-thuis');
    assert.match(visibleText(kaart), /het Energie-dashboard van Home Assistant/);
  });

  it('houdt de zin en laat de link weg als er niets is ingevuld', async () => {
    // **De zin bestaat om te zeggen wáár het antwoord woont** (§62.4), niet om
    // te navigeren. Zonder adres zou een link naar een leeg dashboard kunnen
    // sturen, of een bewoner op een wandtablet achterlaten waar hij vastzit.
    const { tab } = await openOverview();
    const kaart = card(tab, 'Hoe het gisteren ging');

    assert.match(visibleText(kaart), /het Energie-dashboard van Home Assistant/);
    assert.equal(
      [...kaart.querySelectorAll('a')].filter((a) => isVisible(a)).length,
      0,
    );
  });
});
