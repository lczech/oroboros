from __future__ import annotations

"""Public result objects returned by the parse stage."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ..model import CppModule, SourceLocation


@dataclass(slots=True)
class ParserDiagnostic:
    """Store one clang-level parser diagnostic."""

    severity: Literal["note", "warning", "error", "fatal"]
    message: str
    location: SourceLocation | None = None


@dataclass(slots=True)
class ParseResult:
    """Store the semantic module plus diagnostics from one parse run."""

    # Semantic module built from the parsed headers, or an empty default module.
    module: CppModule = field(default_factory=lambda: CppModule(name="module"))
    # Clang diagnostics reported while parsing the synthetic translation unit.
    diagnostics: list[ParserDiagnostic] = field(default_factory=list)
    # Oroboros-level parser warnings that are not raw clang diagnostics.
    warnings: list[str] = field(default_factory=list)
    # Counts of unsupported libclang cursor kinds skipped during tree building.
    skipped_kind_counts: dict[str, int] = field(default_factory=dict)
    # Ordered active headers that were used as parser input.
    headers: list[Path] = field(default_factory=list)
