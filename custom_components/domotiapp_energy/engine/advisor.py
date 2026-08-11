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
    ADVICE_RANK_TIME_LIMIT,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONTRACT_TYPE_DYNAMIC,
    DEVICE_TYPE_EV_CHARGER,
    MEASUREMENT_GRID_LOAD_PERCENT,
    MEASUREMENT_GRID_POWER_W,
    MEASUREMENT_MINUTES_LEFT,
    MEASUREMENT_MISSING_ITEMS,
    MEASUREMENT_PRICE,
    MEASUREMENT_SOLAR_SURPLUS_W,
    MINUTES_PER_DAY,
    MINUTES_PER_HOUR,
    PRIORITIES,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SOURCE_TYPE_FEED_IN_PRICE,
    URGENCY_LEAD_MINUTES,
    WATTS_PER_KILOWATT,
)
from custom_components.domotiapp_energy.models import (
    AdviceItem,
    DeviceProfile,
    EnergyMetrics,
    StoredConfiguration,
    minutes_since_midnight,
)
from custom_components.domotiapp_energy.validators import is_within_window

from .completeness import is_advisable
from .reason_codes import (
    REASON_DEADLINE_APPROACHING,
    REASON_HIGH_ENERGY_PRICE,
    REASON_HIGH_GRID_EXPORT,
    REASON_HIGH_GRID_LOAD,
    REASON_LOW_ENERGY_PRICE,
    REASON_MISSING_REQUIRED_DATA,
    REASON_NEUTRAL_ENERGY_SITUATION,
    REASON_OUTSIDE_ALLOWED_WINDOW,
    REASON_QUIET_HOURS_ACTIVE,
    REASON_SOLAR_SURPLUS_AVAILABLE,
)
from .scheduling import latest_start_minutes

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
    REASON_DEADLINE_APPROACHING: ADVICE_RANK_TIME_LIMIT,
    REASON_SOLAR_SURPLUS_AVAILABLE: ADVICE_RANK_SOLAR,
    # The deferred form of the same advice, so the same rank. It replaces the
    # surplus item rather than joining it, and it says the same thing about the
    # same moment — only the recommended action differs.
    REASON_QUIET_HOURS_ACTIVE: ADVICE_RANK_SOLAR,
    # Same again for the no-run window: it is the surplus advice, explaining
    # itself instead of vanishing. Same moment, same subject, other action
    # (SPEC.md §51).
    REASON_OUTSIDE_ALLOWED_WINDOW: ADVICE_RANK_SOLAR,
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
                _advise_deadline,
                _advise_solar_surplus,
                _advise_price,
            )
            for item in rule(context)
        ]

        advice = _filter_by_savings(advice, config)
        advice = _drop_second_advice_per_device(advice)
        advice.sort(key=lambda item: advice_rank(item.reason_code))

        if not advice:
            return [_neutral_advice()]
        return advice[: config.preferences.max_advice_count]


