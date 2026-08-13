"""Count transient spikes in a power series from the recorder (read-only).

**What this measures, and what it does not.** It counts *transients*: a reading
that stands far above the level on both sides of it and falls straight back.
It cannot know what caused one. An inverter reporting nonsense while it starts
up and a genuine flash of sun through a hole in the cloud look the same from
here, and calling either of them an artefact would be this script deciding
something it cannot see. The per-episode table is therefore the output that
matters; the totals only say how often the shape occurs.

**Why not "any production before sunrise".** That was the first criterion and it
was wrong, measured against the case it was written for (Sven, 2026-08-13):
sunrise 06:15, the panels genuinely coming off zero around 06:30, and the spike
at about 06:40 — 500 W on a real production of some 20 W, twenty-five times
over and immediately back down. A rule about darkness finds nothing there and
would have reported that the phenomenon never happens.

So the criterion is the *shape*: a peak that returns to its own baseline. A
reading in the dark is not excluded by that — it is the special case where the
baseline happens to be zero, and it is still counted through the absolute rise.

**Horizon.** This reads state history, which the recorder keeps for
`purge_keep_days` (ten by default) — long-term statistics are hourly and cannot
show a spike that lasts a minute. The script reports the window it actually got
back, which is how you see where your own recorder stops.

**Read-only.** Every call is a GET against `/api/history/period`. Nothing here
writes, calls a service or changes a configuration.

Usage::

    py -3.13 scripts/solar_spikes.py --entity sensor.solaredge_ac_power
    py -3.13 scripts/solar_spikes.py --entity sensor.pv --days 30 --json

``HA_URL`` and ``HA_TOKEN`` come from ``.env`` in the repository root, like
``ha_check.py``; ``--url`` and ``--token`` override them, for pointing a run at
an instance that is not the one in ``.env``.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"

# A day of state history for a power sensor is thousands of rows, and the
# recorder has to read them off disk.
TIMEOUT_SECONDS = 120

# How far to look on each side for the level this reading should be judged
# against. Ten minutes is long enough that a spike of a minute or two cannot
# drag its own baseline up, and short enough that the morning ramp — which
# moves over hours — barely changes across it.
DEFAULT_WINDOW_MINUTES = 10.0

# How far above the baseline a peak has to stand, as a multiple. Five, against
# a measured twenty-five: broken cloud gives brief overshoots of tens of
# percent rather than multiples, so this leaves the weather out without being
# tuned so tightly around one observation that nothing else fits.
DEFAULT_RATIO = 5.0

# And in watts, because a multiple means nothing near zero: 2 W over a baseline
# of 0.2 W is a factor of ten and is not a phenomenon. This is also what counts
# a spike in the dark, where the baseline is zero and the ratio says nothing.
DEFAULT_MIN_RISE_W = 100.0

# Two weeks asked by default. Anything the recorder no longer holds comes back
# empty, and the summary says so rather than quietly reporting a shorter run.
DEFAULT_DAYS = 14

# A transient this soon after the day's first production is consistent with
# something that happens when the inverter starts. It is a grouping in the
# report, never a filter: the episodes outside it are printed too.
STARTUP_MINUTES = 30.0

# Samples closer together than this belong to the same episode. A spike is
# often two or three consecutive readings, and counting each of them would
# report one event three times.
EPISODE_GAP_MINUTES = 5.0

# States that are not a measurement. Skipped rather than read as zero, for the
# reason the engine skips them: an unavailable sensor is not a sensor reading
# nothing (SPEC.md §15).
NON_NUMERIC_STATES = frozenset({"unavailable", "unknown", "none", ""})


class HomeAssistantError(RuntimeError):
    """Raised when Home Assistant cannot be reached or refuses the request."""


@dataclass(frozen=True, slots=True)
class Sample:
    """One reading, in local time."""

    at: datetime
    watts: float


@dataclass(frozen=True, slots=True)
class Transient:
    """A peak that stood above both of its neighbourhoods and fell back."""

    peak_at: datetime
    peak_w: float
    baseline_w: float
    seconds: float
    minutes_after_first_production: float | None

    @property
    def ratio(self) -> float | None:
        """Return how many times the baseline the peak was, if that means anything."""
        if self.baseline_w <= 0:
            return None
        return self.peak_w / self.baseline_w

    def as_dict(self) -> dict[str, Any]:
        """Return the episode as plain data, for ``--json``."""
        return {
            "peak_at": self.peak_at.isoformat(),
            "peak_w": round(self.peak_w, 1),
            "baseline_w": round(self.baseline_w, 1),
            "ratio": None if self.ratio is None else round(self.ratio, 1),
            "seconds": round(self.seconds, 1),
            "minutes_after_first_production": (
                None
                if self.minutes_after_first_production is None
                else round(self.minutes_after_first_production, 1)
            ),
        }


# --- Talking to Home Assistant ----------------------------------------------


def read_env() -> dict[str, str]:
    """Return the key/value pairs from .env, or an empty mapping when there is none."""
    if not ENV_FILE.is_file():
        return {}

    env: dict[str, str] = {}
    for raw_line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip("\"'")
    return env


def fetch_history(
    url: str, token: str, entity_id: str, start: datetime, end: datetime
) -> list[Sample]:
    """Return every numeric reading of one entity between two moments.

    The recorder stores changes, so this is every value the entity reported
    that differed from the one before it — which is exactly what a spike is.
    """
    query = urllib.parse.urlencode(
        {"filter_entity_id": entity_id, "end_time": end.isoformat()}
    )
    path = (
        f"{url.rstrip('/')}/api/history/period/{urllib.parse.quote(start.isoformat())}"
        f"?{query}&minimal_response&no_attributes"
    )
    # The URL comes from our own .env or from --url, never from user input.
    request = urllib.request.Request(
        path,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = "check the token" if err.code in (401, 403) else err.reason
        raise HomeAssistantError(f"{url} returned {err.code}: {detail}") from err
    except urllib.error.URLError as err:
        raise HomeAssistantError(f"Could not reach {url}: {err.reason}") from err

    return [sample for series in payload for sample in _parse_series(series)]


def _parse_series(series: list[dict[str, Any]]) -> list[Sample]:
    """Return the usable readings of one entity's history series."""
    samples: list[Sample] = []
    for row in series:
        moment = _parse_time(row)
        value = _parse_watts(row.get("state"))
        if moment is not None and value is not None:
            samples.append(Sample(at=moment.astimezone(), watts=value))
    samples.sort(key=lambda sample: sample.at)
    return samples


