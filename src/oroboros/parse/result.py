from __future__ import annotations

"""Public result objects returned by the parse stage."""

from dataclasses import dataclass, field
from pathlib import Path

from ..diagnostics import DiagnosticReport
from ..model import CppModule


class ParserInvariantError(RuntimeError):
    """Raise when the parser reaches a state that should be impossible internally."""


@dataclass(slots=True)
class ParseResult:
    """Store the semantic module plus diagnostics from one parse run."""

    # Ordered active headers that were used as parser input.
    headers: list[Path] = field(default_factory=list)
    # Semantic module built from the parsed headers, or an empty default module.
    module: CppModule = field(default_factory=lambda: CppModule(name="module"))
    # Structured diagnostics collected across header selection, clang parsing, parser
    # enrichment, and optional model validation.
    report: DiagnosticReport = field(default_factory=DiagnosticReport)
