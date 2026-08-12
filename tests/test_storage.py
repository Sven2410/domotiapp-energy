"""Tests for the models and the configuration store (SPEC.md §24)."""

from collections.abc import Generator
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, timedelta
from typing import Any
from unittest.mock import patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.domotiapp_energy.const import (
    CAPABILITY_READ,
    CAPABILITY_SET_POWER_LIMIT,
    CAPABILITY_SWITCH,
    CONTROL_ADVICE_ONLY,
    CONTROL_MONITOR_ONLY,
    DEFAULT_CONTRACT_TYPE,
    DEFAULT_HOME_NAME,
    DEFAULT_MAX_ADVICE_COUNT,
    DEFAULT_PEAK_WARNING_PERCENT,
    DEFAULT_PHASES,
    DEFAULT_PRIORITY,
    DEFAULT_SCALE_FACTOR,
    DEFAULT_VAT_PERCENT,
    DEVICE_TYPE_DISHWASHER,
    DEVICE_TYPE_HEAT_PUMP,
    DUPLICATE_SUBJECT_PREFIX,
    INITIAL_REVISION,
    INVALID_REASON_UNKNOWN_TYPE,
    LOG_DEDUPE_WINDOW_MINUTES,
    LOG_EVENT_ADVICE_RECALCULATED,
    LOG_EVENT_CONFIG_CHANGED,
    LOG_EVENT_INVALID_CONFIGURATION,
    LOG_EVENT_PEAK_RISK_DETECTED,
    LOG_EVENT_SOLAR_SURPLUS_DETECTED,
    LOG_FLUSH_INTERVAL_SECONDS,
    MAX_ADVICE_COUNT,
    MAX_LOG_ENTRIES,
    METER_MODE_SINGLE_SIGNED,
    NOMINAL_VOLTAGE_PER_PHASE,
    PHASES_THREE,
    PRICE_BASIS_ALL_IN,
    PRICE_BASIS_MARKET,
    SCHEMA_VERSION,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SOURCE_TYPE_CURRENT_PRICE,
    SOURCE_TYPE_GRID_METER,
    STORAGE_KEY,
    STORAGE_MINOR_VERSION,
    STORAGE_VERSION,
    UNIT_KW,
    UNIT_NONE,
    VALUE_SOURCE_ATTRIBUTE,
    VALUE_SOURCE_STATE,
)
from custom_components.domotiapp_energy.models import (
    AdviceItem,
    CoachResult,
    DataQualityResult,
    DeviceProfile,
    EnergyMetrics,
    EnergySnapshot,
    EnergySource,
    HomeProfile,
    SourceFailure,
    StoredConfiguration,
)
from custom_components.domotiapp_energy.storage import (
    ConfigurationStore,
    DomotiAppEnergyStore,
    RevisionConflictError,
    StorageError,
)


def _stored(
    data: dict[str, Any], *, minor_version: int = STORAGE_MINOR_VERSION
) -> dict[str, Any]:
    """Wrap raw data in the envelope Home Assistant writes to .storage."""
    return {
        "version": STORAGE_VERSION,
        "minor_version": minor_version,
        "key": STORAGE_KEY,
        "data": data,
    }


# --- Defaults ---------------------------------------------------------------


async def test_load_without_stored_file_yields_defaults(hass: HomeAssistant) -> None:
    """A fresh install loads a complete, usable default configuration."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    assert config.schema_version == SCHEMA_VERSION
    assert config.revision == INITIAL_REVISION
    assert config.home.home_name == DEFAULT_HOME_NAME
    assert config.home.phases == DEFAULT_PHASES
    assert config.home.contract_type == DEFAULT_CONTRACT_TYPE
    assert config.home.peak_warning_percent == DEFAULT_PEAK_WARNING_PERCENT
    assert config.home.main_fuse_a is None
    assert config.home.max_grid_power_w is None
    assert config.sources == []
    assert config.devices == []
    assert config.logs == []
    assert config.preferences.max_advice_count == DEFAULT_MAX_ADVICE_COUNT


async def test_default_configuration_matches_documented_shape(
    hass: HomeAssistant,
) -> None:
    """to_dict() produces exactly the top-level keys from SPEC.md §13."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    assert set(config.to_dict()) == {
        "schema_version",
        "revision",
        "home",
        "sources",
        "devices",
        "preferences",
        "logs",
    }


async def test_config_before_load_raises(hass: HomeAssistant) -> None:
    """Reading the configuration before loading is a programming error."""
    store = ConfigurationStore(hass)

    assert store.loaded is False
    with pytest.raises(StorageError):
        _ = store.config


# --- Saving, loading and revisions ------------------------------------------


