# Brand images

Drop the DomotiTech artwork in **this folder**. Home Assistant serves whatever is here at
`/api/brands/integration/domotiapp_energy/<file>` and it takes priority over the brands
CDN. No manifest entry, no configuration, nothing else to do.

| File | Size | Needed? |
|---|---|---|
| `icon.png` | 256×256, square | **yes** — this is the one shown everywhere |
| `icon@2x.png` | 512×512, square | recommended, for high-DPI screens |
| `logo.png` | landscape, shortest side 128–256 | optional; without it the icon is used |
| `logo@2x.png` | landscape, shortest side 256–512 | optional |
| `dark_icon.png`, `dark_logo.png` (+ `@2x`) | same sizes | only if the light version is unreadable on dark |

Requirements, from the Home Assistant brands specification:

- PNG only, losslessly compressed, interlaced preferred, transparency preferred.
- Trimmed: no empty border around the artwork.
- Optimised for a white background; a `dark_` variant covers the other case.
- **No Home Assistant branding** — a custom integration may not look official.

## Why this folder and not a pull request

Since Home Assistant 2026.3 a custom integration ships its own brand images this way, and
the [`home-assistant/brands`](https://github.com/home-assistant/brands) repository
**no longer accepts pull requests for custom integrations** — its pull request template
says so, and recent custom-integration submissions there are closed unmerged.

Verified on this project's test instance (HA 2026.7.4): with a file in this folder, the
API returned it byte for byte and the artwork appeared on the integration page.

**One caveat:** the HACS dashboard itself still reads its icons from `data-v2.hacs.xyz`
and shows a blank tile for integrations that only ship local brand images. That is an
open HACS bug ([hacs/integration#5171](https://github.com/hacs/integration/issues/5171))
with a fix proposed; nothing on our side changes it. Everywhere in Home Assistant proper —
the integrations page, the device page, the entity dialogs — the local file is used.

This folder is empty on purpose: no placeholder ships in production code.
