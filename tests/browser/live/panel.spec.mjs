/**
 * Route 1: the panel inside the running Home Assistant, with real clicks.
 *
 * # Why this file exists
 *
 * Every other layer in this project is blind to one thing: whether a control a
 * customer touches actually accepts the touch. `ha-form` ships with Home
 * Assistant, so jsdom stubs it and route 2 never loads it. The day selector
 * shipped broken through a green suite for exactly that reason — the rendering
 * depends on the option count and on the Home Assistant version, and no
 * automated check in this project could see which one it got.
 *
 * That is not a hypothetical. Writing this file found the **third** rendering
 * of the same field: on 2026.7 the seven-day multi-select is neither the
 * combobox nor the checkboxes that were seen before, but a set of
 * `ha-input-chip`s. Nothing in our code changed; Home Assistant's did. This is
 * the only layer that would ever notice.
 *
 * So the rule for this file: **only put a test here that needs a rendered Home
 * Assistant control.** Anything about layout, visibility or the cascade belongs
 * in route 2, where it runs on every push instead of when someone remembers.
 *
 * # It writes to the instance it points at
 *
 * There is no read-only version of "does saving work". Every row created here
 * carries `TEST_ROW_NAME` and is deleted again in `afterEach`; if a run dies
 * half way, that row is the thing to delete by hand on Apparaten.
 */

import { expect, test } from '@playwright/test';

import { readEnvironment, signIn } from './session.mjs';

/** Distinctive on purpose: a leftover row must be obvious in a device list. */
const TEST_ROW_NAME = 'PLAYWRIGHT TESTRIJ';

const PANEL_PATH = '/domotiapp-energy';

/** The panel element. Playwright's CSS engine pierces the shadow roots. */
const PANEL = 'domotiapp-energy-panel';

/** The dialog that is currently open; two are built and one is hidden. */
const OPEN_DIALOG = `${PANEL} .dialog:not(.is-hidden)`;

/** Match a button by its exact label, whitespace and icon aside. */
function exactly(label) {
  return new RegExp(`^\\s*${label}\\s*$`);
}

test.beforeEach(async ({ context, page }) => {
  const environment = await readEnvironment();
  if (!environment.HA_TOKEN) {
    throw new Error('HA_TOKEN is missing from .env');
  }
  await signIn(context, { url: environment.HA_URL, token: environment.HA_TOKEN });
  await page.goto(PANEL_PATH);
  await expect(page.locator(PANEL)).toBeVisible();
});

test('the panel loads inside Home Assistant and shows its six tabs', async ({
  page,
}) => {
  await expect(page.locator(`${PANEL} .tab-button`)).toHaveCount(6);
  // If this is empty the panel loaded and the data did not, which looks the
  // same from the outside and is the failure a customer reports as "leeg".
  await expect(page.locator(`${PANEL} .card-title`).first()).toBeVisible();
});

test('a real click on the day selector reaches the backend', async ({ page }) => {
  await page.locator(`${PANEL} .tab-button`, { hasText: 'Apparaten' }).click();
  await page
    .locator(`${PANEL} button`, { hasText: exactly('Apparaat toevoegen') })
    .click();

  const dialog = page.locator(OPEN_DIALOG);
  await expect(dialog).toBeVisible();

  // The first visible input is Naam: the first section is open on arrival and
  // Naam is its first field. Targeted by visibility rather than by tag on
  // purpose — Home Assistant 2026.7 renders a text selector as
  // ha-input/wa-input where earlier versions used ha-textfield, and pinning the
  // tag would make this test a report on their component names instead of on
  // our form. Getting the wrong field here fails two assertions down anyway.
  await dialog.locator('input:visible').first().fill(TEST_ROW_NAME);

  // A collapsed section renders its controls invisible, so the section is
  // opened first — the same tap a customer makes.
  await dialog
    .locator('button', { hasText: exactly('Wanneer het mag draaien') })
    .click();

  // The click that no other layer can make. A synthetic `value-changed` would
  // prove the handler and say nothing about the control.
  // Substring, not an anchored pattern: the chip carries a check icon beside
  // its label, so its text is not exactly the day name.
  const monday = dialog.locator('ha-input-chip', { hasText: 'Maandag' });
  await expect(monday).toBeVisible();
  await monday.click();

  await dialog.locator('button', { hasText: exactly('Opslaan') }).click();
  await expect(dialog).toBeHidden();

  await expect(
    page.locator(`${PANEL} .row-item`, { hasText: TEST_ROW_NAME }).first(),
  ).toBeVisible();

  // A reload is what separates "the panel drew it" from "the backend kept it":
  // everything on screen after this came back out of storage.
  await page.reload();
  await page.locator(`${PANEL} .tab-button`, { hasText: 'Apparaten' }).click();
  await page
    .locator(`${PANEL} .row-item`, { hasText: TEST_ROW_NAME })
    .first()
    .locator('button', { hasText: exactly('Bewerken') })
    .click();

  const reopened = page.locator(OPEN_DIALOG);
  await reopened
    .locator('button', { hasText: exactly('Wanneer het mag draaien') })
    .click();
  await expect(
    reopened.locator('ha-input-chip[selected]', { hasText: 'Maandag' }),
  ).toBeVisible();
});

test.afterEach(async ({ page }) => {
  // Cleanup runs even when the test above failed part way, because a leftover
  // row changes what the next run sees.
  //
  // The wait matters and was missing at first: `count()` does not wait, so a
  // freshly loaded tab reported zero rows, the loop never ran, and the first
  // run left its device behind in Sven's configuration. Auto-waiting for the
  // row to be visible — and treating the timeout as "there is none" — is what
  // makes this reliable.
  await page.goto(PANEL_PATH);
  // Wait for the panel itself before asking anything about its contents. The
  // same non-waiting mistake, one level up: `count()` on a page that is still
  // loading answers zero, and the cleanup returned as if there were nothing to
  // clean. Two runs' worth of rows were left behind before this line existed.
  await expect(page.locator(PANEL)).toBeVisible();
  await page.locator(`${PANEL} .tab-button`, { hasText: 'Apparaten' }).click();

  const row = page.locator(`${PANEL} .row-item`, { hasText: TEST_ROW_NAME });
  try {
    await expect(row.first()).toBeVisible({ timeout: 5000 });
  } catch {
    return;
  }

  // Count down rather than "loop until none left". Deleting re-renders the
  // list, and for a moment it is empty — a `toHaveCount(0)` catches that
  // instant and passes while a second row is on its way back in. Asserting the
  // count went down by exactly one is the same check without the race, and it
  // is why a second leftover row survived the first version of this cleanup.
  let remaining = await row.count();
  while (remaining > 0) {
    await row
      .first()
      .locator('button', { hasText: exactly('Verwijderen') })
      .click();
    await page
      .locator(`${OPEN_DIALOG} .dialog-actions button`, {
        hasText: exactly('Verwijderen'),
      })
      .click();
    remaining -= 1;
    await expect(row).toHaveCount(remaining, { timeout: 10_000 });
  }
});
