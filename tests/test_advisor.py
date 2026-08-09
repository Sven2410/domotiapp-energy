"""Tests for the advisor and the coach provider (SPEC.md §24).

Covers the advice half of the SPEC.md §24 calculator list: price advice
suppressed on a fixed contract, quiet hours including a window across midnight,
advice priority and sorting, the neutral situation, and the savings threshold.
"""

from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant

from custom_components.domotiapp_energy.const import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONTRACT_TYPE_DYNAMIC,
    CONTRACT_TYPE_FIXED,
    CONTROL_MONITOR_ONLY,
    DEVICE_TYPE_DISHWASHER,
    DEVICE_TYPE_EV_CHARGER,
    DEVICE_TYPE_GENERIC_MONITOR,
    EXPLANATION_KEYS,
    MEASUREMENT_MINUTES_LEFT,
    MEASUREMENT_PRICE,
    PRIORITY_HIGH,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SOURCE_TYPE_FEED_IN_PRICE,
)
from custom_components.domotiapp_energy.engine.advisor import Advisor
from custom_components.domotiapp_energy.engine.calculator import self_consumption_margin
from custom_components.domotiapp_energy.engine.providers import (
    CoachProvider,
    ExtensionCoachProvider,
    RuleBasedCoachProvider,
)
from custom_components.domotiapp_energy.engine.reason_codes import (
    REASON_DEADLINE_APPROACHING,
    REASON_HIGH_ENERGY_PRICE,
    REASON_HIGH_GRID_EXPORT,
    REASON_HIGH_GRID_LOAD,
    REASON_LOW_ENERGY_PRICE,
    REASON_MISSING_REQUIRED_DATA,
    REASON_NEUTRAL_ENERGY_SITUATION,
    REASON_QUIET_HOURS_ACTIVE,
    REASON_SOLAR_SURPLUS_AVAILABLE,
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
    UserPreferences,
)

# Every checklist item passed, so "missing data" never fires by accident.
_COMPLETE = DataQualityResult(score=100, completed_items=["all"], missing_items=[])


def _config(**home_overrides: Any) -> StoredConfiguration:
    """Return a configuration whose home profile is complete.

    Net metering is **off** unless a test switches it on. These tests describe
    the world from 2027 onwards, where a fed-in kWh is worth the feed-in tariff
    and self-consumption has real value. The net-metering regime has its own
    tests further down, because it makes a different claim entirely.

    The feed-in cost is an explicit **0.0**, meaning "this home pays nothing to
    feed in", because that is what these tests are about: the arithmetic of the
    savings formula. Leaving it at ``None`` says something else entirely — that
    the amount is unknown and no saving may be quoted — and that rule has its
    own tests further down. The two used to be the same thing, and every test
    here silently relied on the guess.
    """
    defaults: dict[str, Any] = {
        "main_fuse_a": 25,
        "max_grid_power_w": 5750.0,
        "net_metering_until": None,
        "feed_in_cost_eur_kwh": 0.0,
    }
    return StoredConfiguration(home=HomeProfile(**(defaults | home_overrides)))


def _metrics(
    config: StoredConfiguration | None = None, **overrides: Any
) -> EnergyMetrics:
    """Return metrics with a complete checklist and no problems.

    **Pass `config` whenever the test is about a euro amount.** The saving is
    `energie per cyclus x marge`, and the margin is composed by the calculator
    from the contract, the feed-in tariff and the feed-in cost (SPEC.md §35.4d).
    Handing that composition to the same function the product uses keeps this
    fixture from drifting away from it — writing the number in by hand would
    let a test keep passing while the composition changed underneath it, which
    is how `feed_in_cost_eur_kwh` once made every saving test quietly assume
    "unknown = 0".

    A test that states a margin explicitly is describing a home the composition
    cannot reach from here, and says so at the call site.

    **`solar_surplus_confidence` is stated here on purpose.** The model default
    is `low`, which is right for metrics that carry no surplus at all, and
    wrong for the home these tests describe: a grid meter reporting export,
    which is the exact measurement (variant 1, SPEC.md §16).

    Leaving it at the default would make every surplus test in this file
    describe a home with an unreadable battery — the one case where the advice
    is deliberately suppressed (0.4.1) — so they would assert the absence of
    advice while claiming to test its content. Thirty-eight tests went red on
    exactly that when the suppression was added, which is the fixture doing its
    job for once.
    """
    defaults: dict[str, Any] = {
        "data_quality": _COMPLETE,
        "grid_power_w": 500.0,
        "grid_load_percent": 8.7,
        "energy_score": 80,
        "solar_surplus_confidence": CONFIDENCE_HIGH,
    }
    metrics = EnergyMetrics(**(defaults | overrides))
    if config is not None and "self_consumption_margin_eur_kwh" not in overrides:
        metrics.self_consumption_margin_eur_kwh = self_consumption_margin(
            config,
            EnergySnapshot(
                timestamp=metrics.timestamp,
                current_price_eur_kwh=metrics.current_price_eur_kwh,
                feed_in_price_eur_kwh=metrics.feed_in_price_eur_kwh,
            ),
        )
    return metrics


def _device(**overrides: Any) -> DeviceProfile:
    """Return a usable, flexible dishwasher built the way storage builds one.

    **1200 W, against the 1500 W of surplus these tests use.** The figure used
    to be 2000 W, which meant every surplus test in this file described a
    dishwasher that the surplus could not actually run — 500 W short, imported
    from the grid, while the advice said "benut je zonneoverschot" and the
    saving was calculated as though the whole cycle came from the roof. The
    fixtures had codified the defect, so the suite went green on it.

    Tests that are *about* a device outgrowing the surplus set the power
    explicitly; see the ones around `_fits_in_surplus`.
    """
    data: dict[str, Any] = {
        "id": "d1",
        "name": "Vaatwasser",
        "device_type": DEVICE_TYPE_DISHWASHER,
        "nominal_power_w": 1200.0,
        "energy_per_cycle_kwh": 1.0,
    }
    return DeviceProfile.from_dict(data | overrides)


