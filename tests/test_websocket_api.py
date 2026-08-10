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
    ATTR_ISSUES,
    ATTR_ITEM,
    ATTR_REVISION,
    CONF_HOME_NAME,
    CONF_MANUAL_SETUP_ACKNOWLEDGED,
    CONTRACT_TYPE_DYNAMIC,
    CONTROL_AUTOMATIC,
    CONTROL_MONITOR_ONLY,
    DEFAULT_HOME_NAME,
    DEVICE_OPERATION_FIELDS,
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
    SOURCE_TYPE_CURRENT_PRICE,
    SOURCE_TYPE_GRID_METER,
    UNIT_W,
    WS_COACH_GET,
    WS_COACH_RECALCULATE,
    WS_CONFIG_GET,
    WS_DEVICES_CREATE,
    WS_DEVICES_DELETE,
    WS_DEVICES_LIST,
    WS_DEVICES_SET_OPERATION,
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
from custom_components.domotiapp_energy.models import (
    DeviceProfile,
    StoredConfiguration,
)
from custom_components.domotiapp_energy.websocket_api import _OPERATION_SCHEMA

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


async def test_updating_one_home_field_leaves_the_others_alone(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """A partial payload updates what it names and nothing else (SPEC.md §49.3).

    The regression test for a configuration that was destroyed in the field.
    Naming one amount used to reset the other twelve values to their defaults —
    name, phases, fuse, maximum power, contract type, tax, markup, thresholds —
    and answer `success` with a fresh revision.
    """
    client = await hass_ws_client(hass)
    store = entry.runtime_data.store

    await _send(
        client,
        {
            "type": WS_HOME_UPDATE,
            ATTR_EXPECTED_REVISION: store.revision,
            "home": {
                "home_name": "Beukenlaan 14",
                "phases": 3,
                "main_fuse_a": 25,
                "max_grid_power_w": 17250,
                "contract_type": CONTRACT_TYPE_DYNAMIC,
            },
        },
    )

    await _send(
        client,
        {
            "type": WS_HOME_UPDATE,
            ATTR_EXPECTED_REVISION: store.revision,
            "home": {"feed_in_markup_eur_kwh": 0.02},
        },
    )

    home = store.config.home
    assert home.feed_in_markup_eur_kwh == 0.02
    assert home.home_name == "Beukenlaan 14"
    assert home.phases == 3
    assert home.main_fuse_a == 25
    assert home.max_grid_power_w == 17250
    assert home.contract_type == CONTRACT_TYPE_DYNAMIC


async def test_an_explicit_null_still_clears_a_home_field(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Absent means "leave alone"; null means "clear" (SPEC.md §49.3).

    The panel depends on exactly this split: `payload()` sends every editable
    field and writes a cleared one as `null`, so clearing has to stay
    expressible now that omission no longer resets anything.
    """
    client = await hass_ws_client(hass)
    store = entry.runtime_data.store

    await _send(
        client,
        {
            "type": WS_HOME_UPDATE,
            ATTR_EXPECTED_REVISION: store.revision,
            "home": {"main_fuse_a": 25},
        },
    )
    assert store.config.home.main_fuse_a == 25

    await _send(
        client,
        {
            "type": WS_HOME_UPDATE,
            ATTR_EXPECTED_REVISION: store.revision,
            "home": {"main_fuse_a": None},
        },
    )

    assert store.config.home.main_fuse_a is None


async def test_updating_the_preferences(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Preferences take the same rule as the home profile (SPEC.md §49.3).

    This used to read "replaced as a whole, the way the form submits them", and
    it only passed because it asserted the two fields it set. Setting the quiet
    hours alone reset the other seven preferences.

    **The fields checked for survival are set to non-default values first, on
    purpose.** Asserting the defaults would be green either way — the untouched
    fields would come back as defaults under replacement too, and the test would
    confirm the defect instead of catching it (CLAUDE.md, the fixture that
    codifies the bug).
    """
    client = await hass_ws_client(hass)
    store = entry.runtime_data.store

    await _send(
        client,
        {
            "type": WS_PREFERENCES_UPDATE,
            ATTR_EXPECTED_REVISION: store.revision,
            "preferences": {
                "quiet_hours_end": "06:30",
                "show_technical_explanation": False,
                "min_savings_eur": 0.25,
            },
        },
    )

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
    # None of these are defaults, so they can only be here by surviving.
    assert store.config.preferences.quiet_hours_end == "06:30"
    assert store.config.preferences.show_technical_explanation is False
    assert store.config.preferences.min_savings_eur == 0.25


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
        {"type": WS_LOGS_CLEAR},
    ],
)
async def test_a_non_admin_may_not_write_installer_fields(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    command: dict[str, Any],
) -> None:
    """Every installer command refuses a read-only user (SPEC.md §14, §33.9).

    The panel greys these fields out for a resident, but that is presentation;
    this is the check that actually holds. ``preferences/update`` used to be in
    this list and deliberately is not any more — see the resident tests below.
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


# --- Validation issues and the one hard block (SPEC.md §12 and §14) ----------


async def test_reads_carry_the_validation_issues(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Issues travel with the answer, keyed by subject, so a form can place them.

    A second round trip after every save is what makes a form feel slow, so the
    map rides along with what the panel was going to fetch anyway.
    """
    client = await hass_ws_client(hass)
    await _send(
        client,
        {
            "type": WS_SOURCES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            # A price source without a basis: savable, but not usable yet.
            "source": {"id": "prijs", "type": SOURCE_TYPE_CURRENT_PRICE},
        },
    )

    issues = (await _send(client, {"type": WS_CONFIG_GET}))["result"][ATTR_ISSUES]

    assert "prijs" in issues
    fields = {issue["field"] for issue in issues["prijs"]}
    assert {"entity_id", "price_basis"} <= fields
    assert all(
        {"field", "code", "message", "severity"} == set(issue)
        for issue in issues["prijs"]
    )


