"""Tests for the coordinator (SPEC.md §18).

The coordinator is where the engine meets Home Assistant, so this file checks
the four properties SPEC.md §18 demands — a listener on the linked entities and
nothing else, rebuilt on a configuration change, debounced triggers and no
overlapping calculations — plus the safety interval and a clean unload.

It also covers the report of quarantined rows. ``async_report_invalid_rows``
had no caller until now: the coordinator calls it at the moment the engine
would otherwise skip those rows silently. Both findings it can produce — a row
with an unrecognised type and two enabled sources of a type that may occur once
— are asserted to reach the logbook, because a silent failure there is
indistinguishable from a healthy installation.
"""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.domotiapp_energy.const import (
    CONF_HOME_NAME,
    CONF_MANUAL_SETUP_ACKNOWLEDGED,
    DEFAULT_HOME_NAME,
    DOMAIN,
    DUPLICATE_SUBJECT_PREFIX,
    LOG_EVENT_INVALID_CONFIGURATION,
    LOG_EVENT_SOLAR_SURPLUS_DETECTED,
    METER_MODE_SINGLE_SIGNED,
    POSITIVE_MEANS_IMPORT,
    RECALCULATE_DEBOUNCE_SECONDS,
    SAFETY_RECALCULATE_INTERVAL_MINUTES,
    SEVERITY_WARNING,
    SOURCE_TYPE_GRID_METER,
    SOURCE_TYPE_SOLAR,
    STORAGE_KEY,
    STORAGE_VERSION,
    UNIT_W,
)
from custom_components.domotiapp_energy.coordinator import (
    EnergyCoordinator,
    tracked_entity_ids,
)
from custom_components.domotiapp_energy.engine.calculator import Calculator
from custom_components.domotiapp_energy.models import (
    CoachResult,
    DeviceProfile,
    EnergySource,
    HomeProfile,
    StoredConfiguration,
)
from custom_components.domotiapp_energy.storage import ConfigurationStore

GRID_ENTITY = "sensor.netmeter"
SOLAR_ENTITY = "sensor.omvormer"
UNRELATED_ENTITY = "sensor.woonkamer_temperatuur"


def _grid_source(entity_id: str = GRID_ENTITY, **overrides: Any) -> EnergySource:
    """Return a usable single-signed grid meter."""
    return EnergySource.from_dict(
        {
            "id": "grid",
            "name": "Netmeter",
            "type": SOURCE_TYPE_GRID_METER,
            "entity_id": entity_id,
            "unit": UNIT_W,
            "meter_mode": METER_MODE_SINGLE_SIGNED,
            "positive_means": POSITIVE_MEANS_IMPORT,
        }
        | overrides
    )


def _solar_source(entity_id: str = SOLAR_ENTITY, **overrides: Any) -> EnergySource:
    """Return a usable solar source."""
    return EnergySource.from_dict(
        {
            "id": "solar",
            "name": "Omvormer",
            "type": SOURCE_TYPE_SOLAR,
            "entity_id": entity_id,
            "unit": UNIT_W,
        }
        | overrides
    )


def _store_data(config: StoredConfiguration) -> dict[str, Any]:
    """Return the storage payload for a configuration."""
    return {
        "version": STORAGE_VERSION,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": config.to_dict(),
    }


async def _setup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config: StoredConfiguration,
) -> MockConfigEntry:
    """Set up the integration with a prepared configuration."""
    hass_storage[STORAGE_KEY] = _store_data(config)
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


async def _flush_debouncer(hass: HomeAssistant) -> None:
    """Let the debounce cooldown expire and run what it scheduled."""
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RECALCULATE_DEBOUNCE_SECONDS + 1)
    )
    await hass.async_block_till_done()


# --- Which entities are watched ---------------------------------------------


async def test_only_explicitly_linked_entities_are_tracked(
    hass: HomeAssistant,
) -> None:
    """The tracked set is exactly what the installer linked (SPEC.md §2.1)."""
    config = StoredConfiguration(
        sources=[
            _grid_source(),
            _solar_source(),
            # Disabled, so nothing to read and nothing to watch.
            EnergySource.from_dict(
                {
                    "id": "battery",
                    "type": "home_battery",
                    "entity_id": "sensor.batterij",
                    "enabled": False,
                }
            ),
        ],
        devices=[
            DeviceProfile.from_dict(
                {
                    "id": "dishwasher",
                    "device_type": "dishwasher",
                    "power_entity": "sensor.vaatwasser_vermogen",
                }
            )
        ],
    )

    assert tracked_entity_ids(config) == {
        GRID_ENTITY,
        SOLAR_ENTITY,
        "sensor.vaatwasser_vermogen",
    }


