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
    COMPLETENESS_UNCONDITIONAL_ITEMS,
    COMPONENT_MAX,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONTRACT_TYPE_DYNAMIC,
    HOME_CONSUMPTION_BATTERY_UNREADABLE,
    HOME_CONSUMPTION_NO_GRID_READING,
    HOME_CONSUMPTION_SOLAR_UNREADABLE,
    METER_MODE_SEPARATE,
    METER_MODE_SINGLE_SIGNED,
    PERCENT_MAX,
    POSITIVE_MEANS_EXPORT,
    POSITIVE_MEANS_IMPORT,
    PRICE_BASES,
    PRICE_BASIS_MARKET,
    SCORE_COMPONENT_PRICE,
    SCORE_COMPONENT_SOLAR,
    SCORE_COMPONENT_WEIGHTS,
    SCORE_UNAVAILABLE_CHEAP_PRICE,
    SCORE_UNAVAILABLE_INCOMPLETE_SETUP,
    SCORE_UNAVAILABLE_NO_SUN_CHEAP_PRICE,
    SCORE_UNAVAILABLE_NO_SUN_FIXED_TARIFF,
    SCORE_UNAVAILABLE_NO_VARIABLE_SIGNAL,
    SCORE_UNAVAILABLE_NOTHING_MOVABLE,
    SCORE_UNAVAILABLE_PRICE_THRESHOLDS_MISSING,
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

from .completeness import (
    evaluate_completeness,
    has_movable_load,
)
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

        consumption, consumption_reason = _home_consumption(config, snapshot)

        data_quality = evaluate_completeness(config, snapshot)
        components = _score_components(config, snapshot)
        score = _energy_score(components, data_quality)

        return EnergyMetrics(
            timestamp=snapshot.timestamp,
            grid_power_w=snapshot.grid_power_w,
            solar_power_w=snapshot.solar_power_w,
            home_consumption_w=consumption,
            home_consumption_unavailable_reason=consumption_reason,
            solar_surplus_w=surplus,
            solar_surplus_confidence=confidence,
            grid_load_percent=load_percent,
            peak_risk=_peak_risk(config, load_percent),
            current_price_eur_kwh=snapshot.current_price_eur_kwh,
            market_price_eur_kwh=snapshot.market_price_eur_kwh,
            feed_in_price_eur_kwh=snapshot.feed_in_price_eur_kwh,
            market_feed_in_price_eur_kwh=snapshot.market_feed_in_price_eur_kwh,
            data_quality=data_quality,
            energy_score=score,
            score_components=components,
            not_applicable_components=not_applicable_components(components),
            score_unavailable_reason=(
                None
                if score is not None
                else _score_unavailable_reason(config, snapshot, data_quality)
            ),
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
    config: StoredConfiguration, snapshot: EnergySnapshot
) -> dict[str, float]:
    """Return the weighted components that apply to this home, right now.

    Two components, both about the same question: did movable consumption fall
    on the right moment (SPEC.md §35.8). Three others were removed in 0.4.0 for
    failing one of the two rules in §35.1, and the rules are worth repeating
    here because this is where a fourth component would be added:

    1. **The drop-out rule.** A component is left out when the home cannot
       influence it *in this situation* — not when the signal happens to be
       zero. A component that is absent leaves both the sum and the divisor, so
       100 stays reachable; there is no number on a 0-100 axis that means "does
       not apply", and every attempt to find one has cost a real home real
       points. A fixed contract scored 50 here, meant as neutral, which was a
       permanent 7.5-point deduction for choosing a fixed contract.
    2. **The advice rule.** Following the coach's advice may never lower the
       score. `peak_component` did exactly that — a 3.7 kW charge the coach had
       just recommended took a 1x25 A home from 100 to 57 on that axis — and no
       amount of re-anchoring its slope closes that, because the conflict is
       between what the axis measures and what the advice asks for.

    A missing input does **not** score zero any more. That used to be the rule
    ("the signal exists and was not configured"), and it was another way of
    deducting points for the installer's paperwork from the resident's number.
    An unreadable price makes the price component inapplicable; the omission is
    reported by the data quality checklist and by the gate, where it belongs.

    Each component is rounded to two decimals. The linear interpolations
    otherwise leave binary floating point noise (74.99999999999999 for a clean
    75), which would show up in the panel and make the score jitter between two
    whole numbers on identical input.
    """
    candidates = (
        (SCORE_COMPONENT_SOLAR, _solar_component(config, snapshot)),
        (SCORE_COMPONENT_PRICE, _price_component(config, snapshot)),
    )
    return {key: round(value, 2) for key, value in candidates if value is not None}


