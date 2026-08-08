"""Tests for the calculation engine (SPEC.md §24 "Rekenmotor").

Covers the calculator list from SPEC.md §24: a signed grid meter in both
directions, separate import/export, solar surplus via the meter and via
consumption, no reliable calculation at all, peak warning, and the data quality
checklist and energy score.
"""

import math
from typing import Any

import pytest
from homeassistant.core import HomeAssistant

from custom_components.domotiapp_energy.const import (
    COMPLETENESS_ITEM_DEVICE_PROFILE,
    COMPLETENESS_ITEM_GRID,
    COMPLETENESS_ITEM_HOME,
    COMPLETENESS_ITEM_PRICE,
    COMPLETENESS_ITEM_SOLAR,
    COMPLETENESS_ITEM_TIME_WINDOWS,
    COMPLETENESS_UNCONDITIONAL_ITEMS,
    COMPONENT_MAX,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONTRACT_TYPE_DYNAMIC,
    CONTRACT_TYPE_FIXED,
    CONTROL_MONITOR_ONLY,
    DEVICE_TYPE_DISHWASHER,
    DEVICE_TYPE_GENERIC_MONITOR,
    HOME_CONSUMPTION_BATTERY_UNREADABLE,
    HOME_CONSUMPTION_NO_GRID_READING,
    HOME_CONSUMPTION_SOLAR_UNREADABLE,
    METER_MODE_SEPARATE,
    METER_MODE_SINGLE_SIGNED,
    POSITIVE_MEANS_EXPORT,
    POSITIVE_MEANS_IMPORT,
    PRICE_BASIS_ALL_IN,
    PRICE_BASIS_MARKET,
    SCORE_COMPONENT_PRICE,
    SCORE_COMPONENT_SOLAR,
    SCORE_UNAVAILABLE_CHEAP_PRICE,
    SCORE_UNAVAILABLE_INCOMPLETE_SETUP,
    SCORE_UNAVAILABLE_NO_SUN_CHEAP_PRICE,
    SCORE_UNAVAILABLE_NO_SUN_FIXED_TARIFF,
    SCORE_UNAVAILABLE_NO_VARIABLE_SIGNAL,
    SCORE_UNAVAILABLE_NOTHING_MOVABLE,
    SCORE_UNAVAILABLE_PRICE_THRESHOLDS_MISSING,
    SOURCE_TYPE_CURRENT_PRICE,
    SOURCE_TYPE_FEED_IN_PRICE,
    SOURCE_TYPE_GENERAL_CONSUMPTION,
    SOURCE_TYPE_GRID_METER,
    SOURCE_TYPE_HOME_BATTERY,
    SOURCE_TYPE_SOLAR,
    UNIT_CT_KWH,
    UNIT_EUR_KWH,
    UNIT_KW,
    UNIT_W,
)
from custom_components.domotiapp_energy.engine.calculator import Calculator
from custom_components.domotiapp_energy.engine.completeness import (
    evaluate_completeness,
)
from custom_components.domotiapp_energy.engine.reason_codes import (
    REASON_INVALID_ENTITY_STATE,
    REASON_MISSING_REQUIRED_DATA,
)
from custom_components.domotiapp_energy.models import (
    DataQualityResult,
    DeviceProfile,
    EnergySnapshot,
    EnergySource,
    EntityBinding,
    HomeProfile,
    StoredConfiguration,
)


def _config(**home_overrides: Any) -> StoredConfiguration:
    """Return a configuration with a usable home profile."""
    home = HomeProfile(
        main_fuse_a=25,
        max_grid_power_w=5750.0,
        **home_overrides,
    )
    return StoredConfiguration(home=home)


def _source(source_type: str, entity_id: str, **overrides: Any) -> EnergySource:
    """Return an enabled source of the given type on the given entity."""
    return EnergySource(
        id=f"{source_type}-1",
        name=source_type,
        type=source_type,
        binding=EntityBinding(entity_id=entity_id, unit=UNIT_W),
        **overrides,
    )


def _movable_device(**overrides: Any) -> DeviceProfile:
    """Return an appliance that can actually be moved to another moment.

    Both fields are set on purpose and neither is decoration: without them
    `has_movable_load` is False, the solar component does not apply, and a test
    that meant to measure self-consumption would quietly measure nothing at all.
    """
    defaults: dict[str, Any] = {
        "id": "d1",
        "device_type": DEVICE_TYPE_DISHWASHER,
        "nominal_power_w": 2000.0,
        "energy_per_cycle_kwh": 1.2,
    }
    return DeviceProfile(**(defaults | overrides))


def _solar_home(**home_overrides: Any) -> StoredConfiguration:
    """Return a home with panels, a grid meter and something to shift.

    The movable appliance is what makes the solar axis apply at all (SPEC.md
    §35.4a): a home with panels and nothing to shift cannot raise its own
    self-consumption, so the component is deliberately absent there. Every test
    about *how much* self-consumption is scored needs this home; the test about
    a home without anything movable builds its own.

    **The fixed import price is not decoration either.** Without it the price
    checklist item fails, the gate shuts, and `energy_score` is None whatever
    the solar component says — so a test that meant to measure self-consumption
    would silently be testing the gate instead.
    """
    home_overrides.setdefault("fixed_import_price_eur_kwh", 0.30)
    config = _config(**home_overrides)
    config.sources.append(_grid_meter())
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
    config.devices.append(_movable_device())
    return config


def _price_source(entity_id: str = "sensor.price", **overrides: Any) -> EnergySource:
    """Return a price source that reports the all-in price, in EUR/kWh.

    The basis is stated in every test that expects a usable price, because
    there is no default: a source that does not say what kind of price it
    reports is refused rather than guessed at (SPEC.md §16).
    """
    defaults: dict[str, Any] = {"price_basis": PRICE_BASIS_ALL_IN}
    source = _source(SOURCE_TYPE_CURRENT_PRICE, entity_id, **(defaults | overrides))
    source.binding = EntityBinding(entity_id=entity_id, unit=UNIT_EUR_KWH)
    return source


def _feed_in_source(entity_id: str = "sensor.terug", **overrides: Any) -> EnergySource:
    """Return a feed-in price source in EUR/kWh.

    Like `_price_source`, the basis is stated per test and has no default: a
    source that does not say what kind of price it reports is refused rather
    than guessed at (SPEC.md §16).
    """
    source = _source(SOURCE_TYPE_FEED_IN_PRICE, entity_id, **overrides)
    source.binding = EntityBinding(entity_id=entity_id, unit=UNIT_EUR_KWH)
    return source


def _grid_meter(entity_id: str = "sensor.grid", **overrides: Any) -> EnergySource:
    """Return a signed grid meter where positive means import."""
    defaults: dict[str, Any] = {
        "meter_mode": METER_MODE_SINGLE_SIGNED,
        "positive_means": POSITIVE_MEANS_IMPORT,
    }
    return _source(SOURCE_TYPE_GRID_METER, entity_id, **(defaults | overrides))


# --- Grid power normalisation -----------------------------------------------


async def test_signed_meter_with_positive_import(hass: HomeAssistant) -> None:
    """positive_means=import leaves the value untouched (SPEC.md §16)."""
    hass.states.async_set("sensor.grid", "1500")
    config = _config()
    config.sources.append(_grid_meter())

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.grid_power_w == 1500.0


async def test_signed_meter_with_positive_export(hass: HomeAssistant) -> None:
    """positive_means=export flips the sign to the internal convention."""
    hass.states.async_set("sensor.grid", "1500")
    config = _config()
    config.sources.append(_grid_meter(positive_means=POSITIVE_MEANS_EXPORT))

    snapshot = Calculator(hass).build_snapshot(config)

    # Positive means export, so 1500 W out of the house is -1500 W internally.
    assert snapshot.grid_power_w == -1500.0


async def test_a_meter_at_zero_never_reports_negative_zero(
    hass: HomeAssistant,
) -> None:
    """0 W stays 0.0 through the sign flip and into the surplus.

    ``-0.0 == 0.0``, so an equality assertion cannot see the difference; the
    customer can, because the sensor state reads ``-0.0``. Both the meter
    normalisation and the surplus clamp can produce it — ``max()`` returns its
    first argument when the two compare equal.
    """
    hass.states.async_set("sensor.grid", "0")
    config = _config()
    config.sources.append(_grid_meter(positive_means=POSITIVE_MEANS_EXPORT))

    metrics = Calculator(hass).calculate(config)

    assert metrics.grid_power_w == 0.0
    assert math.copysign(1.0, metrics.grid_power_w) == 1.0
    assert metrics.solar_surplus_w == 0.0
    assert math.copysign(1.0, metrics.solar_surplus_w) == 1.0


async def test_importing_power_yields_a_positive_zero_surplus(
    hass: HomeAssistant,
) -> None:
    """Drawing from the grid means no surplus, reported as a plain 0.0."""
    hass.states.async_set("sensor.grid", "1500")
    config = _config()
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)

    assert metrics.solar_surplus_w == 0.0
    assert math.copysign(1.0, metrics.solar_surplus_w) == 1.0


async def test_separate_import_and_export_entities(hass: HomeAssistant) -> None:
    """separate_import_export subtracts export from import."""
    hass.states.async_set("sensor.import", "400")
    hass.states.async_set("sensor.export", "1000")
    config = _config()
    config.sources.append(
        EnergySource(
            id="s1",
            type=SOURCE_TYPE_GRID_METER,
            binding=EntityBinding(unit=UNIT_W),
            meter_mode=METER_MODE_SEPARATE,
            import_entity_id="sensor.import",
            export_entity_id="sensor.export",
        )
    )

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.grid_power_w == -600.0


async def test_a_grid_meter_without_a_mode_is_unusable(hass: HomeAssistant) -> None:
    """The meter mode is never derived from the linked entities."""
    hass.states.async_set("sensor.grid", "1500")
    config = _config()
    config.sources.append(
        _source(SOURCE_TYPE_GRID_METER, "sensor.grid", meter_mode=None)
    )

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.grid_power_w is None
    assert snapshot.invalid_source_ids == ["grid_meter-1"]
    assert REASON_MISSING_REQUIRED_DATA in snapshot.reason_codes


async def test_a_separate_meter_needs_both_entities(hass: HomeAssistant) -> None:
    """One readable half is not half a measurement."""
    hass.states.async_set("sensor.import", "400")
    config = _config()
    config.sources.append(
        EnergySource(
            id="s1",
            type=SOURCE_TYPE_GRID_METER,
            binding=EntityBinding(unit=UNIT_W),
            meter_mode=METER_MODE_SEPARATE,
            import_entity_id="sensor.import",
            export_entity_id="sensor.export",
        )
    )

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.grid_power_w is None
    assert snapshot.invalid_source_ids == ["s1"]


async def test_a_signed_meter_without_positive_means_is_unusable(
    hass: HomeAssistant,
) -> None:
    """Without knowing what a positive value means, the sign is a guess."""
    hass.states.async_set("sensor.grid", "1500")
    config = _config()
    config.sources.append(_grid_meter(positive_means=None))

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.grid_power_w is None
    assert REASON_MISSING_REQUIRED_DATA in snapshot.reason_codes


