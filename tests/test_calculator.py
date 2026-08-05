"""Tests for the calculation engine (SPEC.md §24 "Rekenmotor").

Covers the calculator list from SPEC.md §24: a signed grid meter in both
directions, separate import/export, solar surplus via the meter and via
consumption, no reliable calculation at all, peak warning, and the data quality
checklist and energy score.
"""

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
    COMPLETENESS_POINTS,
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
    SCORE_COMPONENT_DATA_QUALITY,
    SCORE_COMPONENT_FLEXIBILITY,
    SCORE_COMPONENT_PEAK,
    SCORE_COMPONENT_PRICE,
    SCORE_COMPONENT_SOLAR,
    SOURCE_TYPE_CURRENT_PRICE,
    SOURCE_TYPE_GENERAL_CONSUMPTION,
    SOURCE_TYPE_GRID_METER,
    SOURCE_TYPE_HOME_BATTERY,
    SOURCE_TYPE_SOLAR,
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
    """Nothing configured means no points at all."""
    result = evaluate_completeness(StoredConfiguration(), EnergySnapshot())

    assert result.score == 0
    assert result.completed_items == []
    assert len(result.missing_items) == len(COMPLETENESS_POINTS)


def test_each_checklist_item_is_worth_its_documented_points() -> None:
    """The weights are the ones in the SPEC.md §16 table."""
    config = _config(contract_type=CONTRACT_TYPE_FIXED, fixed_import_price_eur_kwh=0.28)
    config.devices.append(
        DeviceProfile(
            id="d1",
            device_type=DEVICE_TYPE_DISHWASHER,
            nominal_power_w=2000.0,
            energy_per_cycle_kwh=1.2,
            earliest_start="08:00",
            latest_finish="23:00",
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
            earliest_start="08:00",
            latest_finish="23:00",
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
            earliest_start="08:00",
            latest_finish="23:00",
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
    price = _source(SOURCE_TYPE_CURRENT_PRICE, "sensor.price")
    price.binding = EntityBinding(entity_id="sensor.price", unit=UNIT_EUR_KWH)
    config.sources.append(price)
    config.devices.append(
        DeviceProfile(
            id="d1",
            device_type=DEVICE_TYPE_DISHWASHER,
            nominal_power_w=2000.0,
            energy_per_cycle_kwh=1.2,
            earliest_start="08:00",
            latest_finish="23:00",
        )
    )

    metrics = Calculator(hass).calculate(config)

    # Data quality 100, load 50% -> peak 100, surplus 2875 >= 500 -> solar 100,
    # price 0.20 between 0.15 and 0.35 -> 75, one flexible device -> 100.
    assert metrics.score_components == {
        SCORE_COMPONENT_DATA_QUALITY: 100.0,
        SCORE_COMPONENT_PEAK: 100.0,
        SCORE_COMPONENT_SOLAR: 100.0,
        SCORE_COMPONENT_PRICE: 75.0,
        SCORE_COMPONENT_FLEXIBILITY: 100.0,
    }
    # 0.30x100 + 0.25x100 + 0.20x100 + 0.15x75 + 0.10x100 = 96.25 -> 96
    assert metrics.energy_score == 96


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


async def test_an_unknown_surplus_scores_no_solar_points(
    hass: HomeAssistant,
) -> None:
    """SPEC.md §16 is explicit that unknown surplus scores zero."""
    config = _config()

    metrics = Calculator(hass).calculate(config)

    assert metrics.solar_surplus_w is None
    assert metrics.score_components[SCORE_COMPONENT_SOLAR] == 0.0


async def test_a_partial_surplus_scores_proportionally(
    hass: HomeAssistant,
) -> None:
    """Half the required surplus is half the solar component."""
    hass.states.async_set("sensor.grid", "-250")
    config = _config(min_solar_surplus_w=500.0)
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_SOLAR] == 50.0


async def test_a_zero_minimum_surplus_scores_on_presence_alone(
    hass: HomeAssistant,
) -> None:
    """With no minimum configured, any surplus at all is full marks."""
    hass.states.async_set("sensor.grid", "-100")
    config = _config(min_solar_surplus_w=0.0)
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_SOLAR] == 100.0


async def test_a_zero_minimum_without_surplus_scores_nothing(
    hass: HomeAssistant,
) -> None:
    """No surplus is no surplus, whatever the minimum is set to."""
    hass.states.async_set("sensor.grid", "1000")
    config = _config(min_solar_surplus_w=0.0)
    config.sources.append(_grid_meter())

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_SOLAR] == 0.0


async def test_a_fixed_contract_scores_a_neutral_price(
    hass: HomeAssistant,
) -> None:
    """A fixed contract has no price signal, so the component is 50."""
    config = _config(contract_type=CONTRACT_TYPE_FIXED)

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_PRICE] == 50.0


async def test_a_dynamic_contract_without_a_price_is_neutral(
    hass: HomeAssistant,
) -> None:
    """An undeterminable component is neutral, not zero."""
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_PRICE] == 50.0


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
    price = _source(SOURCE_TYPE_CURRENT_PRICE, "sensor.price")
    price.binding = EntityBinding(entity_id="sensor.price", unit=UNIT_EUR_KWH)
    config.sources.append(price)

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
    price = _source(SOURCE_TYPE_CURRENT_PRICE, "sensor.price")
    price.binding = EntityBinding(entity_id="sensor.price", unit=UNIT_EUR_KWH)
    config.sources.append(price)

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_PRICE] == 0.0


async def test_a_usable_flexible_device_scores_the_flexibility_points(
    hass: HomeAssistant,
) -> None:
    """One usable flexible device is enough for the full component."""
    config = _config()
    config.devices.append(DeviceProfile(id="d1", device_type=DEVICE_TYPE_DISHWASHER))

    metrics = Calculator(hass).calculate(config)

    assert metrics.score_components[SCORE_COMPONENT_FLEXIBILITY] == 100.0


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
