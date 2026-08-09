/**
 * Route 1: the panel inside the real Home Assistant, driven with real clicks.
 *
 * This is the layer that renders `ha-form`, and it is the only one that can.
 * Everything else in this project — pytest, the jsdom suite, route 2 — is blind
 * to whether a control accepts a click, which is how a broken day selector once
 * shipped with a green suite.
 *
 * **Not part of CI, on purpose.** It needs a running Home Assistant, a token
 * and a configuration that changes while you work; wiring that into a workflow
 * would produce a check that fails for reasons that have nothing to do with the
 * commit. It is a deliberate run: `.\\scripts\\browsertest.ps1`.
 *
 * It writes to the instance it points at. Every row it creates carries the name
 * in `TEST_ROW_NAME` and is deleted again in the same file.
 */

import { defineConfig, devices } from '@playwright/test';

import { readEnvironment } from './live/session.mjs';

const environment = await readEnvironment();
const baseURL = environment.HA_URL ?? 'http://localhost:8123';

export default defineConfig({
  testDir: './live',
  testMatch: /\.spec\.mjs$/,
  // One worker: these tests write to a single shared Home Assistant, and two of
  // them saving at once would fight over the revision (SPEC.md §13).
  workers: 1,
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  timeout: 60_000,
  use: {
    baseURL,
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
    ...devices['Desktop Chrome'],
    // A phone-sized window, and it comes after the device preset so it wins:
    // this is the layer where the controls a thumb has to hit are the ones
    // being tested.
    viewport: { width: 393, height: 852 },
  },
});
