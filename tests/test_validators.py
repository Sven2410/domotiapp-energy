"""Tests for reading entity values and validating configuration (SPEC.md §24).

The validation list from SPEC.md §24 is the contract for this file: valid and
invalid entities, negative power, scale factors, missing attributes, invalid
time windows, a latest_finish before earliest_start evaluated as a window across
midnight, an invalid main fuse, max_grid_power_w = 0, and the unit conversions
kW->W and ct->EUR.
"""

import math
from typing import Any

import pytest
from homeassistant.core import HomeAssistant

from custom_components.domotiapp_energy.const import (
    CAPABILITY_READ,
    CAPABILITY_SET_CURRENT,
    CAPABILITY_SET_POWER_LIMIT,
    CONTRACT_TYPE_DYNAMIC,
    CONTROL_ADVICE_ONLY,
    CONTROL_AUTOMATIC,
    DEVICE_TYPE_DISHWASHER,
    DEVICE_TYPE_EV_CHARGER,
    DEVICE_TYPE_GENERIC_MONITOR,
    DEVICE_TYPE_GENERIC_SCHEDULABLE,
    MAX_ADVICE_COUNT,
    METER_MODE_SEPARATE,
    METER_MODE_SINGLE_SIGNED,
    PHASES_THREE,
    POSITIVE_MEANS_IMPORT,
    PRICE_BASIS_ALL_IN,
    PRICE_BASIS_MARKET,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SOURCE_TYPE_CURRENT_PRICE,
    SOURCE_TYPE_GRID_METER,
    SOURCE_TYPE_SOLAR,
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
)
from custom_components.domotiapp_energy.validators import (
    ReadResult,
    ValidationIssue,
    has_errors,
    is_within_window,
    read_entity_value,
    validate_configuration,
    validate_device_profile,
    validate_energy_source,
    validate_home_profile,
    validate_preferences,
    window_length_minutes,
)

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
    home = HomeProfile(phases=2, contract_type="barter", default_strategy="vibes")

    assert _fields(validate_home_profile(home)) == {
        "phases",
        "contract_type",
        "default_strategy",
    }


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
        earliest_start="08:00",
        latest_finish="23:00",
    )

    assert validate_device_profile(device) == []


def test_a_device_without_a_time_window_is_not_an_error() -> None:
    """No window at all is allowed; it only costs a data quality point."""
    device = DeviceProfile(id="d1", device_type=DEVICE_TYPE_DISHWASHER)

    assert validate_device_profile(device) == []


def test_latest_finish_before_earliest_start_is_a_midnight_window() -> None:
    """22:00-06:00 is the normal Dutch scenario, not an error (SPEC.md §16)."""
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        earliest_start="22:00",
        latest_finish="06:00",
    )

    assert validate_device_profile(device) == []


def test_a_run_fitting_inside_a_midnight_window_is_accepted() -> None:
    """The window is eight hours long, so a three hour cycle fits."""
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        duration_minutes=180,
        earliest_start="22:00",
        latest_finish="06:00",
    )

    assert validate_device_profile(device) == []


def test_a_run_too_long_for_a_midnight_window_is_rejected() -> None:
    """The length wraps as (finish - start) mod 1440, so ten hours does not fit."""
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        duration_minutes=600,
        earliest_start="22:00",
        latest_finish="06:00",
    )

    issues = validate_device_profile(device)

    assert _fields(issues) == {"duration_minutes"}
    assert VALIDATION_INVALID_TIME_WINDOW in _codes(issues)


def test_an_equal_start_and_finish_is_rejected() -> None:
    """Zero length or a full day: there is no way to tell which was meant."""
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        earliest_start="09:00",
        latest_finish="09:00",
    )

    issues = validate_device_profile(device)

    assert _fields(issues) == {"latest_finish"}
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


def test_half_a_time_window_is_rejected() -> None:
    """One end without the other leaves the window undefined."""
    only_start = DeviceProfile(
        id="d1", device_type=DEVICE_TYPE_DISHWASHER, earliest_start="09:00"
    )
    only_finish = DeviceProfile(
        id="d2", device_type=DEVICE_TYPE_DISHWASHER, latest_finish="17:00"
    )

    assert _fields(validate_device_profile(only_start)) == {"latest_finish"}
    assert _fields(validate_device_profile(only_finish)) == {"earliest_start"}


def test_a_malformed_time_is_rejected() -> None:
    """A directly constructed profile can still hold a broken time string."""
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        earliest_start="ochtend",
        latest_finish="17:00",
    )

    issues = validate_device_profile(device)

    assert _fields(issues) == {"earliest_start"}
    assert VALIDATION_INVALID_TIME_WINDOW in _codes(issues)


def test_a_run_that_does_not_fit_its_window_is_rejected() -> None:
    """A four hour cycle cannot run inside a two hour window."""
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        duration_minutes=240,
        earliest_start="09:00",
        latest_finish="11:00",
    )

    issues = validate_device_profile(device)

    assert _fields(issues) == {"duration_minutes"}
    assert VALIDATION_INVALID_TIME_WINDOW in _codes(issues)


def test_a_run_that_exactly_fills_its_window_is_accepted() -> None:
    """Fitting exactly is still fitting."""
    device = DeviceProfile(
        id="d1",
        device_type=DEVICE_TYPE_DISHWASHER,
        duration_minutes=120,
        earliest_start="09:00",
        latest_finish="11:00",
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
            earliest_start="22:00",
            latest_finish="06:00",
        ),
        DeviceProfile(
            id="d2",
            device_type=DEVICE_TYPE_DISHWASHER,
            earliest_start="09:00",
            latest_finish="09:00",
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
