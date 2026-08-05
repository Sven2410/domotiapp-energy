"""Tests for the WebSocket API (SPEC.md §14 and §24).

Covers the list from SPEC.md §24 — reading as a normal user, writing as an
admin, a write refused for a non-admin, an unknown id, a duplicate id and a
stale ``expected_revision`` — plus the answer shape every write shares and the
logbook entries the writes produce.
"""

from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.domotiapp_energy.const import (
    ATTR_EXPECTED_REVISION,
    ATTR_ITEM,
    ATTR_REVISION,
    CONF_HOME_NAME,
    CONF_MANUAL_SETUP_ACKNOWLEDGED,
    DEFAULT_HOME_NAME,
    DEVICE_TYPE_DISHWASHER,
    DOMAIN,
    ERR_DUPLICATE_ID,
    ERR_INVALID_FORMAT,
    ERR_NOT_FOUND,
    ERR_REVISION_CONFLICT,
    ERR_STORAGE_ERROR,
    LOG_EVENT_CONFIG_CHANGED,
    LOG_EVENT_DEVICE_ADDED,
    LOG_EVENT_DEVICE_REMOVED,
    METER_MODE_SINGLE_SIGNED,
    POSITIVE_MEANS_IMPORT,
    SOURCE_TYPE_GRID_METER,
    UNIT_W,
    WS_COACH_GET,
    WS_COACH_RECALCULATE,
    WS_CONFIG_GET,
    WS_DEVICES_CREATE,
    WS_DEVICES_DELETE,
    WS_DEVICES_LIST,
    WS_DEVICES_UPDATE,
    WS_HOME_UPDATE,
    WS_LOGS_CLEAR,
    WS_LOGS_LIST,
    WS_PREFERENCES_GET,
    WS_PREFERENCES_UPDATE,
    WS_SOURCES_CREATE,
    WS_SOURCES_DELETE,
    WS_SOURCES_LIST,
    WS_SOURCES_UPDATE,
)
from custom_components.domotiapp_energy.coordinator import tracked_entity_ids

SOURCE_PAYLOAD: dict[str, Any] = {
    "id": "grid",
    "name": "Netmeter",
    "type": SOURCE_TYPE_GRID_METER,
    "entity_id": "sensor.netmeter",
    "unit": UNIT_W,
    "meter_mode": METER_MODE_SINGLE_SIGNED,
    "positive_means": POSITIVE_MEANS_IMPORT,
}

DEVICE_PAYLOAD: dict[str, Any] = {
    "id": "dishwasher",
    "name": "Vaatwasser",
    "device_type": DEVICE_TYPE_DISHWASHER,
    "nominal_power_w": 2000.0,
    "energy_per_cycle_kwh": 1.0,
}


@pytest.fixture(name="entry")
async def entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration with an empty configuration."""
    assert await async_setup_component(hass, "websocket_api", {})

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


async def _send(client: Any, command: dict[str, Any]) -> dict[str, Any]:
    """Send one command and return the raw result frame."""
    await client.send_json_auto_id(command)
    response = await client.receive_json()
    assert response["type"] == TYPE_RESULT
    return response


def _revision(entry: MockConfigEntry) -> int:
    """Return the revision the next write should be based on."""
    return entry.runtime_data.store.revision


# --- Reading ----------------------------------------------------------------


async def test_a_normal_user_may_read(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Every logged-in user can read the configuration (SPEC.md §14)."""
    client = await hass_ws_client(hass, hass_read_only_access_token)

    response = await _send(client, {"type": WS_CONFIG_GET})

    assert response["success"] is True
    assert response["result"][ATTR_REVISION] == _revision(entry)
    assert "home" in response["result"]
    # The logbook has its own command; sending 200 entries with every read of
    # the configuration would dominate the payload.
    assert "logs" not in response["result"]


