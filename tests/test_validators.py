"""Tests for reading entity values and validating configuration (SPEC.md §24).

The validation list from SPEC.md §24 is the contract for this file: valid and
invalid entities, negative power, scale factors, missing attributes, invalid
time windows, a ready_before before ready_from evaluated as a window across
midnight, an invalid main fuse, max_grid_power_w = 0, and the unit conversions
kW->W and ct->EUR.
"""

import math
from datetime import timedelta
from typing import Any

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant

from custom_components.domotiapp_energy.const import (
    CAPABILITY_READ,
    CAPABILITY_SET_CURRENT,
    CAPABILITY_SET_POWER_LIMIT,
    CONTRACT_TYPE_DYNAMIC,
    CONTRACT_TYPE_FIXED,
    CONTROL_ADVICE_ONLY,
    CONTROL_AUTOMATIC,
    DEVICE_TYPE_DISHWASHER,
    DEVICE_TYPE_DRYER,
    DEVICE_TYPE_EV_CHARGER,
    DEVICE_TYPE_GENERIC_MONITOR,
    DEVICE_TYPE_GENERIC_SCHEDULABLE,
    DEVICE_TYPE_WASHING_MACHINE,
    ENTITY_STALE_AFTER_MINUTES,
    EXPORT_STALE_MINUTES,
    MAX_ADVICE_COUNT,
    METER_MODE_SEPARATE,
    METER_MODE_SINGLE_SIGNED,
    PHASES_THREE,
    POSITIVE_MEANS_IMPORT,
    PRICE_BASIS_ALL_IN,
    PRICE_BASIS_MARKET,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SOURCE_STALE_MINUTES,
    SOURCE_TYPE_CURRENT_PRICE,
    SOURCE_TYPE_FEED_IN_PRICE,
    SOURCE_TYPE_GRID_METER,
    SOURCE_TYPE_HOME_BATTERY,
    SOURCE_TYPE_SOLAR,
    SOURCE_TYPES,
    STALE_AFTER_MINUTES_MEASUREMENT,
    STALE_AFTER_MINUTES_PRICE,
    STALE_AFTER_MINUTES_RESTING,
    UNIT_A,
    UNIT_CT_KWH,
    UNIT_EUR_KWH,
    UNIT_KW,
    UNIT_KWH,
    UNIT_NONE,
    UNIT_W,
    VALIDATION_ABOVE_THEORETICAL_MAXIMUM,
    VALIDATION_CAPABILITY_MISSING,
    VALIDATION_CONTROL_FORBIDDEN,
    VALIDATION_INVALID_TIME_WINDOW,
    VALIDATION_OUT_OF_RANGE,
    VALIDATION_REQUIRED,
    VALIDATION_UNIT_MISMATCH,
    VALIDATION_UNKNOWN_TYPE,
    VALUE_SOURCE_ATTRIBUTE,
)
from custom_components.domotiapp_energy.engine.reason_codes import (
    REASON_CODES,
    REASON_INVALID_ENTITY_STATE,
    REASON_MISSING_REQUIRED_DATA,
)
from custom_components.domotiapp_energy.models import (
    DeviceProfile,
    EnergySource,
    EntityBinding,
    HomeProfile,
    UserPreferences,
    minutes_since_midnight,
)
from custom_components.domotiapp_energy.validators import (
    ReadResult,
    ValidationIssue,
    is_within_window,
    read_entity_value,
    validate_configuration,
    validate_device_profile,
    validate_energy_source,
    validate_home_profile,
    validate_preferences,
    window_length_minutes,
)


def has_errors(issues: list[ValidationIssue]) -> bool:
    """Return whether any issue would block use of the row.

    A test convenience, and it lives here because that is the only place it was
    ever used. It sat in `validators.py` as production code until 0.7.1, where
    it was exported, documented and called by nothing — no engine, no WebSocket
    handler, no panel. The audit of SPEC.md §37.2b found it and this round
    removes it; the assertions it makes readable are worth keeping, so it moved
    rather than disappearing.
    """
    return any(issue.is_error for issue in issues)


ENTITY_ID = "sensor.grid_power"


def _binding(entity_id: str = ENTITY_ID, **overrides: Any) -> EntityBinding:
    """Return a binding on ENTITY_ID, or on another entity, with overrides."""
    return EntityBinding(entity_id=entity_id, **overrides)


def _codes(issues: list[ValidationIssue]) -> set[str]:
    """Return the issue codes, for assertions that do not care about order."""
    return {issue.code for issue in issues}


def _fields(issues: list[ValidationIssue]) -> set[str]:
    """Return the fields the issues point at."""
    return {issue.field for issue in issues}


# --- Reading a valid entity -------------------------------------------------


async def test_reading_a_plain_state(hass: HomeAssistant) -> None:
    """A numeric state is returned unchanged when nothing is configured."""
    hass.states.async_set(ENTITY_ID, "1234.5")

    result = read_entity_value(hass, _binding(unit=UNIT_W))

    assert result.ok is True
    assert result.value == 1234.5
    assert result.reason_code is None
    assert result.entity_id == ENTITY_ID


async def test_reading_a_negative_power(hass: HomeAssistant) -> None:
    """A negative value survives: it is export, not an error (SPEC.md §16)."""
    hass.states.async_set(ENTITY_ID, "-2300")

    result = read_entity_value(hass, _binding(unit=UNIT_W))

    assert result.ok is True
    assert result.value == -2300.0


async def test_reading_an_integer_state(hass: HomeAssistant) -> None:
    """Whole numbers come back as floats, not as ints."""
    hass.states.async_set(ENTITY_ID, "500")

    result = read_entity_value(hass, _binding(unit=UNIT_W))

    assert result.value == 500.0
    assert isinstance(result.value, float)


async def test_reading_an_attribute(hass: HomeAssistant) -> None:
    """With value_source=attribute the named attribute is read, not the state."""
    hass.states.async_set(ENTITY_ID, "on", {"current_power": 750})

    result = read_entity_value(
        hass,
        _binding(
            value_source=VALUE_SOURCE_ATTRIBUTE,
            attribute_name="current_power",
            unit=UNIT_W,
        ),
    )

    assert result.ok is True
    assert result.value == 750.0


# --- Refusing an unusable entity --------------------------------------------


async def test_a_binding_without_an_entity_is_missing_data(
    hass: HomeAssistant,
) -> None:
    """An unlinked binding is missing configuration, not a bad reading."""
    result = read_entity_value(hass, EntityBinding())

    assert result.ok is False
    assert result.value is None
    assert result.reason_code == REASON_MISSING_REQUIRED_DATA
    assert result.entity_id == ""


async def test_an_unknown_entity_is_refused(hass: HomeAssistant) -> None:
    """An entity that does not exist yields no value at all."""
    result = read_entity_value(hass, _binding(entity_id="sensor.does_not_exist"))

    assert result.ok is False
    assert result.value is None
    assert result.reason_code == REASON_INVALID_ENTITY_STATE
    assert result.entity_id == "sensor.does_not_exist"


@pytest.mark.parametrize("state", ["unknown", "unavailable", "none", "", "  "])
async def test_unusable_states_are_refused(hass: HomeAssistant, state: str) -> None:
    """unknown, unavailable, none and empty are never treated as zero."""
    hass.states.async_set(ENTITY_ID, state)

    result = read_entity_value(hass, _binding(unit=UNIT_W))

    assert result.ok is False
    assert result.value is None
    assert result.reason_code == REASON_INVALID_ENTITY_STATE


@pytest.mark.parametrize("state", ["nonsense", "1,5", "12 W", "NaN", "inf"])
async def test_non_numeric_states_are_refused(hass: HomeAssistant, state: str) -> None:
    """Anything that is not a finite number is refused, never coerced."""
    hass.states.async_set(ENTITY_ID, state)

    result = read_entity_value(hass, _binding(unit=UNIT_W))

    assert result.ok is False
    assert result.reason_code == REASON_INVALID_ENTITY_STATE


