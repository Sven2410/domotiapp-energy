r"""Extract every string this product can put on a customer's screen.

Writes ``TEKSTEN.md`` in the repository root. Run it after any round that adds
or rewrites a sentence::

    py -3.13 .\\scripts\\extract_texts.py          # rewrite TEKSTEN.md
    py -3.13 .\\scripts\\extract_texts.py --check  # fail if it is out of date

``tests/test_texts.py`` runs the second form, so the document cannot quietly
age between rounds — which is what happened to the hand-made version: it was
generated once at 0.4.2 and was three rounds stale by 0.8.0.

**Standard library only, and nothing here reaches production.** Same rule as
``ha_check.py``: this is tooling, it adds nothing to ``custom_components/`` and
nothing to the runtime requirements.

What it does *not* do is decide whether a sentence is any good. It collects and
sorts; the rewriting round reads. The point of running it every round is that
the diff shows what a round added, in the customer's words.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "custom_components" / "domotiapp_energy"
OUTPUT = ROOT / "TEKSTEN.md"

# --- What counts as a text ---------------------------------------------------
#
# The filter is a heuristic and is documented as one. It errs towards keeping:
# a false positive is a line somebody skips while reading, a false negative is a
# sentence nobody reviews.

# An identifier, a key, an entity id, a format spec, a CSS declaration. None of
# these is ever read by a customer.
_CODE_LIKE = re.compile(
    r"""^(
        [a-z0-9_.]+                 # snake_case keys and dotted entity ids
        |[A-Z0-9_]+                 # constants
        |[-\w]+/[-\w/]*             # paths and command names
        |mdi:[-\w]+                 # icons
        |%[-\w.]+                   # format specs
        |\W*                        # punctuation and separators only
    )$""",
    re.VERBOSE,
)

# A CSS declaration or selector that happens to live in a string.
_CSS_LIKE = re.compile(r"[{};]\s*$|^\s*[.#@:][-\w]+\s*\{|^[-\w]+:\s*[-\w(]")

# Words that mark a line as English rather than Dutch. Deliberately small and
# deliberately unambiguous: none of these is a Dutch word.
_ENGLISH = {
    "the",
    "and",
    "with",
    "for",
    "that",
    "this",
    "from",
    "have",
    "has",
    "was",
    "were",
    "which",
    "would",
    "should",
    "could",
    "there",
    "their",
    "when",
    "what",
    "where",
    "because",
    "about",
    "into",
    "than",
    "then",
}
# Deliberately without "is", "in" and "of": each is a word in both languages,
# and one shared word put every English log line in the Dutch chapter on the
# first run of this script.
_DUTCH = {
    "de",
    "het",
    "een",
    "en",
    "van",
    "niet",
    "wordt",
    "op",
    "voor",
    "met",
    "dat",
    "dit",
    "je",
    "er",
    "aan",
    "bij",
    "als",
    "naar",
    "om",
    "geen",
    "wel",
    "nog",
    "deze",
    "die",
    "kan",
    "wat",
    "zijn",
    "worden",
}


# Shorter than this and it is a separator, a unit or an abbreviation.
_MIN_LENGTH = 3


def _is_text(value: str) -> bool:
    """Return whether this string could ever be read by a person."""
    stripped = value.strip()
    if len(stripped) < _MIN_LENGTH or "\n" in stripped:
        return False
    if _CODE_LIKE.match(stripped) or _CSS_LIKE.search(stripped):
        return False
    # A sentence has a space, or is a short label with a capital and a vowel.
    if " " in stripped:
        return True
    return stripped[:1].isupper() and any(c in "aeiouAEIOU" for c in stripped)


def _language(value: str) -> str:
    """Return `nl` or `en`, by the stop words each language does not share."""
    words = {word.strip(".,:;!?()'\"").lower() for word in value.split()}
    if words & _DUTCH:
        return "nl"
    if words & _ENGLISH:
        return "en"
    return "nl"


@dataclass(frozen=True, order=True)
class Text:
    """One string, and where it comes from."""

    text: str
    where: str
    context: str
    language: str


# --- Python ------------------------------------------------------------------


class _Collector(ast.NodeVisitor):
    """Gather every string constant that is not a docstring."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.found: list[Text] = []
        self._context: list[str] = []
        self._docstrings: set[int] = set()

    def _enter(self, node: ast.AST, name: str) -> None:
        body = getattr(node, "body", [])
        # ast.get_docstring only handles the node types below, and a docstring
        # is the one string in this package nobody ever sees on a screen.
        if body and isinstance(body[0], ast.Expr):
            value = body[0].value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                self._docstrings.add(id(value))
        self._context.append(name)
        self.generic_visit(node)
        self._context.pop()

    def visit_Module(self, node: ast.Module) -> None:
        self._enter(node, "")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._enter(node, node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._enter(node, node.name)

    def visit_Constant(self, node: ast.Constant) -> None:
        if not isinstance(node.value, str) or id(node) in self._docstrings:
            return
        if not _is_text(node.value):
            return
        self.found.append(
            Text(
                text=node.value.strip(),
                where=f"{self.path.as_posix()}:{node.lineno}",
                context=self._context[-1] or "module",
                language=_language(node.value),
            )
        )

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        """Rebuild an f-string with its slots marked, then judge the whole."""
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("{...}")
        joined = "".join(parts)
        if _is_text(joined):
            self.found.append(
                Text(
                    text=joined.strip(),
                    where=f"{self.path.as_posix()}:{node.lineno}",
                    context=self._context[-1] or "module",
                    language=_language(joined),
                )
            )


def _from_python() -> list[Text]:
    """Every text in the integration's Python."""
    found: list[Text] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        collector = _Collector(path.relative_to(ROOT))
        collector.visit(tree)
        found.extend(collector.found)
    return found


# --- JavaScript --------------------------------------------------------------

_JS_STRING = re.compile(r"'((?:[^'\\\n]|\\.)*)'")
_JS_COMMENT = re.compile(r"/\*[\s\S]*?\*/|//[^\n]*")


def _strip_stylesheet(source: str) -> str:
    """Remove the panel's stylesheet, which is CSS and not language.

    It is a template literal of several hundred lines and every declaration in
    it looks like a string to a regular expression. Cutting it out is the
    "filter de CSS-blokken eruit" of this round; without it the inventory is
    two thirds padding and nobody reads it twice.
    """
    start = source.find("const STYLES = `")
    if start == -1:
        return source
    end = source.find("`;", start)
    return source[:start] + source[end + 2 :] if end != -1 else source[:start]


def _from_javascript() -> list[Text]:
    """Every text in the panel."""
    found: list[Text] = []
    frontend = PACKAGE / "frontend"
    for path in sorted(frontend.rglob("*.js")):
        source = _JS_COMMENT.sub(
            "", _strip_stylesheet(path.read_text(encoding="utf-8"))
        )
        for line_number, line in enumerate(source.splitlines(), start=1):
            for match in _JS_STRING.finditer(line):
                value = match.group(1).replace("\\'", "'")
                if not _is_text(value):
                    continue
                found.append(
                    Text(
                        text=value.strip(),
                        where=f"{path.relative_to(ROOT).as_posix()}:{line_number}",
                        context=path.stem,
                        language=_language(value),
                    )
                )
    return found


# --- The document ------------------------------------------------------------


def _render(texts: list[Text]) -> str:
    """Return TEKSTEN.md for these texts."""
    dutch = [t for t in texts if t.language == "nl"]
    english = [t for t in texts if t.language == "en"]

    by_text: dict[str, list[Text]] = {}
    for item in dutch:
        by_text.setdefault(item.text, []).append(item)
    duplicated = {text for text, uses in by_text.items() if len(uses) > 1}

    lines: list[str] = [
        "# Alle teksten die dit product kan tonen",
        "",
        "**Gegenereerd door `scripts/extract_texts.py`. Niet met de hand bijwerken.**",
        "",
        "Draai het script opnieuw na elke ronde die een zin toevoegt of herschrijft;",
        "`tests/test_texts.py` faalt zolang dit bestand achterloopt. De diff van dit",
        "bestand is wat een ronde aan de klant heeft toegevoegd, in zijn woorden.",
        "",
        "## Hoe je dit leest",
        "",
        "Gesorteerd per bestand, want dat is wat het script weet. De redactionele",
        "indeling op zichtbaarheid komt terug wanneer het herschrijven begint — dan",
        "is dit de invoer en niet de uitvoer.",
        "",
        "**Geen regelnummers.** Die stonden hier tot 0.32.0 en maakten van deze",
        "inventaris iets dat onderhouden moest worden in plaats van andersom: één",
        "toegevoegde commentaarregel verschoof tientallen nummers en liet",
        "`tests/test_texts.py` rood worden om een wijziging die geen tekst raakte.",
        "Dat gebeurde tweemaal in één week. Een zin is met zijn eigen woorden te",
        "vinden; het bestand en de context zeggen genoeg.",
        "",
        "- **`{...}`** is een waarde die wordt ingevuld: een getal, een naam,",
        "  een bedrag.",
        "- **↔** staat achter een tekst die op meer dan één plek in de broncode staat.",
        "  Die twee moeten samen herschreven worden of ze lopen uiteen.",
        "- De **CSS** van het paneel is eruit gefilterd; dat is opmaak, geen taal.",
        "- **Engelse regels staan apart**, onderaan. Een Engelse zin in dit product is",
        "  een fout tenzij zij een identifier is: de UI is Nederlands (CLAUDE.md).",
        "",
        f"**{len(dutch)} Nederlandse teksten**, waarvan {len(duplicated)} op meer"
        f" dan één plek. En {len(english)} Engelse regels om na te lopen.",
        "",
    ]

    current = ""
    for item in sorted(dutch, key=lambda t: (t.where.split(":")[0], t.text)):
        source_file = item.where.split(":")[0]
        if source_file != current:
            current = source_file
            lines.extend(
                [
                    "",
                    f"## `{source_file}`",
                    "",
                    "| Tekst | Waar |",
                    "|---|---|",
                ]
            )
        mark = " ↔" if item.text in duplicated else ""
        text = item.text.replace("|", "\\|")
        lines.append(f"| {text}{mark} | {item.context} |")

    lines.extend(["", "", "## Engelse regels", "", "| Tekst | Waar |", "|---|---|"])
    for item in sorted(english, key=lambda t: (t.where.split(":")[0], t.text)):
        source_file = item.where.split(":")[0]
        lines.append(f"| {item.text.replace('|', chr(92) + '|')} | `{source_file}` |")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Write the inventory, or report that it is out of date."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 when TEKSTEN.md differs",
    )
    args = parser.parse_args()

    rendered = _render(_from_python() + _from_javascript())

    if not args.check:
        OUTPUT.write_text(rendered, encoding="utf-8")
        print(f"{OUTPUT.relative_to(ROOT)} written")
        return 0

    current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
    if current == rendered:
        print("TEKSTEN.md is up to date")
        return 0
    print("TEKSTEN.md is out of date; run scripts/extract_texts.py", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