def _parse_time(row: dict[str, Any]) -> datetime | None:
    """Return when this row was recorded, whichever key carries it.

    ``minimal_response`` shortens the rows after the first one, and the key it
    leaves behind has changed shape between Home Assistant versions. Trying all
    four is cheaper than pinning a version.
    """
    for key in ("last_changed", "last_updated", "lc", "lu"):
        raw = row.get(key)
        if isinstance(raw, int | float):
            return datetime.fromtimestamp(raw).astimezone()
        if isinstance(raw, str):
            try:
                return datetime.fromisoformat(raw)
            except ValueError:
                continue
    return None


def _parse_watts(raw: Any) -> float | None:
    """Return the reading as a number, or None when it is not one."""
    if not isinstance(raw, str) or raw.strip().lower() in NON_NUMERIC_STATES:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    # NaN and infinity are what a broken conversion upstream looks like; the
    # engine refuses them too (`as_finite_float`).
    return value if math.isfinite(value) else None


# --- Finding the shape ------------------------------------------------------


def _median_between(
    samples: list[Sample], times: list[datetime], start: datetime, end: datetime
) -> float | None:
    """Return the median reading in ``[start, end)``, or None when there is none."""
    low = bisect.bisect_left(times, start)
    high = bisect.bisect_left(times, end)
    if high <= low:
        return None
    return statistics.median(sample.watts for sample in samples[low:high])