def _codes(advice: list[AdviceItem]) -> list[str]:
    """Return the reason codes in the order the advisor produced them."""
    return [item.reason_code for item in advice]


TIME_ZONE = "Europe/Amsterdam"


def local_on(day: date, hour: int = 12) -> datetime:
    """Return the UTC instant at which TIME_ZONE reads this hour on this date."""
    return datetime(
        day.year, day.month, day.day, hour, tzinfo=ZoneInfo(TIME_ZONE)
    ).astimezone(UTC)


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


async def test_overload_by_export_advises_using_power_not_postponing_it(
    hass: HomeAssistant,
) -> None:
    """Exporting past the limit gets its own code and the opposite advice.

    The fuse limits both directions, so the warning is identical — but a home
    that is already pushing 10 kW into the grid has to use more, not less.
    Telling it to postpone its appliances would deepen the overload
    (SPEC.md §16).
    """
    metrics = _metrics(grid_power_w=-10000.0, grid_load_percent=173.9, peak_risk=True)

    advice = Advisor().generate(_config(), metrics)

    assert advice[0].reason_code == REASON_HIGH_GRID_EXPORT
    assert advice[0].severity == SEVERITY_WARNING
    assert advice[0].measurements["netbelasting_procent"] == 173.9
    assert advice[0].measurements["netvermogen_w"] == -10000.0
    assert "extra verbruikers in" in advice[0].message
    # The import wording must not leak into the export case.
    assert "uit" not in advice[0].message.split("Schakel")[0]
    assert REASON_HIGH_GRID_LOAD not in _codes(advice)


async def test_overload_by_import_keeps_the_original_advice(
    hass: HomeAssistant,
) -> None:
    """Drawing past the limit is unchanged: postpone the large consumers."""
    metrics = _metrics(grid_power_w=10000.0, grid_load_percent=173.9, peak_risk=True)

    advice = Advisor().generate(_config(), metrics)

    assert advice[0].reason_code == REASON_HIGH_GRID_LOAD
    assert "Stel extra grootverbruikers indien mogelijk uit" in advice[0].message
    assert REASON_HIGH_GRID_EXPORT not in _codes(advice)


async def test_the_two_peak_directions_never_occur_together(
    hass: HomeAssistant,
) -> None:
    """Grid power has one sign, so exactly one of the two can fire."""
    for grid_power in (-8000.0, 8000.0):
        codes = _codes(
            Advisor().generate(
                _config(),
                _metrics(
                    grid_power_w=grid_power, grid_load_percent=139.1, peak_risk=True
                ),
            )
        )
        assert (REASON_HIGH_GRID_LOAD in codes) != (REASON_HIGH_GRID_EXPORT in codes)


async def test_export_overload_outranks_the_solar_surplus_advice(
    hass: HomeAssistant,
) -> None:
    """Both say "use power now", so the more urgent one has to lead.

    They can genuinely co-occur: heavy export means a large surplus. The peak
    rank puts the overload first, so the primary advice is the one that
    explains the risk rather than the opportunity.
    """
    config = _config()
    config.devices = [_device()]
    metrics = _metrics(
        grid_power_w=-9000.0,
        grid_load_percent=156.5,
        peak_risk=True,
        solar_surplus_w=9000.0,
    )

    codes = _codes(Advisor().generate(config, metrics))

    assert codes[0] == REASON_HIGH_GRID_EXPORT
    assert REASON_SOLAR_SURPLUS_AVAILABLE in codes
    assert codes.index(REASON_HIGH_GRID_EXPORT) < codes.index(
        REASON_SOLAR_SURPLUS_AVAILABLE
    )


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


# --- The ready window (SPEC.md §32) -----------------------------------------


async def test_a_device_that_can_no_longer_finish_in_time_is_not_suggested(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The defect the ready window exists to fix.

    A 180-minute dishwasher that has to be finished by 06:00 must start by
    03:00. The old model only asked whether *now* fell inside the window, so at
    05:55 it happily advised a programme that would run until 08:55 — nearly
    three hours past the time the resident gave. The validator did not catch it
    either: it checked that the duration fitted the window, never that enough of
    the window was left.
    """
    freezer.move_to(local(5, 55))
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(
        _device(ready_from="22:00", ready_before="06:00", duration_minutes=180)
    )
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(
        Advisor().generate(config, metrics)
    )


async def test_the_same_device_is_suggested_while_it_can_still_finish(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """At 02:30 there is still time to run to completion before 06:00.

    The deadline advice would otherwise take this appliance's place in the list
    — 02:30 sits inside its urgency window — and that is the right behaviour
    but the wrong subject for this test, which is about the ready window. A
    deadline three hours later keeps the two apart.
    """
    freezer.move_to(local(2, 30))
    config = _config(min_solar_surplus_w=500.0)
    # A dishwasher is noisy by default and 02:30 is inside the quiet hours, so
    # without a quiet appliance the test would pass or fail on the wrong rule.
    # It used to switch the quiet hours off with a preference; that preference
    # is gone, and saying "this one makes no noise" is the truer way to say
    # "this test is about the window" anyway.
    config.devices.append(
        _device(
            ready_from="22:00",
            ready_before="09:00",
            duration_minutes=180,
            is_noisy=False,
        )
    )
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


async def test_without_a_duration_the_deadline_degrades_to_the_old_meaning(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """No duration means no start to derive, and no guessed one either.

    `ready_before` then means what `latest_finish` meant: may not run after. At
    05:55 that still allows the device, which is the pre-0.2 behaviour and the
    reason the migration is neutral for devices without a duration.
    """
    freezer.move_to(local(5, 55))
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(
        _device(ready_from="22:00", ready_before="06:00", is_noisy=False)
    )
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


async def test_half_a_ready_window_restricts_nothing_yet(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A lone bound is not a window on a 24-hour clock.

    "Finished by 06:00" with no lower bound would have to mean "in time for the
    *next* 06:00", and which one that is depends on when you ask. Working that
    out is the urgency advice's job; it is deliberately not half-answered here.
    """
    freezer.move_to(local(12, 0))
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(ready_before="06:00", duration_minutes=180))
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