async def test_a_separate_meter_needs_a_readable_import(
    hass: HomeAssistant,
) -> None:
    """An unreadable import half refuses the whole meter."""
    hass.states.async_set("sensor.export", "1000")
    config = _config()
    config.sources.append(
        EnergySource(
            id="s1",
            type=SOURCE_TYPE_GRID_METER,
            binding=EntityBinding(unit=UNIT_W),
            meter_mode=METER_MODE_SEPARATE,
            import_entity_id="sensor.import",
            export_entity_id="sensor.export",
        )
    )

    assert Calculator(hass).build_snapshot(config).grid_power_w is None


async def test_a_disabled_source_is_not_read(hass: HomeAssistant) -> None:
    """A source the installer switched off contributes nothing at all."""
    hass.states.async_set("sensor.grid", "1500")
    config = _config()
    config.sources.append(_grid_meter(enabled=False))

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.grid_power_w is None
    # Disabled on purpose is not the same as broken, so it is not reported.
    assert snapshot.invalid_source_ids == []


async def test_a_quarantined_source_is_not_read(hass: HomeAssistant) -> None:
    """A row with an unrecognised type never reaches a calculation."""
    hass.states.async_set("sensor.grid", "1500")
    config = _config()
    config.sources.append(
        EnergySource(
            id="s1",
            type="grid_metre",
            binding=EntityBinding(entity_id="sensor.grid", unit=UNIT_W),
        )
    )

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.grid_power_w is None


async def test_an_unreadable_source_is_reported(hass: HomeAssistant) -> None:
    """A source whose entity is unavailable names itself in the snapshot."""
    hass.states.async_set("sensor.grid", "unavailable")
    config = _config()
    config.sources.append(_grid_meter())

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.grid_power_w is None
    assert snapshot.invalid_source_ids == ["grid_meter-1"]
    assert REASON_INVALID_ENTITY_STATE in snapshot.reason_codes


async def test_two_solar_sources_add_up(hass: HomeAssistant) -> None:
    """Two inverters produce more together than either does alone."""
    hass.states.async_set("sensor.pv_east", "1200")
    hass.states.async_set("sensor.pv_west", "800")
    config = _config()
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv_east"))
    second = _source(SOURCE_TYPE_SOLAR, "sensor.pv_west")
    second.id = "solar-2"
    config.sources.append(second)

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.solar_power_w == 2000.0


async def test_the_unit_of_each_source_is_applied(hass: HomeAssistant) -> None:
    """Each source converts with its own unit, not a shared one."""
    hass.states.async_set("sensor.grid", "1.5")
    config = _config()
    meter = _grid_meter()
    meter.binding = EntityBinding(entity_id="sensor.grid", unit=UNIT_KW)
    config.sources.append(meter)

    assert Calculator(hass).build_snapshot(config).grid_power_w == 1500.0


# --- Duplicate sources of an exclusive type ---------------------------------


async def test_two_grid_meters_are_both_refused(hass: HomeAssistant) -> None:
    """Neither is used: picking one would be a guess (SPEC.md §16)."""
    hass.states.async_set("sensor.grid_a", "1500")
    hass.states.async_set("sensor.grid_b", "1600")
    config = _config()
    first = _grid_meter("sensor.grid_a")
    first.id = "meter-a"
    second = _grid_meter("sensor.grid_b")
    second.id = "meter-b"
    config.sources.extend([first, second])

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.grid_power_w is None
    assert snapshot.invalid_source_ids == ["meter-a", "meter-b"]
    assert REASON_MISSING_REQUIRED_DATA in snapshot.reason_codes


async def test_two_price_sources_are_both_refused(hass: HomeAssistant) -> None:
    """The same rule applies to the price source."""
    hass.states.async_set("sensor.price_a", "0.20")
    hass.states.async_set("sensor.price_b", "0.25")
    config = _config(contract_type=CONTRACT_TYPE_DYNAMIC)
    for index, entity in enumerate(("sensor.price_a", "sensor.price_b")):
        price = _price_source(entity)
        price.id = f"price-{index}"
        config.sources.append(price)

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.current_price_eur_kwh is None
    assert snapshot.invalid_source_ids == ["price-0", "price-1"]


async def test_duplicate_meters_count_as_invalid_items(
    hass: HomeAssistant,
) -> None:
    """Both rows show up in the data quality result."""
    hass.states.async_set("sensor.grid_a", "1500")
    hass.states.async_set("sensor.grid_b", "1600")
    config = _config()
    first = _grid_meter("sensor.grid_a")
    first.id = "meter-a"
    second = _grid_meter("sensor.grid_b")
    second.id = "meter-b"
    config.sources.extend([first, second])

    metrics = Calculator(hass).calculate(config)

    assert metrics.data_quality.invalid_items == ["meter-a", "meter-b"]
    assert COMPLETENESS_ITEM_GRID in metrics.data_quality.missing_items


async def test_a_disabled_duplicate_leaves_the_other_usable(
    hass: HomeAssistant,
) -> None:
    """Switching one off is exactly how the installer resolves this."""
    hass.states.async_set("sensor.grid_a", "1500")
    hass.states.async_set("sensor.grid_b", "1600")
    config = _config()
    first = _grid_meter("sensor.grid_a")
    first.id = "meter-a"
    second = _grid_meter("sensor.grid_b", enabled=False)
    second.id = "meter-b"
    config.sources.extend([first, second])

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.grid_power_w == 1500.0
    assert snapshot.invalid_source_ids == []


async def test_a_quarantined_duplicate_does_not_block_the_other(
    hass: HomeAssistant,
) -> None:
    """A row with an unrecognised type is not a second grid meter."""
    hass.states.async_set("sensor.grid_a", "1500")
    config = _config()
    meter = _grid_meter("sensor.grid_a")
    meter.id = "meter-a"
    config.sources.append(meter)
    config.sources.append(EnergySource(id="broken", type="grid_metre"))

    assert Calculator(hass).build_snapshot(config).grid_power_w == 1500.0


async def test_both_exclusive_types_duplicated_at_once(
    hass: HomeAssistant,
) -> None:
    """Two problems of the same kind still record one reason code."""
    config = _config(contract_type=CONTRACT_TYPE_DYNAMIC)
    for index in range(2):
        meter = _grid_meter(f"sensor.grid_{index}")
        meter.id = f"meter-{index}"
        config.sources.append(meter)
        price = _price_source(f"sensor.price_{index}")
        price.id = f"price-{index}"
        config.sources.append(price)

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.grid_power_w is None
    assert snapshot.current_price_eur_kwh is None
    assert snapshot.reason_codes == [REASON_MISSING_REQUIRED_DATA]
    assert sorted(snapshot.invalid_source_ids) == [
        "meter-0",
        "meter-1",
        "price-0",
        "price-1",
    ]


async def test_two_sources_failing_the_same_way_share_one_reason_code(
    hass: HomeAssistant,
) -> None:
    """Reason codes are a set of causes, not a list per row."""
    hass.states.async_set("sensor.pv_east", "unavailable")
    hass.states.async_set("sensor.pv_west", "unavailable")
    config = _config()
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv_east"))
    second = _source(SOURCE_TYPE_SOLAR, "sensor.pv_west")
    second.id = "solar-2"
    config.sources.append(second)

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.solar_power_w is None
    assert snapshot.reason_codes == [REASON_INVALID_ENTITY_STATE]
    assert snapshot.invalid_source_ids == ["solar-1", "solar-2"]


async def test_two_solar_sources_are_not_a_duplicate_problem(
    hass: HomeAssistant,
) -> None:
    """Additive types are explicitly allowed to occur more than once."""
    hass.states.async_set("sensor.pv_east", "1200")
    hass.states.async_set("sensor.pv_west", "800")
    config = _config()
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv_east"))
    second = _source(SOURCE_TYPE_SOLAR, "sensor.pv_west")
    second.id = "solar-2"
    config.sources.append(second)

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.solar_power_w == 2000.0
    assert snapshot.invalid_source_ids == []


# --- Price composition (SPEC.md §16 "Prijsopbouw") ---------------------------


async def test_an_all_in_price_source_is_used_as_it_is(hass: HomeAssistant) -> None:
    """A source that already reports the all-in price needs no conversion."""
    hass.states.async_set("sensor.price", "0.28")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        energy_tax_eur_kwh=0.1088,
        supplier_markup_eur_kwh=0.02,
    )
    config.sources.append(_price_source())

    snapshot = Calculator(hass).build_snapshot(config)

    # The components are filled in, but an all-in source must not be marked up
    # a second time: that is the whole point of asking for the basis.
    assert snapshot.current_price_eur_kwh == 0.28


async def test_a_market_price_is_normalised_to_an_all_in_price(
    hass: HomeAssistant,
) -> None:
    """(market + opslag + belasting) x (1 + btw), exactly as SPEC.md §16 says."""
    hass.states.async_set("sensor.price", "0.08")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        energy_tax_eur_kwh=0.1088,
        supplier_markup_eur_kwh=0.02,
        vat_percent=21.0,
    )
    config.sources.append(_price_source(price_basis=PRICE_BASIS_MARKET))

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.current_price_eur_kwh == pytest.approx(0.2088 * 1.21)


async def test_a_market_price_in_cents_is_converted_before_it_is_normalised(
    hass: HomeAssistant,
) -> None:
    """The unit conversion of SPEC.md §15 runs first, the price formula second."""
    hass.states.async_set("sensor.price", "8.0")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        energy_tax_eur_kwh=0.1088,
        supplier_markup_eur_kwh=0.02,
    )
    price = _price_source(price_basis=PRICE_BASIS_MARKET)
    price.binding = EntityBinding(entity_id="sensor.price", unit=UNIT_CT_KWH)
    config.sources.append(price)

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.current_price_eur_kwh == pytest.approx(0.2088 * 1.21)


async def test_a_price_source_without_a_basis_is_unusable(
    hass: HomeAssistant,
) -> None:
    """No basis is not "probably all-in": the source is refused (SPEC.md §16).

    The same strictness as a grid meter without a meter mode, and for the same
    reason — the two possible readings are a factor of about three apart.
    """
    hass.states.async_set("sensor.price", "0.08")
    config = _config(contract_type=CONTRACT_TYPE_DYNAMIC)
    config.sources.append(_price_source(price_basis=None))

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.current_price_eur_kwh is None
    assert snapshot.invalid_source_ids == ["current_price-1"]
    assert snapshot.reason_codes == [REASON_MISSING_REQUIRED_DATA]
    # Nothing broke: the entity is fine, the configuration is unfinished.
    assert snapshot.source_failures == []


async def test_a_market_price_without_the_components_is_unusable(
    hass: HomeAssistant,
) -> None:
    """A missing energy tax is refused, never treated as zero.

    Treating it as zero would understate the price by more than half while
    every threshold, saving and coach answer kept quoting it as fact.
    """
    hass.states.async_set("sensor.price", "0.08")
    config = _config(contract_type=CONTRACT_TYPE_DYNAMIC, supplier_markup_eur_kwh=0.02)
    config.sources.append(_price_source(price_basis=PRICE_BASIS_MARKET))

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.current_price_eur_kwh is None
    assert snapshot.invalid_source_ids == ["current_price-1"]
    assert snapshot.reason_codes == [REASON_MISSING_REQUIRED_DATA]
    assert snapshot.source_failures == []


