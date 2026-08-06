"""Tests for the hysteresis that keeps an answer still (SPEC.md §16).

These are the unit tests for :mod:`engine.hysteresis`; the coordinator's use of
it is asserted in ``test_coordinator.py`` against a grid load that hovers around
the warning threshold, which is the situation that produced this module.

The constants are fixed on purpose, so the tests state the numbers they expect
rather than reading them from the configuration: a release margin that quietly
becomes zero would make every one of these pass while the flapping came back.
"""

from datetime import timedelta

from homeassistant.util import dt as dt_util

from custom_components.domotiapp_energy.const import (
    CONFIDENCE_HIGH,
    SEVERITY_INFO,
)
from custom_components.domotiapp_energy.engine.advisor import advice_rank
from custom_components.domotiapp_energy.engine.hysteresis import (
    Latch,
    PrimaryAdviceGate,
)
from custom_components.domotiapp_energy.engine.reason_codes import (
    REASON_HIGH_GRID_LOAD,
    REASON_LOW_ENERGY_PRICE,
    REASON_NEUTRAL_ENERGY_SITUATION,
    REASON_SOLAR_SURPLUS_AVAILABLE,
)
from custom_components.domotiapp_energy.models import AdviceItem


def _advice(reason_code: str) -> AdviceItem:
    """Return a minimal advice item carrying only its reason."""
    return AdviceItem(
        id=reason_code,
        title=reason_code,
        message="",
        severity=SEVERITY_INFO,
        reason_code=reason_code,
        confidence=CONFIDENCE_HIGH,
    )


# --- The threshold latch ----------------------------------------------------


def test_the_latch_holds_its_answer_inside_the_margin() -> None:
    """A value between the release point and the threshold changes nothing."""
    latch = Latch()

    assert latch.update(78.0, on_at=80.0, off_at=75.0) is False
    assert latch.update(81.0, on_at=80.0, off_at=75.0) is True
    # This is the reading that used to switch the warning straight back off,
    # every second, for as long as the load sat near the threshold.
    assert latch.update(78.0, on_at=80.0, off_at=75.0) is True
    assert latch.update(79.9, on_at=80.0, off_at=75.0) is True
    assert latch.update(74.9, on_at=80.0, off_at=75.0) is False


def test_the_latch_releases_without_a_measurement() -> None:
    """An unknown value drops the answer instead of preserving it.

    Holding a warning on a measurement we no longer have would be claiming
    something we cannot see; the missing data is reported on its own.
    """
    latch = Latch()
    latch.update(90.0, on_at=80.0, off_at=75.0)

    assert latch.update(None, on_at=80.0, off_at=75.0) is False


def test_the_latch_follows_an_edited_threshold() -> None:
    """The thresholds are arguments, so a configuration change takes effect."""
    latch = Latch()
    latch.update(60.0, on_at=80.0, off_at=75.0)
    assert latch.state is False

    # The installer lowered the warning level; 60% is now over it.
    assert latch.update(60.0, on_at=50.0, off_at=45.0) is True


def test_resetting_the_latch_forgets_the_answer() -> None:
    """A configuration change clears a held answer."""
    latch = Latch()
    latch.update(90.0, on_at=80.0, off_at=75.0)

    latch.reset()

    assert latch.state is False


# --- The primary advice gate ------------------------------------------------


def test_the_first_advice_is_shown_at_once() -> None:
    """There is nothing to protect on the first calculation."""
    gate = PrimaryAdviceGate(minimum_seconds=60.0)
    now = dt_util.utcnow()

    chosen = gate.choose(
        [_advice(REASON_SOLAR_SURPLUS_AVAILABLE)], now=now, rank_of=advice_rank
    )

    assert chosen[0].reason_code == REASON_SOLAR_SURPLUS_AVAILABLE


def test_a_less_urgent_advice_waits_for_the_dwell_time() -> None:
    """A demotion inside the minute keeps the headline where it was."""
    gate = PrimaryAdviceGate(minimum_seconds=60.0)
    now = dt_util.utcnow()
    solar = _advice(REASON_SOLAR_SURPLUS_AVAILABLE)
    price = _advice(REASON_LOW_ENERGY_PRICE)

    gate.choose([solar, price], now=now, rank_of=advice_rank)

    # Ten seconds later the price advice would take over. Too soon: one
    # sentence rewriting itself every few seconds is what this prevents.
    chosen = gate.choose(
        [price, solar], now=now + timedelta(seconds=10), rank_of=advice_rank
    )
    assert chosen[0].reason_code == REASON_SOLAR_SURPLUS_AVAILABLE
    # Nothing is dropped; the candidate only moves down a place.
    assert {item.reason_code for item in chosen} == {
        REASON_SOLAR_SURPLUS_AVAILABLE,
        REASON_LOW_ENERGY_PRICE,
    }

    chosen = gate.choose(
        [price, solar], now=now + timedelta(seconds=61), rank_of=advice_rank
    )
    assert chosen[0].reason_code == REASON_LOW_ENERGY_PRICE


