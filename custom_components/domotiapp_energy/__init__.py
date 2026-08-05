"""The DomotiApp Energy integration (SPEC.md §6, §18, §19, §20).

Setup is deliberately boring: load the storage, build a coordinator around the
engine, hand both to ``entry.runtime_data`` and forward the two entity
platforms. Everything that varies per installation is in the storage, not here.

Two things are registered once in ``async_setup`` rather than per entry: the
services. Registering them in ``async_setup_entry`` would remove them on the
first reload and never bring them back (SPEC.md §20).

The side panel is not registered yet — that is phase 7 of SPEC.md §30, together
with ``panel.py`` and the frontend.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_HOME_NAME,
    DEFAULT_HOME_NAME,
    DOMAIN,
    SERVICE_CLEAR_LOG,
    SERVICE_RECALCULATE,
)
from .coordinator import (
    DomotiAppEnergyConfigEntry,
    DomotiAppEnergyData,
    EnergyCoordinator,
)
from .engine.providers import RuleBasedCoachProvider
from .models import StoredConfiguration
from .storage import ConfigurationStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services once, for the lifetime of Home Assistant."""
    _async_register_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: DomotiAppEnergyConfigEntry
) -> bool:
    """Set up the single config entry."""
    store = ConfigurationStore(hass)
    await store.async_load()
    await _async_sync_home_name(store, entry)

    coordinator = EnergyCoordinator(hass, entry, store, RuleBasedCoachProvider())
    entry.runtime_data = DomotiAppEnergyData(store=store, coordinator=coordinator)

    coordinator.async_start()
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DomotiAppEnergyConfigEntry
) -> bool:
    """Unload the config entry.

    The subscriptions of the coordinator were registered with
    ``entry.async_on_unload`` and are taken down by Home Assistant itself. The
    services stay registered: they belong to the integration, not to this entry
    (SPEC.md §20).
    """
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant, entry: DomotiAppEnergyConfigEntry
) -> None:
    """Reload the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_sync_home_name(store: ConfigurationStore, entry: ConfigEntry) -> None:
    """Copy the home name from the entry into the storage when it changed.

    The name lives in both places on purpose: the entry needs it for its title,
    the storage needs it for the panel. The entry wins, because that is where
    the config flow writes it (SPEC.md §6). Everything else in the storage is
    untouched here.

    This is a configuration change made by a user in the GUI, so it consumes a
    revision — but only when there is really something to change, so a restart
    or a reload does not quietly bump the revision (SPEC.md §13).
    """
    home_name = entry.data.get(CONF_HOME_NAME, DEFAULT_HOME_NAME)
    if store.config.home.home_name == home_name:
        return

    def _apply(config: StoredConfiguration) -> None:
        config.home.home_name = home_name

    await store.async_update(_apply)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the two services of SPEC.md §20."""
    if hass.services.has_service(DOMAIN, SERVICE_RECALCULATE):
        return

    async def _async_recalculate(call: ServiceCall) -> None:
        """Force a recalculation. Controls nothing (SPEC.md §2.2)."""
        await _async_check_admin(hass, call)
        for entry in _loaded_entries(hass):
            await entry.runtime_data.coordinator.async_recalculate()

    async def _async_clear_log(call: ServiceCall) -> None:
        """Empty the internal logbook. Touches nothing else."""
        await _async_check_admin(hass, call)
        for entry in _loaded_entries(hass):
            await entry.runtime_data.store.async_clear_logs()

    hass.services.async_register(DOMAIN, SERVICE_RECALCULATE, _async_recalculate)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_LOG, _async_clear_log)


def _loaded_entries(hass: HomeAssistant) -> list[DomotiAppEnergyConfigEntry]:
    """Return the entries that are loaded and therefore have runtime data.

    ``single_config_entry`` limits this to one, but iterating costs nothing and
    does not depend on that staying true.
    """
    return [
        entry
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if hasattr(entry, "runtime_data")
    ]


async def _async_check_admin(hass: HomeAssistant, call: ServiceCall) -> None:
    """Refuse a service call from a non-admin user.

    Home Assistant does not check this for services, so it is done explicitly
    (SPEC.md §20). A call without a user id comes from an automation or script
    rather than from a person and is allowed: those are configured by an admin
    in the first place.
    """
    if call.context.user_id is None:
        return

    user = await hass.auth.async_get_user(call.context.user_id)
    if user is None or not user.is_admin:
        raise Unauthorized(context=call.context)