async def test_configuration_survives_a_reload(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Everything written is read back by a fresh store instance."""
    store = ConfigurationStore(hass)
    await store.async_load()

    def _configure(config: StoredConfiguration) -> None:
        config.home.home_name = "Testwoning"
        config.home.phases = PHASES_THREE
        config.home.main_fuse_a = 25
        config.home.max_grid_power_w = 17250.0
        config.sources.append(
            EnergySource(
                id="source-1",
                name="Slimme meter",
                type=SOURCE_TYPE_GRID_METER,
                meter_mode=METER_MODE_SINGLE_SIGNED,
                positive_means="import",
            )
        )
        config.devices.append(
            DeviceProfile(id="device-1", name="Vaatwasser", device_type="dishwasher")
        )

    await store.async_update(_configure)
    assert STORAGE_KEY in hass_storage

    reloaded = await ConfigurationStore(hass).async_load()

    assert reloaded.home.home_name == "Testwoning"
    assert reloaded.home.phases == PHASES_THREE
    assert reloaded.home.main_fuse_a == 25
    assert reloaded.home.max_grid_power_w == 17250.0
    assert [source.id for source in reloaded.sources] == ["source-1"]
    assert reloaded.sources[0].type == SOURCE_TYPE_GRID_METER
    assert reloaded.sources[0].meter_mode == METER_MODE_SINGLE_SIGNED
    assert [device.name for device in reloaded.devices] == ["Vaatwasser"]


async def test_every_write_increments_the_revision(hass: HomeAssistant) -> None:
    """Each successful write bumps the revision by exactly one."""
    store = ConfigurationStore(hass)
    config = await store.async_load()
    start = config.revision

    def _rename(target: StoredConfiguration) -> None:
        target.home.home_name = "Nieuwe naam"

    assert await store.async_update(_rename) == start + 1
    assert await store.async_update(_rename) == start + 2
    assert store.revision == start + 2


async def test_matching_expected_revision_is_accepted(hass: HomeAssistant) -> None:
    """A caller that is up to date may write."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    def _rename(target: StoredConfiguration) -> None:
        target.home.home_name = "Woning A"

    new_revision = await store.async_update(_rename, expected_revision=config.revision)

    assert new_revision == config.revision
    assert config.home.home_name == "Woning A"


async def test_stale_expected_revision_is_rejected(hass: HomeAssistant) -> None:
    """A stale revision raises and leaves the configuration untouched."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    def _rename(target: StoredConfiguration) -> None:
        target.home.home_name = "Eerste"

    await store.async_update(_rename)
    current = config.revision

    def _conflicting(target: StoredConfiguration) -> None:
        target.home.home_name = "Tweede"

    with pytest.raises(RevisionConflictError) as err:
        await store.async_update(_conflicting, expected_revision=current - 1)

    assert err.value.expected == current - 1
    assert err.value.actual == current
    assert config.home.home_name == "Eerste"
    assert config.revision == current


# --- Logbook ----------------------------------------------------------------


async def test_logs_are_trimmed_to_the_maximum(hass: HomeAssistant) -> None:
    """The logbook never grows past 200 entries and keeps the newest."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    for index in range(MAX_LOG_ENTRIES + 50):
        await store.async_add_log_entry(
            LOG_EVENT_CONFIG_CHANGED,
            f"Wijziging {index}",
            "Configuratie aangepast",
            subject=f"subject-{index}",
        )

    assert len(config.logs) == MAX_LOG_ENTRIES
    # Newest first, so the very last event written is at index 0.
    assert config.logs[0].title == f"Wijziging {MAX_LOG_ENTRIES + 49}"
    assert config.logs[-1].title == f"Wijziging {50}"


async def test_repeated_identical_events_bump_the_count(hass: HomeAssistant) -> None:
    """Anti-spam: the same event about the same subject collapses into one."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    for _ in range(3):
        await store.async_add_log_entry(
            LOG_EVENT_ADVICE_RECALCULATED,
            "Advies herberekend",
            "Er is een nieuwe berekening uitgevoerd",
            subject="coach",
        )

    assert len(config.logs) == 1
    assert config.logs[0].count == 3


async def test_a_logbook_entry_does_not_change_the_revision(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A background event is persisted but never expires a frontend edit."""
    store = ConfigurationStore(hass)
    config = await store.async_load()
    revision_before = config.revision

    await store.async_add_log_entry(
        LOG_EVENT_ADVICE_RECALCULATED, "Advies herberekend", "", subject="coach"
    )

    assert len(config.logs) == 1
    assert config.revision == revision_before
    # The entry did reach the storage file.
    assert len(hass_storage[STORAGE_KEY]["data"]["logs"]) == 1
    assert hass_storage[STORAGE_KEY]["data"]["revision"] == revision_before


async def test_a_different_subject_creates_a_new_entry(hass: HomeAssistant) -> None:
    """Only identical consecutive events collapse; other subjects do not."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    await store.async_add_log_entry(
        LOG_EVENT_CONFIG_CHANGED, "Bron gewijzigd", "", subject="source-1"
    )
    await store.async_add_log_entry(
        LOG_EVENT_CONFIG_CHANGED, "Bron gewijzigd", "", subject="source-2"
    )

    assert len(config.logs) == 2
    assert [entry.count for entry in config.logs] == [1, 1]


async def test_events_outside_the_dedupe_window_are_logged_again(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """After the anti-spam window an identical event is a new line."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    await store.async_add_log_entry(
        LOG_EVENT_ADVICE_RECALCULATED, "Advies herberekend", "", subject="coach"
    )
    freezer.tick(timedelta(minutes=LOG_DEDUPE_WINDOW_MINUTES + 1))
    await store.async_add_log_entry(
        LOG_EVENT_ADVICE_RECALCULATED, "Advies herberekend", "", subject="coach"
    )

    assert len(config.logs) == 2
    assert [entry.count for entry in config.logs] == [1, 1]


# --- Write amplification ----------------------------------------------------
#
# Every one of these counts calls to Store.async_save, which is what actually
# rewrites .storage/domotiapp_energy.config. Collapsing a repeat into a counter
# used to write the whole file anyway, and the engine collapses the same event
# on every recalculation — with a real meter reporting every second that was a
# write every couple of seconds, all day long, invisible because the file never
# grows. These tests are the guard: they fail loudly if the writes come back.


@contextmanager
def _count_writes() -> Generator[list[int]]:
    """Count the disk writes performed while inside the block."""
    writes = [0]
    original = DomotiAppEnergyStore.async_save

    async def _counting(self: DomotiAppEnergyStore, data: dict[str, Any]) -> None:
        writes[0] += 1
        await original(self, data)

    with patch.object(DomotiAppEnergyStore, "async_save", _counting):
        yield writes


async def test_repeated_events_are_written_once(hass: HomeAssistant) -> None:
    """Fifty identical events cost one write, not fifty."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    with _count_writes() as writes:
        for _ in range(50):
            await store.async_add_log_entry(
                LOG_EVENT_SOLAR_SURPLUS_DETECTED,
                "Zonneoverschot beschikbaar",
                "Er is 2000 W zonneoverschot beschikbaar.",
                subject="metrics:solar_surplus",
            )

    # Only the first event is a new line; the other 49 are a counter in memory.
    assert writes[0] == 1
    assert len(config.logs) == 1
    assert config.logs[0].count == 50


async def test_a_pending_counter_reaches_the_disk(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The counter held in memory is flushed once the interval has passed."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    with _count_writes() as writes:
        for _ in range(10):
            await store.async_add_log_entry(
                LOG_EVENT_SOLAR_SURPLUS_DETECTED, "Zonneoverschot", "", subject="solar"
            )
        assert writes[0] == 1

        freezer.tick(timedelta(seconds=LOG_FLUSH_INTERVAL_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # One flush for everything that accumulated, and no timer left running.
        assert writes[0] == 2

        freezer.tick(timedelta(seconds=LOG_FLUSH_INTERVAL_SECONDS + 1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert writes[0] == 2

    assert config.logs[0].count == 10


async def test_a_configuration_write_carries_the_pending_counter(
    hass: HomeAssistant,
) -> None:
    """A normal save persists the counter too, so no extra flush is needed."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    with _count_writes() as writes:
        for _ in range(5):
            await store.async_add_log_entry(
                LOG_EVENT_SOLAR_SURPLUS_DETECTED, "Zonneoverschot", "", subject="solar"
            )

        def _rename(stored: StoredConfiguration) -> None:
            stored.home.home_name = "Nieuwe naam"

        await store.async_update(_rename)
        # The insert, plus the configuration change. The pending counter rode
        # along with the second one rather than paying for a third write.
        assert writes[0] == 2
        await store.async_flush_logs()
        assert writes[0] == 2

    assert config.logs[0].count == 5


async def test_flushing_writes_a_pending_counter_before_unload(
    hass: HomeAssistant,
) -> None:
    """Unloading inside the interval still gets the counter onto the disk."""
    store = ConfigurationStore(hass)
    await store.async_load()

    with _count_writes() as writes:
        for _ in range(3):
            await store.async_add_log_entry(
                LOG_EVENT_SOLAR_SURPLUS_DETECTED, "Zonneoverschot", "", subject="solar"
            )
        await store.async_flush_logs()
        assert writes[0] == 2
        # Nothing pending any more, so a second flush is free.
        await store.async_flush_logs()
        assert writes[0] == 2


