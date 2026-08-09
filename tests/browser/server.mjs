/**
 * A static file server for the browser tests, rooted at the repository.
 *
 * The panel is native ES modules, so a relative `import` has to resolve over
 * http — `file://` fails on module resolution in Chromium and would make the
 * harness test something other than what ships. Serving the repository root
 * rather than a copied build directory is deliberate: the tests then load the
 * exact bytes in `custom_components/`, with no step in between that could go
 * stale (CLAUDE.md rule 5: no build step).
 *
 * Standard library only. This is test tooling and adds nothing to the
 * integration.
 */

import { createReadStream } from 'node:fs';
import { stat } from 'node:fs/promises';
import { createServer } from 'node:http';
import { extname, join, normalize, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(fileURLToPath(new URL('../..', import.meta.url)));
const PORT = Number(process.env.DOMOTIAPP_TEST_PORT ?? 4173);

const CONTENT_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
};

/**
 * Resolve a request path inside the root, or null when it escapes.
 *
 * `..` in a URL is the one way a static server hands out a file it was never
 * meant to. This is a test server on localhost, but a check that costs two
 * lines is cheaper than remembering that it does not matter here.
 */
function resolveWithinRoot(urlPath) {
  const decoded = decodeURIComponent(urlPath.split('?')[0]);
  const target = resolve(join(ROOT, normalize(decoded)));
  if (target !== ROOT && !target.startsWith(ROOT + sep)) {
    return null;
  }
  return target;
}

const server = createServer(async (request, response) => {
  const target = resolveWithinRoot(request.url ?? '/');
  if (!target) {
    response.writeHead(403).end('Outside the repository');
    return;
  }

  try {
    const info = await stat(target);
    const file = info.isDirectory() ? join(target, 'index.html') : target;
    await stat(file);
    response.writeHead(200, {
      'content-type': CONTENT_TYPES[extname(file)] ?? 'application/octet-stream',
      // Nothing may be cached: a test run that reads yesterday's module is the
      // failure mode this whole layer exists to prevent.
      'cache-control': 'no-store',
    });
    createReadStream(file).pipe(response);
  } catch {
    response.writeHead(404).end(`Not found: ${request.url}`);
  }
});

server.listen(PORT, '127.0.0.1', () => {
  process.stdout.write(`harness server on http://127.0.0.1:${PORT}\n`);
});
