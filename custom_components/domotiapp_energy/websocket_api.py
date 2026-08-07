"""The WebSocket API the panel talks to (SPEC.md §14 and §33.9).

Seventeen commands. The reads may be called by any logged-in user; the writes
divide along **who owns the field**, not along whether they write:

* commands that change **installer** configuration require an admin — the home
  profile, the sources, the whole of an appliance row, the logbook;
* commands that change **resident** configuration do not — the advice
  preferences and the six operating fields of an appliance
  (:data:`~.const.DEVICE_OPERATION_FIELDS`).

That second group does raise the revision, so it looks like it belongs in the
admin list. It does not: the line is drawn by whose data changes. A resident who
may not set his own quiet hours cannot use the tab that exists for him
(SPEC.md §33.9). The panel no longer hides any tab; it greys out what a resident
does not own, and this module is where that is actually enforced — a disabled
field is not a permission check.

Two rules shape every write:

* **Optimistic concurrency.** Each write carries the ``expected_revision`` it
  was based on. If the stored configuration moved on in the meantime the write
  is refused with ``revision_conflict`` and the current configuration comes
  back with the error, so the panel can reload instead of overwriting someone
  else's change blind.
* **Nothing is trusted.** Voluptuous validates the envelope and the type enums;
  :mod:`.models` coerces every remaining field defensively. A payload can add
  keys we do not know and they are ignored, not stored.

Every read and write answer carries an ``issues`` map alongside its documented
keys, so the panel can put each validation message next to the field it is
about. Almost nothing is refused for what is in that map: an installer fills a
row in gradually, and a half-finished source has to be savable as a work in
progress. The single exception is control that was ruled out for this
installation — see :func:`_forbidden_control_error`.

All commands are registered once in ``async_setup``. Registering per entry
would leave them dangling after the first reload (SPEC.md §14).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.components.websocket_api import messages as ws_messages
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    ATTR_EXPECTED_REVISION,
    ATTR_ISSUES,
    ATTR_ITEM,
    ATTR_REVISION,
    CONF_HOME_NAME,
    CONTROL_MODES,
    DEVICE_TYPES,
    DOMAIN,
    ERR_DUPLICATE_ID,
    ERR_INVALID_FORMAT,
    ERR_NOT_FOUND,
    ERR_REVISION_CONFLICT,
    ERR_STORAGE_ERROR,
    LOG_EVENT_CONFIG_CHANGED,
    LOG_EVENT_DEVICE_ADDED,
    LOG_EVENT_DEVICE_REMOVED,
    MAX_DAY_OF_WEEK,
    MIN_DAY_OF_WEEK,
    PRIORITIES,
    SOURCE_TYPES,
    VALIDATION_CONTROL_FORBIDDEN,
    WS_COACH_GET,
    WS_COACH_RECALCULATE,
    WS_CONFIG_GET,
    WS_DEVICES_CREATE,
    WS_DEVICES_DELETE,
    WS_DEVICES_LIST,
    WS_DEVICES_SET_OPERATION,
    WS_DEVICES_UPDATE,
    WS_HOME_UPDATE,
    WS_LOGS_CLEAR,
    WS_LOGS_LIST,
    WS_PREFERENCES_GET,
    WS_PREFERENCES_UPDATE,
    WS_SOURCES_CREATE,
    WS_SOURCES_DELETE,
    WS_SOURCES_LIST,
    WS_SOURCES_UPDATE,
)
from .coordinator import DomotiAppEnergyData
from .models import (
    DeviceProfile,
    EnergySource,
    HomeProfile,
    StoredConfiguration,
    UserPreferences,
)
from .storage import RevisionConflictError, StorageError
from .validators import (
    ValidationIssue,
    validate_configuration,
    validate_device_profile,
    validate_energy_source,
)

_LOGGER = logging.getLogger(__name__)

# Logbook subjects for changes that are not about a single row.
_SUBJECT_HOME = "home"
_SUBJECT_PREFERENCES = "preferences"


class _CommandError(HomeAssistantError):
    """A refusal with one of the error codes from SPEC.md §14.

    Raised from inside the store's mutate callback, so existence and duplicate
    checks run while the write lock is held. Raising there also means nothing
    is written: the store only persists after the callback returns.
    """

    def __init__(self, code: str, message: str) -> None:
        """Store the machine-readable code alongside the readable message."""
        super().__init__(message)
        self.code = code
        self.reason = message


# --- Schemas ----------------------------------------------------------------
#
# The type enums are enforced here rather than in the model layer. A stored row
# with an unrecognised type is quarantined and kept (SPEC.md §12), because it
# came from a file we did not write; a row arriving from the panel with an
# unknown type is simply a bad request, and accepting it would create a
# quarantined row on purpose.

_SOURCE_TYPE = {vol.Required("type"): vol.In(SOURCE_TYPES)}
_DEVICE_TYPE = {vol.Required("device_type"): vol.In(DEVICE_TYPES)}

# extra=ALLOW_EXTRA on purpose: the remaining fields are coerced defensively by
# from_dict(), which ignores what it does not know instead of failing a form.
_CREATE_SOURCE = vol.Schema(
    {vol.Optional("id"): str, **_SOURCE_TYPE}, extra=vol.ALLOW_EXTRA
)
_UPDATE_SOURCE = vol.Schema(
    {vol.Required("id"): str, **_SOURCE_TYPE}, extra=vol.ALLOW_EXTRA
)
_CREATE_DEVICE = vol.Schema(
    {vol.Optional("id"): str, **_DEVICE_TYPE}, extra=vol.ALLOW_EXTRA
)
_UPDATE_DEVICE = vol.Schema(
    {vol.Required("id"): str, **_DEVICE_TYPE}, extra=vol.ALLOW_EXTRA
)

# The one schema in this module that does **not** allow extra keys, and that is
# the whole point of it (SPEC.md §33.10). Everywhere else a stray key is
# harmless because an admin sent it and from_dict drops it. Here the absence of
# a key is the permission boundary: this command is open to every logged-in
# user, so anything beyond the six resident fields has to be refused rather than
# quietly ignored. Voluptuous rejects an unknown key by default and Home
# Assistant turns that into `invalid_format`, which is exactly the answer the
# caller should see.
#
# `vol.Length(min=1)` keeps an empty operation out: it would change nothing and
# still consume a revision, which is the write amplification round A removed.
# Each field is validated on its own here rather than generated from
# DEVICE_OPERATION_FIELDS, because a list of names cannot say that a priority is
# one of four words and a weekday is 0-6. The two are kept in step by a test
# that compares them — the same arrangement the entity object ids use.
_OPERATION_SCHEMA = vol.Schema(
    {
        vol.Optional("control_mode"): vol.In(CONTROL_MODES),
        vol.Optional("priority"): vol.In(PRIORITIES),
        # A time as "HH:MM", or null to clear the bound. Both fields are
        # independently optional on a ready window (SPEC.md §32.2), so clearing
        # one has to be expressible.
        vol.Optional("ready_from"): vol.Any(str, None),
        vol.Optional("ready_before"): vol.Any(str, None),
        vol.Optional("days_of_week"): [
            vol.All(int, vol.Range(min=MIN_DAY_OF_WEEK, max=MAX_DAY_OF_WEEK))
        ],
        vol.Optional("is_noisy"): bool,
    }
)

_SET_OPERATION = vol.All(_OPERATION_SCHEMA, vol.Length(min=1))


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    """Register every command once, for the lifetime of Home Assistant."""
    for handler in (
        handle_config_get,
        handle_home_update,
        handle_sources_list,
        handle_sources_create,
        handle_sources_update,
        handle_sources_delete,
        handle_devices_list,
        handle_devices_create,
        handle_devices_update,
        handle_devices_delete,
        handle_devices_set_operation,
        handle_preferences_get,
        handle_preferences_update,
        handle_coach_get,
        handle_coach_recalculate,
        handle_logs_list,
        handle_logs_clear,
    ):
        websocket_api.async_register_command(hass, handler)


# --- Shared plumbing --------------------------------------------------------


def _async_get_data(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> DomotiAppEnergyData | None:
    """Return the runtime data, or send an error and return None."""
    entries = [
        entry
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if hasattr(entry, "runtime_data")
    ]
    if not entries:
        connection.send_error(
            msg["id"],
            ERR_NOT_FOUND,
            "DomotiApp Energy is niet geladen.",
        )
        return None
    return entries[0].runtime_data


async def _async_write(
    connection: ActiveConnection,
    msg: dict[str, Any],
    data: DomotiAppEnergyData,
    mutate: Callable[[StoredConfiguration], None],
) -> int | None:
    """Apply a configuration change and return the new revision, or None.

    Sends the appropriate error itself when the write is refused, so a handler
    only has to check for ``None``.
    """
    try:
        return await data.store.async_update(
            mutate, expected_revision=msg[ATTR_EXPECTED_REVISION]
        )
    except RevisionConflictError:
        _send_revision_conflict(connection, msg, data)
        return None
    except _CommandError as err:
        connection.send_error(msg["id"], err.code, err.reason)
        return None
    except StorageError:
        # Logged without any of the configuration: it holds the home name
        # (SPEC.md §21).
        _LOGGER.exception("Could not persist a configuration change")
        connection.send_error(
            msg["id"],
            ERR_STORAGE_ERROR,
            "De configuratie kon niet worden opgeslagen.",
        )
        return None


@callback
def _send_revision_conflict(
    connection: ActiveConnection, msg: dict[str, Any], data: DomotiAppEnergyData
) -> None:
    """Refuse a stale write and hand back the current configuration.

    ``send_error`` carries only a code and a message, but SPEC.md §14 requires
    the current configuration to travel with the refusal so the panel can
    reload instead of overwriting someone else's change. The frame is therefore
    built from the same helper Home Assistant uses, with two extra keys in the
    error payload.
    """
    message = ws_messages.error_message(
        msg["id"],
        ERR_REVISION_CONFLICT,
        "De configuratie is inmiddels gewijzigd. De actuele gegevens zijn "
        "opnieuw opgehaald.",
    )
    message["error"][ATTR_REVISION] = data.store.revision
    message["error"]["config"] = _config_payload(data.store.config)
    connection.send_message(message)


def _config_payload(config: StoredConfiguration) -> dict[str, Any]:
    """Return the configuration without the logbook.

    The logbook has its own command and can hold 200 entries; sending it along
    with every configuration read would dominate the payload.
    """
    payload = config.to_dict()
    payload.pop("logs", None)
    payload[ATTR_ISSUES] = _issues_payload(config)
    return payload


def _issues_payload(config: StoredConfiguration) -> dict[str, list[dict[str, str]]]:
    """Return every validation issue, keyed by subject (SPEC.md §14).

    The keys are ``"home"``, ``"preferences"`` and the id of each source and
    device that has something wrong, so the panel can put each message next to
    the field it is about instead of showing one generic sentence.

    This travels with **every** read and write answer rather than through a
    command of its own. A second round trip after each save would make every
    form feel slow, and the check itself is a handful of pure comparisons over
    data that is already in memory.
    """
    return {
        subject: [issue.to_dict() for issue in issues]
        for subject, issues in validate_configuration(
            config.home, config.sources, config.devices, config.preferences
        ).items()
    }


def _forbidden_control_error(row: DeviceProfile | EnergySource) -> str | None:
    """Return why this row may not be stored, or None when it may.

    The **only** thing a write is refused for. Everything else validation finds
    travels back as an issue and is stored anyway, because an installer in a
    meter cupboard fills a row in gradually: a grid meter without a meter mode
    is an error too, and refusing it would make a half-finished row impossible
    to save as a work in progress (SPEC.md §12).

    Control that was ruled out for this installation is different in kind. It is
    an agreement about a customer's home, not an unfinished field, and it must
    not be lost because someone later picked a controlling mode from a dropdown.
    """
    for issue in _validate_row(row):
        if issue.code == VALIDATION_CONTROL_FORBIDDEN:
            return issue.message
    return None


def _validate_row(row: DeviceProfile | EnergySource) -> list[ValidationIssue]:
    """Validate one incoming row with the checks that fit its kind."""
    if isinstance(row, DeviceProfile):
        return validate_device_profile(row)
    return validate_energy_source(row)


def _send_write_result(
    connection: ActiveConnection,
    msg: dict[str, Any],
    revision: int,
    item: dict[str, Any] | None,
    config: StoredConfiguration,
) -> None:
    """Send the answer shape every write command shares (SPEC.md §14).

    ``issues`` is a superset of the shape SPEC.md §14 fixes: the two documented
    keys are unchanged, so nothing that ignores the third one breaks.
    """
    connection.send_result(
        msg["id"],
        {
            ATTR_REVISION: revision,
            ATTR_ITEM: item,
            ATTR_ISSUES: _issues_payload(config),
        },
    )


def _find(rows: list[Any], row_id: str, what: str) -> int:
    """Return the index of the row with this id, or raise ``not_found``."""
    for index, row in enumerate(rows):
        if row.id == row_id:
            return index
    raise _CommandError(ERR_NOT_FOUND, f"{what} bestaat niet.")


# --- Reading ----------------------------------------------------------------


@websocket_api.websocket_command({vol.Required("type"): WS_CONFIG_GET})
@websocket_api.async_response
async def handle_config_get(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the whole configuration except the logbook."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], _config_payload(data.store.config))


@websocket_api.websocket_command({vol.Required("type"): WS_SOURCES_LIST})
@websocket_api.async_response
async def handle_sources_list(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return every configured energy source."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return
    config = data.store.config
    connection.send_result(
        msg["id"],
        {
            ATTR_REVISION: config.revision,
            "sources": [source.to_dict() for source in config.sources],
            ATTR_ISSUES: _issues_payload(config),
        },
    )


@websocket_api.websocket_command({vol.Required("type"): WS_DEVICES_LIST})
@websocket_api.async_response
async def handle_devices_list(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return every configured appliance."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return
    config = data.store.config
    connection.send_result(
        msg["id"],
        {
            ATTR_REVISION: config.revision,
            "devices": [device.to_dict() for device in config.devices],
            ATTR_ISSUES: _issues_payload(config),
        },
    )


@websocket_api.websocket_command({vol.Required("type"): WS_PREFERENCES_GET})
@websocket_api.async_response
async def handle_preferences_get(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the advice preferences."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return
    config = data.store.config
    connection.send_result(
        msg["id"],
        {
            ATTR_REVISION: config.revision,
            "preferences": config.preferences.to_dict(),
            ATTR_ISSUES: _issues_payload(config),
        },
    )


@websocket_api.websocket_command({vol.Required("type"): WS_COACH_GET})
@websocket_api.async_response
async def handle_coach_get(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the most recent coach result."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return
    connection.send_result(msg["id"], data.coordinator.data.to_dict())


@websocket_api.websocket_command({vol.Required("type"): WS_LOGS_LIST})
@websocket_api.async_response
async def handle_logs_list(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the logbook, newest entry first."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return
    connection.send_result(
        msg["id"],
        {"logs": [entry.to_dict() for entry in data.store.config.logs]},
    )


@websocket_api.websocket_command({vol.Required("type"): WS_COACH_RECALCULATE})
@websocket_api.async_response
async def handle_coach_recalculate(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Recalculate now and return the fresh result.

    Not an admin command and not revision-guarded: a recalculation produces a
    runtime result, never a configuration change (SPEC.md §13).
    """
    if (data := _async_get_data(hass, connection, msg)) is None:
        return
    await data.coordinator.async_recalculate()
    connection.send_result(msg["id"], data.coordinator.data.to_dict())


