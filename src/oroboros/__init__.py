"""Public package exports for Oroboros."""

from typing import TYPE_CHECKING, Any


__all__ = [
    "ActivationHeaderUpdateResult",
    "Diagnostic",
    "DiagnosticReport",
    "HeaderFile",
    "HeaderSelection",
    "ParseResult",
    "ParserConfig",
    "CompilerToolchain",
    "detect_compiler_toolchain",
    "discover_headers",
    "find_all_headers",
    "find_included_headers",
    "parse_header_selection",
    "parse_activation_header",
    "print_parse_result",
    "print_parse_summary",
    "print_update_report",
    "select_active_headers",
    "update_activation_header",
    "write_activation_header",
]


if TYPE_CHECKING:
    from .diagnostics import Diagnostic, DiagnosticReport
    from .headers import (
        ActivationHeaderUpdateResult,
        HeaderFile,
        HeaderSelection,
        discover_headers,
        find_all_headers,
        find_included_headers,
        parse_activation_header,
        print_update_report,
        select_active_headers,
        update_activation_header,
        write_activation_header,
    )
    from .parse import (
        CompilerToolchain,
        ParseResult,
        ParserConfig,
        detect_compiler_toolchain,
        parse_header_selection,
        print_parse_result,
        print_parse_summary,
    )


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from .headers import (
        ActivationHeaderUpdateResult,
        HeaderFile,
        HeaderSelection,
        discover_headers,
        find_all_headers,
        find_included_headers,
        parse_activation_header,
        print_update_report,
        select_active_headers,
        update_activation_header,
        write_activation_header,
    )
    from .diagnostics import Diagnostic, DiagnosticReport
    from .parse import (
        CompilerToolchain,
        ParseResult,
        ParserConfig,
        detect_compiler_toolchain,
        parse_header_selection,
        print_parse_result,
        print_parse_summary,
    )

    exports = {
        "ActivationHeaderUpdateResult": ActivationHeaderUpdateResult,
        "CompilerToolchain": CompilerToolchain,
        "Diagnostic": Diagnostic,
        "DiagnosticReport": DiagnosticReport,
        "HeaderFile": HeaderFile,
        "HeaderSelection": HeaderSelection,
        "ParseResult": ParseResult,
        "ParserConfig": ParserConfig,
        "detect_compiler_toolchain": detect_compiler_toolchain,
        "discover_headers": discover_headers,
        "find_all_headers": find_all_headers,
        "find_included_headers": find_included_headers,
        "parse_header_selection": parse_header_selection,
        "parse_activation_header": parse_activation_header,
        "print_parse_result": print_parse_result,
        "print_parse_summary": print_parse_summary,
        "print_update_report": print_update_report,
        "select_active_headers": select_active_headers,
        "update_activation_header": update_activation_header,
        "write_activation_header": write_activation_header,
    }
    return exports[name]
