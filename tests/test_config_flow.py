"""Tests for the config flow and the entry lifecycle (SPEC.md §24).

Covers the list from SPEC.md §24: a successful setup, the
``single_instance_allowed`` abort on a second entry, the refusal when the
acknowledgement is not ticked, and reconfiguring the home name.
"""

from typing import Any

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.domotiapp_energy.const import (
    CONF_HOME_NAME,
    CONF_MANUAL_SETUP_ACKNOWLEDGED,
    DEFAULT_HOME_NAME,
    DOMAIN,
    ERROR_ACKNOWLEDGEMENT_REQUIRED,
    SERVICE_CLEAR_LOG,
    SERVICE_RECALCULATE,
)


def _entry(**data: Any) -> MockConfigEntry:
    """Return a config entry as the config flow would have created it."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=data.get(CONF_HOME_NAME, DEFAULT_HOME_NAME),
        data={
            CONF_HOME_NAME: DEFAULT_HOME_NAME,
            CONF_MANUAL_SETUP_ACKNOWLEDGED: True,
        }
        | data,
    )


async def test_user_flow_creates_the_entry(hass: HomeAssistant) -> None:
    """A ticked acknowledgement creates one entry with the home name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOME_NAME: "Woning Kool", CONF_MANUAL_SETUP_ACKNOWLEDGED: True},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Woning Kool"
    assert result["data"] == {
        CONF_HOME_NAME: "Woning Kool",
        CONF_MANUAL_SETUP_ACKNOWLEDGED: True,
    }

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.LOADED


async def test_user_flow_requires_the_acknowledgement(hass: HomeAssistant) -> None:
    """Without the acknowledgement the form comes back with an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOME_NAME: "Woning Kool", CONF_MANUAL_SETUP_ACKNOWLEDGED: False},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {
        CONF_MANUAL_SETUP_ACKNOWLEDGED: ERROR_ACKNOWLEDGEMENT_REQUIRED
    }
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_user_flow_falls_back_to_the_default_name(hass: HomeAssistant) -> None:
    """A blank home name becomes the default rather than an empty title."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOME_NAME: "   ", CONF_MANUAL_SETUP_ACKNOWLEDGED: True},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOME_NAME] == DEFAULT_HOME_NAME


async def test_only_one_entry_is_allowed(hass: HomeAssistant) -> None:
    """A second entry aborts with single_instance_allowed.

    The manifest's ``single_config_entry`` produces this; there is deliberately
    no hand-written check for it (SPEC.md §6).
    """
    entry = _entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_reconfigure_changes_the_home_name(hass: HomeAssistant) -> None:
    """Reconfiguring updates the entry, its title and the stored home name."""
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOME_NAME: "Woning Noord"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOME_NAME] == "Woning Noord"
    assert entry.title == "Woning Noord"
    # The storage follows the entry: the panel reads the name from there.
    assert entry.runtime_data.store.config.home.home_name == "Woning Noord"


async def test_setup_does_not_bump_the_revision_without_a_change(
    hass: HomeAssistant,
) -> None:
    """A reload with an unchanged home name leaves the revision alone.

    Otherwise every restart would expire the ``expected_revision`` the frontend
    is holding (SPEC.md §13).
    """
    entry = _entry(**{CONF_HOME_NAME: "Woning Kool"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    revision = entry.runtime_data.store.revision

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data.store.revision == revision


async def test_unload_and_reload(hass: HomeAssistant) -> None:
    """The entry unloads cleanly and can be set up again."""
    entry = _entry()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    # The services belong to the integration, not to the entry, so an unload
    # must not remove them (SPEC.md §20).
    assert hass.services.has_service(DOMAIN, SERVICE_RECALCULATE)
    assert hass.services.has_service(DOMAIN, SERVICE_CLEAR_LOG)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