async def test_a_boolean_attribute_is_not_a_measurement(hass: HomeAssistant) -> None:
    """True must not silently become 1.0."""
    hass.states.async_set(ENTITY_ID, "on", {"running": True})

    result = read_entity_value(
        hass,
        _binding(value_source=VALUE_SOURCE_ATTRIBUTE, attribute_name="running"),
    )

    assert result.ok is False
    assert result.reason_code == REASON_INVALID_ENTITY_STATE


async def test_a_missing_attribute_is_refused(hass: HomeAssistant) -> None:
    """A configured attribute that the entity does not have is refused."""
    hass.states.async_set(ENTITY_ID, "on", {"other_attribute": 5})

    result = read_entity_value(
        hass,
        _binding(value_source=VALUE_SOURCE_ATTRIBUTE, attribute_name="current_power"),
    )

    assert result.ok is False
    assert result.reason_code == REASON_INVALID_ENTITY_STATE


async def test_attribute_source_without_an_attribute_name(
    hass: HomeAssistant,
) -> None:
    """Choosing "attribute" without naming one is missing configuration."""
    hass.states.async_set(ENTITY_ID, "on", {"current_power": 750})

    result = read_entity_value(hass, _binding(value_source=VALUE_SOURCE_ATTRIBUTE))

    assert result.ok is False
    assert result.reason_code == REASON_MISSING_REQUIRED_DATA


async def test_an_unavailable_attribute_value_is_refused(
    hass: HomeAssistant,
) -> None:
    """An attribute holding "unavailable" is as unusable as such a state."""
    hass.states.async_set(ENTITY_ID, "on", {"current_power": "unavailable"})

    result = read_entity_value(
        hass,
        _binding(value_source=VALUE_SOURCE_ATTRIBUTE, attribute_name="current_power"),
    )

    assert result.ok is False
    assert result.reason_code == REASON_INVALID_ENTITY_STATE