def not_applicable_components(components: dict[str, float]) -> list[str]:
    """Return the component keys this home is not being judged on.

    Public because the panel and the coach both name them, for the reason the
    checklist names its own: a score built from one component instead of two
    looks like it skipped something unless it says which one and why.
    """
    return [key for key in SCORE_COMPONENT_WEIGHTS if key not in components]


def _production_now(snapshot: EnergySnapshot) -> float | None:
    """Return what the panels are producing, or None when that is nothing.

    **The single definition of "the sun is doing something right now."** It was
    inline in `_solar_component` until 0.4.2, when the tile's reason selector
    turned out to be answering the same question from the configuration
    instead — it checked whether a solar *row* existed, and told a customer at
    nine in the evening that there was production he was failing to use.

    That is the drop-out rule from SPEC.md §35.1 read backwards: a row is what
    the home owns, this is what it is doing. Two callers, one function, so the
    sentence and the component cannot disagree about which of the two they mean.
    """
    production = snapshot.solar_power_w
    if production is None or production <= SOLAR_COMPONENT_MIN_PRODUCTION_W:
        return None
    return production


def _has_row(config: StoredConfiguration, source_type: str) -> bool:
    """Return whether the installer said this home has such a source.

    A disabled row still counts. The hardware is there; somebody switched the
    reading off, which means we cannot see it — the same reading the solar
    checklist item uses (SPEC.md §16).
    """
    return any(source.type == source_type for source in config.sources)


def _balance_term(
    config: StoredConfiguration, source_type: str, value: float | None
) -> float | None:
    """Return a term of the energy balance, or None when it is unknowable.

    Three outcomes, and the middle one is the whole point (SPEC.md §36.3):

    - **no row** — the home does not have the thing, so the term is a true 0.
    - **a row we cannot read** — we do not know the term, and treating it as 0
      would be the invisible guess this project keeps banning.
    - **a readable row** — the value.
    """
    if value is not None:
        return value
    return None if _has_row(config, source_type) else 0.0


def _home_consumption(
    config: StoredConfiguration, snapshot: EnergySnapshot
) -> tuple[float | None, str | None]:
    """Return what the house itself is using, and why it is unknown if it is.

    ::

        thuisverbruik = netvermogen + zonneproductie - batterijvermogen

    with the conventions of SPEC.md §16: grid positive means import, battery
    positive means charging. A charging battery is consumption the household
    is not doing, so it comes off; a discharging battery feeds the house and
    adds through its negative value.

    **A measured source wins.** With a usable `general_consumption` row that
    reading *is* the answer: a measurement beats the difference of two other
    measurements, and linking it was the installer saying so.

    **The result is clamped at zero.** Negative household consumption does not
    exist. Two sensors that do not sample on the same second produce -40 W now
    and then, and putting that on screen raises a question with no answer. This
    is a physical floor, not an assumption.

    **A battery we cannot read withholds the figure**, where the solar surplus
    keeps it with a caveat. That difference is deliberate and argued in
    SPEC.md §36.3: there a charging battery shifts the number, here it is
    attributed to the household in full.
    """
    measured = snapshot.household_consumption_w
    if measured is not None:
        return without_negative_zero(max(measured, 0.0)), None

    if snapshot.grid_power_w is None:
        return None, HOME_CONSUMPTION_NO_GRID_READING

    solar = _balance_term(config, SOURCE_TYPE_SOLAR, snapshot.solar_power_w)
    if solar is None:
        return None, HOME_CONSUMPTION_SOLAR_UNREADABLE

    battery = _balance_term(config, SOURCE_TYPE_HOME_BATTERY, snapshot.battery_power_w)
    if battery is None:
        return None, HOME_CONSUMPTION_BATTERY_UNREADABLE

    consumption = snapshot.grid_power_w + solar - battery
    return without_negative_zero(max(consumption, 0.0)), None


