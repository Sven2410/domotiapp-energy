"""Tests for the models and the configuration store (SPEC.md §24)."""

from copy import deepcopy
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.domotiapp_energy.const import (
    CONTROL_ADVICE_ONLY,
    CONTROL_MONITOR_ONLY,
    DEFAULT_CONTRACT_TYPE,
    DEFAULT_HOME_NAME,
    DEFAULT_MAX_ADVICE_COUNT,
    DEFAULT_PEAK_WARNING_PERCENT,
    DEFAULT_PHASES,
    DEFAULT_PRIORITY,
    DEFAULT_SCALE_FACTOR,
    DEVICE_TYPE_DISHWASHER,
    DEVICE_TYPE_HEAT_PUMP,
    INITIAL_REVISION,
    INVALID_REASON_UNKNOWN_TYPE,
    LOG_DEDUPE_WINDOW_MINUTES,
    LOG_EVENT_ADVICE_RECALCULATED,
    LOG_EVENT_CONFIG_CHANGED,
    LOG_EVENT_INVALID_CONFIGURATION,
    MAX_ADVICE_COUNT,
    MAX_LOG_ENTRIES,
    METER_MODE_SINGLE_SIGNED,
    NOMINAL_VOLTAGE_PER_PHASE,
    PHASES_THREE,
    SCHEMA_VERSION,
    SEVERITY_INFO,
    SEVERITY_WARNING,
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
            "earliest_start": "07:30:00",
            "latest_finish": "23:00",
        }
    )

    assert device.earliest_start == "07:30"
    assert device.latest_finish == "23:00"
    assert device.has_time_window is True


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
        reason_codes=["invalid_entity_state"],
    )

    restored = EnergySnapshot.from_dict(snapshot.to_dict())

    assert restored.grid_power_w == -1200.0
    assert restored.solar_power_w == 3000.0
    assert restored.household_consumption_w == 1800.0
    assert restored.current_price_eur_kwh == 0.21
    assert restored.invalid_source_ids == ["source-9"]
    assert restored.reason_codes == ["invalid_entity_state"]
    assert restored.timestamp == snapshot.timestamp


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
