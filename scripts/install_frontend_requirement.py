"""Install the frontend package the installed Home Assistant expects.

``domotiapp_energy`` depends on ``panel_custom``, which depends on ``frontend``,
which imports ``hass_frontend`` during setup. Home Assistant declares that as a
component requirement rather than a package dependency, and the test harness
does not install component requirements — so without this step every test that
sets up the integration fails with ``No module named 'hass_frontend'``.

The version is read from the installed Home Assistant's own manifest instead of
being pinned here, so bumping pytest-homeassistant-custom-component keeps
working without a second version to maintain.

Run it after installing the development dependencies:

    python scripts/install_frontend_requirement.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import homeassistant


def main() -> int:
    """Install the pinned home-assistant-frontend release."""
    manifest = (
        Path(homeassistant.__file__).parent
        / "components"
        / "frontend"
        / "manifest.json"
    )
    requirements = json.loads(manifest.read_text(encoding="utf-8"))["requirements"]

    return subprocess.call([sys.executable, "-m", "pip", "install", *requirements])


if __name__ == "__main__":
    raise SystemExit(main())
