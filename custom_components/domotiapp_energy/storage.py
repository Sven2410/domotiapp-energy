"""Persistent storage for the DomotiApp Energy configuration (SPEC.md §13).

The store owns the single source of truth for the extended configuration: the
home profile, energy sources, device profiles, preferences and the logbook.
Only the home name is duplicated in the config entry.

Two invariants make concurrent writes safe:

* every write runs under an ``asyncio.Lock``, so writes are serialised;
* every successful write increments ``revision`` by one. A caller that passes
  a stale ``expected_revision`` is rejected with :class:`RevisionConflictError`
  and can reload before retrying (optimistic concurrency, SPEC.md §14).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    LOG_DEDUPE_WINDOW_MINUTES,
    MAX_LOG_ENTRIES,
    SEVERITY_INFO,
    STORAGE_KEY,
    STORAGE_MINOR_VERSION,
    STORAGE_VERSION,
)
from .models import LogEntry, StoredConfiguration

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

    async def async_load(self) -> StoredConfiguration:
        """Load the configuration, falling back to safe defaults.

        A missing file yields a default configuration. A file that cannot be
        parsed is reported and also yields defaults, so a damaged install still
        starts instead of blocking Home Assistant.
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
        return self._config

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
    ) -> int:
        """Add a logbook event and return the new revision.

        Consecutive identical events (same type and same subject) within
        ``LOG_DEDUPE_WINDOW_MINUTES`` bump the ``count`` of the newest entry
        instead of adding a line, which keeps the logbook readable when a
        recalculation runs repeatedly (SPEC.md §8).
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

        return await self.async_update(_mutate)

    async def async_clear_logs(self) -> int:
        """Empty the logbook and return the new revision."""

        def _mutate(config: StoredConfiguration) -> None:
            config.logs.clear()

        return await self.async_update(_mutate)

    async def async_remove(self) -> None:
        """Delete the stored configuration file and drop the cache."""
        await self._store.async_remove()
        self._config = None

    async def _async_write(self) -> int:
        """Write the cached configuration. The caller must hold the lock."""
        config = self.config
        config.revision += 1
        # Guard the limit here too: a caller may have appended logs directly.
        del config.logs[MAX_LOG_ENTRIES:]

        try:
            await self._store.async_save(config.to_dict())
        except (OSError, HomeAssistantError) as err:
            # Keep the in-memory revision in step with what is on disk, so a
            # retry does not skip a number and trip the conflict check.
            config.revision -= 1
            raise StorageError(f"Could not write {STORAGE_KEY}") from err

        return config.revision