async def test_a_device_outside_its_window_is_not_suggested(
    hass: HomeAssistant,
) -> None:
    """At midday a device allowed only in the evening is not advised."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(ready_from="18:00", ready_before="23:00"))
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(
        Advisor().generate(config, metrics)
    )


async def test_a_device_inside_its_window_is_suggested(
    hass: HomeAssistant,
) -> None:
    """The same device inside its window is fair game."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(ready_from="08:00", ready_before="18:00"))
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


async def test_a_midnight_window_covers_the_evening(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A 22:00-06:00 device is eligible at 23:30 (SPEC.md §16)."""
    freezer.move_to(local(23, 30))
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(
        _device(ready_from="22:00", ready_before="06:00", is_noisy=False)
    )
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


async def test_a_midnight_window_covers_the_small_hours(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The same window still applies after midnight."""
    freezer.move_to(local(3, 0))
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(
        _device(ready_from="22:00", ready_before="06:00", is_noisy=False)
    )
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


async def test_a_midnight_window_excludes_the_day(
    hass: HomeAssistant,
) -> None:
    """At midday the 22:00-06:00 device is outside its window."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(ready_from="22:00", ready_before="06:00"))
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
    config.devices.append(_device(ready_from="22:00", ready_before="06:00"))
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
    device.ready_from = "12:00"
    device.ready_before = "12:00"
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


async def test_quiet_hours_defer_the_advice_instead_of_hiding_it(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The advice is deferred, not suppressed, and it says until when.

    The quiet hours used to remove the advice altogether, with a preference to
    switch that off again. Both are gone (finding 12): the resident keeps the
    advice, and it tells him what to do with it — which is the one thing a
    silent panel could never do.
    """
    freezer.move_to(local(23, 30))
    config = _config(min_solar_surplus_w=500.0)
    config.preferences = UserPreferences(
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
    )
    config.devices.append(_device(name="Vaatwasser"))
    metrics = _metrics(config, solar_surplus_w=1500.0)

    advice = Advisor().generate(config, metrics)

    assert REASON_QUIET_HOURS_ACTIVE in _codes(advice)
    assert REASON_SOLAR_SURPLUS_AVAILABLE not in _codes(advice)
    message = advice[0].message
    assert "Vaatwasser" in message
    # The time the resident needs, in the sentence rather than in a setting.
    assert "07:00" in message
    # No euro amount beside a deferral: it would read as a reason to ignore it.
    assert advice[0].estimated_savings_eur is None


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
    device.ready_from = "ochtend"
    device.ready_before = "23:00"
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
    metrics = _metrics(config, solar_surplus_w=1500.0, current_price_eur_kwh=0.30)

    advice = Advisor().generate(config, metrics)

    # 2 kWh x (0.30 - 0.05) = EUR 0.50.
    assert advice[0].estimated_savings_eur == 0.50


async def test_a_saving_that_works_out_negative_is_reported_as_it_stands(
    hass: HomeAssistant,
) -> None:
    """Feeding in pays better, and the customer is told so in euros.

    This used to be clamped to zero, which is the one presentation that hides
    the situation worth knowing about: self-consumption is currently *costing*
    money, and "EUR 0,00" reads as "makes no difference". The advice survives —
    the surplus is real — but neither the amount nor the sentence may claim a
    favourable moment (round B, finding 2).
    """
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.05,
        feed_in_price_eur_kwh=0.30,
    )
    config.devices.append(_device())
    metrics = _metrics(config, solar_surplus_w=1500.0)

    advice = Advisor().generate(config, metrics)

    # 1 kWh x (0.05 - 0.30) = EUR -0.25.
    assert advice[0].reason_code == REASON_SOLAR_SURPLUS_AVAILABLE
    assert advice[0].estimated_savings_eur == -0.25
    # The sentence has to follow the arithmetic rather than talk over it.
    assert "gunstig moment" not in advice[0].message
    assert "€ 0,25" in advice[0].message


async def test_an_unknown_feed_in_cost_yields_no_amount_at_all(
    hass: HomeAssistant,
) -> None:
    """An empty feed-in cost means unknown, and unknown is not zero.

    Reading a blank field as 0.0 was a guess wearing the clothes of a
    calculation. Under net metering it was the whole answer, because the avoided
    feed-in cost is the only term that survives the cancellation — so a customer
    who had never filled the field in was shown "EUR 0,00" as though it had been
    worked out (round B, finding 4c).
    """
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.30,
        feed_in_price_eur_kwh=0.05,
        feed_in_cost_eur_kwh=None,
    )
    config.devices.append(_device())
    # The metrics carry the price that applies, whatever the contract is: on a
    # fixed contract that is the entered tariff (SPEC.md 48). Before 0.13.0 the
    # advisor read that field off the home itself, so this fixture could leave
    # it out.
    metrics = _metrics(solar_surplus_w=1500.0, current_price_eur_kwh=0.30)

    advice = Advisor().generate(config, metrics)

    assert advice[0].reason_code == REASON_SOLAR_SURPLUS_AVAILABLE
    assert advice[0].estimated_savings_eur is None
    # And it says which field would answer it, rather than going quiet.
    assert "terugleverkosten" in advice[0].message


async def test_a_missing_amount_names_the_term_that_is_actually_missing(
    hass: HomeAssistant,
) -> None:
    """Four gaps can stop the sum, and the sentence has to name the right one.

    Found on the running instance, not in this suite: a home whose price source
    had gone stale was told to go and fill in the feed-in cost — a field it had
    already filled in. Every unknown saving blamed the same field, because the
    message was written as though only one thing could ever be missing.
    """
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_DYNAMIC,
        feed_in_price_eur_kwh=0.05,
        feed_in_cost_eur_kwh=0.0,
    )
    config.devices.append(_device())
    # A dynamic contract with no live price: the price is the missing term.
    metrics = _metrics(solar_surplus_w=1500.0, current_price_eur_kwh=None)

    advice = Advisor().generate(config, metrics)

    assert advice[0].estimated_savings_eur is None
    assert "geen actuele prijs" in advice[0].message
    assert "terugleverkosten" not in advice[0].message


