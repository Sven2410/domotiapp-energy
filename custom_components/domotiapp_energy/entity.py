"""The shared base class for the DomotiApp Energy entities (SPEC.md §19).

Both platforms need the same device, the same unique-id scheme and the same
naming rules, so those live here rather than being copied into ``sensor.py``
and ``binary_sensor.py``.

Deviation from SPEC.md §4, which does not list this file: the alternative was
for ``binary_sensor.py`` to import a base class out of ``sensor.py``, which
makes one platform depend on another for no reason.

Naming is the part that matters. ``_attr_has_entity_name`` plus a translation
key is all that is set: Home Assistant then builds the object id as
``slugify(device name + " " + English entity name)``, and the English name
comes from ``translations/en.json``. Nothing forces an object id, so the ids in
the README are the ones the normal derivation produces — which is exactly what
tests/test_entities.py verifies.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MODEL, DOMAIN, INTEGRATION_NAME, MANUFACTURER, VERSION
from .coordinator import EnergyCoordinator
from .models import EnergyMetrics


class DomotiAppEnergyEntity(CoordinatorEntity[EnergyCoordinator]):
    """One entity of the integration's own device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EnergyCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        """Bind the entity to the coordinator and to the integration's device.

        The device name is fixed to ``DomotiApp Energy`` and deliberately not
        the home name: the entity ids are derived from it, so letting the home
        name in would give every customer different ids (SPEC.md §19).
        """
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=INTEGRATION_NAME,
            manufacturer=MANUFACTURER,
            model=DEVICE_MODEL,
            sw_version=VERSION,
        )

    @property
    def available(self) -> bool:
        """Return True for as long as the integration is loaded.

        Missing source data yields a state of ``unknown``, never
        ``unavailable``: an unavailable data quality meter disappears from the
        dashboard exactly when it has something to say (SPEC.md §19).
        """
        return True

    @property
    def metrics(self) -> EnergyMetrics:
        """Return the metrics of the most recent calculation."""
        return self.coordinator.data.metrics
