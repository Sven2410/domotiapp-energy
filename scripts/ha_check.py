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

    # call a WebSocket command, optionally as another user
    py -3.13 scripts/ha_check.py --ws domotiapp_energy/config/get
    py -3.13 scripts/ha_check.py --ws domotiapp_energy/config/get --as READONLY

There are three ways to give a command its payload, because typing JSON on a
Windows PowerShell 5 command line is a fight nobody should have to win::

    # 1. --field, repeatable. No JSON, no quoting problem. Dotted keys nest,
    #    and each value is read as JSON when it can be, as text otherwise.
    py -3.13 scripts/ha_check.py --ws domotiapp_energy/sources/create `
        --field expected_revision=3 `
        --field source.type=current_price `
        --field source.name="Dynamische prijs" `
        --field source.price_basis=all_in `
        --field source.enabled=true

    # 2. --data-file, for a payload that is easier to keep in a file. Use "-"
    #    to read it from stdin. A UTF-8 BOM is accepted, because that is what
    #    Set-Content writes in PowerShell 5.
    py -3.13 scripts/ha_check.py --ws domotiapp_energy/sources/create `
        --data-file scratch/source.json

    # 3. --data, the raw JSON string. Fine in bash, painful in PowerShell 5.
    py -3.13 scripts/ha_check.py --ws domotiapp_energy/sources/create \
        --data '{"expected_revision": 1, "source": {}}'

``--field`` merges on top of ``--data`` or ``--data-file``, so a payload from a
file can be reused with one value changed. ``--dry-run`` prints the frame that
would be sent and stops there; it needs neither a token nor a running instance,
which makes it the quickest way to check that an invocation quotes correctly.

``--set`` calls ``input_number.set_value`` on the helper that stands in for a
grid meter, so a recalculation can be triggered without clicking through the
UI. That is this script acting as a developer would by hand; the integration
itself still controls nothing (SPEC.md §2.2).

