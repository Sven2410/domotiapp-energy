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

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, STATE_UNAVAILABLE
from homeassistant.core import CoreState, HomeAssistant
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
    LOG_EVENT_INVALID_MEASUREMENT,
    LOG_EVENT_PEAK_RISK_DETECTED,
    LOG_EVENT_SOLAR_SURPLUS_DETECTED,
    LOG_EVENT_SOURCE_UNAVAILABLE,
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
from custom_components.domotiapp_energy.engine.reason_codes import (
    REASON_INVALID_ENTITY_STATE,
)
from custom_components.domotiapp_energy.models import (
    CoachResult,
    DeviceProfile,
    EnergySource,
    HomeProfile,
    StoredConfiguration,
)
from custom_components.domotiapp_energy.runtime_store import RuntimeStore
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
        Calculator,
        "build_snapshot",
        autospec=True,
        side_effect=Calculator.build_snapshot,
    ) as build_snapshot:
        hass.states.async_set(GRID_ENTITY, "250")
        await hass.async_block_till_done()
        await _flush_debouncer(hass)

    assert build_snapshot.call_count == 1
    assert entry.runtime_data.coordinator.data.metrics.grid_power_w == 250.0


async def test_an_unlinked_entity_does_not_trigger_anything(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Entities nobody linked are not watched, however many there are."""
    hass.states.async_set(GRID_ENTITY, "100")
    await _setup(hass, hass_storage, StoredConfiguration(sources=[_grid_source()]))

    with patch.object(
        Calculator,
        "build_snapshot",
        autospec=True,
        side_effect=Calculator.build_snapshot,
    ) as build_snapshot:
        hass.states.async_set(UNRELATED_ENTITY, "21.5")
        await hass.async_block_till_done()
        await _flush_debouncer(hass)

    assert build_snapshot.call_count == 0


async def test_a_burst_of_changes_is_debounced_into_one_calculation(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Five updates within the cooldown cost one calculation (SPEC.md §18)."""
    hass.states.async_set(GRID_ENTITY, "100")
    await _setup(hass, hass_storage, StoredConfiguration(sources=[_grid_source()]))

    with patch.object(
        Calculator,
        "build_snapshot",
        autospec=True,
        side_effect=Calculator.build_snapshot,
    ) as build_snapshot:
        for value in range(200, 250, 10):
            hass.states.async_set(GRID_ENTITY, str(value))
        await hass.async_block_till_done()
        await _flush_debouncer(hass)

    assert build_snapshot.call_count == 1


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
        Calculator,
        "build_snapshot",
        autospec=True,
        side_effect=Calculator.build_snapshot,
    ) as build_snapshot:
        # The old entity is no longer linked and must be ignored.
        hass.states.async_set(GRID_ENTITY, "999")
        await hass.async_block_till_done()
        await _flush_debouncer(hass)
        assert build_snapshot.call_count == 0

        # The new one is watched without anyone having to say so.
        hass.states.async_set(SOLAR_ENTITY, "1500")
        await hass.async_block_till_done()
        await _flush_debouncer(hass)
        assert build_snapshot.call_count == 1