async def test_a_missing_energy_per_cycle_names_the_device_field(
    hass: HomeAssistant,
) -> None:
    """The first check in the formula, and it points at the Apparaten tab."""
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.30,
        feed_in_price_eur_kwh=0.05,
        feed_in_cost_eur_kwh=0.0,
    )
    config.devices.append(_device(energy_per_cycle_kwh=None))
    metrics = _metrics(solar_surplus_w=1500.0)

    advice = Advisor().generate(config, metrics)

    assert advice[0].estimated_savings_eur is None
    assert "energie per cyclus" in advice[0].message
    assert "terugleverkosten" not in advice[0].message


async def test_a_feed_in_cost_of_zero_is_a_calculated_zero(
    hass: HomeAssistant,
) -> None:
    """The same home with an explicit 0.0 gets a real amount, not a blank.

    This is the pair of the test above, and together they are the whole point of
    the distinction: same form, one field, two different truths.
    """
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.30,
        feed_in_price_eur_kwh=0.05,
        feed_in_cost_eur_kwh=0.0,
    )
    config.devices.append(_device())
    metrics = _metrics(config, solar_surplus_w=1500.0)

    advice = Advisor().generate(config, metrics)

    # 1 kWh x (0.30 - 0.05) = EUR 0.25.
    assert advice[0].estimated_savings_eur == 0.25


async def test_a_live_feed_in_tariff_beats_the_fixed_amount(
    hass: HomeAssistant,
) -> None:
    """A linked feed-in source is the statement that the tariff varies.

    The fixed field stays on file — the panel disables rather than clears it —
    so removing the source restores it (SPEC.md §16).
    """
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.30,
        # Deliberately different from the live rate, so the test can tell which
        # of the two was used.
        feed_in_price_eur_kwh=0.20,
    )
    config.devices.append(_device())
    metrics = _metrics(config, solar_surplus_w=1500.0, feed_in_price_eur_kwh=0.05)

    advice = Advisor().generate(config, metrics)

    # 1 kWh x (0.30 - 0.05) = EUR 0.25, not the 0.10 the fixed amount gives.
    assert advice[0].estimated_savings_eur == 0.25


async def test_the_fixed_amount_applies_without_a_feed_in_source(
    hass: HomeAssistant,
) -> None:
    """The pair of the test above, and the case every install starts in."""
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.30,
        feed_in_price_eur_kwh=0.20,
    )
    config.devices.append(_device())
    metrics = _metrics(config, solar_surplus_w=1500.0)

    advice = Advisor().generate(config, metrics)

    # 1 kWh x (0.30 - 0.20) = EUR 0.10.
    assert advice[0].estimated_savings_eur == 0.10


async def test_a_negative_feed_in_tariff_makes_self_consumption_worth_more(
    hass: HomeAssistant,
) -> None:
    """Negative market prices are real, and then feeding in costs money.

    The saving goes *up*, because the kWh you use yourself is one you no longer
    pay to export. Nothing clamps it on the way through.
    """
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.30,
    )
    config.devices.append(_device())
    metrics = _metrics(config, solar_surplus_w=1500.0, feed_in_price_eur_kwh=-0.05)

    advice = Advisor().generate(config, metrics)

    # 1 kWh x (0.30 - -0.05) = EUR 0.35.
    assert advice[0].estimated_savings_eur == 0.35


async def test_a_broken_feed_in_source_points_at_the_source(
    hass: HomeAssistant,
) -> None:
    """Do not send an installer to a field they deliberately left empty.

    A home with a feed-in source has nothing to fill in on the Woning tab, and
    saying so would repeat the wrong-field mistake the price sentence made.
    """
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.30,
        feed_in_price_eur_kwh=None,
    )
    config.sources.append(
        EnergySource(id="f1", name="Teruglevering", type=SOURCE_TYPE_FEED_IN_PRICE)
    )
    config.devices.append(_device())
    # The feed-in source is linked but unreadable, so there is no live rate;
    # the import price is the entered tariff, the way the metrics carry it
    # since SPEC 48.
    metrics = _metrics(solar_surplus_w=1500.0, current_price_eur_kwh=0.30)

    advice = Advisor().generate(config, metrics)

    assert advice[0].estimated_savings_eur is None
    assert "terugleverprijsbron" in advice[0].message
    assert "vul die in bij Woning" not in advice[0].message


async def test_a_charger_caps_its_confidence_at_medium(hass: HomeAssistant) -> None:
    """A perfect surplus reading does not make a charger's energy figure certain.

    "Energie per laadsessie" is a typical session the installer estimated; the
    state of charge is not knowable in this release. Reporting high confidence
    for a euro amount built on that estimate claims more than we know
    (round B, finding 7).
    """
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.30,
        feed_in_price_eur_kwh=0.05,
    )
    config.devices.append(
        _device(device_type=DEVICE_TYPE_EV_CHARGER, energy_per_cycle_kwh=10.0)
    )
    metrics = _metrics(
        config, solar_surplus_w=1500.0, solar_surplus_confidence=CONFIDENCE_HIGH
    )

    advice = Advisor().generate(config, metrics)

    assert advice[0].confidence == CONFIDENCE_MEDIUM
    # The saving itself is still calculated; only the claim about it is softened.
    assert advice[0].estimated_savings_eur == 2.50


async def test_a_dishwasher_keeps_the_confidence_the_measurement_earned(
    hass: HomeAssistant,
) -> None:
    """The cap is about the charger's unknown, not a blanket downgrade."""
    config = _config(
        min_solar_surplus_w=500.0,
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.30,
        feed_in_price_eur_kwh=0.05,
    )
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0, solar_surplus_confidence=CONFIDENCE_HIGH)

    advice = Advisor().generate(config, metrics)

    assert advice[0].confidence == CONFIDENCE_HIGH


# --- Net metering (SPEC.md §16) ---------------------------------------------


