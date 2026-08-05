"""The peak risk binary sensor (SPEC.md §19).

``problem`` is the right device class: the sensor says whether the grid load is
at or above the configured warning level, not whether anything is switched on.
The integration only warns — it never intervenes (SPEC.md §2.2).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ENTITY_KEY_PEAK_RISK
from .coordinator import DomotiAppEnergyConfigEntry, EnergyCoordinator
from .entity import DomotiAppEnergyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DomotiAppEnergyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors for this config entry."""
    async_add_entities([PeakRiskBinarySensor(entry.runtime_data.coordinator, entry)])


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