async def test_two_alternating_findings_still_collapse(hass: HomeAssistant) -> None:
    """The engine reports several situations per pass, and they interleave.

    On a sunny afternoon under load the coordinator writes a peak risk and a
    solar surplus in the same recalculation. Collapsing only into the newest
    line meant each one found the *other* at the front and started a new one —
    two writes per recalculation, from the rule that exists to prevent exactly
    that. Found by watching the file on a running instance, not by a test that
    only ever sent one kind of event.
    """
    store = ConfigurationStore(hass)
    config = await store.async_load()

    with _count_writes() as writes:
        for _ in range(20):
            await store.async_add_log_entry(
                LOG_EVENT_PEAK_RISK_DETECTED, "Piekbelasting", "", subject="peak"
            )
            await store.async_add_log_entry(
                LOG_EVENT_SOLAR_SURPLUS_DETECTED, "Zonneoverschot", "", subject="solar"
            )

    # One write per subject, for the line each of them started.
    assert writes[0] == 2
    assert len(config.logs) == 2
    assert sorted(entry.count for entry in config.logs) == [20, 20]
    # Still ordered newest-first, so trimming keeps dropping the oldest.
    assert config.logs[0].timestamp >= config.logs[1].timestamp


async def test_an_event_outside_the_window_is_not_collapsed_into(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Searching the list does not reach past the anti-spam window."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    await store.async_add_log_entry(
        LOG_EVENT_PEAK_RISK_DETECTED, "Piekbelasting", "", subject="peak"
    )
    freezer.tick(timedelta(minutes=LOG_DEDUPE_WINDOW_MINUTES + 1))
    await store.async_add_log_entry(
        LOG_EVENT_PEAK_RISK_DETECTED, "Piekbelasting", "", subject="peak"
    )

    assert len(config.logs) == 2
    assert [entry.count for entry in config.logs] == [1, 1]


async def test_a_new_log_line_is_written_immediately(hass: HomeAssistant) -> None:
    """Different events are each worth a write; only repeats are held back."""
    store = ConfigurationStore(hass)

    await store.async_load()
    with _count_writes() as writes:
        await store.async_add_log_entry(
            LOG_EVENT_SOLAR_SURPLUS_DETECTED, "Zonneoverschot", "", subject="solar"
        )
        await store.async_add_log_entry(
            LOG_EVENT_PEAK_RISK_DETECTED, "Piekbelasting", "", subject="peak"
        )
        # Back to a subject that already has a line: a counter, not a write.
        await store.async_add_log_entry(
            LOG_EVENT_SOLAR_SURPLUS_DETECTED, "Zonneoverschot", "", subject="solar"
        )

    assert writes[0] == 2


async def test_clearing_the_logbook(hass: HomeAssistant) -> None:
    """Clearing empties the logbook without consuming a revision number."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    await store.async_add_log_entry(
        LOG_EVENT_CONFIG_CHANGED, "Wijziging", "", severity=SEVERITY_WARNING
    )
    revision_before = config.revision

    await store.async_clear_logs()

    assert config.logs == []
    # The logbook is not part of what expected_revision guards (SPEC.md §14).
    assert config.revision == revision_before


async def test_log_entries_are_serialisable(hass: HomeAssistant) -> None:
    """A stored log entry keeps only the documented fields."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    await store.async_add_log_entry(
        LOG_EVENT_CONFIG_CHANGED, "Titel", "Omschrijving", subject="source-1"
    )

    assert set(config.logs[0].to_dict()) == {
        "id",
        "timestamp",
        "event_type",
        "title",
        "message",
        "severity",
        "subject",
        "count",
    }


# --- Defensive loading ------------------------------------------------------


