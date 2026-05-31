from __future__ import annotations

"""Structured diagnostics shared across header discovery, parsing, and validation."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterable, Literal

if TYPE_CHECKING:
    from ..model.location import SourceLocation
else:
    SourceLocation = Any


DiagnosticSeverity = Literal["note", "warning", "error", "fatal"]
DiagnosticStage = Literal["headers", "clang", "parse", "validation"]


@dataclass(slots=True)
class Diagnostic:
    """Store one structured diagnostic message."""

    # User-facing severity level of this diagnostic.
    severity: DiagnosticSeverity
    # Pipeline stage that emitted this diagnostic.
    stage: DiagnosticStage
    # Stable machine-readable diagnostic identifier.
    code: str
    # Human-readable diagnostic message.
    message: str
    # Optional supplemental detail payload for expanded diagnostic rendering.
    detail: str | None = None
    # One or more relevant source locations associated with this diagnostic.
    locations: list[SourceLocation] = field(default_factory=list)
    # Semantic-model access path when the issue refers to one model element/subtree.
    element_path: str | None = None


@dataclass(slots=True)
class DiagnosticReport:
    """Store the collected diagnostics for one workflow."""

    # Preserved ordered diagnostics accumulated during one workflow.
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def notes(self) -> list[Diagnostic]:
        return self.by_severity("note")

    @property
    def warnings(self) -> list[Diagnostic]:
        return self.by_severity("warning")

    @property
    def errors(self) -> list[Diagnostic]:
        return self.by_severity("error")

    @property
    def fatals(self) -> list[Diagnostic]:
        return self.by_severity("fatal")

    def by_severity(self, severity: DiagnosticSeverity) -> list[Diagnostic]:
        return [diagnostic for diagnostic in self.diagnostics if diagnostic.severity == severity]

    def by_stage(self, stage: DiagnosticStage) -> list[Diagnostic]:
        return [diagnostic for diagnostic in self.diagnostics if diagnostic.stage == stage]

    def has_warnings(self) -> bool:
        return bool(self.warnings)

    def has_errors(self) -> bool:
        return bool(self.errors or self.fatals)

    def add(self, diagnostic: Diagnostic) -> None:
        if diagnostic not in self.diagnostics:
            self.diagnostics.append(diagnostic)

    def extend(self, diagnostics: Iterable[Diagnostic]) -> None:
        for diagnostic in diagnostics:
            self.add(diagnostic)

    def copy(self) -> "DiagnosticReport":
        return DiagnosticReport(diagnostics=list(self.diagnostics))

    def raise_for_errors(self, message: str = "Errors were reported.") -> None:
        if not self.has_errors():
            return
        raise ReportedError(
            message,
            diagnostics=self.errors + self.fatals,
        )


class ReportedError(ValueError):
    """Raise one or more collected diagnostics as a normal exception."""

    def __init__(self, message: str, *, diagnostics: list[Diagnostic]) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics
