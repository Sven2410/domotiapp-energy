"""Tests for the advisor and the coach provider (SPEC.md §24).

Covers the advice half of the SPEC.md §24 calculator list: price advice
suppressed on a fixed contract, quiet hours including a window across midnight,
advice priority and sorting, the neutral situation, and the savings threshold.
"""

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant

from custom_components.domotiapp_energy.const import (
    CONFIDENCE_HIGH,
    CONTRACT_TYPE_DYNAMIC,
    CONTRACT_TYPE_FIXED,
    DEVICE_TYPE_DISHWASHER,
    DEVICE_TYPE_EV_CHARGER,
    DEVICE_TYPE_GENERIC_MONITOR,
    EXPLANATION_KEYS,
    PRIORITY_HIGH,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)
from custom_components.domotiapp_energy.engine.advisor import Advisor
from custom_components.domotiapp_energy.engine.providers import (
    CoachProvider,
    ExtensionCoachProvider,
    RuleBasedCoachProvider,
)
from custom_components.domotiapp_energy.engine.reason_codes import (
    REASON_HIGH_ENERGY_PRICE,
    REASON_HIGH_GRID_LOAD,
    REASON_LOW_ENERGY_PRICE,
    REASON_MISSING_REQUIRED_DATA,
    REASON_NEUTRAL_ENERGY_SITUATION,
    REASON_SOLAR_SURPLUS_AVAILABLE,
)
from custom_components.domotiapp_energy.models import (
    AdviceItem,
    CoachResult,
    DataQualityResult,
    DeviceProfile,
    EnergyMetrics,
    HomeProfile,
    StoredConfiguration,
    UserPreferences,
)

# Every checklist item passed, so "missing data" never fires by accident.
_COMPLETE = DataQualityResult(score=100, completed_items=["all"], missing_items=[])


def _config(**home_overrides: Any) -> StoredConfiguration:
    """Return a configuration whose home profile is complete."""
    return StoredConfiguration(
        home=HomeProfile(main_fuse_a=25, max_grid_power_w=5750.0, **home_overrides)
    )


def _metrics(**overrides: Any) -> EnergyMetrics:
    """Return metrics with a complete checklist and no problems."""
    defaults: dict[str, Any] = {
        "data_quality": _COMPLETE,
        "grid_power_w": 500.0,
        "grid_load_percent": 8.7,
        "energy_score": 80,
    }
    return EnergyMetrics(**(defaults | overrides))


def _device(**overrides: Any) -> DeviceProfile:
    """Return a usable, flexible dishwasher built the way storage builds one."""
    data: dict[str, Any] = {
        "id": "d1",
        "name": "Vaatwasser",
        "device_type": DEVICE_TYPE_DISHWASHER,
        "nominal_power_w": 2000.0,
        "energy_per_cycle_kwh": 1.0,
    }
    return DeviceProfile.from_dict(data | overrides)


def _codes(advice: list[AdviceItem]) -> list[str]:
    """Return the reason codes in the order the advisor produced them."""
    return [item.reason_code for item in advice]


TIME_ZONE = "Europe/Amsterdam"


def local(hour: int, minute: int = 0) -> datetime:
    """Return the UTC instant at which the wall clock in TIME_ZONE reads this.

    Time windows and quiet hours are evaluated in the Home Assistant timezone
    via dt_util.now() (SPEC.md §16), so a test that wants "23:30 at night" has
    to freeze the matching UTC moment, not 23:30 UTC.
    """
    return datetime(2026, 8, 5, hour, minute, tzinfo=ZoneInfo(TIME_ZONE)).astimezone(
        UTC
    )