def _net_metering_config(**home_overrides: Any) -> StoredConfiguration:
    """Return a configuration where net metering is still running."""
    defaults: dict[str, Any] = {
        "min_solar_surplus_w": 500.0,
        "contract_type": CONTRACT_TYPE_FIXED,
        "fixed_import_price_eur_kwh": 0.30,
        "feed_in_price_eur_kwh": 0.05,
        "net_metering_until": date(2027, 1, 1),
    }
    config = _config(**(defaults | home_overrides))
    config.devices.append(_device(energy_per_cycle_kwh=2.0))
    return config


async def test_net_metering_leaves_nothing_extra_to_earn(hass: HomeAssistant) -> None:
    """Under net metering a fed-in kWh is worth the full price, so the saving is nil.

    The old formula claimed 2 x (0.30 - 0.05) = EUR 0.50 here, which the
    customer never sees on their bill while netting applies.
    """
    config = _net_metering_config()
    metrics = _metrics(config, solar_surplus_w=1500.0)

    advice = Advisor().generate(config, metrics)

    assert advice[0].reason_code == REASON_SOLAR_SURPLUS_AVAILABLE
    assert advice[0].estimated_savings_eur == 0.0


async def test_net_metering_still_saves_the_feed_in_cost(hass: HomeAssistant) -> None:
    """A supplier that charges for feeding in makes self-consumption pay again."""
    config = _net_metering_config(feed_in_cost_eur_kwh=0.11)
    metrics = _metrics(config, solar_surplus_w=1500.0)

    # 2 kWh x EUR 0.11 avoided feed-in cost.
    assert Advisor().generate(config, metrics)[0].estimated_savings_eur == 0.22


async def test_the_same_home_earns_the_full_difference_after_the_changeover(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """One day later the regime flips by itself, with no setting changed.

    The metrics are rebuilt after each jump because the margin is composed from
    the date: on the last day of netting a fed-in kWh is still worth the retail
    price, and on the first day after it is worth the feed-in tariff.
    """
    config = _net_metering_config()

    freezer.move_to(local_on(date(2026, 12, 31)))
    metrics = _metrics(config, solar_surplus_w=1500.0)
    assert Advisor().generate(config, metrics)[0].estimated_savings_eur == 0.0

    # 2 kWh x (0.30 - 0.05) = EUR 0.50.
    freezer.move_to(local_on(date(2027, 1, 1)))
    metrics = _metrics(config, solar_surplus_w=1500.0)
    assert Advisor().generate(config, metrics)[0].estimated_savings_eur == 0.50


async def test_net_metering_needs_no_feed_in_tariff_to_calculate(
    hass: HomeAssistant,
) -> None:
    """While netting applies the feed-in tariff does not enter the sum at all."""
    config = _net_metering_config(feed_in_price_eur_kwh=None, feed_in_cost_eur_kwh=0.05)
    metrics = _metrics(config, solar_surplus_w=1500.0)

    assert Advisor().generate(config, metrics)[0].estimated_savings_eur == 0.10


async def test_a_zero_saving_says_why_it_is_zero(hass: HomeAssistant) -> None:
    """A "gunstig moment" beside EUR 0,00 contradicts itself unless explained."""
    config = _net_metering_config()
    metrics = _metrics(config, solar_surplus_w=1500.0)

    message = Advisor().generate(config, metrics)[0].message

    assert "gunstig moment" in message
    assert "salderingsregeling" in message


async def test_a_real_saving_is_not_explained_away(hass: HomeAssistant) -> None:
    """The extra sentence appears only when there is genuinely nothing to earn."""
    config = _net_metering_config(feed_in_cost_eur_kwh=0.11)
    metrics = _metrics(solar_surplus_w=1500.0)

    assert "salderingsregeling" not in Advisor().generate(config, metrics)[0].message


async def test_a_zero_saving_survives_the_savings_threshold(
    hass: HomeAssistant,
) -> None:
    """The threshold must not silence a panel for a whole year (SPEC.md §8).

    With the corrected formula almost every solar advice is worth EUR 0.00
    until 2027. Filtering those would leave the customer with a product that
    says nothing, while the advice itself is perfectly sound.
    """
    config = _net_metering_config()
    config.preferences = UserPreferences(min_savings_eur=1.00)
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


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


async def test_the_biggest_consumer_that_fits_wins_at_equal_priority(
    hass: HomeAssistant,
) -> None:
    """Among the appliances the surplus can carry, the largest uses most of it."""
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
    metrics = _metrics(solar_surplus_w=8000.0)

    assert Advisor().generate(config, metrics)[0].related_device_ids == ["d2"]


async def test_a_device_the_surplus_cannot_run_is_not_suggested(
    hass: HomeAssistant,
) -> None:
    """600 W of surplus does not "run" a 2000 W dishwasher.

    It used to be advised anyway: the rule only checked the surplus against
    `min_solar_surplus_w` and never against the appliance. The resident was told
    to "benut je zonneoverschot" while 1400 W came off the grid, and the saving
    underneath was calculated as though the whole cycle came from the roof
    (production finding, 2026-08-07).
    """
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(id="d1", name="Vaatwasser", nominal_power_w=2000.0))
    metrics = _metrics(solar_surplus_w=600.0)

    assert _codes(Advisor().generate(config, metrics)) == [
        REASON_NEUTRAL_ENERGY_SITUATION
    ]


async def test_no_surplus_advice_when_the_surplus_may_be_overstated(
    hass: HomeAssistant,
) -> None:
    """The real defect the confidence label was papering over (0.4.1).

    A home battery that cannot be read may be consuming exactly the 2500 W
    shown as spare. The coach used to advise starting the dishwasher on it,
    with a euro amount underneath, and labelled the whole thing
    "betrouwbaarheid: laag" — which suppressed nothing and which no resident
    can act on. Now it says nothing about the surplus, and the panel says what
    to link.
    """
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(id="d1", name="Vaatwasser", nominal_power_w=1200.0))
    metrics = _metrics(solar_surplus_w=2500.0, solar_surplus_confidence=CONFIDENCE_LOW)

    advice = Advisor().generate(config, metrics)

    assert not any(
        item.reason_code == REASON_SOLAR_SURPLUS_AVAILABLE for item in advice
    )


