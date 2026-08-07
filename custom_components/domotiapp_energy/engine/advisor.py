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
    DEVICE_TYPE_EV_CHARGER,
    MEASUREMENT_GRID_LOAD_PERCENT,
    MEASUREMENT_GRID_POWER_W,
    MEASUREMENT_MISSING_ITEMS,
    MEASUREMENT_PRICE,
    MEASUREMENT_SOLAR_SURPLUS_W,
    MINUTES_PER_HOUR,
    PRIORITIES,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SOURCE_TYPE_FEED_IN_PRICE,
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


def advice_rank(reason_code: str) -> int:
    """Return how urgent this reason is; lower sorts first (SPEC.md §16).

    Public because the coordinator's dwell timer needs it: a peak warning has to
    be allowed past a timer that is holding a solar advice in place.
    """
    return _ADVICE_RANKS.get(reason_code, ADVICE_RANK_GENERAL)


@dataclass(slots=True)
class _Context:
    """Everything the rules need, gathered once."""

    config: StoredConfiguration
    metrics: EnergyMetrics
    now_minutes: int
    # Monday = 0 ... Sunday = 6, matching const.ALL_DAYS_OF_WEEK and therefore
    # comparable to a device's stored day list without translation. Read from
    # the same `now` as `now_minutes`, so a rule can never straddle midnight by
    # asking the clock twice.
    weekday: int
    quiet_hours: bool
    # Whether net metering still applies today. Read once here so every rule
    # sees the same answer, and so the date is evaluated in the Home Assistant
    # timezone like every other time decision (SPEC.md §16).
    net_metering: bool


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
            weekday=now.weekday(),
            quiet_hours=_in_quiet_hours(config, now.hour, now.minute),
            net_metering=config.home.is_net_metering_active(now.date()),
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
        advice.sort(key=lambda item: advice_rank(item.reason_code))

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
            measurements={MEASUREMENT_MISSING_ITEMS: len(missing)},
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
        MEASUREMENT_GRID_LOAD_PERCENT: round(context.metrics.grid_load_percent, 1),
        MEASUREMENT_GRID_POWER_W: grid_power,
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
    """Suggest a flexible device when there is enough surplus to use it.

    "Enough" is normally decided by the coordinator's latch, so a surplus
    drifting around the threshold does not switch this advice — and the euro
    amount under it — on and off every few seconds. Without a decision the plain
    comparison stands, which is what the advisor produces on its own.
    """
    surplus = context.metrics.solar_surplus_w
    if surplus is None:
        return []
    sufficient = context.metrics.solar_surplus_sufficient
    if sufficient is None:
        sufficient = surplus >= context.config.home.min_solar_surplus_w
    if not sufficient:
        return []
    if not context.config.preferences.prefer_solar:
        return []

    device = _best_device_for_now(context, surplus)
    if device is None:
        return []

    savings = _solar_savings(context, device)

    return [
        AdviceItem(
            id=f"{REASON_SOLAR_SURPLUS_AVAILABLE}:{device.id}",
            title="Zonneoverschot beschikbaar",
            message=_surplus_message(context, device, savings),
            severity=SEVERITY_INFO,
            reason_code=REASON_SOLAR_SURPLUS_AVAILABLE,
            confidence=_surplus_confidence(context, device),
            estimated_savings_eur=savings,
            related_device_ids=[device.id],
            measurements={MEASUREMENT_SOLAR_SURPLUS_W: round(surplus, 1)},
        )
    ]


def _surplus_confidence(context: _Context, device: DeviceProfile) -> str:
    """Return how much to trust the surplus advice for this device.

    The measurement can be excellent and the advice still be a guess. A charger
    is the case: "energie per laadsessie" is a typical session the installer
    estimated, because nothing here knows how empty the car is — that arrives
    with the state of charge in a later release. Claiming high confidence for a
    euro amount resting on that estimate overstates what we know, so a charger
    is capped at medium however good the surplus reading is (SPEC.md §16).
    """
    measured = context.metrics.solar_surplus_confidence
    if device.device_type != DEVICE_TYPE_EV_CHARGER:
        return measured
    return CONFIDENCE_MEDIUM if measured == CONFIDENCE_HIGH else measured


