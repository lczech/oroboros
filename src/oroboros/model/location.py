from __future__ import annotations

"""Source location helpers for semantic model nodes."""

from dataclasses import dataclass
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
