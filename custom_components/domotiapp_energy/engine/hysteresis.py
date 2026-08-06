"""Keeping an answer still while the measurement moves (SPEC.md §16).

A threshold comparison is a fine way to decide something once. Asked again every
few seconds against a real meter it is a switch that rattles: a P1 meter reports
every second, so a load sitting at 79-81% of the configured maximum turned the
peak warning on and off continuously, and a solar surplus drifting around
``min_solar_surplus_w`` made an advice — and the euro amount under it — appear
and disappear at the same rate. A number that flickers is not a measurement a
customer can act on, and it makes everything beside it look unreliable too.

Two mechanisms, both with fixed constants from :mod:`..const`:

* :class:`Latch` turns a comparison into a switch with a release margin. It
  turns on at the threshold and off only once the value has moved a stated
  distance back, so the value has to *mean* the change before the answer does.
* :class:`PrimaryAdviceGate` keeps the headline advice on screen for a minimum
  time, so the one sentence the customer reads does not rewrite itself faster
  than it can be read.

**All the state lives here, and this module lives with the coordinator, not
with the calculator.** The calculator and the advisor stay pure functions of
their input: given the same snapshot they produce the same metrics and the same
advice, which is what makes them testable without moving time. The coordinator
owns an instance of each of these and applies them to the result.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from custom_components.domotiapp_energy.models import AdviceItem


@dataclass(slots=True)
class Latch:
    """A boolean that switches on at one level and off at a lower one.

    The thresholds are passed per call rather than stored: they come from the
    configuration and change the moment an installer edits it, and a latch
    holding a copy would keep comparing against the old setting.
    """

    state: bool = False

    def update(self, value: float | None, *, on_at: float, off_at: float) -> bool:
        """Return the latched state for this reading.

        An unknown value releases the latch. Holding a warning on a measurement
        we no longer have would be claiming something we cannot see, and the
        missing data is reported on its own.
        """
        if value is None:
            self.state = False
        elif value >= on_at:
            self.state = True
        elif value < off_at:
            self.state = False
        # Between off_at and on_at the previous answer stands: that gap is the
        # whole point.
        return self.state

    def reset(self) -> None:
        """Forget the previous answer, for a configuration change."""
        self.state = False


@dataclass(slots=True)
class PrimaryAdviceGate:
    """Holds the headline advice still for a minimum time.

    The rules, in order:

    * the first advice is shown immediately — there is nothing to protect yet;
    * an advice with the same reason code is always taken, so the text keeps the
      latest measurements while the subject stays put;
    * a **more urgent** advice is taken immediately. A peak warning may never
      wait for a timer;
    * an advice the current data no longer supports is dropped immediately. The
      alternative is holding a sentence about a surplus that is gone, and a
      stale answer is worse than a changing one;
    * anything else waits until the minimum time has passed.

    The fourth rule is a deliberate limit and worth stating plainly: this gate
    smooths a *ranking* that changes, not a situation that genuinely comes and
    goes. Stopping that is the job of :class:`Latch`, at the threshold where the
    coming and going starts.
    """

    minimum_seconds: float
    current: AdviceItem | None = None
    shown_since: datetime | None = None

    def choose(
        self,
        advice: list[AdviceItem],
        *,
        now: datetime,
        rank_of: Callable[[str], int],
    ) -> list[AdviceItem]:
        """Return the advice list with the primary one held where it should be.

        The list is returned with the chosen primary first, because everything
        downstream — the sensor, the panel, the coach — reads ``advice[0]`` as
        the primary one.
        """
        if not advice:
            self.current = None
            self.shown_since = None
            return advice

        candidate = advice[0]
        held = self._held(advice, candidate, now, rank_of)
        if held is None:
            self._adopt(candidate, now)
            return advice

        # Keep the held advice as the primary one, without dropping anything:
        # the candidate simply moves down one place.
        self.current = held
        return [held, *(item for item in advice if item is not held)]

    def _held(
        self,
        advice: list[AdviceItem],
        candidate: AdviceItem,
        now: datetime,
        rank_of: Callable[[str], int],
    ) -> AdviceItem | None:
        """Return the advice to keep showing, or None to take the candidate."""
        current = self.current
        if current is None or self.shown_since is None:
            return None
        if candidate.reason_code == current.reason_code:
            return None
        if rank_of(candidate.reason_code) < rank_of(current.reason_code):
            return None

        still_supported = next(
            (item for item in advice if item.reason_code == current.reason_code), None
        )
        if still_supported is None:
            return None
        if now - self.shown_since >= timedelta(seconds=self.minimum_seconds):
            return None
        return still_supported

    def _adopt(self, item: AdviceItem, now: datetime) -> None:
        """Start showing this advice, restarting the clock only on a change."""
        if self.current is None or self.current.reason_code != item.reason_code:
            self.shown_since = now
        self.current = item

    def reset(self) -> None:
        """Forget what is on screen, for a configuration change."""
        self.current = None
        self.shown_since = None
