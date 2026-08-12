"""Stable reason codes (SPEC.md §12).

A reason code says *why* a result is what it is. Every Dutch text in the panel
is built from these codes, so they are part of the contract with the frontend:
never inline the string, never rename one without updating the translations.

This module is created in phase 3 rather than phase 4 because
:mod:`..validators` already has to report why an entity value was refused.
"""

from __future__ import annotations

from typing import Final

# Something the calculation needs is absent: no entity linked, no meter mode
# chosen, no maximum grid power entered.
REASON_MISSING_REQUIRED_DATA: Final = "missing_required_data"
# The entity is linked, present and reporting, but what it reports cannot be
# used as a measurement: a word where a number was expected, an attribute that
# is not there, a value that is not finite.
#
# **This code became narrower in 0.28.0** (SPEC.md §63.5). Until then it was
# the single answer to four different situations, and the four below took its
# place. What is left is the one of the five that is always a statement about
# the installation rather than about the moment.
REASON_INVALID_ENTITY_STATE: Final = "invalid_entity_state"

# --- Why an entity carried no measurement (SPEC.md §63.5) --------------------
#
# Home Assistant already distinguishes these, and the distinction is the whole
# repair: `unknown` means "this entity is alive and has no value yet", while
# `unavailable` means "the integration behind it declares the device
# unreachable". Collapsing them made a source that had not spoken yet
# indistinguishable from a source that was broken.

# The entity is not in the state machine at all. True while an integration is
# still setting up, true while one is being torn down, and true when the
# installer linked something that does not exist.
REASON_ENTITY_MISSING: Final = "entity_missing"
# The entity is there and available, but carries no value yet: `unknown`, or an
# attribute that exists without content. A source that has never spoken is an
# unanswered question, not a fault.
REASON_ENTITY_WITHOUT_VALUE: Final = "entity_without_value"
# The integration itself reports the entity as `unavailable`. This is the one
# statement in this group that another integration made on purpose.
REASON_ENTITY_UNAVAILABLE: Final = "entity_unavailable"
# There is a value, and it is older than the window for this kind of source
# (SPEC.md §47). The source went quiet while everything around it kept running.
REASON_ENTITY_STALE: Final = "entity_stale"

REASON_SOLAR_SURPLUS_AVAILABLE: Final = "solar_surplus_available"
# Overload caused by drawing from the grid: postpone consumers.
REASON_HIGH_GRID_LOAD: Final = "high_grid_load"
# Overload caused by feeding back into the grid. The main fuse limits both
# directions, so the risk is identical, but the action is the opposite one:
# advising a home that exports 10 kW to postpone its appliances would push it
# further into the overload it is already in (SPEC.md §16).
REASON_HIGH_GRID_EXPORT: Final = "high_grid_export"
REASON_LOW_ENERGY_PRICE: Final = "low_energy_price"
REASON_HIGH_ENERGY_PRICE: Final = "high_energy_price"
REASON_FLEXIBLE_DEVICE_AVAILABLE: Final = "flexible_device_available"
REASON_OUTSIDE_ALLOWED_WINDOW: Final = "outside_allowed_window"
REASON_QUIET_HOURS_ACTIVE: Final = "quiet_hours_active"
# The urgency advice of SPEC.md §32.3, at rank 3 — the "hard time limits" place
# in the sort order that has been empty since 0.1.0.
REASON_DEADLINE_APPROACHING: Final = "deadline_approaching"
REASON_INSUFFICIENT_SAVINGS: Final = "insufficient_savings"
REASON_NEUTRAL_ENERGY_SITUATION: Final = "neutral_energy_situation"

REASON_CODES: Final[tuple[str, ...]] = (
    REASON_MISSING_REQUIRED_DATA,
    REASON_SOLAR_SURPLUS_AVAILABLE,
    REASON_HIGH_GRID_LOAD,
    REASON_HIGH_GRID_EXPORT,
    REASON_LOW_ENERGY_PRICE,
    REASON_HIGH_ENERGY_PRICE,
    REASON_FLEXIBLE_DEVICE_AVAILABLE,
    REASON_OUTSIDE_ALLOWED_WINDOW,
    REASON_QUIET_HOURS_ACTIVE,
    REASON_DEADLINE_APPROACHING,
    REASON_INVALID_ENTITY_STATE,
    REASON_ENTITY_MISSING,
    REASON_ENTITY_WITHOUT_VALUE,
    REASON_ENTITY_UNAVAILABLE,
    REASON_ENTITY_STALE,
    REASON_INSUFFICIENT_SAVINGS,
    REASON_NEUTRAL_ENERGY_SITUATION,
)