async def test_a_meter_that_went_quiet_is_refused(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A state older than the staleness window is no longer a measurement.

    Home Assistant keeps the last state of an entity forever, so a meter that
    stops reporting leaves a number behind that reads as current. This is the
    check that only matters against real hardware: with a slider in a test
    instance the value moves whenever someone moves it (SPEC.md §15).
    """
    hass.states.async_set(ENTITY_ID, "1500")
    assert read_entity_value(hass, _binding(unit=UNIT_W)).ok is True

    freezer.tick(timedelta(minutes=ENTITY_STALE_AFTER_MINUTES + 1))
    result = read_entity_value(hass, _binding(unit=UNIT_W))

    assert result.ok is False
    assert result.value is None
    # Unavailable, not unreadable: nothing is wrong with how the source is
    # configured, the entity simply stopped reporting.
    assert result.unavailable is True
    assert result.reason_code == REASON_INVALID_ENTITY_STATE


async def test_a_steady_reading_is_not_stale(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A meter reporting the same value is alive, not quiet.

    The check reads ``last_reported`` for exactly this reason. Home Assistant
    treats an unchanged report as no change: ``last_changed`` and
    ``last_updated`` both stand still, and only ``last_reported`` moves. A house
    drawing a steady load makes its meter repeat the same number indefinitely,
    so judging age on either of the others declares a healthy meter dead.

    Note there is no ``force_update`` here, deliberately: that would move
    ``last_updated`` too and the test would pass against the wrong attribute.
    """
    hass.states.async_set(ENTITY_ID, "1500")
    freezer.tick(timedelta(minutes=ENTITY_STALE_AFTER_MINUTES + 1))
    # The same value, reported again, exactly as a real meter does it.
    hass.states.async_set(ENTITY_ID, "1500")

    assert read_entity_value(hass, _binding(unit=UNIT_W)).ok is True


async def test_every_refusal_uses_a_stable_reason_code(hass: HomeAssistant) -> None:
    """Reason codes come from the fixed list in SPEC.md §12."""
    hass.states.async_set(ENTITY_ID, "unavailable")

    refused = [
        read_entity_value(hass, EntityBinding()),
        read_entity_value(hass, _binding()),
        read_entity_value(hass, _binding(entity_id="sensor.missing")),
    ]

    assert all(result.reason_code in REASON_CODES for result in refused)


# --- Scale factor, inversion and unit conversion ----------------------------


async def test_scale_factor_is_applied(hass: HomeAssistant) -> None:
    """A meter reporting in units of ten is scaled by the entered factor."""
    hass.states.async_set(ENTITY_ID, "12")

    result = read_entity_value(hass, _binding(unit=UNIT_W, scale_factor=10.0))

    assert result.value == 120.0


async def test_a_fractional_scale_factor_is_applied(hass: HomeAssistant) -> None:
    """A scale factor below one divides the reading."""
    hass.states.async_set(ENTITY_ID, "1000")

    result = read_entity_value(hass, _binding(unit=UNIT_W, scale_factor=0.5))

    assert result.value == 500.0


async def test_invert_value_flips_the_sign(hass: HomeAssistant) -> None:
    """A meter wired the other way round is inverted, not re-interpreted."""
    hass.states.async_set(ENTITY_ID, "800")

    result = read_entity_value(hass, _binding(unit=UNIT_W, invert_value=True))

    assert result.value == -800.0


async def test_inverting_zero_does_not_produce_negative_zero(
    hass: HomeAssistant,
) -> None:
    """An inverted meter reading exactly 0 W reports 0.0, not -0.0.

    IEEE 754 keeps the sign through the negation. ``-0.0 == 0.0`` is true, so
    no assertion on equality would catch this — but the customer sees the state
    ``-0.0`` in the panel, which reads as a defect. ``copysign`` is what
    actually distinguishes the two.
    """
    hass.states.async_set(ENTITY_ID, "0")

    result = read_entity_value(hass, _binding(unit=UNIT_W, invert_value=True))

    assert result.value == 0.0
    assert math.copysign(1.0, result.value) == 1.0


async def test_kilowatts_are_converted_to_watts(hass: HomeAssistant) -> None:
    """Kilowatts become watts: x1000 (SPEC.md §15)."""
    hass.states.async_set(ENTITY_ID, "2.5")

    result = read_entity_value(hass, _binding(unit=UNIT_KW))

    assert result.value == 2500.0


async def test_cents_are_converted_to_euros(hass: HomeAssistant) -> None:
    """ct/kWh -> EUR/kWh is /100 (SPEC.md §15)."""
    hass.states.async_set(ENTITY_ID, "24.5")

    result = read_entity_value(hass, _binding(unit=UNIT_CT_KWH))

    assert result.value == pytest.approx(0.245)


async def test_kilowatt_hours_are_converted_to_watt_hours(
    hass: HomeAssistant,
) -> None:
    """Kilowatt-hours become watt-hours, by the same rule as kW -> W."""
    hass.states.async_set(ENTITY_ID, "3")

    result = read_entity_value(hass, _binding(unit=UNIT_KWH))

    assert result.value == 3000.0


@pytest.mark.parametrize("unit", [UNIT_W, UNIT_EUR_KWH, UNIT_NONE])
async def test_units_that_need_no_conversion(hass: HomeAssistant, unit: str) -> None:
    """The engine's own units pass through untouched."""
    hass.states.async_set(ENTITY_ID, "7")

    assert read_entity_value(hass, _binding(unit=unit)).value == 7.0


async def test_scale_inversion_and_conversion_are_applied_in_order(
    hass: HomeAssistant,
) -> None:
    """Scale, then invert, then convert the unit (SPEC.md §15 steps 6-8)."""
    hass.states.async_set(ENTITY_ID, "1.5")

    result = read_entity_value(
        hass, _binding(unit=UNIT_KW, scale_factor=2.0, invert_value=True)
    )

    # 1.5 x 2 = 3.0 -> -3.0 -> -3000 W
    assert result.value == -3000.0


async def test_the_home_assistant_unit_is_ignored(hass: HomeAssistant) -> None:
    """Conversion follows the chosen unit only, never the entity's own."""
    hass.states.async_set(ENTITY_ID, "2", {"unit_of_measurement": "kW"})

    # The installer said W, so 2 stays 2 even though the entity claims kW.
    assert read_entity_value(hass, _binding(unit=UNIT_W)).value == 2.0


# --- Home profile validation ------------------------------------------------


def test_a_complete_home_profile_has_no_issues() -> None:
    """A correctly filled in home profile validates cleanly."""
    home = HomeProfile(
        phases=PHASES_THREE,
        main_fuse_a=25,
        max_grid_power_w=17250.0,
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.15,
        high_price_threshold_eur_kwh=0.35,
    )

    assert validate_home_profile(home) == []


@pytest.mark.parametrize("fuse", [0, -25, 101, 1000])
def test_an_invalid_main_fuse_is_rejected(fuse: int) -> None:
    """The main fuse must be between 1 and 100 A (SPEC.md §8)."""
    issues = validate_home_profile(HomeProfile(main_fuse_a=fuse))

    assert "main_fuse_a" in _fields(issues)
    assert VALIDATION_OUT_OF_RANGE in _codes(issues)
    assert has_errors(issues) is True


@pytest.mark.parametrize("fuse", [1, 25, 100])
def test_a_valid_main_fuse_is_accepted(fuse: int) -> None:
    """The bounds themselves are valid values."""
    assert validate_home_profile(HomeProfile(main_fuse_a=fuse)) == []


def test_a_missing_main_fuse_is_not_an_error() -> None:
    """An empty optional field is incomplete, not invalid."""
    assert validate_home_profile(HomeProfile()) == []


def test_max_grid_power_of_zero_is_rejected() -> None:
    """Zero would make grid_load_percent divide by zero (SPEC.md §16)."""
    issues = validate_home_profile(HomeProfile(max_grid_power_w=0.0))

    assert _fields(issues) == {"max_grid_power_w"}
    assert VALIDATION_OUT_OF_RANGE in _codes(issues)
    assert has_errors(issues) is True


def test_negative_max_grid_power_is_rejected() -> None:
    """A negative maximum is meaningless."""
    issues = validate_home_profile(HomeProfile(max_grid_power_w=-100.0))

    assert has_errors(issues) is True


def test_max_grid_power_above_the_theoretical_maximum_only_warns() -> None:
    """SPEC.md §8 requires a warning here, never a block."""
    home = HomeProfile(phases=1, main_fuse_a=25, max_grid_power_w=99_000.0)

    issues = validate_home_profile(home)

    assert len(issues) == 1
    assert issues[0].code == VALIDATION_ABOVE_THEORETICAL_MAXIMUM
    assert issues[0].severity == SEVERITY_WARNING
    assert issues[0].is_error is False
    # A warning must not make the row unusable.
    assert has_errors(issues) is False


def test_max_grid_power_at_the_theoretical_maximum_is_fine() -> None:
    """Exactly at the theoretical maximum is not above it."""
    home = HomeProfile(phases=1, main_fuse_a=25, max_grid_power_w=5750.0)

    assert validate_home_profile(home) == []


def test_an_invalid_peak_warning_percentage_is_rejected() -> None:
    """The warning threshold is a percentage."""
    issues = validate_home_profile(HomeProfile(peak_warning_percent=140))

    assert "peak_warning_percent" in _fields(issues)


def test_price_thresholds_must_be_ordered() -> None:
    """The high threshold has to sit above the low one."""
    home = HomeProfile(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        low_price_threshold_eur_kwh=0.40,
        high_price_threshold_eur_kwh=0.20,
    )

    issues = validate_home_profile(home)

    assert "high_price_threshold_eur_kwh" in _fields(issues)
    assert has_errors(issues) is True


def test_a_single_price_threshold_is_not_compared() -> None:
    """One threshold on its own cannot be out of order."""
    home = HomeProfile(
        contract_type=CONTRACT_TYPE_DYNAMIC, low_price_threshold_eur_kwh=0.40
    )

    assert validate_home_profile(home) == []


def test_a_negative_minimum_solar_surplus_is_rejected() -> None:
    """A surplus threshold below zero would make every moment qualify."""
    issues = validate_home_profile(HomeProfile(min_solar_surplus_w=-500.0))

    assert _fields(issues) == {"min_solar_surplus_w"}
    assert VALIDATION_OUT_OF_RANGE in _codes(issues)


def test_a_vat_percentage_outside_the_range_is_rejected() -> None:
    """VAT is a percentage, however editable the field is."""
    issues = validate_home_profile(HomeProfile(vat_percent=210.0))

    assert _fields(issues) == {"vat_percent"}
    assert VALIDATION_OUT_OF_RANGE in _codes(issues)


def test_a_negative_energy_tax_is_rejected() -> None:
    """There is no negative energy tax per kWh; a typo should say so."""
    issues = validate_home_profile(HomeProfile(energy_tax_eur_kwh=-0.1))

    assert _fields(issues) == {"energy_tax_eur_kwh"}


def test_the_default_vat_percentage_validates() -> None:
    """The default the form starts with is itself valid."""
    assert validate_home_profile(HomeProfile()) == []


def test_invalid_choices_in_the_home_profile_are_reported() -> None:
    """A directly constructed profile with nonsense choices is caught."""
    home = HomeProfile(phases=2, contract_type="barter")

    assert _fields(validate_home_profile(home)) == {"phases", "contract_type"}


# --- Energy source validation -----------------------------------------------


def test_a_complete_solar_source_has_no_issues() -> None:
    """A solar source only needs a linked entity."""
    source = EnergySource(
        id="s1",
        name="Omvormer",
        type=SOURCE_TYPE_SOLAR,
        binding=EntityBinding(entity_id="sensor.pv_power", unit=UNIT_W),
    )

    assert validate_energy_source(source) == []


def test_a_source_without_an_entity_is_incomplete() -> None:
    """A source that reads nothing cannot contribute a measurement."""
    issues = validate_energy_source(EnergySource(id="s1", type=SOURCE_TYPE_SOLAR))

    assert _fields(issues) == {"entity_id"}
    assert VALIDATION_REQUIRED in _codes(issues)


def test_a_power_source_in_kwh_is_flagged() -> None:
    """The mistake a real P1 meter invites, caught before it does damage.

    Most Dutch smart meter integrations show the cumulative ``energy_import``
    counter in kWh far more prominently than the instantaneous power sensor.
    Linked to a grid meter it turns 12,000 kWh into 12,000,000 W: a permanent
    peak warning on a perfectly healthy house, with nothing to explain it.
    """
    source = EnergySource.from_dict(
        {
            "id": "s1",
            "type": SOURCE_TYPE_GRID_METER,
            "entity_id": ENTITY_ID,
            "unit": UNIT_KWH,
            "meter_mode": METER_MODE_SINGLE_SIGNED,
            "positive_means": POSITIVE_MEANS_IMPORT,
        }
    )

    issues = validate_energy_source(source)
    mismatch = [issue for issue in issues if issue.code == VALIDATION_UNIT_MISMATCH]

    assert len(mismatch) == 1
    assert mismatch[0].field == "unit"
    # A warning, not an error: a half-finished row has to stay saveable, and
    # this compares two choices rather than finding one of them impossible.
    assert mismatch[0].severity == SEVERITY_WARNING
    assert not has_errors(issues)
    assert "kWh" in mismatch[0].message


@pytest.mark.parametrize("unit", [UNIT_W, UNIT_KW, UNIT_NONE])
def test_a_power_source_in_a_power_unit_is_accepted(unit: str) -> None:
    """W, kW and "no conversion" all describe an instantaneous power."""
    source = EnergySource.from_dict(
        {"id": "s1", "type": SOURCE_TYPE_SOLAR, "entity_id": ENTITY_ID, "unit": unit}
    )

    codes = _codes(validate_energy_source(source))

    assert VALIDATION_UNIT_MISMATCH not in codes


def test_a_price_source_in_watts_is_flagged() -> None:
    """A price is not a power, whichever way round the mistake was made."""
    source = EnergySource.from_dict(
        {
            "id": "s1",
            "type": SOURCE_TYPE_CURRENT_PRICE,
            "entity_id": ENTITY_ID,
            "unit": UNIT_W,
            "price_basis": PRICE_BASIS_ALL_IN,
        }
    )

    codes = _codes(validate_energy_source(source))

    assert VALIDATION_UNIT_MISMATCH in codes


def test_amperes_on_a_power_source_are_flagged() -> None:
    """The same trap with a smaller number: nothing converts amperes."""
    source = EnergySource.from_dict(
        {
            "id": "s1",
            "type": SOURCE_TYPE_HOME_BATTERY,
            "entity_id": ENTITY_ID,
            "unit": UNIT_A,
        }
    )

    codes = _codes(validate_energy_source(source))

    assert VALIDATION_UNIT_MISMATCH in codes


def test_an_unknown_source_type_short_circuits_validation() -> None:
    """Which fields are required depends on the type, so nothing else is checked."""
    source = EnergySource(id="s1", type="grid_metre")

    issues = validate_energy_source(source)

    assert len(issues) == 1
    assert issues[0].code == VALIDATION_UNKNOWN_TYPE
    assert issues[0].field == "type"


def test_a_non_positive_scale_factor_is_rejected() -> None:
    """SPEC.md §8: the scale factor must be greater than zero."""
    source = EnergySource(
        id="s1",
        type=SOURCE_TYPE_SOLAR,
        binding=EntityBinding(entity_id="sensor.pv", scale_factor=0.0),
    )

    assert "scale_factor" in _fields(validate_energy_source(source))


def test_an_attribute_source_without_an_attribute_name_is_incomplete() -> None:
    """The attribute to read is never guessed from the entity."""
    source = EnergySource(
        id="s1",
        type=SOURCE_TYPE_SOLAR,
        binding=EntityBinding(
            entity_id="sensor.pv", value_source=VALUE_SOURCE_ATTRIBUTE
        ),
    )

    assert "attribute_name" in _fields(validate_energy_source(source))


def test_a_unit_outside_the_enum_is_rejected() -> None:
    """The unit is an enum, never free text (SPEC.md §8)."""
    source = EnergySource(
        id="s1",
        type=SOURCE_TYPE_SOLAR,
        binding=EntityBinding(entity_id="sensor.pv", unit="furlongs"),
    )

    assert "unit" in _fields(validate_energy_source(source))


def test_a_grid_meter_without_a_meter_mode_is_incomplete() -> None:
    """The meter mode is never derived from the linked entities (SPEC.md §8)."""
    source = EnergySource(
        id="s1",
        type=SOURCE_TYPE_GRID_METER,
        binding=EntityBinding(entity_id="sensor.grid"),
        import_entity_id="sensor.import",
        export_entity_id="sensor.export",
    )

    issues = validate_energy_source(source)

    assert _fields(issues) == {"meter_mode"}
    assert has_errors(issues) is True


def test_a_signed_grid_meter_needs_to_know_what_positive_means() -> None:
    """Without positive_means the sign of the reading is a guess."""
    source = EnergySource(
        id="s1",
        type=SOURCE_TYPE_GRID_METER,
        binding=EntityBinding(entity_id="sensor.grid"),
        meter_mode=METER_MODE_SINGLE_SIGNED,
    )

    assert _fields(validate_energy_source(source)) == {"positive_means"}


def test_a_signed_grid_meter_needs_an_entity() -> None:
    """A signed meter reads one entity, so that entity is required."""
    source = EnergySource(
        id="s1",
        type=SOURCE_TYPE_GRID_METER,
        meter_mode=METER_MODE_SINGLE_SIGNED,
        positive_means=POSITIVE_MEANS_IMPORT,
    )

    assert _fields(validate_energy_source(source)) == {"entity_id"}


def test_a_complete_signed_grid_meter_has_no_issues() -> None:
    """A fully configured signed meter validates cleanly."""
    source = EnergySource(
        id="s1",
        type=SOURCE_TYPE_GRID_METER,
        binding=EntityBinding(entity_id="sensor.grid", unit=UNIT_W),
        meter_mode=METER_MODE_SINGLE_SIGNED,
        positive_means=POSITIVE_MEANS_IMPORT,
    )

    assert validate_energy_source(source) == []


def test_a_separate_grid_meter_needs_both_entities() -> None:
    """Import and export are two separate readings, both required."""
    source = EnergySource(
        id="s1", type=SOURCE_TYPE_GRID_METER, meter_mode=METER_MODE_SEPARATE
    )

    assert _fields(validate_energy_source(source)) == {
        "import_entity_id",
        "export_entity_id",
    }


def test_a_complete_separate_grid_meter_has_no_issues() -> None:
    """A separate meter does not need the main entity_id."""
    source = EnergySource(
        id="s1",
        type=SOURCE_TYPE_GRID_METER,
        meter_mode=METER_MODE_SEPARATE,
        import_entity_id="sensor.import",
        export_entity_id="sensor.export",
    )

    assert validate_energy_source(source) == []


def test_a_price_source_without_a_basis_is_incomplete() -> None:
    """As strict as the meter mode, because the two readings differ threefold."""
    source = EnergySource(
        id="s1",
        type=SOURCE_TYPE_CURRENT_PRICE,
        binding=EntityBinding(entity_id="sensor.price", unit=UNIT_EUR_KWH),
    )

    issues = validate_energy_source(source)

    assert "price_basis" in _fields(issues)
    assert VALIDATION_REQUIRED in _codes(issues)
    assert has_errors(issues) is True


def test_a_price_source_with_a_basis_has_no_issues() -> None:
    """Stating the basis is all a price source needs beyond its entity."""
    source = EnergySource(
        id="s1",
        type=SOURCE_TYPE_CURRENT_PRICE,
        binding=EntityBinding(entity_id="sensor.price", unit=UNIT_EUR_KWH),
        price_basis=PRICE_BASIS_ALL_IN,
    )

    assert validate_energy_source(source) == []


def test_a_price_source_still_needs_an_entity() -> None:
    """The basis check does not replace the entity check."""
    source = EnergySource(
        id="s1", type=SOURCE_TYPE_CURRENT_PRICE, price_basis=PRICE_BASIS_MARKET
    )

    assert _fields(validate_energy_source(source)) == {"entity_id"}


# --- Device profile validation ----------------------------------------------


def test_a_complete_device_profile_has_no_issues() -> None:
    """A dishwasher with a sane window validates cleanly."""
    device = DeviceProfile(
        id="d1",
        name="Vaatwasser",
        device_type=DEVICE_TYPE_DISHWASHER,
        nominal_power_w=2000.0,
        energy_per_cycle_kwh=1.2,
        duration_minutes=120,
        ready_from="08:00",
        ready_before="23:00",
    )

    assert validate_device_profile(device) == []


def test_a_device_without_a_time_window_is_not_an_error() -> None:
    """No window at all is allowed; it only costs a data quality point."""
    device = DeviceProfile(id="d1", device_type=DEVICE_TYPE_DISHWASHER)

    assert validate_device_profile(device) == []


def test_ready_before_before_ready_from_is_a_midnight_window() -> None:
    """22:00-06:00 is the normal Dutch scenario, not an error (SPEC.md §16)."""
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        ready_from="22:00",
        ready_before="06:00",
    )

    assert validate_device_profile(device) == []


