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
    PRICE_COMPONENT_FIXED_CONTRACT,
    SCORE_COMPONENT_DATA_QUALITY,
    SCORE_COMPONENT_FLEXIBILITY,
    SCORE_COMPONENT_PEAK,
    SCORE_COMPONENT_PRICE,
    SCORE_COMPONENT_SOLAR,
    SCORE_WEIGHT_DATA_QUALITY,
    SCORE_WEIGHT_FLEXIBILITY,
    SCORE_WEIGHT_PEAK,
    SCORE_WEIGHT_PRICE,
    SCORE_WEIGHT_SOLAR,
    SOURCE_TYPE_CURRENT_PRICE,
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
    StoredConfiguration,
    without_negative_zero,
)
from custom_components.domotiapp_energy.validators import read_entity_value

from .completeness import evaluate_completeness
from .reason_codes import REASON_MISSING_REQUIRED_DATA

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _Readings:
    """What could be read, and what could not, while building a snapshot."""

    values: dict[str, float]
    invalid_source_ids: list[str]
    reason_codes: list[str]


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
            invalid_source_ids=readings.invalid_source_ids,
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
            solar_surplus_w=surplus,
            solar_surplus_confidence=confidence,
            grid_load_percent=load_percent,
            peak_risk=_peak_risk(config, load_percent),
            current_price_eur_kwh=snapshot.current_price_eur_kwh,
            data_quality=data_quality,
            energy_score=_energy_score(components),
            score_components=components,
            reason_codes=reason_codes,
        )

    # --- Reading ------------------------------------------------------------

    def _read_sources(self, config: StoredConfiguration) -> _Readings:
        """Read every usable source, grouped by what it measures."""
        readings = _Readings(values={}, invalid_source_ids=[], reason_codes=[])

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

            value = self._read_source(source, readings)
            if value is None:
                continue

            if source.type in ADDITIVE_SOURCE_TYPES:
                readings.values[source.type] = (
                    readings.values.get(source.type, 0.0) + value
                )
            else:
                readings.values[source.type] = value

        return readings

    def _read_source(self, source: EnergySource, readings: _Readings) -> float | None:
        """Read one source, recording why it failed when it does."""
        if source.type == SOURCE_TYPE_GRID_METER:
            value, reason = self._read_grid_meter(source)
        else:
            result = read_entity_value(self._hass, source.binding)
            value = result.value if result.ok else None
            reason = result.reason_code

        if value is not None:
            return value

        readings.invalid_source_ids.append(source.id)
        if reason is not None and reason not in readings.reason_codes:
            readings.reason_codes.append(reason)
        return None

    def _read_grid_meter(self, source: EnergySource) -> tuple[float | None, str | None]:
        """Read a grid meter and normalise it to positive = import.

        The meter mode is never derived from which entities happen to be
        filled in: without an explicit mode the meter is unusable (SPEC.md §8).
        """
        if source.meter_mode == METER_MODE_SINGLE_SIGNED:
            return self._read_signed_meter(source)
        if source.meter_mode == METER_MODE_SEPARATE:
            return self._read_separate_meter(source)
        return None, REASON_MISSING_REQUIRED_DATA

    def _read_signed_meter(
        self, source: EnergySource
    ) -> tuple[float | None, str | None]:
        """Read a meter that reports one signed value."""
        if source.positive_means not in (POSITIVE_MEANS_IMPORT, POSITIVE_MEANS_EXPORT):
            return None, REASON_MISSING_REQUIRED_DATA

        result = read_entity_value(self._hass, source.binding)
        if not result.ok or result.value is None:
            return None, result.reason_code

        if source.positive_means == POSITIVE_MEANS_EXPORT:
            # A meter reading exactly 0 would otherwise normalise to -0.0.
            return without_negative_zero(-result.value), None
        return result.value, None

    def _read_separate_meter(
        self, source: EnergySource
    ) -> tuple[float | None, str | None]:
        """Read a meter with separate import and export entities."""
        imported = read_entity_value(self._hass, source.import_binding)
        exported = read_entity_value(self._hass, source.export_binding)

        if not imported.ok or imported.value is None:
            return None, imported.reason_code
        if not exported.ok or exported.value is None:
            return None, exported.reason_code

        return imported.value - exported.value, None


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
    """Return the five weighted components behind the energy score.

    Each component is rounded to two decimals. The linear interpolations
    otherwise leave binary floating point noise (74.99999999999999 for a clean
    75), which would show up in the panel and make the score jitter between
    two whole numbers on identical input.
    """
    return {
        key: round(value, 2)
        for key, value in (
            (SCORE_COMPONENT_DATA_QUALITY, float(data_quality.score)),
            (SCORE_COMPONENT_PEAK, _peak_component(load_percent)),
            (SCORE_COMPONENT_SOLAR, _solar_component(config, snapshot)),
            (SCORE_COMPONENT_PRICE, _price_component(config, snapshot)),
            (SCORE_COMPONENT_FLEXIBILITY, _flexibility_component(config)),
        )
    }


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


def _solar_component(config: StoredConfiguration, snapshot: EnergySnapshot) -> float:
    """Return how well the current surplus meets the configured minimum."""
    surplus, _, _ = _solar_surplus(config, snapshot)
    if surplus is None:
        # SPEC.md §16 is explicit: unknown surplus scores zero here.
        return COMPONENT_MIN

    minimum = config.home.min_solar_surplus_w
    if minimum <= 0:
        return COMPONENT_MAX if surplus > 0 else COMPONENT_MIN
    return min(surplus / minimum, 1.0) * COMPONENT_MAX


def _price_component(config: StoredConfiguration, snapshot: EnergySnapshot) -> float:
    """Return 100 at or below the low price, 0 at or above the high price.

    A fixed contract has no price to react to, so the component is neutral: it
    is not applicable rather than unknown. A dynamic contract without a
    readable price or without thresholds *is* unknown, and scores zero
    (SPEC.md §16).
    """
    if config.home.contract_type != CONTRACT_TYPE_DYNAMIC:
        return PRICE_COMPONENT_FIXED_CONTRACT

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


def _flexibility_component(config: StoredConfiguration) -> float:
    """Return 100 when at least one usable flexible device exists."""
    has_flexible = any(
        device.is_usable and device.is_flexible for device in config.devices
    )
    return COMPONENT_MAX if has_flexible else COMPONENT_MIN


def _energy_score(components: dict[str, float]) -> int:
    """Return the weighted score from SPEC.md §16, rounded to a whole number."""
    weighted = (
        SCORE_WEIGHT_DATA_QUALITY * components[SCORE_COMPONENT_DATA_QUALITY]
        + SCORE_WEIGHT_PEAK * components[SCORE_COMPONENT_PEAK]
        + SCORE_WEIGHT_SOLAR * components[SCORE_COMPONENT_SOLAR]
        + SCORE_WEIGHT_PRICE * components[SCORE_COMPONENT_PRICE]
        + SCORE_WEIGHT_FLEXIBILITY * components[SCORE_COMPONENT_FLEXIBILITY]
    )
    return round(weighted)
