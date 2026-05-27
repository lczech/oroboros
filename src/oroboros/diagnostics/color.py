from __future__ import annotations

"""ANSI color helpers for terminal-oriented diagnostic output."""

from os import environ
import sys
from typing import TextIO


RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GREEN = "\033[32m"


def should_use_color(
    stream: TextIO | None,
    *,
    color: bool | None = None,
) -> bool:
    """Return whether ANSI color should be used for one output stream."""

    if color is not None:
        return color

    if environ.get("NO_COLOR"):
        return False
    if environ.get("CLICOLOR_FORCE") not in {None, "", "0"}:
        return True

    output_stream = stream if stream is not None else sys.stdout
    isatty = getattr(output_stream, "isatty", None)
    if not callable(isatty) or not isatty():
        return False

    return environ.get("TERM", "").lower() != "dumb"


def colorize(text: str, *styles: str, color: bool) -> str:
    """Wrap text in ANSI styles when color output is enabled."""

    if not color or not styles:
        return text
    return "".join(styles) + text + RESET


def style_title(text: str, *, color: bool) -> str:
    """Render one section title consistently across terminal outputs."""

    return colorize(text, BOLD, color=color)


def style_muted(text: str, *, color: bool) -> str:
    """Render one low-emphasis label or placeholder."""

    return colorize(text, DIM, color=color)


def style_location(text: str, *, color: bool) -> str:
    """Render one source location string."""

    return colorize(text, CYAN, color=color)


def style_severity(text: str, severity: str, *, color: bool) -> str:
    """Render one severity-coded label consistently."""

    style = {
        "fatal": (BOLD, RED),
        "error": (RED,),
        "warning": (YELLOW,),
        "note": (BLUE,),
    }.get(severity, ())
    return colorize(text, *style, color=color)


def style_bool(value: bool, *, color: bool) -> str:
    """Render one boolean value with a stable success/error palette."""

    return colorize(str(value), GREEN if value else RED, color=color)


def style_success(text: str, *, color: bool) -> str:
    """Render one success-style heading or status label."""

    return colorize(text, BOLD, GREEN, color=color)


def style_failure(text: str, *, color: bool) -> str:
    """Render one failure-style heading or status label."""

    return colorize(text, BOLD, RED, color=color)
