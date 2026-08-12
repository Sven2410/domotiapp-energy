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
from collections.abc import Set as AbstractSet
from datetime import timedelta
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DUPLICATE_SUBJECT_PREFIX,
    INVALID_REASON_DUPLICATE_SOURCE,
    LOG_DEDUPE_WINDOW_MINUTES,
    LOG_EVENT_INVALID_CONFIGURATION,
    LOG_EVENT_INVALID_MEASUREMENT,
    LOG_EVENT_SOURCE_UNAVAILABLE,
    LOG_FLUSH_INTERVAL_SECONDS,
    MAX_LOG_ENTRIES,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    SOURCE_FAILURE_LOG_EVENTS,
    STORAGE_KEY,
    STORAGE_MINOR_VERSION,
    STORAGE_VERSION,
)
from .engine.reason_codes import (
    REASON_ENTITY_MISSING,
    REASON_ENTITY_STALE,
    REASON_ENTITY_UNAVAILABLE,
    REASON_ENTITY_WITHOUT_VALUE,
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
        self._hass = hass
        self._store = DomotiAppEnergyStore(
            hass,
            STORAGE_VERSION,
            STORAGE_KEY,
            minor_version=STORAGE_MINOR_VERSION,
        )
        self._lock = asyncio.Lock()
        self._config: StoredConfiguration | None = None
        # A bumped log counter that is in memory but not yet on disk, plus the
        # single timer that will put it there. Together they cap the logbook at
        # one write per LOG_FLUSH_INTERVAL_SECONDS; see the constant for why.
        self._logs_pending = False
        self._cancel_log_flush: CALLBACK_TYPE | None = None
        self._unsub_final_write: CALLBACK_TYPE | None = None
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
        self,
        failures: Sequence[SourceFailure] = (),
        *,
        still_failing: AbstractSet[str] = frozenset(),
        readable: AbstractSet[str] = frozenset(),
    ) -> None:
        """Report every row the engine refuses to use, and every failed read.

        Three collections, because the caller knows three different things and
        this method must not re-derive any of them (SPEC.md §63.6):

        ``failures`` are the ones worth a logbook line. ``still_failing`` is
        every subject that failed, **including the ones the coordinator chose
        not to report** — without it a silenced failure is indistinguishable
        from a repair, which is the 0.28.0 regression this fixes. ``readable``
        is every source that produced a usable value on this pass, and it is
        what closes an open entry.

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
        # Seeded with everything that is still broken, reported or not. A
        # failure the coordinator silenced is still a failure; leaving it out
        # here made the forget loop below read "silent" as "repaired" (0.28.0).
        still_invalid: set[str] = set(still_failing)

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

        await self._async_close_resolved_entries(readable)

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

        **Whether a failure gets here at all is not decided here.** The
        coordinator holds the single predicate for that (SPEC.md §63.5); this
        method phrases and writes whatever it is handed. Every reason code
        therefore has whole words of its own, including the two the coordinator
        normally filters out: a mapping with a hole would put the wrong sentence
        under the right event the first time the two disagree.
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
            if failure.reason_code == REASON_ENTITY_UNAVAILABLE:
                # **Its own whole sentence, not the old one with a word swapped.**
                # This says what another integration decided, and the action that
                # follows is to look at that integration — not at our source row.
                title = "Bron niet bereikbaar"
                message = (
                    f"De energiebron '{name}' was niet bereikbaar. De integratie "
                    f"achter '{failure.entity_id}' meldde de entiteit als niet "
                    f"beschikbaar, dus er was geen meting."
                )
            elif failure.reason_code == REASON_ENTITY_STALE:
                title = "Bron is stilgevallen"
                message = (
                    f"De energiebron '{name}' was stilgevallen. De entiteit "
                    f"'{failure.entity_id}' bestond nog en meldde geen storing, maar "
                    f"had te lang geen nieuwe waarde gerapporteerd om nog als een "
                    f"meting te gelden."
                )
            elif failure.reason_code == REASON_ENTITY_MISSING:
                title = "Bron niet gevonden"
                message = (
                    f"De energiebron '{name}' verwijst naar de entiteit "
                    f"'{failure.entity_id}', en die bestaat niet in deze Home "
                    f"Assistant. Controleer of de entiteit hernoemd of verwijderd is."
                )
            elif failure.reason_code == REASON_ENTITY_WITHOUT_VALUE:
                title = "Bron heeft nog geen waarde"
                message = (
                    f"De energiebron '{name}' is gekoppeld aan '{failure.entity_id}', "
                    f"en die entiteit bestond wel maar droeg geen meetwaarde."
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

    async def _async_close_resolved_entries(self, readable: AbstractSet[str]) -> None:
        """Record that the situation an open entry describes is over.

        **Not driven by the anti-spam ledger, and that is the whole point**
        (SPEC.md §63.6). The ledger lives in memory, so a restart while a source
        is down would leave its entry open for good — a logbook that lies in a
        new way instead of the old one. This hangs on the event itself: a source
        that reads cleanly closes its newest open entry, whether or not this
        process saw that entry being written.

        Only the newest open entry per subject, because an older one describes
        an earlier episode that had its own end, recorded or not.
        """
        if not readable:
            return

        closed = False
        now = dt_util.utcnow()
        seen: set[str] = set()
        for entry in self.config.logs:
            subject = entry.subject
            if (
                subject is None
                or subject in seen
                or subject not in readable
                or entry.resolved_at is not None
                or entry.event_type not in SOURCE_FAILURE_LOG_EVENTS
            ):
                continue
            # Newest first, so the first match per subject is the current one.
            seen.add(subject)
            entry.resolved_at = now
            closed = True

        if closed:
            async with self._lock:
                await self._async_write(bump_revision=False)

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

        **A collapsed repeat does not reach the disk right away.** Bumping a
        counter used to rewrite the whole storage file, and the engine bumps the
        same counter on every recalculation — with a real meter that is a write
        every couple of seconds, all day. The bump is applied in memory and
        flushed at most once per ``LOG_FLUSH_INTERVAL_SECONDS``; a genuinely new
        line is still written immediately.
        """
        async with self._lock:
            if self._collapse_into_recent(
                event_type, title, message, severity, subject
            ):
                self._schedule_log_flush()
                return

            self.config.logs.insert(
                0,
                LogEntry(
                    timestamp=dt_util.utcnow(),
                    event_type=event_type,
                    title=title,
                    message=message,
                    severity=severity,
                    subject=subject,
                ),
            )
            # Logs are newest first, so trimming the tail drops the oldest.
            del self.config.logs[MAX_LOG_ENTRIES:]
            await self._async_write(bump_revision=False)

    def _collapse_into_recent(
        self,
        event_type: str,
        title: str,
        message: str,
        severity: str,
        subject: str | None,
    ) -> bool:
        """Fold this event into a recent matching entry, or report it as new.

        The caller must hold the lock. Returning ``True`` means nothing has to
        be written now: the change is a counter and a timestamp on a line that
        is already on disk.

        **The whole window is searched, not just the newest line.** Looking only
        at ``logs[0]`` collapses a repeat and nothing else, and the engine does
        not repeat itself one subject at a time: on a sunny afternoon under load
        it reports a peak risk and a solar surplus in the same pass, so each one
        found the *other* at the front and wrote a new line. Two lines per
        recalculation, for as long as both situations lasted — the write
        amplification this collapsing exists to prevent, hiding behind the very
        rule meant to stop it. Measured against a live instance, not found by
        the unit test that only ever sent one kind of event.

        The matched entry moves back to the front, so the list stays ordered
        newest-first and trimming still drops the oldest.
        """
        now = dt_util.utcnow()
        window = timedelta(minutes=LOG_DEDUPE_WINDOW_MINUTES)
        logs = self.config.logs

        for index, entry in enumerate(logs):
            if now - entry.timestamp > window:
                # Ordered newest-first, so everything beyond here is older.
                return False
            if entry.event_type != event_type or entry.subject != subject:
                continue

            entry.count += 1
            entry.timestamp = now
            entry.title = title
            entry.message = message
            entry.severity = severity
            # **A closed entry that happens again re-opens** (SPEC.md §63.6).
            # The first design forbade collapsing into a resolved entry, so its
            # recorded end could not be erased — and that turned a source
            # flickering every minute into one entry per cycle, which is exactly
            # the write amplification this collapsing exists to prevent. Inside
            # the window it is one situation with a counter, and the end of its
            # previous occurrence is not worth a line per flicker. Beyond the
            # window it is a new entry anyway, so last night's ending survives.
            entry.resolved_at = None
            if index:
                logs.insert(0, logs.pop(index))
            return True

        return False

    @callback
    def _schedule_log_flush(self) -> None:
        """Make sure the pending counter reaches the disk before long.

        One timer at a time: further bumps ride along on the flush that is
        already scheduled, so the interval is a hard ceiling on the write rate
        rather than a delay that keeps being pushed forward. The final-write
        listener covers a shutdown inside the interval.
        """
        self._logs_pending = True
        if self._cancel_log_flush is None:
            self._cancel_log_flush = async_call_later(
                self._hass, LOG_FLUSH_INTERVAL_SECONDS, self._async_flush_log_timer
            )
        if self._unsub_final_write is None:
            self._unsub_final_write = self._hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_FINAL_WRITE, self._async_flush_on_stop
            )

    async def _async_flush_log_timer(self, _now: Any) -> None:
        """Write the pending logbook change; called by the flush timer."""
        self._cancel_log_flush = None
        await self.async_flush_logs()

    async def _async_flush_on_stop(self, _event: Event) -> None:
        """Write the pending logbook change before Home Assistant stops."""
        self._unsub_final_write = None
        await self.async_flush_logs()

    async def async_flush_logs(self) -> None:
        """Persist a pending logbook change, if there is one.

        Public because unloading the entry has to call it: a reload halfway
        through the interval would otherwise drop the counter.
        """
        async with self._lock:
            if not self._logs_pending or self._config is None:
                return
            await self._async_write(bump_revision=False)

    @callback
    def _cancel_pending_log_flush(self) -> None:
        """Drop the flush timer and its listener; every write clears them."""
        self._logs_pending = False
        if self._cancel_log_flush is not None:
            self._cancel_log_flush()
            self._cancel_log_flush = None
        if self._unsub_final_write is not None:
            self._unsub_final_write()
            self._unsub_final_write = None

    async def async_clear_logs(self) -> None:
        """Empty the logbook."""
        async with self._lock:
            self.config.logs.clear()
            await self._async_write(bump_revision=False)

    async def async_remove(self) -> None:
        """Delete the stored configuration file and drop the cache."""
        self._cancel_pending_log_flush()
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

        # Whatever the reason for this write, it puts the whole configuration on
        # disk — including any counter that was still only in memory. Clearing
        # the timer here is what keeps a busy configuration from also paying for
        # a logbook flush a moment later.
        self._cancel_pending_log_flush()

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
