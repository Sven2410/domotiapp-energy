"""Tests for the ready flags (SPEC.md §32.5 and §32.6).

The flag answers one question the engine cannot: *is there anything in it?* It
lives in its own store for a hard reason — it clears itself, and a write to the
configuration would raise the revision under an open form — so the two things
these tests care about most are that it never touches the configuration, and
that "hij is vol" stops being true at the moment it stops being true.
"""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.domotiapp_energy.const import (
    DEVICE_TYPE_DISHWASHER,
    READY_FLAG_MAX_AGE_HOURS,
    RUNTIME_STORAGE_KEY,
    STORAGE_KEY,
)
from custom_components.domotiapp_energy.models import DeviceProfile
from custom_components.domotiapp_energy.runtime_store import RuntimeStore, expires_at

TIME_ZONE = "Europe/Amsterdam"


def _device(**overrides: Any) -> DeviceProfile:
    """Return the dishwasher of §32: loaded by hand, done by 07:00."""
    data: dict[str, Any] = {
        "id": "d1",
        "name": "Vaatwasser",
        "device_type": DEVICE_TYPE_DISHWASHER,
        "ready_before": "07:00",
        "duration_minutes": 180,
    }
    return DeviceProfile.from_dict(data | overrides)


async def _loaded(hass: HomeAssistant) -> RuntimeStore:
    """Return a store that has read from disk, as setup does."""
    store = RuntimeStore(hass)
    await store.async_load()
    return store


async def test_setting_and_clearing_the_flag(hass: HomeAssistant) -> None:
    """The two things a resident can say about his machine."""
    store = await _loaded(hass)
    device = _device()

    assert store.is_ready(device) is False

    await store.async_set_ready(device.id, True)
    assert store.is_ready(device) is True

    await store.async_set_ready(device.id, False)
    assert store.is_ready(device) is False


async def test_the_flag_survives_a_restart(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Filled at 22:00, still true at 23:00 — even across a Home Assistant restart.

    The reason it is persisted at all: a resident says it once, in the kitchen,
    and the advice that uses it fires in the middle of the night.
    """
    store = await _loaded(hass)
    await store.async_set_ready("d1", True)

    assert RUNTIME_STORAGE_KEY in hass_storage

    revived = await _loaded(hass)
    assert revived.is_ready(_device()) is True


async def test_the_flag_never_touches_the_configuration(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """**The reason this store exists at all** (SPEC.md §32.5).

    A flag that clears itself would otherwise raise the configuration revision
    twice a day, and every raise expires the `expected_revision` of a form
    somebody has open — refusing a valid save with `revision_conflict`.
    """
    store = await _loaded(hass)

    await store.async_set_ready("d1", True)
    await store.async_set_ready("d1", False)

    assert STORAGE_KEY not in hass_storage
    assert "revision" not in hass_storage[RUNTIME_STORAGE_KEY]["data"]


async def test_a_flag_without_a_window_lasts_a_day(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Twenty-four hours, and deliberately not midnight (SPEC.md §32.6).

    Midnight is exactly wrong for a household that fills the dishwasher late in
    the evening: the flag would expire before the machine ever ran.
    """
    await hass.config.async_set_time_zone(TIME_ZONE)
    freezer.move_to(dt_util.utcnow())
    store = await _loaded(hass)
    device = _device(ready_before=None)

    await store.async_set_ready(device.id, True)
    assert store.is_ready(device) is True

    freezer.tick(timedelta(hours=READY_FLAG_MAX_AGE_HOURS, minutes=1))
    assert store.is_ready(device) is False


async def test_a_flag_with_a_window_lasts_until_the_deadline(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Set at 22:00 for a 07:00 deadline: the window it belongs to is tomorrow's.

    The ordinary case rather than an edge one — which is why the expiry looks
    forward to the next 07:00 instead of the one that has already gone by.
    """
    await hass.config.async_set_time_zone(TIME_ZONE)
    set_at = dt_util.as_utc(
        dt_util.parse_datetime("2026-08-11T22:00:00+02:00")  # type: ignore[arg-type]
    )

    expiry = expires_at(_device(), set_at)

    assert dt_util.as_local(expiry).isoformat() == "2026-08-12T07:00:00+02:00"


async def test_a_flag_set_after_its_deadline_waits_for_the_next_one(
    hass: HomeAssistant,
) -> None:
    """08:00, past this morning's 07:00: the flag is about tomorrow morning."""
    await hass.config.async_set_time_zone(TIME_ZONE)
    set_at = dt_util.as_utc(
        dt_util.parse_datetime("2026-08-11T08:00:00+02:00")  # type: ignore[arg-type]
    )

    expiry = expires_at(_device(), set_at)

    assert dt_util.as_local(expiry).isoformat() == "2026-08-12T07:00:00+02:00"


async def test_a_deleted_appliance_loses_its_flag(hass: HomeAssistant) -> None:
    """A flag nobody can see is a flag nobody can clear."""
    store = await _loaded(hass)
    await store.async_set_ready("d1", True)
    await store.async_set_ready("weg", True)

    await store.async_forget({"d1"})

    assert store.set_at("d1") is not None
    assert store.set_at("weg") is None


async def test_an_unreadable_timestamp_is_dropped_rather_than_repaired(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A flag whose age is unknown cannot be expired, so it is not kept.

    The opposite choice from a stored *configuration* value, which is
    quarantined and kept verbatim (SPEC.md §53). There the value is something a
    person typed and can repair; here it is a moment nobody can reconstruct,
    and a flag that can never expire would feed the urgency advice forever.
    """
    hass_storage[RUNTIME_STORAGE_KEY] = {
        "version": 1,
        "data": {"ready": {"d1": "gisteravond"}},
    }

    store = await _loaded(hass)

    assert store.set_at("d1") is None