def test_a_run_fitting_inside_a_midnight_window_is_accepted() -> None:
    """The window is eight hours long, so a three hour cycle fits."""
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        duration_minutes=180,
        ready_from="22:00",
        ready_before="06:00",
    )

    assert validate_device_profile(device) == []


def test_a_cycle_longer_than_its_midnight_window_is_accepted() -> None:
    """Ten hours of running against an eight hour finish window is fine.

    It used to be an error, and that was the old `earliest_start` /
    `latest_finish` meaning surviving the rename (SPEC.md §49.1). Both bounds
    are *finish* times now: this device starts between 12:00 and 20:00 and is
    done between 22:00 and 06:00, exactly as the resident asked.
    """
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        duration_minutes=600,
        ready_from="22:00",
        ready_before="06:00",
    )

    assert validate_device_profile(device) == []


def test_an_equal_start_and_finish_is_rejected() -> None:
    """Zero length or a full day: there is no way to tell which was meant."""
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        ready_from="09:00",
        ready_before="09:00",
    )

    issues = validate_device_profile(device)

    assert _fields(issues) == {"ready_before"}
    assert has_errors(issues) is True


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (22 * 60, True),  # exactly at the start, inclusive
        (23 * 60 + 30, True),  # before midnight
        (0, True),  # midnight itself
        (5 * 60 + 59, True),  # just before the end
        (6 * 60, False),  # exactly at the end, exclusive
        (12 * 60, False),  # the middle of the day
    ],
)
def test_a_midnight_window_contains_the_right_moments(now: int, expected: bool) -> None:
    """The shared window helper wraps past midnight (SPEC.md §16)."""
    assert is_within_window(now, 22 * 60, 6 * 60) is expected


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (9 * 60, True),
        (10 * 60, True),
        (11 * 60, False),
        (8 * 60, False),
    ],
)
def test_a_same_day_window_contains_the_right_moments(now: int, expected: bool) -> None:
    """A window that does not wrap uses the plain comparison."""
    assert is_within_window(now, 9 * 60, 11 * 60) is expected


