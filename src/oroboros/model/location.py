from __future__ import annotations

"""Source location helpers for semantic model elements."""

from dataclasses import dataclass, field
from pathlib import Path


# ==================================================================================================
#     Location
# ==================================================================================================


@dataclass(slots=True)
class SourceLocation:
    """Store one file, line, and column reference from C++ source."""

    file: Path
    line: int
    column: int


@dataclass(slots=True)
class CppLocationInfo:
    """Store primary, declaration, and definition source locations together."""

    primary: SourceLocation | None = None
    declarations: list[SourceLocation] = field(default_factory=list)
    definition: SourceLocation | None = None