async def test_unknown_and_invalid_fields_fall_back_to_defaults(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A damaged storage file still yields a usable configuration."""
    hass_storage[STORAGE_KEY] = _stored(
        {
            "schema_version": 1,
            "revision": 7,
            "unknown_top_level_key": "ignored",
            "home": {
                "home_name": "Woning",
                "phases": 99,
                "main_fuse_a": "not a number",
                "peak_warning_percent": 500,
                "contract_type": "barter",
                "unknown_key": True,
            },
            "sources": [
                {
                    "id": "source-1",
                    "type": SOURCE_TYPE_GRID_METER,
                    "unit": "furlongs",
                    "scale_factor": -5,
                    "value_source": "telepathy",
                    "meter_mode": "guess",
                },
                "this is not a mapping",
            ],
            "devices": [
                {"id": "device-1", "device_type": DEVICE_TYPE_DISHWASHER, "priority": 7}
            ],
            "preferences": {"max_advice_count": 99, "prefer_solar": "yes"},
            "logs": [{"severity": "explosive", "count": -3}],
        }
    )

    config = await ConfigurationStore(hass).async_load()

    # Known-good values survive.
    assert config.revision == 7
    assert config.home.home_name == "Woning"
    # Invalid values fall back to the documented defaults.
    assert config.home.phases == DEFAULT_PHASES
    assert config.home.main_fuse_a is None
    assert config.home.peak_warning_percent == 100
    assert config.home.contract_type == DEFAULT_CONTRACT_TYPE
    # Entries that are not mappings are dropped, the rest is repaired.
    assert len(config.sources) == 1
    assert config.sources[0].id == "source-1"
    assert config.sources[0].binding.unit == UNIT_NONE
    assert config.sources[0].binding.scale_factor == DEFAULT_SCALE_FACTOR
    assert config.sources[0].binding.value_source == VALUE_SOURCE_STATE
    # Never guessed: an unusable meter mode stays unset (SPEC.md §8).
    assert config.sources[0].meter_mode is None
    # A valid type is untouched, so the row stays usable.
    assert config.sources[0].type == SOURCE_TYPE_GRID_METER
    assert config.sources[0].invalid_reason is None
    assert config.devices[0].priority == DEFAULT_PRIORITY
    assert config.preferences.max_advice_count == MAX_ADVICE_COUNT
    assert config.preferences.prefer_solar is True
    assert config.logs[0].severity == SEVERITY_INFO
    assert config.logs[0].count == 1


async def test_empty_payload_falls_back_to_defaults(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """An empty stored payload behaves like a fresh install."""
    hass_storage[STORAGE_KEY] = _stored({})

    config = await ConfigurationStore(hass).async_load()

    assert config.home.home_name == DEFAULT_HOME_NAME
    assert config.revision == INITIAL_REVISION


def test_from_dict_ignores_unknown_keys_without_raising() -> None:
    """from_dict() never raises on unexpected input (SPEC.md §12)."""
    config = StoredConfiguration.from_dict(
        {"sources": "not a list", "devices": None, "logs": 42, "home": "nonsense"}
    )

    assert config.sources == []
    assert config.devices == []
    assert config.logs == []
    assert config.home.home_name == DEFAULT_HOME_NAME


def test_from_dict_of_none_yields_defaults() -> None:
    """A missing payload behaves exactly like an empty one."""
    assert StoredConfiguration.from_dict(None).home.home_name == DEFAULT_HOME_NAME


def test_a_store_written_before_round_1_loads_unchanged() -> None:
    """The two removed dead fields need no migration (SPEC.md §33.5).

    ``default_strategy`` and ``respect_max_grid_load`` were stored, validated
    and rendered, and read by nothing. They are simply gone; ``from_dict``
    ignores keys it does not know, so an existing customer's file loads with
    everything around them intact and nothing has to be re-entered.
    """
    config = StoredConfiguration.from_dict(
        {
            "home": {
                "home_name": "Kerkstraat 12",
                "main_fuse_a": 40,
                "default_strategy": "max_self_consumption",
            },
            "preferences": {
                "quiet_hours_start": "23:00",
                "respect_max_grid_load": False,
            },
        }
    )

    assert config.home.home_name == "Kerkstraat 12"
    assert config.home.main_fuse_a == 40
    assert config.preferences.quiet_hours_start == "23:00"
    assert not hasattr(config.home, "default_strategy")
    assert not hasattr(config.preferences, "respect_max_grid_load")
    # And they do not come back out either, so the next write drops them.
    assert "default_strategy" not in config.home.to_dict()
    assert "respect_max_grid_load" not in config.preferences.to_dict()


# --- Model behaviour --------------------------------------------------------


def test_energy_source_round_trip() -> None:
    """A source keeps its binding fields flat in the stored shape."""
    source = EnergySource.from_dict(
        {
            "id": "source-1",
            "name": "Omvormer",
            "type": "solar",
            "entity_id": "sensor.pv_power",
            "value_source": VALUE_SOURCE_ATTRIBUTE,
            "attribute_name": "current_power",
            "unit": UNIT_KW,
            "scale_factor": 2.0,
            "invert_value": True,
        }
    )

    restored = EnergySource.from_dict(source.to_dict())

    assert restored.binding.entity_id == "sensor.pv_power"
    assert restored.binding.value_source == VALUE_SOURCE_ATTRIBUTE
    assert restored.binding.attribute_name == "current_power"
    assert restored.binding.unit == UNIT_KW
    assert restored.binding.scale_factor == 2.0
    assert restored.binding.invert_value is True


def test_grid_meter_import_and_export_bindings_inherit_the_unit() -> None:
    """Separate import/export entities are read with the same rules."""
    source = EnergySource.from_dict(
        {
            "id": "source-1",
            "type": SOURCE_TYPE_GRID_METER,
            "unit": UNIT_KW,
            "scale_factor": 3.0,
            "meter_mode": "separate_import_export",
            "import_entity_id": "sensor.import",
            "export_entity_id": "sensor.export",
        }
    )

    assert source.import_binding.entity_id == "sensor.import"
    assert source.import_binding.unit == UNIT_KW
    assert source.import_binding.scale_factor == 3.0
    assert source.export_binding.entity_id == "sensor.export"


def test_device_defaults_depend_on_the_device_type() -> None:
    """is_noisy and is_flexible follow the type defaults from SPEC.md §8."""
    dishwasher = DeviceProfile.from_dict(
        {"id": "d1", "device_type": DEVICE_TYPE_DISHWASHER}
    )
    heat_pump = DeviceProfile.from_dict(
        {"id": "d2", "device_type": DEVICE_TYPE_HEAT_PUMP}
    )

    assert dishwasher.is_noisy is True
    assert dishwasher.is_flexible is True
    assert heat_pump.is_noisy is False
    assert heat_pump.is_flexible is False
    assert dishwasher.priority == DEFAULT_PRIORITY


def test_type_defaults_also_apply_to_a_directly_constructed_device() -> None:
    """The rule lives in __post_init__, not only in from_dict.

    A heat pump built by hand must not come out flexible: the engine would
    then offer to move something that cannot be moved.
    """
    dishwasher = DeviceProfile(id="d1", device_type=DEVICE_TYPE_DISHWASHER)
    heat_pump = DeviceProfile(id="d2", device_type=DEVICE_TYPE_HEAT_PUMP)

    assert dishwasher.is_noisy is True
    assert dishwasher.is_flexible is True
    assert heat_pump.is_noisy is False
    assert heat_pump.is_flexible is False


def test_an_explicit_flag_survives_the_type_default() -> None:
    """A choice the installer made is never overwritten by the type default."""
    quiet_dishwasher = DeviceProfile(
        id="d1", device_type=DEVICE_TYPE_DISHWASHER, is_noisy=False
    )
    flexible_heat_pump = DeviceProfile.from_dict(
        {"id": "d2", "device_type": DEVICE_TYPE_HEAT_PUMP, "is_flexible": True}
    )

    assert quiet_dishwasher.is_noisy is False
    assert flexible_heat_pump.is_flexible is True


def test_the_type_default_survives_a_round_trip() -> None:
    """Resolved flags are written out as real booleans, never as the marker."""
    heat_pump = DeviceProfile(id="d2", device_type=DEVICE_TYPE_HEAT_PUMP)

    stored = heat_pump.to_dict()

    assert stored["is_flexible"] is False
    assert DeviceProfile.from_dict(stored).is_flexible is False


def test_device_entity_links_are_omitted_when_unset() -> None:
    """An unset entity link is absent, never an empty string (SPEC.md §8)."""
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "device_type": DEVICE_TYPE_DISHWASHER,
            "power_entity": "sensor.power",
            "status_entity": "",
        }
    )

    stored = device.to_dict()

    assert stored["power_entity"] == "sensor.power"
    assert "status_entity" not in stored
    assert "temperature_entity" not in stored


def test_device_times_are_normalised() -> None:
    """The time selector's "HH:MM:SS" is stored as "HH:MM"."""
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "device_type": DEVICE_TYPE_DISHWASHER,
            "ready_from": "07:30:00",
            "ready_before": "23:00",
        }
    )

    assert device.ready_from == "07:30"
    assert device.ready_before == "23:00"
    assert device.has_complete_ready_window is True


# --- Migrating the old start window (SPEC.md §32.4) --------------------------


def test_an_old_start_window_becomes_a_ready_window() -> None:
    """A stored device from before 0.2 keeps meaning what it meant.

    `earliest_start` said "do not start before"; adding the duration makes that
    exactly "do not be finished before", which is what `ready_from` means. The
    translation happens on reading, so `async_load` still writes nothing
    (SPEC.md §13).
    """
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "device_type": DEVICE_TYPE_DISHWASHER,
            "earliest_start": "22:00",
            "latest_finish": "06:00",
            "duration_minutes": 180,
        }
    )

    # 22:00 plus three hours is 01:00 — the earliest it can be *finished*.
    assert device.ready_from == "01:00"
    assert device.ready_before == "06:00"
    # And the start window derived back from it is the one that was stored.
    assert device.earliest_start == "22:00"