async def test_every_list_command_carries_the_issues(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """sources/list, devices/list and preferences/get answer the same way."""
    client = await hass_ws_client(hass)

    for command in (WS_SOURCES_LIST, WS_DEVICES_LIST, WS_PREFERENCES_GET):
        assert ATTR_ISSUES in (await _send(client, {"type": command}))["result"]


async def test_a_write_answers_with_the_issues_of_what_was_written(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The answer shape of SPEC.md §14 with one key added, not changed."""
    client = await hass_ws_client(hass)

    response = await _send(
        client,
        {
            "type": WS_SOURCES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "source": {"id": "prijs", "type": SOURCE_TYPE_CURRENT_PRICE},
        },
    )

    assert set(response["result"]) == {ATTR_REVISION, ATTR_ITEM, ATTR_ISSUES}
    assert "price_basis" in {
        issue["field"] for issue in response["result"][ATTR_ISSUES]["prijs"]
    }


async def test_a_half_finished_row_is_still_saved(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """An installer in a meter cupboard fills a row in gradually (SPEC.md §12).

    A grid meter without a meter mode is an error-severity issue, and refusing
    it would make a work in progress impossible to save. It is stored, reported,
    and the engine leaves it alone until it is finished.
    """
    client = await hass_ws_client(hass)

    response = await _send(
        client,
        {
            "type": WS_SOURCES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "source": {"id": "grid", "type": SOURCE_TYPE_GRID_METER},
        },
    )

    assert response["success"] is True
    assert [source.id for source in entry.runtime_data.store.config.sources] == ["grid"]
    assert "meter_mode" in {
        issue["field"] for issue in response["result"][ATTR_ISSUES]["grid"]
    }


async def test_forbidden_control_blocks_a_controlling_device(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The one refusal: an agreement outranks a mode picked from a dropdown."""
    client = await hass_ws_client(hass)

    response = await _send(
        client,
        {
            "type": WS_DEVICES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device": DEVICE_PAYLOAD
            | {
                "control_mode": CONTROL_AUTOMATIC,
                "control_forbidden": True,
                "control_forbidden_reason": "Afgesproken met de klant",
            },
        },
    )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_INVALID_FORMAT
    assert entry.runtime_data.store.config.devices == []


async def test_a_source_records_the_agreement_and_cannot_contradict_it(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """On a source the block has nothing to fire on, and that is correct today.

    SPEC.md §12 puts all three kinds of truth on ``EnergySource`` as well, but
    §8 gives a source no ``control_mode``: it has the agreement and the
    capabilities, and no intent field that could contradict them. So the
    agreement is stored and nothing is refused. The check in
    ``_forbidden_control_error`` is written for both models, so it starts
    working the day a source gains an intent of its own.
    """
    client = await hass_ws_client(hass)

    response = await _send(
        client,
        {
            "type": WS_SOURCES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "source": SOURCE_PAYLOAD
            | {
                "control_mode": CONTROL_AUTOMATIC,
                "control_forbidden": True,
                "control_forbidden_reason": "Omvormer van de installateur",
            },
        },
    )

    assert response["success"] is True
    stored = entry.runtime_data.store.config.sources[0]
    assert stored.control_forbidden is True
    assert stored.control_forbidden_reason == "Omvormer van de installateur"
    assert not hasattr(stored, "control_mode")


async def test_forbidden_control_without_a_controlling_mode_is_fine(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """Recording the agreement is exactly what the field is for."""
    client = await hass_ws_client(hass)

    response = await _send(
        client,
        {
            "type": WS_DEVICES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device": DEVICE_PAYLOAD
            | {
                "control_forbidden": True,
                "control_forbidden_reason": "Afgesproken met de klant",
            },
        },
    )

    assert response["success"] is True
    assert entry.runtime_data.store.config.devices[0].control_forbidden is True


# --- Writing as a resident (SPEC.md §33.9) ----------------------------------


async def test_a_resident_may_set_his_own_preferences(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """The whole preferences tab is resident territory (SPEC.md §33.4).

    This command used to require an admin, which meant a resident could not set
    his own quiet hours — the defect that opened round 1. It does change the
    configuration and it does raise the revision; the line is drawn by whose
    data changes, not by whether something changes.
    """
    client = await hass_ws_client(hass, hass_read_only_access_token)
    store = entry.runtime_data.store
    revision = store.revision

    response = await _send(
        client,
        {
            "type": WS_PREFERENCES_UPDATE,
            ATTR_EXPECTED_REVISION: revision,
            "preferences": {"quiet_hours_start": "23:30"},
        },
    )

    assert response["success"] is True
    assert store.config.preferences.quiet_hours_start == "23:30"
    assert store.revision == revision + 1


async def test_a_resident_may_set_the_operating_fields_of_an_appliance(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """The six fields from DEVICE_OPERATION_FIELDS, and the row survives."""
    admin = await hass_ws_client(hass)
    await _send(
        admin,
        {
            "type": WS_DEVICES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device": DEVICE_PAYLOAD,
        },
    )

    resident = await hass_ws_client(hass, hass_read_only_access_token)
    response = await _send(
        resident,
        {
            "type": WS_DEVICES_SET_OPERATION,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device_id": "dishwasher",
            "operation": {
                "ready_before": "07:00",
                "days_of_week": [0, 1, 2, 3, 4],
                "is_noisy": False,
            },
        },
    )

    assert response["success"] is True
    stored = entry.runtime_data.store.config.devices[0]
    assert stored.ready_before == "07:00"
    assert stored.days_of_week == [0, 1, 2, 3, 4]
    assert stored.is_noisy is False
    # Merged, not replaced: what the installer filled in has to survive a
    # resident touching his own fields.
    assert stored.nominal_power_w == 2000.0
    assert stored.energy_per_cycle_kwh == 1.0
    assert stored.name == "Vaatwasser"


@pytest.mark.parametrize(
    "operation",
    [
        {"nominal_power_w": 1.0},
        {"control_forbidden": False},
        {"entity_links": {}},
        {"status_entity": "sensor.iets"},
        {"name": "Andere naam"},
        {"enabled": False},
        {"ready_before": "07:00", "energy_per_cycle_kwh": 99.0},
    ],
)
async def test_set_operation_refuses_anything_outside_the_allow_list(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
    operation: dict[str, Any],
) -> None:
    """An unknown key is refused, never silently dropped (SPEC.md §33.10).

    This is the one schema in the module that forbids extra keys, and the
    reason is that the absence of a key *is* the permission boundary here: the
    command is open to every logged-in user. The last case matters most — a
    legitimate field alongside a forbidden one must not sneak the forbidden one
    through.
    """
    admin = await hass_ws_client(hass)
    await _send(
        admin,
        {
            "type": WS_DEVICES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device": DEVICE_PAYLOAD,
        },
    )

    resident = await hass_ws_client(hass, hass_read_only_access_token)
    response = await _send(
        resident,
        {
            "type": WS_DEVICES_SET_OPERATION,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device_id": "dishwasher",
            "operation": operation,
        },
    )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_INVALID_FORMAT
    stored = entry.runtime_data.store.config.devices[0]
    assert stored.nominal_power_w == 2000.0
    assert stored.energy_per_cycle_kwh == 1.0
    assert stored.ready_before is None


async def test_an_empty_operation_is_refused(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """Changing nothing must not consume a revision."""
    admin = await hass_ws_client(hass)
    await _send(
        admin,
        {
            "type": WS_DEVICES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device": DEVICE_PAYLOAD,
        },
    )
    revision = _revision(entry)

    resident = await hass_ws_client(hass, hass_read_only_access_token)
    response = await _send(
        resident,
        {
            "type": WS_DEVICES_SET_OPERATION,
            ATTR_EXPECTED_REVISION: revision,
            "device_id": "dishwasher",
            "operation": {},
        },
    )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_INVALID_FORMAT
    assert _revision(entry) == revision


async def test_the_agreement_outranks_what_the_resident_wants(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """``control_forbidden`` finally carries weight (SPEC.md §33.11).

    Until the resident could set ``control_mode``, this block could not fire in
    practice: only an admin could set the mode, and an admin also sets the
    agreement. It is now the installer's veto over what the resident wants,
    which is exactly what SPEC.md §12 designed it for.
    """
    admin = await hass_ws_client(hass)
    await _send(
        admin,
        {
            "type": WS_DEVICES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device": DEVICE_PAYLOAD
            | {
                "control_forbidden": True,
                "control_forbidden_reason": "Geen aansturing afgesproken",
            },
        },
    )

    resident = await hass_ws_client(hass, hass_read_only_access_token)
    response = await _send(
        resident,
        {
            "type": WS_DEVICES_SET_OPERATION,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device_id": "dishwasher",
            "operation": {"control_mode": CONTROL_AUTOMATIC},
        },
    )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_INVALID_FORMAT
    assert entry.runtime_data.store.config.devices[0].control_mode != CONTROL_AUTOMATIC


async def test_a_resident_may_still_switch_a_permitted_appliance_off(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """``monitor_only`` is the resident's off switch, which is why `enabled` is not.

    An agreement not to steer must not also block the resident from asking for
    *less*: monitor_only steers nothing, so the veto has nothing to object to.
    """
    admin = await hass_ws_client(hass)
    await _send(
        admin,
        {
            "type": WS_DEVICES_CREATE,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device": DEVICE_PAYLOAD
            | {
                "control_forbidden": True,
                "control_forbidden_reason": "Geen aansturing afgesproken",
            },
        },
    )

    resident = await hass_ws_client(hass, hass_read_only_access_token)
    response = await _send(
        resident,
        {
            "type": WS_DEVICES_SET_OPERATION,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device_id": "dishwasher",
            "operation": {"control_mode": CONTROL_MONITOR_ONLY},
        },
    )

    assert response["success"] is True
    stored = entry.runtime_data.store.config.devices[0]
    assert stored.control_mode == CONTROL_MONITOR_ONLY
    assert stored.enabled is True


async def test_set_operation_on_an_unknown_device_is_not_found(
    hass: HomeAssistant, entry: MockConfigEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The id has to exist, like every other row command."""
    client = await hass_ws_client(hass)

    response = await _send(
        client,
        {
            "type": WS_DEVICES_SET_OPERATION,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device_id": "bestaat-niet",
            "operation": {"is_noisy": True},
        },
    )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_NOT_FOUND


async def test_a_quarantined_row_cannot_be_operated(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    hass_read_only_access_token: str,
) -> None:
    """A row with an unknown type is out of service, and stays untouched.

    Refusing also keeps derived state out of the file: ``from_dict`` disables an
    unknown type on the way in, so merging and storing would write that
    derivation back — which SPEC.md §13 forbids.
    """
    store = entry.runtime_data.store

    def _quarantine(config: StoredConfiguration) -> None:
        config.devices.append(
            DeviceProfile.from_dict({"id": "raar", "device_type": "x"})
        )

    await store.async_update(_quarantine, expected_revision=store.revision)

    resident = await hass_ws_client(hass, hass_read_only_access_token)
    response = await _send(
        resident,
        {
            "type": WS_DEVICES_SET_OPERATION,
            ATTR_EXPECTED_REVISION: _revision(entry),
            "device_id": "raar",
            "operation": {"is_noisy": True},
        },
    )

    assert response["success"] is False
    assert response["error"]["code"] == ERR_INVALID_FORMAT
    assert store.config.devices[0].is_noisy is False


def test_the_allow_list_and_the_schema_cannot_drift() -> None:
    """DEVICE_OPERATION_FIELDS is the documented list; the schema is the guard.

    The schema is spelled out per field rather than generated, because a list of
    names cannot say that a priority is one of four words. That leaves two
    places holding the same truth, so this compares them — the same arrangement
    that keeps the entity object ids in step with their translation file.
    """
    schema_fields = {str(key) for key in _OPERATION_SCHEMA.schema}

    assert schema_fields == set(DEVICE_OPERATION_FIELDS)