def test_window_length_wraps_past_midnight() -> None:
    """22:00 to 06:00 is eight hours, not minus sixteen."""
    assert window_length_minutes(22 * 60, 6 * 60) == 8 * 60
    assert window_length_minutes(9 * 60, 11 * 60) == 2 * 60


def test_half_a_ready_window_is_allowed() -> None:
    """The two bounds answer different questions, so either may stand alone.

    The start window this replaced needed both ends or neither, because half a
    window was undefined. A ready window is not: "not finished before 09:00"
    guards against spoilage and "finished by 17:00" is a deadline, and a
    resident may well mean only one of them (SPEC.md §32).
    """
    only_from = DeviceProfile(
        id="d1", device_type=DEVICE_TYPE_DISHWASHER, ready_from="09:00"
    )
    only_before = DeviceProfile(
        id="d2", device_type=DEVICE_TYPE_DISHWASHER, ready_before="17:00"
    )

    assert validate_device_profile(only_from) == []
    assert validate_device_profile(only_before) == []


def test_an_impossible_hour_from_the_form_is_reported_not_swallowed() -> None:
    """The message exists; until §49.2 it could never fire from the panel.

    Home Assistant's hour box is an `<input type="number" max="23"
    maxlength="2">`, and `maxlength` does nothing on a number input, so typing
    "0730" in one go is accepted by the control and arrives as an impossible
    hour. `_as_time` turned that into `None` — indistinguishable from "not
    filled in" — so the save reported success and the field was empty on the
    way back, and this validator saw nothing to complain about.

    `_kept_time` keeps it, so the installer is told which field to fix.
    """
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "device_type": DEVICE_TYPE_DISHWASHER,
            "ready_before": "0730:00",
        }
    )

    # Kept rather than dropped: that is what makes the message reachable.
    assert device.ready_before == "0730:00"

    issues = validate_device_profile(device)

    assert _fields(issues) == {"ready_before"}
    assert VALIDATION_INVALID_TIME_WINDOW in _codes(issues)


def test_a_kept_broken_time_still_yields_no_bound_downstream() -> None:
    """Keeping it must not let it reach the engine as a real time.

    Every consumer goes through `minutes_since_midnight`, which still refuses
    it, so the device behaves as one without that bound while the panel shows
    the error.
    """
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "device_type": DEVICE_TYPE_DISHWASHER,
            "duration_minutes": 120,
            "ready_before": "0730:00",
        }
    )

    assert minutes_since_midnight(device.ready_before) is None
    assert device.latest_start is None


def test_an_empty_time_still_means_absent() -> None:
    """Clearing a bound has to stay expressible (SPEC.md §32.2)."""
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "device_type": DEVICE_TYPE_DISHWASHER,
            "ready_from": "",
            "ready_before": None,
        }
    )

    assert device.ready_from is None
    assert device.ready_before is None
    assert validate_device_profile(device) == []


def test_a_malformed_time_is_rejected() -> None:
    """A directly constructed profile can still hold a broken time string."""
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        ready_from="ochtend",
        ready_before="17:00",
    )

    issues = validate_device_profile(device)

    assert _fields(issues) == {"ready_from"}
    assert VALIDATION_INVALID_TIME_WINDOW in _codes(issues)


def test_the_washing_machine_of_woning_2_validates_cleanly() -> None:
    """The configuration the ready window exists for is not an error.

    **The regression test for SPEC.md §49.1**, written from the resident's own
    words: the washing is not to sit wet, so it may not be finished before
    07:00; they leave at 08:00, so it must be finished by then; the programme
    takes 90 minutes.

    Until this revision that produced a severity-`error` on `duration_minutes`
    — the one number the resident is certain of — because 90 > 60. The device
    starts between 05:30 and 06:30 and finishes inside the hour the resident
    named. Nothing about it is wrong.
    """
    device = DeviceProfile(
        id="wasmachine",
        name="Wasmachine",
        device_type=DEVICE_TYPE_WASHING_MACHINE,
        nominal_power_w=2000.0,
        energy_per_cycle_kwh=0.9,
        duration_minutes=90,
        ready_from="07:00",
        ready_before="08:00",
    )

    assert validate_device_profile(device) == []


def test_a_cycle_of_a_full_day_cannot_carry_a_ready_window() -> None:
    """The one duration-versus-clock rule that does hold (SPEC.md §49.1).

    `latest_start` subtracts the duration modulo 1440, so a 25-hour programme
    with a 07:30 deadline would report a latest start of 06:30 — an hour before
    the finish — and say nothing about it.
    """
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        duration_minutes=25 * 60,
        ready_before="07:30",
    )

    issues = validate_device_profile(device)

    assert _fields(issues) == {"duration_minutes"}
    assert VALIDATION_INVALID_TIME_WINDOW in _codes(issues)


def test_a_long_cycle_without_a_ready_window_is_not_asked_about() -> None:
    """No bound to subtract from, so the clock rule does not apply.

    A requirement is not stated where the value it guards is never used —
    the rule of SPEC.md §16, applied to this check.
    """
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        duration_minutes=25 * 60,
    )

    assert validate_device_profile(device) == []


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("nominal_power_w", {"nominal_power_w": -100.0}),
        ("energy_per_cycle_kwh", {"energy_per_cycle_kwh": -1.0}),
        ("duration_minutes", {"duration_minutes": -30}),
    ],
)
def test_negative_device_numbers_are_rejected(
    field_name: str, kwargs: dict[str, Any]
) -> None:
    """A device cannot use negative power, energy or time."""
    device = DeviceProfile(id="d1", device_type=DEVICE_TYPE_DISHWASHER, **kwargs)

    issues = validate_device_profile(device)

    assert field_name in _fields(issues)
    assert VALIDATION_OUT_OF_RANGE in _codes(issues)


def test_invalid_choices_on_a_device_are_reported() -> None:
    """Priority and control mode are enums, checked as a last line of defence."""
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        priority="urgent",
        control_mode="telepathy",
    )

    assert _fields(validate_device_profile(device)) == {"priority", "control_mode"}


def test_an_unknown_device_type_short_circuits_validation() -> None:
    """As with a source, nothing else can be judged without the type."""
    issues = validate_device_profile(DeviceProfile(id="d1", device_type="heatpump"))

    assert len(issues) == 1
    assert issues[0].code == VALIDATION_UNKNOWN_TYPE
    assert issues[0].field == "device_type"


# --- Preference validation --------------------------------------------------


def test_default_preferences_have_no_issues() -> None:
    """The shipped defaults are valid."""
    assert validate_preferences(UserPreferences()) == []


def test_quiet_hours_across_midnight_are_valid() -> None:
    """22:00-07:00 is the documented example from SPEC.md §16."""
    preferences = UserPreferences(quiet_hours_start="22:00", quiet_hours_end="07:00")

    assert validate_preferences(preferences) == []


def test_identical_quiet_hours_are_rejected() -> None:
    """Start equal to end is either empty or a full day; do not guess."""
    preferences = UserPreferences(quiet_hours_start="22:00", quiet_hours_end="22:00")

    issues = validate_preferences(preferences)

    assert VALIDATION_INVALID_TIME_WINDOW in _codes(issues)


def test_a_malformed_quiet_hour_is_rejected() -> None:
    """A broken time string is reported against its own field."""
    preferences = UserPreferences(quiet_hours_start="avond")

    assert _fields(validate_preferences(preferences)) == {"quiet_hours_start"}