def test_an_old_window_without_a_duration_carries_over_unchanged() -> None:
    """Nothing to add, so the times stand as they are — and behave as before."""
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "device_type": DEVICE_TYPE_DISHWASHER,
            "earliest_start": "09:00",
            "latest_finish": "17:00",
        }
    )

    assert device.ready_from == "09:00"
    assert device.ready_before == "17:00"
    # Without a duration the derived start degrades to the ready time itself,
    # which is exactly what the old start window did.
    assert device.earliest_start == "09:00"
    assert device.latest_start is None


def test_a_migrated_window_crosses_midnight_correctly() -> None:
    """23:00 plus a three-hour programme is 02:00, not 26:00."""
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "device_type": DEVICE_TYPE_DISHWASHER,
            "earliest_start": "23:00",
            "duration_minutes": 180,
        }
    )

    assert device.ready_from == "02:00"


def test_an_already_migrated_device_is_left_alone() -> None:
    """A configuration that has been translated once is never touched again.

    Both sets of keys can coexist in a file that was written by a new release
    and then read by one — the new fields win, and the old ones are ignored
    rather than re-applied on top.
    """
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "device_type": DEVICE_TYPE_DISHWASHER,
            "ready_from": "01:00",
            "ready_before": "06:00",
            "earliest_start": "22:00",
            "latest_finish": "06:00",
            "duration_minutes": 180,
        }
    )

    assert device.ready_from == "01:00"
    assert device.ready_before == "06:00"


def test_the_old_keys_disappear_from_storage() -> None:
    """Once read, a device is written back in the new shape only."""
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "device_type": DEVICE_TYPE_DISHWASHER,
            "earliest_start": "09:00",
            "latest_finish": "17:00",
        }
    )

    stored = device.to_dict()

    assert stored["ready_from"] == "09:00"
    assert stored["ready_before"] == "17:00"
    assert "earliest_start" not in stored
    assert "latest_finish" not in stored


def test_device_days_of_week_default_to_every_day() -> None:
    """An absent or unusable day list means the device may run any day."""
    every_day = [0, 1, 2, 3, 4, 5, 6]

    def _device(**extra: Any) -> DeviceProfile:
        return DeviceProfile.from_dict(
            {"id": "d1", "device_type": DEVICE_TYPE_DISHWASHER, **extra}
        )

    assert _device().days_of_week == every_day
    assert _device(days_of_week=["nonsense", 9, -1]).days_of_week == every_day
    assert _device(days_of_week=[5, 5, 0]).days_of_week == [0, 5]


def test_control_mode_is_capped_at_advice_only() -> None:
    """In 0.1.0 nothing above advice_only is ever applied (SPEC.md §2.2)."""
    automatic = DeviceProfile.from_dict(
        {"id": "d1", "device_type": DEVICE_TYPE_DISHWASHER, "control_mode": "automatic"}
    )
    monitor = DeviceProfile.from_dict(
        {
            "id": "d2",
            "device_type": DEVICE_TYPE_DISHWASHER,
            "control_mode": "monitor_only",
        }
    )

    assert automatic.control_mode == "automatic"
    assert automatic.effective_control_mode == CONTROL_ADVICE_ONLY
    assert monitor.effective_control_mode == CONTROL_MONITOR_ONLY


def test_home_control_level_is_forced_to_advice_only() -> None:
    """A stored control level from a future release is ignored in 0.1.0."""
    home = HomeProfile.from_dict({"control_level": "automatic"})

    assert home.control_level == CONTROL_ADVICE_ONLY


def test_theoretical_maximum_grid_power() -> None:
    """The hint is phases x 230 V x fuse, and None without a fuse."""
    home = HomeProfile.from_dict({"phases": PHASES_THREE, "main_fuse_a": 25})

    assert home.theoretical_max_grid_power_w == PHASES_THREE * (
        NOMINAL_VOLTAGE_PER_PHASE * 25
    )
    assert HomeProfile.from_dict({}).theoretical_max_grid_power_w is None


# --- Unrecognised types are quarantined, never degraded ---------------------


def test_unknown_source_type_is_kept_and_quarantined() -> None:
    """An unknown source type is never replaced by a known one (SPEC.md §12)."""
    source = EnergySource.from_dict(
        {
            "id": "source-1",
            "name": "Slimme meter",
            "type": "grid_metre",
            "enabled": True,
        }
    )

    # The stored value survives, so the installer can see what went wrong.
    assert source.type == "grid_metre"
    assert source.enabled is False
    assert source.invalid_reason == INVALID_REASON_UNKNOWN_TYPE
    assert source.is_usable is False
    # And it round-trips: reloading does not repair or degrade it either.
    assert EnergySource.from_dict(source.to_dict()).type == "grid_metre"


def test_missing_source_type_is_also_quarantined() -> None:
    """A source without any type is unusable rather than assumed."""
    source = EnergySource.from_dict({"id": "source-1"})

    assert source.type == ""
    assert source.enabled is False
    assert source.invalid_reason == INVALID_REASON_UNKNOWN_TYPE
    assert source.is_usable is False


def test_unknown_device_type_is_kept_and_quarantined() -> None:
    """An unknown device type gets the same treatment as a source."""
    device = DeviceProfile.from_dict(
        {"id": "device-1", "name": "Warmtepomp", "device_type": "heatpump"}
    )

    assert device.device_type == "heatpump"
    assert device.enabled is False
    assert device.invalid_reason == INVALID_REASON_UNKNOWN_TYPE
    assert device.is_usable is False


def test_a_valid_row_is_not_marked_invalid() -> None:
    """The quarantine only ever applies to unrecognised types."""
    source = EnergySource.from_dict({"id": "s1", "type": SOURCE_TYPE_GRID_METER})
    device = DeviceProfile.from_dict(
        {"id": "d1", "device_type": DEVICE_TYPE_DISHWASHER}
    )

    assert source.invalid_reason is None
    assert source.is_usable is True
    assert device.invalid_reason is None
    assert device.is_usable is True
    # A row the installer disabled on purpose is valid but not usable.
    disabled = EnergySource.from_dict(
        {"id": "s2", "type": SOURCE_TYPE_GRID_METER, "enabled": False}
    )
    assert disabled.invalid_reason is None
    assert disabled.is_usable is False


def _broken_configuration() -> dict[str, Any]:
    """Return a stored payload with one broken source and one broken device."""
    return {
        "revision": 3,
        "sources": [
            {"id": "source-1", "name": "Slimme meter", "type": "grid_metre"},
            {"id": "source-2", "name": "Zon", "type": "solar"},
        ],
        "devices": [
            {"id": "device-1", "name": "Warmtepomp", "device_type": "heatpump"}
        ],
    }