async def test_the_same_surplus_is_advised_on_once_the_battery_is_readable(
    hass: HomeAssistant,
) -> None:
    """The other half: the suppression is about the blind spot, not the number.

    Identical readings, identical appliance. Without this test the suite would
    stay green if surplus advice stopped working altogether.
    """
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(id="d1", name="Vaatwasser", nominal_power_w=1200.0))
    metrics = _metrics(
        solar_surplus_w=2500.0, solar_surplus_confidence=CONFIDENCE_MEDIUM
    )

    advice = Advisor().generate(config, metrics)

    assert any(item.reason_code == REASON_SOLAR_SURPLUS_AVAILABLE for item in advice)


async def test_alleen_meekijken_stops_the_advice(hass: HomeAssistant) -> None:
    """The resident's own off switch, which had no reader at all until 0.6.1.

    `control_mode = monitor_only` is what SPEC.md §33 calls his off switch, and
    the advisor filtered on `is_usable and is_flexible` only — so a dishwasher
    he had set to "alleen meekijken" was still advised on. The product ignored
    an explicit instruction.
    """
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(
        _device(id="d1", name="Vaatwasser", control_mode=CONTROL_MONITOR_ONLY)
    )
    metrics = _metrics(solar_surplus_w=1500.0)

    advice = Advisor().generate(config, metrics)

    assert not any(
        item.reason_code == REASON_SOLAR_SURPLUS_AVAILABLE for item in advice
    )


async def test_the_same_appliance_is_advised_on_when_it_may_be(
    hass: HomeAssistant,
) -> None:
    """The other half: the suppression is about the switch, not the appliance."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(id="d1", name="Vaatwasser"))
    metrics = _metrics(solar_surplus_w=1500.0)

    advice = Advisor().generate(config, metrics)

    assert any(item.reason_code == REASON_SOLAR_SURPLUS_AVAILABLE for item in advice)


async def test_a_monitor_only_type_is_never_advised_on(hass: HomeAssistant) -> None:
    """The other axis: the type says "measure this, do not move it"."""
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(
        _device(id="d1", name="Tabletlader", device_type=DEVICE_TYPE_GENERIC_MONITOR)
    )
    metrics = _metrics(solar_surplus_w=1500.0)

    advice = Advisor().generate(config, metrics)

    assert not any(
        item.reason_code == REASON_SOLAR_SURPLUS_AVAILABLE for item in advice
    )


async def test_the_surplus_picks_the_appliance_it_can_actually_run(
    hass: HomeAssistant,
) -> None:
    """The sorting used to pick the appliance that fitted *worst*.

    With 2500 W of surplus the charger is out of reach and the dishwasher is
    not. The old code sorted on raw power and handed back the charger.
    """
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
    metrics = _metrics(solar_surplus_w=2500.0)

    assert Advisor().generate(config, metrics)[0].related_device_ids == ["d1"]


async def test_an_unknown_power_is_not_disqualified_by_the_surplus(
    hass: HomeAssistant,
) -> None:
    """We cannot show it does not fit, so refusing it would be a guess.

    It sorts last, so it only ever wins when nothing else qualifies — which is
    exactly this case.
    """
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(id="d1", nominal_power_w=None))
    metrics = _metrics(solar_surplus_w=600.0)

    assert Advisor().generate(config, metrics)[0].related_device_ids == ["d1"]


async def test_a_day_the_resident_unticked_gets_no_advice(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The day list was stored, shown, and then never read by anything.

    A resident who untick Sunday was advised to run the dishwasher on Sunday
    regardless — the panel asked, they answered, and the engine overruled them
    silently. That is worse than not having the field
    (production finding, 2026-08-07).
    """
    # Sunday, 9 August 2026, midday.
    freezer.move_to(local_on(date(2026, 8, 9), 12))
    config = _config(min_solar_surplus_w=500.0)
    # Monday to Saturday, so today is out.
    config.devices.append(_device(days_of_week=[0, 1, 2, 3, 4, 5]))
    metrics = _metrics(solar_surplus_w=1500.0)

    assert _codes(Advisor().generate(config, metrics)) == [
        REASON_NEUTRAL_ENERGY_SITUATION
    ]


