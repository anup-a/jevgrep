"""ANSI colour support, following grep's --color and the NO_COLOR convention."""

from __future__ import annotations

from collections.abc import Mapping

RESET = "\033[0m"
DIM = "\033[2m"
ORIGIN = "\033[35m"  # magenta, matching grep's filename colour
LINE_NUMBER = "\033[32m"  # green, matching grep's line-number colour
SEPARATOR = "\033[36m"  # cyan, matching grep's separator colour

# A value's colour is its trustworthiness at a glance: green reads as settled,
# yellow as hesitant, red as "do not act on this without looking".
CONFIDENT = "\033[1;32m"
WAVERING = "\033[1;33m"
UNSURE = "\033[1;31m"

CONFIDENT_AT = 0.9
WAVERING_AT = 0.7

WHEN_CHOICES = ("auto", "always", "never")


def should_color(when: str, isatty: bool, env: Mapping[str, str]) -> bool:
    """Whether to emit ANSI escapes.

    `always` is an explicit request and wins over NO_COLOR; `auto` defers to the terminal
    and to NO_COLOR, which is presence-based rather than value-based by convention.
    """
    if when not in WHEN_CHOICES:
        raise ValueError(f"--color must be one of {', '.join(WHEN_CHOICES)}, got {when!r}")
    if when == "never":
        return False
    if when == "always":
        return True
    if "NO_COLOR" in env or env.get("TERM") == "dumb":
        return False
    return isatty


def confidence_color(value: float | None) -> str:
    """Colour for a probability or confidence. A missing value is never reassuring."""
    if value is None:
        return UNSURE
    if value >= CONFIDENT_AT:
        return CONFIDENT
    if value >= WAVERING_AT:
        return WAVERING
    return UNSURE


def paint(text: str, color: str, enabled: bool) -> str:
    return f"{color}{text}{RESET}" if enabled else text