async def test_loading_a_broken_row_does_not_change_the_revision(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Loading is read-only, even when rows have to be quarantined.

    The revision only ever moves through an explicit user action, so a restart
    with a damaged configuration must not expire the frontend's
    expected_revision or rewrite the storage file.
    """
    hass_storage[STORAGE_KEY] = _stored(_broken_configuration())
    stored_before = deepcopy(hass_storage[STORAGE_KEY])

    config = await ConfigurationStore(hass).async_load()

    # The rows are quarantined in memory...
    assert [source.id for source in config.invalid_sources] == ["source-1"]
    assert [device.id for device in config.invalid_devices] == ["device-1"]
    # ...while the revision and the file on disk are untouched.
    assert config.revision == 3
    assert config.logs == []
    assert hass_storage[STORAGE_KEY] == stored_before


async def test_a_clean_configuration_is_loaded_without_side_effects(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A configuration without unknown types is loaded without any write."""
    hass_storage[STORAGE_KEY] = _stored(
        {
            "revision": 3,
            "sources": [{"id": "source-1", "type": SOURCE_TYPE_GRID_METER}],
        }
    )
    stored_before = deepcopy(hass_storage[STORAGE_KEY])

    config = await ConfigurationStore(hass).async_load()

    assert config.logs == []
    assert config.revision == 3
    assert hass_storage[STORAGE_KEY] == stored_before


async def test_invalid_rows_are_reported_when_the_engine_uses_them(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """The quarantine is logged where it becomes functionally relevant."""
    hass_storage[STORAGE_KEY] = _stored(_broken_configuration())
    store = ConfigurationStore(hass)
    config = await store.async_load()

    await store.async_report_invalid_rows()

    logged = [
        entry
        for entry in config.logs
        if entry.event_type == LOG_EVENT_INVALID_CONFIGURATION
    ]
    assert len(logged) == 2
    assert {entry.subject for entry in logged} == {"source-1", "device-1"}
    assert all(entry.severity == SEVERITY_WARNING for entry in logged)
    # A logbook entry is not a configuration change.
    assert config.revision == 3


async def test_repeated_reports_do_not_repeat_the_log_line(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Anti-spam: a recurring recalculation reports each row only once."""
    hass_storage[STORAGE_KEY] = _stored(_broken_configuration())
    store = ConfigurationStore(hass)
    config = await store.async_load()

    for _ in range(5):
        await store.async_report_invalid_rows()

    assert len(config.logs) == 2
    assert [entry.count for entry in config.logs] == [1, 1]


async def test_a_row_that_breaks_again_is_reported_again(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Repairing and re-breaking a row produces a fresh report."""
    hass_storage[STORAGE_KEY] = _stored(_broken_configuration())
    store = ConfigurationStore(hass)
    config = await store.async_load()

    await store.async_report_invalid_rows()
    assert len(config.logs) == 2

    def _repair(target: StoredConfiguration) -> None:
        target.sources[0].type = SOURCE_TYPE_GRID_METER

    def _break(target: StoredConfiguration) -> None:
        target.sources[0].type = "grid_metre"

    await store.async_update(_repair)
    await store.async_report_invalid_rows()
    await store.async_update(_break)
    await store.async_report_invalid_rows()

    reported = [
        entry
        for entry in config.logs
        if entry.event_type == LOG_EVENT_INVALID_CONFIGURATION
        and entry.subject == "source-1"
    ]
    assert sum(entry.count for entry in reported) == 2


async def test_duplicate_exclusive_sources_are_reported(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Two enabled grid meters are a configuration problem worth logging."""
    hass_storage[STORAGE_KEY] = _stored(
        {
            "revision": 3,
            "sources": [
                {"id": "meter-a", "name": "Meter A", "type": SOURCE_TYPE_GRID_METER},
                {"id": "meter-b", "name": "Meter B", "type": SOURCE_TYPE_GRID_METER},
            ],
        }
    )
    store = ConfigurationStore(hass)
    config = await store.async_load()

    await store.async_report_invalid_rows()

    logged = [
        entry
        for entry in config.logs
        if entry.event_type == LOG_EVENT_INVALID_CONFIGURATION
    ]
    # One line about the type, not one per row.
    assert len(logged) == 1
    assert logged[0].subject == f"{DUPLICATE_SUBJECT_PREFIX}{SOURCE_TYPE_GRID_METER}"
    assert logged[0].severity == SEVERITY_WARNING
    assert config.revision == 3


async def test_repeated_duplicate_reports_are_not_repeated(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """The duplicate report uses the same anti-spam route as the others."""
    hass_storage[STORAGE_KEY] = _stored(
        {
            "sources": [
                {"id": "meter-a", "type": SOURCE_TYPE_GRID_METER},
                {"id": "meter-b", "type": SOURCE_TYPE_GRID_METER},
            ]
        }
    )
    store = ConfigurationStore(hass)
    config = await store.async_load()

    for _ in range(5):
        await store.async_report_invalid_rows()

    assert len(config.logs) == 1
    assert config.logs[0].count == 1


async def test_resolving_a_duplicate_stops_the_reports(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Switching one off resolves it, and a relapse is reported afresh."""
    hass_storage[STORAGE_KEY] = _stored(
        {
            "sources": [
                {"id": "meter-a", "type": SOURCE_TYPE_GRID_METER},
                {"id": "meter-b", "type": SOURCE_TYPE_GRID_METER},
            ]
        }
    )
    store = ConfigurationStore(hass)
    config = await store.async_load()

    await store.async_report_invalid_rows()

    def _disable(target: StoredConfiguration) -> None:
        target.sources[1].enabled = False

    def _enable(target: StoredConfiguration) -> None:
        target.sources[1].enabled = True

    await store.async_update(_disable)
    await store.async_report_invalid_rows()
    await store.async_update(_enable)
    await store.async_report_invalid_rows()

    assert sum(entry.count for entry in config.logs) == 2


async def test_a_valid_configuration_reports_nothing(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Nothing is logged when there is nothing to quarantine."""
    hass_storage[STORAGE_KEY] = _stored(
        {"revision": 3, "sources": [{"id": "source-1", "type": SOURCE_TYPE_GRID_METER}]}
    )
    store = ConfigurationStore(hass)
    config = await store.async_load()

    await store.async_report_invalid_rows()

    assert config.logs == []
    assert config.revision == 3


# --- Failure paths ----------------------------------------------------------


async def test_unreadable_storage_file_falls_back_to_defaults(
    hass: HomeAssistant,
) -> None:
    """A storage file that cannot be parsed does not block startup."""
    store = ConfigurationStore(hass)

    with patch.object(
        DomotiAppEnergyStore, "async_load", side_effect=ValueError("corrupt json")
    ):
        config = await store.async_load()

    assert config.home.home_name == DEFAULT_HOME_NAME
    assert config.revision == INITIAL_REVISION


async def test_a_failed_write_rolls_back_the_revision(hass: HomeAssistant) -> None:
    """A write that fails must not consume a revision number."""
    store = ConfigurationStore(hass)
    config = await store.async_load()
    revision_before = config.revision

    def _rename(target: StoredConfiguration) -> None:
        target.home.home_name = "Woning"

    with (
        patch.object(
            DomotiAppEnergyStore, "async_save", side_effect=OSError("disk full")
        ),
        pytest.raises(StorageError),
    ):
        await store.async_update(_rename)

    assert config.revision == revision_before


# --- Runtime result models --------------------------------------------------


def test_energy_snapshot_round_trip() -> None:
    """A snapshot survives serialisation, including negative grid power."""
    snapshot = EnergySnapshot(
        grid_power_w=-1200.0,
        solar_power_w=3000.0,
        household_consumption_w=1800.0,
        battery_power_w=0.0,
        current_price_eur_kwh=0.21,
        invalid_source_ids=["source-9"],
        source_failures=[
            SourceFailure(
                source_id="source-9",
                entity_id="sensor.weg",
                reason_code="entity_unavailable",
            )
        ],
        reason_codes=["entity_unavailable"],
    )

    restored = EnergySnapshot.from_dict(snapshot.to_dict())

    assert restored.grid_power_w == -1200.0
    assert restored.solar_power_w == 3000.0
    assert restored.household_consumption_w == 1800.0
    assert restored.current_price_eur_kwh == 0.21
    assert restored.invalid_source_ids == ["source-9"]
    assert restored.reason_codes == ["entity_unavailable"]
    assert restored.timestamp == snapshot.timestamp
    assert restored.source_failures == snapshot.source_failures


def test_a_damaged_source_failure_degrades_to_empty_strings() -> None:
    """A failure record rebuilt from rubbish is usable, not an exception.

    ``unavailable`` in the payload is ignored on the way in: it is derived from
    the reason code, so a mapping that disagrees with its own code cannot smuggle
    the disagreement back in (SPEC.md §63.5).
    """
    restored = SourceFailure.from_dict({"source_id": 42, "unavailable": "misschien"})

    assert restored.source_id == ""
    assert restored.entity_id == ""
    assert restored.reason_code == ""
    assert restored.unavailable is False


def test_coach_result_round_trip() -> None:
    """The full coach result survives the trip to the frontend and back."""
    advice = AdviceItem(
        id="advice-1",
        title="Netbelasting hoog",
        message="Stel grootverbruikers uit.",
        severity=SEVERITY_WARNING,
        reason_code="high_grid_load",
        confidence="high",
        estimated_savings_eur=0.42,
        related_device_ids=["device-1"],
        measurements={"grid_power_w": 5200.0, "toelichting": "piek"},
    )
    result = CoachResult(
        primary_advice=advice,
        advice=[advice],
        metrics=EnergyMetrics(
            grid_power_w=5200.0,
            grid_load_percent=72.5,
            peak_risk=True,
            data_quality=DataQualityResult(
                score=60, completed_items=["home_profile_complete"]
            ),
            energy_score=48,
            score_components={"peak_component": 55.0},
        ),
        explanations={"why_advice": "Uitleg"},
        missing_data=["price_information_available"],
    )

    restored = CoachResult.from_dict(result.to_dict())

    assert restored.primary_advice is not None
    assert restored.primary_advice.reason_code == "high_grid_load"
    assert restored.primary_advice.estimated_savings_eur == 0.42
    # Measurements keep numbers as numbers and text as text.
    assert restored.primary_advice.measurements == {
        "grid_power_w": 5200.0,
        "toelichting": "piek",
    }
    assert len(restored.advice) == 1
    assert restored.metrics.peak_risk is True
    assert restored.metrics.energy_score == 48
    assert restored.metrics.grid_load_percent == 72.5
    assert restored.metrics.data_quality.score == 60
    assert restored.metrics.score_components == {"peak_component": 55.0}
    assert restored.explanations == {"why_advice": "Uitleg"}
    assert restored.missing_data == ["price_information_available"]
    assert restored.generated_at == result.generated_at


def test_coach_result_from_damaged_input() -> None:
    """Unusable coach data degrades instead of raising."""
    restored = CoachResult.from_dict(
        {
            "primary_advice": "not a mapping",
            "advice": [42, {"id": "a1", "severity": "explosive"}],
            "metrics": {"energy_score": 4000, "score_components": {"peak": "nonsense"}},
            "explanations": {"why_advice": "", "other": 5},
            "missing_data": [None, "price"],
        }
    )

    assert restored.primary_advice is None
    assert len(restored.advice) == 1
    assert restored.advice[0].severity == SEVERITY_INFO
    # Out of range, so no score at all rather than a wrong one.
    assert restored.metrics.energy_score is None
    assert restored.metrics.score_components == {}
    assert restored.explanations == {}
    assert restored.missing_data == ["price"]


# --- Migration --------------------------------------------------------------


async def test_migration_function_is_callable_and_keeps_data(
    hass: HomeAssistant,
) -> None:
    """The migration function exists and currently migrates identically."""
    store = DomotiAppEnergyStore(
        hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_MINOR_VERSION
    )

    migrated = await store._async_migrate_func(STORAGE_VERSION, 0, {"revision": 3})

    assert migrated == {"revision": 3}


async def test_migration_refuses_a_newer_schema(hass: HomeAssistant) -> None:
    """Data from a newer release is refused rather than silently reduced."""
    store = DomotiAppEnergyStore(
        hass, STORAGE_VERSION, STORAGE_KEY, minor_version=STORAGE_MINOR_VERSION
    )

    with pytest.raises(NotImplementedError):
        await store._async_migrate_func(STORAGE_VERSION + 1, 0, {"revision": 3})


async def test_loading_an_older_minor_version_migrates(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """An older minor version is migrated on load and fields are restored."""
    hass_storage[STORAGE_KEY] = _stored(
        {"revision": 4, "home": {"home_name": "Oud"}}, minor_version=0
    )

    config = await ConfigurationStore(hass).async_load()

    assert config.revision == 4
    assert config.home.home_name == "Oud"
    # Fields the old payload never had come back as defaults.
    assert config.preferences.max_advice_count == DEFAULT_MAX_ADVICE_COUNT
    assert config.home.contract_type == DEFAULT_CONTRACT_TYPE


async def test_timestamps_use_home_assistant_time(hass: HomeAssistant) -> None:
    """Log timestamps come from dt_util, never from datetime.now()."""
    store = ConfigurationStore(hass)
    config = await store.async_load()

    await store.async_add_log_entry(LOG_EVENT_CONFIG_CHANGED, "Titel", "")

    assert config.logs[0].timestamp.tzinfo is not None
    assert abs((dt_util.utcnow() - config.logs[0].timestamp).total_seconds()) < 5


# --- Capability, agreement and net metering (SPEC.md §12 and §16) -----------


def test_capabilities_and_the_agreement_survive_a_round_trip() -> None:
    """Both new fields make it through storage on a source and on a device."""
    source = EnergySource.from_dict(
        {
            "id": "s1",
            "type": SOURCE_TYPE_GRID_METER,
            "capabilities": [CAPABILITY_SET_POWER_LIMIT, CAPABILITY_READ],
            "control_forbidden": True,
            "control_forbidden_reason": "Afspraak met de klant.",
        }
    )
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "device_type": DEVICE_TYPE_DISHWASHER,
            "capabilities": [CAPABILITY_SWITCH],
        }
    )

    restored_source = EnergySource.from_dict(source.to_dict())
    restored_device = DeviceProfile.from_dict(device.to_dict())

    # Stored in the canonical order, not the order they were typed in.
    assert restored_source.capabilities == [CAPABILITY_READ, CAPABILITY_SET_POWER_LIMIT]
    assert restored_source.control_forbidden is True
    assert restored_source.control_forbidden_reason == "Afspraak met de klant."
    assert restored_device.capabilities == [CAPABILITY_SWITCH]
    assert restored_device.control_forbidden is False


def test_an_unrecognised_capability_is_dropped() -> None:
    """Unlike a type, a capability we do not know describes nothing usable.

    Keeping it would make the list claim something was checked when it was not.
    """
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "device_type": DEVICE_TYPE_DISHWASHER,
            "capabilities": [CAPABILITY_READ, "beam_me_up", 42],
        }
    )

    assert device.capabilities == [CAPABILITY_READ]


def test_a_row_without_capabilities_claims_nothing() -> None:
    """An empty list means nobody said, not that the hardware can do nothing."""
    device = DeviceProfile.from_dict(
        {"id": "d1", "device_type": DEVICE_TYPE_DISHWASHER}
    )

    assert device.capabilities == []


def test_net_metering_defaults_to_the_statutory_end_date() -> None:
    """A file written before the field existed gets the default."""
    home = HomeProfile.from_dict({"home_name": "Oude woning"})

    assert home.net_metering_until == date(2027, 1, 1)


def test_an_explicit_null_net_metering_date_survives_a_reload() -> None:
    """Clearing the field must not hand the home net metering back.

    from_dict cannot otherwise tell "key absent, use the default" from "the
    installer cleared this on purpose", and the second reading is the one that
    would silently undo their choice on the next load.
    """
    home = HomeProfile.from_dict({"net_metering_until": None})

    assert home.net_metering_until is None
    assert HomeProfile.from_dict(home.to_dict()).net_metering_until is None


def test_the_net_metering_date_round_trips_as_an_iso_string() -> None:
    """Stored as YYYY-MM-DD, for the same reason times are stored as HH:MM."""
    home = HomeProfile(net_metering_until=date(2028, 7, 1))

    assert home.to_dict()["net_metering_until"] == "2028-07-01"
    assert HomeProfile.from_dict(home.to_dict()).net_metering_until == date(2028, 7, 1)


def test_net_metering_is_active_up_to_but_not_on_the_end_date() -> None:
    """The regime ends *on* the date, so that day itself is already after."""
    home = HomeProfile(net_metering_until=date(2027, 1, 1))

    assert home.is_net_metering_active(date(2026, 12, 31)) is True
    assert home.is_net_metering_active(date(2027, 1, 1)) is False


def test_no_date_means_no_net_metering() -> None:
    """None is a real answer here, not a missing one."""
    home = HomeProfile(net_metering_until=None)

    assert home.is_net_metering_active(date(2020, 1, 1)) is False


def test_the_feed_in_cost_round_trips_and_refuses_a_negative() -> None:
    """A negative feed-in cost is not a cost; it falls back to unknown."""
    assert HomeProfile.from_dict(
        {"feed_in_cost_eur_kwh": 0.11}
    ).feed_in_cost_eur_kwh == (0.11)
    assert HomeProfile.from_dict({"feed_in_cost_eur_kwh": -1}).feed_in_cost_eur_kwh is (
        None
    )


# --- Price composition (SPEC.md §16 "Prijsopbouw") ---------------------------


def test_the_price_components_round_trip() -> None:
    """The three contract fields survive a write and a read."""
    home = HomeProfile(
        energy_tax_eur_kwh=0.1088,
        supplier_markup_eur_kwh=0.02,
        vat_percent=9.0,
    )

    restored = HomeProfile.from_dict(home.to_dict())

    assert restored.energy_tax_eur_kwh == 0.1088
    assert restored.supplier_markup_eur_kwh == 0.02
    assert restored.vat_percent == 9.0


def test_a_missing_vat_percentage_falls_back_to_the_default() -> None:
    """An older file predates the field and gets the Dutch rate."""
    assert HomeProfile.from_dict({}).vat_percent == DEFAULT_VAT_PERCENT


def test_a_negative_energy_tax_is_not_stored() -> None:
    """There is no negative tax per kWh, so it becomes "not entered"."""
    home = HomeProfile.from_dict({"energy_tax_eur_kwh": -0.1})

    assert home.energy_tax_eur_kwh is None


def test_a_negative_supplier_markup_is_kept() -> None:
    """A discount is a real contract term, unlike a negative tax."""
    home = HomeProfile.from_dict({"supplier_markup_eur_kwh": -0.01})

    assert home.supplier_markup_eur_kwh == -0.01


def test_the_price_basis_round_trips_on_a_source() -> None:
    """The basis is part of the stored source, never re-derived."""
    source = EnergySource(
        id="s1", type=SOURCE_TYPE_CURRENT_PRICE, price_basis=PRICE_BASIS_MARKET
    )

    assert source.to_dict()["price_basis"] == PRICE_BASIS_MARKET
    assert EnergySource.from_dict(source.to_dict()).price_basis == PRICE_BASIS_MARKET


def test_an_unrecognised_price_basis_becomes_none() -> None:
    """Unlike the source type, a bad basis is dropped rather than quarantined.

    The row still describes a price source; only the one field is unusable, and
    the calculator already treats "no basis" as "do not use this source".
    """
    source = EnergySource.from_dict({"type": "current_price", "price_basis": "spot"})

    assert source.price_basis is None
    assert source.invalid_reason is None


def test_the_all_in_price_of_an_all_in_source_is_the_price_itself() -> None:
    """No conversion, whatever the components say (SPEC.md §16)."""
    home = HomeProfile(energy_tax_eur_kwh=0.1088, supplier_markup_eur_kwh=0.02)

    assert home.all_in_price_eur_kwh(0.28, PRICE_BASIS_ALL_IN) == 0.28


def test_a_market_price_without_components_has_no_all_in_price() -> None:
    """Refused, not completed with zeroes."""
    assert HomeProfile().all_in_price_eur_kwh(0.08, PRICE_BASIS_MARKET) is None
    assert HomeProfile().has_price_components is False


def test_an_unstated_basis_has_no_all_in_price() -> None:
    """The strictness of the meter mode, applied to the price."""
    home = HomeProfile(energy_tax_eur_kwh=0.1088, supplier_markup_eur_kwh=0.02)

    assert home.all_in_price_eur_kwh(0.08, None) is None
