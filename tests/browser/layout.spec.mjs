/**
 * Route 2: layout, the cascade, container queries and safe areas — in a real
 * browser, with a stubbed Home Assistant.
 *
 * # What this file can prove, and what it cannot
 *
 * **Read this before trusting a green run.** The jsdom layer already went wrong
 * once by testing a shape instead of an outcome, and a browser makes the same
 * mistake easier to believe: the page is real, so the results feel complete.
 *
 * It is real for everything the panel draws itself:
 *
 * - the cascade — `.is-hidden` really computing `display: none`, which jsdom
 *   cannot settle because it implements CSS only in part;
 * - container queries, which need layout to exist at all;
 * - viewport widths, wrapping, and horizontal overflow;
 * - the geometry the safe-area insets produce, faked through the custom
 *   properties the panel reads them from.
 *
 * **It proves nothing about any Home Assistant component.** `ha-form`,
 * `ha-textfield`, `ha-select`, `ha-icon` and friends are not loaded here — they
 * ship with Home Assistant, not with us, and pulling them in would mean a CDN
 * or a build step (CLAUDE.md rule 5). In this page they are unknown elements:
 * the browser keeps them in the tree, gives them no shadow root and no
 * behaviour. So:
 *
 * > **A green run here says nothing about whether a control accepts a click.**
 *
 * That is the exact gap the day selector fell through — seven options rendered
 * as a combobox and worked, four rendered as checkboxes and did not, and every
 * automated layer was blind to the difference because none of them rendered a
 * control. Route 1 (`scripts/browsertest.ps1`) exists for that, and only it can
 * close it.
 *
 * Practical consequence: **never widen a test here to "check the form works".**
 * If a question needs a rendered control, it belongs in route 1.
 */

import { expect, test } from '@playwright/test';

const HARNESS = '/tests/browser/harness/index.html';

/** Widths a customer actually holds, plus the two that bracket the rules. */
const VIEWPORTS = [
  { name: 'small phone', width: 320, height: 640 },
  { name: 'iPhone SE', width: 375, height: 667 },
  { name: 'iPhone 15', width: 393, height: 852 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 800 },
];

/** The insets of a notched phone, portrait: status bar and home indicator. */
const NOTCHED_PORTRAIT = { top: 47, right: 0, bottom: 34, left: 0 };

/** The insets of a notched phone, landscape: the cut-out eats one side. */
const NOTCHED_LANDSCAPE = { top: 0, right: 44, bottom: 21, left: 44 };

test.beforeEach(async ({ page }) => {
  await page.goto(HARNESS);
  await page.waitForFunction(() => window.harnessReady === true);
});

test.describe('nothing scrolls sideways', () => {
  for (const viewport of VIEWPORTS) {
    test(`at ${viewport.name} (${viewport.width}px)`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.evaluate(() => window.harness.remount());

      const overflow = await page.evaluate(() => ({
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
      }));

      // A page that scrolls sideways on a phone is the fault a customer
      // notices first and reports last, because it looks like his own thumb.
      expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth);
    });
  }
});

test.describe('the tab bar', () => {
  test('fits on two lines at the width the rule was tuned for', async ({ page }) => {
    // 360px, not 320. SPEC.md §39 tuned the tightening against 358px, and at
    // 320 the six buttons still take three lines — measured, not assumed. That
    // is a real limit and it is reported as one rather than absorbed by a
    // looser bound here: a test that quietly widens its tolerance to stay green
    // stops describing what was designed.
    await page.setViewportSize({ width: 360, height: 640 });
    await page.evaluate(() => window.harness.remount());

    const lines = await page.evaluate(() => {
      const tops = window.harness
        .findAll('.tab-button')
        .map((button) => Math.round(button.getBoundingClientRect().top));
      return new Set(tops).size;
    });

    // Six tabs wrapped onto three lines at 358px before 0.9.0, which is a third
    // of the screen spent before anything is read (SPEC.md §39).
    expect(lines).toBeLessThanOrEqual(2);
  });

  test('is a single line on a desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.evaluate(() => window.harness.remount());

    const lines = await page.evaluate(() => {
      const tops = window.harness
        .findAll('.tab-button')
        .map((button) => Math.round(button.getBoundingClientRect().top));
      return new Set(tops).size;
    });

    expect(lines).toBe(1);
  });

  test('keeps every button at a 44px touch target', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.evaluate(() => window.harness.remount());

    const heights = await page.evaluate(() =>
      window.harness
        .findAll('.tab-button')
        .map((button) => button.getBoundingClientRect().height),
    );

    expect(heights.length).toBe(6);
    // The tightening takes air, never the target: a thumb in a meter cupboard
    // is the worst input device this panel gets (SPEC.md §11).
    for (const height of heights) {
      expect(height).toBeGreaterThanOrEqual(44);
    }
  });
});