def find_transients(
    samples: list[Sample],
    *,
    window_minutes: float,
    ratio: float,
    min_rise_w: float,
    first_production: datetime | None,
) -> list[Transient]:
    """Return every peak that stands above both neighbourhoods and falls back.

    The baseline is taken on **both** sides and the higher of the two is used.
    That is what makes this a spike detector rather than a step detector: a
    morning that simply climbs has a high level after it, so the peak is never
    a multiple of its own surroundings and nothing is reported. A reading that
    goes up and comes back has a low level on both sides, whatever the hour.
    """
    times = [sample.at for sample in samples]
    window = timedelta(minutes=window_minutes)
    marked: list[int] = []

    for index, sample in enumerate(samples):
        before = _median_between(samples, times, sample.at - window, sample.at)
        after = _median_between(
            samples, times, sample.at + timedelta(microseconds=1), sample.at + window
        )
        if before is None or after is None:
            # One side falls outside the data: the start of the series, the end
            # of it, or a gap. Nothing can be said about a shape with one edge.
            continue
        baseline = max(before, after)
        if sample.watts - baseline < min_rise_w:
            continue
        if baseline > 0 and sample.watts < baseline * ratio:
            continue
        marked.append(index)

    return _group_episodes(samples, marked, first_production)


def _group_episodes(
    samples: list[Sample], marked: list[int], first_production: datetime | None
) -> list[Transient]:
    """Fold consecutive marked readings into one episode each."""
    if not marked:
        return []

    gap = timedelta(minutes=EPISODE_GAP_MINUTES)
    episodes: list[list[int]] = [[marked[0]]]
    for index in marked[1:]:
        if samples[index].at - samples[episodes[-1][-1]].at <= gap:
            episodes[-1].append(index)
        else:
            episodes.append([index])

    return [_describe(samples, group, first_production) for group in episodes]


def _describe(
    samples: list[Sample], group: list[int], first_production: datetime | None
) -> Transient:
    """Return one episode as a peak with its context."""
    peak = max((samples[index] for index in group), key=lambda sample: sample.watts)
    window = timedelta(minutes=DEFAULT_WINDOW_MINUTES)
    times = [sample.at for sample in samples]
    before = _median_between(samples, times, peak.at - window, peak.at)
    after = _median_between(
        samples, times, peak.at + timedelta(microseconds=1), peak.at + window
    )
    baseline = max(before or 0.0, after or 0.0)

    minutes: float | None = None
    if first_production is not None:
        minutes = (peak.at - first_production).total_seconds() / 60

    return Transient(
        peak_at=peak.at,
        peak_w=peak.watts,
        baseline_w=baseline,
        seconds=(samples[group[-1]].at - samples[group[0]].at).total_seconds(),
        minutes_after_first_production=minutes,
    )


def first_production_of(
    samples: list[Sample], *, window_minutes: float = DEFAULT_WINDOW_MINUTES
) -> datetime | None:
    """Return when this day started producing and kept producing.

    **Not simply the first reading above zero**, and the difference is the whole
    value of the column this feeds. A spike in the dark is itself a reading
    above zero, so the naive version made every such spike its own "first
    production" and printed it as +0 minutes — exactly the mark of an inverter
    waking up, on the one case that is nothing of the sort. Requiring the next
    ten minutes to hold up as well leaves a lone spike where it belongs: before
    any production, or on a day that had none.
    """
    times = [sample.at for sample in samples]
    window = timedelta(minutes=window_minutes)
    for sample in samples:
        if sample.watts <= 0:
            continue
        held = _median_between(samples, times, sample.at, sample.at + window)
        if held is not None and held > 0:
            return sample.at
    return None


# --- Reporting --------------------------------------------------------------


def _local_midnight(days_ago: int) -> datetime:
    """Return the start of a local day, ``days_ago`` days back."""
    today = (
        datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    )
    return today - timedelta(days=days_ago)


@dataclass(slots=True)
class DayResult:
    """What one local day produced."""

    date: str
    samples: int
    transients: list[Transient]


def scan(
    url: str, token: str, entity_id: str, days: int, options: argparse.Namespace
) -> list[DayResult]:
    """Walk back over the days one at a time and collect the episodes."""
    results: list[DayResult] = []
    # **Today included, and that was wrong on the first run** (2026-08-13). The
    # loop stopped at yesterday, so the one morning the whole question came from
    # was the one morning it could not see. `--days 1` means today.
    for days_ago in range(days - 1, -1, -1):
        start = _local_midnight(days_ago)
        end = start + timedelta(days=1)
        samples = fetch_history(url, token, entity_id, start, end)
        transients = find_transients(
            samples,
            window_minutes=options.window,
            ratio=options.ratio,
            min_rise_w=options.min_rise,
            first_production=first_production_of(samples),
        )
        results.append(
            DayResult(
                date=start.date().isoformat(),
                samples=len(samples),
                transients=transients,
            )
        )
        print(
            f"  {start.date().isoformat()}: {len(samples):>6} readings, "
            f"{len(transients)} transient(s)",
            file=sys.stderr,
        )
    return results