def _surplus_message(
    context: _Context, device: DeviceProfile, savings: float | None
) -> str:
    """Phrase the surplus advice so it matches the amount underneath it.

    Four situations, and the sentence has to follow the arithmetic rather than
    assume it. "Dit is een gunstig moment" under a loss, or under a blank
    amount, is the panel contradicting its own figure.
    """
    opening = "Er is momenteel zonneoverschot beschikbaar."
    favourable = f"Dit is een gunstig moment om {device.name} te gebruiken."

    if savings is None:
        # Name the term that is actually missing. Four different gaps can stop
        # the sum, and an earlier version of this sentence blamed the feed-in
        # cost for all of them — it told an installer whose price source had
        # gone stale to go and fill in a field that was already filled in.
        return f"{opening} {favourable} {_why_no_amount(context, device)}"

    if savings < 0:
        # Feeding in pays better than self-consumption. Rare, but real once the
        # feed-in tariff exceeds the import price, and the customer is owed the
        # figure rather than a cheerful sentence over the top of it.
        return (
            f"{opening} Zelf verbruiken levert nu echter minder op dan "
            f"terugleveren: {device.name} nu gebruiken kost naar schatting "
            f"{_euro(-savings)} ten opzichte van het overschot terugleveren. "
            f"Wachten tot de terugleververgoeding lager ligt is voordeliger."
        )

    if savings == 0 and context.net_metering:
        # Saying "gunstig moment" while showing a saving of EUR 0,00 reads as a
        # contradiction. It is not: the advice is about using your own surplus,
        # and under net metering that simply earns nothing extra.
        return (
            f"{opening} {favourable} Zolang de salderingsregeling geldt levert "
            f"dit geen extra besparing op, maar het overschot zelf gebruiken "
            f"blijft de meest efficiënte keuze."
        )

    if savings == 0:
        return (
            f"{opening} {favourable} Het levert op dit moment niets extra op, "
            f"maar het kost ook niets."
        )

    return f"{opening} {favourable}"


def _has_feed_in_source(context: _Context) -> bool:
    """Return whether a feed-in price source row exists at all.

    The row is the statement, readable or not: a home that linked one is not
    told to go and fill in the fixed field it deliberately left empty.
    """
    return any(
        source.type == SOURCE_TYPE_FEED_IN_PRICE for source in context.config.sources
    )


def _feed_in_tariff(context: _Context) -> float | None:
    """Return what a fed-in kWh is worth right now, or None when unknown.

    The live rate from a ``feed_in_price`` source when one is linked and
    readable, otherwise the fixed amount from the home profile. The live one is
    already normalised by the feed-in formula — market price minus the
    supplier's cut — so both branches return the same kind of number.

    **This becomes the whole difference on 2027-01-01.** Until net metering
    ends, a fed-in kWh is worth the retail price and this value never gets
    consulted; after it, it is the only term separating self-consumption from
    feeding in (SPEC.md §16).
    """
    if context.metrics.feed_in_price_eur_kwh is not None:
        return context.metrics.feed_in_price_eur_kwh
    return context.config.home.feed_in_price_eur_kwh


def _euro(amount: float) -> str:
    """Return an amount as Dutch currency, with the comma these texts use."""
    return f"€ {amount:.2f}".replace(".", ",")


def _why_no_amount(context: _Context, device: DeviceProfile) -> str:
    """Say which missing term stopped the saving from being calculated.

    The order matches the checks in :func:`_solar_savings`, so the sentence
    names the term that actually stopped it rather than the last one that could
    have. Each answer says where to go and what to enter, because "niet te
    berekenen" on its own leaves the installer hunting.
    """
    home = context.config.home

    if device.energy_per_cycle_kwh is None:
        return (
            f"Hoeveel dit oplevert is niet te berekenen zonder de energie per "
            f"cyclus van {device.name} — vul die in bij Apparaten."
        )

    if (
        context.metrics.current_price_eur_kwh
        if home.contract_type == CONTRACT_TYPE_DYNAMIC
        else home.fixed_import_price_eur_kwh
    ) is None:
        if home.contract_type == CONTRACT_TYPE_DYNAMIC:
            return (
                "Hoeveel dit oplevert is niet te berekenen zolang er geen "
                "actuele prijs is. Controleer de prijsbron bij Energiebronnen."
            )
        return (
            "Hoeveel dit oplevert is niet te berekenen zonder het vaste "
            "leveringstarief — vul dat in bij Woning."
        )

    if not context.net_metering and _feed_in_tariff(context) is None:
        # Which of the two routes is missing decides where to send them: a home
        # with a feed-in source has nothing to fill in on the Woning tab, and
        # telling it to would be the same wrong-field mistake the price sentence
        # used to make.
        if _has_feed_in_source(context):
            return (
                "Hoeveel dit oplevert is niet te berekenen zolang de "
                "terugleverprijsbron geen bruikbare waarde geeft. Controleer "
                "die bij Energiebronnen."
            )
        return (
            "Hoeveel dit oplevert is niet te berekenen zonder de "
            "terugleververgoeding — vul die in bij Woning, of koppel een "
            "terugleverprijsbron."
        )

    return (
        "Hoeveel dit oplevert is niet te berekenen zolang de terugleverkosten "
        "niet zijn ingevuld — vul ze in bij Woning, of zet ze op 0 als deze "
        "aansluiting ze niet betaalt."
    )