# --- Writing ----------------------------------------------------------------


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_HOME_UPDATE,
        vol.Required(ATTR_EXPECTED_REVISION): int,
        vol.Required("home"): dict,
    }
)
@websocket_api.async_response
async def handle_home_update(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Replace the home profile.

    The whole profile is replaced rather than patched: the panel submits the
    complete form, and a partial update would silently keep a value the
    installer just cleared.

    The home name lives in the config entry as well (SPEC.md §6). It is written
    to both here, so the two can never disagree and the copy that
    ``async_setup_entry`` makes on the next reload stays a no-op.
    """
    if (data := _async_get_data(hass, connection, msg)) is None:
        return

    home = HomeProfile.from_dict(msg["home"])

    def _apply(config: StoredConfiguration) -> None:
        config.home = home

    revision = await _async_write(connection, msg, data, _apply)
    if revision is None:
        return

    _async_sync_entry_name(hass, home.home_name)
    await data.store.async_add_log_entry(
        LOG_EVENT_CONFIG_CHANGED,
        "Woninggegevens gewijzigd",
        "De woninggegevens zijn bijgewerkt.",
        subject=_SUBJECT_HOME,
    )
    _send_write_result(connection, msg, revision, home.to_dict(), data.store.config)


@callback
def _async_sync_entry_name(hass: HomeAssistant, home_name: str) -> None:
    """Keep the config entry's copy of the home name in step."""
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        if entry.data.get(CONF_HOME_NAME) == home_name:
            continue
        hass.config_entries.async_update_entry(
            entry,
            title=home_name,
            data={**entry.data, CONF_HOME_NAME: home_name},
        )


# **Deliberately not require_admin** (SPEC.md §33.9). Every field on this
# command is resident territory: the quiet hours, how many pieces of advice to
# show, whether to show the estimated saving. It does change the configuration
# and it does raise the revision, so it looks like it belongs in the admin list
# — but the line is drawn by *whose* data changes, not by *whether* something
# changes. A resident who may not set his own quiet hours cannot use the tab
# that exists for him. Do not "fix" this back; read §33.9 first.
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_PREFERENCES_UPDATE,
        vol.Required(ATTR_EXPECTED_REVISION): int,
        vol.Required("preferences"): dict,
    }
)
@websocket_api.async_response
async def handle_preferences_update(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Replace the advice preferences."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return

    preferences = UserPreferences.from_dict(msg["preferences"])

    def _apply(config: StoredConfiguration) -> None:
        config.preferences = preferences

    revision = await _async_write(connection, msg, data, _apply)
    if revision is None:
        return

    await data.store.async_add_log_entry(
        LOG_EVENT_CONFIG_CHANGED,
        "Voorkeuren gewijzigd",
        "De adviesvoorkeuren zijn bijgewerkt.",
        subject=_SUBJECT_PREFERENCES,
    )
    _send_write_result(
        connection, msg, revision, preferences.to_dict(), data.store.config
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SOURCES_CREATE,
        vol.Required(ATTR_EXPECTED_REVISION): int,
        vol.Required("source"): _CREATE_SOURCE,
    }
)
@websocket_api.async_response
async def handle_sources_create(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add an energy source."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return

    source = EnergySource.from_dict(msg["source"])

    if (refusal := _forbidden_control_error(source)) is not None:
        connection.send_error(msg["id"], ERR_INVALID_FORMAT, refusal)
        return

    def _apply(config: StoredConfiguration) -> None:
        if any(existing.id == source.id for existing in config.sources):
            raise _CommandError(
                ERR_DUPLICATE_ID, "Er bestaat al een energiebron met dit ID."
            )
        config.sources.append(source)

    revision = await _async_write(connection, msg, data, _apply)
    if revision is None:
        return

    await data.store.async_add_log_entry(
        LOG_EVENT_CONFIG_CHANGED,
        "Energiebron toegevoegd",
        f"De energiebron '{source.name}' is toegevoegd.",
        subject=source.id,
    )
    _send_write_result(connection, msg, revision, source.to_dict(), data.store.config)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SOURCES_UPDATE,
        vol.Required(ATTR_EXPECTED_REVISION): int,
        vol.Required("source"): _UPDATE_SOURCE,
    }
)
@websocket_api.async_response
async def handle_sources_update(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Replace an existing energy source."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return

    source = EnergySource.from_dict(msg["source"])

    if (refusal := _forbidden_control_error(source)) is not None:
        connection.send_error(msg["id"], ERR_INVALID_FORMAT, refusal)
        return

    def _apply(config: StoredConfiguration) -> None:
        config.sources[_find(config.sources, source.id, "Deze energiebron")] = source

    revision = await _async_write(connection, msg, data, _apply)
    if revision is None:
        return

    await data.store.async_add_log_entry(
        LOG_EVENT_CONFIG_CHANGED,
        "Energiebron gewijzigd",
        f"De energiebron '{source.name}' is bijgewerkt.",
        subject=source.id,
    )
    _send_write_result(connection, msg, revision, source.to_dict(), data.store.config)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_SOURCES_DELETE,
        vol.Required(ATTR_EXPECTED_REVISION): int,
        vol.Required("source_id"): str,
    }
)
@websocket_api.async_response
async def handle_sources_delete(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete an energy source."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return

    source_id = msg["source_id"]
    removed: list[EnergySource] = []

    def _apply(config: StoredConfiguration) -> None:
        index = _find(config.sources, source_id, "Deze energiebron")
        removed.append(config.sources.pop(index))

    revision = await _async_write(connection, msg, data, _apply)
    if revision is None:
        return

    await data.store.async_add_log_entry(
        LOG_EVENT_CONFIG_CHANGED,
        "Energiebron verwijderd",
        f"De energiebron '{removed[0].name}' is verwijderd.",
        subject=source_id,
    )
    _send_write_result(connection, msg, revision, None, data.store.config)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_DEVICES_CREATE,
        vol.Required(ATTR_EXPECTED_REVISION): int,
        vol.Required("device"): _CREATE_DEVICE,
    }
)
@websocket_api.async_response
async def handle_devices_create(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Add an appliance."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return

    device = DeviceProfile.from_dict(msg["device"])

    if (refusal := _forbidden_control_error(device)) is not None:
        connection.send_error(msg["id"], ERR_INVALID_FORMAT, refusal)
        return

    def _apply(config: StoredConfiguration) -> None:
        if any(existing.id == device.id for existing in config.devices):
            raise _CommandError(
                ERR_DUPLICATE_ID, "Er bestaat al een apparaat met dit ID."
            )
        config.devices.append(device)

    revision = await _async_write(connection, msg, data, _apply)
    if revision is None:
        return

    await data.store.async_add_log_entry(
        LOG_EVENT_DEVICE_ADDED,
        "Apparaat toegevoegd",
        f"Het apparaat '{device.name}' is toegevoegd.",
        subject=device.id,
    )
    _send_write_result(connection, msg, revision, device.to_dict(), data.store.config)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_DEVICES_UPDATE,
        vol.Required(ATTR_EXPECTED_REVISION): int,
        vol.Required("device"): _UPDATE_DEVICE,
    }
)
@websocket_api.async_response
async def handle_devices_update(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Replace an existing appliance."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return

    device = DeviceProfile.from_dict(msg["device"])

    if (refusal := _forbidden_control_error(device)) is not None:
        connection.send_error(msg["id"], ERR_INVALID_FORMAT, refusal)
        return

    def _apply(config: StoredConfiguration) -> None:
        config.devices[_find(config.devices, device.id, "Dit apparaat")] = device

    revision = await _async_write(connection, msg, data, _apply)
    if revision is None:
        return

    await data.store.async_add_log_entry(
        LOG_EVENT_CONFIG_CHANGED,
        "Apparaat gewijzigd",
        f"Het apparaat '{device.name}' is bijgewerkt.",
        subject=device.id,
    )
    _send_write_result(connection, msg, revision, device.to_dict(), data.store.config)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_DEVICES_DELETE,
        vol.Required(ATTR_EXPECTED_REVISION): int,
        vol.Required("device_id"): str,
    }
)
@websocket_api.async_response
async def handle_devices_delete(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete an appliance."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return

    device_id = msg["device_id"]
    removed: list[DeviceProfile] = []

    def _apply(config: StoredConfiguration) -> None:
        index = _find(config.devices, device_id, "Dit apparaat")
        removed.append(config.devices.pop(index))

    revision = await _async_write(connection, msg, data, _apply)
    if revision is None:
        return

    await data.store.async_add_log_entry(
        LOG_EVENT_DEVICE_REMOVED,
        "Apparaat verwijderd",
        f"Het apparaat '{removed[0].name}' is verwijderd.",
        subject=device_id,
    )
    _send_write_result(connection, msg, revision, None, data.store.config)


# **Deliberately not require_admin** (SPEC.md §33.9, §33.10). This is the
# resident saying what his own appliance should do: when it must be finished, on
# which days, whether it may make noise, and whether it may be steered at all.
#
# It is the counterpart of `devices/update`, which stays admin-only and has no
# field filter — a resident calling that one could overwrite `nominal_power_w`,
# the entity links and `control_forbidden`, and an agreement would disappear
# with a click. The safety here is the allow-list in `_SET_OPERATION`, not the
# caller's role.
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_DEVICES_SET_OPERATION,
        vol.Required(ATTR_EXPECTED_REVISION): int,
        vol.Required("device_id"): str,
        vol.Required("operation"): _SET_OPERATION,
    }
)
@websocket_api.async_response
async def handle_devices_set_operation(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Change the operating fields a resident owns on one appliance."""
    if (data := _async_get_data(hass, connection, msg)) is None:
        return

    device_id = msg["device_id"]
    operation = msg["operation"]
    updated: list[DeviceProfile] = []

    def _apply(config: StoredConfiguration) -> None:
        index = _find(config.devices, device_id, "Dit apparaat")
        stored = config.devices[index]

        # A quarantined row is not something anyone operates. Refusing here also
        # keeps derived state out of the file: `from_dict` disables an unknown
        # type on the way in, and a merge-and-store would write that derivation
        # back, which SPEC.md §13 forbids.
        if stored.invalid_reason is not None:
            raise _CommandError(
                ERR_INVALID_FORMAT,
                "Dit apparaat heeft een onbekend type en is buiten werking gesteld.",
            )

        # Merged rather than replaced: the caller sends only the fields it owns,
        # and everything else on the row is the installer's and must survive
        # untouched. Going back through from_dict keeps the coercion — time
        # normalisation, the day list, the type defaults — in the one place that
        # already does it.
        merged = DeviceProfile.from_dict({**stored.to_dict(), **operation})

        # The installer's veto, and the first time it actually carries weight:
        # until now only an admin could set `control_mode`, and an admin also
        # sets `control_forbidden` (SPEC.md §33.11).
        if (refusal := _forbidden_control_error(merged)) is not None:
            raise _CommandError(ERR_INVALID_FORMAT, refusal)

        config.devices[index] = merged
        updated.append(merged)

    revision = await _async_write(connection, msg, data, _apply)
    if revision is None:
        return

    device = updated[0]
    await data.store.async_add_log_entry(
        LOG_EVENT_CONFIG_CHANGED,
        "Bediening gewijzigd",
        f"De instellingen van '{device.name}' zijn bijgewerkt.",
        subject=device.id,
    )
    _send_write_result(connection, msg, revision, device.to_dict(), data.store.config)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_LOGS_CLEAR,
        vol.Required(ATTR_EXPECTED_REVISION): int,
    }
)
@websocket_api.async_response
async def handle_logs_clear(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Empty the logbook.

    Guarded by ``expected_revision`` like every other write, but it does not
    consume one: the logbook is not part of the configuration the revision
    counts (SPEC.md §13), so the answer carries the unchanged revision.
    """
    if (data := _async_get_data(hass, connection, msg)) is None:
        return

    store = data.store
    if msg[ATTR_EXPECTED_REVISION] != store.revision:
        _send_revision_conflict(connection, msg, data)
        return

    await store.async_clear_logs()
    _send_write_result(connection, msg, store.revision, None, store.config)