def report(
    results: list[DayResult], entity_id: str, options: argparse.Namespace
) -> None:
    """Print the episodes and what can be said about them."""
    with_data = [day for day in results if day.samples]
    episodes = [(day, item) for day in results for item in day.transients]

    print(f"\nTransients in {entity_id}")
    print(
        f"Criterion: at least {options.min_rise:.0f} W above the higher of the two "
        f"{options.window:.0f}-minute baselines, plus (when that baseline is "
        f"above zero) at least {options.ratio:.1f}x it."
    )
    print(f"Asked for {len(results)} days; {len(with_data)} of them returned readings.")
    if len(with_data) < len(results):
        print(
            "  The empty days are where your recorder stops (purge_keep_days), "
            "not days without sun."
        )

    if not episodes:
        print("\nNo transient matched. Loosen --ratio or --min-rise to widen the net.")
        return

    print(
        f"\n{'date':<12}{'peak':<10}{'W':>8}{'baseline':>10}{'ratio':>8}"
        f"{'lasted':>8}  after first production"
    )
    for day, item in episodes:
        ratio = "-" if item.ratio is None else f"{item.ratio:.1f}x"
        after = (
            "-"
            if item.minutes_after_first_production is None
            else f"{item.minutes_after_first_production:+.0f} min"
        )
        print(
            f"{day.date:<12}{item.peak_at.strftime('%H:%M:%S'):<10}"
            f"{item.peak_w:>8.0f}{item.baseline_w:>10.1f}{ratio:>8}"
            f"{item.seconds:>7.0f}s  {after}"
        )

    days_hit = len({day.date for day, _ in episodes})
    startup = [
        item
        for _, item in episodes
        if item.minutes_after_first_production is not None
        and 0 <= item.minutes_after_first_production <= STARTUP_MINUTES
    ]
    dark = [
        item
        for _, item in episodes
        if item.minutes_after_first_production is not None
        and item.minutes_after_first_production < 0
    ]
    print(
        f"\n{len(episodes)} transient(s) on {days_hit} of {len(with_data)} days "
        f"with data."
    )
    print(
        f"{len(startup)} fell within {STARTUP_MINUTES:.0f} minutes of that day's "
        f"first production; {len(dark)} before it."
    )
    print(
        "A transient is a shape, not a cause: a flash of sun through cloud makes "
        "the same one. Clustering just after first production is what points at "
        "the inverter."
    )


def main() -> int:
    """Read the arguments, scan, and report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--entity", required=True, help="the power entity to scan")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--window", type=float, default=DEFAULT_WINDOW_MINUTES)
    parser.add_argument("--ratio", type=float, default=DEFAULT_RATIO)
    parser.add_argument("--min-rise", type=float, default=DEFAULT_MIN_RISE_W)
    parser.add_argument("--url", help="overrides HA_URL from .env")
    parser.add_argument("--token", help="overrides HA_TOKEN from .env")
    parser.add_argument("--json", action="store_true", help="print raw episodes")
    options = parser.parse_args()

    env = read_env()
    url = options.url or env.get("HA_URL")
    token = options.token or env.get("HA_TOKEN")
    if not url or not token:
        print(
            "No HA_URL/HA_TOKEN in .env and none given with --url/--token.",
            file=sys.stderr,
        )
        return 2

    try:
        results = scan(url, token, options.entity, options.days, options)
    except HomeAssistantError as err:
        print(f"{err}", file=sys.stderr)
        return 1

    if options.json:
        print(
            json.dumps(
                {
                    "entity_id": options.entity,
                    "days": [
                        {
                            "date": day.date,
                            "samples": day.samples,
                            "transients": [item.as_dict() for item in day.transients],
                        }
                        for day in results
                    ],
                },
                indent=2,
            )
        )
    else:
        report(results, options.entity, options)
    return 0


if __name__ == "__main__":
    sys.exit(main())
