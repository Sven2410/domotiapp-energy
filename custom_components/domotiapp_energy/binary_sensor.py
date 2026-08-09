"""The two binary sensors (SPEC.md §19, §45).

``problem`` is the right device class for both: they say whether something is
wrong, not whether anything is switched on. The integration only warns — it
never intervenes (SPEC.md §2.2).

The device class is also what makes them usable on a dashboard without a line
of styling: every core card paints a ``problem`` sensor red when it is on.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTENTION_ADVICE_REASON_CODES,
    ATTR_ADVICE_MESSAGE,
    ATTR_ADVICE_REASON_CODE,
    ATTR_ADVICE_TITLE,
    ENTITY_KEY_ATTENTION,
    ENTITY_KEY_PEAK_RISK,
)
from .coordinator import DomotiAppEnergyConfigEntry, EnergyCoordinator
from .entity import DomotiAppEnergyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DomotiAppEnergyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors for this config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            PeakRiskBinarySensor(coordinator, entry),
            AttentionBinarySensor(coordinator, entry),
        ]
    )


class PeakRiskBinarySensor(DomotiAppEnergyEntity, BinarySensorEntity):
    """On when the grid load reaches the configured warning level."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: EnergyCoordinator,
        entry: DomotiAppEnergyConfigEntry,
    ) -> None:
        """Set up the peak risk sensor."""
        super().__init__(coordinator, entry, ENTITY_KEY_PEAK_RISK)

    @property
    def is_on(self) -> bool | None:
        """Return whether there is a peak risk, or None when unknown.

        Without a measurable grid load there is no risk to report and none to
        deny, so the state stays ``unknown`` rather than claiming "no problem"
        (SPEC.md §16).
        """
        metrics = self.metrics
        if metrics.grid_load_percent is None:
            return None
        return metrics.peak_risk

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the load behind the verdict, so the state is explainable."""
        metrics = self.metrics
        return {
            "grid_load_percent": (
                round(metrics.grid_load_percent, 1)
                if metrics.grid_load_percent is not None
                else None
            ),
        }


class AttentionBinarySensor(DomotiAppEnergyEntity, BinarySensorEntity):
    """On when something about this installation needs a person.

    **This entity exists for a dashboard, not for the panel** (SPEC.md §45). It
    is the one tile an installer puts on a customer's own overview: it colours
    when there is something to do, and tapping it opens the panel.

    Before it existed, that tile needed a `template` binary sensor in every
    customer's `configuration.yaml`. Twenty homes meant twenty copies of one
    condition, and a copy is where drift starts — the definition of "attention"
    would have been slightly different in each of them within a year.

    **What counts as attention is a short, closed list and it is meant to stay
    short.** The bar is not "is this a warning" but *can a person do something
    about it, and is it wrong rather than merely happening*. A price that is
    high every evening is a warning by severity and noise by frequency, and a
    tile that is red every evening is a tile nobody looks at.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: EnergyCoordinator,
        entry: DomotiAppEnergyConfigEntry,
    ) -> None:
        """Set up the attention sensor."""
        super().__init__(coordinator, entry, ENTITY_KEY_ATTENTION)

    @property
    def is_on(self) -> bool | None:
        """Return whether somebody should look, or None before the first result.

        **One source, and that is the fix of 0.11.1.** The reason is written out
        in SPEC.md §45.6: until then this also turned on for any
        `invalid_entity_state` in the metrics, while the attributes kept quoting
        the advice — so the colour came from one object and the sentence from
        another, and on Sven's dashboard the tile went red beside "Geen actie
        nodig". A tile with `device_class: problem` that contradicts its own
        text is worse than no tile.

        Whatever lights it must therefore also supply its sentence, and only the
        advice does that.
        """
        result = self.coordinator.data
        if result.primary_advice is None:
            return None
        return result.primary_advice.reason_code in ATTENTION_ADVICE_REASON_CODES

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return what a tile needs to say something without a template.

        `advice_title` is what `state_content` puts on the second line, so one
        tile carries both the colour and the sentence. Without it a dashboard
        shows "Problem" — true, and useless next to a house that has an actual
        reason.
        """
        primary = self.coordinator.data.primary_advice
        if primary is None:
            return {}
        return {
            ATTR_ADVICE_TITLE: primary.title,
            ATTR_ADVICE_MESSAGE: primary.message,
            ATTR_ADVICE_REASON_CODE: primary.reason_code,
        }
