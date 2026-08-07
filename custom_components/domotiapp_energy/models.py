"""Typed data models for the DomotiApp Energy integration.

Every model is JSON round-trippable. ``to_dict()`` produces exactly the shape
that is written to storage and sent over the WebSocket API; ``from_dict()``
rebuilds the model from input that may be incomplete, reordered or corrupted.

``from_dict()`` never raises (SPEC.md §12): unknown keys are ignored and any
value that cannot be used falls back to the documented default. That makes a
damaged storage file degrade into a usable configuration instead of preventing
the integration from starting.

Conventions used throughout:

* Times are stored as ``"HH:MM"`` strings; ``"HH:MM:SS"`` from the Home
  Assistant time selector is accepted and normalised.
* Weekdays are integers, Monday = 0 ... Sunday = 6, matching
  ``datetime.weekday()`` so they compare directly against ``dt_util.now()``.
* Timestamps are timezone-aware ``datetime`` objects and serialise to ISO 8601.
* Optional entity links are omitted from the output when unset, never written
  as an empty string (SPEC.md §8).
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Final, Self, cast

from homeassistant.util import dt as dt_util

from .const import (
    ALL_DAYS_OF_WEEK,
    ALL_IN_PRICE_DECIMALS,
    ALLOWED_PHASES,
    CAPABILITIES,
    CONFIDENCE_LEVELS,
    CONFIDENCE_LOW,
    CONTRACT_TYPES,
    CONTROL_ADVICE_ONLY,
    CONTROL_LEVEL_0_1_0,
    CONTROL_MODES,
    CONTROL_MONITOR_ONLY,
    DEFAULT_CONTRACT_TYPE,
    DEFAULT_CONTROL_MODE,
    DEFAULT_HOME_NAME,
    DEFAULT_MAX_ADVICE_COUNT,
    DEFAULT_MIN_SAVINGS_EUR,
    DEFAULT_MIN_SOLAR_SURPLUS_W,
    DEFAULT_NET_METERING_UNTIL,
    DEFAULT_PEAK_WARNING_PERCENT,
    DEFAULT_PHASES,
    DEFAULT_PRIORITY,
    DEFAULT_QUIET_HOURS_END,
    DEFAULT_QUIET_HOURS_START,
    DEFAULT_SCALE_FACTOR,
    DEFAULT_STRATEGY,
    DEFAULT_VAT_PERCENT,
    DEVICE_ENTITY_BINDING_KEYS,
    DEVICE_TYPES,
    EXCLUSIVE_SOURCE_TYPES,
    INFLEXIBLE_BY_DEFAULT_DEVICE_TYPES,
    INITIAL_REVISION,
    INVALID_REASON_UNKNOWN_TYPE,
    MAX_ADVICE_COUNT,
    MAX_DAY_OF_WEEK,
    MAX_HOUR,
    MAX_MAIN_FUSE_A,
    MAX_MINUTE,
    METER_MODES,
    MIN_ADVICE_COUNT,
    MIN_DAY_OF_WEEK,
    MIN_MAIN_FUSE_A,
    MIN_VAT_PERCENT,
    MINUTES_PER_DAY,
    MINUTES_PER_HOUR,
    NOISY_BY_DEFAULT_DEVICE_TYPES,
    NOMINAL_VOLTAGE_PER_PHASE,
    PERCENT_MAX,
    POSITIVE_MEANS_OPTIONS,
    PRICE_BASES,
    PRICE_BASIS_ALL_IN,
    PRICE_BASIS_MARKET,
    PRIORITIES,
    SCHEMA_VERSION,
    SEVERITIES,
    SEVERITY_INFO,
    SOURCE_TYPES,
    STRATEGIES,
    UNIT_NONE,
    UNITS,
    VALUE_SOURCE_STATE,
    VALUE_SOURCES,
)

# A "HH:MM" or "HH:MM:SS" string needs at least an hour and a minute part.
_TIME_PARTS_REQUIRED: Final = 2


class _TypeDefault:
    """Marker for "no explicit choice was made for this flag"."""

    __slots__ = ()


# Sentinel default for the boolean flags whose default depends on the device
# type. A plain ``False`` cannot express this: it is indistinguishable from an
# installer who deliberately switched the flag off. The cast keeps the field
# annotation ``bool``, which is what it always is once __post_init__ has run.
TYPE_DEFAULT: Final[bool] = cast(bool, _TypeDefault())


# --- Defensive coercion helpers ---------------------------------------------
#
# These are deliberately small and total: each one returns a usable value for
# every possible input, so from_dict() never has to guard its callers.


def _as_str(value: Any, default: str) -> str:
    """Return a non-empty string, or the default."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _as_optional_str(value: Any) -> str | None:
    """Return a non-empty string, or None. Empty strings become None."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _as_bool(value: Any, default: bool) -> bool:
    """Return a boolean, or the default for anything that is not one."""
    return value if isinstance(value, bool) else default


def as_finite_float(value: Any) -> float | None:
    """Return a finite float, or None.

    Public because :mod:`.validators` reads entity states with exactly these
    rules: a measurement is either a usable finite number or it is refused.

    Booleans are rejected explicitly: ``bool`` is a subclass of ``int``, so
    ``True`` would otherwise silently become ``1.0``.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def without_negative_zero(value: float) -> float:
    """Return the value with ``-0.0`` collapsed to ``0.0``.

    IEEE 754 keeps the sign through a negation or a multiplication, so
    inverting a meter that reads exactly 0 W yields ``-0.0``. That is
    numerically equal to zero and compares equal to it, but it reaches the
    customer as the state ``-0.0`` in the interface, which reads as a defect.

    Public because every place that flips a sign has to apply it: the unit and
    inversion step in :mod:`.validators`, and the meter normalisation and
    surplus clamp in :mod:`.engine.calculator`.
    """
    return 0.0 if value == 0 else value


def _as_float(value: Any, default: float, *, minimum: float | None = None) -> float:
    """Return a finite float clamped to a lower bound, or the default."""
    number = as_finite_float(value)
    if number is None:
        return default
    if minimum is not None and number < minimum:
        return default
    return number


def _as_optional_float(
    value: Any, *, minimum: float | None = None, maximum: float | None = None
) -> float | None:
    """Return a finite float within bounds, or None."""
    number = as_finite_float(value)
    if number is None:
        return None
    if minimum is not None and number < minimum:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


