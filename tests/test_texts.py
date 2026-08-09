"""The text inventory may not fall behind the code (SPEC.md §41).

`TEKSTEN.md` was made by hand once, at 0.4.2, and was three rounds stale by
0.8.0 — ten sentences on the score tile, the split export warning, the forecast
notice and the three control-level sentences had all arrived without it moving.
A document that ages silently is worse than no document: it is read as current.

So the inventory is generated, and this test is what makes "generated" mean
something. It fails on any round that adds a sentence without regenerating,
and the fix is one command.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "extract_texts.py"


def _extractor():
    """Import the script by path.

    `scripts/` is deliberately not a package: it holds tooling that must never
    become importable from `custom_components/`, and putting an `__init__.py`
    there would invite exactly that.
    """
    spec = importlib.util.spec_from_file_location("extract_texts", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["extract_texts"] = module
    spec.loader.exec_module(module)
    return module


def test_the_inventory_is_current() -> None:
    """Regenerating must produce exactly what is committed."""
    extract = _extractor()

    expected = extract._render(extract._from_python() + extract._from_javascript())
    actual = (ROOT / "TEKSTEN.md").read_text(encoding="utf-8")

    assert actual == expected, (
        "TEKSTEN.md is out of date. Run: py -3.13 .\\scripts\\extract_texts.py"
    )


def test_the_stylesheet_is_not_part_of_the_inventory() -> None:
    """CSS is layout, not language, and it drowns the document.

    The panel's stylesheet is a template literal of several hundred lines whose
    every declaration looks like a string. Left in, two thirds of the inventory
    is padding and nobody reads it twice.
    """
    extract = _extractor()

    texts = [item.text for item in extract._from_javascript()]

    assert not [text for text in texts if "px" in text and ":" in text]
    assert "flex" not in texts
    # The sentences the panel really shows are still there.
    assert any(text == "Niet beschikbaar" for text in texts)


def test_dutch_and_english_are_told_apart() -> None:
    """An English line in the UI is a defect unless it is an identifier.

    Marked separately rather than filtered out: the log messages that show up
    there are meant to be English, and a reader deciding that per line is the
    point. The classifier leans on stop words that are *not* shared between the
    two languages — "is" was in the Dutch set on the first run and put every
    English log line in the Dutch chapter.
    """
    extract = _extractor()

    assert extract._language("Er is nu opwek, maar geen apparaat") == "nl"
    assert extract._language("The energy configuration is kept in storage") == "en"
    assert extract._language("Configuration accessed before it was loaded") == "en"
    # A label with no stop word at all falls to Dutch, which is the safe side:
    # it lands in the chapter somebody reads.
    assert extract._language("Zonneoverschot") == "nl"