@pytest.mark.parametrize("count", [0, -1, MAX_ADVICE_COUNT + 1])
def test_an_out_of_range_advice_count_is_rejected(count: int) -> None:
    """SPEC.md §8: between one and five advices."""
    issues = validate_preferences(UserPreferences(max_advice_count=count))

    assert _fields(issues) == {"max_advice_count"}


def test_a_negative_minimum_saving_is_rejected() -> None:
    """A saving threshold below zero would filter nothing meaningfully."""
    assert _fields(validate_preferences(UserPreferences(min_savings_eur=-1.0))) == {
        "min_savings_eur"
    }


# --- Whole configuration ----------------------------------------------------


def test_validating_a_whole_configuration_groups_issues_per_subject() -> None:
    """Issues are keyed by row id so the panel can mark the right rows."""
    home = HomeProfile(max_grid_power_w=0.0)
    sources = [
        EnergySource(id="s1", type=SOURCE_TYPE_SOLAR, binding=_binding()),
        EnergySource(id="s2", type="grid_metre"),
    ]
    devices = [
        # A window across midnight is fine; equal ends are not.
        DeviceProfile(
            id="d1",
            device_type=DEVICE_TYPE_DISHWASHER,
            ready_from="22:00",
            ready_before="06:00",
        ),
        DeviceProfile(
            id="d2",
            device_type=DEVICE_TYPE_DISHWASHER,
            ready_from="09:00",
            ready_before="09:00",
        ),
    ]

    issues = validate_configuration(home, sources, devices, UserPreferences())

    # Only the broken subjects appear.
    assert set(issues) == {"home", "s2", "d2"}
    assert issues["s2"][0].code == VALIDATION_UNKNOWN_TYPE
    assert issues["d2"][0].code == VALIDATION_INVALID_TIME_WINDOW


def test_preference_issues_get_their_own_key() -> None:
    """Preferences are reported separately from the home profile."""
    issues = validate_configuration(
        HomeProfile(), [], [], UserPreferences(max_advice_count=99)
    )

    assert set(issues) == {"preferences"}
    assert _fields(issues["preferences"]) == {"max_advice_count"}


def test_a_market_price_source_demands_the_components_that_complete_it() -> None:
    """The cross-check that makes a silently refused price visible.

    Without it the installer sees a price source that validates cleanly, no
    price anywhere in the panel, and nothing that explains the gap.
    """
    home = HomeProfile(contract_type=CONTRACT_TYPE_DYNAMIC)
    sources = [
        EnergySource(
            id="s1",
            type=SOURCE_TYPE_CURRENT_PRICE,
            binding=EntityBinding(entity_id="sensor.price", unit=UNIT_EUR_KWH),
            price_basis=PRICE_BASIS_MARKET,
        )
    ]

    issues = validate_configuration(home, sources, [], UserPreferences())

    assert set(issues) == {"home"}
    assert _fields(issues["home"]) == {"energy_tax_eur_kwh"}
    assert VALIDATION_REQUIRED in _codes(issues["home"])


def test_an_all_in_price_source_needs_no_components() -> None:
    """Nothing has to be converted, so nothing has to be entered."""
    home = HomeProfile(contract_type=CONTRACT_TYPE_DYNAMIC)
    sources = [
        EnergySource(
            id="s1",
            type=SOURCE_TYPE_CURRENT_PRICE,
            binding=EntityBinding(entity_id="sensor.price", unit=UNIT_EUR_KWH),
            price_basis=PRICE_BASIS_ALL_IN,
        )
    ]

    assert validate_configuration(home, sources, [], UserPreferences()) == {}


def test_a_market_source_with_the_components_produces_no_issues() -> None:
    """Both components filled in is the complete case."""
    home = HomeProfile(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        energy_tax_eur_kwh=0.1088,
        supplier_markup_eur_kwh=0.02,
    )
    sources = [
        EnergySource(
            id="s1",
            type=SOURCE_TYPE_CURRENT_PRICE,
            binding=EntityBinding(entity_id="sensor.price", unit=UNIT_EUR_KWH),
            price_basis=PRICE_BASIS_MARKET,
        )
    ]

    assert validate_configuration(home, sources, [], UserPreferences()) == {}


def test_a_fixed_contract_with_a_market_source_is_asked_too() -> None:
    """The dead end of SPEC.md §49.10, and the inversion of an older test.

    That test read "a fixed contract never consults the live price, so it needs
    no formula". True when it was written; false since 0.13.0, which lets a
    fixed contract fall back to the source when the tariff field is empty. The
    result was a home with a linked market-price source, no price at all, no
    message, and no way to reach the fields that would have fixed it — the
    silent refusal this check exists to prevent, arriving from the other side.

    The 2026-08-07 finding underneath it still stands and is still honoured: a
    message must not land on a hidden field. `contractSchema` in `home.js` now
    shows the composition fields on the same condition this fires on.
    """
    home = HomeProfile(
        contract_type=CONTRACT_TYPE_FIXED,
        energy_tax_eur_kwh=None,
        supplier_markup_eur_kwh=None,
    )
    sources = [
        EnergySource(
            id="s1",
            type=SOURCE_TYPE_CURRENT_PRICE,
            binding=EntityBinding(entity_id="sensor.price", unit=UNIT_EUR_KWH),
            price_basis=PRICE_BASIS_MARKET,
        )
    ]

    issues = validate_configuration(home, sources, [], UserPreferences())

    assert "energy_tax_eur_kwh" in _fields(issues["home"])


def test_a_fixed_contract_without_a_market_source_is_not_asked() -> None:
    """The rule is the market price, not the contract — so this stays silent.

    The half that keeps the 2026-08-07 finding fixed: nothing to convert means
    nothing to ask, on any contract.
    """
    home = HomeProfile(
        contract_type=CONTRACT_TYPE_FIXED,
        fixed_import_price_eur_kwh=0.24171,
        energy_tax_eur_kwh=None,
        supplier_markup_eur_kwh=None,
    )

    assert validate_configuration(home, [], [], UserPreferences()) == {}


def test_a_dynamic_contract_is_still_asked() -> None:
    """The pair of the test above: there the components really are needed."""
    home = HomeProfile(
        contract_type=CONTRACT_TYPE_DYNAMIC,
        energy_tax_eur_kwh=None,
        supplier_markup_eur_kwh=None,
    )
    sources = [
        EnergySource(
            id="s1",
            type=SOURCE_TYPE_CURRENT_PRICE,
            binding=EntityBinding(entity_id="sensor.price", unit=UNIT_EUR_KWH),
            price_basis=PRICE_BASIS_MARKET,
        )
    ]

    issues = validate_configuration(home, sources, [], UserPreferences())

    assert [issue.field for issue in issues["home"]] == ["energy_tax_eur_kwh"]


def test_a_feed_in_source_without_a_basis_is_reported() -> None:
    """Shipped in 0.1.4 without this: refused by the engine, reported nowhere.

    `_validate_price_source` ran for the import type only, so a feed-in row with
    no basis simply did nothing and said nothing.
    """
    sources = [
        EnergySource(
            id="f1",
            type=SOURCE_TYPE_FEED_IN_PRICE,
            binding=EntityBinding(entity_id="sensor.terug", unit=UNIT_EUR_KWH),
            price_basis=None,
        )
    ]

    issues = validate_configuration(HomeProfile(), sources, [], UserPreferences())

    assert [issue.field for issue in issues["f1"]] == ["price_basis"]
    # Worded for this side of the meter, not the import side.
    assert "vergoeding" in issues["f1"][0].message


def test_a_market_feed_in_source_without_a_markup_is_reported() -> None:
    """The installer has to see why the feed-in tariff is being ignored.

    Reported against the home, because that is where the missing field lives,
    even though it took a source to make it necessary.
    """
    home = HomeProfile(feed_in_markup_eur_kwh=None)
    sources = [
        EnergySource(
            id="f1",
            type=SOURCE_TYPE_FEED_IN_PRICE,
            binding=EntityBinding(entity_id="sensor.terug", unit=UNIT_EUR_KWH),
            price_basis=PRICE_BASIS_MARKET,
        )
    ]

    issues = validate_configuration(home, sources, [], UserPreferences())

    assert [issue.field for issue in issues["home"]] == ["feed_in_markup_eur_kwh"]