test.describe('the narrow rules follow the panel, not the screen', () => {
  /**
   * The situation: a tablet in landscape with the Home Assistant sidebar open.
   * The viewport is roomy, the panel is not. A media query would read the
   * screen and leave the tab bar in its desktop spacing inside a 500px column;
   * a container query reads the panel and tightens.
   *
   * This is the test that tells the two apart, and it is why the rule is a
   * container query at all (SPEC.md §39).
   */
  test('a wide window with a narrow panel gets the compact spacing', async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.evaluate(() => {
      window.harness.panel.style.width = '500px';
      window.harness.panel.style.display = 'block';
    });

    const columnGap = await page.evaluate(
      () => getComputedStyle(window.harness.find('.tabs')).columnGap,
    );

    expect(columnGap).toBe('10px');
  });

  test('the same window at full width keeps the roomy spacing', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.evaluate(() => {
      window.harness.panel.style.width = '';
    });

    const columnGap = await page.evaluate(
      () => getComputedStyle(window.harness.find('.tabs')).columnGap,
    );

    expect(columnGap).toBe('24px');
  });
});

test.describe('hiding is the panel own contract', () => {
  /**
   * jsdom can see the class but not what it does; a browser can see both. This
   * is the assertion phase 7a needed and could not make: three visibility bugs
   * shipped while every check passed, because none of them ever asked a real
   * cascade what `display` came out.
   */
  test('is-hidden really computes to display none', async ({ page }) => {
    const displays = await page.evaluate(() =>
      window.harness
        .findAll('.tab-host > *')
        .map((node) => [
          node.classList.contains('is-hidden'),
          getComputedStyle(node).display,
        ]),
    );

    const visible = displays.filter(([hidden]) => !hidden);
    expect(visible.length).toBe(1);
    for (const [hidden, display] of displays) {
      if (hidden) {
        expect(display).toBe('none');
      } else {
        expect(display).not.toBe('none');
      }
    }
  });

  test('exactly one tab panel is on screen after switching tabs', async ({ page }) => {
    await page.evaluate(() => {
      const button = window.harness
        .findAll('.tab-button')
        .find((node) => node.textContent.includes('Apparaten'));
      button.click();
    });
    await page.evaluate(() => window.harness.settle());

    const onScreen = await page.evaluate(
      () =>
        window.harness
          .findAll('.tab-host > *')
          .filter((node) => getComputedStyle(node).display !== 'none').length,
    );

    expect(onScreen).toBe(1);
  });
});

test.describe('the safe areas, faked', () => {
  /**
   * The situation this reproduces: 0.8.0 on Sven's iPhone. The full-height
   * dialog opened with its title behind the clock and its close button behind
   * the battery icon — and a full-screen sheet has no scrim left to tap and no
   * Escape key on a phone, so it was a trap rather than a cosmetic fault
   * (SPEC.md §40).
   *
   * `env()` cannot be written from script, so this fakes the *inputs* the panel
   * reads them through, and every rule under test is the rule that ships.
   */
  async function openDialogOnDevices(page) {
    await page.evaluate(() => {
      const button = window.harness
        .findAll('.tab-button')
        .find((node) => node.textContent.includes('Apparaten'));
      button.click();
    });
    await page.evaluate(() => window.harness.settle());
    await page.evaluate(() => {
      const add = window.harness
        .findAll('button')
        .find((node) => node.textContent.trim() === 'Apparaat toevoegen');
      add.click();
    });
    await page.evaluate(() => window.harness.settle());
  }

  test('the sheet stays inside the screen in portrait', async ({ page }) => {
    await page.setViewportSize({ width: 393, height: 852 });
    await page.evaluate(() => window.harness.remount());
    await page.evaluate((insets) => window.harness.setInsets(insets), NOTCHED_PORTRAIT);
    await openDialogOnDevices(page);

    const box = await page.evaluate(() => {
      const surface = window.harness.find('.dialog-surface');
      const rect = surface.getBoundingClientRect();
      return { top: rect.top, bottom: rect.bottom, height: rect.height };
    });

    // The box-sizing bug made the sheet exactly as much taller than the screen
    // as the insets were deep — 81px on this phone — so both ends fell off it.
    expect(box.height).toBeLessThanOrEqual(852);
    expect(box.bottom).toBeLessThanOrEqual(852 + 0.5);
  });

  test('the close button is reachable under the status bar', async ({ page }) => {
    await page.setViewportSize({ width: 393, height: 852 });
    await page.evaluate(() => window.harness.remount());
    await page.evaluate((insets) => window.harness.setInsets(insets), NOTCHED_PORTRAIT);
    await openDialogOnDevices(page);

    const close = await page.evaluate(() => {
      const rect = window.harness.find('.dialog-close').getBoundingClientRect();
      return { top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right };
    });

    // Below the status bar, above the home indicator, inside both edges. This
    // is the only way out of a full-screen sheet on a phone.
    expect(close.top).toBeGreaterThanOrEqual(NOTCHED_PORTRAIT.top);
    expect(close.bottom).toBeLessThanOrEqual(852 - NOTCHED_PORTRAIT.bottom);
    expect(close.left).toBeGreaterThanOrEqual(0);
    expect(close.right).toBeLessThanOrEqual(393);
  });

  test('the cut-out in landscape does not cover the sheet either', async ({ page }) => {
    await page.setViewportSize({ width: 852, height: 393 });
    await page.evaluate(() => window.harness.remount());
    await page.evaluate((insets) => window.harness.setInsets(insets), NOTCHED_LANDSCAPE);
    await openDialogOnDevices(page);

    const box = await page.evaluate(() => {
      const rect = window.harness.find('.dialog-header').getBoundingClientRect();
      return { left: rect.left, right: rect.right };
    });

    // Landscape is the orientation the four-sided fix was actually for: until
    // 0.8.1 only the bottom inset existed, so a rotated phone put the header
    // under the cut-out.
    expect(box.left).toBeGreaterThanOrEqual(NOTCHED_LANDSCAPE.left);
    expect(box.right).toBeLessThanOrEqual(852 - NOTCHED_LANDSCAPE.right);
  });

  test('a screen without insets loses nothing to them', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.evaluate(() => window.harness.remount());
    await openDialogOnDevices(page);

    const padding = await page.evaluate(() => {
      const style = getComputedStyle(window.harness.find('.dialog-surface'));
      return [
        style.paddingTop,
        style.paddingRight,
        style.paddingBottom,
        style.paddingLeft,
      ];
    });

    // The insets live outside the media query on purpose, so they are always
    // on. That is only safe if they cost nothing where there is no notch.
    expect(padding).toEqual(['0px', '0px', '0px', '0px']);
  });
});