@pytest.fixture(autouse=True)
async def _midday(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Run in a real timezone, frozen at midday, outside the quiet hours."""
    await hass.config.async_set_time_zone(TIME_ZONE)
    freezer.move_to(local(12, 0))


# --- The neutral situation --------------------------------------------------


async def test_nothing_to_advise_yields_exactly_one_neutral_advice(
    hass: HomeAssistant,
) -> None:
    """SPEC.md §16: there is always exactly one primary advice."""
    advice = Advisor().generate(_config(), _metrics())

    assert len(advice) == 1
    assert advice[0].reason_code == REASON_NEUTRAL_ENERGY_SITUATION
    assert advice[0].severity == SEVERITY_INFO


# --- Missing data -----------------------------------------------------------


async def test_missing_data_is_advised_first(hass: HomeAssistant) -> None:
    """Incomplete input outranks everything else that might be said."""
    metrics = _metrics(
        data_quality=DataQualityResult(score=45, missing_items=["grid_source_valid"]),
        grid_load_percent=95.0,
        peak_risk=True,
    )

    advice = Advisor().generate(_config(), metrics)

    assert _codes(advice)[0] == REASON_MISSING_REQUIRED_DATA
    assert REASON_HIGH_GRID_LOAD in _codes(advice)


# --- Peak load --------------------------------------------------------------


async def test_peak_risk_produces_a_warning(hass: HomeAssistant) -> None:
    """A peak risk is a warning, with the measurement attached."""
    metrics = _metrics(grid_power_w=5000.0, grid_load_percent=87.0, peak_risk=True)

    advice = Advisor().generate(_config(), metrics)

    assert advice[0].reason_code == REASON_HIGH_GRID_LOAD
    assert advice[0].severity == SEVERITY_WARNING
    assert advice[0].measurements["netbelasting_procent"] == 87.0


async def test_no_peak_risk_produces_no_peak_advice(hass: HomeAssistant) -> None:
    """Without a risk the rule stays silent."""
    advice = Advisor().generate(_config(), _metrics(peak_risk=False))

    assert REASON_HIGH_GRID_LOAD not in _codes(advice)


# --- Solar surplus ----------------------------------------------------------


async def test_enough_surplus_suggests_a_flexible_device(
    hass: HomeAssistant,
) -> None:
    """A surplus above the minimum names a device that could use it."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0, solar_surplus_confidence=CONFIDENCE_HIGH)

    advice = Advisor().generate(config, metrics)

    assert advice[0].reason_code == REASON_SOLAR_SURPLUS_AVAILABLE
    assert advice[0].related_device_ids == ["d1"]
    assert "Vaatwasser" in advice[0].message
    assert advice[0].measurements["zonneoverschot_w"] == 1500.0


async def test_a_surplus_below_the_minimum_advises_nothing(
    hass: HomeAssistant,
) -> None:
    """The configured minimum is a real threshold, not a suggestion."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=200.0)

    assert _codes(Advisor().generate(config, metrics)) == [
        REASON_NEUTRAL_ENERGY_SITUATION
    ]


async def test_surplus_without_a_device_advises_nothing(
    hass: HomeAssistant,
) -> None:
    """Advice names a device; without one there is nothing to suggest."""
    config = _config(min_solar_surplus_w=500.0)
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(
        Advisor().generate(config, metrics)
    )


async def test_an_inflexible_device_is_never_suggested(
    hass: HomeAssistant,
) -> None:
    """A monitor-only device cannot be moved, so it is not advised."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(
        DeviceProfile.from_dict(
            {"id": "d1", "name": "Meter", "device_type": DEVICE_TYPE_GENERIC_MONITOR}
        )
    )
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(
        Advisor().generate(config, metrics)
    )


async def test_prefer_solar_switched_off_suppresses_the_advice(
    hass: HomeAssistant,
) -> None:
    """The preference is honoured, not overruled by a good opportunity."""
    config = _config(min_solar_surplus_w=500.0)
    config.preferences = UserPreferences(prefer_solar=False)
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(
        Advisor().generate(config, metrics)
    )


