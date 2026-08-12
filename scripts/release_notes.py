"""Print the CHANGELOG section for one version, for the release workflow.

**A separate script and not a few lines inside the workflow, on purpose.** The
round this was written in existed because `release.yml` contained a check with
nothing behind it, and nothing could see that: a workflow step is reachable by
no test. Logic that decides what a customer reads belongs where `pytest` can
get at it, and `tests/test_release_notes.py` is what gets at this.

Standard library only, and it adds nothing to the integration: `custom_components/`
never imports this.

Usage::

    python scripts/release_notes.py 0.29.0
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).parent.parent / "CHANGELOG.md"

# The script name plus one version.
_EXPECTED_ARGUMENTS = 2

# A version heading, as CHANGELOG.md writes them: "## 0.29.0" at the start of a
# line. The next heading of the same level ends the section.
_HEADING = re.compile(r"^## +(?P<version>\S+) *$", re.MULTILINE)


def notes_for(version: str, changelog: str) -> str:
    """Return the notes for ``version``, or a pointer when there are none.

    **The fallback is a sentence and not an empty string.** A release with empty
    notes looks finished and says nothing; a release that points at the
    CHANGELOG is honest about where the story is, and it is still better than
    the workflow failing over prose. Nobody should be unable to ship because a
    heading was spelled differently.
    """
    for match in _HEADING.finditer(changelog):
        if match.group("version") != version:
            continue
        following = _HEADING.search(changelog, match.end())
        end = following.start() if following else len(changelog)
        body = changelog[match.end() : end].strip()
        if body:
            return body
        break

    return (
        f"Zie [CHANGELOG.md](https://github.com/Sven2410/domotiapp-energy/"
        f"blob/{version}/CHANGELOG.md) voor wat er in deze versie zit."
    )


def main(argv: list[str]) -> int:
    """Print the notes for the version named on the command line."""
    if len(argv) != _EXPECTED_ARGUMENTS:
        print("usage: release_notes.py <version>", file=sys.stderr)
        return 2

    print(notes_for(argv[1], CHANGELOG.read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
