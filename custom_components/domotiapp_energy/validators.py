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
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from .const import (
    ALLOWED_PHASES,
    CONTRACT_TYPE_DYNAMIC,
    CONTRACT_TYPES,
    CONTROL_CAPABILITIES,
    CONTROL_MODES,
    CONTROLLING_MODES,
    ENTITY_STALE_AFTER_MINUTES,
    MAX_ADVICE_COUNT,
    MAX_MAIN_FUSE_A,
    MAX_PEAK_WARNING_PERCENT,
    MAX_VAT_PERCENT,
    METER_MODE_SEPARATE,
    METER_MODE_SINGLE_SIGNED,
    METER_MODES,
    MIN_ADVICE_COUNT,
    MIN_MAIN_FUSE_A,
    MIN_PEAK_WARNING_PERCENT,
    MIN_VAT_PERCENT,
    MINUTES_PER_DAY,
    POSITIVE_MEANS_OPTIONS,
    POWER_SOURCE_TYPES,
    POWER_SOURCE_UNITS,
    PRICE_BASES,
    PRICE_BASIS_MARKET,
    PRICE_SOURCE_UNITS,
    PRICED_SOURCE_TYPES,
    PRIORITIES,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
    SOURCE_TYPE_CURRENT_PRICE,
    SOURCE_TYPE_FEED_IN_PRICE,
    SOURCE_TYPE_GRID_METER,
    UNIT_CONVERSION_FACTORS,
    UNITS,
    UNUSABLE_ENTITY_STATES,
    VALIDATION_ABOVE_THEORETICAL_MAXIMUM,
    VALIDATION_CAPABILITY_MISSING,
    VALIDATION_CONTROL_FORBIDDEN,
    VALIDATION_INVALID_CHOICE,
    VALIDATION_INVALID_TIME_WINDOW,
    VALIDATION_OUT_OF_RANGE,
    VALIDATION_REQUIRED,
    VALIDATION_UNIT_MISMATCH,
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
    without_negative_zero,
)

# --- Reading an entity value ------------------------------------------------


@dataclass(slots=True, frozen=True)
class ReadResult:
    """The outcome of reading one linked entity (SPEC.md §15).

    ``value`` is only meaningful when ``ok`` is true, and ``reason_code`` only
    when it is false. ``entity_id`` is always present so the caller can name
    the offending row without looking it up again; it is an empty string when
    the binding had no entity linked at all.

    ``unavailable`` separates the two ways a read can fail, because they need
    different logbook entries (SPEC.md §8): the entity is gone or reports no
    value at all, versus the entity is there and reports something unusable.
    The distinction is made here because this is the only place that knows
    which of the two happened.
    """

    ok: bool
    value: float | None
    reason_code: str | None
    entity_id: str
    unavailable: bool = False

    @classmethod
    def succeeded(cls, value: float, entity_id: str) -> ReadResult:
        """Return a usable measurement."""
        return cls(ok=True, value=value, reason_code=None, entity_id=entity_id)

    @classmethod
    def failed(
        cls, reason_code: str, entity_id: str, *, unavailable: bool = False
    ) -> ReadResult:
        """Return a refusal. There is deliberately no fallback value."""
        return cls(
            ok=False,
            value=None,
            reason_code=reason_code,
            entity_id=entity_id,
            unavailable=unavailable,
        )


def read_entity_value(hass: HomeAssistant, binding: EntityBinding) -> ReadResult:
    """Read one entity and return its value in the engine's own unit.

    The steps are those of SPEC.md §15, in that order: existence, availability,
    age, attribute selection, safe conversion to float, scale factor, inversion,
    unit conversion. A value that fails any step is refused rather than
    replaced — an unavailable meter is not a meter reading zero.

    The age check is the one that only matters against real hardware. Home
    Assistant keeps the last state of an entity forever, so a meter that stops
    reporting leaves a number behind that reads as current. Without this the
    panel showed an hours-old figure with full confidence, and the five-minute
    safety recalculation kept re-reading the same stale value and finding
    nothing wrong (SPEC.md §15).
    """
    entity_id = binding.entity_id
    if entity_id is None:
        return ReadResult.failed(REASON_MISSING_REQUIRED_DATA, "")

    state = _live_state(hass, entity_id)
    if state is None:
        # Removed, renamed or gone quiet. All three are "unavailable" rather
        # than "unreadable": nothing is wrong with how this source is
        # configured, there is simply no current measurement behind it.
        return ReadResult.failed(
            REASON_INVALID_ENTITY_STATE, entity_id, unavailable=True
        )

    raw, reason_code = _select_raw_value(state, binding)
    if reason_code is not None:
        return ReadResult.failed(reason_code, entity_id)

    if _is_unusable(raw):
        # The entity exists but is carrying no measurement at all.
        return ReadResult.failed(
            REASON_INVALID_ENTITY_STATE, entity_id, unavailable=True
        )

    number = as_finite_float(raw)
    if number is None:
        # Present and reporting, but not a number we can use.
        return ReadResult.failed(REASON_INVALID_ENTITY_STATE, entity_id)

    number *= binding.scale_factor
    if binding.invert_value:
        number = -number
    # A unit outside the enum cannot reach this point through from_dict(), but
    # a directly constructed binding could; leaving the value unconverted is
    # the only honest fallback.
    number *= UNIT_CONVERSION_FACTORS.get(binding.unit, 1.0)

    # Inverting a meter that reads exactly zero produces -0.0, which would show
    # up verbatim in the panel and in the sensor state.
    return ReadResult.succeeded(without_negative_zero(number), entity_id)


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


