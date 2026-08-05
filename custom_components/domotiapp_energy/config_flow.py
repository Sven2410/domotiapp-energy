"""The config flow of DomotiApp Energy (SPEC.md §6).

One step, one entry, two fields: the home name and an acknowledgement that this
integration configures nothing by itself. Everything else — sources, devices,
preferences — is entered in the panel and lives in the storage helper, so the
config flow stays as short as the installer's first minute with the product.

There is no options flow. SPEC.md §6 asks for an options flow *or*
``async_step_reconfigure`` and to use one consistently; reconfigure is the one
used here, because the home name is entry data rather than a runtime option and
reconfigure edits exactly that.

``single_config_entry: true`` in the manifest produces the
``single_instance_allowed`` abort on a second entry, so there is no hand-written
check for it here.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    CONF_HOME_NAME,
    CONF_MANUAL_SETUP_ACKNOWLEDGED,
    DEFAULT_HOME_NAME,
    DOMAIN,
    ERROR_ACKNOWLEDGEMENT_REQUIRED,
)


def _schema(home_name: str, *, acknowledged: bool = False) -> vol.Schema:
    """Return the form schema, pre-filled with what is known."""
    return vol.Schema(
        {
            vol.Required(CONF_HOME_NAME, default=home_name): str,
            vol.Required(CONF_MANUAL_SETUP_ACKNOWLEDGED, default=acknowledged): bool,
        }
    )


def _reconfigure_schema(home_name: str) -> vol.Schema:
    """Return the form for changing the home name only."""
    return vol.Schema({vol.Required(CONF_HOME_NAME, default=home_name): str})


class DomotiAppEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Adds and reconfigures the single DomotiApp Energy entry."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the home name and the manual-setup acknowledgement."""
        errors: dict[str, str] = {}
        home_name = DEFAULT_HOME_NAME
        acknowledged = False

        if user_input is not None:
            home_name = user_input[CONF_HOME_NAME].strip() or DEFAULT_HOME_NAME
            acknowledged = user_input[CONF_MANUAL_SETUP_ACKNOWLEDGED]

            if acknowledged:
                return self.async_create_entry(
                    title=home_name,
                    data={
                        CONF_HOME_NAME: home_name,
                        CONF_MANUAL_SETUP_ACKNOWLEDGED: True,
                    },
                )
            # Refused rather than silently accepted: the acknowledgement is the
            # installer confirming that nothing is detected for them, which is
            # the whole premise of the product (SPEC.md §2.1).
            errors[CONF_MANUAL_SETUP_ACKNOWLEDGED] = ERROR_ACKNOWLEDGEMENT_REQUIRED

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(home_name, acknowledged=acknowledged),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the home name of the existing entry.

        The acknowledgement is not asked again: it was given once and cannot be
        withdrawn without removing the integration.

        The name is written to the entry only. ``async_setup_entry`` copies it
        into the storage on the reload that follows, which keeps the storage
        the single place where the extended configuration is written
        (SPEC.md §6, §13).
        """
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            home_name = user_input[CONF_HOME_NAME].strip() or DEFAULT_HOME_NAME
            return self.async_update_reload_and_abort(
                entry,
                title=home_name,
                data_updates={CONF_HOME_NAME: home_name},
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_reconfigure_schema(
                entry.data.get(CONF_HOME_NAME, DEFAULT_HOME_NAME)
            ),
        )
