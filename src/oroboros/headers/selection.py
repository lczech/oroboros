from __future__ import annotations

"""Structured header records passed from discovery and selection into parsing."""

from dataclasses import dataclass, field
from pathlib import Path

from ..diagnostics import DiagnosticReport


@dataclass(frozen=True, slots=True)
class HeaderFile:
    """Represent one project header relative to a configured base directory."""

    full_path: Path
    relative_path: Path
    active: bool = True


@dataclass(frozen=True, slots=True)
class HeaderSelection:
    """Represent known project headers plus the currently active subset."""

    header_files: list[HeaderFile]
    report: DiagnosticReport = field(default_factory=DiagnosticReport)

    @property
    def known_headers(self) -> list[HeaderFile]:
        """Return all known project headers in preserved inventory order."""

        return list(self.header_files)

    @property
    def active_headers(self) -> list[HeaderFile]:
        """Return only the headers currently selected for parsing."""

        return [header_file for header_file in self.header_files if header_file.active]

    @property
    def known_project_headers(self) -> list[Path]:
        """Return full paths for all known project headers."""

        return [header_file.full_path for header_file in self.known_headers]

    @property
    def active_project_headers(self) -> list[Path]:
        """Return full paths for the active subset of project headers."""

        return [header_file.full_path for header_file in self.active_headers]
