"""Tests for the two services (SPEC.md §20).

Home Assistant does not check permissions for services, so the admin check is
written by hand — and therefore has to be tested by hand. A call without a user
id comes from an automation or a script and is allowed on purpose.
"""

import pytest
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

from custom_components.domotiapp_energy.const import (
    CONF_HOME_NAME,
    CONF_MANUAL_SETUP_ACKNOWLEDGED,
    DEFAULT_HOME_NAME,
    DOMAIN,
    LOG_EVENT_ADVICE_RECALCULATED,
    SERVICE_CLEAR_LOG,
    SERVICE_RECALCULATE,
    SEVERITY_INFO,
)


@pytest.fixture(name="entry")
async def entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
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


async def test_recalculate_recalculates_and_logs_it(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """The service forces a calculation and records it in the logbook."""
    store = entry.runtime_data.store
    before = entry.runtime_data.coordinator.data.generated_at

    await hass.services.async_call(DOMAIN, SERVICE_RECALCULATE, blocking=True)
    await hass.async_block_till_done()

    assert entry.runtime_data.coordinator.data.generated_at >= before
    assert any(
        log.event_type == LOG_EVENT_ADVICE_RECALCULATED for log in store.config.logs
    )


async def test_recalculate_leaves_the_revision_alone(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Recalculating produces a result, not a configuration change."""
    store = entry.runtime_data.store
    revision = store.revision

    await hass.services.async_call(DOMAIN, SERVICE_RECALCULATE, blocking=True)
    await hass.async_block_till_done()

    assert store.revision == revision


async def test_clear_log_empties_the_logbook(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """The service removes every entry and nothing else."""
    store = entry.runtime_data.store
    await store.async_add_log_entry(
        "config_changed", "Titel", "Bericht", severity=SEVERITY_INFO
    )
    assert store.config.logs

    home_name = store.config.home.home_name
    await hass.services.async_call(DOMAIN, SERVICE_CLEAR_LOG, blocking=True)
    await hass.async_block_till_done()

    assert store.config.logs == []
    assert store.config.home.home_name == home_name


@pytest.mark.parametrize("service", [SERVICE_RECALCULATE, SERVICE_CLEAR_LOG])
async def test_a_non_admin_may_not_call_the_services(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_read_only_user: MockUser,
    service: str,
) -> None:
    """A read-only user is refused, whichever service they try."""
    context = Context(user_id=hass_read_only_user.id)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(DOMAIN, service, blocking=True, context=context)


async def test_an_admin_may_call_the_services(
    hass: HomeAssistant, entry: MockConfigEntry, hass_admin_user: MockUser
) -> None:
    """An admin passes the same check that stops the read-only user."""
    store = entry.runtime_data.store
    await store.async_add_log_entry("config_changed", "Titel", "Bericht")

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CLEAR_LOG,
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.async_block_till_done()

    assert store.config.logs == []


async def test_a_call_without_a_user_is_allowed(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """An automation or script has no user id and is allowed (SPEC.md §20)."""
    store = entry.runtime_data.store
    await store.async_add_log_entry("config_changed", "Titel", "Bericht")

    await hass.services.async_call(
        DOMAIN, SERVICE_CLEAR_LOG, blocking=True, context=Context()
    )
    await hass.async_block_till_done()

    assert store.config.logs == []


async def test_the_services_survive_an_unload(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Unloading the entry leaves the services registered (SPEC.md §20).

    Calling one then does nothing at all, because there is no loaded entry to
    act on — but the service does not disappear from Home Assistant.
    """
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_RECALCULATE)
    await hass.services.async_call(DOMAIN, SERVICE_RECALCULATE, blocking=True)
