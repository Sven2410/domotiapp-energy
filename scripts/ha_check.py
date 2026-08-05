"""Read the DomotiApp Energy entities from the running Home Assistant.

A verification tool, **not** part of the integration and **not** a replacement
for the test suite. A phase is finished when ``pytest`` passes; this script
catches what the test harness cannot see by construction: another Home
Assistant version, another UI language, and real entities in a real instance.
Phase 5 shipped entity ids that moved with the customer's language while every
test was green — that is what this exists for.

It uses the standard library only, and adds nothing to ``custom_components/``
or to the runtime requirements. Keep production logic out of it.

Configuration comes from ``.env`` in the repository root (git-ignored)::

    HA_URL=http://localhost:8124
    HA_TOKEN=<long-lived access token>
    HA_INPUT_NUMBER=input_number.netvermogen   # optional, for --set

Usage::

    py -3.13 scripts/ha_check.py                 # show the six entities
    py -3.13 scripts/ha_check.py --set -5700     # set the meter, then show
    py -3.13 scripts/ha_check.py --json          # raw states

``--set`` calls ``input_number.set_value`` on the helper that stands in for a
grid meter, so a recalculation can be triggered without clicking through the
UI. That is this script acting as a developer would by hand; the integration
itself still controls nothing (SPEC.md §2.2).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"

# The six entity ids SPEC.md §19 fixes. Hard-coded rather than imported from
# const.py: this script has to notice when the running instance disagrees with
# what we think we ship, and importing our own expectation would hide exactly
# that.
EXPECTED_ENTITIES = (
    "sensor.domotiapp_energy_score",
    "sensor.domotiapp_energy_data_quality",
    "sensor.domotiapp_energy_grid_power",
    "sensor.domotiapp_energy_solar_surplus",
    "sensor.domotiapp_energy_current_advice",
    "binary_sensor.domotiapp_energy_peak_risk",
)

# Attributes worth showing per entity; anything else is noise in a terminal.
INTERESTING_ATTRIBUTES = (
    "friendly_name",
    "unit_of_measurement",
    "device_class",
    "grid_load_percent",
    "reason_code",
    "confidence",
)

DEFAULT_INPUT_NUMBER = "input_number.netvermogen"
TIMEOUT_SECONDS = 10

# The coordinator debounces recalculations by RECALCULATE_DEBOUNCE_SECONDS (2 s),
# so reading straight after --set would show the previous calculation and look
# like the change was ignored. Wait past the cooldown before reading.
SETTLE_SECONDS = 3.0


class HomeAssistantError(RuntimeError):
    """Raised when Home Assistant cannot be reached or refuses the request."""


def read_env() -> dict[str, str]:
    """Return the key/value pairs from .env, or exit with an explanation."""
    if not ENV_FILE.is_file():
        raise HomeAssistantError(
            f"No {ENV_FILE.name} found in {REPO_ROOT}. Create one with HA_URL and "
            f"HA_TOKEN; it is git-ignored."
        )

    env: dict[str, str] = {}
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip("\"'")

    missing = [key for key in ("HA_URL", "HA_TOKEN") if not env.get(key)]
    if missing:
        raise HomeAssistantError(f"{ENV_FILE.name} is missing {', '.join(missing)}")
    return env


def request(
    env: dict[str, str], path: str, payload: dict[str, Any] | None = None
) -> Any:
    """Call the Home Assistant REST API and return the decoded response."""
    url = f"{env['HA_URL'].rstrip('/')}/api/{path.lstrip('/')}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    # The URL comes from our own .env, never from user input.
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {env['HA_TOKEN']}",
            "Content-Type": "application/json",
        },
        method="POST" if data is not None else "GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        detail = "check HA_TOKEN" if err.code in (401, 403) else err.reason
        raise HomeAssistantError(f"{url} returned {err.code}: {detail}") from err
    except urllib.error.URLError as err:
        raise HomeAssistantError(
            f"Could not reach {url}: {err.reason}. Is the container running?"
        ) from err


def set_input_number(env: dict[str, str], entity_id: str, value: float) -> None:
    """Set a helper to a value, so the coordinator recalculates."""
    request(
        env,
        "services/input_number/set_value",
        {"entity_id": entity_id, "value": value},
    )
    print(f"Set {entity_id} to {value}, waiting {SETTLE_SECONDS:g}s for the debounce\n")
    time.sleep(SETTLE_SECONDS)


def fetch_states(env: dict[str, str]) -> dict[str, dict[str, Any]]:
    """Return every state in the instance, keyed by entity id."""
    return {state["entity_id"]: state for state in request(env, "states")}


def print_report(states: dict[str, dict[str, Any]]) -> bool:
    """Print the six entities and return whether all of them were found."""
    width = max(len(entity_id) for entity_id in EXPECTED_ENTITIES)
    complete = True

    for entity_id in EXPECTED_ENTITIES:
        state = states.get(entity_id)
        if state is None:
            complete = False
            print(f"{entity_id:<{width}}  MISSING")
            continue
        print(f"{entity_id:<{width}}  {state['state']}")
        for key in INTERESTING_ATTRIBUTES:
            if (value := state["attributes"].get(key)) is not None:
                print(f"{'':<{width}}    {key}: {value}")

    if not complete:
        print(
            "\nOne or more of the six entity ids from SPEC.md §19 is missing.\n"
            "Either the integration is not set up, or the ids have moved — check\n"
            "the entity registry for entities named domotiapp_energy_* and compare."
        )

    unexpected = sorted(
        entity_id
        for entity_id in states
        if "domotiapp_energy" in entity_id and entity_id not in EXPECTED_ENTITIES
    )
    if unexpected:
        complete = False
        print("\nUnexpected DomotiApp entities present:")
        for entity_id in unexpected:
            print(f"  {entity_id}  {states[entity_id]['state']}")

    return complete


def main() -> int:
    """Run the verification and return a shell exit code."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--set",
        type=float,
        metavar="WATTS",
        help="set the grid meter helper to this value before reading the states",
    )
    parser.add_argument(
        "--entity",
        default=None,
        metavar="ENTITY_ID",
        help=f"the helper --set writes to (default: {DEFAULT_INPUT_NUMBER})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the raw states of the six entities instead of a table",
    )
    args = parser.parse_args()

    try:
        env = read_env()
        if args.set is not None:
            entity_id = (
                args.entity or env.get("HA_INPUT_NUMBER") or DEFAULT_INPUT_NUMBER
            )
            set_input_number(env, entity_id, args.set)

        states = fetch_states(env)
    except HomeAssistantError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2

    if args.json:
        print(
            json.dumps(
                {entity_id: states.get(entity_id) for entity_id in EXPECTED_ENTITIES},
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    return 0 if print_report(states) else 1


if __name__ == "__main__":
    raise SystemExit(main())