def _drop_second_advice_per_device(advice: list[AdviceItem]) -> list[AdviceItem]:
    """Keep one advice per appliance: the most urgent reason it appears for.

    A dishwasher inside its urgency window while the sun is out produced two
    items about the same machine — *start hem nu voor 07:00* and *er is
    zonneoverschot, gebruik hem nu*. Both true, both asking for the same
    action, and one of them is noise.

    The same lesson as the doubled primary advice on the Overzicht (SPEC.md
    §42.1), one layer up: there the panel printed one item twice, here the
    engine produced two items about one subject. Rank decides which survives,
    so the deadline beats the sun and the sun beats the price.

    Advice without an appliance — safety, peak, price, neutral — is never
    touched: those are about the house, and two of them can be true at once.
    """
    # Keyed on identity rather than on the item: AdviceItem is a plain
    # dataclass, so it compares by value and is not hashable, and two items
    # that happen to carry the same fields are still two items.
    best: dict[str, AdviceItem] = {}
    for item in advice:
        for device_id in item.related_device_ids:
            current = best.get(device_id)
            if current is None or advice_rank(item.reason_code) < advice_rank(
                current.reason_code
            ):
                best[device_id] = item

    kept = {id(item) for item in best.values()}
    return [item for item in advice if not item.related_device_ids or id(item) in kept]


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
        # Two whole sentences, and which one is true depends on the margin
        # (SPEC.md §35.4d). The capacity argument holds either way — the fuse
        # does not care what a kWh is worth — but the second half of the
        # original sentence promised a benefit, and with feeding in paying
        # better than self-consumption that promise is simply false. The
        # resident is still told to switch something on, because the limit is
        # the limit; they are told what it costs rather than what it saves.
        margin = context.metrics.self_consumption_margin_eur_kwh
        message = (
            "De teruglevering ligt dicht bij de ingestelde maximale "
            "woningbelasting. Schakel indien mogelijk juist extra verbruikers "
            "in om het overschot zelf te benutten."
        )
        if margin is not None and margin < 0:
            message = (
                "De teruglevering ligt dicht bij de ingestelde maximale "
                "woningbelasting. Schakel indien mogelijk juist extra "
                "verbruikers in om de belasting te verlagen. Let op: "
                "terugleveren levert je op dit moment meer op dan zelf "
                "verbruiken, dus dit kost je geld."
            )
        return [
            AdviceItem(
                id=REASON_HIGH_GRID_EXPORT,
                title="Teruglevering hoog",
                message=message,
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

    **No advice at all on a surplus that may be overstated** (0.4.1). When a
    home battery is configured whose power cannot be read, the surplus shown
    could be entirely the battery charging — and this advice would tell the
    resident to switch on a dishwasher that then runs off the grid, with a euro
    amount underneath it that is simply wrong.

    Labelling that "betrouwbaarheid: laag" and sending it out anyway was the
    real defect, and it survived because the label looked like it had dealt
    with the problem. The panel says instead what is wrong and what to link;
    silence plus a reason beats a confident sentence built on a number we know
    can be false.
    """
    surplus = context.metrics.solar_surplus_w
    if surplus is None or not _surplus_worth_advising(context, surplus):
        return []

    # Quiet hours defer, they do not silence (SPEC.md §42.2). A quiet appliance
    # wins when there is one, and only when every candidate is noisy does the
    # advice change into "wait, and here is until when".
    device = _best_device_for_now(context, surplus)
    deferred = False
    if device is None:
        device = _best_device_for_now(context, surplus, include_silenced=True)
        deferred = device is not None
    if device is None:
        # Nothing qualifies even with the quiet hours lifted. Before falling
        # silent, find out whether a no-run window is what stands in the way —
        # silence with no reason is what sends an installer hunting (SPEC.md
        # §51). Asked last, so it never displaces an advice he could act on.
        blocked = _best_device_for_now(
            context, surplus, include_silenced=True, include_blocked=True
        )
        if blocked is not None and blocked.has_no_run_window:
            return [
                AdviceItem(
                    id=f"{REASON_OUTSIDE_ALLOWED_WINDOW}:{blocked.id}",
                    title="Zonneoverschot, maar dit apparaat mag nu niet draaien",
                    message=_no_run_message(blocked),
                    severity=SEVERITY_INFO,
                    reason_code=REASON_OUTSIDE_ALLOWED_WINDOW,
                    confidence=CONFIDENCE_HIGH,
                    related_device_ids=[blocked.id],
                    measurements={MEASUREMENT_SOLAR_SURPLUS_W: round(surplus, 1)},
                )
            ]
        return []

    if deferred:
        return [
            AdviceItem(
                id=f"{REASON_QUIET_HOURS_ACTIVE}:{device.id}",
                title="Zonneoverschot, maar het zijn stille uren",
                message=_quiet_hours_message(context, device),
                severity=SEVERITY_INFO,
                reason_code=REASON_QUIET_HOURS_ACTIVE,
                confidence=CONFIDENCE_HIGH,
                related_device_ids=[device.id],
                measurements={MEASUREMENT_SOLAR_SURPLUS_W: round(surplus, 1)},
            )
        ]

    savings = _solar_savings(context, device)
    rate = _solar_savings_rate(context, device, surplus)

    return [
        AdviceItem(
            id=f"{REASON_SOLAR_SURPLUS_AVAILABLE}:{device.id}",
            title="Zonneoverschot beschikbaar",
            message=_surplus_message(context, device, savings, rate, surplus),
            severity=SEVERITY_INFO,
            reason_code=REASON_SOLAR_SURPLUS_AVAILABLE,
            confidence=_surplus_confidence(context, device),
            estimated_savings_eur=savings,
            savings_rate_eur_per_hour=rate,
            related_device_ids=[device.id],
            measurements={MEASUREMENT_SOLAR_SURPLUS_W: round(surplus, 1)},
        )
    ]


def _surplus_worth_advising(context: _Context, surplus: float) -> bool:
    """Return whether there is a surplus this home wants to hear about.

    Split out of the rule so the rule itself stays a sequence of *decisions*
    rather than a sequence of guards. Every condition here is about the
    measurement; everything left in the rule is about which appliance and which
    sentence.
    """
    if context.metrics.solar_surplus_may_be_overstated:
        return False
    if not context.config.preferences.prefer_solar:
        return False
    sufficient = context.metrics.solar_surplus_sufficient
    if sufficient is None:
        sufficient = surplus >= context.config.home.min_solar_surplus_w
    return sufficient


def _quiet_hours_message(context: _Context, device: DeviceProfile) -> str:
    """Say that the surplus is real, that this appliance is noisy, and until when.

    **No estimated saving on this one.** The euro amount answers "what does
    running it now earn", and the advice is not to run it now; an amount beside
    a deferral reads as an argument to ignore the deferral.

    The last clause replaces a preference rather than a fact. Until 0.9.0 there
    was a toggle — *toch adviseren tijdens de stille uren* — which suppressed
    the whole advice when off. In the deferring form there is nothing left for
    it to switch, so it is gone (finding 12); the resident who disagrees with
    the window moves the window, and the sentence says where.
    """
    return (
        f"Er is momenteel zonneoverschot beschikbaar. {device.name} maakt "
        f"geluid en het zijn stille uren tot "
        f"{context.config.preferences.quiet_hours_end}. Wacht daarmee tot na "
        f"{context.config.preferences.quiet_hours_end}, of pas de stille uren "
        f"aan bij Mijn voorkeuren."
    )


def _no_run_message(device: DeviceProfile) -> str:
    """Say that the surplus is real, and that this appliance may not use it now.

    **The window is the installer's, not the resident's**, and the sentence has
    to make that visible or the resident goes looking in Mijn voorkeuren — where
    the quiet hours live — and finds nothing that explains it. So it names where
    the rule was set instead of inviting him to change it, which is the
    difference with :func:`_quiet_hours_message`.

    No estimated saving here either, for the same reason: an amount beside "not
    now" reads as an argument against the "not".

    Both bounds are known — `has_no_run_window` is checked before this is
    called — so the sentence never has a hole in it (SPEC.md §26).
    """
    return (
        f"Er is momenteel zonneoverschot beschikbaar, maar {device.name} mag "
        f"tussen {device.no_run_from} en {device.no_run_until} niet draaien. "
        f"Dat is bij de installatie zo ingesteld en staat los van je stille "
        f"uren. Na {device.no_run_until} kan het weer."
    )


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
    context: _Context,
    device: DeviceProfile,
    savings: float | None,
    rate: float | None,
    surplus: float | None,
) -> str:
    """Phrase the surplus advice so it matches the amount underneath it.

    Four situations, and the sentence has to follow the arithmetic rather than
    assume it. "Dit is een gunstig moment" under a loss, or under a blank
    amount, is the panel contradicting its own figure.

    **A modulating appliance has no total on purpose**, and that is a fifth
    situation rather than a missing term (SPEC.md §56.4). Left to the branch
    below it, an empty total was read as "the sum could not be made" and the
    sentence went looking for the term to blame — so a charger with a perfectly
    good rate underneath it told the installer to go and fill in a feed-in cost
    he had just entered. Found in the browser, which is the only place it could
    have been: every layer below agreed with itself.

    **But an empty rate under that appliance is a missing term again**, and
    until 0.21.0 nothing said so: the card simply showed neither amount row and
    the sentence was as cheerful as ever (SPEC.md §56.8). The two cases have to
    be told apart by the amount that appliance actually carries, which is why
    the rate is an argument here — asking `savings` would answer for the wrong
    figure, and it is empty for every modulating appliance by design.
    """
    opening = "Er is momenteel zonneoverschot beschikbaar."
    favourable = f"Dit is een gunstig moment om {device.name} te gebruiken."

    if device.modulates:
        return _modulating_surplus_message(context, device, rate, surplus)

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


def _modulating_surplus_message(
    context: _Context,
    device: DeviceProfile,
    rate: float | None,
    surplus: float | None,
) -> str:
    """Phrase the advice for an appliance that takes whatever is spare.

    Its own function because it reads its own figure. The total below is empty
    for every one of these appliances by design (SPEC.md §56.4), so the branches
    of :func:`_surplus_message` cannot say anything about this one — asking
    `savings` here would answer for a sum that was never attempted.

    Two situations rather than five: the rate is there, or a term is missing.

    **A negative rate is a third one, and it is not handled here** (SPEC.md
    §56.9). Once feeding in pays better than self-consumption the margin goes
    negative, and this sentence stays as cheerful as ever above a rate that is
    below zero — exactly the contradiction the per-cycle branch has its own
    sentence for. It cannot happen under net metering, where the margin is the
    avoided feed-in cost and never negative, so it is a 2027 problem and it
    needs its own wording rather than the per-cycle sentence with another unit.
    """
    opening = "Er is momenteel zonneoverschot beschikbaar."
    favourable = f"Dit is een gunstig moment om {device.name} te gebruiken."

    if rate is None:
        return f"{opening} {favourable} {_why_no_rate(context, device, surplus)}"
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
    """Say which missing term stopped the per-cycle saving from being made.

    The order matches the checks in :func:`_solar_savings`, so the sentence
    names the term that actually stopped it rather than the last one that could
    have. Each answer says where to go and what to enter, because "niet te
    berekenen" on its own leaves the installer hunting.

    **Its own half is the cycle; the rest belongs to the margin** (SPEC.md
    §56.8). This function used to hold both, and that is precisely why the
    modulating branch of :func:`_surplus_message` could not call it: a charger
    that takes whatever is spare does not use `energy_per_cycle_kwh`, so the
    first sentence here would send its installer to a field that has no bearing
    on his amount. Split, both branches can name the term that stopped their
    own sum — see :func:`_why_no_rate`.
    """
    if device.energy_per_cycle_kwh is None:
        # **Two whole sentences, not one with the field name slotted in**
        # (SPEC.md §26). A charger's form asks for *Energie per laadsessie*,
        # because a car has no cycle; every other appliance is asked for
        # *Energie per cyclus*. Composing that from a fragment would leave the
        # sentence the customer reads existing nowhere in the source.
        if device.device_type == DEVICE_TYPE_EV_CHARGER:
            return (
                f"Hoeveel dit oplevert is niet te berekenen zonder de energie "
                f"per laadsessie van {device.name} — vul die in bij Apparaten."
            )
        return (
            f"Hoeveel dit oplevert is niet te berekenen zonder de energie per "
            f"cyclus van {device.name} — vul die in bij Apparaten."
        )

    return _why_no_margin(context)


def _why_no_rate(
    context: _Context, device: DeviceProfile, surplus: float | None
) -> str:
    """Say which missing term stopped the hourly amount from being made.

    The counterpart of :func:`_why_no_amount` for an appliance that takes
    whatever is spare (SPEC.md §56.8). The order matches the checks in
    :func:`_solar_savings_rate`: its own term first, then the margin the two
    amounts share.

    The margin sentences are reused word for word, and that is the point of the
    split rather than a shortcut. A missing import price stops both sums for the
    same reason and is filled in at the same place, so the scale of the amount
    changes nothing about what the installer has to go and do.
    """
    if device.usable_power_w(surplus) is None:
        # The same two labels one branch up, and the same rule: whole sentences
        # (SPEC.md §26). A charger's form calls this *Maximaal laadvermogen*,
        # everything else *Nominaal vermogen* — and modulating is not restricted
        # to chargers, since the switch is offered on every advisable type, so
        # the type is asked rather than assumed.
        if device.device_type == DEVICE_TYPE_EV_CHARGER:
            return (
                f"Hoeveel dit per uur oplevert is niet te berekenen zonder het "
                f"maximale laadvermogen van {device.name} — vul dat in bij "
                f"Apparaten."
            )
        return (
            f"Hoeveel dit per uur oplevert is niet te berekenen zonder het "
            f"nominale vermogen van {device.name} — vul dat in bij Apparaten."
        )

    return _why_no_margin(context)


def _why_no_margin(context: _Context) -> str:
    """Say which missing term stopped the self-consumption margin.

    The half of the story that is about the home rather than the appliance:
    what a kWh costs, what feeding it in is worth, and what feeding it in
    costs. The order follows `self_consumption_margin` in the calculator, so
    the sentence names the term that actually stopped the composition.

    **No appliance is mentioned here on purpose.** Both amounts multiply this
    margin — the per-cycle total and the per-hour rate — so both are stopped by
    exactly the same gaps, at exactly the same fields. One answer, so the two
    can never come to disagree about where the installer should go (SPEC.md
    §56.8).
    """
    home = context.config.home

    # The metrics already carry the price that applies, whatever the contract
    # is (SPEC.md §48); this only has to notice that there is none.
    if context.metrics.current_price_eur_kwh is None:
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


def _advise_deadline(context: _Context) -> list[AdviceItem]:
    """Say when an appliance has to start now to be finished on time.

    **The one advice that needs no forecast.** You do not have to know the
    future to know that starting later than this makes the deadline
    unreachable, which is why SPEC.md §32.3 puts it at rank 3 — above solar and
    price. A deadline is hard; waiting for the sun is an optimisation.

    The window runs from ``latest_start - URGENCY_LEAD_MINUTES`` **to
    ``latest_start``**, and not on to the deadline itself. §32.3 says "loopt tot
    de deadline", and that is one moment too late: past the last start the
    sentence "start nu, dan is hij om 07:00 klaar" is simply false, and there is
    no other true sentence that helps. Silence there is the same choice §32.3
    makes after the deadline has passed, for the same reason, taken at the
    moment the deadline actually becomes unreachable rather than at the moment
    it formally expires.

    **The phrasing is conditional and the severity is info, both deliberately
    against the table in §32.3.** That table specifies "Start [naam] nu om
    [tijd] te halen" as a warning, and it is right — once phase 3 knows there is
    work to do. Phase 2 has no such signal: `needs_ready_flag` is the next
    phase, so this rule cannot tell a full dishwasher from an empty one. A
    nightly warning claiming urgency about an empty machine is the kind of
    message that teaches people to ignore warnings, so the sentence states the
    condition it actually knows — *if* you want it finished by then — and the
    severity waits for the flag that makes the claim true.
    """
    now = context.now_minutes
    lead = URGENCY_LEAD_MINUTES
    items: list[AdviceItem] = []

    for device in context.config.devices:
        if not is_advisable(device) or not _allowed_today(device, context):
            continue
        # A participating day is not automatically a day with a deadline
        # (SPEC.md §56.1). Without this the charger of woning 3 would be told on
        # a Saturday morning to start now for a 06:15 he does not have.
        if not device.deadline_applies_on(context.weekday):
            continue
        latest = latest_start_minutes(device, context.metrics)
        if latest is None:
            continue
        # The window may cross midnight — 03:00 for a 06:00 deadline is the
        # normal case — so it is compared the same way every other window in
        # this engine is (SPEC.md §16).
        if not is_within_window(now, (latest - lead) % MINUTES_PER_DAY, latest):
            continue

        items.append(
            AdviceItem(
                id=f"{REASON_DEADLINE_APPROACHING}:{device.id}",
                title="Bijna te laat om op tijd klaar te zijn",
                message=(
                    f"Start {device.name} nu als hij om {device.ready_before} "
                    f"klaar moet zijn."
                ),
                severity=SEVERITY_INFO,
                reason_code=REASON_DEADLINE_APPROACHING,
                confidence=CONFIDENCE_HIGH,
                related_device_ids=[device.id],
                measurements={
                    MEASUREMENT_MINUTES_LEFT: (latest - now) % MINUTES_PER_DAY
                },
            )
        )

    return items


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
    context: _Context,
    surplus: float | None = None,
    *,
    include_silenced: bool = False,
    include_blocked: bool = False,
) -> DeviceProfile | None:
    """Return the device to suggest right now, or None when there is none.

    A device qualifies when it is **advisable**, allowed on today's weekday,
    inside its own time window, not silenced by the quiet hours, and — when a
    surplus is given — small enough for that surplus to actually run it.

    ``include_blocked`` drops the no-run window, and exists for one purpose: to
    find out **whether that window is the reason** there is no advice. Asked
    only after asking without it, exactly like ``include_silenced``. Without
    this, a home with a banned dryer and nothing else simply produced silence,
    and the installer who set the ban had no way to tell that from a broken
    sensor (SPEC.md §51).

    ``include_silenced`` drops the quiet-hours condition, and the caller asks
    for it only after asking without it. That order is the whole point of the
    deferring form (SPEC.md §42.2): a resident with a quiet appliance available
    gets advice he can act on, and only a resident with nothing but a noisy one
    gets told to wait. Asking with the flag first would trade a usable advice
    for a deferral.

    **`is_advisable` replaced "usable and flexible" in 0.6.1**, and the third
    condition inside it is the fix: `control_mode = monitor_only` had no reader
    anywhere in the engine, so a dishwasher the resident had set to "alleen
    meekijken" was still advised on. That is his own off switch (SPEC.md §33),
    and the product ignored it.

    ``surplus`` is optional so a caller with no surplus in hand (a price rule,
    say) still gets a sensible device. Passing it is what turns "the biggest
    appliance" from the wrong answer into the right one; see
    :func:`_fits_in_surplus`.
    """
    candidates = [
        device
        for device in context.config.devices
        if is_advisable(device)
        and _allowed_today(device, context)
        and _within_window(device, context.now_minutes, context.weekday)
        and (include_blocked or device.may_run_at(context.now_minutes))
        and _fits_in_surplus(device, surplus)
        and (include_silenced or not _silenced_by_quiet_hours(device, context))
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
    if device.modulates and device.min_power_w is not None:
        # **A washing machine cannot accept a partial surplus; a charger can**
        # (SPEC.md §56.3). Judging a modulating appliance on its maximum is what
        # kept the charger of woning 3 silent on the ordinary Dutch afternoon —
        # car at home, panels producing less than the charging maximum, which is
        # exactly the moment the customer bought this for.
        return device.min_power_w <= surplus
    return device.nominal_power_w <= surplus


def _priority_rank(device: DeviceProfile) -> int:
    """Return the device priority as a sortable number.

    PRIORITIES runs from low to critical, so its index is the rank.
    """
    if device.priority not in PRIORITIES:
        return 0
    return PRIORITIES.index(device.priority)


def _within_window(device: DeviceProfile, now_minutes: int, weekday: int) -> bool:
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
    if not device.has_complete_ready_window:
        # No window, or half a window: no restriction, and never "never". The
        # *complete* predicate on purpose — this needs two edges to test
        # against, unlike the checklist, which only asks whether anything was
        # stated at all.
        return True

    if not device.deadline_applies_on(weekday):
        # Today is a participating day without a deadline (SPEC.md §56.1). The
        # appliance is unrestricted, exactly as one with no window is — which is
        # what makes "op zaterdag alleen als het gunstig is" expressible.
        return True

    start = minutes_since_midnight(device.earliest_start)
    # Falls back to the ready time itself when there is no duration to subtract,
    # which is the documented degradation to "may not run after".
    finish = minutes_since_midnight(device.latest_start or device.ready_before)
    if start is None or finish is None or start == finish:
        return False
    return is_within_window(now_minutes, start, finish)


def _silenced_by_quiet_hours(device: DeviceProfile, context: _Context) -> bool:
    """Return whether the quiet hours defer advice for this appliance.

    Named for what it does to the *candidate list*, not to the advice: a
    silenced appliance is passed over while another one is available, and only
    when none is does it come back with a deferring sentence (SPEC.md §42.2).

    There is no preference beside this any more. `allow_advice_during_quiet
    _hours` switched the whole advice off, and in the deferring form there is
    nothing left for it to switch (finding 12).
    """
    return device.is_noisy and context.quiet_hours


def _in_quiet_hours(config: StoredConfiguration, hour: int, minute: int) -> bool:
    """Return whether now falls inside the quiet hours.

    Supports a window across midnight, which is the normal case (22:00-07:00).

    **An unreadable time means no quiet hours, and that is a deliberate trade**
    (SPEC.md §53). Until then a typo was silently replaced by 22:00 and the
    window kept working, which sounds safer and is not: the resident saw hours
    he never entered and had no way to find out. Now the value is kept, the
    panel reports it against the field, and the window does not apply while it
    is wrong.

    The cost is real and worth naming: advice can appear during what the
    resident *meant* to be his quiet hours until he fixes the typo. It is
    bounded — this integration sends no notifications, so the advice sits in a
    panel and a sensor — and it comes with an error on screen that says exactly
    what to correct, which the silent substitution never did.
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

    **The bracket is no longer computed here.** It never depended on the
    appliance — only the scale did — and keeping it inside this function meant
    the one fact it establishes, that feeding in currently pays better, could
    only ever be stated about an appliance. A home with panels and no complete
    flexible appliance could not be told, which is exactly the home whose solar
    axis drops out for having nothing movable. It is now
    `EnergyMetrics.self_consumption_margin_eur_kwh`, read by the score, the tile
    and this sum alike (SPEC.md §35.4d).
    """
    if device.modulates:
        # **No total for an appliance whose advice has no end** (SPEC.md §56.4).
        # "Charge on what is spare" runs as long as the sun does, so there is no
        # cycle to price; `energy_per_cycle_kwh` would put a confident EUR 1,20
        # under advice about the next twenty minutes.
        #
        # Empty is the right answer and not a gap, and it has a second effect
        # that is equally deliberate: `_filter_by_savings` never drops advice
        # without a calculable saving, so a per-advice threshold cannot silently
        # remove a charger whose worth is a rate. The rate itself travels in
        # `savings_rate_eur_per_hour`; see :func:`_solar_savings_rate`.
        return None

    energy = device.energy_per_cycle_kwh
    if energy is None:
        return None

    margin = context.metrics.self_consumption_margin_eur_kwh
    if margin is None:
        return None

    return round(energy * margin, 2)


def _solar_savings_rate(
    context: _Context, device: DeviceProfile, surplus: float | None
) -> float | None:
    """Return what this appliance earns per hour on the current surplus.

    **Only for an appliance that modulates**, and it is the honest half of a
    problem the per-cycle amount could not solve (SPEC.md §56.4). A charger's
    advice is "take what is spare right now", which has no end, so there is no
    cycle to price. Running the old formula anyway produced a confident
    "EUR 1,20" for a piece of advice about the next twenty minutes of sun — a
    number that looks plausible and promises something that does not happen.

    The counterpart is in :func:`_solar_savings`, which returns ``None`` for
    exactly these appliances so the two amounts can never be confused, and so
    the per-advice threshold never measures a rate.
    """
    if not device.modulates:
        return None

    power_w = device.usable_power_w(surplus)
    margin = context.metrics.self_consumption_margin_eur_kwh
    if power_w is None or margin is None:
        return None
    return round(power_w / WATTS_PER_KILOWATT * margin, 2)


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