def _advise_price(context: _Context) -> list[AdviceItem]:
    """Advise on price, but only when the contract actually has one.

    SPEC.md §16: with a fixed contract ``low_energy_price`` and
    ``high_energy_price`` are never generated.

    The price compared here is the all-in price the calculator normalised on
    reading, and both thresholds are all-in amounts as well, so the comparison
    never depends on what the customer's price sensor happens to report.
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
                measurements={MEASUREMENT_PRICE: price},
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
                measurements={MEASUREMENT_PRICE: price},
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


def _best_device_for_now(
    context: _Context, surplus: float | None = None
) -> DeviceProfile | None:
    """Return the device to suggest right now, or None when there is none.

    A device qualifies when it is usable, flexible, allowed on today's weekday,
    inside its own time window, not silenced by the quiet hours, and — when a
    surplus is given — small enough for that surplus to actually run it.

    ``surplus`` is optional so a caller with no surplus in hand (a price rule,
    say) still gets a sensible device. Passing it is what turns "the biggest
    appliance" from the wrong answer into the right one; see
    :func:`_fits_in_surplus`.
    """
    candidates = [
        device
        for device in context.config.devices
        if device.is_usable
        and device.is_flexible
        and _allowed_today(device, context)
        and _within_window(device, context.now_minutes)
        and not _silenced_by_quiet_hours(device, context)
        and _fits_in_surplus(device, surplus)
    ]
    if not candidates:
        return None

    # Highest priority first, then the largest consumer. With the surplus filter
    # in front of it that second key finally means what its comment always
    # claimed: among the appliances this surplus can carry, the biggest one uses
    # the most of it. Without the filter it picked the appliance that fitted
    # *worst*, which is how "benut je zonneoverschot" ended up on a 2000 W
    # dishwasher with 600 W of surplus.
    return max(
        candidates,
        key=lambda device: (
            _priority_rank(device),
            device.nominal_power_w or 0.0,
        ),
    )


def _allowed_today(device: DeviceProfile, context: _Context) -> bool:
    """Return whether this device may run on today's weekday.

    The day list was stored, shown in the form, and then never read by anything
    — a resident who unticked Sunday was still advised to run the dishwasher on
    Sunday. An ignored instruction is worse than an absent field: the panel
    asked, the resident answered, and the engine overruled them silently.

    An empty list cannot occur: `_as_days_of_week` normalises it to every day,
    because "no days at all" would mean an appliance that may never run, which
    is what disabling it is for.
    """
    return context.weekday in device.days_of_week


def _fits_in_surplus(device: DeviceProfile, surplus: float | None) -> bool:
    """Return whether the surplus can actually carry this device.

    Advising a 2000 W dishwasher on 600 W of surplus calls importing 1400 W from
    the grid "using your own surplus". The saving underneath it is calculated as
    though the whole cycle came from the roof, so the amount is wrong too.

    A device whose power is unknown is **not** disqualified. We cannot show that
    it does not fit, and refusing on a missing value would be a guess in the
    other direction (SPEC.md §12). It sorts last anyway, so it only ever wins
    when nothing else qualifies.
    """
    if surplus is None or device.nominal_power_w is None:
        return True
    return device.nominal_power_w <= surplus


def _priority_rank(device: DeviceProfile) -> int:
    """Return the device priority as a sortable number.

    PRIORITIES runs from low to critical, so its index is the rank.
    """
    if device.priority not in PRIORITIES:
        return 0
    return PRIORITIES.index(device.priority)


def _within_window(device: DeviceProfile, now_minutes: int) -> bool:
    """Return whether starting now still fits the device's ready window.

    **This asks about the start, derived from the deadline.** The old model
    tested only whether the current moment fell inside the window, which let a
    180-minute dishwasher begin at 05:55 against a 06:00 finish and run until
    08:55 — nearly three hours past the time the resident gave. The validator
    never caught it: it checked that the duration *fitted* the window, not that
    there was still enough of the window left (SPEC.md §32).

    A window whose end precedes its start crosses midnight (22:00 to 06:00), the
    same reading the quiet hours use.

    Without a duration there is no start to derive, and `ready_before` falls back
    to its old meaning of "may not run after" — the safe reading, and never a
    guessed duration.

    **Only a complete ready window restricts anything here.** A single bound is
    not expressible as a window on a 24-hour clock: "finished by 07:00" with no
    lower bound would have to mean "in time for the *next* 07:00", and which
    07:00 that is depends on the moment you ask. Working that out is what the
    urgency advice does, and it is deliberately not smuggled in here as a
    half-answer. A device with one bound is therefore unrestricted in this
    check, exactly as one with no bounds is.
    """
    if not device.has_time_window:
        # No window, or half a window: no restriction, and never "never".
        return True

    start = minutes_since_midnight(device.earliest_start)
    # Falls back to the ready time itself when there is no duration to subtract,
    # which is the documented degradation to "may not run after".
    finish = minutes_since_midnight(device.latest_start or device.ready_before)
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

    One formula covers both regimes (SPEC.md §16)::

        saving = energy x (import - effective_feed_in + feed_in_cost)

    Using a kWh yourself avoids importing it, forgoes whatever feeding it in
    would have been worth, and avoids the cost of feeding it in.

    Under net metering a fed-in kWh is worth the full retail price, so
    ``import - effective_feed_in`` cancels out and only the avoided feed-in cost
    remains — which is exactly right: until 2027 there is nothing extra to earn
    beyond the cost your supplier charges for feeding in. After that the feed-in
    tariff takes over and the difference becomes real.

    Returns ``0.0`` rather than ``None`` when the sum works out to nothing: that
    is a calculated answer, not an unknown one, and the advice stays visible
    because the reason to run the appliance now still holds.

    **A negative result is returned as it stands.** It used to be clamped to
    zero, which turned "self-consumption costs you money right now" into a
    cheerful EUR 0,00 — the one figure that hides exactly the situation worth
    knowing about. It happens once the feed-in tariff exceeds the import price,
    and it is a fact about the customer's contract, not an error to smooth over.

    **An empty feed-in cost means unknown, not zero.** The two are different
    statements and the form now says so: leave it empty and the saving cannot be
    calculated, enter 0 and the saving is genuinely zero. Reading an empty field
    as 0.0 was a guess presented as a number, and under net metering it was the
    whole answer — the avoided feed-in cost is the only term that survives the
    cancellation, so a blank field silently produced "EUR 0,00" for what was
    actually unknown.

    Every amount in the formula is all-in: the dynamic price because the
    calculator normalised it on reading, the fixed tariff and the feed-in
    amounts because the form asks for them that way (SPEC.md §16). Mixing a bare
    market price into this sum would overstate the saving by the energy tax.
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
    if import_price is None:
        return None

    if context.net_metering:
        # Fed in and taken back at the same price, so only the feed-in cost is
        # avoided. No feed-in tariff is needed to work this out.
        effective_feed_in = import_price
    else:
        # A linked feed-in source wins over the fixed amount: creating that row
        # is an explicit statement that this home's feed-in tariff varies, the
        # same reading the checklist gives a source row (SPEC.md §16). The fixed
        # field stays on file and the panel disables rather than clears it, so
        # removing the source restores it.
        effective_feed_in = _feed_in_tariff(context)
        if effective_feed_in is None:
            return None

    feed_in_cost = home.feed_in_cost_eur_kwh
    if feed_in_cost is None:
        return None

    saving = energy * (import_price - effective_feed_in + feed_in_cost)
    return round(saving, 2)


def _filter_by_savings(
    advice: list[AdviceItem], config: StoredConfiguration
) -> list[AdviceItem]:
    """Drop advice whose calculated saving is below the threshold.

    Two kinds of advice are never filtered. Advice without a calculable saving —
    safety, peak, missing data, neutral — because the threshold says nothing
    about it (SPEC.md §8). And advice whose saving works out to zero or less,
    because that is a different statement: the reason to run the appliance now
    still holds, there is simply nothing extra to earn. Under net metering that
    is the normal case, and filtering it would leave the panel almost silent
    for a year while its advice was perfectly sound.

    A negative saving reaches the customer for the same reason, and it is the
    one the threshold would have swallowed most quietly: "not worth mentioning"
    is the wrong verdict on "this is currently costing you money".

    So the threshold applies to exactly one situation: there is money in this,
    but not enough to bother the customer with.
    """
    minimum = config.preferences.min_savings_eur
    return [
        item
        for item in advice
        if item.estimated_savings_eur is None
        or item.estimated_savings_eur <= 0
        or item.estimated_savings_eur >= minimum
    ]