def _price_thresholds_usable(config: StoredConfiguration) -> bool:
    """Return whether the low and high price thresholds can be compared."""
    low = config.home.low_price_threshold_eur_kwh
    high = config.home.high_price_threshold_eur_kwh
    return low is not None and high is not None and high > low


def _solar_component(
    config: StoredConfiguration, snapshot: EnergySnapshot
) -> float | None:
    """Return what share of this moment's production the home uses itself.

    ::

        zelfverbruik = (opwek - teruglevering) / opwek

    Returns ``None`` — not applicable — in three cases, each a different way of
    having nothing to measure:

    - **no production.** At night nothing is being wasted. A nightly zero was
      twenty points off a home that had done nothing wrong.
    - **no readable grid power.** Without it the export is unknown, so the
      share cannot be computed. Not zero: see the module note on missing
      inputs.
    - **nothing movable** (`has_movable_load`). A home with panels, no battery
      and no complete flexible appliance cannot raise its self-consumption at
      all, so the axis would be a discount rather than a meter (SPEC.md §35.4a).
      Adding a battery switches it on, which is the honest description of what
      a battery does: the ceiling and the bar rise together.

    **An earlier definition measured the opposite of its own name.** It scored
    the *surplus* — power flowing out — so it awarded 100 to a home exporting
    everything and 0 to a home consuming all of its own production, while being
    labelled "zonnebenutting" and sitting next to a coach advising the resident
    to use that surplus themselves.

    This moves with behaviour, which is what keeps it a measurement rather than
    a discount, and it moves the right way: a resident who runs the dishwasher
    while the sun is out raises it. That is precisely what the coach advises,
    so the advice rule holds.
    """
    production = _production_now(snapshot)
    if production is None:
        return None
    if snapshot.grid_power_w is None or not has_movable_load(config):
        return None

    exported = max(-snapshot.grid_power_w, 0.0)
    self_used = (production - exported) / production
    return min(max(self_used, 0.0), 1.0) * COMPONENT_MAX


def _price_component(
    config: StoredConfiguration, snapshot: EnergySnapshot
) -> float | None:
    """Return how little of the connection is being drawn while it is expensive.

    ::

        prijspositie = clamp((prijs - laag) / (hoog - laag), 0, 1)
        importdeel   = clamp(max(netvermogen, 0) / max_grid_power_w, 0, 1)
        component    = 100 * (1 - prijspositie * importdeel)

    **The previous definition measured the weather.** It scored the price alone,
    so every dynamic home scored 0 at 18:00 and 100 at 03:00 whatever it did,
    and two identical houses — one asleep, one running the tumble dryer —
    scored the same. Now the sleeping house scores high and the one with the
    dryer on scores low, and exporting during an expensive hour counts as full
    utilisation, because it is.

    Returns ``None`` — not applicable — when there is nothing to avoid:

    - **a fixed contract.** No price to react to, ever.
    - **a price at or below the low threshold.** `prijspositie` is then zero and
      the component would be 100 without anybody being able to move it, which
      is the drop-out rule. At the threshold itself it is exactly 100, so
      stepping in and out is continuous — no jump in the component.
    - **a missing price, threshold, maximum or grid reading.** Not zero; see
      the module note on missing inputs.

    **The axis is deliberately asymmetric.** Avoiding expensive consumption is
    behaviour; seeking out cheap consumption is only behaviour if you had
    something to run. Penalising a house that sleeps at 03:00 for not using
    cheap power would make the score demand that a tumble dryer be switched on.
    """
    if config.home.contract_type != CONTRACT_TYPE_DYNAMIC:
        return None

    if not _price_thresholds_usable(config):
        return None

    price = snapshot.current_price_eur_kwh
    low = config.home.low_price_threshold_eur_kwh
    high = config.home.high_price_threshold_eur_kwh
    maximum = config.home.max_grid_power_w
    grid_power = snapshot.grid_power_w
    if price is None or low is None or high is None:
        return None
    if maximum is None or maximum <= 0 or grid_power is None:
        return None
    if price <= low:
        return None

    price_position = min((price - low) / (high - low), 1.0)
    import_share = min(max(grid_power, 0.0) / maximum, 1.0)
    return (1.0 - price_position * import_share) * COMPONENT_MAX