async def test_the_surplus_confidence_travels_with_the_advice(
    hass: HomeAssistant,
) -> None:
    """The advice is never more certain than the calculation behind it."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0, solar_surplus_confidence="medium")

    assert Advisor().generate(config, metrics)[0].confidence == "medium"


# --- Time windows -----------------------------------------------------------


async def test_a_device_outside_its_window_is_not_suggested(
    hass: HomeAssistant,
) -> None:
    """At midday a device allowed only in the evening is not advised."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(earliest_start="18:00", latest_finish="23:00"))
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(
        Advisor().generate(config, metrics)
    )


async def test_a_device_inside_its_window_is_suggested(
    hass: HomeAssistant,
) -> None:
    """The same device inside its window is fair game."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(earliest_start="08:00", latest_finish="18:00"))
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


async def test_a_midnight_window_covers_the_evening(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A 22:00-06:00 device is eligible at 23:30 (SPEC.md §16)."""
    freezer.move_to(local(23, 30))
    config = _config(min_solar_surplus_w=500.0)
    config.preferences = UserPreferences(allow_advice_during_quiet_hours=True)
    config.devices.append(_device(earliest_start="22:00", latest_finish="06:00"))
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


async def test_a_midnight_window_covers_the_small_hours(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The same window still applies after midnight."""
    freezer.move_to(local(3, 0))
    config = _config(min_solar_surplus_w=500.0)
    config.preferences = UserPreferences(allow_advice_during_quiet_hours=True)
    config.devices.append(_device(earliest_start="22:00", latest_finish="06:00"))
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


async def test_a_midnight_window_excludes_the_day(
    hass: HomeAssistant,
) -> None:
    """At midday the 22:00-06:00 device is outside its window."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(earliest_start="22:00", latest_finish="06:00"))
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(
        Advisor().generate(config, metrics)
    )


async def test_quiet_hours_still_silence_a_noisy_midnight_device(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Being inside its own window does not lift the quiet hours rule."""
    freezer.move_to(local(23, 30))
    config = _config(min_solar_surplus_w=500.0)
    config.preferences = UserPreferences(
        quiet_hours_start="22:00", quiet_hours_end="07:00"
    )
    config.devices.append(_device(earliest_start="22:00", latest_finish="06:00"))
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(
        Advisor().generate(config, metrics)
    )


async def test_a_window_with_equal_ends_is_never_open(
    hass: HomeAssistant,
) -> None:
    """An ambiguous window is refused rather than read as a full day."""
    config = _config(min_solar_surplus_w=500.0)
    device = _device()
    device.earliest_start = "12:00"
    device.latest_finish = "12:00"
    config.devices.append(device)
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(
        Advisor().generate(config, metrics)
    )


async def test_a_device_without_a_window_is_always_eligible(
    hass: HomeAssistant,
) -> None:
    """No window means no restriction, not "never"."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


# --- Quiet hours ------------------------------------------------------------


async def test_a_noisy_device_is_silenced_during_quiet_hours(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A dishwasher is noisy by default and is not advised at night."""
    freezer.move_to(local(23, 30))
    config = _config(min_solar_surplus_w=500.0)
    config.preferences = UserPreferences(
        quiet_hours_start="22:00", quiet_hours_end="07:00"
    )
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(
        Advisor().generate(config, metrics)
    )


async def test_the_quiet_window_wraps_around_midnight(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """22:00-07:00 also covers the small hours (SPEC.md §16)."""
    freezer.move_to(local(3, 0))
    config = _config(min_solar_surplus_w=500.0)
    config.preferences = UserPreferences(
        quiet_hours_start="22:00", quiet_hours_end="07:00"
    )
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(
        Advisor().generate(config, metrics)
    )


async def test_just_outside_the_quiet_window_is_allowed(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The end of the window is exclusive: at 07:00 advice resumes."""
    freezer.move_to(local(7, 0))
    config = _config(min_solar_surplus_w=500.0)
    config.preferences = UserPreferences(
        quiet_hours_start="22:00", quiet_hours_end="07:00"
    )
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


async def test_quiet_hours_can_be_overridden(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The installer may allow advice during quiet hours anyway."""
    freezer.move_to(local(23, 30))
    config = _config(min_solar_surplus_w=500.0)
    config.preferences = UserPreferences(
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
        allow_advice_during_quiet_hours=True,
    )
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


async def test_a_quiet_device_is_not_silenced(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Quiet hours only silence devices marked as noisy."""
    freezer.move_to(local(23, 30))
    config = _config(min_solar_surplus_w=500.0)
    config.preferences = UserPreferences(
        quiet_hours_start="22:00", quiet_hours_end="07:00"
    )
    config.devices.append(_device(device_type=DEVICE_TYPE_EV_CHARGER, name="Laadpaal"))
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


# --- Price advice -----------------------------------------------------------


async def test_a_low_price_is_advised_on_a_dynamic_contract(
    hass: HomeAssistant,
) -> None:
    """Below the low threshold the advisor says so."""
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )
    metrics = _metrics(current_price_eur_kwh=0.10)

    advice = Advisor().generate(config, metrics)

    assert advice[0].reason_code == REASON_LOW_ENERGY_PRICE
    assert advice[0].measurements["prijs_eur_kwh"] == 0.10


async def test_a_high_price_is_advised_on_a_dynamic_contract(
    hass: HomeAssistant,
) -> None:
    """Above the high threshold the advisor warns."""
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )
    metrics = _metrics(current_price_eur_kwh=0.50)

    advice = Advisor().generate(config, metrics)

    assert advice[0].reason_code == REASON_HIGH_ENERGY_PRICE
    assert advice[0].severity == SEVERITY_WARNING


async def test_price_advice_is_suppressed_on_a_fixed_contract(
    hass: HomeAssistant,
) -> None:
    """SPEC.md §16: never on a fixed contract, whatever the price says."""
    config = _config(
        contract_type=CONTRACT_TYPE_FIXED,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )
    metrics = _metrics(current_price_eur_kwh=0.05)

    codes = _codes(Advisor().generate(config, metrics))

    assert REASON_LOW_ENERGY_PRICE not in codes
    assert REASON_HIGH_ENERGY_PRICE not in codes


async def test_price_advice_needs_a_price(hass: HomeAssistant) -> None:
    """A dynamic contract without a readable price says nothing about price."""
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )

    assert _codes(Advisor().generate(config, _metrics())) == [
        REASON_NEUTRAL_ENERGY_SITUATION
    ]


async def test_a_price_between_the_thresholds_advises_nothing(
    hass: HomeAssistant,
) -> None:
    """Only the extremes are worth an advice."""
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )
    metrics = _metrics(current_price_eur_kwh=0.25)

    assert _codes(Advisor().generate(config, metrics)) == [
        REASON_NEUTRAL_ENERGY_SITUATION
    ]


