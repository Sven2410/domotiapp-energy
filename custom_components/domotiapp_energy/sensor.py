"""The five sensors of the DomotiApp Energy device (SPEC.md §19).

Four of them expose one number from the latest calculation; the fifth exposes
the primary advice, whose full text does not fit in a state and therefore lives
in the attributes.

None of these sensors reads an entity itself: they render what the coordinator
last calculated, and go to ``unknown`` when a value could not be determined.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    ATTR_ADVICE_CONFIDENCE,
    ATTR_ADVICE_ITEMS,
    ATTR_ADVICE_MEASUREMENTS,
    ATTR_ADVICE_MESSAGE,
    ATTR_ADVICE_REASON_CODE,
    ATTR_ADVICE_SEVERITY,
    ATTR_LAST_CALCULATED,
    ENTITY_KEY_CURRENT_ADVICE,
    ENTITY_KEY_DATA_QUALITY,
    ENTITY_KEY_ENERGY_SCORE,
    ENTITY_KEY_GRID_POWER,
    ENTITY_KEY_SOLAR_SURPLUS,
    MAX_ADVICE_ITEMS_IN_ATTRIBUTES,
    MAX_STATE_LENGTH,
)
from .coordinator import DomotiAppEnergyConfigEntry, EnergyCoordinator
from .entity import DomotiAppEnergyEntity
from .models import CoachResult


@dataclass(frozen=True, kw_only=True)
class DomotiAppEnergySensorDescription(SensorEntityDescription):
    """A sensor plus the one value it reads out of the coach result."""

    value_fn: Callable[[CoachResult], StateType]


SENSOR_DESCRIPTIONS: tuple[DomotiAppEnergySensorDescription, ...] = (
    DomotiAppEnergySensorDescription(
        key=ENTITY_KEY_ENERGY_SCORE,
        state_class=SensorStateClass.MEASUREMENT,
        # No device class and no unit: this is a DomotiApp indicator, not a
        # certified efficiency rating (SPEC.md §16).
        value_fn=lambda result: result.metrics.energy_score,
    ),
    DomotiAppEnergySensorDescription(
        key=ENTITY_KEY_DATA_QUALITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda result: result.metrics.data_quality.score,
    ),
    DomotiAppEnergySensorDescription(
        key=ENTITY_KEY_GRID_POWER,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda result: result.metrics.grid_power_w,
    ),
    DomotiAppEnergySensorDescription(
        key=ENTITY_KEY_SOLAR_SURPLUS,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda result: result.metrics.solar_surplus_w,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DomotiAppEnergyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors for this config entry."""
    coordinator = entry.runtime_data.coordinator
    entities: list[DomotiAppEnergyEntity] = [
        DomotiAppEnergySensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    entities.append(CurrentAdviceSensor(coordinator, entry))
    async_add_entities(entities)


class DomotiAppEnergySensor(DomotiAppEnergyEntity, SensorEntity):
    """A single number from the latest calculation."""

    entity_description: DomotiAppEnergySensorDescription

    def __init__(
        self,
        coordinator: EnergyCoordinator,
        entry: DomotiAppEnergyConfigEntry,
        description: DomotiAppEnergySensorDescription,
    ) -> None:
        """Store the description that says what to read."""
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the value, or None when it could not be determined.

        None becomes ``unknown``, which is the honest answer: a grid meter that
        cannot be read is not a grid meter reading zero (SPEC.md §16).
        """
        return self.entity_description.value_fn(self.coordinator.data)


class CurrentAdviceSensor(DomotiAppEnergyEntity, SensorEntity):
    """The primary advice, with the rest of the coach result in attributes."""

    def __init__(
        self,
        coordinator: EnergyCoordinator,
        entry: DomotiAppEnergyConfigEntry,
    ) -> None:
        """Set up the advice sensor."""
        super().__init__(coordinator, entry, ENTITY_KEY_CURRENT_ADVICE)

    @property
    def native_value(self) -> str | None:
        """Return the advice title, hard-truncated to what a state may hold.

        Home Assistant refuses a state longer than 255 characters, and a
        refused state would drop the sensor entirely instead of shortening it.
        """
        primary = self.coordinator.data.primary_advice
        if primary is None:
            return None
        return primary.title[:MAX_STATE_LENGTH]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the full advice text and the supporting numbers.

        Capped at the top five advice items so the attributes stay well within
        the state machine's budget (SPEC.md §19).
        """
        result = self.coordinator.data
        primary = result.primary_advice
        attributes: dict[str, Any] = {
            ATTR_LAST_CALCULATED: result.generated_at.isoformat(),
            ATTR_ADVICE_ITEMS: [
                {
                    "title": item.title,
                    ATTR_ADVICE_MESSAGE: item.message,
                    ATTR_ADVICE_REASON_CODE: item.reason_code,
                    ATTR_ADVICE_SEVERITY: item.severity,
                    ATTR_ADVICE_CONFIDENCE: item.confidence,
                }
                for item in result.advice[:MAX_ADVICE_ITEMS_IN_ATTRIBUTES]
            ],
        }

        if primary is not None:
            attributes[ATTR_ADVICE_MESSAGE] = primary.message
            attributes[ATTR_ADVICE_REASON_CODE] = primary.reason_code
            attributes[ATTR_ADVICE_SEVERITY] = primary.severity
            attributes[ATTR_ADVICE_CONFIDENCE] = primary.confidence
            attributes[ATTR_ADVICE_MEASUREMENTS] = dict(primary.measurements)

        return attributes