def _energy_score(
    components: dict[str, float], data_quality: DataQualityResult
) -> int | None:
    """Return the weighted score over the components that apply, or None.

    The share of the applicable weight that was earned, so a home is measured
    against what it can influence and 100 stays reachable.

    ``None`` in two cases, and the panel says which (SPEC.md §35.9):

    - **the gate is shut.** The three unconditional checklist items — the home
      profile, a usable grid source, a price — are what the integration is for,
      and without them it measures nothing. This is what keeps the guarantee
      that a fresh install cannot score 100: it scores nothing at all. It
      replaces `data_quality_component`, whose 0.30 weight made the resident's
      number mostly a report on the installer's paperwork.
    - **nothing applies.** No sun to use, no expensive hour to avoid. A tile
      saying "nothing to measure right now" is more honest than a number that
      claims something untrue, and that number has already claimed something
      untrue twice (Sven, 2026-08-07).

    The gate is the item list rather than a percentage on purpose: a threshold
    would have been an invented number, and these three items are already the
    project's own definition of an installation that means something.
    """
    if any(
        item in data_quality.missing_items for item in COMPLETENESS_UNCONDITIONAL_ITEMS
    ):
        return None

    total = sum(SCORE_COMPONENT_WEIGHTS[key] for key in components)
    if not total:
        return None

    weighted = sum(
        SCORE_COMPONENT_WEIGHTS[key] * value for key, value in components.items()
    )
    return round(weighted / total)


def _score_unavailable_reason(
    config: StoredConfiguration,
    snapshot: EnergySnapshot,
    data_quality: DataQualityResult,
) -> str:
    """Return why there is no score, so the panel can explain rather than dash.

    A tile with a dash reads as a fault. Most of these are not faults: they
    describe a home doing nothing wrong with nothing to optimise at this
    moment (SPEC.md §35.9).

    **The snapshot is an argument because two of these sentences are about the
    present moment**, and until 0.4.2 this function could not see it. It chose
    `nothing_movable` — "er is nu opwek, maar geen apparaat dat verbruik kan
    verplaatsen" — on whether a solar *row* existed, so an evening with the
    panels at 0 W got a sentence claiming production. Configuration answers
    "what does this home own"; only a reading answers "what is it doing".

    The order is precedence, from "somebody can fix this" to "there is nothing
    to fix". Each branch owns exactly one sentence, and each sentence may claim
    only what its branch has established:

    1. **the gate** — the installation is incomplete.
    2. **no variable signal** — a fixed tariff and no panels. Never a number,
       which is accepted; the coach keeps working.
    3. **nothing movable** — the sun *is* producing and there is nothing to
       shift it to. Deliberately not restricted to a fixed tariff any more: a
       dynamic home in the sun with nothing movable used to fall through to a
       sentence claiming its panels were idle.
    4. **thresholds missing** — a dynamic tariff whose price cannot be judged.
       A shortcoming, and the only one of the last four that is.
    5-7. **nothing right now**, split by what is actually true of this home:
       panels idle plus a cheap hour, panels idle on a fixed tariff, or a cheap
       hour without panels. One sentence each, so none of them mentions an
       expensive hour to a home that has no price signal.

    Cases 5 to 7 all imply the panels are idle: production plus something
    movable makes the solar component apply, which means a score, which means
    this function is never called.
    """
    if any(
        item in data_quality.missing_items for item in COMPLETENESS_UNCONDITIONAL_ITEMS
    ):
        return SCORE_UNAVAILABLE_INCOMPLETE_SETUP

    dynamic = config.home.contract_type == CONTRACT_TYPE_DYNAMIC
    panels = any(source.type == SOURCE_TYPE_SOLAR for source in config.sources)

    if not dynamic and not panels:
        return SCORE_UNAVAILABLE_NO_VARIABLE_SIGNAL
    if _production_now(snapshot) is not None and not has_movable_load(config):
        return SCORE_UNAVAILABLE_NOTHING_MOVABLE
    if dynamic and not _price_thresholds_usable(config):
        return SCORE_UNAVAILABLE_PRICE_THRESHOLDS_MISSING
    if panels:
        return (
            SCORE_UNAVAILABLE_NO_SUN_CHEAP_PRICE
            if dynamic
            else SCORE_UNAVAILABLE_NO_SUN_FIXED_TARIFF
        )
    return SCORE_UNAVAILABLE_CHEAP_PRICE