def test_a_more_urgent_advice_never_waits() -> None:
    """A peak warning is shown immediately, timer or no timer."""
    gate = PrimaryAdviceGate(minimum_seconds=60.0)
    now = dt_util.utcnow()
    solar = _advice(REASON_SOLAR_SURPLUS_AVAILABLE)
    peak = _advice(REASON_HIGH_GRID_LOAD)

    gate.choose([solar], now=now, rank_of=advice_rank)
    chosen = gate.choose(
        [peak, solar], now=now + timedelta(seconds=1), rank_of=advice_rank
    )

    assert chosen[0].reason_code == REASON_HIGH_GRID_LOAD
    assert advice_rank(REASON_HIGH_GRID_LOAD) < advice_rank(
        REASON_SOLAR_SURPLUS_AVAILABLE
    )


def test_an_unsupported_advice_is_dropped_at_once() -> None:
    """What the data no longer supports is never held on screen.

    The deliberate limit of this gate: it smooths a ranking that changes, not a
    situation that genuinely comes and goes. Holding a sentence about a surplus
    that has gone would be a stale answer, which is worse than a changing one —
    stopping the coming and going is the latch's job, at the threshold.
    """
    gate = PrimaryAdviceGate(minimum_seconds=60.0)
    now = dt_util.utcnow()

    gate.choose([_advice(REASON_SOLAR_SURPLUS_AVAILABLE)], now=now, rank_of=advice_rank)
    chosen = gate.choose(
        [_advice(REASON_NEUTRAL_ENERGY_SITUATION)],
        now=now + timedelta(seconds=1),
        rank_of=advice_rank,
    )

    assert chosen[0].reason_code == REASON_NEUTRAL_ENERGY_SITUATION


def test_the_same_advice_keeps_the_latest_measurements() -> None:
    """Holding the subject still does not mean freezing its numbers."""
    gate = PrimaryAdviceGate(minimum_seconds=60.0)
    now = dt_util.utcnow()

    first = _advice(REASON_SOLAR_SURPLUS_AVAILABLE)
    first.measurements = {"zonneoverschot_w": 1200.0}
    gate.choose([first], now=now, rank_of=advice_rank)

    second = _advice(REASON_SOLAR_SURPLUS_AVAILABLE)
    second.measurements = {"zonneoverschot_w": 1400.0}
    chosen = gate.choose([second], now=now + timedelta(seconds=5), rank_of=advice_rank)

    assert chosen[0].measurements == {"zonneoverschot_w": 1400.0}


def test_the_dwell_clock_starts_at_the_change_not_at_every_pass() -> None:
    """Repeating the same advice does not push the timer forward.

    Otherwise a recalculation every fifteen seconds would keep resetting the
    minute, and the headline could never change at all.
    """
    gate = PrimaryAdviceGate(minimum_seconds=60.0)
    now = dt_util.utcnow()
    solar = _advice(REASON_SOLAR_SURPLUS_AVAILABLE)
    price = _advice(REASON_LOW_ENERGY_PRICE)

    for seconds in (0, 15, 30, 45):
        gate.choose(
            [solar, price], now=now + timedelta(seconds=seconds), rank_of=advice_rank
        )

    chosen = gate.choose(
        [price, solar], now=now + timedelta(seconds=61), rank_of=advice_rank
    )

    assert chosen[0].reason_code == REASON_LOW_ENERGY_PRICE


def test_an_empty_list_clears_what_was_held() -> None:
    """Nothing to advise means nothing held over to the next calculation."""
    gate = PrimaryAdviceGate(minimum_seconds=60.0)
    now = dt_util.utcnow()

    gate.choose([_advice(REASON_SOLAR_SURPLUS_AVAILABLE)], now=now, rank_of=advice_rank)
    assert gate.choose([], now=now, rank_of=advice_rank) == []
    assert gate.current is None