async def test_prefer_low_price_switched_off_suppresses_price_advice(
    hass: HomeAssistant,
) -> None:
    """The price preference is honoured just like the solar one."""
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )
    config.preferences = UserPreferences(prefer_low_price=False)
    metrics = _metrics(current_price_eur_kwh=0.10)

    assert REASON_LOW_ENERGY_PRICE not in _codes(Advisor().generate(config, metrics))


async def test_a_device_with_a_broken_window_is_not_suggested(
    hass: HomeAssistant,
) -> None:
    """An unparseable window is a reason to skip, never to ignore it."""
    config = _config(min_solar_surplus_w=500.0)
    device = _device()
    device.earliest_start = "ochtend"
    device.latest_finish = "23:00"
    config.devices.append(device)
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(
        Advisor().generate(config, metrics)
    )


async def test_an_unknown_priority_does_not_crash_the_choice(
    hass: HomeAssistant,
) -> None:
    """A directly constructed device with a bad priority still sorts."""
    config = _config(min_solar_surplus_w=500.0)
    device = _device()
    device.priority = "urgent"
    config.devices.append(device)
    metrics = _metrics(solar_surplus_w=1500.0)

    assert Advisor().generate(config, metrics)[0].related_device_ids == ["d1"]


async def test_identical_quiet_hours_silence_nothing(
    hass: HomeAssistant,
) -> None:
    """An ambiguous window is treated as no window, never as a full day."""
    config = _config(min_solar_surplus_w=500.0)
    config.preferences = UserPreferences(
        quiet_hours_start="12:00", quiet_hours_end="12:00"
    )
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


