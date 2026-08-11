"""The ready flags, which are state and not configuration (SPEC.md §32.5).

A dishwasher starts when the door closes, and nothing in this system knows
whether there is anything in it. The flag is the resident saying there is:
*"hij is vol"*. It goes out again by itself when the programme finishes.

**Why this is a second store and not three lines in the configuration.** That
"by itself" is the whole reason. A flag that clears on its own is a write
nobody asked for, and every write to the configuration raises the revision —
after which the `expected_revision` of a form somebody has open expires and a
perfectly valid save is refused with `revision_conflict` (SPEC.md §13). A
dishwasher that runs twice a day would do that twice a day. That is the defect
round A opened the forms on, and it is the same rule that keeps the derived
observations of §59.3 out of storage.

So this store carries **no revision** and takes no `expected_revision`. It is
written straight through: two to four writes per appliance per day are
negligible, and unlike the logbook they do not need a deferred flush.

The stored shape is deliberately the smallest thing that answers the question::

    { "ready": { "<device_id>": "<iso timestamp>" } }

The timestamp is when the resident said it, because the *expiry* is computed
from it — a shelf life on an intention rather than a claim about the machine.
An appliance whose id is absent has no flag, which is the ordinary state.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    MINUTES_PER_DAY,
    READY_FLAG_MAX_AGE_HOURS,
    RUNTIME_STORAGE_KEY,
    RUNTIME_STORAGE_VERSION,
)
from .models import DeviceProfile, minutes_since_midnight

_LOGGER = logging.getLogger(__name__)

_KEY_READY = "ready"


class RuntimeStore:
    """Holds the ready flags and the moment each of them was set."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Set up the store without touching the filesystem yet."""
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass, RUNTIME_STORAGE_VERSION, RUNTIME_STORAGE_KEY
        )
        self._lock = asyncio.Lock()
        self._ready: dict[str, datetime] = {}

    async def async_load(self) -> None:
        """Read the flags from disk, writing nothing.

        Same rule as the configuration store: loading never writes. An entry
        whose timestamp cannot be parsed is dropped rather than repaired —
        there is no honest way to guess when somebody said their machine was
        full, and a flag with an unknown age cannot be expired.
        """
        data = await self._store.async_load() or {}
        stored = data.get(_KEY_READY)
        loaded: dict[str, datetime] = {}
        if isinstance(stored, dict):
            for device_id, raw in stored.items():
                moment = dt_util.parse_datetime(str(raw))
                if moment is None:
                    _LOGGER.warning(
                        "Dropping ready flag for %r: %r is not a timestamp",
                        device_id,
                        raw,
                    )
                    continue
                loaded[str(device_id)] = dt_util.as_utc(moment)
        self._ready = loaded

    def set_at(self, device_id: str) -> datetime | None:
        """Return when the flag for this appliance was set, or None."""
        return self._ready.get(device_id)

    def is_ready(self, device: DeviceProfile, now: datetime | None = None) -> bool:
        """Return whether this appliance is currently flagged as having work.

        **An expired flag is not set**, and that is decided here rather than by
        a timer that clears it. A timer would mean the answer depends on
        whether something ran; this way "hij is vol van vanochtend" simply
        stops being true at the moment it stops being true, however long Home
        Assistant was off in between.
        """
        moment = self._ready.get(device.id)
        if moment is None:
            return False
        asked_at = dt_util.utcnow() if now is None else now
        return asked_at < expires_at(device, moment)

    async def async_set_ready(self, device_id: str, ready: bool) -> datetime | None:
        """Set or clear the flag, and return when it was set.

        Returns ``None`` when the flag was cleared, so a caller can phrase the
        answer without asking a second question.
        """
        async with self._lock:
            if ready:
                self._ready[device_id] = dt_util.utcnow()
            else:
                self._ready.pop(device_id, None)
            await self._async_save()
            return self._ready.get(device_id)

    async def async_forget(self, device_ids: set[str]) -> None:
        """Drop flags for appliances that no longer exist.

        Called after a configuration change. A flag whose appliance was deleted
        can never be cleared by the resident and never expires visibly, so it
        would sit in the file forever.
        """
        async with self._lock:
            stale = set(self._ready) - device_ids
            if not stale:
                return
            for device_id in stale:
                del self._ready[device_id]
            await self._async_save()

    async def _async_save(self) -> None:
        """Write the flags. No revision, so nothing here expires a form."""
        await self._store.async_save(
            {_KEY_READY: {k: v.isoformat() for k, v in self._ready.items()}}
        )


def expires_at(device: DeviceProfile, set_at: datetime) -> datetime:
    """Return the moment this flag stops meaning anything (SPEC.md §32.6).

    Two shelf lives, and both are statements about the *intention* rather than
    about the machine:

    - **with a ready window**, at the end of that window. Once the deadline has
      passed, "he is full" has been overtaken by events either way.
    - **without one**, twenty-four hours after it was set.

    **Not midnight**, which is exactly wrong for a household that fills the
    dishwasher late in the evening: the flag would expire before the machine
    ever ran. A day also says something more useful — if nothing has happened
    for that long, something else is wrong.
    """
    fallback = set_at + timedelta(hours=READY_FLAG_MAX_AGE_HOURS)
    finish = minutes_since_midnight(device.ready_before)
    if finish is None:
        return fallback

    local_set = dt_util.as_local(set_at)
    start_of_day = local_set.replace(hour=0, minute=0, second=0, microsecond=0)
    deadline = start_of_day + timedelta(minutes=finish)
    if deadline <= local_set:
        # The deadline for today has already gone by, so the window this flag
        # belongs to is tomorrow's. Filling the dishwasher at 22:00 for a 07:00
        # deadline is the ordinary case, not the exception.
        deadline += timedelta(minutes=MINUTES_PER_DAY)
    return dt_util.as_utc(deadline)