``--ws`` speaks the Home Assistant WebSocket API directly, because that API is
the only way to reach the integration's own commands — they are not exposed
over REST. It is limited to ``domotiapp_energy/*`` plus ``auth/current_user``,
which is there to prove *which* user a token belongs to when verifying the
permission checks; this is a verification aid, not a remote control for Home
Assistant.

The WebSocket client below is written against RFC 6455 by hand for one reason:
the standard library has no WebSocket client, and this script may not add a
dependency. It handles exactly what talking to Home Assistant needs.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
import socket
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"

# The eight entity ids SPEC.md §19 fixes. Hard-coded rather than imported from
# const.py: this script has to notice when the running instance disagrees with
# what we think we ship, and importing our own expectation would hide exactly
# that.
EXPECTED_ENTITIES = (
    "sensor.domotiapp_energy_score",
    "sensor.domotiapp_energy_data_quality",
    "sensor.domotiapp_energy_grid_power",
    "sensor.domotiapp_energy_home_consumption",
    "sensor.domotiapp_energy_solar_surplus",
    "sensor.domotiapp_energy_current_advice",
    "binary_sensor.domotiapp_energy_peak_risk",
    "binary_sensor.domotiapp_energy_attention",
)

# Attributes worth showing per entity; anything else is noise in a terminal.
INTERESTING_ATTRIBUTES = (
    "friendly_name",
    "advice_title",
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


# --- WebSocket ---------------------------------------------------------------

WS_OPCODE_TEXT = 0x1
WS_OPCODE_CLOSE = 0x8
WS_OPCODE_PING = 0x9
WS_OPCODE_PONG = 0xA

# Commands this script is allowed to send. auth/current_user is included so a
# run can prove which user the token belongs to; everything else is ours.
WS_ALLOWED_PREFIXES = ("domotiapp_energy/",)
WS_ALLOWED_COMMANDS = ("auth/current_user",)


class _WebSocket:
    """A minimal RFC 6455 client: enough to talk to Home Assistant.

    Only what is needed here: a text frame out, a text frame in, client-side
    masking (mandatory for a client), and a pong for a server ping. No
    extensions, no compression, no fragmentation on the way out.
    """

    def __init__(self, sock: socket.socket) -> None:
        """Wrap a socket that has already completed the HTTP upgrade."""
        self._sock = sock
        self._buffer = b""

    def send(self, payload: dict[str, Any]) -> None:
        """Send one JSON message as a masked text frame."""
        data = json.dumps(payload).encode("utf-8")
        header = bytearray([0x80 | WS_OPCODE_TEXT])
        length = len(data)

        if length < 126:  # noqa: PLR2004 - the RFC's own thresholds
            header.append(0x80 | length)
        elif length < 65536:  # noqa: PLR2004
            header.append(0x80 | 126)
            header += struct.pack("!H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack("!Q", length)

        mask = os.urandom(4)
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(data))
        self._sock.sendall(bytes(header) + mask + masked)

    def receive(self) -> dict[str, Any]:
        """Return the next JSON message, answering pings along the way."""
        while True:
            opcode, payload = self._read_frame()
            if opcode == WS_OPCODE_TEXT:
                return json.loads(payload.decode("utf-8"))
            if opcode == WS_OPCODE_PING:
                self._send_control(WS_OPCODE_PONG, payload)
            elif opcode == WS_OPCODE_CLOSE:
                raise HomeAssistantError("Home Assistant closed the connection")

    def close(self) -> None:
        """Close the connection, best effort."""
        with contextlib.suppress(OSError):
            self._send_control(WS_OPCODE_CLOSE, b"")
        self._sock.close()

    def _send_control(self, opcode: int, payload: bytes) -> None:
        """Send a masked control frame."""
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        self._sock.sendall(bytes([0x80 | opcode, 0x80 | len(payload)]) + mask + masked)

    def _read_frame(self) -> tuple[int, bytes]:
        """Read one frame and return its opcode and unmasked payload."""
        first, second = self._read_exactly(2)
        opcode = first & 0x0F
        length = second & 0x7F

        if length == 126:  # noqa: PLR2004
            length = struct.unpack("!H", self._read_exactly(2))[0]
        elif length == 127:  # noqa: PLR2004
            length = struct.unpack("!Q", self._read_exactly(8))[0]

        # A server never masks, so there is no mask key to read.
        return opcode, self._read_exactly(length)

    def _read_exactly(self, count: int) -> bytes:
        """Read exactly this many bytes, or fail."""
        while len(self._buffer) < count:
            chunk = self._sock.recv(65536)
            if not chunk:
                raise HomeAssistantError("Connection closed while reading a frame")
            self._buffer += chunk
        data, self._buffer = self._buffer[:count], self._buffer[count:]
        return data


def _ws_connect(env: dict[str, str], token: str) -> _WebSocket:
    """Open a WebSocket to Home Assistant and authenticate."""
    url = urllib.parse.urlparse(env["HA_URL"])
    if url.scheme == "https":
        raise HomeAssistantError(
            "This script speaks plain ws:// only; point HA_URL at the local "
            "http:// instance."
        )
    host = url.hostname or "localhost"
    port = url.port or 80

    key = base64.b64encode(os.urandom(16)).decode()
    request_lines = (
        f"GET {url.path or '/'}api/websocket HTTP/1.1",
        f"Host: {host}:{port}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
    )

    try:
        sock = socket.create_connection((host, port), timeout=TIMEOUT_SECONDS)
    except OSError as err:
        raise HomeAssistantError(
            f"Could not connect to {host}:{port}: {err}. Is the container running?"
        ) from err

    sock.sendall(("\r\n".join(request_lines) + "\r\n\r\n").encode())

    handshake = b""
    while b"\r\n\r\n" not in handshake:
        chunk = sock.recv(4096)
        if not chunk:
            raise HomeAssistantError("Home Assistant closed the upgrade handshake")
        handshake += chunk

    status = handshake.split(b"\r\n", 1)[0].decode(errors="replace")
    if "101" not in status:
        sock.close()
        raise HomeAssistantError(f"Upgrade refused: {status}")

    # SHA-1 with this fixed GUID is what RFC 6455 prescribes for the handshake.
    # It is a protocol check, not a security primitive.
    expected = base64.b64encode(
        hashlib.sha1(f"{key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11".encode()).digest()
    ).decode()
    if expected.encode() not in handshake:
        sock.close()
        raise HomeAssistantError("Upgrade accepted with a wrong Sec-WebSocket-Accept")

    connection = _WebSocket(sock)

    greeting = connection.receive()
    if greeting.get("type") != "auth_required":
        connection.close()
        raise HomeAssistantError(f"Unexpected greeting: {greeting}")

    connection.send({"type": "auth", "access_token": token})
    result = connection.receive()
    if result.get("type") != "auth_ok":
        connection.close()
        raise HomeAssistantError(
            f"Authentication refused: {result.get('message', result)}"
        )
    return connection


def call_websocket(
    env: dict[str, str], token: str, command_type: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Send one WebSocket command and return the whole result frame."""
    if not command_type.startswith(WS_ALLOWED_PREFIXES) and (
        command_type not in WS_ALLOWED_COMMANDS
    ):
        raise HomeAssistantError(
            f"Refusing to send {command_type!r}: this script only sends "
            f"domotiapp_energy/* commands and auth/current_user."
        )

    connection = _ws_connect(env, token)
    try:
        connection.send({"id": 1, "type": command_type, **payload})
        while True:
            message = connection.receive()
            # Home Assistant may interleave other frames; ours carries id 1.
            if message.get("id") == 1 and message.get("type") == "result":
                return message
    finally:
        connection.close()


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


def _read_data_file(path: str) -> str:
    """Return the contents of a payload file, or of stdin for "-".

    ``utf-8-sig`` rather than ``utf-8`` on purpose: ``Set-Content -Encoding
    UTF8`` in Windows PowerShell 5 writes a byte order mark, and a plain UTF-8
    read would hand that BOM to the JSON parser as a stray character.
    """
    if path == "-":
        return sys.stdin.read()
    try:
        return Path(path).read_text(encoding="utf-8-sig")
    except OSError as err:
        raise HomeAssistantError(f"Could not read {path}: {err}") from err


def _field_value(raw: str) -> Any:
    """Return a --field value as JSON when it is JSON, as text otherwise.

    So ``expected_revision=3`` is a number, ``enabled=true`` is a boolean and
    ``name=Slimme meter`` is a string, without anyone having to say which is
    which. A value that has to stay text but happens to look like JSON can be
    quoted the JSON way: ``name="42"``.
    """
    try:
        return json.loads(raw)
    except ValueError:
        return raw


def _assign(payload: dict[str, Any], path: str, value: Any) -> None:
    """Set a possibly nested key, creating the objects along the way.

    ``source.binding.unit`` builds the two objects it needs. Walking into
    something that is not an object is refused rather than overwritten: that is
    a typo in the invocation, and silently dropping the earlier value would
    send a payload nobody asked for.
    """
    keys = path.split(".")
    target = payload
    for index, key in enumerate(keys[:-1]):
        existing = target.setdefault(key, {})
        if not isinstance(existing, dict):
            walked = ".".join(keys[: index + 1])
            raise HomeAssistantError(
                f"--field {path}: {walked} is already a value, not an object"
            )
        target = existing
    target[keys[-1]] = value


def _build_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Assemble the command payload from --data, --data-file and --field."""
    if args.data is not None and args.data_file is not None:
        raise HomeAssistantError("Use either --data or --data-file, not both")

    raw = args.data
    if args.data_file is not None:
        raw = _read_data_file(args.data_file)

    payload: dict[str, Any] = {}
    if raw is not None and raw.strip():
        try:
            parsed = json.loads(raw)
        except ValueError as err:
            source = "--data-file" if args.data_file is not None else "--data"
            raise HomeAssistantError(f"{source} is not valid JSON: {err}") from err
        if not isinstance(parsed, dict):
            raise HomeAssistantError("The payload must be a JSON object")
        payload = parsed

    for field in args.field or []:
        key, separator, value = field.partition("=")
        if not separator or not key:
            raise HomeAssistantError(f"--field {field!r} is not key=value")
        _assign(payload, key, _field_value(value))

    return payload


def _run_websocket(env: dict[str, str], args: argparse.Namespace) -> int:
    """Send one WebSocket command and print the answer verbatim.

    Prints the whole frame, success or failure, because the point of this mode
    is to see what Home Assistant actually replied — including the error code
    and, for a revision conflict, the configuration it sends back.
    """
    key = f"HA_TOKEN_{args.token_suffix.upper()}" if args.token_suffix else "HA_TOKEN"
    token = env.get(key)
    if not token:
        raise HomeAssistantError(f"{ENV_FILE.name} has no {key}")

    payload = _build_payload(args)
    if args.merge:
        payload = _merged_payload(env, token, args.ws, payload)
    else:
        _warn_if_replacing(args.ws, payload)

    result = call_websocket(env, token, args.ws, payload)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("success") else 1


# Commands that **replace** their subject rather than patching it. Sending one
# of these a partial object silently resets everything it does not mention.
#
# That is deliberate in the integration and it is not a defect: the device form
# clears a field by leaving it out, because a field the chosen type has no
# answer for must not keep a stored answer (SPEC.md §49.3). `home/update` and
# `preferences/update` merge instead, so they are not listed here.
#
# It is a bad fit for `--field`, though, which invites you to name one thing.
# Both times this script wiped half a row it was in exactly this way.
_REPLACING_COMMANDS: dict[str, str] = {
    "domotiapp_energy/sources/update": "source",
    "domotiapp_energy/devices/update": "device",
}


def _warn_if_replacing(command_type: str, payload: dict[str, Any]) -> None:
    """Say out loud that this command replaces rather than patches."""
    key = _REPLACING_COMMANDS.get(command_type)
    if key is None or not isinstance(payload.get(key), dict):
        return
    print(
        f"Let op: {command_type} vervangt de hele rij. Velden die je hier niet "
        f"noemt worden teruggezet op hun standaardwaarde.\n"
        f"         Gebruik --merge om de opgeslagen rij op te halen en alleen "
        f"deze velden te wijzigen.\n",
        file=sys.stderr,
    )


def _merged_payload(
    env: dict[str, str], token: str, command_type: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Return the payload with the stored row underneath it.

    Reads the current configuration, finds the row this command names, and lays
    the given fields on top — so a replacing command carries the whole object
    and changes only what was asked for.

    Refuses rather than guesses when the row cannot be found: creating a row by
    accident, out of a command meant to change one, is worse than an error.
    """
    key = _REPLACING_COMMANDS.get(command_type)
    if key is None:
        raise HomeAssistantError(
            f"--merge only applies to {', '.join(sorted(_REPLACING_COMMANDS))}"
        )

    given = payload.get(key)
    if not isinstance(given, dict) or not given.get("id"):
        raise HomeAssistantError(f"--merge needs {key}.id to know which row to read")

    answer = call_websocket(env, token, "domotiapp_energy/config/get", {})
    if not answer.get("success"):
        raise HomeAssistantError(f"could not read the configuration: {answer}")

    collection = f"{key}s"
    rows = answer["result"].get(collection, [])
    stored = next((row for row in rows if row.get("id") == given["id"]), None)
    if stored is None:
        raise HomeAssistantError(f"no {key} with id {given['id']!r} to merge into")

    merged = {**stored, **given}
    changed = sorted(k for k in given if k != "id" and stored.get(k) != given[k])
    print(
        f"--merge: {len(stored)} opgeslagen velden gelezen, "
        f"{len(changed)} gewijzigd ({', '.join(changed) or 'geen'}).",
        file=sys.stderr,
    )
    return {**payload, key: merged}


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
    parser.add_argument(
        "--ws",
        metavar="COMMAND",
        help="send a domotiapp_energy WebSocket command and print the result",
    )
    parser.add_argument(
        "--data",
        metavar="JSON",
        help="extra fields for --ws, as a JSON object",
    )
    parser.add_argument(
        "--data-file",
        metavar="PATH",
        help='read the --ws payload from this file, or from stdin for "-"',
    )
    parser.add_argument(
        "--field",
        action="append",
        metavar="KEY=VALUE",
        help=(
            "one payload field, repeatable; dotted keys nest (source.name=Slimme meter)"
        ),
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help=(
            "read the stored row first and change only the named fields; "
            "for sources/update and devices/update, which otherwise replace "
            "the whole row"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the frame --ws would send and stop, without connecting",
    )
    parser.add_argument(
        "--as",
        dest="token_suffix",
        metavar="SUFFIX",
        help="use HA_TOKEN_<SUFFIX> from .env instead of HA_TOKEN",
    )
    args = parser.parse_args()

    try:
        if args.dry_run:
            # Deliberately before read_env(): checking how an invocation is
            # quoted should not need a token or a running instance.
            if not args.ws:
                raise HomeAssistantError("--dry-run only applies to --ws")
            payload = _build_payload(args)
            # The warning belongs here too, and arguably most of all: --dry-run
            # is what you run to check an invocation *before* firing it.
            _warn_if_replacing(args.ws, payload)
            frame = {"id": 1, "type": args.ws, **payload}
            print(json.dumps(frame, indent=2, ensure_ascii=False))
            return 0

        env = read_env()

        if args.ws:
            return _run_websocket(env, args)

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