async def test_a_market_price_without_a_markup_is_unusable(
    hass: HomeAssistant,
) -> None:
    """Both components are needed; a markup of zero has to be typed in."""
    hass.states.async_set("sensor.price", "0.08")
    config = _config(contract_type=CONTRACT_TYPE_DYNAMIC, energy_tax_eur_kwh=0.1088)
    config.sources.append(_price_source(price_basis=PRICE_BASIS_MARKET))

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.current_price_eur_kwh is None


async def test_a_zero_markup_is_a_choice_and_not_a_gap(hass: HomeAssistant) -> None:
    """An explicit 0.0 is an answer; only None means "not entered"."""
    hass.states.async_set("sensor.price", "0.08")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        energy_tax_eur_kwh=0.1088,
        supplier_markup_eur_kwh=0.0,
    )
    config.sources.append(_price_source(price_basis=PRICE_BASIS_MARKET))

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.current_price_eur_kwh == pytest.approx(0.1888 * 1.21)


async def test_a_negative_supplier_markup_survives(hass: HomeAssistant) -> None:
    """A discount is a real contract, so it must not be dropped as unusable."""
    hass.states.async_set("sensor.price", "0.08")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        energy_tax_eur_kwh=0.1088,
        supplier_markup_eur_kwh=-0.01,
    )
    config.sources.append(_price_source(price_basis=PRICE_BASIS_MARKET))

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.current_price_eur_kwh == pytest.approx(0.1788 * 1.21)


async def test_the_vat_rate_is_a_setting_and_not_a_constant(
    hass: HomeAssistant,
) -> None:
    """A changed rate follows through without a release (SPEC.md §16)."""
    hass.states.async_set("sensor.price", "0.08")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        energy_tax_eur_kwh=0.1088,
        supplier_markup_eur_kwh=0.02,
        vat_percent=9.0,
    )
    config.sources.append(_price_source(price_basis=PRICE_BASIS_MARKET))

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.current_price_eur_kwh == pytest.approx(0.2088 * 1.09)


async def test_a_normalised_price_carries_no_floating_point_noise(
    hass: HomeAssistant,
) -> None:
    """The panel shows this number verbatim, so it may not read as 0.2806799…."""
    hass.states.async_set("sensor.price", "0.1")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        energy_tax_eur_kwh=0.1,
        supplier_markup_eur_kwh=0.03,
    )
    config.sources.append(_price_source(price_basis=PRICE_BASIS_MARKET))

    snapshot = Calculator(hass).build_snapshot(config)

    assert snapshot.current_price_eur_kwh == 0.2783


async def test_an_unusable_price_source_costs_the_price_points(
    hass: HomeAssistant,
) -> None:
    """A price nobody can interpret is missing data, and the checklist says so."""
    hass.states.async_set("sensor.price", "0.08")
    config = _config(contract_type=CONTRACT_TYPE_DYNAMIC)
    config.sources.append(_price_source(price_basis=None))

    metrics = Calculator(hass).calculate(config)

    assert COMPLETENESS_ITEM_PRICE in metrics.data_quality.missing_items
    assert "current_price-1" in metrics.data_quality.invalid_items


async def test_the_price_component_judges_the_normalised_price(
    hass: HomeAssistant,
) -> None:
    """Thresholds and price share one unit, which is what makes this work.

    A market price of 0.08 looks "low" against a 0.15 threshold; the all-in
    price it stands for is 0.25 and is not low at all.
    """
    hass.states.async_set("sensor.price", "0.08")
    # The grid meter is what makes the component computable at all: the import
    # share is half of what it multiplies (SPEC.md §35.4c).
    hass.states.async_set("sensor.grid", "2000")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
        energy_tax_eur_kwh=0.1088,
        supplier_markup_eur_kwh=0.02,
    )
    config.sources.append(_grid_meter())
    config.sources.append(_price_source(price_basis=PRICE_BASIS_MARKET))

    metrics = Calculator(hass).calculate(config)

    assert metrics.current_price_eur_kwh == pytest.approx(0.2526, abs=0.0001)
    assert metrics.score_components[SCORE_COMPONENT_PRICE] < COMPONENT_MAX


# --- Solar surplus ----------------------------------------------------------


async def test_solar_surplus_from_the_grid_meter(hass: HomeAssistant) -> None:
    """Export is surplus, with high confidence (SPEC.md §16 variant 1)."""
    hass.states.async_set("sensor.grid", "-2200")
    config = _config()
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)

    assert metrics.solar_surplus_w == 2200.0
    assert metrics.solar_surplus_confidence == CONFIDENCE_HIGH


async def test_importing_means_no_surplus(hass: HomeAssistant) -> None:
    """Drawing from the grid is a surplus of zero, not a negative surplus."""
    hass.states.async_set("sensor.grid", "800")
    config = _config()
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)

    assert metrics.solar_surplus_w == 0.0
    assert metrics.solar_surplus_confidence == CONFIDENCE_HIGH