def test_a_feed_in_markup_of_zero_satisfies_the_check() -> None:
    """An explicit zero is an answer; only "not entered" blocks."""
    home = HomeProfile(feed_in_markup_eur_kwh=0.0)
    sources = [
        EnergySource(
            id="f1",
            type=SOURCE_TYPE_FEED_IN_PRICE,
            binding=EntityBinding(entity_id="sensor.terug", unit=UNIT_EUR_KWH),
            price_basis=PRICE_BASIS_MARKET,
        )
    ]

    assert validate_configuration(home, sources, [], UserPreferences()) == {}


def test_an_all_in_feed_in_source_needs_no_markup() -> None:
    """Nothing is being converted, so there is nothing to ask for."""
    home = HomeProfile(feed_in_markup_eur_kwh=None)
    sources = [
        EnergySource(
            id="f1",
            type=SOURCE_TYPE_FEED_IN_PRICE,
            binding=EntityBinding(entity_id="sensor.terug", unit=UNIT_EUR_KWH),
            price_basis=PRICE_BASIS_ALL_IN,
        )
    ]

    assert validate_configuration(home, sources, [], UserPreferences()) == {}


def test_a_disabled_market_source_demands_nothing() -> None:
    """A source the engine will not read cannot make a field necessary."""
    home = HomeProfile(contract_type=CONTRACT_TYPE_DYNAMIC)
    sources = [
        EnergySource(
            id="s1",
            type=SOURCE_TYPE_CURRENT_PRICE,
            enabled=False,
            binding=EntityBinding(entity_id="sensor.price", unit=UNIT_EUR_KWH),
            price_basis=PRICE_BASIS_MARKET,
        )
    ]

    assert validate_configuration(home, sources, [], UserPreferences()) == {}


def test_the_component_issue_joins_the_other_home_issues() -> None:
    """It is added to the home key rather than replacing what is already there."""
    home = HomeProfile(contract_type=CONTRACT_TYPE_DYNAMIC, max_grid_power_w=0.0)
    sources = [
        EnergySource(
            id="s1",
            type=SOURCE_TYPE_CURRENT_PRICE,
            binding=EntityBinding(entity_id="sensor.price", unit=UNIT_EUR_KWH),
            price_basis=PRICE_BASIS_MARKET,
        )
    ]

    issues = validate_configuration(home, sources, [], UserPreferences())

    assert _fields(issues["home"]) == {"max_grid_power_w", "energy_tax_eur_kwh"}


def test_a_valid_configuration_produces_no_issues() -> None:
    """Nothing wrong means an empty mapping, not a mapping of empty lists."""
    home = HomeProfile(phases=PHASES_THREE, main_fuse_a=25, max_grid_power_w=17250.0)
    sources = [
        EnergySource(
            id="s1",
            type=SOURCE_TYPE_GRID_METER,
            binding=EntityBinding(entity_id="sensor.grid", unit=UNIT_W),
            meter_mode=METER_MODE_SINGLE_SIGNED,
            positive_means=POSITIVE_MEANS_IMPORT,
        )
    ]

    assert validate_configuration(home, sources, [], UserPreferences()) == {}


# --- Result objects ---------------------------------------------------------


def test_read_result_carries_no_fallback_value() -> None:
    """A refusal never offers a number the caller might accidentally use."""
    result = ReadResult.failed(REASON_INVALID_ENTITY_STATE, ENTITY_ID)

    assert result.ok is False
    assert result.value is None
    assert result.entity_id == ENTITY_ID


def test_validation_issue_severity_defaults_to_error() -> None:
    """Most issues block use; a warning has to be asked for explicitly."""
    issue = ValidationIssue("field", VALIDATION_REQUIRED, "Bericht")

    assert issue.severity == SEVERITY_ERROR
    assert issue.is_error is True


# --- Capability, intent and agreement (SPEC.md §12) -------------------------


async def test_wanting_control_without_the_capability_warns(
    hass: HomeAssistant,
) -> None:
    """Intent beyond what the hardware can do is a warning, not a block.

    The installer may be describing hardware they are about to replace, and
    0.1.0 controls nothing either way.
    """
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "name": "Enphase",
            "device_type": DEVICE_TYPE_GENERIC_MONITOR,
            "control_mode": CONTROL_AUTOMATIC,
            "capabilities": [CAPABILITY_READ],
        }
    )

    issues = validate_device_profile(device)
    capability_issues = [
        issue for issue in issues if issue.code == VALIDATION_CAPABILITY_MISSING
    ]

    assert len(capability_issues) == 1
    assert capability_issues[0].severity == SEVERITY_WARNING
    assert not has_errors(issues)


async def test_control_capability_satisfies_the_intent(hass: HomeAssistant) -> None:
    """Hardware that can be driven raises nothing."""
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "name": "Easee",
            "device_type": DEVICE_TYPE_EV_CHARGER,
            "control_mode": CONTROL_AUTOMATIC,
            "capabilities": [CAPABILITY_READ, CAPABILITY_SET_CURRENT],
        }
    )

    assert validate_device_profile(device) == []


async def test_a_forbidden_device_may_not_be_set_to_automatic(
    hass: HomeAssistant,
) -> None:
    """The one hard block: an agreement outranks any later intention.

    A customer with medical equipment, or a specific arrangement, must stay
    off limits whatever anyone types into control_mode afterwards.
    """
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "name": "SolarEdge",
            "device_type": DEVICE_TYPE_GENERIC_SCHEDULABLE,
            "control_mode": CONTROL_AUTOMATIC,
            "capabilities": [CAPABILITY_READ, CAPABILITY_SET_POWER_LIMIT],
            "control_forbidden": True,
            "control_forbidden_reason": "Medische apparatuur in de woning.",
        }
    )

    issues = validate_device_profile(device)
    forbidden = [
        issue for issue in issues if issue.code == VALIDATION_CONTROL_FORBIDDEN
    ]

    assert len(forbidden) == 1
    assert forbidden[0].severity == SEVERITY_ERROR
    # An error, so the row is refused rather than merely flagged.
    assert has_errors(issues)


async def test_a_forbidden_device_may_still_advise(hass: HomeAssistant) -> None:
    """Advising is not controlling, so advice_only stays allowed."""
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "name": "SolarEdge",
            "device_type": DEVICE_TYPE_GENERIC_SCHEDULABLE,
            "control_mode": CONTROL_ADVICE_ONLY,
            "control_forbidden": True,
            "control_forbidden_reason": "Afspraak met de klant.",
        }
    )

    assert validate_device_profile(device) == []


async def test_a_forbidden_row_without_a_reason_warns(hass: HomeAssistant) -> None:
    """The reason is the point: without it the flag is unreadable in two years."""
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "name": "SolarEdge",
            "device_type": DEVICE_TYPE_GENERIC_SCHEDULABLE,
            "control_forbidden": True,
        }
    )

    issues = validate_device_profile(device)

    assert [issue.field for issue in issues] == ["control_forbidden_reason"]
    assert not has_errors(issues)


async def test_a_source_carries_the_same_agreement(hass: HomeAssistant) -> None:
    """A controllable inverter is a source, so the flag belongs there too.

    Without it a SolarEdge that can be read *and* limited would have to be
    entered twice, as a source and as a device, on one piece of hardware.
    """
    source = EnergySource.from_dict(
        {
            "id": "s1",
            "name": "SolarEdge",
            "type": SOURCE_TYPE_SOLAR,
            "entity_id": "sensor.solaredge",
            "capabilities": [CAPABILITY_READ, CAPABILITY_SET_POWER_LIMIT],
            "control_forbidden": True,
        }
    )

    issues = validate_energy_source(source)

    assert [issue.code for issue in issues] == [VALIDATION_REQUIRED]
    assert issues[0].field == "control_forbidden_reason"


# --- How long a source may stay quiet (SPEC.md §47) --------------------------
#
# Written from the situation, because the situation is what went wrong: a
# perfectly healthy home whose price sensor publishes once an hour and whose
# export sensor reads zero all night was told its sources could not be read.
# See CLAUDE.md, eighth variant — the old rule made an assumption about the
# world (every source reports within a quarter of an hour) that no unit test
# could contradict, because every unit test writes its state a moment before
# reading it.