async def test_the_read_commands_return_their_sections(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """sources, devices, preferences, coach and logs each answer."""
    client = await hass_ws_client(hass)

    assert (await _send(client, {"type": WS_SOURCES_LIST}))["result"]["sources"] == []
    assert (await _send(client, {"type": WS_DEVICES_LIST}))["result"]["devices"] == []

    preferences = await _send(client, {"type": WS_PREFERENCES_GET})
    assert preferences["result"]["preferences"]["max_advice_count"] >= 1

    coach = await _send(client, {"type": WS_COACH_GET})
    assert coach["result"]["primary_advice"]["reason_code"]

    logs = await _send(client, {"type": WS_LOGS_LIST})
    assert isinstance(logs["result"]["logs"], list)


async def test_recalculating_is_not_an_admin_command(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """A recalculation produces a result, not a configuration change."""
    client = await hass_ws_client(hass, hass_read_only_access_token)
    revision = _revision(entry)

    response = await _send(client, {"type": WS_COACH_RECALCULATE})

    assert response["success"] is True
    assert response["result"]["metrics"]
    assert _revision(entry) == revision


# --- Writing as an admin ----------------------------------------------------


async def test_an_admin_can_create_update_and_delete_a_source(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The full lifecycle of a source, with the revision moving each time."""
    client = await hass_ws_client(hass)
    store = entry.runtime_data.store
    start = store.revision

    created = await _send(
        client,
        {
            "type": WS_SOURCES_CREATE,
            ATTR_EXPECTED_REVISION: start,
            "source": SOURCE_PAYLOAD,
        },
    )
    assert created["success"] is True
    assert created["result"][ATTR_REVISION] == start + 1
    assert created["result"][ATTR_ITEM]["id"] == "grid"
    assert [source.id for source in store.config.sources] == ["grid"]

    updated = await _send(
        client,
        {
            "type": WS_SOURCES_UPDATE,
            ATTR_EXPECTED_REVISION: start + 1,
            "source": SOURCE_PAYLOAD | {"name": "Hoofdmeter"},
        },
    )
    assert updated["result"][ATTR_REVISION] == start + 2
    assert updated["result"][ATTR_ITEM]["name"] == "Hoofdmeter"
    assert store.config.sources[0].name == "Hoofdmeter"

    deleted = await _send(
        client,
        {
            "type": WS_SOURCES_DELETE,
            ATTR_EXPECTED_REVISION: start + 2,
            "source_id": "grid",
        },
    )
    assert deleted["result"][ATTR_REVISION] == start + 3
    assert deleted["result"][ATTR_ITEM] is None
    assert store.config.sources == []


async def test_an_admin_can_create_update_and_delete_a_device(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The same lifecycle for an appliance."""
    client = await hass_ws_client(hass)
    store = entry.runtime_data.store

    created = await _send(
        client,
        {
            "type": WS_DEVICES_CREATE,
            ATTR_EXPECTED_REVISION: store.revision,
            "device": DEVICE_PAYLOAD,
        },
    )
    assert created["result"][ATTR_ITEM]["id"] == "dishwasher"

    updated = await _send(
        client,
        {
            "type": WS_DEVICES_UPDATE,
            ATTR_EXPECTED_REVISION: store.revision,
            "device": DEVICE_PAYLOAD | {"name": "Vaatwasser keuken"},
        },
    )
    assert updated["result"][ATTR_ITEM]["name"] == "Vaatwasser keuken"

    deleted = await _send(
        client,
        {
            "type": WS_DEVICES_DELETE,
            ATTR_EXPECTED_REVISION: store.revision,
            "device_id": "dishwasher",
        },
    )
    assert deleted["result"][ATTR_ITEM] is None
    assert store.config.devices == []


async def test_updating_the_home_also_updates_the_config_entry(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The home name lives in two places and may never disagree.

    ``async_setup_entry`` copies the entry's name into the storage on every
    setup, so a name changed only in the storage would be reverted on the next
    restart (SPEC.md §6).
    """
    client = await hass_ws_client(hass)
    store = entry.runtime_data.store

    response = await _send(
        client,
        {
            "type": WS_HOME_UPDATE,
            ATTR_EXPECTED_REVISION: store.revision,
            "home": {
                "home_name": "Woning Noord",
                "phases": 3,
                "main_fuse_a": 25,
                "max_grid_power_w": 17250,
            },
        },
    )

    assert response["result"][ATTR_ITEM]["home_name"] == "Woning Noord"
    assert store.config.home.phases == 3
    assert entry.data[CONF_HOME_NAME] == "Woning Noord"
    assert entry.title == "Woning Noord"


async def test_updating_the_preferences(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Preferences are replaced as a whole, the way the form submits them."""
    client = await hass_ws_client(hass)
    store = entry.runtime_data.store

    response = await _send(
        client,
        {
            "type": WS_PREFERENCES_UPDATE,
            ATTR_EXPECTED_REVISION: store.revision,
            "preferences": {"max_advice_count": 5, "quiet_hours_start": "23:00"},
        },
    )

    assert response["result"][ATTR_ITEM]["max_advice_count"] == 5
    assert store.config.preferences.quiet_hours_start == "23:00"


# --- Refusals ---------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        {"type": WS_HOME_UPDATE, "home": {}},
        {"type": WS_SOURCES_CREATE, "source": SOURCE_PAYLOAD},
        {"type": WS_SOURCES_UPDATE, "source": SOURCE_PAYLOAD},
        {"type": WS_SOURCES_DELETE, "source_id": "grid"},
        {"type": WS_DEVICES_CREATE, "device": DEVICE_PAYLOAD},
        {"type": WS_DEVICES_UPDATE, "device": DEVICE_PAYLOAD},
        {"type": WS_DEVICES_DELETE, "device_id": "dishwasher"},
        {"type": WS_PREFERENCES_UPDATE, "preferences": {}},
        {"type": WS_LOGS_CLEAR},
    ],
)
async def test_a_non_admin_may_not_write(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    command: dict[str, Any],
) -> None:
    """Every write command refuses a read-only user (SPEC.md §14).

    The panel hides the configuration tabs for non-admins, but that is a
    convenience; this is the check that actually holds.
    """
    client = await hass_ws_client(hass, hass_read_only_access_token)

    response = await _send(client, command | {ATTR_EXPECTED_REVISION: _revision(entry)})

    assert response["success"] is False
    assert response["error"]["code"] == "unauthorized"


async def test_an_unknown_source_is_not_found(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Updating something that does not exist is not_found, not a crash."""
    client = await hass_ws_client(hass)

    response = await _send(
        client,
        {
            "type": WS_SOURCES_UPDATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "source": SOURCE_PAYLOAD | {"id": "bestaat-niet"},
        },
    )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_NOT_FOUND
    # A refused write consumes no revision.
    assert _revision(entry) == 1


async def test_an_unknown_device_is_not_found(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Deleting an appliance that does not exist is not_found."""
    client = await hass_ws_client(hass)

    response = await _send(
        client,
        {
            "type": WS_DEVICES_DELETE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device_id": "bestaat-niet",
        },
    )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_NOT_FOUND


async def test_a_duplicate_id_is_refused(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Creating the same id twice is duplicate_id (SPEC.md §14)."""
    client = await hass_ws_client(hass)

    await _send(
        client,
        {
            "type": WS_SOURCES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "source": SOURCE_PAYLOAD,
        },
    )
    response = await _send(
        client,
        {
            "type": WS_SOURCES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "source": SOURCE_PAYLOAD,
        },
    )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_DUPLICATE_ID
    assert len(entry.runtime_data.store.config.sources) == 1


async def test_a_duplicate_device_id_is_refused(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Appliances guard their ids the same way sources do."""
    client = await hass_ws_client(hass)

    await _send(
        client,
        {
            "type": WS_DEVICES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device": DEVICE_PAYLOAD,
        },
    )
    response = await _send(
        client,
        {
            "type": WS_DEVICES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device": DEVICE_PAYLOAD,
        },
    )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_DUPLICATE_ID
    assert len(entry.runtime_data.store.config.devices) == 1


async def test_a_stale_revision_is_a_conflict_and_returns_the_configuration(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """A write based on an outdated revision is refused with the current state.

    The configuration travels with the error so the panel can reload instead of
    overwriting someone else's change (SPEC.md §14).
    """
    client = await hass_ws_client(hass)
    store = entry.runtime_data.store
    stale = store.revision

    await _send(
        client,
        {
            "type": WS_SOURCES_CREATE,
            ATTR_EXPECTED_REVISION: stale,
            "source": SOURCE_PAYLOAD,
        },
    )

    response = await _send(
        client,
        {
            "type": WS_DEVICES_CREATE,
            ATTR_EXPECTED_REVISION: stale,
            "device": DEVICE_PAYLOAD,
        },
    )

    assert response["success"] is False
    error = response["error"]
    assert error["code"] == ERR_REVISION_CONFLICT
    assert error[ATTR_REVISION] == store.revision
    assert [source["id"] for source in error["config"]["sources"]] == ["grid"]
    # The refused write changed nothing.
    assert store.config.devices == []


async def test_an_unknown_type_is_an_invalid_format(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """A type the panel cannot offer is a bad request, not a quarantined row.

    A stored row with an unrecognised type is kept and disabled (SPEC.md §12),
    because it came from a file we did not write. One arriving over the API is
    simply refused.
    """
    client = await hass_ws_client(hass)

    response = await _send(
        client,
        {
            "type": WS_SOURCES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "source": SOURCE_PAYLOAD | {"type": "zonnepaneel_v2"},
        },
    )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_INVALID_FORMAT
    assert entry.runtime_data.store.config.sources == []


async def test_a_write_without_a_revision_is_refused(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """expected_revision is required, so a write can never skip the check."""
    client = await hass_ws_client(hass)

    response = await _send(
        client, {"type": WS_SOURCES_CREATE, "source": SOURCE_PAYLOAD}
    )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_INVALID_FORMAT


# --- The logbook producers --------------------------------------------------


async def test_writes_are_recorded_in_the_logbook(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """config_changed, device_added and device_removed get their producers.

    These three event types existed in the model since phase 2 with nothing
    writing them; the write commands are where they belong (SPEC.md §8).
    """
    client = await hass_ws_client(hass)
    store = entry.runtime_data.store

    await _send(
        client,
        {
            "type": WS_HOME_UPDATE,
            ATTR_EXPECTED_REVISION: store.revision,
            "home": {"home_name": DEFAULT_HOME_NAME, "main_fuse_a": 25},
        },
    )
    await _send(
        client,
        {
            "type": WS_DEVICES_CREATE,
            ATTR_EXPECTED_REVISION: store.revision,
            "device": DEVICE_PAYLOAD,
        },
    )
    await _send(
        client,
        {
            "type": WS_DEVICES_DELETE,
            ATTR_EXPECTED_REVISION: store.revision,
            "device_id": "dishwasher",
        },
    )

    events = {log.event_type for log in store.config.logs}
    assert LOG_EVENT_CONFIG_CHANGED in events
    assert LOG_EVENT_DEVICE_ADDED in events
    assert LOG_EVENT_DEVICE_REMOVED in events

    removed = next(
        log for log in store.config.logs if log.event_type == LOG_EVENT_DEVICE_REMOVED
    )
    assert "Vaatwasser" in removed.message
    assert removed.subject == "dishwasher"


async def test_clearing_the_logbook_keeps_the_revision(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The logbook is not configuration, so clearing it consumes no revision.

    It is still guarded by expected_revision like every other write, and still
    admin-only (SPEC.md §13 and §14).
    """
    client = await hass_ws_client(hass)
    store = entry.runtime_data.store
    await store.async_add_log_entry("config_changed", "Titel", "Bericht")
    revision = store.revision

    response = await _send(
        client, {"type": WS_LOGS_CLEAR, ATTR_EXPECTED_REVISION: revision}
    )

    assert response["result"][ATTR_REVISION] == revision
    assert response["result"][ATTR_ITEM] is None
    assert store.config.logs == []
    assert store.revision == revision


async def test_clearing_the_logbook_refuses_a_stale_revision(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The guard applies to logs/clear too."""
    client = await hass_ws_client(hass)
    store = entry.runtime_data.store
    await store.async_add_log_entry("config_changed", "Titel", "Bericht")

    response = await _send(
        client, {"type": WS_LOGS_CLEAR, ATTR_EXPECTED_REVISION: store.revision + 5}
    )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_REVISION_CONFLICT
    assert store.config.logs != []


# --- Without a loaded entry -------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        {"type": WS_CONFIG_GET},
        {"type": WS_SOURCES_LIST},
        {"type": WS_DEVICES_LIST},
        {"type": WS_PREFERENCES_GET},
        {"type": WS_COACH_GET},
        {"type": WS_COACH_RECALCULATE},
        {"type": WS_LOGS_LIST},
        {"type": WS_HOME_UPDATE, ATTR_EXPECTED_REVISION: 1, "home": {}},
        {
            "type": WS_SOURCES_CREATE,
            ATTR_EXPECTED_REVISION: 1,
            "source": SOURCE_PAYLOAD,
        },
        {
            "type": WS_SOURCES_UPDATE,
            ATTR_EXPECTED_REVISION: 1,
            "source": SOURCE_PAYLOAD,
        },
        {"type": WS_SOURCES_DELETE, ATTR_EXPECTED_REVISION: 1, "source_id": "grid"},
        {
            "type": WS_DEVICES_CREATE,
            ATTR_EXPECTED_REVISION: 1,
            "device": DEVICE_PAYLOAD,
        },
        {
            "type": WS_DEVICES_UPDATE,
            ATTR_EXPECTED_REVISION: 1,
            "device": DEVICE_PAYLOAD,
        },
        {"type": WS_DEVICES_DELETE, ATTR_EXPECTED_REVISION: 1, "device_id": "x"},
        {"type": WS_PREFERENCES_UPDATE, ATTR_EXPECTED_REVISION: 1, "preferences": {}},
        {"type": WS_LOGS_CLEAR, ATTR_EXPECTED_REVISION: 1},
    ],
)
async def test_commands_answer_cleanly_without_a_loaded_entry(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, command: dict[str, Any]
) -> None:
    """Every command exists before the integration is set up, and says so.

    They are registered in async_setup, so they answer even when there is no
    entry — with not_found rather than a traceback (SPEC.md §21).
    """
    assert await async_setup_component(hass, DOMAIN, {})
    client = await hass_ws_client(hass)

    response = await _send(client, command)

    assert response["success"] is False
    assert response["error"]["code"] == ERR_NOT_FOUND


async def test_a_failing_write_reports_storage_error(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """A disk that refuses the write is reported, not swallowed (SPEC.md §21)."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.helpers.storage.Store.async_save",
        side_effect=OSError("disk vol"),
    ):
        response = await _send(
            client,
            {
                "type": WS_SOURCES_CREATE,
                ATTR_EXPECTED_REVISION: _revision(entry),
                "source": SOURCE_PAYLOAD,
            },
        )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_STORAGE_ERROR
    # The revision is rolled back with the failed write, so a retry does not
    # skip a number and trip the conflict check.
    assert _revision(entry) == 1


async def test_a_configuration_change_reaches_the_coordinator(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Adding a source over the API rebuilds the coordinator's listener.

    The store notifies its subscribers on every configuration change, so no
    write command has to remember to tell the coordinator (SPEC.md §18).
    """
    client = await hass_ws_client(hass)
    hass.states.async_set("sensor.netmeter", "1200")

    await _send(
        client,
        {
            "type": WS_SOURCES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "source": SOURCE_PAYLOAD,
        },
    )
    await hass.async_block_till_done()

    assert tracked_entity_ids(entry.runtime_data.store.config) == {"sensor.netmeter"}
