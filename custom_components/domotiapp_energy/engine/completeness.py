"""The weighted data completeness checklist (SPEC.md §16 "Datakwaliteit").

The checklist is deliberately transparent: six items, fixed weights, and a
score that is nothing more than the sum of the items that passed. An installer
who wants a higher number has to configure something real, and the panel can
name exactly what is still missing.

The check never reads entities itself. It judges a :class:`EnergySnapshot` the
calculator already produced, so "a grid source with a valid current value"
means the same thing here as it does in every calculation.
"""

from __future__ import annotations

from custom_components.domotiapp_energy.const import (
    COMPLETENESS_ITEM_DEVICE_PROFILE,
    COMPLETENESS_ITEM_GRID,
    COMPLETENESS_ITEM_HOME,
    COMPLETENESS_ITEM_PRICE,
    COMPLETENESS_ITEM_SOLAR,
    COMPLETENESS_ITEM_TIME_WINDOWS,
    COMPLETENESS_POINTS,
    CONTRACT_TYPE_DYNAMIC,
    CONTRACT_TYPES,
)
from custom_components.domotiapp_energy.models import (
    DataQualityResult,
    EnergySnapshot,
    StoredConfiguration,
)


def evaluate_completeness(
    config: StoredConfiguration, snapshot: EnergySnapshot
) -> DataQualityResult:
    """Score how complete and usable the configuration is, from 0 to 100.

    ``invalid_items`` holds the ids of rows the engine had to refuse — a source
    or device with an unrecognised type (SPEC.md §12), and a source whose
    entity could not be read. ``completed_items`` and ``missing_items`` hold
    checklist keys, not ids.
    """
    passed = {
        COMPLETENESS_ITEM_HOME: _home_profile_complete(config),
        COMPLETENESS_ITEM_GRID: snapshot.grid_power_w is not None,
        COMPLETENESS_ITEM_SOLAR: snapshot.solar_power_w is not None,
        COMPLETENESS_ITEM_PRICE: _price_information_available(config, snapshot),
        COMPLETENESS_ITEM_DEVICE_PROFILE: _has_complete_device_profile(config),
        COMPLETENESS_ITEM_TIME_WINDOWS: _flexible_devices_have_windows(config),
    }

    return DataQualityResult(
        score=sum(COMPLETENESS_POINTS[item] for item, ok in passed.items() if ok),
        completed_items=[item for item, ok in passed.items() if ok],
        missing_items=[item for item, ok in passed.items() if not ok],
        invalid_items=_invalid_items(config, snapshot),
    )


def _home_profile_complete(config: StoredConfiguration) -> bool:
    """Return whether phases, fuse, maximum power and contract are all set."""
    home = config.home
    return (
        home.main_fuse_a is not None
        # Zero is not a usable maximum: it makes the grid load unmeasurable.
        and home.max_grid_power_w is not None
        and home.max_grid_power_w > 0
        and home.contract_type in CONTRACT_TYPES
    )


def _price_information_available(
    config: StoredConfiguration, snapshot: EnergySnapshot
) -> bool:
    """Return whether a price is known, in the way this contract needs it."""
    if config.home.contract_type == CONTRACT_TYPE_DYNAMIC:
        return snapshot.current_price_eur_kwh is not None
    return config.home.fixed_import_price_eur_kwh is not None


def _has_complete_device_profile(config: StoredConfiguration) -> bool:
    """Return whether one usable device has both power and energy per cycle."""
    return any(
        device.nominal_power_w is not None and device.energy_per_cycle_kwh is not None
        for device in config.devices
        if device.is_usable
    )


def _flexible_devices_have_windows(config: StoredConfiguration) -> bool:
    """Return whether every usable flexible device has a time window.

    An empty configuration does not pass. Read literally the condition is
    vacuously true with zero devices, which would hand a fresh install ten
    points for something it has not configured.
    """
    flexible = [
        device for device in config.devices if device.is_usable and device.is_flexible
    ]
    return bool(flexible) and all(device.has_time_window for device in flexible)


def _invalid_items(config: StoredConfiguration, snapshot: EnergySnapshot) -> list[str]:
    """Return the ids of every row the engine had to refuse."""
    invalid = [source.id for source in config.invalid_sources]
    invalid.extend(
        source_id
        for source_id in snapshot.invalid_source_ids
        if source_id not in invalid
    )
    invalid.extend(device.id for device in config.invalid_devices)
    return invalid
