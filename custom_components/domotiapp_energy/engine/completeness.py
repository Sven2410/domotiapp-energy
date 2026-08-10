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
    COMPLETENESS_UNCONDITIONAL_ITEMS,
    CONTRACT_TYPES,
    CONTROL_MONITOR_ONLY,
    DEVICE_TYPE_HOME_BATTERY,
    NEVER_ADVISED_DEVICE_TYPES,
    SOURCE_TYPE_HOME_BATTERY,
    SOURCE_TYPE_SOLAR,
)
from custom_components.domotiapp_energy.models import (
    DataQualityResult,
    DeviceProfile,
    EnergySnapshot,
    StoredConfiguration,
    import_price_now,
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

    **The two appliance items hang on `is_advisable`, not on "has a row"**
    (0.6.1). Both ask for something that only means anything when advice will
    follow: a complete profile so a saving can be named, a time window so the
    advice can be timed. An appliance the coach will never mention needs
    neither, and asking anyway is a requirement that does not apply, presented
    as a shortcoming — the fourth and fifth time this checklist did that.
    """
    applicable = set(COMPLETENESS_UNCONDITIONAL_ITEMS)

    # A disabled solar row still counts: the panels exist, they were switched
    # off in the panel. That the item then fails is correct — it is a gap the
    # installer created and can close.
    if any(source.type == SOURCE_TYPE_SOLAR for source in config.sources):
        applicable.add(COMPLETENESS_ITEM_SOLAR)

    if any(is_advisable(device) for device in config.devices):
        applicable.add(COMPLETENESS_ITEM_DEVICE_PROFILE)
        # The same condition on purpose. The window sharpens advice, so it is
        # asked of exactly the appliances advice can be about — no longer of a
        # flexible appliance the resident switched to "alleen meekijken".
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
    """Return whether a price per kWh is known at all.

    Not "in the way this contract needs it" any more: a price source works on a
    fixed contract too, and a home that has one is not missing price
    information because it also left the tariff field empty (SPEC.md §48).
    """
    price, _origin = import_price_now(config.home, snapshot)
    return price is not None


def is_complete_device_profile(device: DeviceProfile) -> bool:
    """Return whether this device is described well enough to act on.

    Public, and the only definition of "a complete device" in the project. The
    data quality checklist asks it of at least one device, `has_movable_load`
    asks it of the appliance that would switch the solar axis on, and the
    Apparaten tab marks exactly these two fields. One predicate, so the three
    cannot drift apart.

    The time window is deliberately **not** part of it. A device without one is
    allowed at any hour, so it is *more* available for advice, not less;
    requiring a window here would punish the freer device and would count the
    checklist's own time-window item a second time (SPEC.md §16).
    """
    return (
        device.nominal_power_w is not None and device.energy_per_cycle_kwh is not None
    )


def is_advisable(device: DeviceProfile) -> bool:
    """Return whether the coach can ever say anything about this appliance.

    **The one question the completeness of an appliance hangs on**, because the
    two fields the checklist asks for exist only to produce advice: the energy
    per cycle becomes the estimated saving, the nominal power decides whether a
    surplus can carry it. For an appliance nobody will be advised about,
    neither has a consumer, and demanding them is asking for a number that will
    never be read.

    Four conditions, on three different axes on purpose:

    - **usable** — enabled, and not quarantined for an unknown type.
    - **a type the coach can address** (`NEVER_ADVISED_DEVICE_TYPES`). A home
      battery has no moment anybody starts it, so there is no advice to give
      about it however the other flags are set.
    - **flexible** — a `generic_monitor` or a `heat_pump` says "measure this,
      do not move it" (`INFLEXIBLE_BY_DEFAULT_DEVICE_TYPES`). The installer can
      override it per appliance, which is why this reads the flag and not the
      type.
    - **not monitor_only** — the resident's own off switch (SPEC.md §33). It
      had no reader at all until 0.6.1: a dishwasher set to "alleen meekijken"
      was still advised on, so the product ignored an explicit instruction.

    Production finding, 2026-08-09: a tablet charger on a smart plug, added as
    `generic_monitor`, was told its energy per cycle was missing — a cycle
    being exactly what that type says it does not have. The battery is the same
    finding one type further along, and it needed its own axis: a battery is
    flexible, so the flag could not carry it (SPEC.md §38.2).
    """
    return (
        device.is_usable
        and device.device_type not in NEVER_ADVISED_DEVICE_TYPES
        and device.is_flexible
        and device.effective_control_mode != CONTROL_MONITOR_ONLY
    )


def has_movable_load(config: StoredConfiguration) -> bool:
    """Return whether this home can move consumption to another moment.

    The condition on the solar component (SPEC.md §35.4a). A home with panels
    but nothing to shift cannot raise its own self-consumption: 100% is
    physically out of reach, so scoring the axis is a discount and not a
    measurement — the same failure the fixed contract's permanent 50 was.

    Two ways to qualify, and they are genuinely different:

    - **a complete, flexible appliance** — somebody can start the dishwasher
      now instead of tonight. The completeness bar is the shared one, because
      an appliance without an energy per cycle gives the coach nothing to say
      about it, and an axis nobody can be advised on fails the advice rule.
    - **a home battery** — it moves energy without anybody touching anything.

    The battery counts as a *row*, enabled or not, the same reading the solar
    checklist item uses: a row is the installer's statement that the home has
    the thing. Switching it off in the panel does not remove the hardware, and
    the question here is what the home is capable of.

    Public for the reason `is_complete_device_profile` is: the score asks it,
    the panel explains it, and one predicate keeps them from disagreeing.
    """
    usable = [device for device in config.devices if device.is_usable]
    if any(
        device.is_flexible and is_complete_device_profile(device) for device in usable
    ):
        return True
    if any(device.device_type == DEVICE_TYPE_HOME_BATTERY for device in usable):
        return True
    return any(source.type == SOURCE_TYPE_HOME_BATTERY for source in config.sources)


def _has_complete_device_profile(config: StoredConfiguration) -> bool:
    """Return whether one advisable device has both power and energy per cycle."""
    return any(
        is_complete_device_profile(device)
        for device in config.devices
        if is_advisable(device)
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

    **One bound is enough**, which is `has_ready_window` and not
    `has_complete_ready_window`. A dishwasher with "klaar uiterlijk om 20:15"
    has told us when it must be finished; demanding a lower bound as well would
    punish the very configuration the ready window was built for. That is what
    happened when both questions shared one predicate.

    **"Any moment is fine" counts as an answer** (SPEC.md §52). The dryer of
    woning 2 is the case: *"hier zit geen haast op; als hij op woensdagmiddag
    draait wanneer de zon schijnt, is dat prima."* That is a complete answer,
    and until `runs_any_time` existed the form could not tell it apart from an
    unanswered question — so the resident lost ten points for having described
    his house correctly, and could only get them back by inventing a deadline.

    The check is `has_ready_window or runs_any_time` rather than a three-state
    field, and that choice carries its own weight: a device stored before this
    existed keeps passing on its window, and one with neither still fails. No
    migration, and nothing starts passing that was not already passing.
    """
    advisable = [device for device in config.devices if is_advisable(device)]
    return bool(advisable) and all(
        device.has_ready_window or device.runs_any_time for device in advisable
    )


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
