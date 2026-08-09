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
# The entity is linked but its current state cannot be used as a measurement.
REASON_INVALID_ENTITY_STATE: Final = "invalid_entity_state"

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
    REASON_INSUFFICIENT_SAVINGS,
    REASON_NEUTRAL_ENERGY_SITUATION,
)