def _as_int(
    value: Any,
    default: int,
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Return an int clamped to the allowed range, or the default."""
    number = as_finite_float(value)
    if number is None:
        return default
    result = int(number)
    if minimum is not None:
        result = max(result, minimum)
    if maximum is not None:
        result = min(result, maximum)
    return result


def _as_optional_int(
    value: Any, *, minimum: int | None = None, maximum: int | None = None
) -> int | None:
    """Return an int within bounds, or None when it is unusable."""
    number = as_finite_float(value)
    if number is None:
        return None
    result = int(number)
    if minimum is not None and result < minimum:
        return None
    if maximum is not None and result > maximum:
        return None
    return result


def _as_choice(value: Any, allowed: Sequence[Any], default: Any) -> Any:
    """Return the value when it is one of the allowed options, else default."""
    return value if value in allowed else default


def _as_time(value: Any, default: str | None = None) -> str | None:
    """Normalise "HH:MM" or "HH:MM:SS" to "HH:MM"; else return the default."""
    if not isinstance(value, str):
        return default
    parts = value.strip().split(":")
    if len(parts) < _TIME_PARTS_REQUIRED:
        return default
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return default
    if not (0 <= hour <= MAX_HOUR and 0 <= minute <= MAX_MINUTE):
        return default
    return f"{hour:02d}:{minute:02d}"


def minutes_since_midnight(value: str | None) -> int | None:
    """Return "HH:MM" as minutes past midnight, or None when unusable.

    Public because every module that compares two stored times has to agree on
    this conversion: comparing the strings directly only works by accident of
    zero padding.
    """
    normalised = _as_time(value)
    if normalised is None:
        return None
    hour, minute = normalised.split(":")
    return int(hour) * MINUTES_PER_HOUR + int(minute)


def time_at_minutes(minutes: int) -> str:
    """Return minutes past midnight as "HH:MM", wrapping past a full day.

    The inverse of :func:`minutes_since_midnight`. Wrapping is not a rounding
    convenience: a ready window that crosses midnight produces a start time on
    the previous day, and 23:00 plus a three-hour programme really is 02:00.
    """
    wrapped = minutes % MINUTES_PER_DAY
    return f"{wrapped // MINUTES_PER_HOUR:02d}:{wrapped % MINUTES_PER_HOUR:02d}"


def migrate_time_window(data: Mapping[str, Any]) -> tuple[str | None, str | None]:
    """Return the ready window for a device, translating an old start window.

    The pre-0.2 fields were ``earliest_start`` and ``latest_finish``: when a
    device *may run*. The ready window says when it must *be finished*, which is
    what a resident actually means and the only way to express spoilage
    (SPEC.md §32). The translation is faithful::

        ready_from   = earliest_start + duration_minutes
        ready_before = latest_finish

    ``earliest_start`` meant "do not start before"; adding the duration makes
    that exactly "do not be finished before". Without a duration there is
    nothing to add and the old time carries over unchanged.

    Nothing is translated when the new fields are already present, so a
    configuration that has been migrated once is never touched again. This runs
    on **reading**, in memory: `async_load` writes nothing (SPEC.md §13), and
    the translated values reach the disk with the next save the installer makes.
    """
    if "ready_from" in data or "ready_before" in data:
        return _as_time(data.get("ready_from")), _as_time(data.get("ready_before"))

    earliest = _as_time(data.get("earliest_start"))
    latest = _as_time(data.get("latest_finish"))
    if earliest is None:
        return None, latest

    duration = _as_optional_int(data.get("duration_minutes"), minimum=0)
    if duration is None:
        return earliest, latest

    start_minutes = minutes_since_midnight(earliest)
    if start_minutes is None:
        return None, latest
    return time_at_minutes(start_minutes + duration), latest


def _as_days_of_week(value: Any) -> list[int]:
    """Return a sorted list of weekday numbers; empty input means every day."""
    if not isinstance(value, (list, tuple, set)):
        return list(ALL_DAYS_OF_WEEK)
    days = {
        day
        for item in value
        if (
            day := _as_optional_int(
                item, minimum=MIN_DAY_OF_WEEK, maximum=MAX_DAY_OF_WEEK
            )
        )
        is not None
    }
    return sorted(days) if days else list(ALL_DAYS_OF_WEEK)


def _as_date(value: Any) -> date | None:
    """Parse a "YYYY-MM-DD" string into a date, or return None.

    Dates are stored as ISO strings for the same reason times are stored as
    ``"HH:MM"``: the storage file has to stay readable and diffable.
    """
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _as_datetime(value: Any) -> datetime | None:
    """Parse an ISO 8601 timestamp, or return None."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    return dt_util.parse_datetime(value)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    """Return a mapping; anything else becomes an empty one."""
    return value if isinstance(value, Mapping) else {}


def _as_capabilities(value: Any) -> list[str]:
    """Return the recognised capability tokens, in a stable order.

    Unknown tokens are dropped rather than kept: unlike a source or device
    *type*, a capability we do not recognise describes nothing we could act on
    later, so keeping it would only make the list lie about what was checked.
    """
    if not isinstance(value, (list, tuple, set)):
        return []
    chosen = {token for token in value if token in CAPABILITIES}
    return [token for token in CAPABILITIES if token in chosen]


def _as_str_list(value: Any) -> list[str]:
    """Return a list of non-empty strings, dropping anything unusable."""
    if not isinstance(value, (list, tuple)):
        return []
    return [text for item in value if (text := _as_optional_str(item)) is not None]


def _new_id() -> str:
    """Return a new identifier for a manually added source or device."""
    return str(uuid.uuid4())


# --- Configuration models ---------------------------------------------------


@dataclass(slots=True)
class EntityBinding:
    """How a single Home Assistant entity value is read and interpreted.

    The unit is an explicit user choice, never derived from the entity's own
    ``unit_of_measurement`` or its name (SPEC.md §8 and §15).
    """

    entity_id: str | None = None
    value_source: str = VALUE_SOURCE_STATE
    attribute_name: str | None = None
    unit: str = UNIT_NONE
    scale_factor: float = DEFAULT_SCALE_FACTOR
    invert_value: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the binding as a flat JSON-serialisable mapping."""
        return {
            "entity_id": self.entity_id,
            "value_source": self.value_source,
            "attribute_name": self.attribute_name,
            "unit": self.unit,
            "scale_factor": self.scale_factor,
            "invert_value": self.invert_value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a binding from stored data, filling in defaults."""
        data = _as_mapping(data)
        return cls(
            entity_id=_as_optional_str(data.get("entity_id")),
            value_source=_as_choice(
                data.get("value_source"), VALUE_SOURCES, VALUE_SOURCE_STATE
            ),
            attribute_name=_as_optional_str(data.get("attribute_name")),
            unit=_as_choice(data.get("unit"), UNITS, UNIT_NONE),
            # A scale factor must be > 0; 0 or a negative value would silently
            # destroy every measurement, so it falls back to the default.
            scale_factor=_as_float(
                data.get("scale_factor"), DEFAULT_SCALE_FACTOR, minimum=0.0
            )
            or DEFAULT_SCALE_FACTOR,
            invert_value=_as_bool(data.get("invert_value"), False),
        )

    def with_entity_id(self, entity_id: str | None) -> EntityBinding:
        """Return a copy that reads a different entity with the same rules.

        Used for the separate import/export entities of a grid meter, which
        share the unit, scale factor and inversion of their source.
        """
        return EntityBinding(
            entity_id=entity_id,
            value_source=self.value_source,
            attribute_name=self.attribute_name,
            unit=self.unit,
            scale_factor=self.scale_factor,
            invert_value=self.invert_value,
        )


@dataclass(slots=True)
class HomeProfile:
    """The manually entered properties of the home (SPEC.md §8 "Woning")."""

    home_name: str = DEFAULT_HOME_NAME
    phases: int = DEFAULT_PHASES
    main_fuse_a: int | None = None
    max_grid_power_w: float | None = None
    peak_warning_percent: int = DEFAULT_PEAK_WARNING_PERCENT
    contract_type: str = DEFAULT_CONTRACT_TYPE
    # An all-in amount, like every other price in this model: what the customer
    # pays per imported kWh including energy tax and VAT (SPEC.md §16).
    fixed_import_price_eur_kwh: float | None = None
    # The two per-kWh components a bare market price is missing. They live on
    # the home and not on the price source because they belong to the contract:
    # two price sources would otherwise carry two copies that can drift apart.
    energy_tax_eur_kwh: float | None = None
    # No lower bound, unlike the energy tax: a supplier markup can genuinely be
    # negative, and refusing that would push a real contract into "not entered".
    supplier_markup_eur_kwh: float | None = None
    vat_percent: float = DEFAULT_VAT_PERCENT
    # The fixed feed-in tariff, used when no feed_in_price source is linked. An
    # all-in amount: whatever reaches the invoice per fed-in kWh.
    feed_in_price_eur_kwh: float | None = None
    # What the supplier keeps per fed-in kWh on a *dynamic* feed-in contract,
    # subtracted from the market price. No lower bound and no default: some
    # suppliers keep nothing (an explicit 0), and a silent zero would overstate
    # what the customer receives (SPEC.md §16).
    feed_in_markup_eur_kwh: float | None = None
    # Both thresholds are compared against the normalised all-in price, so they
    # are all-in amounts as well (SPEC.md §16).
    low_price_threshold_eur_kwh: float | None = None
    high_price_threshold_eur_kwh: float | None = None
    # What the supplier charges per fed-in kWh. A per-kWh amount, not the
    # monthly band several suppliers bill: the advice is about one appliance
    # cycle, so only the marginal cost is meaningful (SPEC.md §8).
    feed_in_cost_eur_kwh: float | None = None
    # Net metering applies while today is before this date; None means this
    # home has none at all (SPEC.md §16).
    net_metering_until: date | None = DEFAULT_NET_METERING_UNTIL
    min_solar_surplus_w: float = DEFAULT_MIN_SOLAR_SURPLUS_W
    default_strategy: str = DEFAULT_STRATEGY
    # Fixed to advice_only in 0.1.0; the field exists so a later release can
    # widen it without a storage migration (SPEC.md §2.2).
    control_level: str = CONTROL_LEVEL_0_1_0

    def to_dict(self) -> dict[str, Any]:
        """Return the profile as a JSON-serialisable mapping."""
        return {
            "home_name": self.home_name,
            "phases": self.phases,
            "main_fuse_a": self.main_fuse_a,
            "max_grid_power_w": self.max_grid_power_w,
            "peak_warning_percent": self.peak_warning_percent,
            "contract_type": self.contract_type,
            "fixed_import_price_eur_kwh": self.fixed_import_price_eur_kwh,
            "energy_tax_eur_kwh": self.energy_tax_eur_kwh,
            "supplier_markup_eur_kwh": self.supplier_markup_eur_kwh,
            "vat_percent": self.vat_percent,
            "feed_in_price_eur_kwh": self.feed_in_price_eur_kwh,
            "feed_in_markup_eur_kwh": self.feed_in_markup_eur_kwh,
            "low_price_threshold_eur_kwh": self.low_price_threshold_eur_kwh,
            "high_price_threshold_eur_kwh": self.high_price_threshold_eur_kwh,
            "feed_in_cost_eur_kwh": self.feed_in_cost_eur_kwh,
            "net_metering_until": (
                self.net_metering_until.isoformat() if self.net_metering_until else None
            ),
            "min_solar_surplus_w": self.min_solar_surplus_w,
            "default_strategy": self.default_strategy,
            "control_level": self.control_level,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a home profile from stored data, filling in defaults."""
        data = _as_mapping(data)
        return cls(
            home_name=_as_str(data.get("home_name"), DEFAULT_HOME_NAME),
            phases=_as_choice(data.get("phases"), ALLOWED_PHASES, DEFAULT_PHASES),
            main_fuse_a=_as_optional_int(
                data.get("main_fuse_a"),
                minimum=MIN_MAIN_FUSE_A,
                maximum=MAX_MAIN_FUSE_A,
            ),
            max_grid_power_w=_as_optional_float(
                data.get("max_grid_power_w"), minimum=0.0
            ),
            peak_warning_percent=_as_int(
                data.get("peak_warning_percent"),
                DEFAULT_PEAK_WARNING_PERCENT,
                minimum=0,
                maximum=100,
            ),
            contract_type=_as_choice(
                data.get("contract_type"), CONTRACT_TYPES, DEFAULT_CONTRACT_TYPE
            ),
            fixed_import_price_eur_kwh=_as_optional_float(
                data.get("fixed_import_price_eur_kwh")
            ),
            energy_tax_eur_kwh=_as_optional_float(
                data.get("energy_tax_eur_kwh"), minimum=0.0
            ),
            supplier_markup_eur_kwh=_as_optional_float(
                data.get("supplier_markup_eur_kwh")
            ),
            vat_percent=_as_float(
                data.get("vat_percent"), DEFAULT_VAT_PERCENT, minimum=MIN_VAT_PERCENT
            ),
            feed_in_price_eur_kwh=_as_optional_float(data.get("feed_in_price_eur_kwh")),
            feed_in_markup_eur_kwh=_as_optional_float(
                data.get("feed_in_markup_eur_kwh")
            ),
            low_price_threshold_eur_kwh=_as_optional_float(
                data.get("low_price_threshold_eur_kwh")
            ),
            high_price_threshold_eur_kwh=_as_optional_float(
                data.get("high_price_threshold_eur_kwh")
            ),
            feed_in_cost_eur_kwh=_as_optional_float(
                data.get("feed_in_cost_eur_kwh"), minimum=0.0
            ),
            # Key absent means an older file that predates the field, and gets
            # the default. An explicit null is a deliberate "no net metering"
            # and must survive: collapsing the two would silently give every
            # home net metering back on the next load.
            net_metering_until=(
                _as_date(data.get("net_metering_until"))
                if "net_metering_until" in data
                else DEFAULT_NET_METERING_UNTIL
            ),
            min_solar_surplus_w=_as_float(
                data.get("min_solar_surplus_w"),
                DEFAULT_MIN_SOLAR_SURPLUS_W,
                minimum=0.0,
            ),
            default_strategy=_as_choice(
                data.get("default_strategy"), STRATEGIES, DEFAULT_STRATEGY
            ),
            # Whatever is stored, 0.1.0 only ever runs in advice_only.
            control_level=CONTROL_LEVEL_0_1_0,
        )

    def is_net_metering_active(self, today: date) -> bool:
        """Return whether net metering still applies on this date.

        The date is passed in rather than read from the clock, so the engine
        stays a pure function of its input and both regimes are testable
        without moving time.
        """
        if self.net_metering_until is None:
            return False
        return today < self.net_metering_until

    @property
    def has_price_components(self) -> bool:
        """Return whether a bare market price can be completed to an all-in one.

        VAT is deliberately not part of this: it has a default, so it is always
        known. The energy tax and the supplier markup have none, because there
        is no rate that is right for everyone and a zero would silently
        understate the price by more than half.
        """
        return (
            self.energy_tax_eur_kwh is not None
            and self.supplier_markup_eur_kwh is not None
        )

    def all_in_price_eur_kwh(self, price: float, basis: str | None) -> float | None:
        """Return one price source reading as an all-in price, or None.

        ``None`` means the reading cannot be made comparable — no basis was
        chosen, or a market price arrived without the components that complete
        it. The caller then treats the source as unusable rather than letting a
        number of an unknown kind into the engine (SPEC.md §16).

        A method on the profile rather than a function in the engine because
        both the calculator and the validators need it, and the validators
        cannot import the calculator.
        """
        if basis == PRICE_BASIS_ALL_IN:
            return price

        markup = self.supplier_markup_eur_kwh
        tax = self.energy_tax_eur_kwh
        if basis != PRICE_BASIS_MARKET or markup is None or tax is None:
            return None

        all_in = (price + markup + tax) * (1 + self.vat_percent / PERCENT_MAX)
        return round(all_in, ALL_IN_PRICE_DECIMALS)

    @property
    def has_feed_in_components(self) -> bool:
        """Return whether a bare market price can be turned into a feed-in rate.

        Only the markup, because that is the only term in the feed-in formula
        that has no answer of its own. It has no default for the same reason the
        energy tax has none: a silent zero would overstate what the customer
        receives, and 0 is a real answer some suppliers give.
        """
        return self.feed_in_markup_eur_kwh is not None

    def net_feed_in_price_eur_kwh(
        self, price: float, basis: str | None
    ) -> float | None:
        """Return one feed-in source reading as the rate actually received.

        **The import formula deliberately does not apply here**, and that is why
        this method exists beside :meth:`all_in_price_eur_kwh` rather than
        reusing it::

            teruglevering = marktprijs - feed_in_markup_eur_kwh

        No energy tax, because none is levied on power the home did not take,
        and no VAT on top: what the customer receives is what reaches the
        invoice. Running feed-in through the import formula would have
        overstated it roughly threefold — the same factor that made
        ``price_basis`` mandatory in the first place.

        The markup is **subtracted** where the import markup is added: on this
        side of the meter the supplier's cut lowers what you are paid.

        The result may be **negative**, and is returned as such. A negative
        market price is a real event, and then feeding in genuinely costs money;
        clamping it would hide exactly the situation worth knowing about, which
        is the mistake the savings formula made until 0.1.2.

        ``None`` means the reading cannot be made comparable — no basis, or a
        market price without the markup that completes it (SPEC.md §16).
        """
        if basis == PRICE_BASIS_ALL_IN:
            return price

        markup = self.feed_in_markup_eur_kwh
        if basis != PRICE_BASIS_MARKET or markup is None:
            return None

        return round(price - markup, ALL_IN_PRICE_DECIMALS)

    @property
    def theoretical_max_grid_power_w(self) -> float | None:
        """Return phases x 230 V x main fuse, or None when the fuse is unset.

        This is shown as a hint in the GUI only. Every calculation uses
        ``max_grid_power_w`` exclusively (SPEC.md §8).
        """
        if self.main_fuse_a is None:
            return None
        return float(self.phases * NOMINAL_VOLTAGE_PER_PHASE * self.main_fuse_a)


@dataclass(slots=True)
class EnergySource:
    """A manually configured energy source (SPEC.md §8 "Energiebronnen")."""

    id: str = field(default_factory=_new_id)
    name: str = ""
    # An unrecognised type is kept verbatim rather than replaced by a known
    # one: a corrupted grid_meter that came back as general_consumption would
    # silently enter the solar surplus formula as household consumption.
    type: str = ""
    enabled: bool = True
    binding: EntityBinding = field(default_factory=EntityBinding)
    # Grid meter only. Never derived or guessed: when the installer has not
    # chosen a meter mode, the calculator treats the meter as unusable.
    meter_mode: str | None = None
    positive_means: str | None = None
    import_entity_id: str | None = None
    export_entity_id: str | None = None
    # Price source only, and just as strict as meter_mode: without an explicit
    # basis the reading cannot be normalised, so the source stays unused. An
    # existing price source therefore goes unusable until someone states what it
    # reports — which is honest, because that really is unknown (SPEC.md §16).
    price_basis: str | None = None
    notes: str | None = None
    # What this hardware can do. Registering only in 0.1.0 (SPEC.md §12); an
    # empty list means nobody said, not that it can do nothing. A controllable
    # inverter belongs here rather than as a second device profile on the same
    # hardware.
    capabilities: list[str] = field(default_factory=list)
    # What was agreed with this customer, whatever the hardware can do.
    control_forbidden: bool = False
    control_forbidden_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the source as a flat JSON-serialisable mapping."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "enabled": self.enabled,
            "invalid_reason": self.invalid_reason,
            "capabilities": list(self.capabilities),
            "control_forbidden": self.control_forbidden,
            "control_forbidden_reason": self.control_forbidden_reason,
            **self.binding.to_dict(),
            "meter_mode": self.meter_mode,
            "positive_means": self.positive_means,
            "import_entity_id": self.import_entity_id,
            "export_entity_id": self.export_entity_id,
            "price_basis": self.price_basis,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a source from stored data, filling in defaults.

        A source whose type is unrecognised keeps that type and is disabled, so
        the engine can never act on a guess (SPEC.md §12).
        """
        data = _as_mapping(data)
        source_type = _as_str(data.get("type"), "")
        known_type = source_type in SOURCE_TYPES
        return cls(
            id=_as_str(data.get("id"), _new_id()),
            name=_as_str(data.get("name"), ""),
            type=source_type,
            enabled=_as_bool(data.get("enabled"), True) if known_type else False,
            binding=EntityBinding.from_dict(data),
            meter_mode=_as_choice(data.get("meter_mode"), METER_MODES, None),
            positive_means=_as_choice(
                data.get("positive_means"), POSITIVE_MEANS_OPTIONS, None
            ),
            import_entity_id=_as_optional_str(data.get("import_entity_id")),
            export_entity_id=_as_optional_str(data.get("export_entity_id")),
            price_basis=_as_choice(data.get("price_basis"), PRICE_BASES, None),
            notes=_as_optional_str(data.get("notes")),
            capabilities=_as_capabilities(data.get("capabilities")),
            control_forbidden=_as_bool(data.get("control_forbidden"), False),
            control_forbidden_reason=_as_optional_str(
                data.get("control_forbidden_reason")
            ),
        )

    @property
    def invalid_reason(self) -> str | None:
        """Return why this source is unusable, or None when it is fine.

        Derived from the type on every access rather than stored, so a stored
        value can never disagree with the type it describes.
        """
        if self.type not in SOURCE_TYPES:
            return INVALID_REASON_UNKNOWN_TYPE
        return None

    @property
    def is_usable(self) -> bool:
        """Return whether the engine may read and use this source."""
        return self.enabled and self.invalid_reason is None

    @property
    def import_binding(self) -> EntityBinding:
        """Return the binding that reads the separate import entity."""
        return self.binding.with_entity_id(self.import_entity_id)

    @property
    def export_binding(self) -> EntityBinding:
        """Return the binding that reads the separate export entity."""
        return self.binding.with_entity_id(self.export_entity_id)


@dataclass(slots=True)
class DeviceProfile:
    """A manually configured appliance (SPEC.md §8 "Apparaten")."""

    id: str = field(default_factory=_new_id)
    name: str = ""
    # Kept verbatim when unrecognised, for the same reason as EnergySource.type.
    device_type: str = ""
    enabled: bool = True
    priority: str = DEFAULT_PRIORITY
    location: str | None = None
    control_mode: str = DEFAULT_CONTROL_MODE
    nominal_power_w: float | None = None
    energy_per_cycle_kwh: float | None = None
    duration_minutes: int | None = None
    # The ready window (SPEC.md §32). These replaced `earliest_start` and
    # `latest_finish`: a resident thinks in deadlines, not in start times, and
    # the same start time is right or wrong depending on how long the programme
    # runs. The start window is derived from these plus `duration_minutes`,
    # which is what finally gives that field a job.
    ready_from: str | None = None
    ready_before: str | None = None
    days_of_week: list[int] = field(default_factory=lambda: list(ALL_DAYS_OF_WEEK))
    notes: str | None = None
    # Left as TYPE_DEFAULT unless the installer chose a value; __post_init__
    # then resolves it from the device type, so a directly constructed profile
    # gets the same defaults as one rebuilt from storage.
    is_noisy: bool = TYPE_DEFAULT
    is_flexible: bool = TYPE_DEFAULT
    # What this hardware can do, as opposed to control_mode, which is what the
    # installer wants from it. Registering only in 0.1.0 (SPEC.md §12).
    capabilities: list[str] = field(default_factory=list)
    # What was agreed with this customer. Outranks any later intention, which
    # is why it is the one thing validation blocks on rather than warns about.
    control_forbidden: bool = False
    control_forbidden_reason: str | None = None
    # Optional entity links, keyed by DEVICE_ENTITY_BINDING_KEYS. A key is
    # absent when unset; it is never stored as an empty string.
    entity_links: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Resolve the flags that depend on the device type (SPEC.md §8)."""
        if self.is_noisy is TYPE_DEFAULT:
            self.is_noisy = self.device_type in NOISY_BY_DEFAULT_DEVICE_TYPES
        if self.is_flexible is TYPE_DEFAULT:
            self.is_flexible = (
                self.device_type not in INFLEXIBLE_BY_DEFAULT_DEVICE_TYPES
            )

    def to_dict(self) -> dict[str, Any]:
        """Return the device as a flat JSON-serialisable mapping."""
        return {
            "id": self.id,
            "name": self.name,
            "device_type": self.device_type,
            "enabled": self.enabled,
            "invalid_reason": self.invalid_reason,
            "priority": self.priority,
            "location": self.location,
            "control_mode": self.control_mode,
            "nominal_power_w": self.nominal_power_w,
            "energy_per_cycle_kwh": self.energy_per_cycle_kwh,
            "duration_minutes": self.duration_minutes,
            "ready_from": self.ready_from,
            "ready_before": self.ready_before,
            "days_of_week": list(self.days_of_week),
            "notes": self.notes,
            "is_noisy": self.is_noisy,
            "is_flexible": self.is_flexible,
            "capabilities": list(self.capabilities),
            "control_forbidden": self.control_forbidden,
            "control_forbidden_reason": self.control_forbidden_reason,
            **self.entity_links,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a device from stored data, filling in defaults.

        A device whose type is unrecognised keeps that type and is disabled, so
        it never produces advice based on a guess (SPEC.md §12).
        """
        data = _as_mapping(data)
        device_type = _as_str(data.get("device_type"), "")
        known_type = device_type in DEVICE_TYPES
        ready_from, ready_before = migrate_time_window(data)
        return cls(
            id=_as_str(data.get("id"), _new_id()),
            name=_as_str(data.get("name"), ""),
            device_type=device_type,
            enabled=_as_bool(data.get("enabled"), True) if known_type else False,
            priority=_as_choice(data.get("priority"), PRIORITIES, DEFAULT_PRIORITY),
            location=_as_optional_str(data.get("location")),
            control_mode=_as_choice(
                data.get("control_mode"), CONTROL_MODES, DEFAULT_CONTROL_MODE
            ),
            nominal_power_w=_as_optional_float(
                data.get("nominal_power_w"), minimum=0.0
            ),
            energy_per_cycle_kwh=_as_optional_float(
                data.get("energy_per_cycle_kwh"), minimum=0.0
            ),
            duration_minutes=_as_optional_int(data.get("duration_minutes"), minimum=0),
            # Translates a pre-0.2 start window on the way in; see
            # migrate_time_window for why the arithmetic is what it is.
            ready_from=ready_from,
            ready_before=ready_before,
            days_of_week=_as_days_of_week(data.get("days_of_week")),
            notes=_as_optional_str(data.get("notes")),
            # Absent or unusable leaves the sentinel in place, so __post_init__
            # applies the type default. The rule lives in one place only.
            is_noisy=_as_bool(data.get("is_noisy"), TYPE_DEFAULT),
            is_flexible=_as_bool(data.get("is_flexible"), TYPE_DEFAULT),
            capabilities=_as_capabilities(data.get("capabilities")),
            control_forbidden=_as_bool(data.get("control_forbidden"), False),
            control_forbidden_reason=_as_optional_str(
                data.get("control_forbidden_reason")
            ),
            entity_links={
                key: entity_id
                for key in DEVICE_ENTITY_BINDING_KEYS
                if (entity_id := _as_optional_str(data.get(key))) is not None
            },
        )

    @property
    def invalid_reason(self) -> str | None:
        """Return why this device is unusable, or None when it is fine."""
        if self.device_type not in DEVICE_TYPES:
            return INVALID_REASON_UNKNOWN_TYPE
        return None

    @property
    def is_usable(self) -> bool:
        """Return whether the engine may consider this device for advice."""
        return self.enabled and self.invalid_reason is None

    @property
    def effective_control_mode(self) -> str:
        """Return the control mode the backend actually applies.

        In 0.1.0 everything except monitor_only is treated as advice_only
        (SPEC.md §2.2); nothing is ever controlled.
        """
        if self.control_mode == CONTROL_MONITOR_ONLY:
            return CONTROL_MONITOR_ONLY
        return CONTROL_ADVICE_ONLY

    @property
    def has_ready_window(self) -> bool:
        """Return whether the resident stated *anything* about when it must be done.

        One bound is enough, because one bound is a real answer: "klaar om
        20:15" is what most residents mean, and `ready_from` alone guards
        against spoilage. The data quality checklist asks this question — did
        you tell us when this appliance has to be finished — and a deadline
        without a lower bound answers it fully.

        **Split from :attr:`has_complete_ready_window` after a production bug.**
        One predicate served both questions, so a dishwasher with only a
        deadline counted as having no window at all: the checklist reported
        "tijdvensters voor flexibele apparaten" as missing and the data quality
        dropped ten points, for the configuration the ready window exists to
        make possible (SPEC.md §32).
        """
        return self.ready_from is not None or self.ready_before is not None

    @property
    def has_complete_ready_window(self) -> bool:
        """Return whether both ends are set, so a window can be tested against.

        The advisor's question, and a different one: to decide whether *now*
        falls inside the allowed period it needs two edges. A single bound is
        not expressible as a window on a 24-hour clock — "finished by 07:00"
        would have to mean the next 07:00, and which one that is depends on
        when you ask (SPEC.md §32).
        """
        return self.ready_from is not None and self.ready_before is not None

    @property
    def latest_start(self) -> str | None:
        """Return the last moment this device can still start and be on time.

        ``ready_before`` minus the duration. ``None`` when either is missing —
        and the missing duration is the interesting case: without it there is no
        deadline to compute, and the engine falls back to reading
        ``ready_before`` as "may not run after", which is what the old start
        window meant (SPEC.md §32). A duration is never guessed.
        """
        finish = minutes_since_midnight(self.ready_before)
        if finish is None or self.duration_minutes is None:
            return None
        return time_at_minutes(finish - self.duration_minutes)

    @property
    def earliest_start(self) -> str | None:
        """Return the first moment this device may start without finishing early.

        ``ready_from`` minus the duration, on the same terms as
        :attr:`latest_start`. Without a duration the ready time carries over
        unchanged, which is the safe reading: it can only make the window
        smaller, never larger.
        """
        start = minutes_since_midnight(self.ready_from)
        if start is None:
            return None
        if self.duration_minutes is None:
            return self.ready_from
        return time_at_minutes(start - self.duration_minutes)


@dataclass(slots=True)
class UserPreferences:
    """Advice preferences (SPEC.md §8 "Voorkeuren")."""

    quiet_hours_start: str = DEFAULT_QUIET_HOURS_START
    quiet_hours_end: str = DEFAULT_QUIET_HOURS_END
    allow_advice_during_quiet_hours: bool = False
    prefer_solar: bool = True
    prefer_low_price: bool = True
    respect_max_grid_load: bool = True
    # Filters only advice for which a saving was actually calculated; safety,
    # peak, missing-data and neutral advice is never filtered (SPEC.md §8).
    min_savings_eur: float = DEFAULT_MIN_SAVINGS_EUR
    max_advice_count: int = DEFAULT_MAX_ADVICE_COUNT
    show_technical_explanation: bool = True
    show_estimated_savings: bool = True
    show_confidence: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Return the preferences as a JSON-serialisable mapping."""
        return {
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "allow_advice_during_quiet_hours": self.allow_advice_during_quiet_hours,
            "prefer_solar": self.prefer_solar,
            "prefer_low_price": self.prefer_low_price,
            "respect_max_grid_load": self.respect_max_grid_load,
            "min_savings_eur": self.min_savings_eur,
            "max_advice_count": self.max_advice_count,
            "show_technical_explanation": self.show_technical_explanation,
            "show_estimated_savings": self.show_estimated_savings,
            "show_confidence": self.show_confidence,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build preferences from stored data, filling in defaults."""
        data = _as_mapping(data)
        return cls(
            quiet_hours_start=_as_time(
                data.get("quiet_hours_start"), DEFAULT_QUIET_HOURS_START
            )
            or DEFAULT_QUIET_HOURS_START,
            quiet_hours_end=_as_time(
                data.get("quiet_hours_end"), DEFAULT_QUIET_HOURS_END
            )
            or DEFAULT_QUIET_HOURS_END,
            allow_advice_during_quiet_hours=_as_bool(
                data.get("allow_advice_during_quiet_hours"), False
            ),
            prefer_solar=_as_bool(data.get("prefer_solar"), True),
            prefer_low_price=_as_bool(data.get("prefer_low_price"), True),
            respect_max_grid_load=_as_bool(data.get("respect_max_grid_load"), True),
            min_savings_eur=_as_float(
                data.get("min_savings_eur"), DEFAULT_MIN_SAVINGS_EUR, minimum=0.0
            ),
            max_advice_count=_as_int(
                data.get("max_advice_count"),
                DEFAULT_MAX_ADVICE_COUNT,
                minimum=MIN_ADVICE_COUNT,
                maximum=MAX_ADVICE_COUNT,
            ),
            show_technical_explanation=_as_bool(
                data.get("show_technical_explanation"), True
            ),
            show_estimated_savings=_as_bool(data.get("show_estimated_savings"), True),
            show_confidence=_as_bool(data.get("show_confidence"), True),
        )


@dataclass(slots=True)
class LogEntry:
    """A single logbook event (SPEC.md §8 "Logboek").

    Never holds a full Home Assistant state object, a location or any other
    personal data: only the fields below are stored.
    """

    id: str = field(default_factory=_new_id)
    timestamp: datetime = field(default_factory=dt_util.utcnow)
    event_type: str = ""
    title: str = ""
    message: str = ""
    severity: str = SEVERITY_INFO
    # Identifies what the event was about (a source or device id, for example)
    # so repeated events about the same subject can be collapsed.
    subject: str | None = None
    count: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Return the entry as a JSON-serialisable mapping."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "subject": self.subject,
            "count": self.count,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a log entry from stored data, filling in defaults."""
        data = _as_mapping(data)
        return cls(
            id=_as_str(data.get("id"), _new_id()),
            timestamp=_as_datetime(data.get("timestamp")) or dt_util.utcnow(),
            event_type=_as_str(data.get("event_type"), ""),
            title=_as_str(data.get("title"), ""),
            message=_as_str(data.get("message"), ""),
            severity=_as_choice(data.get("severity"), SEVERITIES, SEVERITY_INFO),
            subject=_as_optional_str(data.get("subject")),
            count=_as_int(data.get("count"), 1, minimum=1),
        )


@dataclass(slots=True)
class StoredConfiguration:
    """The complete persisted configuration (SPEC.md §13).

    ``logs`` is ordered newest first, so trimming to the maximum length keeps
    the most recent events.
    """

    schema_version: int = SCHEMA_VERSION
    revision: int = INITIAL_REVISION
    home: HomeProfile = field(default_factory=HomeProfile)
    sources: list[EnergySource] = field(default_factory=list)
    devices: list[DeviceProfile] = field(default_factory=list)
    preferences: UserPreferences = field(default_factory=UserPreferences)
    logs: list[LogEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the configuration as a JSON-serialisable mapping."""
        return {
            "schema_version": self.schema_version,
            "revision": self.revision,
            "home": self.home.to_dict(),
            "sources": [source.to_dict() for source in self.sources],
            "devices": [device.to_dict() for device in self.devices],
            "preferences": self.preferences.to_dict(),
            "logs": [entry.to_dict() for entry in self.logs],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> Self:
        """Build a configuration from stored data, filling in defaults.

        A missing, empty or damaged payload yields a valid default
        configuration rather than an error.
        """
        data = _as_mapping(data)
        return cls(
            schema_version=_as_int(
                data.get("schema_version"), SCHEMA_VERSION, minimum=1
            ),
            revision=_as_int(data.get("revision"), INITIAL_REVISION, minimum=1),
            home=HomeProfile.from_dict(_as_mapping(data.get("home"))),
            sources=[
                EnergySource.from_dict(item)
                for item in _as_sequence(data.get("sources"))
            ],
            devices=[
                DeviceProfile.from_dict(item)
                for item in _as_sequence(data.get("devices"))
            ],
            preferences=UserPreferences.from_dict(_as_mapping(data.get("preferences"))),
            logs=[LogEntry.from_dict(item) for item in _as_sequence(data.get("logs"))],
        )

    @property
    def invalid_sources(self) -> list[EnergySource]:
        """Return the sources the engine must never use."""
        return [source for source in self.sources if source.invalid_reason is not None]

    @property
    def invalid_devices(self) -> list[DeviceProfile]:
        """Return the devices the engine must never use."""
        return [device for device in self.devices if device.invalid_reason is not None]

    @property
    def duplicate_exclusive_sources(self) -> dict[str, list[EnergySource]]:
        """Return the usable rows per source type that occurs more than once.

        A grid meter and a price source may exist only once (SPEC.md §8). Two
        of either is a configuration mistake with no correct resolution: the
        readings do not add up, and choosing one of them would be a guess. The
        engine therefore uses neither, so both rows are reported here.
        """
        by_type: dict[str, list[EnergySource]] = {}
        for source in self.sources:
            if source.is_usable and source.type in EXCLUSIVE_SOURCE_TYPES:
                by_type.setdefault(source.type, []).append(source)

        return {
            source_type: rows for source_type, rows in by_type.items() if len(rows) > 1
        }


def _as_sequence(value: Any) -> list[Mapping[str, Any]]:
    """Return a list of mappings, dropping every entry that is not one."""
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


# --- Runtime result models --------------------------------------------------
#
# These are never persisted. They travel from the calculator to the advisor,
# the coach provider, the WebSocket API and the entities.


@dataclass(slots=True)
class SourceFailure:
    """One configured source that could not be read (SPEC.md §8).

    Carries what the logbook needs and nothing more. The raw state is
    deliberately absent: an entry must never hold a Home Assistant state
    (SPEC.md §13), and knowing *that* a value was unusable is what the
    installer acts on, not what the value happened to be.
    """

    source_id: str
    entity_id: str
    reason_code: str
    # True when the entity is gone or carries no measurement at all, False when
    # it is present and reporting something we cannot use. The two need
    # different logbook events: source_unavailable versus invalid_measurement.
    unavailable: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return the failure as a JSON-serialisable mapping."""
        return {
            "source_id": self.source_id,
            "entity_id": self.entity_id,
            "reason_code": self.reason_code,
            "unavailable": self.unavailable,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a failure from a mapping, filling in defaults."""
        data = _as_mapping(data)
        return cls(
            source_id=_as_str(data.get("source_id"), ""),
            entity_id=_as_str(data.get("entity_id"), ""),
            reason_code=_as_str(data.get("reason_code"), ""),
            unavailable=_as_bool(data.get("unavailable"), False),
        )


@dataclass(slots=True)
class EnergySnapshot:
    """The raw, normalised measurements at one moment in time (SPEC.md §16).

    ``grid_power_w`` is already normalised to the internal convention:
    positive means import from the grid, negative means export.
    """

    timestamp: datetime = field(default_factory=dt_util.utcnow)
    grid_power_w: float | None = None
    solar_power_w: float | None = None
    household_consumption_w: float | None = None
    battery_power_w: float | None = None
    # Always the all-in price: the calculator normalises on reading (SPEC.md
    # §16), so nothing downstream has to know what the source reported.
    current_price_eur_kwh: float | None = None
    # What the source actually reported, kept **only** when it was a bare market
    # price. The panel shows it under the all-in figure so the conversion can be
    # checked against the sensor without opening the developer tools; there is
    # nothing to show when the source was already all-in, because then the two
    # numbers are the same one.
    market_price_eur_kwh: float | None = None
    # The live feed-in tariff, normalised by the feed-in formula on reading —
    # market price minus the supplier's cut, never the import formula. None when
    # no feed_in_price source is linked, and then the fixed
    # `feed_in_price_eur_kwh` from the home profile applies instead.
    feed_in_price_eur_kwh: float | None = None
    # The bare reading behind it, on the same terms as market_price_eur_kwh.
    market_feed_in_price_eur_kwh: float | None = None
    # Every source the engine could not use, including the rows of a source
    # type that occurs more than once. Feeds the data quality score.
    invalid_source_ids: list[str] = field(default_factory=list)
    # Only the sources whose *entity* could not be read, with enough detail to
    # report each one. A duplicate source type is a configuration problem and
    # is reported through its own route, so it is deliberately not in here.
    source_failures: list[SourceFailure] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the snapshot as a JSON-serialisable mapping."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "grid_power_w": self.grid_power_w,
            "solar_power_w": self.solar_power_w,
            "household_consumption_w": self.household_consumption_w,
            "battery_power_w": self.battery_power_w,
            "current_price_eur_kwh": self.current_price_eur_kwh,
            "market_price_eur_kwh": self.market_price_eur_kwh,
            "feed_in_price_eur_kwh": self.feed_in_price_eur_kwh,
            "market_feed_in_price_eur_kwh": self.market_feed_in_price_eur_kwh,
            "invalid_source_ids": list(self.invalid_source_ids),
            "source_failures": [failure.to_dict() for failure in self.source_failures],
            "reason_codes": list(self.reason_codes),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a snapshot from a mapping, filling in defaults."""
        data = _as_mapping(data)
        return cls(
            timestamp=_as_datetime(data.get("timestamp")) or dt_util.utcnow(),
            grid_power_w=_as_optional_float(data.get("grid_power_w")),
            solar_power_w=_as_optional_float(data.get("solar_power_w")),
            household_consumption_w=_as_optional_float(
                data.get("household_consumption_w")
            ),
            battery_power_w=_as_optional_float(data.get("battery_power_w")),
            current_price_eur_kwh=_as_optional_float(data.get("current_price_eur_kwh")),
            market_price_eur_kwh=_as_optional_float(data.get("market_price_eur_kwh")),
            feed_in_price_eur_kwh=_as_optional_float(data.get("feed_in_price_eur_kwh")),
            market_feed_in_price_eur_kwh=_as_optional_float(
                data.get("market_feed_in_price_eur_kwh")
            ),
            invalid_source_ids=_as_str_list(data.get("invalid_source_ids")),
            source_failures=[
                SourceFailure.from_dict(item)
                for item in _as_sequence(data.get("source_failures"))
            ],
            reason_codes=_as_str_list(data.get("reason_codes")),
        )


@dataclass(slots=True)
class DataQualityResult:
    """The weighted data completeness checklist (SPEC.md §16)."""

    score: int = 0
    completed_items: list[str] = field(default_factory=list)
    missing_items: list[str] = field(default_factory=list)
    # Items this home cannot be judged on, because it does not own the thing
    # they are about — no solar row, no appliances. They are neither earned nor
    # missing, and the panel needs the distinction to say "3 van de 4" instead
    # of holding a customer to a checklist item they can never satisfy.
    not_applicable_items: list[str] = field(default_factory=list)
    invalid_items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the result as a JSON-serialisable mapping."""
        return {
            "score": self.score,
            "completed_items": list(self.completed_items),
            "missing_items": list(self.missing_items),
            "not_applicable_items": list(self.not_applicable_items),
            "invalid_items": list(self.invalid_items),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a result from a mapping, filling in defaults."""
        data = _as_mapping(data)
        return cls(
            score=_as_int(data.get("score"), 0, minimum=0, maximum=100),
            completed_items=_as_str_list(data.get("completed_items")),
            missing_items=_as_str_list(data.get("missing_items")),
            not_applicable_items=_as_str_list(data.get("not_applicable_items")),
            invalid_items=_as_str_list(data.get("invalid_items")),
        )


@dataclass(slots=True)
class EnergyMetrics:
    """Everything the calculator derived from a snapshot (SPEC.md §16)."""

    timestamp: datetime = field(default_factory=dt_util.utcnow)
    grid_power_w: float | None = None
    # Carried through from the snapshot rather than derived: the Overzicht tab
    # shows solar production next to the surplus (SPEC.md §8), and the panel
    # reads the metrics, never the snapshot.
    solar_power_w: float | None = None
    solar_surplus_w: float | None = None
    solar_surplus_confidence: str = CONFIDENCE_LOW
    grid_load_percent: float | None = None
    peak_risk: bool = False
    # Whether the surplus counts as enough to advise on, after the coordinator's
    # latch has had its say (engine/hysteresis.py). ``None`` means nobody has
    # decided yet, and the advisor falls back to the plain comparison against
    # ``min_solar_surplus_w`` — which is what the calculator on its own produces,
    # so it stays a pure function of its input.
    solar_surplus_sufficient: bool | None = None
    current_price_eur_kwh: float | None = None
    # Carried through from the snapshot so the Overzicht can show where the
    # all-in price came from (SPEC.md §8). Only set for a market source.
    market_price_eur_kwh: float | None = None
    # The live feed-in tariff, when a feed_in_price source is linked. The
    # advisor prefers it over the fixed amount on the home profile; the panel
    # shows it beside the import price.
    feed_in_price_eur_kwh: float | None = None
    market_feed_in_price_eur_kwh: float | None = None
    data_quality: DataQualityResult = field(default_factory=DataQualityResult)
    energy_score: int | None = None
    # The individual weighted components, so the coach can explain the score.
    # Only the ones that apply to this home are present.
    score_components: dict[str, float] = field(default_factory=dict)
    # The component keys left out, and therefore out of the divisor too. Named
    # rather than silently absent: a score built from three components instead
    # of five looks like it skipped something unless it says which two.
    not_applicable_components: list[str] = field(default_factory=list)
    reason_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the metrics as a JSON-serialisable mapping."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "grid_power_w": self.grid_power_w,
            "solar_power_w": self.solar_power_w,
            "solar_surplus_w": self.solar_surplus_w,
            "solar_surplus_confidence": self.solar_surplus_confidence,
            "grid_load_percent": self.grid_load_percent,
            "peak_risk": self.peak_risk,
            "solar_surplus_sufficient": self.solar_surplus_sufficient,
            "current_price_eur_kwh": self.current_price_eur_kwh,
            "market_price_eur_kwh": self.market_price_eur_kwh,
            "feed_in_price_eur_kwh": self.feed_in_price_eur_kwh,
            "market_feed_in_price_eur_kwh": self.market_feed_in_price_eur_kwh,
            "data_quality": self.data_quality.to_dict(),
            "energy_score": self.energy_score,
            "score_components": dict(self.score_components),
            "not_applicable_components": list(self.not_applicable_components),
            "reason_codes": list(self.reason_codes),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build metrics from a mapping, filling in defaults."""
        data = _as_mapping(data)
        return cls(
            timestamp=_as_datetime(data.get("timestamp")) or dt_util.utcnow(),
            grid_power_w=_as_optional_float(data.get("grid_power_w")),
            solar_power_w=_as_optional_float(data.get("solar_power_w")),
            solar_surplus_w=_as_optional_float(data.get("solar_surplus_w")),
            solar_surplus_confidence=_as_choice(
                data.get("solar_surplus_confidence"), CONFIDENCE_LEVELS, CONFIDENCE_LOW
            ),
            grid_load_percent=_as_optional_float(data.get("grid_load_percent")),
            peak_risk=_as_bool(data.get("peak_risk"), False),
            solar_surplus_sufficient=(
                value
                if isinstance(value := data.get("solar_surplus_sufficient"), bool)
                else None
            ),
            current_price_eur_kwh=_as_optional_float(data.get("current_price_eur_kwh")),
            market_price_eur_kwh=_as_optional_float(data.get("market_price_eur_kwh")),
            feed_in_price_eur_kwh=_as_optional_float(data.get("feed_in_price_eur_kwh")),
            market_feed_in_price_eur_kwh=_as_optional_float(
                data.get("market_feed_in_price_eur_kwh")
            ),
            data_quality=DataQualityResult.from_dict(
                _as_mapping(data.get("data_quality"))
            ),
            energy_score=_as_optional_int(
                data.get("energy_score"), minimum=0, maximum=100
            ),
            score_components=_as_number_mapping(data.get("score_components")),
            not_applicable_components=_as_str_list(
                data.get("not_applicable_components")
            ),
            reason_codes=_as_str_list(data.get("reason_codes")),
        )


def _as_number_mapping(value: Any) -> dict[str, float]:
    """Return a mapping of names to finite floats, dropping unusable entries."""
    mapping = _as_mapping(value)
    return {
        key: number
        for key, raw in mapping.items()
        if isinstance(key, str) and (number := as_finite_float(raw)) is not None
    }


def _as_measurements(value: Any) -> dict[str, float | str]:
    """Return advice measurements: finite numbers and short strings only."""
    mapping = _as_mapping(value)
    measurements: dict[str, float | str] = {}
    for key, raw in mapping.items():
        if not isinstance(key, str):
            continue
        number = as_finite_float(raw)
        if number is not None:
            measurements[key] = number
        elif (text := _as_optional_str(raw)) is not None:
            measurements[key] = text
    return measurements


@dataclass(slots=True)
class AdviceItem:
    """A single piece of advice (SPEC.md §12)."""

    id: str
    title: str
    message: str
    severity: str
    reason_code: str
    confidence: str
    recommended_time: str | None = None
    estimated_savings_eur: float | None = None
    related_device_ids: list[str] = field(default_factory=list)
    measurements: dict[str, float | str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return the advice as a JSON-serialisable mapping."""
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "reason_code": self.reason_code,
            "confidence": self.confidence,
            "recommended_time": self.recommended_time,
            "estimated_savings_eur": self.estimated_savings_eur,
            "related_device_ids": list(self.related_device_ids),
            "measurements": dict(self.measurements),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build advice from a mapping, filling in defaults."""
        data = _as_mapping(data)
        return cls(
            id=_as_str(data.get("id"), _new_id()),
            title=_as_str(data.get("title"), ""),
            message=_as_str(data.get("message"), ""),
            severity=_as_choice(data.get("severity"), SEVERITIES, SEVERITY_INFO),
            reason_code=_as_str(data.get("reason_code"), ""),
            confidence=_as_choice(
                data.get("confidence"), CONFIDENCE_LEVELS, CONFIDENCE_LOW
            ),
            recommended_time=_as_optional_str(data.get("recommended_time")),
            estimated_savings_eur=_as_optional_float(data.get("estimated_savings_eur")),
            related_device_ids=_as_str_list(data.get("related_device_ids")),
            measurements=_as_measurements(data.get("measurements")),
        )


@dataclass(slots=True)
class CoachResult:
    """The complete coach output shown in the panel (SPEC.md §8 and §17).

    ``explanations`` is filled by the backend and keyed by the fixed question
    keys from ``const.EXPLANATION_KEYS``. The frontend only renders these
    strings and never draws its own conclusions.
    """

    generated_at: datetime = field(default_factory=dt_util.utcnow)
    primary_advice: AdviceItem | None = None
    advice: list[AdviceItem] = field(default_factory=list)
    metrics: EnergyMetrics = field(default_factory=EnergyMetrics)
    explanations: dict[str, str] = field(default_factory=dict)
    missing_data: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the coach result as a JSON-serialisable mapping."""
        return {
            "generated_at": self.generated_at.isoformat(),
            "primary_advice": (
                self.primary_advice.to_dict() if self.primary_advice else None
            ),
            "advice": [item.to_dict() for item in self.advice],
            "metrics": self.metrics.to_dict(),
            "explanations": dict(self.explanations),
            "missing_data": list(self.missing_data),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a coach result from a mapping, filling in defaults."""
        data = _as_mapping(data)
        primary = data.get("primary_advice")
        return cls(
            generated_at=_as_datetime(data.get("generated_at")) or dt_util.utcnow(),
            primary_advice=(
                AdviceItem.from_dict(primary) if isinstance(primary, Mapping) else None
            ),
            advice=[
                AdviceItem.from_dict(item) for item in _as_sequence(data.get("advice"))
            ],
            metrics=EnergyMetrics.from_dict(_as_mapping(data.get("metrics"))),
            explanations={
                key: text
                for key, raw in _as_mapping(data.get("explanations")).items()
                if isinstance(key, str) and (text := _as_optional_str(raw)) is not None
            },
            missing_data=_as_str_list(data.get("missing_data")),
        )
