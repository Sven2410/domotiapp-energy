"""Persistent storage for the DomotiApp Energy configuration (SPEC.md §13).

The store owns the single source of truth for the extended configuration: the
home profile, energy sources, device profiles, preferences and the logbook.
Only the home name is duplicated in the config entry.

Three invariants make concurrent writes safe:

* every write runs under an ``asyncio.Lock``, so writes are serialised;
* every successful configuration change increments ``revision`` by one. A
  caller that passes a stale ``expected_revision`` is rejected with
  :class:`RevisionConflictError` and can reload before retrying (optimistic
  concurrency, SPEC.md §14);
* the revision changes only through an explicit user action. Loading writes
  nothing, and a logbook entry is persisted without touching the revision.
  Otherwise a background event between opening a form and saving it would
  expire the frontend's ``expected_revision`` and reject a valid save.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Sequence
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DUPLICATE_SUBJECT_PREFIX,
    INVALID_REASON_DUPLICATE_SOURCE,
    LOG_DEDUPE_WINDOW_MINUTES,
    LOG_EVENT_INVALID_CONFIGURATION,
    LOG_EVENT_INVALID_MEASUREMENT,
    LOG_EVENT_SOURCE_UNAVAILABLE,
    MAX_LOG_ENTRIES,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    STORAGE_KEY,
    STORAGE_MINOR_VERSION,
    STORAGE_VERSION,
)
from .models import LogEntry, SourceFailure, StoredConfiguration

_LOGGER = logging.getLogger(__name__)


class StorageError(HomeAssistantError):
    """Raised when the configuration could not be read or written."""


class RevisionConflictError(StorageError):
    """Raised when a write is based on a revision that is no longer current."""

    def __init__(self, expected: int, actual: int) -> None:
        """Store both revisions so the caller can report them."""
        super().__init__(
            f"Configuration was modified: expected revision {expected}, "
            f"current revision is {actual}"
        )
        self.expected = expected
        self.actual = actual


class DomotiAppEnergyStore(Store[dict[str, Any]]):
    """Versioned store with an explicit migration path."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Migrate stored data to the current schema version.

        Home Assistant only calls this when the stored version differs from the
        current one. Version 1.1 is the first published schema, so there is
        nothing to convert yet; the branch structure is in place so a future
        schema change only has to be added here.
        """
        if old_major_version > STORAGE_VERSION:
            # Written by a newer release. Refusing is safer than dropping
            # fields we do not understand; Home Assistant re-raises this for a
            # major mismatch and the integration fails to set up with a clear
            # message instead of silently discarding the configuration.
            raise NotImplementedError(
                f"Cannot downgrade {STORAGE_KEY} from schema version "
                f"{old_major_version}.{old_minor_version}"
            )

        # Every schema change so far has been additive, and
        # StoredConfiguration.from_dict() fills in defaults for anything the
        # older payload does not contain.
        _LOGGER.debug(
            "Migrating %s from schema %s.%s to %s.%s",
            STORAGE_KEY,
            old_major_version,
            old_minor_version,
            STORAGE_VERSION,
            STORAGE_MINOR_VERSION,
        )
        return old_data


class ConfigurationStore:
    """Loads, caches and writes the DomotiApp Energy configuration."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the store without touching the filesystem yet."""
        self._store = DomotiAppEnergyStore(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
            minor_version=STORAGE_MINOR_VERSION,
        )
        self._lock = asyncio.Lock()
        self._config: StoredConfiguration | None = None
        # Called after every configuration change, so the coordinator can
        # rebuild its state listener over the newly linked entities without
        # every writer having to remember to tell it (SPEC.md §18).
        self._change_listeners: list[Callable[[], None]] = []
        # Subject id -> the invalid reason already reported for it. Purely in
        # memory: after a restart every quarantined row is reported once more,
        # which is what an installer reading a fresh log expects.
        self._reported_invalid: dict[str, str] = {}

    @property
    def config(self) -> StoredConfiguration:
        """Return the cached configuration.

        Raises:
            StorageError: when called before :meth:`async_load`.
        """
        if self._config is None:
            raise StorageError("Configuration accessed before it was loaded")
        return self._config

    @property
    def revision(self) -> int:
        """Return the revision of the cached configuration."""
        return self.config.revision

    @property
    def loaded(self) -> bool:
        """Return whether the configuration has been loaded."""
        return self._config is not None

    def add_change_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to configuration changes and return the unsubscribe.

        The listener runs after a change has been written successfully, and
        only for a change to the configuration itself. A logbook write is not a
        configuration change and never triggers it, for the same reason it does
        not consume a revision (SPEC.md §13).
        """
        self._change_listeners.append(listener)

        def _unsubscribe() -> None:
            if listener in self._change_listeners:
                self._change_listeners.remove(listener)

        return _unsubscribe

    async def async_load(self) -> StoredConfiguration:
        """Load the configuration, falling back to safe defaults.

        A missing file yields a default configuration. A file that cannot be
        parsed is reported and also yields defaults, so a damaged install still
        starts instead of blocking Home Assistant.

        Loading performs no write of any kind. The quarantine of a row with an
        unrecognised type is derived from the stored type on every access
        (``EnergySource.invalid_reason``), so there is nothing to repair and
        nothing to persist; the revision survives the load untouched.
        Quarantined rows are reported by :meth:`async_report_invalid_rows`.
        """
        try:
            raw = await self._store.async_load()
        except (ValueError, HomeAssistantError):
            # The stored JSON is unreadable. Log without any of its content:
            # the file may contain the home name (SPEC.md §21).
            _LOGGER.exception(
                "Could not read %s, continuing with a default configuration",
                STORAGE_KEY,
            )
            raw = None

        self._config = StoredConfiguration.from_dict(raw)
        self._reported_invalid.clear()
        return self._config

    async def async_report_invalid_rows(
        self, failures: Sequence[SourceFailure] = ()
    ) -> None:
        """Report every row the engine refuses to use, and every failed read.

        Call this where the problems become functionally relevant: at the
        moment the engine has read the configuration to calculate with it. A
        source or device with an unrecognised type stays in the list but is
        disabled and marked invalid (SPEC.md §12); a source whose entity could
        not be read is passed in as a :class:`SourceFailure`. Without a visible
        warning the installer would only notice either through a silently lower
        data quality score.

        Both kinds share one anti-spam ledger, and they have to: each subject
        is reported once per reason, so a recalculation every few seconds does
        not repeat itself, and a source that is repaired and later breaks again
        is reported afresh. Splitting the ledger over two methods would make
        each of them forget the other's subjects on every pass.
        """
        config = self.config
        still_invalid: set[str] = set()

        for source_type, rows in config.duplicate_exclusive_sources.items():
            # Reported per type rather than per row: the problem is that there
            # are several, not that any single one is wrong.
            subject = f"{DUPLICATE_SUBJECT_PREFIX}{source_type}"
            still_invalid.add(subject)
            if not self._mark_reported(subject, INVALID_REASON_DUPLICATE_SOURCE):
                continue
            _LOGGER.warning(
                "Multiple enabled sources of type %r; none of them is used",
                source_type,
            )
            await self.async_add_log_entry(
                LOG_EVENT_INVALID_CONFIGURATION,
                "Meerdere bronnen van hetzelfde type",
                f"Er zijn {len(rows)} ingeschakelde bronnen van het type "
                f"'{source_type}'. Deze waarden zijn niet op te tellen en er is "
                f"niet te bepalen welke de juiste is, dus geen van beide wordt "
                f"gebruikt. Schakel er één uit of verwijder er één.",
                severity=SEVERITY_WARNING,
                subject=subject,
            )

        for source in config.invalid_sources:
            still_invalid.add(source.id)
            if not self._mark_reported(source.id, source.invalid_reason):
                continue
            # No home name, location or entity state in the Home Assistant log
            # (SPEC.md §21); the readable detail goes to the in-app logbook.
            _LOGGER.warning(
                "Energy source %s has unrecognised type %r and is disabled",
                source.id,
                source.type,
            )
            await self.async_add_log_entry(
                LOG_EVENT_INVALID_CONFIGURATION,
                "Onbekend brontype",
                f"De energiebron '{source.name}' heeft een onbekend type "
                f"('{source.type}') en is uitgeschakeld. Kies een geldig type "
                f"om de bron weer te gebruiken.",
                severity=SEVERITY_WARNING,
                subject=source.id,
            )

        for device in config.invalid_devices:
            still_invalid.add(device.id)
            if not self._mark_reported(device.id, device.invalid_reason):
                continue
            _LOGGER.warning(
                "Device profile %s has unrecognised type %r and is disabled",
                device.id,
                device.device_type,
            )
            await self.async_add_log_entry(
                LOG_EVENT_INVALID_CONFIGURATION,
                "Onbekend apparaattype",
                f"Het apparaat '{device.name}' heeft een onbekend type "
                f"('{device.device_type}') en is uitgeschakeld. Kies een geldig "
                f"type om het apparaat weer te gebruiken.",
                severity=SEVERITY_WARNING,
                subject=device.id,
            )

        await self._async_report_failures(failures, still_invalid)

        # Forget rows that are valid again, so a relapse is reported once more.
        for subject in self._reported_invalid.keys() - still_invalid:
            del self._reported_invalid[subject]

    async def _async_report_failures(
        self, failures: Sequence[SourceFailure], still_invalid: set[str]
    ) -> None:
        """Report the sources whose entity could not be read (SPEC.md §8).

        Two events, because they ask for different things from the installer:
        ``source_unavailable`` when the entity is gone or carries no value at
        all — usually another integration's problem — and
        ``invalid_measurement`` when it is there and reporting something this
        source cannot use, which is normally the unit, the value source or the
        attribute being wrong.
        """
        for failure in failures:
            subject = failure.source_id
            still_invalid.add(subject)

            event_type = (
                LOG_EVENT_SOURCE_UNAVAILABLE
                if failure.unavailable
                else LOG_EVENT_INVALID_MEASUREMENT
            )
            # The reason is part of the key, so a source that goes from
            # unavailable to unreadable is reported again rather than silently
            # keeping the older description.
            if not self._mark_reported(subject, f"{event_type}:{failure.reason_code}"):
                continue

            # The Home Assistant log gets the ids and the reason only: no source
            # name and no state (SPEC.md §21). The readable version, still
            # without the raw state, goes to the in-app logbook.
            _LOGGER.warning(
                "Energy source %s could not be read from %s (%s)",
                failure.source_id,
                failure.entity_id,
                failure.reason_code,
            )

            name = self._source_name(failure.source_id)
            if failure.unavailable:
                title = "Bron niet beschikbaar"
                message = (
                    f"De energiebron '{name}' kon niet worden uitgelezen: de "
                    f"entiteit '{failure.entity_id}' bestaat niet of levert op dit "
                    f"moment geen waarde. (reden: {failure.reason_code})"
                )
            else:
                title = "Ongeldige meting"
                message = (
                    f"De energiebron '{name}' leverde geen bruikbare meetwaarde. "
                    f"Controleer bij de entiteit '{failure.entity_id}' de gekozen "
                    f"waardebron, het attribuut en de eenheid. "
                    f"(reden: {failure.reason_code})"
                )

            await self.async_add_log_entry(
                event_type,
                title,
                message,
                severity=SEVERITY_WARNING,
                subject=subject,
            )

    def _source_name(self, source_id: str) -> str:
        """Return the configured name of a source, or its id as a fallback."""
        for source in self.config.sources:
            if source.id == source_id:
                return source.name or source_id
        return source_id

    def _mark_reported(self, subject: str, reason: str | None) -> bool:
        """Return whether this subject still has to be reported for this reason.

        Records the reason as reported on the way out, so the caller only has
        to act on a ``True``.
        """
        if reason is None or self._reported_invalid.get(subject) == reason:
            return False
        self._reported_invalid[subject] = reason
        return True

    async def async_update(
        self,
        mutate: Callable[[StoredConfiguration], None],
        *,
        expected_revision: int | None = None,
    ) -> int:
        """Apply a change under the write lock and return the new revision.

        Args:
            mutate: Called with the live configuration; any change it makes is
                persisted. It must not perform I/O.
            expected_revision: The revision the caller based its change on.
                ``None`` skips the check, which is only appropriate for writes
                that did not originate from the frontend.

        Raises:
            RevisionConflictError: when ``expected_revision`` is stale.
            StorageError: when the configuration was not loaded, or the write
                failed.
        """
        async with self._lock:
            config = self.config
            if expected_revision is not None and expected_revision != config.revision:
                raise RevisionConflictError(expected_revision, config.revision)

            mutate(config)
            return await self._async_write()

    async def async_add_log_entry(
        self,
        event_type: str,
        title: str,
        message: str,
        *,
        severity: str = SEVERITY_INFO,
        subject: str | None = None,
    ) -> None:
        """Add a logbook event.

        Consecutive identical events (same type and same subject) within
        ``LOG_DEDUPE_WINDOW_MINUTES`` bump the ``count`` of the newest entry
        instead of adding a line, which keeps the logbook readable when a
        recalculation runs repeatedly (SPEC.md §8).

        The logbook is persisted but is not part of what ``expected_revision``
        guards, so writing an entry leaves the revision alone: most events come
        from the engine, not from the user.
        """

        def _mutate(config: StoredConfiguration) -> None:
            now = dt_util.utcnow()
            window = timedelta(minutes=LOG_DEDUPE_WINDOW_MINUTES)
            newest = config.logs[0] if config.logs else None

            if (
                newest is not None
                and newest.event_type == event_type
                and newest.subject == subject
                and now - newest.timestamp <= window
            ):
                newest.count += 1
                newest.timestamp = now
                newest.title = title
                newest.message = message
                newest.severity = severity
                return

            config.logs.insert(
                0,
                LogEntry(
                    timestamp=now,
                    event_type=event_type,
                    title=title,
                    message=message,
                    severity=severity,
                    subject=subject,
                ),
            )
            # Logs are newest first, so trimming the tail drops the oldest.
            del config.logs[MAX_LOG_ENTRIES:]

        await self._async_write_logs(_mutate)

    async def async_clear_logs(self) -> None:
        """Empty the logbook."""

        def _mutate(config: StoredConfiguration) -> None:
            config.logs.clear()

        await self._async_write_logs(_mutate)

    async def _async_write_logs(
        self, mutate: Callable[[StoredConfiguration], None]
    ) -> None:
        """Persist a logbook change under the lock, without a new revision."""
        async with self._lock:
            mutate(self.config)
            await self._async_write(bump_revision=False)

    async def async_remove(self) -> None:
        """Delete the stored configuration file and drop the cache."""
        await self._store.async_remove()
        self._config = None

    async def _async_write(self, *, bump_revision: bool = True) -> int:
        """Write the cached configuration. The caller must hold the lock.

        Args:
            bump_revision: Whether this write is a configuration change. Only
                a change the user asked for consumes a revision number; a
                logbook write passes ``False``.
        """
        config = self.config
        if bump_revision:
            config.revision += 1
        # Guard the limit here too: a caller may have appended logs directly.
        del config.logs[MAX_LOG_ENTRIES:]

        try:
            await self._store.async_save(config.to_dict())
        except (OSError, HomeAssistantError) as err:
            # Keep the in-memory revision in step with what is on disk, so a
            # retry does not skip a number and trip the conflict check.
            if bump_revision:
                config.revision -= 1
            raise StorageError(f"Could not write {STORAGE_KEY}") from err

        if bump_revision:
            self._notify_change()
        return config.revision

    def _notify_change(self) -> None:
        """Tell the subscribers that the configuration itself changed.

        Runs while the write lock is held, so a listener must return
        immediately and must never call back into the store; the coordinator's
        listener only rebuilds its subscriptions and schedules a recalculation.
        """
        for listener in list(self._change_listeners):
            listener()
