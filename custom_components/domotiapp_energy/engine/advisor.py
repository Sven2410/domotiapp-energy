"""Turning metrics into advice (SPEC.md §16 "Adviesregels").

The advisor decides *what* to say, never *how* to say it: every item it
produces carries a reason code, and the phrasing comes from the coach provider
in :mod:`.providers`. It reads no entities, calls no services and controls
nothing — in 0.1.0 the integration only ever advises (SPEC.md §2.2).

Ordering is fixed by SPEC.md §16: safety, peak load, hard time limits, solar,
price, general optimisation. There is always exactly one primary advice; when
no rule matches at all, that primary advice is
``neutral_energy_situation``.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.util import dt as dt_util

from custom_components.domotiapp_energy.const import (
    ADVICE_RANK_GENERAL,
    ADVICE_RANK_PEAK,
    ADVICE_RANK_PRICE,
    ADVICE_RANK_SAFETY,
    ADVICE_RANK_SOLAR,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONTRACT_TYPE_DYNAMIC,
    MINUTES_PER_HOUR,
    PRIORITIES,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)
from custom_components.domotiapp_energy.models import (
    AdviceItem,
    DeviceProfile,
    EnergyMetrics,
    StoredConfiguration,
    minutes_since_midnight,
)
from custom_components.domotiapp_energy.validators import is_within_window

from .reason_codes import (
    REASON_HIGH_ENERGY_PRICE,
    REASON_HIGH_GRID_EXPORT,
    REASON_HIGH_GRID_LOAD,
    REASON_LOW_ENERGY_PRICE,
    REASON_MISSING_REQUIRED_DATA,
    REASON_NEUTRAL_ENERGY_SITUATION,
    REASON_SOLAR_SURPLUS_AVAILABLE,
)

# Rank per reason code, following the sort order in SPEC.md §16. Anything not
# listed sorts as general optimisation.
#
# Both peak variants share the peak rank: they describe the same risk and can
# never occur together, because the grid power is either positive or negative.
# The export variant ranking above solar surplus matters, though — both advise
# using power now, and the more urgent reason has to be the primary one.
_ADVICE_RANKS: dict[str, int] = {
    REASON_MISSING_REQUIRED_DATA: ADVICE_RANK_SAFETY,
    REASON_HIGH_GRID_LOAD: ADVICE_RANK_PEAK,
    REASON_HIGH_GRID_EXPORT: ADVICE_RANK_PEAK,
    REASON_SOLAR_SURPLUS_AVAILABLE: ADVICE_RANK_SOLAR,
    REASON_LOW_ENERGY_PRICE: ADVICE_RANK_PRICE,
    REASON_HIGH_ENERGY_PRICE: ADVICE_RANK_PRICE,
}


@dataclass(slots=True)
class _Context:
    """Everything the rules need, gathered once."""

    config: StoredConfiguration
    metrics: EnergyMetrics
    now_minutes: int
    quiet_hours: bool


class Advisor:
    """Produces the advice list for one set of metrics."""

    def generate(
        self, config: StoredConfiguration, metrics: EnergyMetrics
    ) -> list[AdviceItem]:
        """Return the advice for this moment, most important first.

        The list is already filtered and truncated: advice below the savings
        threshold is dropped, and no more than ``max_advice_count`` items come
        back. The first item is the primary advice.
        """
        now = dt_util.now()
        context = _Context(
            config=config,
            metrics=metrics,
            now_minutes=now.hour * MINUTES_PER_HOUR + now.minute,
            quiet_hours=_in_quiet_hours(config, now.hour, now.minute),
        )

        advice = [
            item
            for rule in (
                _advise_missing_data,
                _advise_peak_risk,
                _advise_solar_surplus,
                _advise_price,
            )
            for item in rule(context)
        ]

        advice = _filter_by_savings(advice, config)
        advice.sort(
            key=lambda item: _ADVICE_RANKS.get(item.reason_code, ADVICE_RANK_GENERAL)
        )

        if not advice:
            return [_neutral_advice()]
        return advice[: config.preferences.max_advice_count]


# --- Rules ------------------------------------------------------------------


def _advise_missing_data(context: _Context) -> list[AdviceItem]:
    """Warn when essential data is missing, before anything else is claimed."""
    missing = context.metrics.data_quality.missing_items
    if not missing:
        return []

    return [
        AdviceItem(
            id=REASON_MISSING_REQUIRED_DATA,
            title="Aanvullende gegevens nodig",
            message=(
                "Vul de ontbrekende energiegegevens aan om een betrouwbaar "
                "advies te ontvangen."
            ),
            severity=SEVERITY_WARNING,
            reason_code=REASON_MISSING_REQUIRED_DATA,
            confidence=CONFIDENCE_HIGH,
            measurements={"ontbrekende_onderdelen": len(missing)},
        )
    ]


def _advise_peak_risk(context: _Context) -> list[AdviceItem]:
    """Warn when the grid load approaches the configured maximum.

    The risk is the same in both directions — the main fuse does not care which
    way the current flows — but the advice is not. A home exporting 10 kW is
    over its limit, and telling it to postpone its appliances would push it
    further over: it has to *use* more, not less (SPEC.md §16).
    """
    if not context.metrics.peak_risk or context.metrics.grid_load_percent is None:
        return []

    grid_power = context.metrics.grid_power_w or 0.0
    measurements: dict[str, float | str] = {
        "netbelasting_procent": round(context.metrics.grid_load_percent, 1),
        "netvermogen_w": grid_power,
    }

    if grid_power < 0:
        return [
            AdviceItem(
                id=REASON_HIGH_GRID_EXPORT,
                title="Teruglevering hoog",
                message=(
                    "De teruglevering ligt dicht bij de ingestelde maximale "
                    "woningbelasting. Schakel indien mogelijk juist extra "
                    "verbruikers in om het overschot zelf te benutten."
                ),
                severity=SEVERITY_WARNING,
                reason_code=REASON_HIGH_GRID_EXPORT,
                confidence=CONFIDENCE_HIGH,
                measurements=measurements,
            )
        ]

    return [
        AdviceItem(
            id=REASON_HIGH_GRID_LOAD,
            title="Netbelasting hoog",
            message=(
                "Het actuele netvermogen ligt dicht bij de ingestelde maximale "
                "woningbelasting. Stel extra grootverbruikers indien mogelijk uit."
            ),
            severity=SEVERITY_WARNING,
            reason_code=REASON_HIGH_GRID_LOAD,
            confidence=CONFIDENCE_HIGH,
            measurements=measurements,
        )
    ]


def _advise_solar_surplus(context: _Context) -> list[AdviceItem]:
    """Suggest a flexible device when there is enough surplus to use it."""
    surplus = context.metrics.solar_surplus_w
    if surplus is None or surplus < context.config.home.min_solar_surplus_w:
        return []
    if not context.config.preferences.prefer_solar:
        return []

    device = _best_device_for_now(context)
    if device is None:
        return []

    return [
        AdviceItem(
            id=f"{REASON_SOLAR_SURPLUS_AVAILABLE}:{device.id}",
            title="Zonneoverschot beschikbaar",
            message=(
                f"Er is momenteel zonneoverschot beschikbaar. Dit is een gunstig "
                f"moment om {device.name} te gebruiken."
            ),
            severity=SEVERITY_INFO,
            reason_code=REASON_SOLAR_SURPLUS_AVAILABLE,
            confidence=context.metrics.solar_surplus_confidence,
            estimated_savings_eur=_solar_savings(context, device),
            related_device_ids=[device.id],
            measurements={"zonneoverschot_w": round(surplus, 1)},
        )
    ]


def _advise_price(context: _Context) -> list[AdviceItem]:
    """Advise on price, but only when the contract actually has one.

    SPEC.md §16: with a fixed contract ``low_energy_price`` and
    ``high_energy_price`` are never generated.
    """
    home = context.config.home
    if home.contract_type != CONTRACT_TYPE_DYNAMIC:
        return []
    if not context.config.preferences.prefer_low_price:
        return []

    price = context.metrics.current_price_eur_kwh
    if price is None:
        return []

    if home.low_price_threshold_eur_kwh is not None and (
        price <= home.low_price_threshold_eur_kwh
    ):
        return [
            AdviceItem(
                id=REASON_LOW_ENERGY_PRICE,
                title="Lage energieprijs",
                message=(
                    "De actuele energieprijs is relatief laag. Flexibele "
                    "apparaten kunnen nu voordeliger worden gebruikt."
                ),
                severity=SEVERITY_INFO,
                reason_code=REASON_LOW_ENERGY_PRICE,
                confidence=CONFIDENCE_HIGH,
                measurements={"prijs_eur_kwh": price},
            )
        ]

    if home.high_price_threshold_eur_kwh is not None and (
        price >= home.high_price_threshold_eur_kwh
    ):
        return [
            AdviceItem(
                id=REASON_HIGH_ENERGY_PRICE,
                title="Hoge energieprijs",
                message=(
                    "De actuele energieprijs is relatief hoog. Stel flexibel "
                    "energiegebruik indien mogelijk uit."
                ),
                severity=SEVERITY_WARNING,
                reason_code=REASON_HIGH_ENERGY_PRICE,
                confidence=CONFIDENCE_HIGH,
                measurements={"prijs_eur_kwh": price},
            )
        ]

    return []


def _neutral_advice() -> AdviceItem:
    """Return the advice shown when no rule matched (SPEC.md §16)."""
    return AdviceItem(
        id=REASON_NEUTRAL_ENERGY_SITUATION,
        title="Geen actie nodig",
        message=("De actuele energiesituatie vraagt momenteel niet om een aanpassing."),
        severity=SEVERITY_INFO,
        reason_code=REASON_NEUTRAL_ENERGY_SITUATION,
        confidence=CONFIDENCE_MEDIUM,
    )


# --- Device selection -------------------------------------------------------


def _best_device_for_now(context: _Context) -> DeviceProfile | None:
    """Return the device to suggest right now, or None when there is none.

    A device qualifies when it is usable, flexible, inside its own time window
    and not silenced by the quiet hours.
    """
    candidates = [
        device
        for device in context.config.devices
        if device.is_usable
        and device.is_flexible
        and _within_window(device, context.now_minutes)
        and not _silenced_by_quiet_hours(device, context)
    ]
    if not candidates:
        return None

    # Highest priority first, then the largest consumer: moving that one saves
    # the most. Both keys are stable, so the same input picks the same device.
    return max(
        candidates,
        key=lambda device: (
            _priority_rank(device),
            device.nominal_power_w or 0.0,
        ),
    )


def _priority_rank(device: DeviceProfile) -> int:
    """Return the device priority as a sortable number.

    PRIORITIES runs from low to critical, so its index is the rank.
    """
    if device.priority not in PRIORITIES:
        return 0
    return PRIORITIES.index(device.priority)


def _within_window(device: DeviceProfile, now_minutes: int) -> bool:
    """Return whether now falls inside the device's allowed time window.

    A window whose end precedes its start crosses midnight (22:00 to 06:00),
    the same reading the quiet hours use.
    """
    if not device.has_time_window:
        # No window means no restriction, not "never".
        return True

    start = minutes_since_midnight(device.earliest_start)
    finish = minutes_since_midnight(device.latest_finish)
    if start is None or finish is None or start == finish:
        return False
    return is_within_window(now_minutes, start, finish)


def _silenced_by_quiet_hours(device: DeviceProfile, context: _Context) -> bool:
    """Return whether the quiet hours rule suppresses advice for this device."""
    if not device.is_noisy or not context.quiet_hours:
        return False
    return not context.config.preferences.allow_advice_during_quiet_hours


def _in_quiet_hours(config: StoredConfiguration, hour: int, minute: int) -> bool:
    """Return whether now falls inside the quiet hours.

    Supports a window across midnight, which is the normal case (22:00-07:00).
    """
    start = minutes_since_midnight(config.preferences.quiet_hours_start)
    end = minutes_since_midnight(config.preferences.quiet_hours_end)
    if start is None or end is None or start == end:
        return False

    return is_within_window(hour * MINUTES_PER_HOUR + minute, start, end)


# --- Savings and filtering --------------------------------------------------


def _solar_savings(context: _Context, device: DeviceProfile) -> float | None:
    """Return what using surplus instead of grid power saves, or None.

    Using a kWh of surplus yourself avoids importing it at the import price and
    forgoes the feed-in payment for it, so the saving is the difference. SPEC.md
    does not put a formula on this; without both prices nothing is claimed.
    """
    energy = device.energy_per_cycle_kwh
    if energy is None:
        return None

    home = context.config.home
    import_price = (
        context.metrics.current_price_eur_kwh
        if home.contract_type == CONTRACT_TYPE_DYNAMIC
        else home.fixed_import_price_eur_kwh
    )
    if import_price is None or home.feed_in_price_eur_kwh is None:
        return None

    saving = energy * (import_price - home.feed_in_price_eur_kwh)
    return round(saving, 2) if saving > 0 else None


def _filter_by_savings(
    advice: list[AdviceItem], config: StoredConfiguration
) -> list[AdviceItem]:
    """Drop advice whose calculated saving is below the threshold.

    Advice without a calculable saving is never filtered: safety, peak,
    missing data and neutral advice always survive (SPEC.md §8).
    """
    minimum = config.preferences.min_savings_eur
    return [
        item
        for item in advice
        if item.estimated_savings_eur is None or item.estimated_savings_eur >= minimum
    ]