async def test_the_same_device_is_advised_on_a_day_that_is_ticked(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The pair of the test above: Saturday is in the list, so it is advised."""
    freezer.move_to(local_on(date(2026, 8, 8), 12))
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device(days_of_week=[0, 1, 2, 3, 4, 5]))
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


async def test_the_default_day_list_allows_every_day(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Nobody who left the days alone may notice this change at all."""
    freezer.move_to(local_on(date(2026, 8, 9), 12))
    config = _config(min_solar_surplus_w=500.0)
    config.devices.append(_device())
    metrics = _metrics(solar_surplus_w=1500.0)

    assert REASON_SOLAR_SURPLUS_AVAILABLE in _codes(Advisor().generate(config, metrics))


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
    metrics = _metrics(config, solar_surplus_w=1500.0)

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
    metrics = _metrics(config, solar_surplus_w=1500.0)

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


async def test_the_provider_advises_using_a_device_during_an_export_peak(
    hass: HomeAssistant,
) -> None:
    """Overloading by export is the peak where using power *is* the answer."""
    advice = AdviceItem(
        id="a1",
        title="Teruglevering hoog",
        message="Schakel juist extra verbruikers in.",
        severity=SEVERITY_WARNING,
        reason_code=REASON_HIGH_GRID_EXPORT,
        confidence=CONFIDENCE_HIGH,
    )
    result = CoachResult(
        primary_advice=advice,
        advice=[advice],
        metrics=_metrics(grid_power_w=-9000.0),
    )

    generated = await RuleBasedCoachProvider().async_generate(result)

    answer = generated.explanations["use_device_now"]
    assert answer.startswith("Ja.")
    assert "geen gunstig moment" not in answer


async def test_the_provider_answers_the_device_question_from_the_price(
    hass: HomeAssistant,
) -> None:
    """A low price is a reason to run something now, and the answer says so.

    Before the price round this fell through to "no reason to move anything"
    while a low price advice was sitting in the list right next to it.
    """
    advice = AdviceItem(
        id="a1",
        title="Lage energieprijs",
        message="De actuele energieprijs is relatief laag.",
        severity=SEVERITY_INFO,
        reason_code=REASON_LOW_ENERGY_PRICE,
        confidence=CONFIDENCE_HIGH,
    )
    result = CoachResult(
        primary_advice=advice,
        advice=[advice],
        metrics=_metrics(current_price_eur_kwh=0.2088),
    )

    generated = await RuleBasedCoachProvider().async_generate(result)

    answer = generated.explanations["use_device_now"]
    assert answer.startswith("Ja.")
    # The same normalised all-in number the thresholds were compared against.
    assert "0,209" in answer
    assert "all-in" in answer


async def test_the_provider_advises_waiting_at_a_high_price(
    hass: HomeAssistant,
) -> None:
    """The mirror image, phrased like the peak answer."""
    advice = AdviceItem(
        id="a1",
        title="Hoge energieprijs",
        message="De actuele energieprijs is relatief hoog.",
        severity=SEVERITY_WARNING,
        reason_code=REASON_HIGH_ENERGY_PRICE,
        confidence=CONFIDENCE_HIGH,
    )
    result = CoachResult(
        primary_advice=advice,
        advice=[advice],
        metrics=_metrics(current_price_eur_kwh=0.45),
    )

    generated = await RuleBasedCoachProvider().async_generate(result)

    answer = generated.explanations["use_device_now"]
    assert "geen gunstig moment" in answer
    assert "0,450" in answer


async def test_the_solar_moment_outranks_the_price_answer(
    hass: HomeAssistant,
) -> None:
    """Surplus comes before price, exactly as the advice ranking does."""
    solar = AdviceItem(
        id="a1",
        title="Zonneoverschot beschikbaar",
        message="Dit is een gunstig moment om Vaatwasser te gebruiken.",
        severity=SEVERITY_INFO,
        reason_code=REASON_SOLAR_SURPLUS_AVAILABLE,
        confidence=CONFIDENCE_HIGH,
    )
    price = AdviceItem(
        id="a2",
        title="Hoge energieprijs",
        message="De actuele energieprijs is relatief hoog.",
        severity=SEVERITY_WARNING,
        reason_code=REASON_HIGH_ENERGY_PRICE,
        confidence=CONFIDENCE_HIGH,
    )
    result = CoachResult(
        primary_advice=solar,
        advice=[solar, price],
        metrics=_metrics(current_price_eur_kwh=0.45),
    )

    generated = await RuleBasedCoachProvider().async_generate(result)

    assert generated.explanations["use_device_now"] == solar.message


async def test_the_provider_names_the_price_as_all_in(hass: HomeAssistant) -> None:
    """The "why" answer may not quote a price of an unknown kind.

    The measurement is the normalised all-in price, and a reader who assumed a
    market price would think the figure was three times too high.
    """
    advice = AdviceItem(
        id="a1",
        title="Hoge energieprijs",
        message="De actuele energieprijs is relatief hoog.",
        severity=SEVERITY_WARNING,
        reason_code=REASON_HIGH_ENERGY_PRICE,
        confidence=CONFIDENCE_HIGH,
        measurements={MEASUREMENT_PRICE: 0.45},
    )
    result = CoachResult(primary_advice=advice, advice=[advice], metrics=_metrics())

    generated = await RuleBasedCoachProvider().async_generate(result)

    assert "all-in prijs in €/kWh: 0.45" in generated.explanations["why_advice"]


async def test_the_provider_reports_the_peak_situation(
    hass: HomeAssistant,
) -> None:
    """The peak answer states the measured load, not a judgement of its own."""
    result = CoachResult(
        metrics=_metrics(grid_power_w=5000.0, grid_load_percent=87.0, peak_risk=True)
    )

    generated = await RuleBasedCoachProvider().async_generate(result)

    assert generated.explanations["peak_risk"].startswith("Ja.")
    assert "87.0%" in generated.explanations["peak_risk"]
    assert "gebruikt" in generated.explanations["peak_risk"]


async def test_the_provider_describes_an_export_peak_as_feeding_back(
    hass: HomeAssistant,
) -> None:
    """A home that is exporting is not "using" its maximum."""
    result = CoachResult(
        metrics=_metrics(grid_power_w=-10000.0, grid_load_percent=173.9, peak_risk=True)
    )

    generated = await RuleBasedCoachProvider().async_generate(result)

    answer = generated.explanations["peak_risk"]
    assert answer.startswith("Ja.")
    assert "levert terug" in answer
    assert "gebruikt" not in answer


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
        metrics=_metrics(energy_score=96, score_components={"solar_component": 96.0})
    )

    generated = await RuleBasedCoachProvider().async_generate(result)

    assert "96" in generated.explanations["score_breakdown"]
    assert "zonnebenutting" in generated.explanations["score_breakdown"]


async def test_the_provider_names_the_unreadable_battery(hass: HomeAssistant) -> None:
    """The answer to "welke gegevens ontbreken nog?" carries the cause and fix.

    Not a checklist item — the battery row exists, so nothing is missing and
    the percentage does not move — but it is the one gap that silently changes
    what the coach does, so it belongs in that answer (0.4.1).
    """
    result = CoachResult(
        metrics=_metrics(
            solar_surplus_w=1900.0, solar_surplus_confidence=CONFIDENCE_LOW
        )
    )

    generated = await RuleBasedCoachProvider().async_generate(result)

    answer = generated.explanations["missing_data"]
    assert "thuisbatterij" in answer
    assert "Koppel de vermogenssensor" in answer


async def test_the_provider_stays_quiet_about_a_readable_battery(
    hass: HomeAssistant,
) -> None:
    """No sentence when there is no blind spot to report."""
    result = CoachResult(metrics=_metrics(solar_surplus_w=1900.0))

    generated = await RuleBasedCoachProvider().async_generate(result)

    assert "thuisbatterij" not in generated.explanations["missing_data"]


async def test_no_answer_carries_a_confidence_sentence(hass: HomeAssistant) -> None:
    """The trailing "Betrouwbaarheid: hoog." is gone from every answer (0.4.1)."""
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

    for answer in generated.explanations.values():
        assert "etrouwbaarheid" not in answer


