"""Turning configured entities into numbers (SPEC.md §16).

The calculator does two things and nothing else: it reads the linked entities
into an :class:`EnergySnapshot`, and it derives an :class:`EnergyMetrics` from
that snapshot. It never phrases anything, never decides what to advise and
never touches Home Assistant beyond reading states.

Everything it cannot determine comes back as ``None`` with a reason code. A
missing measurement is never replaced by zero: "no grid reading" and "no power
flowing" are different situations and would lead to different advice.

Internal conventions, both mirroring each other:

* grid power — positive means import from the grid, negative means export;
* battery power — positive means charging (the home consumes), negative means
  discharging (SPEC.md §16 counts a charging battery as consumption).

A third normalisation happens here for the same reason: the price source is
converted to an **all-in** price on reading, so nothing downstream has to know
whether the customer's sensor reports a bare market price (SPEC.md §16).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.domotiapp_energy.const import (
    ADDITIVE_SOURCE_TYPES,
    COMPONENT_MAX,
    COMPONENT_MIN,
    COMPONENT_UNKNOWN,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONTRACT_TYPE_DYNAMIC,
    METER_MODE_SEPARATE,
    METER_MODE_SINGLE_SIGNED,
    PEAK_COMPONENT_FULL_BELOW_PERCENT,
    PERCENT_MAX,
    POSITIVE_MEANS_EXPORT,
    POSITIVE_MEANS_IMPORT,
    PRICE_BASES,
    PRICE_BASIS_MARKET,
    SCORE_COMPONENT_DATA_QUALITY,
    SCORE_COMPONENT_FLEXIBILITY,
    SCORE_COMPONENT_PEAK,
    SCORE_COMPONENT_PRICE,
    SCORE_COMPONENT_SOLAR,
    SCORE_COMPONENT_WEIGHTS,
    SOLAR_COMPONENT_MIN_PRODUCTION_W,
    SOURCE_TYPE_CURRENT_PRICE,
    SOURCE_TYPE_FEED_IN_PRICE,
    SOURCE_TYPE_GENERAL_CONSUMPTION,
    SOURCE_TYPE_GRID_METER,
    SOURCE_TYPE_HOME_BATTERY,
    SOURCE_TYPE_SOLAR,
)
from custom_components.domotiapp_energy.models import (
    DataQualityResult,
    EnergyMetrics,
    EnergySnapshot,
    EnergySource,
    HomeProfile,
    SourceFailure,
    StoredConfiguration,
    without_negative_zero,
)
from custom_components.domotiapp_energy.validators import ReadResult, read_entity_value

from .completeness import evaluate_completeness, is_complete_device_profile
from .reason_codes import REASON_MISSING_REQUIRED_DATA

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _Readings:
    """What could be read, and what could not, while building a snapshot."""

    values: dict[str, float]
    invalid_source_ids: list[str]
    failures: list[SourceFailure]
    reason_codes: list[str]
    # The bare reading behind a normalised market price, when there was one.
    market_price: float | None = None
    # The same for the feed-in source, which has its own conversion.
    market_feed_in_price: float | None = None


class Calculator:
    """Reads the configured sources and derives the energy metrics.

    Home Assistant is injected rather than reached for, so the calculator can
    be exercised against a plain state machine in the tests.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Store the Home Assistant instance the sources are read from."""
        self._hass = hass

    def build_snapshot(self, config: StoredConfiguration) -> EnergySnapshot:
        """Read every usable source into one normalised snapshot."""
        readings = self._read_sources(config)

        return EnergySnapshot(
            timestamp=dt_util.utcnow(),
            grid_power_w=readings.values.get(SOURCE_TYPE_GRID_METER),
            solar_power_w=readings.values.get(SOURCE_TYPE_SOLAR),
            household_consumption_w=readings.values.get(
                SOURCE_TYPE_GENERAL_CONSUMPTION
            ),
            battery_power_w=readings.values.get(SOURCE_TYPE_HOME_BATTERY),
            current_price_eur_kwh=readings.values.get(SOURCE_TYPE_CURRENT_PRICE),
            market_price_eur_kwh=readings.market_price,
            feed_in_price_eur_kwh=readings.values.get(SOURCE_TYPE_FEED_IN_PRICE),
            market_feed_in_price_eur_kwh=readings.market_feed_in_price,
            invalid_source_ids=readings.invalid_source_ids,
            source_failures=readings.failures,
            reason_codes=readings.reason_codes,
        )

    def calculate(self, config: StoredConfiguration) -> EnergyMetrics:
        """Read the sources and derive everything the advisor needs."""
        return self.derive_metrics(config, self.build_snapshot(config))

    def derive_metrics(
        self, config: StoredConfiguration, snapshot: EnergySnapshot
    ) -> EnergyMetrics:
        """Derive the metrics from an existing snapshot.

        Separate from :meth:`calculate` so the derivation can be tested against
        a snapshot that was built by hand, without a state machine.
        """
        reason_codes = list(snapshot.reason_codes)

        surplus, confidence, surplus_reason = _solar_surplus(config, snapshot)
        if surplus_reason is not None and surplus_reason not in reason_codes:
            reason_codes.append(surplus_reason)

        load_percent, load_reason = _grid_load_percent(config, snapshot)
        if load_reason is not None and load_reason not in reason_codes:
            reason_codes.append(load_reason)

        data_quality = evaluate_completeness(config, snapshot)
        components = _score_components(config, snapshot, data_quality, load_percent)

        return EnergyMetrics(
            timestamp=snapshot.timestamp,
            grid_power_w=snapshot.grid_power_w,
            solar_power_w=snapshot.solar_power_w,
            solar_surplus_w=surplus,
            solar_surplus_confidence=confidence,
            grid_load_percent=load_percent,
            peak_risk=_peak_risk(config, load_percent),
            current_price_eur_kwh=snapshot.current_price_eur_kwh,
            market_price_eur_kwh=snapshot.market_price_eur_kwh,
            feed_in_price_eur_kwh=snapshot.feed_in_price_eur_kwh,
            market_feed_in_price_eur_kwh=snapshot.market_feed_in_price_eur_kwh,
            data_quality=data_quality,
            energy_score=_energy_score(components),
            score_components=components,
            not_applicable_components=not_applicable_components(components),
            reason_codes=reason_codes,
        )

    # --- Reading ------------------------------------------------------------

    def _read_sources(self, config: StoredConfiguration) -> _Readings:
        """Read every usable source, grouped by what it measures."""
        readings = _Readings(
            values={}, invalid_source_ids=[], failures=[], reason_codes=[]
        )

        duplicated = config.duplicate_exclusive_sources
        for source_type, rows in duplicated.items():
            # Two grid meters or two price sources do not add up, and picking
            # one of them would be a guess (SPEC.md §2.1). Neither is used and
            # both are reported, so the panel can mark them and the data
            # quality counts them as invalid items.
            readings.invalid_source_ids.extend(row.id for row in rows)
            if REASON_MISSING_REQUIRED_DATA not in readings.reason_codes:
                readings.reason_codes.append(REASON_MISSING_REQUIRED_DATA)
            _LOGGER.warning(
                "Multiple enabled sources of type %r; none of them is used",
                source_type,
            )

        for source in config.sources:
            if not source.is_usable or source.type in duplicated:
                continue

            value = self._read_source(source, config.home, readings)
            if value is None:
                continue

            if source.type in ADDITIVE_SOURCE_TYPES:
                readings.values[source.type] = (
                    readings.values.get(source.type, 0.0) + value
                )
            else:
                readings.values[source.type] = value

        return readings

    def _read_source(
        self, source: EnergySource, home: HomeProfile, readings: _Readings
    ) -> float | None:
        """Read one source, recording why it failed when it does.

        A read that fails against an actual entity is recorded as a
        :class:`SourceFailure` as well, so the coordinator can tell the
        installer which source went quiet and why. A source that is simply not
        finished — no entity linked, no meter mode chosen, no price basis
        stated — produces no such record: nothing broke, it was never
        configured, and the data quality checklist already reports that.
        """
        if source.type == SOURCE_TYPE_GRID_METER:
            value, result = self._read_grid_meter(source)
        elif source.type == SOURCE_TYPE_CURRENT_PRICE:
            value, result = self._read_price(source, home, readings)
        elif source.type == SOURCE_TYPE_FEED_IN_PRICE:
            value, result = self._read_feed_in_price(source, home, readings)
        else:
            result = read_entity_value(self._hass, source.binding)
            value = result.value if result.ok else None

        if value is not None:
            return value

        readings.invalid_source_ids.append(source.id)
        reason = (
            result.reason_code if result is not None else REASON_MISSING_REQUIRED_DATA
        )
        if reason is not None and reason not in readings.reason_codes:
            readings.reason_codes.append(reason)

        if result is not None and not result.ok and result.entity_id:
            readings.failures.append(
                SourceFailure(
                    source_id=source.id,
                    entity_id=result.entity_id,
                    reason_code=result.reason_code or "",
                    unavailable=result.unavailable,
                )
            )
        return None

    def _read_price(
        self, source: EnergySource, home: HomeProfile, readings: _Readings
    ) -> tuple[float | None, ReadResult | None]:
        """Read the price source and normalise it to an all-in price.

        This is the one place where the conversion happens, and it happens on
        reading (SPEC.md §16). From here on a single kind of price exists: the
        thresholds, the savings formula, the energy score and every sentence the
        coach produces all compare the same number. Letting the source's own
        basis travel any further would put the question "which price is this?"
        into every comparison and every text instead.

        A basis that was never chosen, or a market price without the components
        that complete it, yields ``None`` for both values: the reading is simply
        not usable, and like a grid meter without a mode that is a gap in the
        configuration rather than an entity that failed.
        """
        if source.price_basis not in PRICE_BASES:
            return None, None

        result = read_entity_value(self._hass, source.binding)
        if not result.ok or result.value is None:
            return None, result

        normalised = home.all_in_price_eur_kwh(result.value, source.price_basis)
        if normalised is None:
            return None, None

        if source.price_basis == PRICE_BASIS_MARKET:
            # Kept so the panel can show the conversion next to its result: an
            # all-in figure with no way to check it against the sensor is a
            # number the installer has to take on faith (SPEC.md §8).
            readings.market_price = result.value
        return normalised, result

    def _read_feed_in_price(
        self, source: EnergySource, home: HomeProfile, readings: _Readings
    ) -> tuple[float | None, ReadResult | None]:
        """Read the feed-in source and normalise it to the rate received.

        The same shape as :meth:`_read_price` and deliberately **not** the same
        formula: a fed-in kWh earns the market price minus the supplier's cut,
        with no energy tax and no VAT on top. Running it through the import
        conversion would overstate the tariff roughly threefold, which is the
        whole reason this is its own source type (SPEC.md §16).

        A basis that was never chosen, or a market price without the markup that
        completes it, yields ``None``: the reading is not usable, and that is a
        gap in the configuration rather than an entity that failed.
        """
        if source.price_basis not in PRICE_BASES:
            return None, None

        result = read_entity_value(self._hass, source.binding)
        if not result.ok or result.value is None:
            return None, result

        normalised = home.net_feed_in_price_eur_kwh(result.value, source.price_basis)
        if normalised is None:
            return None, None

        if source.price_basis == PRICE_BASIS_MARKET:
            readings.market_feed_in_price = result.value
        return normalised, result

    def _read_grid_meter(
        self, source: EnergySource
    ) -> tuple[float | None, ReadResult | None]:
        """Read a grid meter and normalise it to positive = import.

        The meter mode is never derived from which entities happen to be
        filled in: without an explicit mode the meter is unusable (SPEC.md §8).
        A ``None`` result means no entity was consulted at all, so there is
        nothing to report as unavailable.
        """
        if source.meter_mode == METER_MODE_SINGLE_SIGNED:
            return self._read_signed_meter(source)
        if source.meter_mode == METER_MODE_SEPARATE:
            return self._read_separate_meter(source)
        return None, None

    def _read_signed_meter(
        self, source: EnergySource
    ) -> tuple[float | None, ReadResult | None]:
        """Read a meter that reports one signed value."""
        if source.positive_means not in (POSITIVE_MEANS_IMPORT, POSITIVE_MEANS_EXPORT):
            return None, None

        result = read_entity_value(self._hass, source.binding)
        if not result.ok or result.value is None:
            return None, result

        if source.positive_means == POSITIVE_MEANS_EXPORT:
            # A meter reading exactly 0 would otherwise normalise to -0.0.
            return without_negative_zero(-result.value), result
        return result.value, result

    def _read_separate_meter(
        self, source: EnergySource
    ) -> tuple[float | None, ReadResult | None]:
        """Read a meter with separate import and export entities."""
        imported = read_entity_value(self._hass, source.import_binding)
        exported = read_entity_value(self._hass, source.export_binding)

        if not imported.ok or imported.value is None:
            return None, imported
        if not exported.ok or exported.value is None:
            return None, exported

        return imported.value - exported.value, imported


# --- Derivation -------------------------------------------------------------


def _solar_surplus(
    config: StoredConfiguration, snapshot: EnergySnapshot
) -> tuple[float | None, str, str | None]:
    """Return the solar surplus, its confidence and any reason code.

    The order from SPEC.md §16 is explicit and the first variant that works
    wins; nothing is estimated when neither does.
    """
    if snapshot.grid_power_w is not None:
        # Export is surplus by definition, whatever the household is doing.
        # max() returns its first argument when the two are equal, so a grid
        # power of exactly 0 would hand back -0.0 without the guard.
        surplus = without_negative_zero(max(-snapshot.grid_power_w, 0.0))
        return surplus, CONFIDENCE_HIGH, None

    if snapshot.solar_power_w is None or snapshot.household_consumption_w is None:
        return None, CONFIDENCE_LOW, REASON_MISSING_REQUIRED_DATA

    surplus = snapshot.solar_power_w - snapshot.household_consumption_w
    if snapshot.battery_power_w is not None and snapshot.battery_power_w > 0:
        # A charging battery is consumption that the household meter does not
        # see, so it eats into the surplus (SPEC.md §16).
        surplus -= snapshot.battery_power_w

    confidence = CONFIDENCE_MEDIUM
    if _battery_configured_but_unreadable(config, snapshot):
        # A battery that may be charging without us knowing how much makes this
        # variant a good deal less trustworthy (SPEC.md §16).
        confidence = CONFIDENCE_LOW

    return without_negative_zero(max(surplus, 0.0)), confidence, None


def _battery_configured_but_unreadable(
    config: StoredConfiguration, snapshot: EnergySnapshot
) -> bool:
    """Return whether a battery source exists whose power could not be read."""
    if snapshot.battery_power_w is not None:
        return False
    return any(
        source.is_usable and source.type == SOURCE_TYPE_HOME_BATTERY
        for source in config.sources
    )


def _grid_load_percent(
    config: StoredConfiguration, snapshot: EnergySnapshot
) -> tuple[float | None, str | None]:
    """Return the load as a percentage of the configured maximum.

    ``abs()`` is deliberate: the main fuse limits both directions, so heavy
    export counts towards peak risk too (SPEC.md §16).
    """
    maximum = config.home.max_grid_power_w
    if maximum is None or maximum == 0:
        return None, REASON_MISSING_REQUIRED_DATA
    if snapshot.grid_power_w is None:
        return None, REASON_MISSING_REQUIRED_DATA

    return abs(snapshot.grid_power_w) / maximum * PERCENT_MAX, None


def _peak_risk(config: StoredConfiguration, load_percent: float | None) -> bool:
    """Return whether the load is at or above the configured warning level."""
    if load_percent is None:
        # Unknown is not a risk: claiming one without a measurement would be a
        # guess, and the missing data is reported separately.
        return False
    return load_percent >= config.home.peak_warning_percent


def _score_components(
    config: StoredConfiguration,
    snapshot: EnergySnapshot,
    data_quality: DataQualityResult,
    load_percent: float | None,
) -> dict[str, float]:
    """Return the weighted components that apply to this home, right now.

    A component that cannot apply is **absent** rather than zero or half, and
    the score divides by the weight of what is left — the same rule the data
    quality checklist follows (SPEC.md §16). Scoring a fixed contract 50 on
    price cost that home 7.5 points forever while the constant's own comment
    claimed the score was "not dragged down by it"; scoring a home without
    appliances 0 on flexibility cost it 10 more. Neither is a measurement: both
    are deductions the resident cannot answer, and a component nobody can move
    is a discount, not a meter.

    Each component is rounded to two decimals. The linear interpolations
    otherwise leave binary floating point noise (74.99999999999999 for a clean
    75), which would show up in the panel and make the score jitter between
    two whole numbers on identical input.
    """
    candidates = (
        (SCORE_COMPONENT_DATA_QUALITY, float(data_quality.score)),
        (SCORE_COMPONENT_PEAK, _peak_component(load_percent)),
        (SCORE_COMPONENT_SOLAR, _solar_component(config, snapshot)),
        (SCORE_COMPONENT_PRICE, _price_component(config, snapshot)),
        (SCORE_COMPONENT_FLEXIBILITY, _flexibility_component(config)),
    )
    return {key: round(value, 2) for key, value in candidates if value is not None}


def not_applicable_components(components: dict[str, float]) -> list[str]:
    """Return the component keys this home is not being judged on.

    Public because the panel and the coach both name them, for the reason the
    checklist names its own: a score built from three components instead of five
    looks like it skipped something unless it says which two and why.
    """
    return [key for key in SCORE_COMPONENT_WEIGHTS if key not in components]


def _peak_component(load_percent: float | None) -> float:
    """Return 100 below half load, dropping linearly to 0 at full load.

    An unknown load scores zero: the grid load is always applicable, so not
    knowing it means it was not configured (SPEC.md §16).
    """
    if load_percent is None:
        return COMPONENT_UNKNOWN
    if load_percent <= PEAK_COMPONENT_FULL_BELOW_PERCENT:
        return COMPONENT_MAX
    if load_percent >= PERCENT_MAX:
        return COMPONENT_MIN

    remaining = PERCENT_MAX - load_percent
    span = PERCENT_MAX - PEAK_COMPONENT_FULL_BELOW_PERCENT
    return remaining / span * COMPONENT_MAX


def _solar_component(
    config: StoredConfiguration, snapshot: EnergySnapshot
) -> float | None:
    """Return what share of this moment's production the home uses itself.

    **The previous definition measured the opposite of its own name.** It scored
    the *surplus*, which is `max(-grid_power, 0)` — power flowing out to the
    grid. So it awarded 100 to a home exporting everything and 0 to a home
    consuming all of its own production, while being labelled "zonnebenutting"
    and sitting next to a coach advising the resident to use their surplus
    themselves. The score rewarded exactly what the advice discouraged
    (production finding, 2026-08-07).

    What it measures now::

        zelfverbruik = (opwek - teruglevering) / opwek

    Returns ``None`` — not applicable — when there is no production to speak of.
    At night nothing is being wasted, so there is nothing to score, and a nightly
    zero was twenty points off a home that had done nothing wrong.

    This still moves with behaviour, which is what keeps it a measurement rather
    than a discount: a resident who runs the dishwasher while the sun is out
    raises it, with or without a smart appliance. That is precisely the advice
    the coach gives.
    """
    production = snapshot.solar_power_w
    if production is None or production <= SOLAR_COMPONENT_MIN_PRODUCTION_W:
        return None

    exported = max(-snapshot.grid_power_w, 0.0) if snapshot.grid_power_w else 0.0
    self_used = (production - exported) / production
    return min(max(self_used, 0.0), 1.0) * COMPONENT_MAX


def _price_component(
    config: StoredConfiguration, snapshot: EnergySnapshot
) -> float | None:
    """Return 100 at or below the low price, 0 at or above the high price.

    A fixed contract has no price to react to, so the component does not apply
    and is left out of the score entirely. It used to score 50 — meant as
    neutral, but on a 0-100 axis where everything else can reach 100 that is a
    permanent 7.5-point deduction for choosing a fixed contract. "Neutral" does
    not exist on this axis; the only neutral answer is not to be weighed.

    A dynamic contract without a readable price or without thresholds *is*
    unknown, and unknown scores zero: the signal exists and was not configured
    (SPEC.md §16).
    """
    if config.home.contract_type != CONTRACT_TYPE_DYNAMIC:
        return None

    price = snapshot.current_price_eur_kwh
    low = config.home.low_price_threshold_eur_kwh
    high = config.home.high_price_threshold_eur_kwh
    if price is None or low is None or high is None or high <= low:
        return COMPONENT_UNKNOWN

    if price <= low:
        return COMPONENT_MAX
    if price >= high:
        return COMPONENT_MIN
    return (high - price) / (high - low) * COMPONENT_MAX


def _flexibility_component(config: StoredConfiguration) -> float | None:
    """Return 100 when one device could actually be advised, 0 when none can.

    Returns ``None`` — not applicable — when the home has **no usable appliances
    at all**. There is then nothing to be flexible with, and no configuring
    would change that: a permanent zero on a home that owns no smart appliances
    is a discount, not a measurement (SPEC.md §16).

    A home that *does* have appliances and none of them flexible or complete
    scores a real 0, because that is a gap the installer can close. The dividing
    line is the same one the data quality checklist draws between "not asked"
    and "missing".

    "Usable and flexible" is not enough to score 100: a row with nothing but a
    name and a type satisfied that, so adding an empty appliance raised the
    score by ten points. That is a meter rewarding what has been *created*
    rather than what the home can *do*.

    The line sits at the same place as the data quality checklist's idea of a
    complete device — a nominal power and an energy per cycle — because that is
    what makes advice about this appliance say something: without the energy per
    cycle there is no saving to name (SPEC.md §16). It is one shared predicate,
    so the score, the checklist and the form cannot disagree about it.
    """
    usable = [device for device in config.devices if device.is_usable]
    if not usable:
        return None

    has_flexible = any(
        device.is_flexible and is_complete_device_profile(device) for device in usable
    )
    return COMPONENT_MAX if has_flexible else COMPONENT_MIN


def _energy_score(components: dict[str, float]) -> int | None:
    """Return the weighted score over the components that apply.

    The share of the applicable weight that was earned, so a home is measured
    against what it can influence and 100 stays reachable. With all five
    components applicable the weights sum to 1.0 and this returns exactly what
    the flat sum used to — a fully configured home sees no change.

    ``None`` when nothing applies at all. Data quality and peak load are both
    unconditional, so in practice that needs a home with no configuration
    whatsoever; returning a number there would be scoring an empty page.
    """
    total = sum(SCORE_COMPONENT_WEIGHTS[key] for key in components)
    if not total:
        return None

    weighted = sum(
        SCORE_COMPONENT_WEIGHTS[key] * value for key, value in components.items()
    )
    return round(weighted / total)
