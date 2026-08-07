"""The weighted data completeness checklist (SPEC.md §16 "Datakwaliteit").

The checklist is deliberately transparent: six items, fixed weights, and a
score that is nothing more than the share of the applicable items that passed.
An installer who wants a higher number has to configure something real, and the
panel can name exactly what is still missing.

**Not every item applies to every home.** A home with solar panels and a smart
meter but no smart appliances used to be told that two of six items were
incomplete, and no amount of configuring could ever fix that — the two items
were about hardware the home does not have. So an item that cannot apply is
dropped from the sum *and* from the divisor, and 100 stays reachable.

What decides "applies" is never a guess. A source row is an explicit statement
about what the home has (Sven, 2026-08-06): somebody sat in the panel and said
"this home has solar". No row means no statement, so the item is not asked. The
same reading covers appliances. This is the opposite of discovery — nothing is
inferred from the entity register, only from what a person entered.

Three items always apply, because they are what the integration is for: the
home profile, the grid source and the price. Without those it measures nothing,
and a fresh install scoring 100 because it has nothing configured would be the
worse failure.

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
    SOURCE_TYPE_SOLAR,
)
from custom_components.domotiapp_energy.models import (
    DataQualityResult,
    DeviceProfile,
    EnergySnapshot,
    StoredConfiguration,
)


def evaluate_completeness(
    config: StoredConfiguration, snapshot: EnergySnapshot
) -> DataQualityResult:
    """Score how complete and usable the configuration is, from 0 to 100.

    ``invalid_items`` holds the ids of rows the engine had to refuse — a source
    or device with an unrecognised type (SPEC.md §12), and a source whose
    entity could not be read. ``completed_items``, ``missing_items`` and
    ``not_applicable_items`` hold checklist keys, not ids.
    """
    applicable = _applicable_items(config)
    passed = {
        COMPLETENESS_ITEM_HOME: _home_profile_complete(config),
        COMPLETENESS_ITEM_GRID: snapshot.grid_power_w is not None,
        COMPLETENESS_ITEM_SOLAR: snapshot.solar_power_w is not None,
        COMPLETENESS_ITEM_PRICE: _price_information_available(config, snapshot),
        COMPLETENESS_ITEM_DEVICE_PROFILE: _has_complete_device_profile(config),
        COMPLETENESS_ITEM_TIME_WINDOWS: _flexible_devices_have_windows(config),
    }

    return DataQualityResult(
        score=_score(passed, applicable),
        completed_items=[
            item for item, ok in passed.items() if ok and item in applicable
        ],
        missing_items=[
            item for item, ok in passed.items() if not ok and item in applicable
        ],
        not_applicable_items=[item for item in passed if item not in applicable],
        invalid_items=_invalid_items(config, snapshot),
    )


def _applicable_items(config: StoredConfiguration) -> set[str]:
    """Return the checklist items this home can actually be judged on.

    The three unconditional items are the integration's own subject matter; the
    other three each depend on the installer having said the home owns the
    thing. See the module docstring for why that is a statement and not a guess.
    """
    applicable = {
        COMPLETENESS_ITEM_HOME,
        COMPLETENESS_ITEM_GRID,
        COMPLETENESS_ITEM_PRICE,
    }

    # A disabled solar row still counts: the panels exist, they were switched
    # off in the panel. That the item then fails is correct — it is a gap the
    # installer created and can close.
    if any(source.type == SOURCE_TYPE_SOLAR for source in config.sources):
        applicable.add(COMPLETENESS_ITEM_SOLAR)

    usable = [device for device in config.devices if device.is_usable]
    if usable:
        applicable.add(COMPLETENESS_ITEM_DEVICE_PROFILE)
    if any(device.is_flexible for device in usable):
        applicable.add(COMPLETENESS_ITEM_TIME_WINDOWS)

    return applicable


def _score(passed: dict[str, bool], applicable: set[str]) -> int:
    """Return the share of the applicable weight that was earned, 0 to 100.

    With every item applicable the weights already sum to 100, so this returns
    exactly what the plain sum used to — a home that configured everything sees
    no change.
    """
    total = sum(COMPLETENESS_POINTS[item] for item in applicable)
    if not total:
        return 0
    earned = sum(
        COMPLETENESS_POINTS[item]
        for item, ok in passed.items()
        if ok and item in applicable
    )
    return round(100 * earned / total)


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


def is_complete_device_profile(device: DeviceProfile) -> bool:
    """Return whether this device is described well enough to act on.

    Public, and the only definition of "a complete device" in the project. The
    data quality checklist asks it of at least one device, the energy score's
    flexibility component asks it of the device it is about to award points for,
    and the Apparaten tab marks exactly these two fields. One predicate, so the
    three cannot drift apart.

    The time window is deliberately **not** part of it. A device without one is
    allowed at any hour, so it is *more* available for advice, not less;
    requiring a window here would punish the freer device and would count the
    checklist's own time-window item a second time (SPEC.md §16).
    """
    return (
        device.nominal_power_w is not None and device.energy_per_cycle_kwh is not None
    )


def _has_complete_device_profile(config: StoredConfiguration) -> bool:
    """Return whether one usable device has both power and energy per cycle."""
    return any(
        is_complete_device_profile(device)
        for device in config.devices
        if device.is_usable
    )


def _flexible_devices_have_windows(config: StoredConfiguration) -> bool:
    """Return whether every usable flexible device has a time window.

    A configuration with no flexible device does not pass, and no longer needs
    to: ``_applicable_items`` drops the item entirely in that case, so the
    vacuous truth never reaches the score. The guard stays because this
    predicate has to be right on its own terms.

    A window is not a required field on the device form — the helper there says
    both times may be left empty, and no asterisk contradicts it any more. It is
    a quality item: leaving it out costs points because the advice gets vaguer,
    not because the device is incomplete.
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
