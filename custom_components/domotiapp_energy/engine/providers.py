"""Phrasing the advice in Dutch (SPEC.md §17).

A coach provider is the last step in the chain: it receives a finished
:class:`CoachResult` and returns one with the ``explanations`` filled in, so
the panel's question selector has an answer for every fixed question.

A provider may never invent a value, give a reason other than the reason codes
the engine produced, control a device, select an entity or call a Home
Assistant service. :class:`RuleBasedCoachProvider` is the only working
implementation in 0.1.0; it phrases what it is given and nothing more.

:class:`ExtensionCoachProvider` is the deliberately inactive extension point
SPEC.md §17 asks for. It contains no provider, no client and no API key, and
raises when used. There is no network access anywhere in this integration.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from custom_components.domotiapp_energy.const import (
    COMPLETENESS_ITEM_DEVICE_PROFILE,
    COMPLETENESS_ITEM_GRID,
    COMPLETENESS_ITEM_HOME,
    COMPLETENESS_ITEM_PRICE,
    COMPLETENESS_ITEM_SOLAR,
    COMPLETENESS_ITEM_TIME_WINDOWS,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    EXPLANATION_KEY_MISSING_DATA,
    EXPLANATION_KEY_PEAK_RISK,
    EXPLANATION_KEY_SCORE_BREAKDOWN,
    EXPLANATION_KEY_USE_DEVICE_NOW,
    EXPLANATION_KEY_WHY_ADVICE,
    MEASUREMENT_GRID_LOAD_PERCENT,
    MEASUREMENT_GRID_POWER_W,
    MEASUREMENT_MISSING_ITEMS,
    MEASUREMENT_PRICE,
    MEASUREMENT_SOLAR_SURPLUS_W,
    SCORE_COMPONENT_DATA_QUALITY,
    SCORE_COMPONENT_FLEXIBILITY,
    SCORE_COMPONENT_PEAK,
    SCORE_COMPONENT_PRICE,
    SCORE_COMPONENT_SOLAR,
)
from custom_components.domotiapp_energy.models import CoachResult, EnergyMetrics

from .reason_codes import (
    REASON_HIGH_ENERGY_PRICE,
    REASON_HIGH_GRID_EXPORT,
    REASON_HIGH_GRID_LOAD,
    REASON_LOW_ENERGY_PRICE,
    REASON_SOLAR_SURPLUS_AVAILABLE,
)

# Dutch labels for the checklist keys and score components, so an explanation
# reads as a sentence instead of a list of identifiers.
_ITEM_LABELS: dict[str, str] = {
    COMPLETENESS_ITEM_HOME: "de woninggegevens",
    COMPLETENESS_ITEM_GRID: "een geldige netbron",
    COMPLETENESS_ITEM_SOLAR: "een geldige zonnebron",
    COMPLETENESS_ITEM_PRICE: "prijsinformatie",
    COMPLETENESS_ITEM_DEVICE_PROFILE: "een compleet apparaatprofiel",
    COMPLETENESS_ITEM_TIME_WINDOWS: "tijdvensters voor flexibele apparaten",
}

# Dutch labels for the measurement keys an AdviceItem carries. The price label
# says "all-in" because that is what the number is: the calculator normalises a
# market price on reading (SPEC.md §16), and a reader who assumed otherwise
# would think the coach was quoting a figure three times too high.
_MEASUREMENT_LABELS: dict[str, str] = {
    MEASUREMENT_PRICE: "all-in prijs in €/kWh",
    MEASUREMENT_GRID_LOAD_PERCENT: "netbelasting in %",
    MEASUREMENT_GRID_POWER_W: "netvermogen in W",
    MEASUREMENT_SOLAR_SURPLUS_W: "zonneoverschot in W",
    MEASUREMENT_MISSING_ITEMS: "ontbrekende onderdelen",
}

# The confidence levels travel as English identifiers, like every other code in
# this project, and one of them used to end up verbatim in the answer to "Waarom
# krijg ik dit advies?": "Betrouwbaarheid: high." A reader is owed a word here,
# and the frontend has the same table in core/labels.js for what it renders.
_CONFIDENCE_LABELS: dict[str, str] = {
    CONFIDENCE_LOW: "laag",
    CONFIDENCE_MEDIUM: "gemiddeld",
    CONFIDENCE_HIGH: "hoog",
}

_COMPONENT_LABELS: dict[str, str] = {
    SCORE_COMPONENT_DATA_QUALITY: "datakwaliteit",
    SCORE_COMPONENT_PEAK: "netbelasting",
    SCORE_COMPONENT_SOLAR: "zonnebenutting",
    SCORE_COMPONENT_PRICE: "prijs",
    SCORE_COMPONENT_FLEXIBILITY: "flexibiliteit",
}


@runtime_checkable
class CoachProvider(Protocol):
    """The contract every coach provider satisfies (SPEC.md §17)."""

    async def async_generate(self, result: CoachResult) -> CoachResult:
        """Return the result with its explanations filled in."""
        ...


class RuleBasedCoachProvider:
    """Builds Dutch explanations from the reason codes and the metrics.

    Every sentence is derived from a value the engine already calculated. When
    a value is unknown the explanation says so rather than filling the gap.
    """

    async def async_generate(self, result: CoachResult) -> CoachResult:
        """Return a copy of the result with the explanations filled in."""
        result.explanations = {
            EXPLANATION_KEY_WHY_ADVICE: _why_advice(result),
            EXPLANATION_KEY_USE_DEVICE_NOW: _use_device_now(result),
            EXPLANATION_KEY_PEAK_RISK: _peak_risk(result.metrics),
            EXPLANATION_KEY_MISSING_DATA: _missing_data(result.metrics),
            EXPLANATION_KEY_SCORE_BREAKDOWN: _score_breakdown(result.metrics),
        }
        result.missing_data = list(result.metrics.data_quality.missing_items)
        return result


class ExtensionCoachProvider:
    """The inactive extension point for a future provider (SPEC.md §17).

    Present so a later release can add a different way of phrasing advice
    without changing the coordinator. It holds no configuration, performs no
    I/O and is never instantiated by the integration itself.
    """

    async def async_generate(self, result: CoachResult) -> CoachResult:
        """Raise: there is no second provider in 0.1.0."""
        raise NotImplementedError(
            "No alternative coach provider is available in this release"
        )


def _why_advice(result: CoachResult) -> str:
    """Explain the primary advice in terms of what was measured."""
    primary = result.primary_advice
    if primary is None:
        return "Er is op dit moment geen advies."

    parts = [primary.message]
    readings = ", ".join(
        f"{label}: {value}"
        for key, value in primary.measurements.items()
        if (label := _MEASUREMENT_LABELS.get(key)) is not None
    )
    if readings:
        parts.append(f"Gebaseerd op {readings}.")

    # A level we have no word for is left out rather than printed as its code:
    # an identifier in a Dutch sentence is worse than a shorter sentence.
    confidence = _CONFIDENCE_LABELS.get(primary.confidence)
    if confidence is not None:
        parts.append(f"Betrouwbaarheid: {confidence}.")
    return " ".join(parts)


def _use_device_now(result: CoachResult) -> str:
    """Answer whether this is a good moment to run a device.

    The order mirrors the advice ranking of SPEC.md §16: surplus and peak load
    outrank the price, so the price only gets to answer when neither of those
    said anything.
    """
    codes = {item.reason_code for item in result.advice}

    for item in result.advice:
        if item.reason_code == REASON_SOLAR_SURPLUS_AVAILABLE:
            return item.message
    if REASON_HIGH_GRID_EXPORT in codes:
        # Overloading by export is the one peak situation where using more is
        # the right answer.
        return (
            "Ja. De woning levert veel terug aan het net; dat overschot kun je "
            "nu beter zelf gebruiken."
        )
    if REASON_HIGH_GRID_LOAD in codes:
        return (
            "Nu is geen gunstig moment: de netbelasting ligt dicht bij het "
            "ingestelde maximum."
        )

    price = _format_price(result.metrics.current_price_eur_kwh)
    if REASON_LOW_ENERGY_PRICE in codes:
        # Without this the answer used to be "no reason to move anything" while
        # the advice list was showing a low price advice right next to it.
        return (
            f"Ja. De all-in energieprijs is nu {price} en ligt onder de "
            f"ingestelde lage prijsgrens."
        )
    if REASON_HIGH_ENERGY_PRICE in codes:
        return (
            f"Nu is geen gunstig moment: de all-in energieprijs is {price} en "
            f"ligt boven de ingestelde hoge prijsgrens."
        )

    return (
        "Er is op dit moment geen aanleiding om een apparaat te verplaatsen of "
        "juist nu te gebruiken."
    )


def _format_price(value: float | None) -> str:
    """Return a price as readable Dutch, or say that it is unknown.

    The number is whatever the metrics hold, which is always the normalised
    all-in price — the same one the thresholds and the savings formula use.
    """
    if value is None:
        return "onbekend"
    return f"€ {value:.3f} per kWh".replace(".", ",")


def _peak_risk(metrics: EnergyMetrics) -> str:
    """Answer whether there is a peak load risk right now.

    The verb follows the direction of the flow: a home that is exporting is not
    "using" its maximum, and saying so would misdescribe the very situation the
    question is about.
    """
    if metrics.grid_load_percent is None:
        return (
            "De netbelasting is niet te bepalen. Vul het maximale netvermogen in "
            "en koppel een netbron."
        )

    load = round(metrics.grid_load_percent, 1)
    exporting = metrics.grid_power_w is not None and metrics.grid_power_w < 0
    direction = "levert terug met" if exporting else "gebruikt"
    verdict = "Ja" if metrics.peak_risk else "Nee"

    return (
        f"{verdict}. De woning {direction} {load}% van het ingestelde maximale "
        f"netvermogen."
    )


def _missing_data(metrics: EnergyMetrics) -> str:
    """List what still has to be configured.

    Items this home cannot be judged on are named separately rather than left
    out in silence. A customer looking at a data quality of 100 with four items
    behind it is owed the sentence explaining why it was four and not six —
    otherwise the score looks like it skipped something.
    """
    quality = metrics.data_quality
    named = [
        label
        for item in quality.missing_items
        if (label := _ITEM_LABELS.get(item)) is not None
    ]
    skipped = [
        label
        for item in quality.not_applicable_items
        if (label := _ITEM_LABELS.get(item)) is not None
    ]

    if named:
        sentence = f"Nog ontbrekend: {', '.join(named)}."
    else:
        sentence = "Alle gegevens voor een betrouwbaar advies zijn ingevuld."

    if skipped:
        sentence += (
            f" Niet van toepassing op deze woning, en dus niet meegeteld: "
            f"{', '.join(skipped)}."
        )
    return sentence


def _score_breakdown(metrics: EnergyMetrics) -> str:
    """Show the components behind the energy score."""
    if metrics.energy_score is None or not metrics.score_components:
        return "De energiescore is nog niet berekend."

    parts = ", ".join(
        f"{label} {round(value)}"
        for key, value in metrics.score_components.items()
        if (label := _COMPONENT_LABELS.get(key)) is not None
    )
    if not parts:
        return "De energiescore is nog niet berekend."
    return f"De score is {metrics.energy_score}, opgebouwd uit: {parts}."