def _live_state(hass: HomeAssistant, entity_id: str) -> State | None:
    """Return the entity's state when it is present and recent enough.

    **``last_reported``, and neither of the other two.** A house drawing a steady
    load makes its meter report the same number over and over, and Home Assistant
    treats an unchanged report as no change at all: it leaves ``last_changed``
    *and* ``last_updated`` where they were and only mutates ``last_reported``
    (``homeassistant/core.py``: "If the state is reported without being changed,
    the existing state will be mutated with an updated last_reported"). Judging
    age on either of the others declares a perfectly healthy meter dead as soon
    as the reading holds still — which is exactly the situation a constant load
    produces.
    """
    state = hass.states.get(entity_id)
    if state is None:
        return None
    age = dt_util.utcnow() - state.last_reported
    if age > timedelta(minutes=ENTITY_STALE_AFTER_MINUTES):
        return None
    return state


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

    def to_dict(self) -> dict[str, str]:
        """Return the issue as the WebSocket API sends it (SPEC.md §14).

        The panel puts ``message`` next to the input named by ``field``; ``code``
        is there so it can render its own text per code instead if it wants to.
        """
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


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

    if not (MIN_VAT_PERCENT <= home.vat_percent <= MAX_VAT_PERCENT):
        issues.append(
            ValidationIssue(
                "vat_percent",
                VALIDATION_OUT_OF_RANGE,
                f"Het btw-percentage moet tussen {MIN_VAT_PERCENT:.0f} en "
                f"{MAX_VAT_PERCENT:.0f} liggen.",
            )
        )

    if home.energy_tax_eur_kwh is not None and home.energy_tax_eur_kwh < 0:
        issues.append(
            ValidationIssue(
                "energy_tax_eur_kwh",
                VALIDATION_OUT_OF_RANGE,
                "De energiebelasting kan niet negatief zijn.",
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
    """Check the price thresholds a dynamic contract needs.

    Both are all-in amounts, because that is what they are compared against
    (SPEC.md §16). Nothing here can check that the installer meant it that way;
    the form label is what carries it.
    """
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


def _validate_unit_matches_type(source: EnergySource) -> list[ValidationIssue]:
    """Warn when the chosen unit does not describe what this type measures.

    Two explicit choices of the installer are compared against each other; no
    entity is looked at and nothing is inferred (SPEC.md §2.1). A warning and
    not an error, because a half-finished row has to stay saveable — but a loud
    one, because the mistake it catches produces a plausible-looking house that
    is wrong by three orders of magnitude.
    """
    unit = source.binding.unit
    if unit not in UNITS:
        # Already reported as an invalid choice; saying it twice helps nobody.
        return []

    if source.type in POWER_SOURCE_TYPES and unit not in POWER_SOURCE_UNITS:
        return [
            ValidationIssue(
                "unit",
                VALIDATION_UNIT_MISMATCH,
                f"Deze bron meet vermogen, maar de eenheid staat op '{unit}'. "
                f"Kies W of kW. Let op: veel slimme-meterintegraties tonen "
                f"vooral de meterstand in kWh; die is een totaal en geen "
                f"vermogen, en levert een netbelasting die honderden keren te "
                f"hoog is.",
                severity=SEVERITY_WARNING,
            )
        ]

    if source.type in PRICED_SOURCE_TYPES and unit not in PRICE_SOURCE_UNITS:
        return [
            ValidationIssue(
                "unit",
                VALIDATION_UNIT_MISMATCH,
                f"Deze bron levert een prijs, maar de eenheid staat op "
                f"'{unit}'. Kies EUR/kWh of ct/kWh.",
                severity=SEVERITY_WARNING,
            )
        ]

    return []


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

    issues.extend(_validate_unit_matches_type(source))

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

    issues.extend(_validate_control(source))

    if source.type == SOURCE_TYPE_GRID_METER:
        issues.extend(_validate_grid_meter(source))
        return issues

    if source.binding.entity_id is None:
        issues.append(
            ValidationIssue(
                "entity_id",
                VALIDATION_REQUIRED,
                "Koppel een entiteit aan deze bron.",
            )
        )
    if source.type in PRICED_SOURCE_TYPES:
        # Both priced types, not just the import one. A feed-in source without a
        # basis was refused by the calculator and reported nowhere, so the row
        # simply did nothing and said nothing — the omission this whole round is
        # about, in the code that shipped it.
        issues.extend(_validate_price_source(source))

    return issues


def _validate_price_source(source: EnergySource) -> list[ValidationIssue]:
    """Check that a priced source says what kind of price it reports.

    As strict as the meter mode, and for the same reason: a bare market price
    and an all-in price differ by roughly a factor of three, so an unstated
    basis is not a gap to fill in with a default but a source that cannot be
    used at all (SPEC.md §16).

    Both priced types land here, each with its own wording: what the two answers
    mean differs, and so does the formula behind them.
    """
    if source.price_basis in PRICE_BASES:
        return []

    if source.type == SOURCE_TYPE_FEED_IN_PRICE:
        message = (
            "Geef aan wat deze bron levert: de kale marktprijs of de vergoeding "
            "die de klant werkelijk krijgt. Zonder die keuze wordt de "
            "terugleververgoeding niet gebruikt."
        )
    else:
        message = (
            "Geef aan wat deze bron levert: de kale marktprijs of de all-in "
            "prijs die de klant betaalt. Zonder die keuze wordt de prijs niet "
            "gebruikt."
        )

    return [ValidationIssue("price_basis", VALIDATION_REQUIRED, message)]


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

    issues.extend(_validate_control(device))
    issues.extend(_validate_time_window(device))
    return issues


def _validate_control(row: DeviceProfile | EnergySource) -> list[ValidationIssue]:
    """Check the intended control against what is possible and what is allowed.

    Three kinds of truth meet here, and they are deliberately not merged:
    ``capabilities`` is what the hardware can do, ``control_mode`` is what the
    installer wants, and ``control_forbidden`` is what was agreed with this
    customer. Only the last one blocks.
    """
    issues: list[ValidationIssue] = []
    control_mode = getattr(row, "control_mode", None)
    wants_control = control_mode in CONTROLLING_MODES

    if row.control_forbidden and wants_control:
        # The one hard block in this file. An agreement not to touch something
        # outranks any intention someone types in later, so this is an error
        # and not a warning.
        issues.append(
            ValidationIssue(
                "control_mode",
                VALIDATION_CONTROL_FORBIDDEN,
                "Voor deze installatie is aansturing uitgesloten. Kies "
                "'alleen monitoren' of 'alleen adviseren'.",
            )
        )
    elif wants_control and not any(
        capability in CONTROL_CAPABILITIES for capability in row.capabilities
    ):
        # A warning, not a block: the installer may be describing hardware they
        # are about to replace, and 0.1.0 controls nothing either way.
        issues.append(
            ValidationIssue(
                "capabilities",
                VALIDATION_CAPABILITY_MISSING,
                "Dit bedieningsniveau vraagt om aansturing, maar er is geen "
                "besturingsmogelijkheid aangevinkt. Controleer wat deze "
                "apparatuur werkelijk ondersteunt.",
                severity=SEVERITY_WARNING,
            )
        )

    if row.control_forbidden and row.control_forbidden_reason is None:
        # Without the reason the flag is unreadable in two years, which is the
        # whole point of recording it.
        issues.append(
            ValidationIssue(
                "control_forbidden_reason",
                VALIDATION_REQUIRED,
                "Noteer waarom aansturing hier is uitgesloten, zodat de reden "
                "later terug te vinden is.",
                severity=SEVERITY_WARNING,
            )
        )

    return issues


def _validate_time_window(device: DeviceProfile) -> list[ValidationIssue]:
    """Check the ready window of a device (SPEC.md §32).

    ``ready_before`` before ``ready_from`` is a window that crosses midnight,
    exactly as it is for the quiet hours (SPEC.md §16). A dishwasher that has to
    be finished between 22:00 and 06:00 is the normal case, not an error. Only a
    window whose ends are equal is refused: that is either empty or a full day
    and there is no way to tell which was meant.

    **Half a window is allowed**, unlike the start window this replaced. The two
    bounds answer different questions — "not before" guards against spoilage,
    "not after" is the deadline — and a resident may well have only one of them.
    """
    malformed = [
        ValidationIssue(
            field_name,
            VALIDATION_INVALID_TIME_WINDOW,
            "Gebruik een geldige tijd in de vorm uu:mm.",
        )
        for value, field_name in (
            (device.ready_from, "ready_from"),
            (device.ready_before, "ready_before"),
        )
        if value is not None and minutes_since_midnight(value) is None
    ]
    if malformed:
        return malformed[:1]

    start_minutes = minutes_since_midnight(device.ready_from)
    finish_minutes = minutes_since_midnight(device.ready_before)
    if start_minutes is None or finish_minutes is None:
        # No window, or half a window. Both are allowed: an absent bound costs a
        # data quality point at most, and the two bounds answer different
        # questions so either may stand alone.
        return []

    if finish_minutes == start_minutes:
        return [
            ValidationIssue(
                "ready_before",
                VALIDATION_INVALID_TIME_WINDOW,
                "De begin- en eindtijd van het gereed-venster mogen niet gelijk zijn.",
            )
        ]

    if device.duration_minutes is not None and (
        device.duration_minutes > window_length_minutes(start_minutes, finish_minutes)
    ):
        return [
            ValidationIssue(
                "duration_minutes",
                VALIDATION_INVALID_TIME_WINDOW,
                "Het apparaat past niet binnen het opgegeven gereed-venster.",
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


def _validate_price_components(
    home: HomeProfile, sources: list[EnergySource]
) -> list[ValidationIssue]:
    """Check that a market price source has what it takes to be normalised.

    The only check in this file that needs two models at once, which is why it
    lives here and not in :func:`validate_home_profile`: whether the energy tax
    and the supplier markup are needed depends entirely on what the price source
    reports. Without them the calculator refuses the price silently as far as
    the installer can see, and this is what makes it visible (SPEC.md §16).

    **Only on a dynamic contract.** A fixed contract never consults
    ``current_price_eur_kwh`` — not in the savings formula, not in
    ``_advise_price``, not in the price component, not in the checklist — so
    asking for the two fields that complete it was asking for input that goes
    nowhere. Worse, the panel hides both fields on a fixed contract, so the
    issue was reported against a field that is not on screen and the installer
    saw nothing at all (production finding, 2026-08-07).
    """
    if home.contract_type != CONTRACT_TYPE_DYNAMIC or home.has_price_components:
        return []

    needs_components = any(
        source.is_usable
        and source.type == SOURCE_TYPE_CURRENT_PRICE
        and source.price_basis == PRICE_BASIS_MARKET
        for source in sources
    )
    if not needs_components:
        return []

    missing = (
        "energy_tax_eur_kwh"
        if home.energy_tax_eur_kwh is None
        else "supplier_markup_eur_kwh"
    )
    return [
        ValidationIssue(
            missing,
            VALIDATION_REQUIRED,
            "De prijsbron levert de kale marktprijs. Vul de energiebelasting en "
            "de opslag van de leverancier per kWh in; zonder die twee is de "
            "all-in prijs niet te berekenen en wordt de prijs niet gebruikt.",
        )
    ]


def _validate_feed_in_components(
    home: HomeProfile, sources: list[EnergySource]
) -> list[ValidationIssue]:
    """Check that a market feed-in source has the markup that completes it.

    The mirror of :func:`_validate_price_components`, and deliberately its own
    function: the feed-in side needs exactly one term, not three, because no
    energy tax or VAT enters that formula (SPEC.md §16).

    An explicit 0 is an answer — plenty of suppliers keep nothing — so only an
    unset markup blocks. Without it the calculator refuses the feed-in tariff
    silently as far as the installer can see.
    """
    if home.has_feed_in_components:
        return []

    needs_markup = any(
        source.is_usable
        and source.type == SOURCE_TYPE_FEED_IN_PRICE
        and source.price_basis == PRICE_BASIS_MARKET
        for source in sources
    )
    if not needs_markup:
        return []

    return [
        ValidationIssue(
            "feed_in_markup_eur_kwh",
            VALIDATION_REQUIRED,
            "De terugleverprijsbron levert de kale marktprijs. Vul in wat de "
            "leverancier per teruggeleverde kWh inhoudt; zonder dat bedrag is "
            "de vergoeding niet te berekenen en wordt de bron niet gebruikt. "
            "Vul 0 in als de leverancier niets inhoudt.",
        )
    ]


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
    if component_issues := _validate_price_components(home, sources):
        # Reported against the home, because that is where the missing fields
        # live, even though it took a source to make them necessary.
        issues.setdefault("home", []).extend(component_issues)
    if feed_in_issues := _validate_feed_in_components(home, sources):
        issues.setdefault("home", []).extend(feed_in_issues)
    if preference_issues := validate_preferences(preferences):
        issues["preferences"] = preference_issues

    for source in sources:
        if source_issues := validate_energy_source(source):
            issues[source.id] = source_issues
    for device in devices:
        if device_issues := validate_device_profile(device):
            issues[device.id] = device_issues

    return issues
