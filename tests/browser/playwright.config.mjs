/**
 * Route 2: the panel in a real browser, with a stubbed Home Assistant.
 *
 * This config is the one CI runs on every push. It answers the questions jsdom
 * cannot: the cascade, container queries, viewport widths and the geometry the
 * safe-area insets produce. It deliberately does **not** need Home Assistant —
 * no token, no container, no network — because a check that only runs when a
 * container happens to be up is a check that stops running.
 *
 * What it cannot prove is written down in `tests/browser/layout.spec.mjs` and
 * in CLAUDE.md, and it is not a detail: no Home Assistant component renders
 * here. Route 1 (`tests/browser/live.config.mjs`) is where those are touched.
 */

import { fileURLToPath } from 'node:url';

import { defineConfig, devices } from '@playwright/test';

const PORT = Number(process.env.DOMOTIAPP_TEST_PORT ?? 4173);

// Playwright starts webServer from the config's directory, not the repository
// root, so the server is given the root explicitly. Otherwise the command works
// when run by hand and fails only under the runner.
const REPO_ROOT = fileURLToPath(new URL('../..', import.meta.url));

export default defineConfig({
  testDir: '.',
  testMatch: /layout\.spec\.mjs$/,
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'node tests/browser/server.mjs',
    cwd: REPO_ROOT,
    url: `http://127.0.0.1:${PORT}/tests/browser/harness/index.html`,
    reuseExistingServer: !process.env.CI,
    stdout: 'ignore',
    stderr: 'pipe',
  },
});
