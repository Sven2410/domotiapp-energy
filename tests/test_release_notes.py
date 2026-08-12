"""Tests for the release notes the workflow puts on a GitHub release.

**Why these exist at all.** Until 2026-08-12 `release.yml` had one job that
compared the tag with the version in the code, a comment claiming it ran
"before the release is published", and **no step that published anything**.
Sven made every release by hand. The workflow went green on 0.28.0 and 0.29.0
while customers stayed on 0.27.1 with a regression that was already fixed.

That is the seventh variant applied to the release process: the check was
right and the action it guarded did not exist. The lesson taken here is that
logic which decides what a customer reads must sit where a test can reach it,
so the extraction lives in `scripts/release_notes.py` rather than in the YAML.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.release_notes import CHANGELOG, notes_for  # noqa: E402

_HEADING = re.compile(r"^## +(\S+) *$", re.MULTILINE)


def _changelog() -> str:
    """Return the real CHANGELOG, because that is what ships."""
    return CHANGELOG.read_text(encoding="utf-8")


def _newest_version() -> str:
    """Return the version at the top of the CHANGELOG."""
    match = _HEADING.search(_changelog())
    assert match is not None, "CHANGELOG.md has no version heading at all"
    return match.group(1)


def test_the_newest_version_has_notes() -> None:
    """Whatever is about to be released must produce something to read."""
    notes = notes_for(_newest_version(), _changelog())

    assert notes.strip()
    assert "Zie [CHANGELOG.md]" not in notes, (
        "the newest version fell through to the fallback, so the heading in "
        "CHANGELOG.md no longer matches what the workflow looks for"
    )


def test_the_notes_stop_at_the_next_version() -> None:
    """One release, one section. Never the whole file.

    Asserted on structure and not on prose: the wording changes every release,
    the shape does not.
    """
    changelog = _changelog()
    versions = _HEADING.findall(changelog)
    assert len(versions) >= 2, "need two versions to test the boundary"

    notes = notes_for(versions[0], changelog)

    assert not notes.startswith("## ")
    assert f"## {versions[1]}" not in notes


def test_every_version_in_the_changelog_can_be_released() -> None:
    """No heading may fall through to the fallback.

    A version that cannot find its own section would ship a release pointing at
    a file instead of saying what changed, and nothing else would notice.
    """
    changelog = _changelog()

    fell_through = [
        version
        for version in _HEADING.findall(changelog)
        if "Zie [CHANGELOG.md]" in notes_for(version, changelog)
    ]

    assert fell_through == []


def test_an_unknown_version_points_at_the_changelog() -> None:
    """The fallback is a sentence, never an empty release.

    A tag without a section is a mistake worth noticing, but it must not be a
    mistake that blocks shipping: the release still says where to look.
    """
    notes = notes_for("9.9.9", _changelog())

    assert "CHANGELOG.md" in notes
    assert "9.9.9" in notes


def test_a_version_with_an_empty_section_falls_back() -> None:
    """A heading with nothing under it is as useless as no heading."""
    notes = notes_for("1.2.3", "# Changelog\n\n## 1.2.3\n\n## 1.2.2\n\nIets.\n")

    assert "CHANGELOG.md" in notes
