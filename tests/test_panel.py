"""Tests for the side panel registration (SPEC.md §7).

Not in the file list of SPEC.md §4, which predates ``panel.py`` having its own
behaviour worth pinning: the panel has to appear, has to carry the cache-busting
module URL, has to be open to non-admins, and has to disappear again on unload
so a reload does not leave a dead sidebar item behind.
"""

import json
import re
from pathlib import Path
from typing import Any

from homeassistant.components import frontend
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.domotiapp_energy.const import (
    COMPLETENESS_POINTS,
    CONF_HOME_NAME,
    CONF_MANUAL_SETUP_ACKNOWLEDGED,
    CONFIDENCE_LEVELS,
    DEFAULT_HOME_NAME,
    DOMAIN,
    FRONTEND_DIR_NAME,
    FRONTEND_URL_BASE,
    FRONTEND_URL_ROOT,
    PANEL_COMPONENT_NAME,
    PANEL_ICON,
    PANEL_MODULE_URL,
    PANEL_TITLE,
    PANEL_URL_PATH,
    VERSION,
)
from custom_components.domotiapp_energy.engine.providers import (
    _CONFIDENCE_LABELS,
    _ITEM_LABELS,
)
from custom_components.domotiapp_energy.engine.reason_codes import REASON_CODES
from custom_components.domotiapp_energy.panel import async_register_panel


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration with an empty configuration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_HOME_NAME,
        data={
            CONF_HOME_NAME: DEFAULT_HOME_NAME,
            CONF_MANUAL_SETUP_ACKNOWLEDGED: True,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _panels(hass: HomeAssistant) -> dict[str, Any]:
    """Return the registered panels."""
    return hass.data.get(frontend.DATA_PANELS, {})


async def test_the_panel_appears_in_the_sidebar(hass: HomeAssistant) -> None:
    """Setting up the integration registers the panel (SPEC.md §7)."""
    await _setup(hass)

    panel = _panels(hass).get(PANEL_URL_PATH)

    assert panel is not None
    assert panel.sidebar_title == PANEL_TITLE
    assert panel.sidebar_icon == PANEL_ICON
    # Non-admins get the read-only tabs; the panel hides the configuration tabs
    # for them and the WebSocket API refuses their writes anyway.
    assert panel.require_admin is False


async def test_the_module_url_carries_the_version(hass: HomeAssistant) -> None:
    """The ?v= query string is what busts an aggressively cached panel."""
    await _setup(hass)

    config = _panels(hass)[PANEL_URL_PATH].config["_panel_custom"]

    assert config["name"] == PANEL_COMPONENT_NAME
    assert config["module_url"] == PANEL_MODULE_URL
    assert config["module_url"].endswith(f"?v={VERSION}")
    assert config["embed_iframe"] is False


async def test_every_frontend_url_carries_the_version(hass: HomeAssistant) -> None:
    """The version is in the path, so an upgrade busts *every* module.

    ``?v=`` only busts the entry point: a relative import inside it does not
    inherit the query string. Home Assistant's service worker caches by exact
    URL and was observed serving the previous release's tab modules to a browser
    that had just loaded the new entry point — half old, half new, and not
    reproducible for whoever reported it.
    """
    await _setup(hass)

    assert f"{FRONTEND_URL_ROOT}/{VERSION}" == FRONTEND_URL_BASE
    # Every module resolves under this base, because a relative import keeps the
    # directory it was loaded from. So one versioned base moves all of them,
    # without naming the version in fifteen import statements.
    assert PANEL_MODULE_URL.startswith(f"{FRONTEND_URL_BASE}/")
    assert VERSION in FRONTEND_URL_BASE


async def test_unloading_removes_the_panel(hass: HomeAssistant) -> None:
    """An unloaded integration leaves no sidebar item that cannot answer."""
    entry = await _setup(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert PANEL_URL_PATH not in _panels(hass)


async def test_reloading_does_not_register_the_panel_twice(
    hass: HomeAssistant,
) -> None:
    """A reload re-registers cleanly; registering twice would raise."""
    entry = await _setup(hass)

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert PANEL_URL_PATH in _panels(hass)


async def test_registering_the_panel_twice_is_harmless(
    hass: HomeAssistant,
) -> None:
    """The guard holds even when registration is reached a second time.

    Home Assistant raises on a duplicate panel, so this is what keeps a setup
    that ran twice from failing outright.
    """
    await _setup(hass)

    await async_register_panel(hass)

    assert PANEL_URL_PATH in _panels(hass)


async def test_the_frontend_files_the_panel_loads_exist() -> None:
    """Every module the entry point imports is actually shipped.

    A missing file here is a panel that loads halfway and then throws in the
    browser console, which is exactly the failure this catches before the
    developer has to find it by hand.
    """
    frontend_dir = (
        Path(__file__).parent.parent / "custom_components" / DOMAIN / FRONTEND_DIR_NAME
    )
    entry_point = frontend_dir / f"{PANEL_COMPONENT_NAME}.js"

    assert entry_point.is_file()

    source = entry_point.read_text(encoding="utf-8")
    imported = [
        line.split("'")[1]
        for line in source.splitlines()
        if line.strip().startswith("import") and "'" in line
    ]

    assert imported, "the entry point imports nothing, which cannot be right"
    for relative in imported:
        assert (entry_point.parent / relative).is_file(), f"{relative} is missing"


# --- Every code the customer can see has a Dutch word ------------------------


def _label_keys(table_name: str) -> set[str]:
    """Return the keys of one table in the panel's shared label module.

    Parsed out of the JavaScript rather than duplicated here, because the point
    of this test is that the two files cannot drift apart. The panel's texts
    live in the frontend and not in ``translations/`` (SPEC.md §26), so this is
    the only place a Python test can reach them.
    """
    source = (
        Path(__file__).parent.parent
        / "custom_components"
        / DOMAIN
        / FRONTEND_DIR_NAME
        / "core"
        / "labels.js"
    ).read_text(encoding="utf-8")

    body = source.split(f"const {table_name} = {{", 1)[1].split("};", 1)[0]
    return {
        line.split(":", 1)[0].strip()
        for line in body.splitlines()
        if ":" in line and not line.strip().startswith("//")
    }


def test_every_reason_code_has_a_dutch_label() -> None:
    """A code without a word is a code the customer ends up reading.

    This is the guard on the leak of phase A: the panel printed "REDEN:
    missing_required_data" because the reason was rendered directly, and every
    table that did exist fell back to the key. The fallbacks are gone, so a new
    code without an entry now shows nothing at all — which is why the check that
    it has one belongs in the suite rather than in someone's memory.
    """
    assert set(REASON_CODES) <= _label_keys("REASON_LABELS")


def test_every_confidence_level_has_a_dutch_label() -> None:
    """Both the panel and the coach need a word for every level."""
    assert set(CONFIDENCE_LEVELS) <= _label_keys("CONFIDENCE_LABELS")
    # The coach builds its own sentences in the backend, so it carries the same
    # table; "Betrouwbaarheid: high." is what a gap here used to produce.
    assert set(CONFIDENCE_LEVELS) <= set(_CONFIDENCE_LABELS)


def test_every_checklist_item_has_a_dutch_label() -> None:
    """The missing-data list names things, never checklist keys."""
    assert set(COMPLETENESS_POINTS) <= _label_keys("CHECKLIST_LABELS")
    assert set(COMPLETENESS_POINTS) <= set(_ITEM_LABELS)


def test_the_panel_never_falls_back_to_a_raw_key() -> None:
    """No lookup in the panel may use the key as its own default.

    ``LABELS[key] || key`` is the pattern that caused this: it turns a missing
    word into a visible identifier, and it does so precisely when something has
    been forgotten.
    """
    tabs = (
        Path(__file__).parent.parent / "custom_components" / DOMAIN / FRONTEND_DIR_NAME
    ).glob("tabs/*.js")

    for path in tabs:
        source = path.read_text(encoding="utf-8")
        for pattern in ("|| item.confidence", "|| item)", "_LABELS[item] ||"):
            assert pattern not in source, f"{path.name} falls back to a raw key"


# --- One version number, in four files ---------------------------------------


def test_the_version_is_the_same_everywhere() -> None:
    """The four places that carry the version have to agree.

    They are not decorative. ``const.VERSION`` builds the static path the panel
    is served under, the panel module carries its own copy for the cache-busting
    query, ``manifest.json`` is what Home Assistant and HACS show, and
    ``pyproject.toml`` is what the package says it is. Let them drift and the
    panel is served under one version while its entry point asks for another —
    which is the half-old, half-new panel the versioned path exists to prevent.

    Bumping a release means changing all four, and this is what says so out
    loud instead of leaving it to whoever remembers.
    """
    root = Path(__file__).parent.parent
    component = root / "custom_components" / DOMAIN

    manifest = json.loads((component / "manifest.json").read_text(encoding="utf-8"))
    panel_source = (
        component / FRONTEND_DIR_NAME / f"{PANEL_COMPONENT_NAME}.js"
    ).read_text(encoding="utf-8")
    panel_version = re.search(r"const VERSION = '([^']+)'", panel_source)
    project = re.search(
        r'^version = "([^"]+)"',
        (root / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE,
    )

    assert panel_version is not None, "the panel no longer declares a VERSION"
    assert project is not None, "pyproject.toml no longer declares a version"

    assert manifest["version"] == VERSION
    assert panel_version.group(1) == VERSION
    assert project.group(1) == VERSION