async def test_a_quiet_window_within_one_day(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A window that does not wrap is handled by the simple comparison."""
    freezer.move_to(local(14, 0))
    config = _config(min_solar_surplus_w=500.0)
    config.preferences = UserPreferences(
        quiet_hours_start="13:00", quiet_hours_end="15:00"
    )
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(
        Advisor().generate(config, metrics)
    )


async def test_no_saving_without_an_energy_per_cycle(hass: HomeAssistant) -> None:
    """Without the energy a cycle uses there is nothing to multiply."""
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.30,
        feed_in_price_eur_kwh=0.05,
    )
    device = _device()
    device.energy_per_cycle_kwh = None
    config.devices.append(device)
    metrics = _metrics(solar_surplus_w=1500.0)

    assert Advisor().generate(config, metrics)[0].estimated_savings_eur is None


async def test_a_dynamic_contract_prices_the_saving_at_the_live_price(
    hass: HomeAssistant,
) -> None:
    """On a dynamic contract the current price is what is being avoided."""
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_DYNAMIC,
        feed_in_price_eur_kwh=0.05,
    )
    config.devices.append(_device(energy_per_cycle_kwh=2.0))
    metrics = _metrics(solar_surplus_w=1500.0, current_price_eur_kwh=0.30)

    advice = Advisor().generate(config, metrics)

    # 2 kWh x (0.30 - 0.05) = EUR 0.50.
    assert advice[0].estimated_savings_eur == 0.50


async def test_no_saving_is_claimed_when_feeding_in_pays_better(
    hass: HomeAssistant,
) -> None:
    """A negative saving is not a saving, so nothing is claimed."""
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.05,
        feed_in_price_eur_kwh=0.30,
    )
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0)

    assert Advisor().generate(config, metrics)[0].estimated_savings_eur is None


# --- Sorting, limiting and filtering ----------------------------------------


async def test_advice_is_sorted_by_the_documented_order(
    hass: HomeAssistant,
) -> None:
    """Peak before solar before price (SPEC.md §16 "Sorteervolgorde")."""
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
        min_solar_surplus_w=500.0,
    )
    config.devices.append(_device())
    metrics = _metrics(
        grid_load_percent=95.0,
        peak_risk=True,
        solar_surplus_w=1500.0,
        current_price_eur_kwh=0.10,
    )

    assert _codes(Advisor().generate(config, metrics)) == [
        REASON_HIGH_GRID_LOAD,
        REASON_SOLAR_SURPLUS_AVAILABLE,
        REASON_LOW_ENERGY_PRICE,
    ]


async def test_no_more_advice_than_the_maximum(hass: HomeAssistant) -> None:
    """max_advice_count is a hard limit (SPEC.md §16)."""
    config = _config(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
        min_solar_surplus_w=500.0,
    )
    config.preferences = UserPreferences(max_advice_count=1)
    config.devices.append(_device())
    metrics = _metrics(
        grid_load_percent=95.0,
        peak_risk=True,
        solar_surplus_w=1500.0,
        current_price_eur_kwh=0.10,
    )

    advice = Advisor().generate(config, metrics)

    assert len(advice) == 1
    assert advice[0].reason_code == REASON_HIGH_GRID_LOAD


async def test_the_highest_priority_device_is_chosen(hass: HomeAssistant) -> None:
    """Priority decides which device the surplus advice names."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(id="d1", name="Vaatwasser"))
    config.devices.append(
        _device(
            id="d2",
            name="Laadpaal",
            device_type=DEVICE_TYPE_EV_CHARGER,
            priority=PRIORITY_HIGH,
        )
    )
    metrics = _metrics(solar_surplus_w=1500.0)

    assert Advisor().generate(config, metrics)[0].related_device_ids == ["d2"]


async def test_the_biggest_consumer_wins_at_equal_priority(
    hass: HomeAssistant,
) -> None:
    """Moving the largest load saves the most, so it is suggested first."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(id="d1", name="Vaatwasser", nominal_power_w=2000.0))
    config.devices.append(
        _device(
            id="d2",
            name="Laadpaal",
            device_type=DEVICE_TYPE_EV_CHARGER,
            nominal_power_w=7400.0,
        )
    )
    metrics = _metrics(solar_surplus_w=1500.0)

    assert Advisor().generate(config, metrics)[0].related_device_ids == ["d2"]


async def test_savings_below_the_threshold_are_filtered(
    hass: HomeAssistant,
) -> None:
    """A calculated saving under min_savings_eur drops out (SPEC.md §8)."""
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.30,
        feed_in_price_eur_kwh=0.25,
    )
    config.preferences = UserPreferences(min_savings_eur=1.00)
    config.devices.append(_device(energy_per_cycle_kwh=1.0))
    metrics = _metrics(solar_surplus_w=1500.0)

    # 1.0 kWh x (0.30 - 0.25) = EUR 0.05, well under the EUR 1.00 threshold.
    assert _codes(Advisor().generate(config, metrics)) == [
        REASON_NEUTRAL_ENERGY_SITUATION
    ]


async def test_advice_without_a_calculable_saving_is_never_filtered(
    hass: HomeAssistant,
) -> None:
    """Safety, peak, missing data and neutral advice always survive."""
    config = _config()
    config.preferences = UserPreferences(min_savings_eur=99.0)
    metrics = _metrics(grid_load_percent=95.0, peak_risk=True)

    assert REASON_HIGH_GRID_LOAD in _codes(Advisor().generate(config, metrics))


async def test_a_saving_above_the_threshold_survives(hass: HomeAssistant) -> None:
    """The threshold filters, it does not block everything."""
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.30,
        feed_in_price_eur_kwh=0.05,
    )
    config.preferences = UserPreferences(min_savings_eur=1.00)
    config.devices.append(_device(energy_per_cycle_kwh=10.0))
    metrics = _metrics(solar_surplus_w=1500.0)

    advice = Advisor().generate(config, metrics)

    # 10 kWh x (0.30 - 0.05) = EUR 2.50.
    assert advice[0].estimated_savings_eur == 2.50


async def test_no_saving_is_claimed_without_both_prices(
    hass: HomeAssistant,
) -> None:
    """Without a feed-in price the saving is unknown, not zero."""
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.30,
    )
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0)

    assert Advisor().generate(config, metrics)[0].estimated_savings_eur is None


# --- The coach provider -----------------------------------------------------


async def test_the_rule_based_provider_answers_every_question(
    hass: HomeAssistant,
) -> None:
    """Each fixed question in the selector gets a non-empty answer."""
    result = CoachResult(
        primary_advice=AdviceItem(
            id="a1",
            title="Netbelasting hoog",
            message="Stel grootverbruikers uit.",
            severity=SEVERITY_WARNING,
            reason_code=REASON_HIGH_GRID_LOAD,
            confidence=CONFIDENCE_HIGH,
            measurements={"netbelasting_procent": 87.0},
        ),
        metrics=_metrics(grid_load_percent=87.0, peak_risk=True),
    )
    result.advice = [result.primary_advice] if result.primary_advice else []

    generated = await RuleBasedCoachProvider().async_generate(result)

    assert set(generated.explanations) == set(EXPLANATION_KEYS)
    assert all(text for text in generated.explanations.values())


async def test_the_provider_points_at_the_solar_moment(
    hass: HomeAssistant,
) -> None:
    """The "use a device now" answer repeats the solar advice verbatim."""
    advice = AdviceItem(
        id="a1",
        title="Zonneoverschot beschikbaar",
        message="Dit is een gunstig moment om Vaatwasser te gebruiken.",
        severity=SEVERITY_INFO,
        reason_code=REASON_SOLAR_SURPLUS_AVAILABLE,
        confidence=CONFIDENCE_HIGH,
    )
    result = CoachResult(primary_advice=advice, advice=[advice], metrics=_metrics())

    generated = await RuleBasedCoachProvider().async_generate(result)

    assert generated.explanations["use_device_now"] == advice.message


async def test_the_provider_advises_against_using_a_device_during_a_peak(
    hass: HomeAssistant,
) -> None:
    """A peak is a reason not to start something now."""
    advice = AdviceItem(
        id="a1",
        title="Netbelasting hoog",
        message="Stel grootverbruikers uit.",
        severity=SEVERITY_WARNING,
        reason_code=REASON_HIGH_GRID_LOAD,
        confidence=CONFIDENCE_HIGH,
    )
    result = CoachResult(primary_advice=advice, advice=[advice], metrics=_metrics())

    generated = await RuleBasedCoachProvider().async_generate(result)

    assert "geen gunstig moment" in generated.explanations["use_device_now"]


async def test_the_provider_reports_the_peak_situation(
    hass: HomeAssistant,
) -> None:
    """The peak answer states the measured load, not a judgement of its own."""
    result = CoachResult(metrics=_metrics(grid_load_percent=87.0, peak_risk=True))

    generated = await RuleBasedCoachProvider().async_generate(result)

    assert generated.explanations["peak_risk"].startswith("Ja.")
    assert "87.0%" in generated.explanations["peak_risk"]


async def test_the_provider_says_when_the_load_is_unknown(
    hass: HomeAssistant,
) -> None:
    """An unknown load is stated as unknown, never guessed at."""
    result = CoachResult(metrics=_metrics(grid_load_percent=None))

    generated = await RuleBasedCoachProvider().async_generate(result)

    assert "niet te bepalen" in generated.explanations["peak_risk"]


async def test_the_provider_lists_the_missing_data(hass: HomeAssistant) -> None:
    """Missing checklist items are named in Dutch, not as raw keys."""
    result = CoachResult(
        metrics=_metrics(
            data_quality=DataQualityResult(
                score=45, missing_items=["grid_source_valid"]
            )
        )
    )

    generated = await RuleBasedCoachProvider().async_generate(result)

    assert "een geldige netbron" in generated.explanations["missing_data"]
    assert generated.missing_data == ["grid_source_valid"]


async def test_the_provider_explains_the_score(hass: HomeAssistant) -> None:
    """The breakdown names every component that went into the score."""
    result = CoachResult(
        metrics=_metrics(energy_score=96, score_components={"peak_component": 100.0})
    )

    generated = await RuleBasedCoachProvider().async_generate(result)

    assert "96" in generated.explanations["score_breakdown"]
    assert "netbelasting" in generated.explanations["score_breakdown"]


async def test_the_provider_invents_nothing_without_advice(
    hass: HomeAssistant,
) -> None:
    """With no advice at all the provider says so instead of filling in."""
    generated = await RuleBasedCoachProvider().async_generate(CoachResult())

    assert generated.explanations["why_advice"] == "Er is op dit moment geen advies."


async def test_the_extension_provider_is_inactive(hass: HomeAssistant) -> None:
    """SPEC.md §17: the extension point exists but does nothing in 0.1.0."""
    with pytest.raises(NotImplementedError):
        await ExtensionCoachProvider().async_generate(CoachResult())


def test_both_providers_satisfy_the_protocol() -> None:
    """The coordinator can be handed either one (dependency injection)."""
    assert isinstance(RuleBasedCoachProvider(), CoachProvider)
    assert isinstance(ExtensionCoachProvider(), CoachProvider)