def test_every_source_type_has_a_staleness_window() -> None:
    """A new source type must be given a window, with a reason beside it.

    This is the guard that keeps §47 from decaying back into one constant with
    exceptions: add a type to `SOURCE_TYPES` and forget the window, and this
    fails rather than silently handing it the strictest number.
    """
    missing = [name for name in SOURCE_TYPES if name not in SOURCE_STALE_MINUTES]

    assert not missing, f"no staleness window chosen for {missing} (SPEC.md §47)"


def test_the_three_windows_are_ordered_and_distinct() -> None:
    """Measurement is the strictest, resting the most patient.

    Not decoration: the three exist because they answer the same question for
    things that behave differently, and a change that collapses two of them
    into one number is exactly the regression this section is about.
    """
    assert STALE_AFTER_MINUTES_MEASUREMENT < STALE_AFTER_MINUTES_PRICE
    assert STALE_AFTER_MINUTES_PRICE < STALE_AFTER_MINUTES_RESTING
    assert EXPORT_STALE_MINUTES == STALE_AFTER_MINUTES_RESTING


async def test_an_hourly_price_is_not_stale_after_half_an_hour(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The situation from the first strange installation, in one test.

    A market price is published once an hour and then stands still by design.
    Under the old single window it was refused for three quarters of every
    hour, and the panel said "Geen bruikbare prijsbron" about a sensor that was
    doing exactly what it should.
    """
    hass.states.async_set(ENTITY_ID, "0.089")
    freezer.tick(timedelta(minutes=45))

    refused = read_entity_value(hass, _binding(unit=UNIT_W))
    accepted = read_entity_value(
        hass, _binding(unit=UNIT_W), stale_after_minutes=STALE_AFTER_MINUTES_PRICE
    )

    # The measurement window would still refuse it, and that is right for power.
    assert refused.ok is False
    assert accepted.ok is True
    assert accepted.value == 0.089


async def test_a_price_that_really_stopped_is_still_refused(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The patience has an end, or the rule would protect nothing."""
    hass.states.async_set(ENTITY_ID, "0.089")
    freezer.tick(timedelta(minutes=STALE_AFTER_MINUTES_PRICE + 1))

    result = read_entity_value(
        hass, _binding(unit=UNIT_W), stale_after_minutes=STALE_AFTER_MINUTES_PRICE
    )

    assert result.ok is False
    assert result.unavailable is True


# --- The no-run window (SPEC.md §51) ----------------------------------------


def _dryer(**overrides: object) -> DeviceProfile:
    """Return the dryer of woning 2: under the children's bedroom, no deadline.

    Two hours and a quarter, which is what makes it interesting — a ban that
    starts at 23:00 has to reach back into the evening far enough that the
    machine is not still turning at half past midnight.
    """
    fields: dict[str, object] = {
        "id": "droger",
        "name": "Droger",
        "device_type": DEVICE_TYPE_DRYER,
        "nominal_power_w": 800.0,
        "energy_per_cycle_kwh": 1.6,
        "duration_minutes": 135,
        "no_run_from": "23:00",
        "no_run_until": "07:00",
    }
    fields.update(overrides)
    return DeviceProfile(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("moment", "allowed", "why"),
    [
        ("14:00", True, "the middle of the afternoon, nowhere near the ban"),
        ("07:00", True, "the minute the ban lifts; the finish is inclusive"),
        ("06:59", False, "one minute earlier is still the banned night"),
        ("23:30", False, "started inside the ban"),
        ("22:00", False, "starts before it but would still run at 00:15"),
        ("20:45", True, "stops exactly at 23:00, so 22:59 is its last minute"),
        ("20:46", False, "one minute later it is still turning at 23:00"),
        ("12:00", True, "plenty of room before the evening"),
    ],
)
def test_when_the_dryer_may_run(moment: str, allowed: bool, why: str) -> None:
    """Answer, per moment of the day, whether this appliance may start.

    **A table of situations with the expected answer beside each**, rather than
    one test per branch. That is the shape CLAUDE.md asks for after the tile
    sentence went wrong: asking "which state produces this outcome" confirms a
    branch, asking "given this situation, what should happen" judges the choice
    and forces the edges out into the open.

    The two rows that matter most are 20:45 and 20:46. Testing the starting
    moment alone would pass both and ship exactly the advice the installer drew
    the window to prevent.
    """
    assert _dryer().may_run_at(minutes_since_midnight(moment)) is allowed, why


def test_without_a_duration_only_the_starting_moment_is_judged() -> None:
    """No run to place, so no run to keep out — and never a guessed length."""
    device = _dryer(duration_minutes=None)

    assert device.may_run_at(minutes_since_midnight("22:00")) is True
    assert device.may_run_at(minutes_since_midnight("23:30")) is False


def test_half_a_no_run_window_restricts_nothing() -> None:
    """One edge cannot say when the ban lifts, and midnight is not assumed.

    Guessing would be an unwritten rule, which is the invisible assumption this
    project keeps paying for (SPEC.md §47).
    """
    device = _dryer(no_run_until=None)

    assert device.has_no_run_window is False
    assert device.may_run_at(minutes_since_midnight("23:30")) is True


def test_a_home_without_a_ban_is_never_restricted() -> None:
    """The ordinary appliance, which is most of them."""
    device = _dryer(no_run_from=None, no_run_until=None)

    assert all(device.may_run_at(minute) for minute in range(0, 1440, 30))


def test_a_deadline_inside_the_ban_is_reported() -> None:
    """The category that came into being with the ban (SPEC.md §51).

    The washing machine of woning 2, made impossible: it must be finished
    between 07:00 and 08:00 and takes ninety minutes, so it has to start between
    05:30 and 06:30 — and every one of those minutes is inside a ban that runs
    to 07:00. Without this the appliance is never advised and nothing says why.

    **Both ends of the ready window are set on purpose.** With only a deadline
    there is no start window to test against, and claiming impossibility would
    be inventing an answer; see `_deadline_is_reachable`.
    """
    device = DeviceProfile(
        id="wasmachine",
        device_type=DEVICE_TYPE_WASHING_MACHINE,
        duration_minutes=90,
        ready_from="07:00",
        ready_before="08:00",
        no_run_from="23:00",
        no_run_until="07:00",
    )

    issues = validate_device_profile(device)

    assert _fields(issues) == {"no_run_from"}
    assert VALIDATION_INVALID_TIME_WINDOW in _codes(issues)


def test_a_deadline_the_ban_still_leaves_room_for_is_accepted() -> None:
    """The pair of the test above, and the reason it is not simply "both set".

    Same ban, same duration, the whole window four hours later: finished between
    11:00 and 12:00 means starting between 09:30 and 10:30, which the ban does
    not touch at all.
    """
    device = DeviceProfile(
        id="wasmachine",
        device_type=DEVICE_TYPE_WASHING_MACHINE,
        duration_minutes=90,
        ready_from="11:00",
        ready_before="12:00",
        no_run_from="23:00",
        no_run_until="07:00",
    )

    assert validate_device_profile(device) == []


def test_an_equal_ban_start_and_end_is_refused() -> None:
    """Zero length or a whole day: there is no way to tell which was meant."""
    device = _dryer(no_run_from="23:00", no_run_until="23:00")

    issues = validate_device_profile(device)

    assert _fields(issues) == {"no_run_until"}


def test_a_broken_ban_time_is_kept_and_reported() -> None:
    """The rule of SPEC.md §49.2, applied to the field it arrived with."""
    device = DeviceProfile.from_dict(
        {
            "id": "d1",
            "device_type": DEVICE_TYPE_DRYER,
            "no_run_from": "0730:00",
            "no_run_until": "07:00",
        }
    )

    assert device.no_run_from == "0730:00"
    assert _fields(validate_device_profile(device)) == {"no_run_from"}


def test_a_broken_ban_time_restricts_nothing_meanwhile() -> None:
    """A typo may not quietly stop every advice while it is being fixed."""
    device = _dryer(no_run_from="ochtend")

    assert device.may_run_at(minutes_since_midnight("23:30")) is True