async def test_separate_import_and_export_entities_are_tracked(
    hass: HomeAssistant,
) -> None:
    """A meter with separate entities contributes both of them."""
    config = StoredConfiguration(
        sources=[
            EnergySource.from_dict(
                {
                    "id": "grid",
                    "type": SOURCE_TYPE_GRID_METER,
                    "meter_mode": "separate_import_export",
                    "import_entity_id": "sensor.afname",
                    "export_entity_id": "sensor.teruglevering",
                }
            )
        ]
    )

    assert tracked_entity_ids(config) == {"sensor.afname", "sensor.teruglevering"}


async def test_a_linked_entity_triggers_a_recalculation(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A state change of a linked entity leads to exactly one calculation."""
    hass.states.async_set(GRID_ENTITY, "100")
    entry = await _setup(
        hass, hass_storage, StoredConfiguration(sources=[_grid_source()])
    )

    with patch.object(
        Calculator, "calculate", autospec=True, side_effect=Calculator.calculate
    ) as calculate:
        hass.states.async_set(GRID_ENTITY, "250")
        await hass.async_block_till_done()
        await _flush_debouncer(hass)

    assert calculate.call_count == 1
    assert entry.runtime_data.coordinator.data.metrics.grid_power_w == 250.0


async def test_an_unlinked_entity_does_not_trigger_anything(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Entities nobody linked are not watched, however many there are."""
    hass.states.async_set(GRID_ENTITY, "100")
    await _setup(hass, hass_storage, StoredConfiguration(sources=[_grid_source()]))

    with patch.object(
        Calculator, "calculate", autospec=True, side_effect=Calculator.calculate
    ) as calculate:
        hass.states.async_set(UNRELATED_ENTITY, "21.5")
        await hass.async_block_till_done()
        await _flush_debouncer(hass)

    assert calculate.call_count == 0


async def test_a_burst_of_changes_is_debounced_into_one_calculation(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Five updates within the cooldown cost one calculation (SPEC.md §18)."""
    hass.states.async_set(GRID_ENTITY, "100")
    await _setup(hass, hass_storage, StoredConfiguration(sources=[_grid_source()]))

    with patch.object(
        Calculator, "calculate", autospec=True, side_effect=Calculator.calculate
    ) as calculate:
        for value in range(200, 250, 10):
            hass.states.async_set(GRID_ENTITY, str(value))
        await hass.async_block_till_done()
        await _flush_debouncer(hass)

    assert calculate.call_count == 1


async def test_the_listener_is_rebuilt_when_the_configuration_changes(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A newly linked entity is watched; an unlinked one stops being watched."""
    hass.states.async_set(GRID_ENTITY, "100")
    entry = await _setup(
        hass, hass_storage, StoredConfiguration(sources=[_grid_source()])
    )
    store = entry.runtime_data.store

    def _replace_source(config: StoredConfiguration) -> None:
        config.sources = [_solar_source()]

    await store.async_update(_replace_source)
    await hass.async_block_till_done()
    await _flush_debouncer(hass)

    with patch.object(
        Calculator, "calculate", autospec=True, side_effect=Calculator.calculate
    ) as calculate:
        # The old entity is no longer linked and must be ignored.
        hass.states.async_set(GRID_ENTITY, "999")
        await hass.async_block_till_done()
        await _flush_debouncer(hass)
        assert calculate.call_count == 0

        # The new one is watched without anyone having to say so.
        hass.states.async_set(SOLAR_ENTITY, "1500")
        await hass.async_block_till_done()
        await _flush_debouncer(hass)
        assert calculate.call_count == 1


async def test_the_safety_interval_recalculates_every_five_minutes(
    hass: HomeAssistant, hass_storage: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """The periodic recalculation runs without any state change (SPEC.md §18)."""
    hass.states.async_set(GRID_ENTITY, "100")
    await _setup(hass, hass_storage, StoredConfiguration(sources=[_grid_source()]))

    with patch.object(
        Calculator, "calculate", autospec=True, side_effect=Calculator.calculate
    ) as calculate:
        freezer.tick(timedelta(minutes=SAFETY_RECALCULATE_INTERVAL_MINUTES, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert calculate.call_count == 1


async def test_unloading_removes_the_state_listener(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """After unloading, a linked entity no longer wakes the integration."""
    hass.states.async_set(GRID_ENTITY, "100")
    entry = await _setup(
        hass, hass_storage, StoredConfiguration(sources=[_grid_source()])
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    with patch.object(
        Calculator, "calculate", autospec=True, side_effect=Calculator.calculate
    ) as calculate:
        hass.states.async_set(GRID_ENTITY, "4000")
        await hass.async_block_till_done()
        await _flush_debouncer(hass)

    assert calculate.call_count == 0


# --- No overlapping calculations --------------------------------------------


async def test_calculations_never_overlap(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Two simultaneous refreshes run one after the other (SPEC.md §18)."""
    hass_storage[STORAGE_KEY] = _store_data(
        StoredConfiguration(sources=[_grid_source()])
    )
    hass.states.async_set(GRID_ENTITY, "100")

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOME_NAME: DEFAULT_HOME_NAME})
    entry.add_to_hass(hass)
    store = ConfigurationStore(hass)
    await store.async_load()

    active = 0
    concurrent = 0

    class _CountingProvider:
        """Records how many calculations are inside the provider at once."""

        async def async_generate(self, result: CoachResult) -> CoachResult:
            nonlocal active, concurrent
            active += 1
            concurrent = max(concurrent, active)
            # Yield control, so a second calculation would get in here if the
            # lock did not hold it back.
            await asyncio.sleep(0)
            active -= 1
            return result

    coordinator = EnergyCoordinator(hass, entry, store, _CountingProvider())
    await asyncio.gather(coordinator.async_refresh(), coordinator.async_refresh())

    assert concurrent == 1


# --- Reporting quarantined rows ---------------------------------------------


async def test_a_calculation_reports_an_unknown_type_and_a_duplicate_source(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Both quarantine findings reach the logbook (SPEC.md §12 and §16).

    ``async_report_invalid_rows`` is only reachable through the coordinator, so
    without this test a broken call would leave a customer with a silently
    lower data quality score and nothing that says why.
    """
    hass.states.async_set(GRID_ENTITY, "100")
    hass.states.async_set("sensor.tweede_netmeter", "150")

    config = StoredConfiguration(
        home=HomeProfile(main_fuse_a=25, max_grid_power_w=5750.0),
        sources=[
            _grid_source(),
            _grid_source(entity_id="sensor.tweede_netmeter", id="grid2", name="Tweede"),
            EnergySource.from_dict(
                {
                    "id": "kapot",
                    "name": "Oude zonnebron",
                    "type": "solar_v2",
                    "entity_id": SOLAR_ENTITY,
                }
            ),
        ],
    )
    entry = await _setup(hass, hass_storage, config)

    logs = entry.runtime_data.store.config.logs
    invalid = [
        entry_
        for entry_ in logs
        if entry_.event_type == LOG_EVENT_INVALID_CONFIGURATION
    ]
    subjects = {entry_.subject for entry_ in invalid}

    # One line for the row whose type nobody recognises...
    assert "kapot" in subjects
    # ...and one for the type that may occur only once but occurs twice.
    assert f"{DUPLICATE_SUBJECT_PREFIX}{SOURCE_TYPE_GRID_METER}" in subjects
    assert all(entry_.severity == SEVERITY_WARNING for entry_ in invalid)

    unknown_type = next(entry_ for entry_ in invalid if entry_.subject == "kapot")
    assert "Oude zonnebron" in unknown_type.message
    assert "solar_v2" in unknown_type.message

    duplicate = next(
        entry_
        for entry_ in invalid
        if entry_.subject == f"{DUPLICATE_SUBJECT_PREFIX}{SOURCE_TYPE_GRID_METER}"
    )
    assert SOURCE_TYPE_GRID_METER in duplicate.message

    # Neither of the two grid meters is used, so there is no grid power at all.
    assert entry.runtime_data.coordinator.data.metrics.grid_power_w is None


async def test_a_solar_surplus_is_recorded_in_the_logbook(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Exporting more than the configured minimum produces one logbook line.

    The subject is fixed, so a surplus that lasts all afternoon stays one line
    with a counter instead of a line per recalculation (SPEC.md §8).
    """
    hass.states.async_set(GRID_ENTITY, "-1500")
    config = StoredConfiguration(
        home=HomeProfile(
            main_fuse_a=25, max_grid_power_w=5750.0, min_solar_surplus_w=500.0
        ),
        sources=[_grid_source()],
    )
    entry = await _setup(hass, hass_storage, config)

    logs = entry.runtime_data.store.config.logs
    surplus_logs = [
        log for log in logs if log.event_type == LOG_EVENT_SOLAR_SURPLUS_DETECTED
    ]

    assert len(surplus_logs) == 1
    assert "1500" in surplus_logs[0].message

    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    logs = entry.runtime_data.store.config.logs
    surplus_logs = [
        log for log in logs if log.event_type == LOG_EVENT_SOLAR_SURPLUS_DETECTED
    ]
    assert len(surplus_logs) == 1
    assert surplus_logs[0].count == 2


async def test_reporting_quarantined_rows_leaves_the_revision_alone(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Writing those log lines is not a configuration change (SPEC.md §13)."""
    config = StoredConfiguration(
        sources=[
            EnergySource.from_dict({"id": "kapot", "name": "Bron", "type": "solar_v2"})
        ]
    )
    entry = await _setup(hass, hass_storage, config)
    store = entry.runtime_data.store

    revision = store.revision
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert store.revision == revision
    assert any(
        log.event_type == LOG_EVENT_INVALID_CONFIGURATION for log in store.config.logs
    )
