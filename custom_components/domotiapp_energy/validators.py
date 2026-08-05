"""Reading entity values and validating configuration (SPEC.md §15).

Two responsibilities, both of which exist to keep guesswork out of the engine:

* :func:`read_entity_value` turns one linked Home Assistant entity into a
  number, or refuses it with a reason code. Conversion is driven **only** by
  the unit the installer picked and the scale factor they entered — never by
  the entity's own ``unit_of_measurement``, its name or its device class
  (SPEC.md §2.1 and §15).
* the ``validate_*`` functions report what is wrong with a stored model. They
  never repair anything: :mod:`.models` already fills in safe defaults per
  field, and a problem that survives that is one the installer has to see.
  These checks are the semantic and cross-field ones a Voluptuous schema in the
  WebSocket API cannot express.

A :class:`ValidationIssue` with severity ``error`` marks a row the engine must
not use; ``warning`` marks something the installer should look at while the row
stays usable (SPEC.md §8 explicitly requires this for a maximum grid power
above the theoretical maximum).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant, State

from .const import (
    ALLOWED_PHASES,
    CONTRACT_TYPES,
    CONTROL_MODES,
    MAX_ADVICE_COUNT,
    MAX_MAIN_FUSE_A,
    MAX_PEAK_WARNING_PERCENT,
    METER_MODE_SEPARATE,
    METER_MODE_SINGLE_SIGNED,
    METER_MODES,
    MIN_ADVICE_COUNT,
    MIN_MAIN_FUSE_A,
    MIN_PEAK_WARNING_PERCENT,
    MINUTES_PER_DAY,
    POSITIVE_MEANS_OPTIONS,
    PRIORITIES,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SOURCE_TYPE_GRID_METER,
    STRATEGIES,
    UNIT_CONVERSION_FACTORS,
    UNITS,
    UNUSABLE_ENTITY_STATES,
    VALIDATION_ABOVE_THEORETICAL_MAXIMUM,
    VALIDATION_INVALID_CHOICE,
    VALIDATION_INVALID_TIME_WINDOW,
    VALIDATION_OUT_OF_RANGE,
    VALIDATION_REQUIRED,
    VALIDATION_UNKNOWN_TYPE,
    VALUE_SOURCE_ATTRIBUTE,
)
from .engine.reason_codes import (
    REASON_INVALID_ENTITY_STATE,
    REASON_MISSING_REQUIRED_DATA,
)
from .models import (
    DeviceProfile,
    EnergySource,
    EntityBinding,
    HomeProfile,
    UserPreferences,
    as_finite_float,
    minutes_since_midnight,
)

# --- Reading an entity value ------------------------------------------------


@dataclass(slots=True, frozen=True)
class ReadResult:
    """The outcome of reading one linked entity (SPEC.md §15).

    ``value`` is only meaningful when ``ok`` is true, and ``reason_code`` only
    when it is false. ``entity_id`` is always present so the caller can name
    the offending row without looking it up again; it is an empty string when
    the binding had no entity linked at all.
    """

    ok: bool
    value: float | None
    reason_code: str | None
    entity_id: str

    @classmethod
    def succeeded(cls, value: float, entity_id: str) -> ReadResult:
        """Return a usable measurement."""
        return cls(ok=True, value=value, reason_code=None, entity_id=entity_id)

    @classmethod
    def failed(cls, reason_code: str, entity_id: str) -> ReadResult:
        """Return a refusal. There is deliberately no fallback value."""
        return cls(ok=False, value=None, reason_code=reason_code, entity_id=entity_id)


def read_entity_value(hass: HomeAssistant, binding: EntityBinding) -> ReadResult:
    """Read one entity and return its value in the engine's own unit.

    The steps are those of SPEC.md §15, in that order: existence, availability,
    attribute selection, safe conversion to float, scale factor, inversion,
    unit conversion. A value that fails any step is refused rather than
    replaced — an unavailable meter is not a meter reading zero.
    """
    entity_id = binding.entity_id
    if entity_id is None:
        return ReadResult.failed(REASON_MISSING_REQUIRED_DATA, "")

    state = hass.states.get(entity_id)
    if state is None:
        return ReadResult.failed(REASON_INVALID_ENTITY_STATE, entity_id)

    raw, reason_code = _select_raw_value(state, binding)
    if reason_code is not None:
        return ReadResult.failed(reason_code, entity_id)

    number = as_finite_float(raw)
    if number is None or _is_unusable(raw):
        return ReadResult.failed(REASON_INVALID_ENTITY_STATE, entity_id)

    number *= binding.scale_factor
    if binding.invert_value:
        number = -number
    # A unit outside the enum cannot reach this point through from_dict(), but
    # a directly constructed binding could; leaving the value unconverted is
    # the only honest fallback.
    number *= UNIT_CONVERSION_FACTORS.get(binding.unit, 1.0)

    return ReadResult.succeeded(number, entity_id)


def _select_raw_value(state: State, binding: EntityBinding) -> tuple[Any, str | None]:
    """Return the raw value the binding points at, or why there is none."""
    if binding.value_source != VALUE_SOURCE_ATTRIBUTE:
        return state.state, None

    if binding.attribute_name is None:
        # The installer chose "attribute" but never named one; guessing which
        # attribute was meant is exactly what SPEC.md §2.1 forbids.
        return None, REASON_MISSING_REQUIRED_DATA
    if binding.attribute_name not in state.attributes:
        return None, REASON_INVALID_ENTITY_STATE
    return state.attributes[binding.attribute_name], None


def _is_unusable(raw: Any) -> bool:
    """Return whether a raw state or attribute carries no measurement."""
    return isinstance(raw, str) and raw.strip().lower() in UNUSABLE_ENTITY_STATES


# --- Validating stored configuration ----------------------------------------


@dataclass(slots=True, frozen=True)
class ValidationIssue:
    """One problem with a stored model.

    ``field`` is the model attribute the problem is about, so the panel can put
    the message next to the right input. ``code`` is stable and machine
    readable; ``message`` is the Dutch fallback text.
    """

    field: str
    code: str
    message: str
    severity: str = SEVERITY_ERROR

    @property
    def is_error(self) -> bool:
        """Return whether this issue makes the row unusable."""
        return self.severity == SEVERITY_ERROR


def has_errors(issues: list[ValidationIssue]) -> bool:
    """Return whether any issue is severe enough to block use of the row."""
    return any(issue.is_error for issue in issues)


def validate_home_profile(home: HomeProfile) -> list[ValidationIssue]:
    """Return everything wrong with the home profile (SPEC.md §8 "Woning")."""
    issues: list[ValidationIssue] = []

    if home.phases not in ALLOWED_PHASES:
        issues.append(
            ValidationIssue(
                "phases",
                VALIDATION_INVALID_CHOICE,
                "Kies 1 of 3 fasen.",
            )
        )

    if home.main_fuse_a is not None and not (
        MIN_MAIN_FUSE_A <= home.main_fuse_a <= MAX_MAIN_FUSE_A
    ):
        issues.append(
            ValidationIssue(
                "main_fuse_a",
                VALIDATION_OUT_OF_RANGE,
                f"De hoofdzekering moet tussen {MIN_MAIN_FUSE_A} en "
                f"{MAX_MAIN_FUSE_A} ampère liggen.",
            )
        )

    issues.extend(_validate_max_grid_power(home))

    if not (
        MIN_PEAK_WARNING_PERCENT
        <= home.peak_warning_percent
        <= MAX_PEAK_WARNING_PERCENT
    ):
        issues.append(
            ValidationIssue(
                "peak_warning_percent",
                VALIDATION_OUT_OF_RANGE,
                f"De waarschuwingsgrens moet tussen {MIN_PEAK_WARNING_PERCENT} en "
                f"{MAX_PEAK_WARNING_PERCENT} procent liggen.",
            )
        )

    if home.contract_type not in CONTRACT_TYPES:
        issues.append(
            ValidationIssue(
                "contract_type",
                VALIDATION_INVALID_CHOICE,
                "Kies een vast of dynamisch contract.",
            )
        )

    if home.default_strategy not in STRATEGIES:
        issues.append(
            ValidationIssue(
                "default_strategy",
                VALIDATION_INVALID_CHOICE,
                "Kies een geldige standaardstrategie.",
            )
        )

    if home.min_solar_surplus_w < 0:
        issues.append(
            ValidationIssue(
                "min_solar_surplus_w",
                VALIDATION_OUT_OF_RANGE,
                "Het minimale zonneoverschot kan niet negatief zijn.",
            )
        )

    issues.extend(_validate_price_thresholds(home))
    return issues


def _validate_max_grid_power(home: HomeProfile) -> list[ValidationIssue]:
    """Check the maximum grid power, including the fuse relationship."""
    if home.max_grid_power_w is None:
        return []

    if home.max_grid_power_w <= 0:
        # Zero is not "no limit": grid_load_percent divides by this value
        # (SPEC.md §16), so it would make the load unmeasurable rather than
        # unlimited.
        return [
            ValidationIssue(
                "max_grid_power_w",
                VALIDATION_OUT_OF_RANGE,
                "Het maximale netvermogen moet groter zijn dan 0 W.",
            )
        ]

    theoretical = home.theoretical_max_grid_power_w
    if theoretical is not None and home.max_grid_power_w > theoretical:
        # A warning, never a block: the installer may knowingly enter a value
        # above the theoretical maximum (SPEC.md §8).
        return [
            ValidationIssue(
                "max_grid_power_w",
                VALIDATION_ABOVE_THEORETICAL_MAXIMUM,
                f"Het ingevulde netvermogen ligt boven het theoretische maximum "
                f"van {theoretical:.0f} W ({home.phases} x 230 V x "
                f"{home.main_fuse_a} A). Controleer de hoofdzekering.",
                severity=SEVERITY_WARNING,
            )
        ]

    return []


def _validate_price_thresholds(home: HomeProfile) -> list[ValidationIssue]:
    """Check the price thresholds a dynamic contract needs."""
    low = home.low_price_threshold_eur_kwh
    high = home.high_price_threshold_eur_kwh
    if low is None or high is None or low < high:
        return []

    return [
        ValidationIssue(
            "high_price_threshold_eur_kwh",
            VALIDATION_OUT_OF_RANGE,
            "De hoge prijsgrens moet boven de lage prijsgrens liggen.",
        )
    ]


def validate_energy_source(source: EnergySource) -> list[ValidationIssue]:
    """Return everything wrong with one energy source (SPEC.md §8)."""
    if source.invalid_reason is not None:
        # An unrecognised type makes every other check meaningless: which
        # fields are required depends on the type.
        return [
            ValidationIssue(
                "type",
                VALIDATION_UNKNOWN_TYPE,
                f"Het brontype '{source.type}' is niet bekend. Kies een geldig type.",
            )
        ]

    issues: list[ValidationIssue] = []

    if source.binding.unit not in UNITS:
        issues.append(
            ValidationIssue(
                "unit",
                VALIDATION_INVALID_CHOICE,
                "Kies een geldige eenheid.",
            )
        )

    if source.binding.scale_factor <= 0:
        issues.append(
            ValidationIssue(
                "scale_factor",
                VALIDATION_OUT_OF_RANGE,
                "De schaalfactor moet groter zijn dan 0.",
            )
        )

    if (
        source.binding.value_source == VALUE_SOURCE_ATTRIBUTE
        and source.binding.attribute_name is None
    ):
        issues.append(
            ValidationIssue(
                "attribute_name",
                VALIDATION_REQUIRED,
                "Vul de naam in van het attribuut dat uitgelezen moet worden.",
            )
        )

    if source.type == SOURCE_TYPE_GRID_METER:
        issues.extend(_validate_grid_meter(source))
    elif source.binding.entity_id is None:
        issues.append(
            ValidationIssue(
                "entity_id",
                VALIDATION_REQUIRED,
                "Koppel een entiteit aan deze bron.",
            )
        )

    return issues


def _validate_grid_meter(source: EnergySource) -> list[ValidationIssue]:
    """Check the extra fields a grid meter needs (SPEC.md §8).

    The meter mode is never derived from the configured entities: a meter with
    two entities linked but no mode chosen stays unusable until the installer
    says what those entities mean.
    """
    if source.meter_mode not in METER_MODES:
        return [
            ValidationIssue(
                "meter_mode",
                VALIDATION_REQUIRED,
                "Kies hoe de netmeter meet: één ondertekende waarde of "
                "gescheiden afname en teruglevering.",
            )
        ]

    issues: list[ValidationIssue] = []

    if source.meter_mode == METER_MODE_SINGLE_SIGNED:
        if source.binding.entity_id is None:
            issues.append(
                ValidationIssue(
                    "entity_id",
                    VALIDATION_REQUIRED,
                    "Koppel een entiteit aan deze bron.",
                )
            )
        if source.positive_means not in POSITIVE_MEANS_OPTIONS:
            issues.append(
                ValidationIssue(
                    "positive_means",
                    VALIDATION_REQUIRED,
                    "Geef aan of een positieve waarde afname of teruglevering "
                    "betekent.",
                )
            )
    elif source.meter_mode == METER_MODE_SEPARATE:
        if source.import_entity_id is None:
            issues.append(
                ValidationIssue(
                    "import_entity_id",
                    VALIDATION_REQUIRED,
                    "Koppel de entiteit die de afname meet.",
                )
            )
        if source.export_entity_id is None:
            issues.append(
                ValidationIssue(
                    "export_entity_id",
                    VALIDATION_REQUIRED,
                    "Koppel de entiteit die de teruglevering meet.",
                )
            )

    return issues


def validate_device_profile(device: DeviceProfile) -> list[ValidationIssue]:
    """Return everything wrong with one device profile (SPEC.md §8)."""
    if device.invalid_reason is not None:
        return [
            ValidationIssue(
                "device_type",
                VALIDATION_UNKNOWN_TYPE,
                f"Het apparaattype '{device.device_type}' is niet bekend. "
                f"Kies een geldig type.",
            )
        ]

    issues: list[ValidationIssue] = []

    if device.priority not in PRIORITIES:
        issues.append(
            ValidationIssue(
                "priority", VALIDATION_INVALID_CHOICE, "Kies een geldige prioriteit."
            )
        )

    if device.control_mode not in CONTROL_MODES:
        issues.append(
            ValidationIssue(
                "control_mode",
                VALIDATION_INVALID_CHOICE,
                "Kies een geldig bedieningsniveau.",
            )
        )

    for field_name, value, label in (
        ("nominal_power_w", device.nominal_power_w, "Het nominale vermogen"),
        (
            "energy_per_cycle_kwh",
            device.energy_per_cycle_kwh,
            "Het energieverbruik per cyclus",
        ),
        ("duration_minutes", device.duration_minutes, "De duur"),
    ):
        if value is not None and value < 0:
            issues.append(
                ValidationIssue(
                    field_name,
                    VALIDATION_OUT_OF_RANGE,
                    f"{label} kan niet negatief zijn.",
                )
            )

    issues.extend(_validate_time_window(device))
    return issues


def _validate_time_window(device: DeviceProfile) -> list[ValidationIssue]:
    """Check the allowed time window of a device.

    ``latest_finish`` before ``earliest_start`` is a window that crosses
    midnight, exactly as it is for the quiet hours (SPEC.md §16). A dishwasher
    allowed to run from 22:00 to 06:00 is the normal case, not an error. Only a
    window whose ends are equal is refused: that is either empty or a full day
    and there is no way to tell which was meant.
    """
    start = device.earliest_start
    finish = device.latest_finish

    if start is None and finish is None:
        # No window at all is allowed; it only costs a data quality point.
        return []

    if start is None or finish is None:
        return [
            ValidationIssue(
                "latest_finish" if start is not None else "earliest_start",
                VALIDATION_INVALID_TIME_WINDOW,
                "Vul zowel de vroegste start als de laatste eindtijd in, of laat "
                "ze allebei leeg.",
            )
        ]

    start_minutes = minutes_since_midnight(start)
    finish_minutes = minutes_since_midnight(finish)
    if start_minutes is None or finish_minutes is None:
        return [
            ValidationIssue(
                "earliest_start" if start_minutes is None else "latest_finish",
                VALIDATION_INVALID_TIME_WINDOW,
                "Gebruik een geldige tijd in de vorm uu:mm.",
            )
        ]

    if finish_minutes == start_minutes:
        return [
            ValidationIssue(
                "latest_finish",
                VALIDATION_INVALID_TIME_WINDOW,
                "De starttijd en eindtijd mogen niet gelijk zijn.",
            )
        ]

    if device.duration_minutes is not None and (
        device.duration_minutes > window_length_minutes(start_minutes, finish_minutes)
    ):
        return [
            ValidationIssue(
                "duration_minutes",
                VALIDATION_INVALID_TIME_WINDOW,
                "Het apparaat past niet binnen het opgegeven tijdvenster.",
            )
        ]

    return []


def window_length_minutes(start_minutes: int, finish_minutes: int) -> int:
    """Return how long a time window lasts, wrapping past midnight if needed."""
    return (finish_minutes - start_minutes) % MINUTES_PER_DAY


def is_within_window(now_minutes: int, start_minutes: int, finish_minutes: int) -> bool:
    """Return whether a moment falls inside a window that may cross midnight.

    Shared by the device time windows and the quiet hours so both interpret
    "22:00 to 06:00" the same way (SPEC.md §16). The start is inclusive and the
    finish exclusive, so two adjacent windows never both contain a moment.
    """
    if start_minutes < finish_minutes:
        return start_minutes <= now_minutes < finish_minutes
    # The window wraps: it runs from the start to midnight and on to the finish.
    return now_minutes >= start_minutes or now_minutes < finish_minutes


def validate_preferences(preferences: UserPreferences) -> list[ValidationIssue]:
    """Return everything wrong with the advice preferences (SPEC.md §8)."""
    issues: list[ValidationIssue] = []

    if not MIN_ADVICE_COUNT <= preferences.max_advice_count <= MAX_ADVICE_COUNT:
        issues.append(
            ValidationIssue(
                "max_advice_count",
                VALIDATION_OUT_OF_RANGE,
                f"Toon minimaal {MIN_ADVICE_COUNT} en maximaal "
                f"{MAX_ADVICE_COUNT} adviezen.",
            )
        )

    if preferences.min_savings_eur < 0:
        issues.append(
            ValidationIssue(
                "min_savings_eur",
                VALIDATION_OUT_OF_RANGE,
                "De minimale besparing kan niet negatief zijn.",
            )
        )

    start = minutes_since_midnight(preferences.quiet_hours_start)
    end = minutes_since_midnight(preferences.quiet_hours_end)
    if start is None or end is None:
        issues.append(
            ValidationIssue(
                "quiet_hours_start" if start is None else "quiet_hours_end",
                VALIDATION_INVALID_TIME_WINDOW,
                "Gebruik een geldige tijd in de vorm uu:mm.",
            )
        )
    elif start == end:
        # A window that starts where it ends is either empty or a full day.
        # Rather than pick one, ask the installer (SPEC.md §2.1).
        issues.append(
            ValidationIssue(
                "quiet_hours_end",
                VALIDATION_INVALID_TIME_WINDOW,
                "Begin en einde van de stille uren mogen niet gelijk zijn.",
            )
        )

    return issues


def validate_configuration(
    home: HomeProfile,
    sources: list[EnergySource],
    devices: list[DeviceProfile],
    preferences: UserPreferences,
) -> dict[str, list[ValidationIssue]]:
    """Validate a whole configuration and return the issues per subject.

    The keys are ``"home"``, ``"preferences"`` and the id of every source and
    device that has at least one issue, so the panel can mark the offending
    rows without walking the whole configuration again.
    """
    issues: dict[str, list[ValidationIssue]] = {}

    if home_issues := validate_home_profile(home):
        issues["home"] = home_issues
    if preference_issues := validate_preferences(preferences):
        issues["preferences"] = preference_issues

    for source in sources:
        if source_issues := validate_energy_source(source):
            issues[source.id] = source_issues
    for device in devices:
        if device_issues := validate_device_profile(device):
            issues[device.id] = device_issues

    return issues