test.describe('both roles get the same bar', () => {
  /**
   * A resident sees six tabs, not four: what he does not own is greyed out
   * where he can read it, because hiding it left him unable to see that his
   * main fuse was wrong (SPEC.md §33.6). So the narrow-width guarantee has to
   * hold for the same six buttons in both roles — there is no lighter bar to
   * fall back on.
   *
   * Written the other way round first, and the browser corrected it.
   */
  test('a resident gets six tabs on a phone, on two lines', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.evaluate(() => window.harness.remount({ isAdmin: false }));

    const labels = await page.evaluate(() =>
      window.harness.findAll('.tab-button').map((node) => node.textContent.trim()),
    );
    const lines = await page.evaluate(() => {
      const tops = window.harness
        .findAll('.tab-button')
        .map((button) => Math.round(button.getBoundingClientRect().top));
      return new Set(tops).size;
    });

    expect(labels.length).toBe(6);
    expect(lines).toBeLessThanOrEqual(2);
  });
});

test.describe('de dagkop in het logboek', () => {
  /**
   * **Precies wat jsdom niet kan zien** (SPEC.md §61.4). De kop staat binnen de
   * rij van zijn dag, en `.row-item` is een flexrij — zonder `flex-basis: 100%`
   * komt hij naast de gebeurtenis te staan in plaats van erboven. De DOM is in
   * beide gevallen identiek, dus alleen een echte cascade beslist dit.
   *
   * Zo is het ook één keer opgeleverd, en pas in de browser gezien.
   */
  test('staat boven de gebeurtenis en niet ernaast', async ({ page }) => {
    const geometrie = await page.evaluate(async () => {
      const nu = new Date();
      nu.setHours(14, 32, 0, 0);
      await window.harness.remount({
        logs: [
          {
            id: 'a',
            timestamp: nu.toISOString(),
            event_type: 'source_unavailable',
            title: 'Bron niet beschikbaar',
            message: 'De netmeter kon niet worden gelezen.',
            severity: 'warning',
            count: 1,
          },
        ],
      });
      const knop = window.harness
        .findAll('.tab-button')
        .find((node) => node.textContent.includes('Logboek'));
      knop.click();
      await window.harness.settle();
      await new Promise((resolve) => setTimeout(resolve, 50));

      const kop = window.harness.find('.day-heading');
      const inhoud = window.harness.find('.row-item .row-main');
      if (!kop || !inhoud) {
        return null;
      }
      const k = kop.getBoundingClientRect();
      const i = inhoud.getBoundingClientRect();
      return { kopOnder: k.bottom, inhoudBoven: i.top, kopBreedte: k.width, rij: window.harness.find('.row-item').getBoundingClientRect().width };
    });

    expect(geometrie).not.toBeNull();
    // Boven, niet ernaast: de onderkant van de kop ligt op of boven de
    // bovenkant van de gebeurtenis.
    expect(geometrie.kopOnder).toBeLessThanOrEqual(geometrie.inhoudBoven + 1);
    // En hij beslaat de hele rij, want dat is wat hem de regel laat breken.
    expect(geometrie.kopBreedte).toBeGreaterThan(geometrie.rij * 0.9);
  });
});
