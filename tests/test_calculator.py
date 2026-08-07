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
    COMPONENT_MAX,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONTRACT_TYPE_DYNAMIC,
    CONTRACT_TYPE_FIXED,
    DEVICE_TYPE_DISHWASHER,
    DEVICE_TYPE_GENERIC_MONITOR,
    METER_MODE_SEPARATE,
    METER_MODE_SINGLE_SIGNED,
    POSITIVE_MEANS_EXPORT,
    POSITIVE_MEANS_IMPORT,
    PRICE_BASIS_ALL_IN,
    PRICE_BASIS_MARKET,
    SCORE_COMPONENT_DATA_QUALITY,
    SCORE_COMPONENT_FLEXIBILITY,
    SCORE_COMPONENT_PEAK,
    SCORE_COMPONENT_PRICE,
    SCORE_COMPONENT_SOLAR,
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
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
        energy_tax_eur_kwh=0.1088,
        supplier_markup_eur_kwh=0.02,
    )
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


def test_quarantined_rows_are_counted_as_invalid_items() -> None:
    """SPEC.md §12: a row with an unrecognised type counts as invalid."""
    config = _config()
    config.sources.append(EnergySource(id="s1", type="grid_metre"))
    config.devices.append(DeviceProfile(id="d1", device_type="heatpump"))

    result = evaluate_completeness(config, EnergySnapshot(invalid_source_ids=["s2"]))

    assert result.invalid_items == ["s1", "s2", "d1"]


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

    # Data quality 100, load 50% -> peak 100, price 0.20 between 0.15 and 0.35
    # -> 75, one flexible device -> 100. Solar: producing 3000 W and exporting
    # 2875 leaves 125 W used at home, so 4.17% self-consumption — the old
    # definition scored this a perfect 100 for exporting almost everything.
    assert metrics.score_components == {
        SCORE_COMPONENT_DATA_QUALITY: 100.0,
        SCORE_COMPONENT_PEAK: 100.0,
        SCORE_COMPONENT_SOLAR: 4.17,
        SCORE_COMPONENT_PRICE: 75.0,
        SCORE_COMPONENT_FLEXIBILITY: 100.0,
    }
    # All five apply, so the weights still sum to 1.0 and no rescaling happens:
    # 0.30x100 + 0.25x100 + 0.20x4.17 + 0.15x75 + 0.10x100 = 77.08 -> 77
    assert metrics.energy_score == 77
    assert metrics.not_applicable_components == []


async def test_the_peak_component_falls_linearly(hass: HomeAssistant) -> None:
    """100 below half load, 0 at full load, straight line between."""
    hass.states.async_set("sensor.grid", "4312.5")
    config = _config()
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)

    assert metrics.grid_load_percent == 75.0
    assert metrics.score_components[SCORE_COMPONENT_PEAK] == 50.0


async def test_a_full_load_scores_no_peak_points(hass: HomeAssistant) -> None:
    """At and above the maximum the peak component is zero."""
    hass.states.async_set("sensor.grid", "6000")
    config = _config()
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_PEAK] == 0.0


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
    config = _config()
    config.sources.append(_grid_meter())
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_SOLAR] == 75.0


async def test_consuming_all_production_is_full_marks(hass: HomeAssistant) -> None:
    """Nothing exported means everything used at home.

    Under the old definition this was the *worst* possible score, because the
    surplus it measured was zero.
    """
    hass.states.async_set("sensor.pv", "2000")
    hass.states.async_set("sensor.grid", "300")
    config = _config()
    config.sources.append(_grid_meter())
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_SOLAR] == 100.0


async def test_exporting_everything_scores_nothing(hass: HomeAssistant) -> None:
    """All production going out to the grid is none of it used at home."""
    hass.states.async_set("sensor.pv", "2000")
    hass.states.async_set("sensor.grid", "-2000")
    config = _config()
    config.sources.append(_grid_meter())
    config.sources.append(_source(SOURCE_TYPE_SOLAR, "sensor.pv"))

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


async def test_a_dynamic_contract_without_a_price_scores_zero(
    hass: HomeAssistant,
) -> None:
    """Unknown is not the same as not applicable (SPEC.md §16)."""
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_PRICE] == 0.0


async def test_a_dynamic_contract_without_thresholds_scores_zero(
    hass: HomeAssistant,
) -> None:
    """A price without thresholds to judge it by is just as unknown."""
    hass.states.async_set("sensor.price", "0.20")
    config = _config(contract_type=CONTRACT_TYPE_DYNAMIC)
    config.sources.append(_price_source())

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_PRICE] == 0.0


async def test_an_unknown_grid_load_scores_no_peak_points(
    hass: HomeAssistant,
) -> None:
    """The grid load is always applicable, so not knowing it scores zero."""
    config = _config()
    config.home.max_grid_power_w = None

    metrics = Calculator(hass).calculate(config)

    assert metrics.grid_load_percent is None
    assert metrics.score_components[SCORE_COMPONENT_PEAK] == 0.0


