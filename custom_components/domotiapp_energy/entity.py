"""The shared base class for the DomotiApp Energy entities (SPEC.md §19).

Both platforms need the same device, the same unique-id scheme and the same
naming rules, so those live here rather than being copied into ``sensor.py``
and ``binary_sensor.py``.

Deviation from SPEC.md §4, which does not list this file: the alternative was
for ``binary_sensor.py`` to import a base class out of ``sensor.py``, which
makes one platform depend on another for no reason.

Naming is the part that matters, and it is not what SPEC.md §19 originally
assumed. Home Assistant builds the object id from
``slugify(device name + " " + entity name)``, but the entity name it uses there
is the one in the *native entity-id language*:

.. code-block:: python

    # homeassistant/helpers/entity_platform.py
    object_id_language = (
        hass.config.language
        if hass.config.language in languages.NATIVE_ENTITY_IDS
        else languages.DEFAULT_LANGUAGE
    )

``NATIVE_ENTITY_IDS`` contains 41 languages including ``nl``, so a Dutch
installation produced ``sensor.domotiapp_energy_energiescore`` while an English
one produced ``sensor.domotiapp_energy_score``. For a normal integration that
is desirable; for this one it is not, because the six ids are documented in the
README and customers build dashboards and automations on them.

:meth:`DomotiAppEnergyEntity.suggested_object_id` therefore pins the name the
object id is built from to the English one. Home Assistant still adds the
device-name prefix and still slugifies, and the *displayed* name stays whatever
the customer's language says — only the id stops moving.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_MODEL,
    DOMAIN,
    ENTITY_OBJECT_ID_NAMES,
    INTEGRATION_NAME,
    MANUFACTURER,
    VERSION,
)
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
        self._entity_key = key
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
    def suggested_object_id(self) -> str | None:
        """Return the English name the object id has to be built from.

        Overriding this property is the only way to pin the id without also
        hard-coding the device-name prefix: ``Entity`` has no
        ``_attr_suggested_object_id``, and setting ``self.entity_id`` directly
        would bypass Home Assistant's own composition entirely.

        Home Assistant calls this once, while the entity is being registered.
        An entity that is already in the registry keeps the id it was given, so
        changing a name here only affects fresh installations — which is why
        CLAUDE.md treats a change to these ids as a breaking change.
        """
        return ENTITY_OBJECT_ID_NAMES[self._entity_key]

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
