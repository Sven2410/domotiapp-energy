"""When an appliance has to start to be finished on time (SPEC.md §32, §34.8).

Two functions, and the reason they are functions rather than the properties that
already exist on :class:`DeviceProfile`.

For a dishwasher the duration is a stored constant, and
``DeviceProfile.latest_start`` reads it straight off the profile. For a charger
it is a **function of the state of charge**, which changes every quarter of an
hour — and a property on a dataclass cannot look at a snapshot, so for a charger
the right answer can never come from there (SPEC.md §34.8).

**The second parameter is the metrics, where SPEC.md §34.8 wrote "snapshot".**
The advisor never sees a snapshot — it is handed an :class:`EnergyMetrics`, and
that is where per-appliance readings already live (``device_power_w``). A state
of charge will land there too. Plumbing a snapshot through the coordinator into
a pure function with no other use for it would be paying for the wrong noun.

Phase 2 does not support the charger and does not pretend to:
:func:`required_duration_minutes` returns ``device.duration_minutes`` and
nothing else. The point is that the urgency advice computes its deadline
*through this function*, so the charger later becomes one branch in one place
instead of a rebuild of the advice.

The properties on :class:`DeviceProfile` stay for what they do well — the form
and the validator, neither of which has a snapshot.
"""

from __future__ import annotations

from custom_components.domotiapp_energy.models import (
    DeviceProfile,
    EnergyMetrics,
    minutes_since_midnight,
)


def required_duration_minutes(
    device: DeviceProfile,
    metrics: EnergyMetrics,
) -> int | None:
    """Return how long this appliance still needs, in minutes.

    ``None`` when nobody has said. **A duration is never guessed**: without one
    there is no last start to compute, and the urgency advice stays silent
    rather than firing on an assumption (SPEC.md §32.2).
    """
    if device.duration_minutes is None:
        return None
    return int(device.duration_minutes)


def latest_start_minutes(device: DeviceProfile, metrics: EnergyMetrics) -> int | None:
    """Return the last minute-of-day this appliance can start and still be on time.

    ``ready_before`` minus what it still needs. ``None`` when either is missing.

    The result may be negative or past midnight and is deliberately **not**
    wrapped into a day here: the caller compares it against the current
    minute-of-day and has to handle a window that crosses midnight anyway, which
    is the normal case for a dishwasher that has to be done by 07:00.
    """
    finish = minutes_since_midnight(device.ready_before)
    duration = required_duration_minutes(device, metrics)
    if finish is None or duration is None:
        return None
    return finish - duration
