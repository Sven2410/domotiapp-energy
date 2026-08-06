"""Registering the side panel and the files it loads (SPEC.md §7).

Two registrations with very different lifetimes, which is why they are guarded
differently:

* the **static path** serves ``frontend/`` and cannot be unregistered — Home
  Assistant has no API for it. It is therefore registered once per process and
  guarded by a module-level flag;
* the **panel** is removed again on unload, so a reload of the integration does
  not leave a dead sidebar item behind.

Caching is handled twice over, because one of the two turned out not to be
enough. ``cache_headers=False`` keeps Home Assistant from putting a year-long
``Cache-Control`` on these files, so the browser revalidates. That is not the
whole story: Home Assistant's **service worker** caches by exact URL and answers
from ``cache-storage`` without asking us at all. It was observed serving the
previous release's tab modules to a browser that had just loaded the new entry
point. The version therefore also sits in the URL path (see
``const.FRONTEND_URL_BASE``), so an upgrade changes the URL of every file rather
than only of the entry point.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import (
    FRONTEND_DIR_NAME,
    FRONTEND_URL_BASE,
    PANEL_COMPONENT_NAME,
    PANEL_ICON,
    PANEL_MODULE_URL,
    PANEL_TITLE,
    PANEL_URL_PATH,
)

_LOGGER = logging.getLogger(__name__)

# Static paths live for the lifetime of the process and cannot be removed, so
# registering one twice is an error. This is registration state, not
# configuration; there is nothing here to configure.
_static_path_registered = False


async def async_register_panel(hass: HomeAssistant) -> None:
    """Serve the frontend and put DomotiApp Energy in the sidebar."""
    await _async_register_static_path(hass)

    if PANEL_URL_PATH in hass.data.get(frontend.DATA_PANELS, {}):
        # A reload that did not get as far as async_unload_entry, or a second
        # entry that should not exist. Either way, re-registering would raise.
        _LOGGER.debug("Panel %s is already registered", PANEL_URL_PATH)
        return

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT_NAME,
        sidebar_title=PANEL_TITLE,
        sidebar_icon=PANEL_ICON,
        module_url=PANEL_MODULE_URL,
        embed_iframe=False,
        # Non-admins get the read-only tabs; the panel hides the configuration
        # tabs for them and the WebSocket API refuses their writes regardless
        # (SPEC.md §7 and §14).
        require_admin=False,
    )


async def _async_register_static_path(hass: HomeAssistant) -> None:
    """Serve the frontend directory, once per process."""
    global _static_path_registered  # noqa: PLW0603 - process-wide registration
    if _static_path_registered:
        return

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                FRONTEND_URL_BASE,
                str(Path(__file__).parent / FRONTEND_DIR_NAME),
                # See the module docstring: the ES-module imports inside the
                # entry point carry no cache-busting query of their own.
                cache_headers=False,
            )
        ]
    )
    _static_path_registered = True


def async_remove_panel(hass: HomeAssistant) -> None:
    """Take the sidebar item down again.

    The static path stays: Home Assistant cannot unregister one, and serving a
    few files for an integration that is not loaded harms nothing.
    """
    if PANEL_URL_PATH in hass.data.get(frontend.DATA_PANELS, {}):
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
