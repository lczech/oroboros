from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "Diagnostic",
    "DiagnosticReport",
    "DiagnosticRenderOptions",
    "ReportedError",
    "format_diagnostic",
    "format_diagnostics",
    "format_report",
    "print_diagnostics",
    "print_report",
]

if TYPE_CHECKING:
    from .formatting import (
        format_diagnostic,
        format_diagnostics,
        format_report,
        DiagnosticRenderOptions,
        print_diagnostics,
        print_report,
    )
    from .report import Diagnostic, DiagnosticReport, ReportedError


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    if name in {"Diagnostic", "DiagnosticReport", "ReportedError"}:
        from .report import Diagnostic, DiagnosticReport, ReportedError

        exports = {
            "Diagnostic": Diagnostic,
            "DiagnosticReport": DiagnosticReport,
            "ReportedError": ReportedError,
        }
        return exports[name]

    from .formatting import (
        format_diagnostic,
        format_diagnostics,
        format_report,
        DiagnosticRenderOptions,
        print_diagnostics,
        print_report,
    )

    exports = {
        "DiagnosticRenderOptions": DiagnosticRenderOptions,
        "format_diagnostic": format_diagnostic,
        "format_diagnostics": format_diagnostics,
        "format_report": format_report,
        "print_diagnostics": print_diagnostics,
        "print_report": print_report,
    }
    return exports[name]
