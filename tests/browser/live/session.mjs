/**
 * Signing in to the running Home Assistant, without typing a password.
 *
 * The frontend keeps its session in `localStorage.hassTokens`. Writing a
 * long-lived access token there before the first load is how a browser test
 * arrives logged in — there is no login form to drive and no password anywhere
 * in this repository.
 *
 * The token comes from `.env` in the repository root, which is in `.gitignore`
 * and never committed. Same file, same variables as `scripts/ha_check.py`.
 *
 * Note for CLAUDE.md rule 6: the panel may not use browser storage, and does
 * not. This writes Home Assistant's own key, from the test harness, to stand in
 * for a login that already happened.
 */

import { readFile } from 'node:fs/promises';

const ENV_PATH = new URL('../../../.env', import.meta.url);

/** Read `.env` into a plain object. Missing file is an error worth reading. */
export async function readEnvironment() {
  let text;
  try {
    text = await readFile(ENV_PATH, 'utf8');
  } catch {
    throw new Error(
      'No .env in the repository root. Route 1 talks to the running Home ' +
        'Assistant and needs HA_URL and HA_TOKEN, the same two that ' +
        'scripts/ha_check.py reads.',
    );
  }

  const values = {};
  for (const line of text.split(/\r?\n/)) {
    const match = /^\s*([A-Z0-9_]+)\s*=\s*(.*)$/.exec(line);
    if (match) {
      values[match[1]] = match[2].trim().replace(/^["']|["']$/g, '');
    }
  }
  return values;
}

/**
 * Hand a browser context a Home Assistant session.
 *
 * `expires` is set a year out. A long-lived token really does last that long,
 * and a value in the past makes the frontend bounce straight to the login page
 * with no error that says why.
 */
export async function signIn(context, { url, token }) {
  const origin = new URL(url).origin;
  await context.addInitScript(
    ([hassUrl, accessToken]) => {
      window.localStorage.setItem(
        'hassTokens',
        JSON.stringify({
          access_token: accessToken,
          token_type: 'Bearer',
          expires_in: 31536000,
          hassUrl,
          clientId: null,
          expires: Date.now() + 31536000000,
        }),
      );
    },
    [origin, token],
  );
}