async def test_a_half_configured_installation_scores_poorly(
    hass: HomeAssistant,
) -> None:
    """The whole point of the distinction: no comfortable score for nothing.

    An empty configuration is judged on the two unconditional components, and
    fails both, so it scores a clean zero. It used to score 8, entirely from the
    50 that a fixed contract was handed for free — a number earned by having
    configured nothing at all.
    """
    metrics = Calculator(hass).calculate(StoredConfiguration())

    # Data quality 0 and peak unknown 0 are all that apply; solar, price and
    # flexibility have nothing to judge.
    assert metrics.energy_score == 0
    assert set(metrics.not_applicable_components) == {
        SCORE_COMPONENT_SOLAR,
        SCORE_COMPONENT_PRICE,
        SCORE_COMPONENT_FLEXIBILITY,
    }


async def test_a_price_below_the_low_threshold_scores_full(
    hass: HomeAssistant,
) -> None:
    """At or below the low threshold the price component is 100."""
    hass.states.async_set("sensor.price", "0.10")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )
    config.sources.append(_price_source())

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_PRICE] == 100.0


async def test_a_price_above_the_high_threshold_scores_zero(
    hass: HomeAssistant,
) -> None:
    """At or above the high threshold the price component is 0."""
    hass.states.async_set("sensor.price", "0.50")
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )
    config.sources.append(_price_source())

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_PRICE] == 0.0


async def test_a_device_with_only_a_name_scores_no_flexibility_points(
    hass: HomeAssistant,
) -> None:
    """Adding an empty row may not raise the score (SPEC.md §16).

    Before this, "usable and flexible" was the whole test, and a row with
    nothing but a name and a type satisfied it — so adding a blank appliance was
    worth ten points. A meter that rewards having created something rather than
    what the home can do is not measuring anything.
    """
    config = _config()
    config.devices.append(DeviceProfile(id="d1", device_type=DEVICE_TYPE_DISHWASHER))

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_FLEXIBILITY] == 0.0


async def test_half_a_device_scores_no_flexibility_points(
    hass: HomeAssistant,
) -> None:
    """Either field on its own is still not something to advise about."""
    config = _config()
    config.devices.append(
        DeviceProfile(
            id="d1", device_type=DEVICE_TYPE_DISHWASHER, nominal_power_w=2000.0
        )
    )

    metrics = Calculator(hass).calculate(config)

    # Without the energy per cycle there is no saving to name, so advice about
    # this appliance would say nothing concrete.
    assert metrics.score_components[SCORE_COMPONENT_FLEXIBILITY] == 0.0


async def test_a_complete_flexible_device_scores_the_flexibility_points(
    hass: HomeAssistant,
) -> None:
    """Power and energy per cycle are what make it count."""
    config = _config()
    config.devices.append(
        DeviceProfile(
            id="d1",
            device_type=DEVICE_TYPE_DISHWASHER,
            nominal_power_w=2000.0,
            energy_per_cycle_kwh=1.2,
        )
    )

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_FLEXIBILITY] == 100.0


async def test_a_missing_time_window_does_not_cost_flexibility_points(
    hass: HomeAssistant,
) -> None:
    """The boundary sits before the window, deliberately (SPEC.md §16).

    A device without a window may run at any hour, so it is *more* available for
    advice, not less. Counting the window here would punish the freer appliance
    and would charge for the checklist's own time-window item twice — which it
    still does, in the data quality, where it belongs.
    """
    config = _config()
    config.devices.append(
        DeviceProfile(
            id="d1",
            device_type=DEVICE_TYPE_DISHWASHER,
            nominal_power_w=2000.0,
            energy_per_cycle_kwh=1.2,
        )
    )

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_FLEXIBILITY] == 100.0
    assert COMPLETENESS_ITEM_TIME_WINDOWS in metrics.data_quality.missing_items


async def test_only_inflexible_devices_score_no_flexibility_points(
    hass: HomeAssistant,
) -> None:
    """A monitor-only device cannot be moved, so it earns nothing here."""
    config = _config()
    config.devices.append(
        DeviceProfile.from_dict(
            {"id": "d1", "device_type": DEVICE_TYPE_GENERIC_MONITOR}
        )
    )

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_FLEXIBILITY] == 0.0


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

    * ``device_profile_complete`` wants one usable device with **both** a
      nominal power and an energy per cycle;
    * ``flexible_devices_have_time_window`` wants **both** ends of a window on
      every usable flexible device.
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

    # A device that is not flexible is never moved, so it needs no window — and
    # the item is therefore not asked at all rather than counted as missing. A
    # home whose only appliance cannot be moved has nothing to fix here, so
    # holding ten points back from it would be a penalty with no remedy.
    inflexible = _score(
        nominal_power_w=2000.0, energy_per_cycle_kwh=1.2, is_flexible=False
    )
    assert COMPLETENESS_ITEM_DEVICE_PROFILE in inflexible.completed_items
    assert COMPLETENESS_ITEM_TIME_WINDOWS in inflexible.not_applicable_items
    assert COMPLETENESS_ITEM_TIME_WINDOWS not in inflexible.missing_items