async def test_the_provider_says_why_there_is_no_score(hass: HomeAssistant) -> None:
    """No score is an answer, not a blank (SPEC.md §35.9).

    "Nog niet berekend" was true only while nothing had run yet. For a home
    with a fixed contract and no panels it would be permanent and wrong: there
    is nothing to calculate, not something still pending.
    """
    result = CoachResult(
        metrics=_metrics(
            energy_score=None,
            score_components={},
            score_unavailable_reason="no_variable_signal",
        )
    )

    generated = await RuleBasedCoachProvider().async_generate(result)

    breakdown = generated.explanations["score_breakdown"]
    assert "niets te optimaliseren" in breakdown
    assert "Het advies blijft gewoon werken." in breakdown


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


# --- The urgency advice (SPEC.md §32.3, fase 2) ------------------------------
#
# One row per situation, with the sentence that belongs to it written down
# before the rule was built — the same rule the tile texts follow, and the one
# that catches a condition testing something other than what its sentence
# claims.


def _deadline_home(**device_overrides: Any) -> StoredConfiguration:
    """Return a home whose dishwasher must be done by 07:00 and runs 180 minutes.

    So the last possible start is 04:00 and the urgency window is 03:30-04:00.
    Not noisy, because the quiet hours would otherwise defer the advice and
    this is not the test for that.
    """
    config = _config(min_solar_surplus_w=500.0)
    defaults: dict[str, Any] = {
        "name": "Vaatwasser",
        "ready_before": "07:00",
        "duration_minutes": 180,
        "is_noisy": False,
    }
    config.devices.append(_device(**(defaults | device_overrides)))
    return config


async def test_the_urgency_advice_fires_inside_its_window(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """03:45 is inside 03:30-04:00, so the deadline is about to become unreachable."""
    freezer.move_to(local(3, 45))
    config = _deadline_home()

    advice = Advisor().generate(config, _metrics(config))

    assert advice[0].reason_code == REASON_DEADLINE_APPROACHING
    assert advice[0].message == (
        "Start Vaatwasser nu als hij om 07:00 klaar moet zijn."
    )
    # Fifteen minutes left before starting later makes 07:00 impossible.
    assert advice[0].measurements[MEASUREMENT_MINUTES_LEFT] == 15


async def test_the_urgency_advice_is_silent_before_its_window(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """At 02:00 there are two hours of slack; saying "nu" would be false."""
    freezer.move_to(local(2, 0))
    config = _deadline_home()

    assert REASON_DEADLINE_APPROACHING not in _codes(
        Advisor().generate(config, _metrics(config))
    )


async def test_the_urgency_advice_stops_once_the_deadline_is_unreachable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """At 04:30 starting now finishes at 07:30, so the sentence would lie.

    SPEC.md §32.3 says the advice runs "tot de deadline"; this stops it one
    moment earlier, at the last start. Past that there is no true sentence left
    that helps — the same reason §32.3 gives for going quiet after the deadline,
    applied where the deadline actually becomes unreachable.
    """
    freezer.move_to(local(4, 30))
    config = _deadline_home()

    assert REASON_DEADLINE_APPROACHING not in _codes(
        Advisor().generate(config, _metrics(config))
    )


async def test_the_urgency_advice_stays_silent_after_the_deadline(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """08:00 is past 07:00: "je hebt het gemist" helps nobody (SPEC.md §32.3)."""
    freezer.move_to(local(8, 0))
    config = _deadline_home()

    assert REASON_DEADLINE_APPROACHING not in _codes(
        Advisor().generate(config, _metrics(config))
    )


async def test_no_duration_means_no_deadline_advice(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Without a duration there is no last start, and none is guessed."""
    freezer.move_to(local(3, 45))
    config = _deadline_home(duration_minutes=None)

    assert REASON_DEADLINE_APPROACHING not in _codes(
        Advisor().generate(config, _metrics(config))
    )


async def test_the_urgency_window_may_cross_midnight(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A 01:00 deadline on a 180-minute cycle starts at 22:00, so the window is 21:30.

    The normal case rather than an edge one, and the reason the comparison uses
    the same midnight-crossing helper every other window in this engine uses.
    """
    freezer.move_to(local(21, 45))
    config = _deadline_home(ready_before="01:00")

    assert REASON_DEADLINE_APPROACHING in _codes(
        Advisor().generate(config, _metrics(config))
    )


async def test_the_deadline_outranks_the_sun(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Rank 3 beats rank 4: a deadline is hard, waiting for sun is an optimisation."""
    freezer.move_to(local(3, 45))
    config = _deadline_home()
    metrics = _metrics(config, solar_surplus_w=1500.0)

    advice = Advisor().generate(config, metrics)

    assert advice[0].reason_code == REASON_DEADLINE_APPROACHING


async def test_one_appliance_gets_one_advice(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Two true sentences about the same machine asking for the same action.

    The doubled primary advice of SPEC.md §42.1, one layer up: there the panel
    printed one item twice, here the engine produced two items about one
    subject. The more urgent reason survives.
    """
    freezer.move_to(local(3, 45))
    config = _deadline_home()
    metrics = _metrics(config, solar_surplus_w=1500.0)

    codes = _codes(Advisor().generate(config, metrics))

    assert codes.count(REASON_DEADLINE_APPROACHING) == 1
    assert REASON_SOLAR_SURPLUS_AVAILABLE not in codes


async def test_advice_about_the_house_is_never_deduplicated(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Price and peak carry no appliance, so two of them may both be true."""
    freezer.move_to(local(3, 45))
    config = _deadline_home()
    config.home.contract_type = CONTRACT_TYPE_DYNAMIC
    config.home.low_price_threshold_eur_kwh = 0.15
    metrics = _metrics(config, current_price_eur_kwh=0.10)

    codes = _codes(Advisor().generate(config, metrics))

    assert REASON_DEADLINE_APPROACHING in codes
    assert REASON_LOW_ENERGY_PRICE in codes