async def test_solar_surplus_from_production_and_consumption(
    hass: HomeAssistant,
) -> None:
    """Without a meter, production minus consumption is the fallback."""
    hass.states.async_set("sensor.pv", "3000")
    hass.states.async_set("sensor.house", "1100")
    config = _config()
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
    config.sources.append(_source(SOURCE_TYPE_GENERAL_CONSUMPTION, "sensor.house"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.solar_surplus_w == 1900.0
    assert metrics.solar_surplus_confidence == CONFIDENCE_MEDIUM


async def test_a_readable_surplus_is_never_flagged_as_overstated(
    hass: HomeAssistant,
) -> None:
    """Variant 2 with everything readable is a fine number, not a doubtful one.

    The other half of the test below. Without this one the suite would stay
    green if the flag were simply always true, which would silence the surplus
    advice for every home that has no grid meter.
    """
    hass.states.async_set("sensor.pv", "3000")
    hass.states.async_set("sensor.house", "1100")
    config = _config()
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
    config.sources.append(_source(SOURCE_TYPE_GENERAL_CONSUMPTION, "sensor.house"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.solar_surplus_may_be_overstated is False


async def test_an_unreadable_battery_marks_the_surplus_as_overstated(
    hass: HomeAssistant,
) -> None:
    """A battery we cannot read could be the whole surplus (0.4.1).

    This is the one case the old three-level label was really about, and it is
    a blind spot rather than a shade of doubt: the 1900 W below could be the
    battery charging, in which case there is nothing spare at all.
    """
    hass.states.async_set("sensor.pv", "3000")
    hass.states.async_set("sensor.house", "1100")
    # The battery source exists and its entity has no readable value.
    config = _config()
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
    config.sources.append(_source(SOURCE_TYPE_GENERAL_CONSUMPTION, "sensor.house"))
    config.sources.append(_source(SOURCE_TYPE_HOME_BATTERY, "sensor.accu"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.solar_surplus_w == 1900.0
    assert metrics.solar_surplus_may_be_overstated is True
    # It travels to the panel as a conclusion, not as a rule to re-apply.
    assert metrics.to_dict()["solar_surplus_may_be_overstated"] is True


async def test_no_surplus_at_all_is_not_an_overstatement(
    hass: HomeAssistant,
) -> None:
    """Without a number there is nothing to overstate.

    `solar_surplus_confidence` is `low` here too — variant 3 returns it with no
    surplus — so a predicate that only read the level would raise the battery
    sentence on a home with no solar configuration whatsoever.
    """
    metrics = Calculator(hass).calculate(_config())

    assert metrics.solar_surplus_w is None
    assert metrics.solar_surplus_may_be_overstated is False


async def test_a_charging_battery_eats_into_the_surplus(
    hass: HomeAssistant,
) -> None:
    """A charging battery is consumption the house meter does not see."""
    hass.states.async_set("sensor.pv", "3000")
    hass.states.async_set("sensor.house", "1000")
    hass.states.async_set("sensor.battery", "1500")
    config = _config()
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
    config.sources.append(_source(SOURCE_TYPE_GENERAL_CONSUMPTION, "sensor.house"))
    config.sources.append(_source(SOURCE_TYPE_HOME_BATTERY, "sensor.battery"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.solar_surplus_w == 500.0


async def test_a_discharging_battery_does_not_add_to_the_surplus(
    hass: HomeAssistant,
) -> None:
    """Discharging is negative, and must not be subtracted as consumption."""
    hass.states.async_set("sensor.pv", "3000")
    hass.states.async_set("sensor.house", "1000")
    hass.states.async_set("sensor.battery", "-1500")
    config = _config()
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
    config.sources.append(_source(SOURCE_TYPE_GENERAL_CONSUMPTION, "sensor.house"))
    config.sources.append(_source(SOURCE_TYPE_HOME_BATTERY, "sensor.battery"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.solar_surplus_w == 2000.0


async def test_an_unreadable_battery_lowers_the_confidence(
    hass: HomeAssistant,
) -> None:
    """SPEC.md §16: variant 2 drops to low when the battery cannot be read."""
    hass.states.async_set("sensor.pv", "3000")
    hass.states.async_set("sensor.house", "1000")
    hass.states.async_set("sensor.battery", "unavailable")
    config = _config()
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
    config.sources.append(_source(SOURCE_TYPE_GENERAL_CONSUMPTION, "sensor.house"))
    config.sources.append(_source(SOURCE_TYPE_HOME_BATTERY, "sensor.battery"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.solar_surplus_w == 2000.0
    assert metrics.solar_surplus_confidence == CONFIDENCE_LOW


async def test_consumption_above_production_is_no_surplus(
    hass: HomeAssistant,
) -> None:
    """The surplus floors at zero rather than going negative."""
    hass.states.async_set("sensor.pv", "500")
    hass.states.async_set("sensor.house", "2000")
    config = _config()
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
    config.sources.append(_source(SOURCE_TYPE_GENERAL_CONSUMPTION, "sensor.house"))

    assert Calculator(hass).calculate(config).solar_surplus_w == 0.0


async def test_no_reliable_surplus_calculation(hass: HomeAssistant) -> None:
    """Neither variant available means None, never an estimate."""
    hass.states.async_set("sensor.pv", "3000")
    config = _config()
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.solar_surplus_w is None
    assert metrics.solar_surplus_confidence == CONFIDENCE_LOW
    assert REASON_MISSING_REQUIRED_DATA in metrics.reason_codes


# --- Grid load and peak risk ------------------------------------------------


async def test_grid_load_percentage(hass: HomeAssistant) -> None:
    """The load is the absolute power over the configured maximum."""
    hass.states.async_set("sensor.grid", "2875")
    config = _config()
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)

    assert metrics.grid_load_percent == 50.0


async def test_heavy_export_also_counts_as_load(hass: HomeAssistant) -> None:
    """abs() is deliberate: the fuse limits both directions (SPEC.md §16)."""
    hass.states.async_set("sensor.grid", "-4600")
    config = _config()
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)

    assert metrics.grid_load_percent == 80.0


async def test_peak_risk_at_the_warning_threshold(hass: HomeAssistant) -> None:
    """The comparison is inclusive: exactly at the threshold is a risk."""
    hass.states.async_set("sensor.grid", "4600")
    config = _config(peak_warning_percent=80)
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)

    assert metrics.grid_load_percent == 80.0
    assert metrics.peak_risk is True


async def test_no_peak_risk_below_the_threshold(hass: HomeAssistant) -> None:
    """Just under the threshold is not a risk."""
    hass.states.async_set("sensor.grid", "4000")
    config = _config(peak_warning_percent=80)
    config.sources.append(_grid_meter())

    assert Calculator(hass).calculate(config).peak_risk is False


@pytest.mark.parametrize("maximum", [None, 0.0])
async def test_an_unusable_maximum_makes_the_load_unknown(
    hass: HomeAssistant, maximum: float | None
) -> None:
    """SPEC.md §16 requires protection against None and 0."""
    hass.states.async_set("sensor.grid", "2000")
    config = _config()
    config.home.max_grid_power_w = maximum
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)

    assert metrics.grid_load_percent is None
    assert metrics.peak_risk is False
    assert REASON_MISSING_REQUIRED_DATA in metrics.reason_codes


async def test_an_unknown_load_is_not_a_peak_risk(hass: HomeAssistant) -> None:
    """Claiming a risk without a measurement would be a guess."""
    config = _config()

    assert Calculator(hass).calculate(config).peak_risk is False


# --- Data quality -----------------------------------------------------------


def test_an_empty_configuration_scores_zero() -> None:
    """Nothing configured means no points at all.

    Only the three unconditional items are asked of an empty configuration —
    there is no solar row and no appliance to judge — and all three fail, so the
    score is zero either way. A fresh install must never score 100 for owning
    nothing, which is the failure mode the unconditional three exist to prevent.
    """
    result = evaluate_completeness(StoredConfiguration(), EnergySnapshot())

    assert result.score == 0
    assert result.completed_items == []
    assert set(result.missing_items) == {
        COMPLETENESS_ITEM_HOME,
        COMPLETENESS_ITEM_GRID,
        COMPLETENESS_ITEM_PRICE,
    }
    assert set(result.not_applicable_items) == {
        COMPLETENESS_ITEM_SOLAR,
        COMPLETENESS_ITEM_DEVICE_PROFILE,
        COMPLETENESS_ITEM_TIME_WINDOWS,
    }


def test_each_checklist_item_is_worth_its_documented_points() -> None:
    """The weights are the ones in the SPEC.md §16 table.

    A home that owns all six things is judged on all six, and the weights then
    sum to 100 exactly as they always did.
    """
    config = _config(contract_type=CONTRACT_TYPE_FIXED, fixed_import_price_eur_kwh=0.28)
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.solar"))
    config.devices.append(
        DeviceProfile(
            id="d1",
            device_type=DEVICE_TYPE_DISHWASHER,
            nominal_power_w=2000.0,
            energy_per_cycle_kwh=1.2,
            ready_from="08:00",
            ready_before="23:00",
        )
    )
    snapshot = EnergySnapshot(grid_power_w=1000.0, solar_power_w=500.0)

    result = evaluate_completeness(config, snapshot)

    assert set(result.completed_items) == {
        COMPLETENESS_ITEM_HOME,
        COMPLETENESS_ITEM_GRID,
        COMPLETENESS_ITEM_SOLAR,
        COMPLETENESS_ITEM_PRICE,
        COMPLETENESS_ITEM_DEVICE_PROFILE,
        COMPLETENESS_ITEM_TIME_WINDOWS,
    }
    assert result.score == 100


def test_one_dishwasher_with_only_a_deadline_is_complete() -> None:
    """The exact production configuration that reported this.

    One dishwasher, "klaar uiterlijk om 20:15", 180 minutes, flexible. It scored
    90 with "tijdvensters voor flexibele apparaten" listed as missing — for the
    one configuration the ready window was built to make possible. A deadline
    without a lower bound is a complete answer to "when must this be finished".
    """
    config = _config(contract_type=CONTRACT_TYPE_FIXED, fixed_import_price_eur_kwh=0.28)
    config.devices.append(
        DeviceProfile(
            id="d1",
            device_type=DEVICE_TYPE_DISHWASHER,
            nominal_power_w=2000.0,
            energy_per_cycle_kwh=1.2,
            duration_minutes=180,
            ready_before="20:15",
        )
    )
    snapshot = EnergySnapshot(grid_power_w=1000.0)

    result = evaluate_completeness(config, snapshot)

    assert COMPLETENESS_ITEM_TIME_WINDOWS in result.completed_items
    assert result.missing_items == []
    assert result.score == 100


def test_a_lower_bound_alone_also_counts() -> None:
    """The mirror case: "not finished before 06:00" is equally an answer."""
    config = _config(contract_type=CONTRACT_TYPE_FIXED, fixed_import_price_eur_kwh=0.28)
    config.devices.append(
        DeviceProfile(
            id="d1",
            device_type=DEVICE_TYPE_DISHWASHER,
            nominal_power_w=2000.0,
            energy_per_cycle_kwh=1.2,
            ready_from="06:00",
        )
    )

    result = evaluate_completeness(config, EnergySnapshot(grid_power_w=1000.0))

    assert COMPLETENESS_ITEM_TIME_WINDOWS in result.completed_items


def test_a_flexible_device_with_no_bounds_still_misses_the_item() -> None:
    """Nothing stated is still nothing stated — the item keeps its meaning."""
    config = _config(contract_type=CONTRACT_TYPE_FIXED, fixed_import_price_eur_kwh=0.28)
    config.devices.append(
        DeviceProfile(
            id="d1",
            device_type=DEVICE_TYPE_DISHWASHER,
            nominal_power_w=2000.0,
            energy_per_cycle_kwh=1.2,
        )
    )

    result = evaluate_completeness(config, EnergySnapshot(grid_power_w=1000.0))

    assert COMPLETENESS_ITEM_TIME_WINDOWS in result.missing_items


def test_solar_panels_and_a_meter_but_no_appliances_can_reach_a_hundred() -> None:
    """The install that reported this: solar, a smart meter, no smart appliances.

    It used to be told "2 van de 6 onderdelen is nog niet compleet" for as long
    as it existed, because the two were about appliances the home does not own.
    Nothing the owner could do would ever close them. The checklist now asks
    only what this home can answer (round B, finding 6).
    """
    config = _config(contract_type=CONTRACT_TYPE_FIXED, fixed_import_price_eur_kwh=0.28)
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.solar"))
    snapshot = EnergySnapshot(grid_power_w=1000.0, solar_power_w=500.0)

    result = evaluate_completeness(config, snapshot)

    assert result.score == 100
    assert result.missing_items == []
    assert set(result.not_applicable_items) == {
        COMPLETENESS_ITEM_DEVICE_PROFILE,
        COMPLETENESS_ITEM_TIME_WINDOWS,
    }


def test_a_home_without_solar_is_not_held_to_the_solar_item() -> None:
    """No solar row means nobody said this home has panels, so it is not asked.

    The row is the statement. This is not discovery by another name: nothing is
    inferred from the entity register, only from what an installer entered.
    """
    config = _config(contract_type=CONTRACT_TYPE_FIXED, fixed_import_price_eur_kwh=0.28)
    snapshot = EnergySnapshot(grid_power_w=1000.0)

    result = evaluate_completeness(config, snapshot)

    assert COMPLETENESS_ITEM_SOLAR in result.not_applicable_items
    assert COMPLETENESS_ITEM_SOLAR not in result.missing_items
    assert result.score == 100


def test_a_solar_row_that_reports_nothing_still_costs_points() -> None:
    """Owning panels and not reading them is a real gap, and stays one.

    The distinction the whole rescaling rests on: "no panels" is not a fault,
    "panels we cannot read" is. If both scored 100 the item would mean nothing.
    """
    config = _config(contract_type=CONTRACT_TYPE_FIXED, fixed_import_price_eur_kwh=0.28)
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.solar"))
    snapshot = EnergySnapshot(grid_power_w=1000.0, solar_power_w=None)

    result = evaluate_completeness(config, snapshot)

    assert COMPLETENESS_ITEM_SOLAR in result.missing_items
    # 20 + 25 + 15 earned out of an applicable 20 + 25 + 15 + 15.
    assert result.score == 80


def test_a_dynamic_contract_needs_a_live_price() -> None:
    """A fixed tariff does not satisfy the price item for a dynamic contract."""
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC, fixed_import_price_eur_kwh=0.28
    )

    result = evaluate_completeness(config, EnergySnapshot())

    assert COMPLETENESS_ITEM_PRICE in result.missing_items


def test_a_dynamic_contract_with_a_live_price_passes() -> None:
    """A readable price source satisfies the item."""
    config = _config(contract_type=CONTRACT_TYPE_DYNAMIC)

    result = evaluate_completeness(config, EnergySnapshot(current_price_eur_kwh=0.24))

    assert COMPLETENESS_ITEM_PRICE in result.completed_items


def test_a_home_without_a_maximum_is_incomplete() -> None:
    """Zero is not a usable maximum, so the home item does not pass."""
    config = _config()
    config.home.max_grid_power_w = 0.0

    result = evaluate_completeness(config, EnergySnapshot())

    assert COMPLETENESS_ITEM_HOME in result.missing_items


def test_a_device_without_energy_per_cycle_is_incomplete() -> None:
    """The device item needs both power and energy per cycle."""
    config = _config()
    config.devices.append(
        DeviceProfile(
            id="d1", device_type=DEVICE_TYPE_DISHWASHER, nominal_power_w=2000.0
        )
    )

    result = evaluate_completeness(config, EnergySnapshot())

    assert COMPLETENESS_ITEM_DEVICE_PROFILE in result.missing_items


def test_one_flexible_device_without_a_window_fails_the_item() -> None:
    """The item is about all flexible devices, not just one of them."""
    config = _config()
    config.devices.append(
        DeviceProfile(
            id="d1",
            device_type=DEVICE_TYPE_DISHWASHER,
            ready_from="08:00",
            ready_before="23:00",
        )
    )
    config.devices.append(DeviceProfile(id="d2", device_type=DEVICE_TYPE_DISHWASHER))

    result = evaluate_completeness(config, EnergySnapshot())

    assert COMPLETENESS_ITEM_TIME_WINDOWS in result.missing_items


def test_an_inflexible_device_needs_no_window() -> None:
    """Only flexible devices are judged on their time window."""
    config = _config()
    config.devices.append(
        DeviceProfile(
            id="d1",
            device_type=DEVICE_TYPE_DISHWASHER,
            ready_from="08:00",
            ready_before="23:00",
        )
    )
    # Through from_dict, so is_flexible picks up its type-dependent default.
    config.devices.append(
        DeviceProfile.from_dict(
            {"id": "d2", "device_type": DEVICE_TYPE_GENERIC_MONITOR}
        )
    )

    result = evaluate_completeness(config, EnergySnapshot())

    assert COMPLETENESS_ITEM_TIME_WINDOWS in result.completed_items


def test_a_measured_appliance_is_not_asked_for_a_cycle() -> None:
    """The production finding of 2026-08-09, as a home rather than a device.

    A tablet charger on a smart plug, added as `generic_monitor`. The checklist
    said "een compleet apparaatprofiel" was missing — of a type whose whole
    meaning is that there is no cycle. Both appliance items now leave the
    numerator *and* the denominator, so the score goes up rather than down.
    """
    config = _config(fixed_import_price_eur_kwh=0.30)
    config.sources.append(_grid_meter())
    config.devices.append(
        DeviceProfile(
            id="d1", name="Tabletlader", device_type=DEVICE_TYPE_GENERIC_MONITOR
        )
    )
    snapshot = EnergySnapshot(grid_power_w=500.0)

    result = evaluate_completeness(config, snapshot)

    assert COMPLETENESS_ITEM_DEVICE_PROFILE in result.not_applicable_items
    assert COMPLETENESS_ITEM_TIME_WINDOWS in result.not_applicable_items
    assert result.missing_items == []
    assert result.score == 100


def test_one_advisable_appliance_brings_both_questions_back() -> None:
    """The other half: a dishwasher beside the monitor is asked as before.

    Without this the suite would stay green if the two items were dropped for
    every home, which is the mirror of the defect being fixed.
    """
    config = _config(fixed_import_price_eur_kwh=0.30)
    config.sources.append(_grid_meter())
    config.devices.append(
        DeviceProfile(
            id="d1", name="Tabletlader", device_type=DEVICE_TYPE_GENERIC_MONITOR
        )
    )
    config.devices.append(DeviceProfile(id="d2", device_type=DEVICE_TYPE_DISHWASHER))
    snapshot = EnergySnapshot(grid_power_w=500.0)

    result = evaluate_completeness(config, snapshot)

    assert COMPLETENESS_ITEM_DEVICE_PROFILE in result.missing_items
    assert COMPLETENESS_ITEM_TIME_WINDOWS in result.missing_items


def test_quarantined_rows_are_counted_as_invalid_items() -> None:
    """SPEC.md §12: a row with an unrecognised type counts as invalid."""
    config = _config()
    config.sources.append(EnergySource(id="s1", type="grid_metre"))
    config.devices.append(DeviceProfile(id="d1", device_type="heatpump"))

    result = evaluate_completeness(config, EnergySnapshot(invalid_source_ids=["s2"]))

    assert result.invalid_items == ["s1", "s2", "d1"]


# --- Home consumption (SPEC.md §36) -----------------------------------------
#
# Rows are situations again, not outcomes: what does this home have, what can
# be read, and what belongs on the tile because of it.


def _consumption_home(
    hass: HomeAssistant,
    *,
    grid: float | None = 500.0,
    solar: float | None = None,
    battery: float | None = None,
    panels: bool = False,
    has_battery: bool = False,
) -> StoredConfiguration:
    """Build a home whose readable terms are exactly the ones named.

    `panels` and `has_battery` are the *rows*; `solar` and `battery` are the
    readings. Separating them is the whole point of §36.3: a row that is absent
    means the home does not have the thing, a row that reads nothing means we
    do not know.
    """
    config = _config(fixed_import_price_eur_kwh=0.30)
    if grid is not None:
        hass.states.async_set("sensor.grid", str(grid))
        config.sources.append(_grid_meter())
    if panels:
        config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
        if solar is not None:
            hass.states.async_set("sensor.pv", str(solar))
    if has_battery:
        config.sources.append(_source(SOURCE_TYPE_HOME_BATTERY, "sensor.accu"))
        if battery is not None:
            hass.states.async_set("sensor.accu", str(battery))
    return config


async def test_home_consumption_is_grid_plus_production(hass: HomeAssistant) -> None:
    """The common installation: a P1 meter and an inverter, nothing else.

    Exporting 2400 W while producing 3000 leaves 600 W for the house — the
    figure that was nowhere on screen, and the one a resident looks for first.
    """
    config = _consumption_home(hass, grid=-2400.0, solar=3000.0, panels=True)

    metrics = Calculator(hass).calculate(config)

    assert metrics.home_consumption_w == 600.0
    assert metrics.home_consumption_unavailable_reason is None


async def test_a_charging_battery_is_not_household_consumption(
    hass: HomeAssistant,
) -> None:
    """It comes off the balance: the house is not the one using it."""
    config = _consumption_home(
        hass, grid=1000.0, solar=2000.0, battery=1500.0, panels=True, has_battery=True
    )

    metrics = Calculator(hass).calculate(config)

    assert metrics.home_consumption_w == 1500.0


async def test_a_discharging_battery_feeds_the_house(hass: HomeAssistant) -> None:
    """Negative battery power adds, through the sign convention of §16."""
    config = _consumption_home(
        hass, grid=200.0, solar=0.0, battery=-800.0, panels=True, has_battery=True
    )

    metrics = Calculator(hass).calculate(config)

    assert metrics.home_consumption_w == 1000.0


async def test_a_home_without_panels_needs_no_production_reading(
    hass: HomeAssistant,
) -> None:
    """No solar row is a statement, not a gap: production is a true zero."""
    config = _consumption_home(hass, grid=750.0)

    metrics = Calculator(hass).calculate(config)

    assert metrics.home_consumption_w == 750.0


async def test_an_unreadable_inverter_yields_no_figure(hass: HomeAssistant) -> None:
    """Panels we cannot read means we do not know the consumption.

    Treating the missing term as zero would report 500 W of household use for a
    home that might be producing three kilowatts.
    """
    config = _consumption_home(hass, grid=500.0, panels=True, solar=None)

    metrics = Calculator(hass).calculate(config)

    assert metrics.home_consumption_w is None
    assert (
        metrics.home_consumption_unavailable_reason == HOME_CONSUMPTION_SOLAR_UNREADABLE
    )


async def test_an_unreadable_battery_yields_no_figure(hass: HomeAssistant) -> None:
    """Deliberately unlike the solar surplus, which keeps its number.

    A charging battery is attributed to the household in full here, so the
    figure would be wrong rather than merely uncertain (SPEC.md §36.3). Do not
    level this with the surplus without reading that section.
    """
    config = _consumption_home(hass, grid=3500.0, has_battery=True, battery=None)

    metrics = Calculator(hass).calculate(config)

    assert metrics.home_consumption_w is None
    assert (
        metrics.home_consumption_unavailable_reason
        == HOME_CONSUMPTION_BATTERY_UNREADABLE
    )


async def test_no_grid_reading_yields_no_figure(hass: HomeAssistant) -> None:
    """Without the meter the balance has no anchor."""
    config = _consumption_home(hass, grid=None)

    metrics = Calculator(hass).calculate(config)

    assert metrics.home_consumption_w is None
    assert (
        metrics.home_consumption_unavailable_reason == HOME_CONSUMPTION_NO_GRID_READING
    )


async def test_a_measured_source_wins_from_the_derivation(hass: HomeAssistant) -> None:
    """A measurement beats the difference of two other measurements.

    The balance here would give 500 + 2000 = 2500; the meter says 900, and the
    installer linking it was the statement that this is the truth.
    """
    hass.states.async_set("sensor.house", "900")
    config = _consumption_home(hass, grid=500.0, solar=2000.0, panels=True)
    config.sources.append(_source(SOURCE_TYPE_GENERAL_CONSUMPTION, "sensor.house"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.home_consumption_w == 900.0


async def test_the_measured_source_answers_without_a_grid_meter(
    hass: HomeAssistant,
) -> None:
    """It is not part of the balance, so it needs none of the other terms."""
    hass.states.async_set("sensor.house", "1200")
    config = _consumption_home(hass, grid=None)
    config.sources.append(_source(SOURCE_TYPE_GENERAL_CONSUMPTION, "sensor.house"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.home_consumption_w == 1200.0
    assert metrics.home_consumption_unavailable_reason is None


async def test_sensor_noise_never_shows_a_negative_consumption(
    hass: HomeAssistant,
) -> None:
    """Two sensors sampling a moment apart, and a physical floor.

    Producing 40 W more than the meter reports leaving is arithmetic, not a
    house that consumes negative power.
    """
    config = _consumption_home(hass, grid=-3040.0, solar=3000.0, panels=True)

    metrics = Calculator(hass).calculate(config)

    assert metrics.home_consumption_w == 0.0
    # A clean zero rather than -0.0, which formats as "-0" in the panel.
    assert math.copysign(1.0, metrics.home_consumption_w) > 0


async def test_home_consumption_survives_the_trip_to_the_panel(
    hass: HomeAssistant,
) -> None:
    """Both the figure and the reason reach the frontend."""
    config = _consumption_home(hass, grid=500.0, panels=True, solar=None)

    metrics = Calculator(hass).calculate(config)
    restored = type(metrics).from_dict(metrics.to_dict())

    assert restored.home_consumption_w == metrics.home_consumption_w
    assert (
        restored.home_consumption_unavailable_reason
        == metrics.home_consumption_unavailable_reason
    )


async def test_home_consumption_changes_neither_score_nor_checklist(
    hass: HomeAssistant,
) -> None:
    """It is a measurement, not an axis, and it asks for no configuration.

    SPEC.md §36.8. Without this the round could quietly move the number a
    customer sees every day.
    """
    config = _consumption_home(hass, grid=-2400.0, solar=3000.0, panels=True)

    metrics = Calculator(hass).calculate(config)

    assert metrics.home_consumption_w == 600.0
    assert metrics.data_quality.score == 100
    assert SCORE_COMPONENT_SOLAR not in metrics.score_components


# --- Power per appliance (SPEC.md §37) --------------------------------------


def _linked_device(hass: HomeAssistant, entity_id: str, unit: str, value: str, **kw):
    """Return a device linked to a power entity that reports `value` in `unit`."""
    hass.states.async_set(entity_id, value, {"unit_of_measurement": unit})
    defaults: dict[str, Any] = {
        "id": "d1",
        "device_type": DEVICE_TYPE_DISHWASHER,
        "nominal_power_w": 2000.0,
        "energy_per_cycle_kwh": 1.2,
        "power_entity": entity_id,
    }
    return DeviceProfile.from_dict(defaults | kw)


async def test_a_linked_appliance_reports_its_power(hass: HomeAssistant) -> None:
    """`power_entity` finally has a reader (SPEC.md §37).

    Until 0.6.0 this field was asked of the installer, stored, and watched by
    the coordinator — so filling it in made the integration recalculate more
    often and nothing else.
    """
    config = _config()
    config.devices.append(_linked_device(hass, "sensor.vaatwasser", UNIT_W, "1150"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.device_power_w == {"d1": 1150.0}


async def test_kilowatts_are_converted_and_not_taken_at_face_value(
    hass: HomeAssistant,
) -> None:
    """A kW sensor read as watts would be off by a thousand."""
    config = _config()
    config.devices.append(_linked_device(hass, "sensor.laadpaal", UNIT_KW, "7.4"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.device_power_w == {"d1": 7400.0}


async def test_an_appliance_without_a_link_is_simply_absent(
    hass: HomeAssistant,
) -> None:
    """Not zero and not unknown: absent, so the panel gives it no line.

    An appliance nobody linked is not a gap, and a column of "onbekend" would
    report a fault where there is none.
    """
    config = _config()
    config.devices.append(_movable_device())

    metrics = Calculator(hass).calculate(config)

    assert metrics.device_power_w == {}


async def test_a_power_entity_without_a_unit_is_refused(hass: HomeAssistant) -> None:
    """No unit is no reading. Assuming watts is the guess §15 forbids."""
    config = _config()
    config.devices.append(_linked_device(hass, "sensor.stekker", "", "1150"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.device_power_w == {}


async def test_a_disabled_appliance_is_not_read(hass: HomeAssistant) -> None:
    """Disabled means the engine leaves it alone, readings included."""
    config = _config()
    config.devices.append(
        _linked_device(hass, "sensor.vaatwasser", UNIT_W, "1150", enabled=False)
    )

    metrics = Calculator(hass).calculate(config)

    assert metrics.device_power_w == {}


async def test_standby_does_not_count_as_running(hass: HomeAssistant) -> None:
    """Two watts is an appliance being off, not an appliance running."""
    config = _config()
    config.devices.append(_linked_device(hass, "sensor.vaatwasser", UNIT_W, "2"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.device_power_w == {"d1": 2.0}
    assert metrics.running_device_count == 0


async def test_the_running_count_counts_only_what_draws_power(
    hass: HomeAssistant,
) -> None:
    """Three linked appliances, two of them actually doing something."""
    config = _config()
    config.devices.append(_linked_device(hass, "sensor.a", UNIT_W, "1150"))
    config.devices.append(_linked_device(hass, "sensor.b", UNIT_KW, "2.2", id="d2"))
    config.devices.append(_linked_device(hass, "sensor.c", UNIT_W, "1", id="d3"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.running_device_count == 2


async def test_device_power_reaches_the_path_the_coordinator_uses(
    hass: HomeAssistant,
) -> None:
    """The production path is `build_snapshot` + `derive_metrics`, not `calculate`.

    The first version attached the reading in `calculate()`, which the
    coordinator never calls — the latch sits between the two halves. Every test
    here used `calculate`, so 588 of them passed while the panel showed nothing
    at all. Found by driving the real instance.
    """
    config = _config()
    config.devices.append(_linked_device(hass, "sensor.vaatwasser", UNIT_W, "1150"))

    calculator = Calculator(hass)
    snapshot = calculator.build_snapshot(config)
    metrics = calculator.derive_metrics(config, snapshot)

    assert metrics.device_power_w == {"d1": 1150.0}


async def test_device_power_survives_the_trip_to_the_panel(
    hass: HomeAssistant,
) -> None:
    """Both the mapping and the count reach the frontend."""
    config = _config()
    config.devices.append(_linked_device(hass, "sensor.vaatwasser", UNIT_W, "1150"))

    metrics = Calculator(hass).calculate(config)
    restored = type(metrics).from_dict(metrics.to_dict())

    assert restored.device_power_w == metrics.device_power_w
    assert metrics.to_dict()["running_device_count"] == 1


# --- Energy score -----------------------------------------------------------


async def test_a_fixed_input_gives_a_fixed_score(hass: HomeAssistant) -> None:
    """SPEC.md §24: the same input must always produce the same score."""
    hass.states.async_set("sensor.grid", "-2875")
    hass.states.async_set("sensor.pv", "3000")
    hass.states.async_set("sensor.price", "0.20")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
        min_solar_surplus_w=500.0,
    )
    config.sources.append(_grid_meter())
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
    config.sources.append(_price_source())
    config.devices.append(
        DeviceProfile(
            id="d1",
            device_type=DEVICE_TYPE_DISHWASHER,
            nominal_power_w=2000.0,
            energy_per_cycle_kwh=1.2,
            ready_from="08:00",
            ready_before="23:00",
        )
    )

    metrics = Calculator(hass).calculate(config)

    # Solar: producing 3000 W and exporting 2875 leaves 125 W used at home, so
    # 4.17% self-consumption — the old definition scored this a perfect 100 for
    # exporting almost everything. Price: the home is exporting, so the import
    # share is zero and there is nothing being drawn at the higher price.
    assert metrics.score_components == {
        SCORE_COMPONENT_SOLAR: 4.17,
        SCORE_COMPONENT_PRICE: 100.0,
    }
    # Both apply, so the weights sum to 1.0 and no rescaling happens:
    # 0.50x4.17 + 0.50x100 = 52.08 -> 52
    assert metrics.energy_score == 52
    assert metrics.not_applicable_components == []
    assert metrics.score_unavailable_reason is None


async def test_no_production_means_no_solar_component_at_all(
    hass: HomeAssistant,
) -> None:
    """At night there is nothing being wasted, so there is nothing to score.

    This used to be a zero, which cost a home twenty points every night for
    something that is not a shortcoming (production finding, 2026-08-07).
    """
    config = _config()

    metrics = Calculator(hass).calculate(config)

    assert SCORE_COMPONENT_SOLAR not in metrics.score_components
    assert SCORE_COMPONENT_SOLAR in metrics.not_applicable_components


async def test_the_solar_component_measures_self_consumption(
    hass: HomeAssistant,
) -> None:
    """Producing 2000 W and exporting 500 W is 75% used at home.

    The old definition scored the *export* and would have called this a poor
    25 while the home was doing well — it rewarded exactly what the coach tells
    the resident to avoid.
    """
    hass.states.async_set("sensor.pv", "2000")
    hass.states.async_set("sensor.grid", "-500")
    config = _solar_home()

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_SOLAR] == 75.0


async def test_consuming_all_production_is_full_marks(hass: HomeAssistant) -> None:
    """Nothing exported means everything used at home.

    Under the old definition this was the *worst* possible score, because the
    surplus it measured was zero.
    """
    hass.states.async_set("sensor.pv", "2000")
    hass.states.async_set("sensor.grid", "300")
    config = _solar_home()

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_SOLAR] == 100.0


async def test_exporting_everything_scores_nothing(hass: HomeAssistant) -> None:
    """All production going out to the grid is none of it used at home."""
    hass.states.async_set("sensor.pv", "2000")
    hass.states.async_set("sensor.grid", "-2000")
    config = _solar_home()

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_SOLAR] == 0.0


async def test_a_fixed_contract_is_not_judged_on_price(
    hass: HomeAssistant,
) -> None:
    """A fixed contract has no price signal, so it is left out of the score.

    It used to score 50, meant as neutral. On a 0-100 axis that is a permanent
    7.5-point deduction for choosing a fixed contract, and the constant's own
    comment claimed the score was not dragged down by it.
    """
    config = _config(contract_type=CONTRACT_TYPE_FIXED)

    metrics = Calculator(hass).calculate(config)

    assert SCORE_COMPONENT_PRICE not in metrics.score_components
    assert SCORE_COMPONENT_PRICE in metrics.not_applicable_components


async def test_a_market_feed_in_source_subtracts_the_supplier_cut(
    hass: HomeAssistant,
) -> None:
    """The feed-in formula, and the reason it is not the import formula.

    A market price of 0.09 with the supplier keeping 0.02 leaves 0.07. Run
    through the *import* conversion the same reading would have produced roughly
    0.24 — the energy tax plus VAT on top of a rate the customer never receives.
    """
    hass.states.async_set("sensor.terug", "0.09")
    config = _config(feed_in_markup_eur_kwh=0.02)
    config.sources.append(_feed_in_source(price_basis=PRICE_BASIS_MARKET))

    metrics = Calculator(hass).calculate(config)

    assert metrics.feed_in_price_eur_kwh == 0.07
    # The bare reading is kept so the conversion can be checked against the
    # sensor, exactly as it is for the import price.
    assert metrics.market_feed_in_price_eur_kwh == 0.09


async def test_an_all_in_feed_in_source_is_used_unchanged(
    hass: HomeAssistant,
) -> None:
    """A source that already reports the net rate needs no markup at all."""
    hass.states.async_set("sensor.terug", "0.065")
    config = _config()
    config.sources.append(_feed_in_source(price_basis=PRICE_BASIS_ALL_IN))

    metrics = Calculator(hass).calculate(config)

    assert metrics.feed_in_price_eur_kwh == 0.065
    assert metrics.market_feed_in_price_eur_kwh is None


async def test_a_market_feed_in_source_without_a_markup_is_refused(
    hass: HomeAssistant,
) -> None:
    """No silent zero: an unset markup would overstate what the customer gets.

    An explicit 0 is a real answer and is accepted; only "not entered" blocks,
    the same rule the import components follow.
    """
    hass.states.async_set("sensor.terug", "0.09")
    config = _config(feed_in_markup_eur_kwh=None)
    config.sources.append(_feed_in_source(price_basis=PRICE_BASIS_MARKET))

    metrics = Calculator(hass).calculate(config)

    assert metrics.feed_in_price_eur_kwh is None


async def test_a_markup_of_zero_is_an_answer(hass: HomeAssistant) -> None:
    """Some suppliers keep nothing, and that has to be sayable."""
    hass.states.async_set("sensor.terug", "0.09")
    config = _config(feed_in_markup_eur_kwh=0.0)
    config.sources.append(_feed_in_source(price_basis=PRICE_BASIS_MARKET))

    metrics = Calculator(hass).calculate(config)

    assert metrics.feed_in_price_eur_kwh == 0.09


async def test_a_negative_market_price_yields_a_negative_feed_in_rate(
    hass: HomeAssistant,
) -> None:
    """Negative prices are real, and then feeding in costs money.

    Returned as it stands. Clamping would hide the situation worth knowing
    about, which is the mistake the savings formula made until 0.1.2.
    """
    hass.states.async_set("sensor.terug", "-0.01")
    config = _config(feed_in_markup_eur_kwh=0.02)
    config.sources.append(_feed_in_source(price_basis=PRICE_BASIS_MARKET))

    metrics = Calculator(hass).calculate(config)

    assert metrics.feed_in_price_eur_kwh == -0.03


async def test_a_feed_in_source_without_a_basis_is_unusable(
    hass: HomeAssistant,
) -> None:
    """Same rule as the import price: an unstated basis makes it unusable."""
    hass.states.async_set("sensor.terug", "0.09")
    config = _config(feed_in_markup_eur_kwh=0.02)
    config.sources.append(_feed_in_source(price_basis=None))

    metrics = Calculator(hass).calculate(config)

    assert metrics.feed_in_price_eur_kwh is None


async def test_a_dynamic_contract_without_a_price_does_not_apply(
    hass: HomeAssistant,
) -> None:
    """A missing input drops the component; it no longer scores zero.

    The old rule was "the signal exists and was not configured, so it scores
    zero", which deducted points from the resident for the installer's
    paperwork. The omission is reported by the data quality checklist and by
    the gate, where the person who can fix it will see it (SPEC.md §35.8).
    """
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )

    metrics = Calculator(hass).calculate(config)

    assert SCORE_COMPONENT_PRICE not in metrics.score_components


async def test_a_dynamic_contract_without_thresholds_does_not_apply(
    hass: HomeAssistant,
) -> None:
    """A price without thresholds to judge it by is just as unusable."""
    hass.states.async_set("sensor.price", "0.20")
    config = _config(contract_type=CONTRACT_TYPE_DYNAMIC)
    config.sources.append(_price_source())

    metrics = Calculator(hass).calculate(config)

    assert SCORE_COMPONENT_PRICE not in metrics.score_components


async def test_an_incomplete_installation_has_no_score_at_all(
    hass: HomeAssistant,
) -> None:
    """The gate: no number until the three unconditional items are answered.

    An empty configuration used to score 8 — a number earned entirely by the 50
    a fixed contract was handed for free — and later 0, which still reads as a
    grade. It is neither: there is nothing to grade yet, and the panel says
    which item is missing (SPEC.md §35.7).
    """
    metrics = Calculator(hass).calculate(StoredConfiguration())

    assert metrics.energy_score is None
    assert metrics.score_unavailable_reason == SCORE_UNAVAILABLE_INCOMPLETE_SETUP


async def test_the_gate_shuts_even_when_a_component_could_be_scored(
    hass: HomeAssistant,
) -> None:
    """A computable component is not enough; the gate comes first.

    Solar can be measured here — there is production, a grid reading and a
    dishwasher to shift — but the home profile has no main fuse, so the
    installation does not yet mean anything and there is no number.
    """
    hass.states.async_set("sensor.pv", "2000")
    hass.states.async_set("sensor.grid", "-500")
    config = _solar_home()
    config.home.main_fuse_a = None

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_SOLAR] == 75.0
    assert metrics.energy_score is None
    assert metrics.score_unavailable_reason == SCORE_UNAVAILABLE_INCOMPLETE_SETUP


async def test_a_cheap_hour_is_not_scored_on_price(hass: HomeAssistant) -> None:
    """At or below the low threshold there is nothing to avoid.

    This used to be a free 100. Nobody can move it, so it is the mirror image
    of the fixed contract's permanent 50 — a component that flatters instead of
    measuring (SPEC.md §35.4c).
    """
    hass.states.async_set("sensor.price", "0.10")
    hass.states.async_set("sensor.grid", "1000")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )
    config.sources.append(_grid_meter())
    config.sources.append(_price_source())

    metrics = Calculator(hass).calculate(config)

    assert SCORE_COMPONENT_PRICE not in metrics.score_components
    assert metrics.energy_score is None
    # No panels on this home, so the sentence is about the price alone.
    assert metrics.score_unavailable_reason == SCORE_UNAVAILABLE_CHEAP_PRICE


async def test_the_price_component_measures_what_is_drawn_while_expensive(
    hass: HomeAssistant,
) -> None:
    """Price position times import share, not the price on its own.

    0.35 of the way between 0.15 and 0.35 is the maximum, so the price position
    is 1.0; drawing 2875 W of a 5750 W connection is half. 100 x (1 - 1 x 0.5)
    = 50. The old definition scored this a flat 0 for the hour alone, whatever
    the house was doing.
    """
    hass.states.async_set("sensor.price", "0.35")
    hass.states.async_set("sensor.grid", "2875")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )
    config.sources.append(_grid_meter())
    config.sources.append(_price_source())

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_PRICE] == 50.0


async def test_two_identical_homes_are_told_apart_by_what_they_draw(
    hass: HomeAssistant,
) -> None:
    """The sleeping house and the one with the dryer on score differently.

    The exact failure the old price component had: it measured the market, so
    both of these scored the same at the same moment (SPEC.md §35.4c).
    """
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )
    config.sources.append(_grid_meter())
    config.sources.append(_price_source())
    hass.states.async_set("sensor.price", "0.35")

    hass.states.async_set("sensor.grid", "100")
    asleep = Calculator(hass).calculate(config)
    hass.states.async_set("sensor.grid", "3000")
    drying = Calculator(hass).calculate(config)

    assert asleep.score_components[SCORE_COMPONENT_PRICE] > 95.0
    assert drying.score_components[SCORE_COMPONENT_PRICE] < 50.0


async def test_exporting_during_an_expensive_hour_is_full_marks(
    hass: HomeAssistant,
) -> None:
    """Nothing drawn is nothing drawn at the high price, so the axis is clean."""
    hass.states.async_set("sensor.price", "0.50")
    hass.states.async_set("sensor.grid", "-1500")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )
    config.sources.append(_grid_meter())
    config.sources.append(_price_source())

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_PRICE] == 100.0


async def test_panels_without_anything_movable_are_not_scored_on_solar(
    hass: HomeAssistant,
) -> None:
    """100% self-consumption is out of reach, so the axis is a discount.

    A home with panels, no battery and no complete flexible appliance cannot
    raise its self-consumption by any action at all (SPEC.md §35.4a).
    """
    hass.states.async_set("sensor.pv", "2000")
    hass.states.async_set("sensor.grid", "-1500")
    # The fixed price keeps the gate open, so this test is about the missing
    # movable load and not about an incomplete installation.
    config = _config(fixed_import_price_eur_kwh=0.30)
    config.sources.append(_grid_meter())
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.data_quality.missing_items == []
    assert SCORE_COMPONENT_SOLAR not in metrics.score_components
    assert metrics.energy_score is None
    assert metrics.score_unavailable_reason == SCORE_UNAVAILABLE_NOTHING_MOVABLE


async def test_an_incomplete_appliance_does_not_switch_the_solar_axis_on(
    hass: HomeAssistant,
) -> None:
    """A row with a name and a type is not something that can be advised on.

    Without the energy per cycle there is no saving to name, so the coach can
    say nothing concrete about this appliance — and an axis nobody can be
    advised on fails the advice rule.
    """
    hass.states.async_set("sensor.pv", "2000")
    hass.states.async_set("sensor.grid", "-1500")
    config = _config()
    config.sources.append(_grid_meter())
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
    config.devices.append(DeviceProfile(id="d1", device_type=DEVICE_TYPE_DISHWASHER))

    metrics = Calculator(hass).calculate(config)

    assert SCORE_COMPONENT_SOLAR not in metrics.score_components


async def test_an_inflexible_appliance_does_not_switch_the_solar_axis_on(
    hass: HomeAssistant,
) -> None:
    """A monitor-only device cannot be moved, so there is still nothing to shift."""
    hass.states.async_set("sensor.pv", "2000")
    hass.states.async_set("sensor.grid", "-1500")
    config = _config()
    config.sources.append(_grid_meter())
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
    config.devices.append(
        DeviceProfile.from_dict(
            {
                "id": "d1",
                "device_type": DEVICE_TYPE_GENERIC_MONITOR,
                "nominal_power_w": 2000.0,
                "energy_per_cycle_kwh": 1.2,
            }
        )
    )

    metrics = Calculator(hass).calculate(config)

    assert SCORE_COMPONENT_SOLAR not in metrics.score_components


async def test_a_battery_switches_the_solar_axis_on(hass: HomeAssistant) -> None:
    """A battery moves energy without anybody touching anything.

    The intended side effect (SPEC.md §35.4a): adding one turns the component
    on, so the ceiling and the bar rise together. Same readings as the test
    above, which scores nothing at all.
    """
    hass.states.async_set("sensor.pv", "2000")
    hass.states.async_set("sensor.grid", "-1500")
    config = _config()
    config.sources.append(_grid_meter())
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
    config.sources.append(_source(SOURCE_TYPE_HOME_BATTERY, "sensor.accu"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_SOLAR] == 25.0


async def test_a_missing_time_window_does_not_block_the_solar_axis(
    hass: HomeAssistant,
) -> None:
    """The boundary sits before the window, deliberately (SPEC.md §16).

    A device without a window may run at any hour, so it is *more* available
    for advice, not less. Counting the window here would punish the freer
    appliance and would charge for the checklist's own time-window item twice —
    which it still does, in the data quality, where it belongs.
    """
    hass.states.async_set("sensor.pv", "2000")
    hass.states.async_set("sensor.grid", "-500")
    config = _solar_home()

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_SOLAR] == 75.0
    assert COMPLETENESS_ITEM_TIME_WINDOWS in metrics.data_quality.missing_items


# --- Which sentence the tile gets, per situation ----------------------------
#
# **Rows are situations, not codes.** Every earlier test here picked a code and
# then went looking for a configuration that produced it, which proves a branch
# renders and says nothing about whether it is the right branch. That is how
# 0.4.1 shipped a tile telling a customer at nine in the evening that his
# panels were producing: the one test for `nothing_movable` set the production
# to 2000 W, and so did the browser check, so both layers agreed on the same
# blind spot (Sven, production, 2026-08-08).
#
# Read each row as the question a reader would ask: given this home, at this
# moment, which sentence belongs on the tile?


def _situation(
    hass: HomeAssistant,
    *,
    panels: bool,
    producing: bool,
    dynamic: bool,
    movable: bool,
    thresholds: bool = True,
) -> StoredConfiguration:
    """Build a home the gate lets through, varying only what the table varies.

    The grid meter and a price answer are always present because without them
    the gate shuts and every row would come back `incomplete_setup` — which is
    a real case, tested separately, and would hide every other row here.
    """
    hass.states.async_set("sensor.grid", "500")
    hass.states.async_set("sensor.pv", "2000" if producing else "0")
    hass.states.async_set("sensor.price", "0.10")

    overrides: dict[str, Any] = {"fixed_import_price_eur_kwh": 0.30}
    if dynamic:
        overrides["contract_type"] = CONTRACT_TYPE_DYNAMIC
        if thresholds:
            overrides["low_price_threshold_eur_kwh"] = 0.15
            overrides["high_price_threshold_eur_kwh"] = 0.35

    config = _config(**overrides)
    config.sources.append(_grid_meter())
    if dynamic:
        config.sources.append(_price_source())
    if panels:
        config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))
    if movable:
        config.devices.append(_movable_device())
    return config


@pytest.mark.parametrize(
    ("home", "expected"),
    [
        # No panels and a fixed tariff: nothing will ever vary. Permanent.
        (
            {"panels": False, "producing": False, "dynamic": False, "movable": False},
            SCORE_UNAVAILABLE_NO_VARIABLE_SIGNAL,
        ),
        # The sun is out and there is nothing to shift it to. The tariff does
        # not matter: this used to be reachable only on a fixed tariff, so a
        # dynamic home in the sun fell through to "je panelen leveren niets".
        (
            {"panels": True, "producing": True, "dynamic": False, "movable": False},
            SCORE_UNAVAILABLE_NOTHING_MOVABLE,
        ),
        (
            {"panels": True, "producing": True, "dynamic": True, "movable": False},
            SCORE_UNAVAILABLE_NOTHING_MOVABLE,
        ),
        # **The production bug.** Evening, panels idle, nothing movable. The
        # old condition read the solar *row* and claimed there was production.
        (
            {"panels": True, "producing": False, "dynamic": True, "movable": False},
            SCORE_UNAVAILABLE_NO_SUN_CHEAP_PRICE,
        ),
        (
            {"panels": True, "producing": False, "dynamic": False, "movable": False},
            SCORE_UNAVAILABLE_NO_SUN_FIXED_TARIFF,
        ),
        # Same evening, but this home can shift something. Same sentence: what
        # it lacks is sun, not an appliance.
        (
            {"panels": True, "producing": False, "dynamic": True, "movable": True},
            SCORE_UNAVAILABLE_NO_SUN_CHEAP_PRICE,
        ),
        (
            {"panels": True, "producing": False, "dynamic": False, "movable": True},
            SCORE_UNAVAILABLE_NO_SUN_FIXED_TARIFF,
        ),
        # No panels at all, so the sentence may not mention them.
        (
            {"panels": False, "producing": False, "dynamic": True, "movable": False},
            SCORE_UNAVAILABLE_CHEAP_PRICE,
        ),
        (
            {"panels": False, "producing": False, "dynamic": True, "movable": True},
            SCORE_UNAVAILABLE_CHEAP_PRICE,
        ),
        # Thresholds unset: we cannot claim the hour is cheap, and this one is
        # a shortcoming somebody can close.
        (
            {
                "panels": False,
                "producing": False,
                "dynamic": True,
                "movable": False,
                "thresholds": False,
            },
            SCORE_UNAVAILABLE_PRICE_THRESHOLDS_MISSING,
        ),
        (
            {
                "panels": True,
                "producing": False,
                "dynamic": True,
                "movable": False,
                "thresholds": False,
            },
            SCORE_UNAVAILABLE_PRICE_THRESHOLDS_MISSING,
        ),
    ],
)
async def test_which_sentence_the_tile_gets(
    hass: HomeAssistant, home: dict[str, bool], expected: str
) -> None:
    """One row per situation, asserting the choice rather than the rendering."""
    config = _situation(hass, **home)

    metrics = Calculator(hass).calculate(config)

    # The gate has to be open, or every row would answer `incomplete_setup`.
    # Only the unconditional items matter here; a movable appliance without a
    # ready window costs a checklist point and changes nothing about the tile.
    assert not [
        item
        for item in metrics.data_quality.missing_items
        if item in COMPLETENESS_UNCONDITIONAL_ITEMS
    ]
    assert metrics.energy_score is None
    assert metrics.score_unavailable_reason == expected


async def test_sun_plus_something_movable_is_a_score_and_not_a_sentence(
    hass: HomeAssistant,
) -> None:
    """The row the table above cannot contain, and the reason it cannot.

    Production with something to shift makes the solar component apply, so
    there is a number and no sentence at all. Asserting it here keeps the
    table's own claim honest — that every row it lists really is a case with
    no score.
    """
    config = _situation(hass, panels=True, producing=True, dynamic=False, movable=True)

    metrics = Calculator(hass).calculate(config)

    assert metrics.energy_score is not None
    assert metrics.score_unavailable_reason is None


async def test_a_home_without_a_variable_signal_never_gets_a_number(
    hass: HomeAssistant,
) -> None:
    """A fixed contract and no panels: no moment is better than another.

    Accepted consequence of the principle (SPEC.md §35.9). The tile explains
    itself rather than showing a dash, and the coach keeps working.
    """
    hass.states.async_set("sensor.grid", "1500")
    config = _config(contract_type=CONTRACT_TYPE_FIXED, fixed_import_price_eur_kwh=0.30)
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)

    assert metrics.data_quality.missing_items == []
    assert metrics.energy_score is None
    assert metrics.score_unavailable_reason == SCORE_UNAVAILABLE_NO_VARIABLE_SIGNAL


# --- The advice rule (SPEC.md §35.1, regel 2) -------------------------------
#
# Following the coach may never lower the score. These tests take an advice the
# coach can give, apply it to the readings, and compare the score before and
# after. It is the falsifiable half of the principle, and it is what removed
# `peak_component`: no re-anchoring of its slope could satisfy it.


async def test_charging_when_the_coach_says_so_does_not_lower_the_score(
    hass: HomeAssistant,
) -> None:
    """The 1x25 A case from SPEC.md §35.4b, which used to cost 10 to 16 points.

    Price low, coach says "charge the car now". Plugging in takes the home from
    400 W to 4100 W, which is 71% of a 5750 W connection. `peak_component`
    scored that 100 -> 57 in the same minute the advice was given.

    The load is still measured and still warns — it is only out of the score.
    """
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )
    config.sources.append(_grid_meter())
    config.sources.append(_price_source())
    hass.states.async_set("sensor.price", "0.10")

    hass.states.async_set("sensor.grid", "400")
    before = Calculator(hass).calculate(config)
    hass.states.async_set("sensor.grid", "4100")
    after = Calculator(hass).calculate(config)

    assert after.score_components == before.score_components
    assert after.energy_score == before.energy_score
    # The warning side is untouched: the load is still tracked and still rises.
    assert after.grid_load_percent is not None
    assert before.grid_load_percent is not None
    assert after.grid_load_percent > before.grid_load_percent


async def test_using_the_solar_surplus_raises_the_score(
    hass: HomeAssistant,
) -> None:
    """The coach's own advice, and the score has to agree with it.

    Producing 2000 W while exporting 1500 is 25% self-consumption. Starting the
    dishwasher on that surplus leaves nothing going out, which is 100.
    """
    config = _solar_home()
    hass.states.async_set("sensor.pv", "2000")

    hass.states.async_set("sensor.grid", "-1500")
    before = Calculator(hass).calculate(config)
    hass.states.async_set("sensor.grid", "0")
    after = Calculator(hass).calculate(config)

    assert before.score_components[SCORE_COMPONENT_SOLAR] == 25.0
    assert after.score_components[SCORE_COMPONENT_SOLAR] == 100.0
    assert after.energy_score is not None
    assert before.energy_score is not None
    assert after.energy_score > before.energy_score


async def test_waiting_out_an_expensive_hour_raises_the_score(
    hass: HomeAssistant,
) -> None:
    """Advice to wait out an expensive hour has to move the number with it."""
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )
    config.sources.append(_grid_meter())
    config.sources.append(_price_source())
    hass.states.async_set("sensor.price", "0.35")

    hass.states.async_set("sensor.grid", "3000")
    running = Calculator(hass).calculate(config)
    hass.states.async_set("sensor.grid", "300")
    waited = Calculator(hass).calculate(config)

    assert waited.energy_score is not None
    assert running.energy_score is not None
    assert waited.energy_score > running.energy_score


async def test_metrics_serialise_for_the_frontend(hass: HomeAssistant) -> None:
    """Everything the calculator produces survives the trip to the panel."""
    hass.states.async_set("sensor.grid", "1500")
    config = _config()
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)
    restored = type(metrics).from_dict(metrics.to_dict())

    assert restored.grid_power_w == metrics.grid_power_w
    assert restored.energy_score == metrics.energy_score
    assert restored.score_components == metrics.score_components
    assert restored.score_unavailable_reason == metrics.score_unavailable_reason
    assert restored.data_quality.score == metrics.data_quality.score


async def test_a_market_price_keeps_the_reading_it_was_derived_from(
    hass: HomeAssistant,
) -> None:
    """The panel shows the conversion, so the raw reading has to survive.

    An all-in figure with no way to check it against the sensor asks the
    installer to trust a multiplication they cannot see (SPEC.md §8).
    """
    hass.states.async_set("sensor.price", "0.08")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        energy_tax_eur_kwh=0.1088,
        supplier_markup_eur_kwh=0.02,
    )
    config.sources.append(_price_source(price_basis=PRICE_BASIS_MARKET))

    metrics = Calculator(hass).calculate(config)

    assert metrics.market_price_eur_kwh == 0.08
    assert metrics.current_price_eur_kwh == pytest.approx(0.2088 * 1.21)


async def test_an_all_in_price_has_no_market_price_to_show(
    hass: HomeAssistant,
) -> None:
    """Nothing extra to show: the two numbers would be the same one."""
    hass.states.async_set("sensor.price", "0.28")
    config = _config(contract_type=CONTRACT_TYPE_DYNAMIC)
    config.sources.append(_price_source())

    metrics = Calculator(hass).calculate(config)

    assert metrics.current_price_eur_kwh == 0.28
    assert metrics.market_price_eur_kwh is None


async def test_a_refused_price_leaves_no_market_price_behind(
    hass: HomeAssistant,
) -> None:
    """A price that is not used may not leave a figure on the Overzicht."""
    hass.states.async_set("sensor.price", "0.08")
    config = _config(contract_type=CONTRACT_TYPE_DYNAMIC)
    config.sources.append(_price_source(price_basis=PRICE_BASIS_MARKET))

    metrics = Calculator(hass).calculate(config)

    assert metrics.current_price_eur_kwh is None
    assert metrics.market_price_eur_kwh is None


def test_the_checklist_asks_a_device_for_exactly_these_fields() -> None:
    """Pin what a device must have, because a form marks its fields from it.

    The Apparaten tab marks "· nodig" on the fields the data quality checklist
    needs, and that marking is written in JavaScript where this rule cannot be
    imported. This test is the guard: change what `completeness.py` asks of a
    device and it fails here, instead of leaving the form quietly marking the
    wrong things.

    The rule, in full:

    * ``device_profile_complete`` wants one **advisable** device with a nominal
      power and an energy per cycle;
    * ``flexible_devices_have_time_window`` wants a window on every advisable
      device, and one bound is a window.

    Both are asked only of an appliance the coach can advise about. An
    appliance that is only measured needs neither, because both fields exist to
    produce advice.
    """
    snapshot = EnergySnapshot()

    def _score(**overrides: Any) -> DataQualityResult:
        device = DeviceProfile(id="d1", device_type=DEVICE_TYPE_DISHWASHER, **overrides)
        config = StoredConfiguration(devices=[device])
        return evaluate_completeness(config, snapshot)

    complete: dict[str, Any] = {
        "nominal_power_w": 2000.0,
        "energy_per_cycle_kwh": 1.2,
        "ready_from": "22:00",
        "ready_before": "06:00",
    }

    passed = _score(**complete).completed_items
    assert COMPLETENESS_ITEM_DEVICE_PROFILE in passed
    assert COMPLETENESS_ITEM_TIME_WINDOWS in passed

    # Drop either power field and the device profile item fails.
    for field_name in ("nominal_power_w", "energy_per_cycle_kwh"):
        without = _score(**{**complete, field_name: None})
        assert COMPLETENESS_ITEM_DEVICE_PROFILE in without.missing_items, field_name

    # **Dropping one *bound* does not fail the window item, and this loop used
    # to assert that it did.** That was true under the old start window, where
    # half a window was undefined; it survived the rename to `ready_from` /
    # `ready_before` because search-and-replace kept it compiling while the
    # meaning underneath had changed. A production install with only a deadline
    # then lost ten points for the configuration the ready window exists to
    # allow (SPEC.md §32).
    for field_name in ("ready_from", "ready_before"):
        one_bound = _score(**{**complete, field_name: None})
        assert COMPLETENESS_ITEM_TIME_WINDOWS in one_bound.completed_items, field_name

    # Dropping both is what leaves nothing stated.
    neither = _score(**{**complete, "ready_from": None, "ready_before": None})
    assert COMPLETENESS_ITEM_TIME_WINDOWS in neither.missing_items

    # **An appliance nobody will be advised about is asked neither question**
    # (0.6.1). Both items exist to sharpen advice, so for an appliance the
    # coach will never mention they are not asked at all rather than counted as
    # missing — a penalty with no remedy. This assertion used to demand the
    # profile item of an inflexible device, which is how a tablet charger on a
    # smart plug was told its energy per cycle was missing.
    inflexible = _score(is_flexible=False)
    assert COMPLETENESS_ITEM_DEVICE_PROFILE in inflexible.not_applicable_items
    assert COMPLETENESS_ITEM_TIME_WINDOWS in inflexible.not_applicable_items
    # Neither is reported as a gap. The three unconditional items are missing
    # here because this configuration has no home profile, grid or price; they
    # are not what this test is about.
    assert COMPLETENESS_ITEM_DEVICE_PROFILE not in inflexible.missing_items
    assert COMPLETENESS_ITEM_TIME_WINDOWS not in inflexible.missing_items

    # The resident's own off switch does the same thing on the other axis.
    monitored = _score(control_mode=CONTROL_MONITOR_ONLY)
    assert COMPLETENESS_ITEM_DEVICE_PROFILE in monitored.not_applicable_items
    assert COMPLETENESS_ITEM_TIME_WINDOWS in monitored.not_applicable_items