async def test_the_safety_interval_recalculates_every_five_minutes(
    hass: HomeAssistant, hass_storage: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """The periodic recalculation runs without any state change (SPEC.md §18)."""
    hass.states.async_set(GRID_ENTITY, "100")
    await _setup(hass, hass_storage, StoredConfiguration(sources=[_grid_source()]))

    with patch.object(
        Calculator,
        "build_snapshot",
        autospec=True,
        side_effect=Calculator.build_snapshot,
    ) as build_snapshot:
        freezer.tick(timedelta(minutes=SAFETY_RECALCULATE_INTERVAL_MINUTES, seconds=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert build_snapshot.call_count == 1


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
        Calculator,
        "build_snapshot",
        autospec=True,
        side_effect=Calculator.build_snapshot,
    ) as build_snapshot:
        hass.states.async_set(GRID_ENTITY, "4000")
        await hass.async_block_till_done()
        await _flush_debouncer(hass)

    assert build_snapshot.call_count == 0


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

    coordinator = EnergyCoordinator(
        hass, entry, store, RuntimeStore(hass), _CountingProvider()
    )
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


@pytest.mark.parametrize(
    ("grid_state", "expected"),
    [("5000", "gebruikt"), ("-10000", "levert terug met")],
)
async def test_the_peak_logbook_line_follows_the_direction(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    grid_state: str,
    expected: str,
) -> None:
    """A home that is exporting past the limit is not "using" its maximum."""
    hass.states.async_set(GRID_ENTITY, grid_state)
    config = StoredConfiguration(
        home=HomeProfile(main_fuse_a=25, max_grid_power_w=5750.0),
        sources=[_grid_source()],
    )
    entry = await _setup(hass, hass_storage, config)

    peak_logs = [
        log
        for log in entry.runtime_data.store.config.logs
        if log.event_type == LOG_EVENT_PEAK_RISK_DETECTED
    ]

    assert len(peak_logs) == 1
    assert expected in peak_logs[0].message


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


async def test_an_entity_that_disappeared_is_reported_as_unavailable(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A linked entity that is gone produces one source_unavailable entry.

    The entry names the source and the entity and carries the reason code, but
    never the raw state (SPEC.md §8 and §13).
    """
    # No state is set at all, so the entity does not exist.
    entry = await _setup(
        hass, hass_storage, StoredConfiguration(sources=[_grid_source()])
    )

    logs = [
        log
        for log in entry.runtime_data.store.config.logs
        if log.event_type == LOG_EVENT_SOURCE_UNAVAILABLE
    ]

    assert len(logs) == 1
    assert logs[0].severity == SEVERITY_WARNING
    assert logs[0].subject == "grid"
    assert "Netmeter" in logs[0].message
    assert GRID_ENTITY in logs[0].message
    assert REASON_INVALID_ENTITY_STATE in logs[0].message


async def test_an_unavailable_entity_is_reported_as_unavailable(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """An entity carrying no measurement is unavailable, not a bad reading."""
    hass.states.async_set(GRID_ENTITY, STATE_UNAVAILABLE)
    entry = await _setup(
        hass, hass_storage, StoredConfiguration(sources=[_grid_source()])
    )

    events = {log.event_type for log in entry.runtime_data.store.config.logs}

    assert LOG_EVENT_SOURCE_UNAVAILABLE in events
    assert LOG_EVENT_INVALID_MEASUREMENT not in events


async def test_a_non_numeric_state_is_reported_as_an_invalid_measurement(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """An entity that is present but reports nonsense is a bad reading.

    A different problem from an unavailable entity, and a different fix: this
    one is normally the wrong entity, unit or attribute rather than another
    integration being down.
    """
    hass.states.async_set(GRID_ENTITY, "aan")
    entry = await _setup(
        hass, hass_storage, StoredConfiguration(sources=[_grid_source()])
    )

    logs = [
        log
        for log in entry.runtime_data.store.config.logs
        if log.event_type == LOG_EVENT_INVALID_MEASUREMENT
    ]

    assert len(logs) == 1
    assert logs[0].subject == "grid"
    assert "Netmeter" in logs[0].message
    # The unusable state itself is never stored.
    assert "aan" not in logs[0].message.replace("waardebron", "")
    assert LOG_EVENT_SOURCE_UNAVAILABLE not in {
        log.event_type for log in entry.runtime_data.store.config.logs
    }


async def test_a_failing_source_is_reported_once_then_again_after_recovery(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """The same failure does not repeat, but a relapse is reported afresh.

    Without the first half a recalculation every few seconds would fill the
    logbook; without the second half a source that breaks again after being
    repaired would stay silent forever.
    """
    hass.states.async_set(GRID_ENTITY, STATE_UNAVAILABLE)
    entry = await _setup(
        hass, hass_storage, StoredConfiguration(sources=[_grid_source()])
    )
    store = entry.runtime_data.store
    coordinator = entry.runtime_data.coordinator

    def _unavailable_entries() -> list[Any]:
        return [
            log
            for log in store.config.logs
            if log.event_type == LOG_EVENT_SOURCE_UNAVAILABLE
        ]

    assert len(_unavailable_entries()) == 1
    assert _unavailable_entries()[0].count == 1

    # Still broken: reported once, so nothing is added and nothing is counted.
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert len(_unavailable_entries()) == 1
    assert _unavailable_entries()[0].count == 1

    # Repaired.
    hass.states.async_set(GRID_ENTITY, "1200")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.data.metrics.grid_power_w == 1200.0

    # Broken again: the installer has to hear about it a second time.
    hass.states.async_set(GRID_ENTITY, STATE_UNAVAILABLE)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    entries = _unavailable_entries()
    assert len(entries) == 1
    assert entries[0].count == 2


async def test_a_source_that_changes_failure_mode_is_reported_again(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Going from unavailable to unreadable is a new finding, not a repeat."""
    hass.states.async_set(GRID_ENTITY, STATE_UNAVAILABLE)
    entry = await _setup(
        hass, hass_storage, StoredConfiguration(sources=[_grid_source()])
    )
    store = entry.runtime_data.store

    hass.states.async_set(GRID_ENTITY, "kapot")
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    events = [
        log.event_type
        for log in store.config.logs
        if log.event_type
        in (LOG_EVENT_SOURCE_UNAVAILABLE, LOG_EVENT_INVALID_MEASUREMENT)
    ]

    assert LOG_EVENT_SOURCE_UNAVAILABLE in events
    assert LOG_EVENT_INVALID_MEASUREMENT in events


async def test_an_unconfigured_source_is_not_reported_as_a_failure(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A source that was never finished has not broken (SPEC.md §8).

    A grid meter without a meter mode consults no entity at all, so there is
    nothing to call unavailable. The data quality checklist already reports
    that it is incomplete.
    """
    entry = await _setup(
        hass,
        hass_storage,
        StoredConfiguration(sources=[_grid_source(meter_mode=None)]),
    )

    events = {log.event_type for log in entry.runtime_data.store.config.logs}

    assert LOG_EVENT_SOURCE_UNAVAILABLE not in events
    assert LOG_EVENT_INVALID_MEASUREMENT not in events


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


# --- Hysteresis against a meter that reports every second --------------------


async def test_a_load_hovering_on_the_threshold_keeps_one_answer(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """The peak warning stops rattling when the load sits near the limit.

    This is the situation a real P1 meter produces: it reports every second, so
    a load a few tens of watts either side of the warning level used to switch
    the warning — and the whole primary advice — on and off continuously
    (SPEC.md §16).
    """
    home = HomeProfile(main_fuse_a=25, max_grid_power_w=5000.0, peak_warning_percent=80)
    # 80% of 5000 W is 4000 W, so this crosses the threshold.
    hass.states.async_set(GRID_ENTITY, "4100")
    entry = await _setup(
        hass, hass_storage, StoredConfiguration(home=home, sources=[_grid_source()])
    )
    coordinator = entry.runtime_data.coordinator
    assert coordinator.data.metrics.peak_risk is True

    # Back under the threshold, but well inside the release margin: the fuse is
    # no less loaded than it was a second ago.
    for value in ("3950", "4050", "3920", "4010"):
        hass.states.async_set(GRID_ENTITY, value)
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator.data.metrics.peak_risk is True, value

    # 75% of 5000 W is 3750 W: past the release point, so the answer changes.
    hass.states.async_set(GRID_ENTITY, "3700")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.data.metrics.peak_risk is False


async def test_a_surplus_hovering_on_the_threshold_keeps_its_advice(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """The solar advice, and the amount under it, stop blinking."""
    home = HomeProfile(
        main_fuse_a=25, max_grid_power_w=5750.0, min_solar_surplus_w=500.0
    )
    hass.states.async_set(GRID_ENTITY, "-600")
    entry = await _setup(
        hass, hass_storage, StoredConfiguration(home=home, sources=[_grid_source()])
    )
    coordinator = entry.runtime_data.coordinator
    assert coordinator.data.metrics.solar_surplus_sufficient is True

    hass.states.async_set(GRID_ENTITY, "-450")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.data.metrics.solar_surplus_sufficient is True

    # Below 80% of the minimum the surplus really has gone.
    hass.states.async_set(GRID_ENTITY, "-390")
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert coordinator.data.metrics.solar_surplus_sufficient is False


async def test_a_configuration_change_clears_the_held_answers(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """An edited threshold is not judged against the answer it replaced."""
    home = HomeProfile(main_fuse_a=25, max_grid_power_w=5000.0, peak_warning_percent=80)
    hass.states.async_set(GRID_ENTITY, "4100")
    entry = await _setup(
        hass, hass_storage, StoredConfiguration(home=home, sources=[_grid_source()])
    )
    coordinator = entry.runtime_data.coordinator
    assert coordinator.data.metrics.peak_risk is True

    def _raise_the_limit(config: StoredConfiguration) -> None:
        config.home.peak_warning_percent = 95

    await entry.runtime_data.store.async_update(_raise_the_limit)
    await hass.async_block_till_done()
    await _flush_debouncer(hass)

    # 4100 W is 82% of the maximum, which is under the new warning level.
    assert coordinator.data.metrics.peak_risk is False


# --- The lowest running power (SPEC.md §59.3) -------------------------------

CHARGER_ENTITY = "sensor.laadpaal_vermogen"


def _charger(entity_id: str = CHARGER_ENTITY) -> DeviceProfile:
    """Return a modulating charger with a power sensor linked.

    `min_power_w` is 4140 W on purpose: three phases at six ampere, which is
    what Sven's Transit Connect turned out to need after the 1380 W he had
    entered proved to describe a car that charges on one phase (SPEC.md §59).
    The observation these tests are about exists to show that kind of mistake.
    """
    return DeviceProfile.from_dict(
        {
            "id": "laadpaal",
            "name": "Laadpaal",
            "device_type": "ev_charger",
            "nominal_power_w": 9660.0,
            "can_modulate": True,
            "min_power_w": 4140.0,
            # A binding is read from a top-level key, not from a nested
            # `entity_links` mapping — `from_dict` builds that mapping itself.
            "power_entity": entity_id,
        }
    )


async def _charging(
    hass: HomeAssistant, coordinator: Any, watts: str, entity_id: str = CHARGER_ENTITY
) -> None:
    """Report a charging power and let the coordinator see it."""
    hass.states.async_set(entity_id, watts, {"unit_of_measurement": UNIT_W})
    await coordinator.async_refresh()
    await hass.async_block_till_done()


async def test_the_lowest_running_power_is_remembered(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """The one figure that can show an entered minimum is too high.

    It is the only half of that mistake anything can catch: too high means the
    advice never comes, and silence looks like "no surplus" (SPEC.md §59.3).
    """
    home = HomeProfile(main_fuse_a=25, max_grid_power_w=5750.0)
    hass.states.async_set(GRID_ENTITY, "500")
    hass.states.async_set(CHARGER_ENTITY, "4765", {"unit_of_measurement": UNIT_W})
    entry = await _setup(
        hass,
        hass_storage,
        StoredConfiguration(home=home, sources=[_grid_source()], devices=[_charger()]),
    )
    coordinator = entry.runtime_data.coordinator

    assert coordinator.data.metrics.device_power_lowest_w == {"laadpaal": 4765.0}

    # The same car charging slower, and then faster again: the lowest holds.
    await _charging(hass, coordinator, "1380")
    await _charging(hass, coordinator, "4765")

    assert coordinator.data.metrics.device_power_lowest_w == {"laadpaal": 1380.0}


async def test_standby_is_not_a_measurement_of_charging(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Running is the floor the overview already counts by.

    A charger idling at a few watts would otherwise set the lowest to those few
    watts, and the row would suggest an installer enter a minimum no car can
    charge at. `DEVICE_RUNNING_MIN_POWER_W` is asked rather than a second
    threshold invented here — two answers to "is this thing on" would drift.
    """
    home = HomeProfile(main_fuse_a=25, max_grid_power_w=5750.0)
    hass.states.async_set(GRID_ENTITY, "500")
    hass.states.async_set(CHARGER_ENTITY, "4140", {"unit_of_measurement": UNIT_W})
    entry = await _setup(
        hass,
        hass_storage,
        StoredConfiguration(home=home, sources=[_grid_source()], devices=[_charger()]),
    )
    coordinator = entry.runtime_data.coordinator

    await _charging(hass, coordinator, "4")
    await _charging(hass, coordinator, "0")

    assert coordinator.data.metrics.device_power_lowest_w == {"laadpaal": 4140.0}


async def test_an_appliance_that_has_never_run_reports_nothing(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Absent, not zero: nothing has been observed yet, which is not a fault."""
    home = HomeProfile(main_fuse_a=25, max_grid_power_w=5750.0)
    hass.states.async_set(GRID_ENTITY, "500")
    hass.states.async_set(CHARGER_ENTITY, "0", {"unit_of_measurement": UNIT_W})
    entry = await _setup(
        hass,
        hass_storage,
        StoredConfiguration(home=home, sources=[_grid_source()], devices=[_charger()]),
    )

    assert entry.runtime_data.coordinator.data.metrics.device_power_lowest_w == {}


async def test_a_different_power_entity_starts_a_new_observation(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A figure belongs to the sensor it was read from.

    Relinking is how an installer fixes a wrong pick (SPEC.md §57), and keeping
    the old minimum would attribute one sensor's reading to another — a mix-up
    nothing downstream could detect.
    """
    home = HomeProfile(main_fuse_a=25, max_grid_power_w=5750.0)
    hass.states.async_set(GRID_ENTITY, "500")
    hass.states.async_set(CHARGER_ENTITY, "1380", {"unit_of_measurement": UNIT_W})
    hass.states.async_set(
        "sensor.easee_laadvermogen", "4140", {"unit_of_measurement": UNIT_W}
    )
    entry = await _setup(
        hass,
        hass_storage,
        StoredConfiguration(home=home, sources=[_grid_source()], devices=[_charger()]),
    )
    coordinator = entry.runtime_data.coordinator
    assert coordinator.data.metrics.device_power_lowest_w == {"laadpaal": 1380.0}

    def _relink(config: StoredConfiguration) -> None:
        config.devices[0].entity_links["power_entity"] = "sensor.easee_laadvermogen"

    await entry.runtime_data.store.async_update(_relink)
    await hass.async_block_till_done()
    await _flush_debouncer(hass)

    assert coordinator.data.metrics.device_power_lowest_w == {"laadpaal": 4140.0}


async def test_a_deleted_appliance_takes_its_observation_with_it(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Memory only, and no longer than the appliance it describes."""
    home = HomeProfile(main_fuse_a=25, max_grid_power_w=5750.0)
    hass.states.async_set(GRID_ENTITY, "500")
    hass.states.async_set(CHARGER_ENTITY, "4140", {"unit_of_measurement": UNIT_W})
    entry = await _setup(
        hass,
        hass_storage,
        StoredConfiguration(home=home, sources=[_grid_source()], devices=[_charger()]),
    )
    coordinator = entry.runtime_data.coordinator
    assert coordinator.data.metrics.device_power_lowest_w == {"laadpaal": 4140.0}

    def _remove(config: StoredConfiguration) -> None:
        config.devices.clear()

    await entry.runtime_data.store.async_update(_remove)
    await hass.async_block_till_done()
    await _flush_debouncer(hass)

    assert coordinator.data.metrics.device_power_lowest_w == {}


async def test_the_observation_never_reaches_the_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Derived state stays in memory (CLAUDE.md rule 9).

    Writing it back would raise the revision from a measurement, which is what
    that rule exists to prevent: an installer's open form would be refused
    because a charger reported a watt less than a second ago.
    """
    home = HomeProfile(main_fuse_a=25, max_grid_power_w=5750.0)
    hass.states.async_set(GRID_ENTITY, "500")
    hass.states.async_set(CHARGER_ENTITY, "4140", {"unit_of_measurement": UNIT_W})
    entry = await _setup(
        hass,
        hass_storage,
        StoredConfiguration(home=home, sources=[_grid_source()], devices=[_charger()]),
    )
    coordinator = entry.runtime_data.coordinator
    revision = entry.runtime_data.store.config.revision

    await _charging(hass, coordinator, "1380")

    stored = hass_storage[STORAGE_KEY]["data"]
    assert "device_power_lowest_w" not in str(stored)
    assert entry.runtime_data.store.config.revision == revision


# --- Opstarten (SPEC.md §63) ------------------------------------------------


async def test_a_source_that_does_not_exist_yet_is_not_reported(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """De race die elke klant bij elke update trof.

    Wij worden opgezet zodra onze eigen afhankelijkheden klaar zijn, en Home
    Assistant zet integraties parallel op — dus de bronnen van een klant kunnen
    er nog niet zijn. Alle drie tegelijk falen is dan feitelijk juist en
    praktisch onzin: een seconde later bestaan ze wel.

    Drie waarschuwingen bij elke herstart leren een klant waarschuwingen
    negeren, en dat kost meer dan de melding oplevert (dezelfde afweging als
    §43.2).
    """
    hass.set_state(CoreState.starting)
    # De entiteit bestaat met opzet niet: dat is precies de toestand tijdens
    # het opstarten.
    entry = await _setup(
        hass,
        hass_storage,
        StoredConfiguration(home=HomeProfile(), sources=[_grid_source()]),
    )

    logs = entry.runtime_data.store.config.logs
    assert not [
        entry for entry in logs if entry.event_type == LOG_EVENT_SOURCE_UNAVAILABLE
    ]


async def test_the_same_source_is_reported_once_home_assistant_has_started(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """De andere helft: zwijgen tijdens het opstarten is geen zwijgen.

    Zodra de installatie er helemaal is, is een bron die niet gelezen kan
    worden wél een uitspraak over die installatie — en dan hoort zij in het
    logboek, zoals altijd.
    """
    hass.set_state(CoreState.starting)
    entry = await _setup(
        hass,
        hass_storage,
        StoredConfiguration(home=HomeProfile(), sources=[_grid_source()]),
    )

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    await _flush_debouncer(hass)

    logs = entry.runtime_data.store.config.logs
    assert [entry for entry in logs if entry.event_type == LOG_EVENT_SOURCE_UNAVAILABLE]


async def test_the_start_signal_recalculates_by_itself(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """**Het punt van de hele reparatie** (SPEC.md §63), en zonder hulp.

    De state-listener vangt het gewone geval al: verschijnt een bron later, dan
    is dat een statuswijziging en herberekenen we. Maar dan hangt het herstel af
    van de vraag óf er nog iets verandert — en een prijsbron die per uur schrijft
    verandert een uur lang niet. Tot dan zou de klant een oordeel over zijn
    installatie krijgen dat op een halve wereld rust.

    Deze test verandert daarom met opzet **niets** aan de entiteiten: alleen het
    startsignaal van Home Assistant, en dat moet op zichzelf genoeg zijn.
    """
    hass.set_state(CoreState.starting)
    hass.states.async_set(GRID_ENTITY, "1150", {"unit_of_measurement": UNIT_W})
    entry = await _setup(
        hass,
        hass_storage,
        StoredConfiguration(
            home=HomeProfile(main_fuse_a=25, max_grid_power_w=5750.0),
            sources=[_grid_source()],
        ),
    )
    coordinator = entry.runtime_data.coordinator
    eerste = coordinator.data.generated_at

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    await _flush_debouncer(hass)

    assert coordinator.data.generated_at > eerste
