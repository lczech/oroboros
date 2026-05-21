"""Public package exports for Oroboros."""

from typing import TYPE_CHECKING, Any


__all__ = [
    "ActivationHeaderUpdateResult",
    "HeaderFile",
    "HeaderSelection",
    "ParseResult",
    "ParserConfig",
    "CompilerToolchain",
    "ParserDiagnostic",
    "detect_compiler_toolchain",
    "discover_headers",
    "find_all_headers",
    "find_included_headers",
    "parse_header_selection",
    "parse_activation_header",
    "print_update_report",
    "select_active_headers",
    "update_activation_header",
    "write_activation_header",
]


if TYPE_CHECKING:
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
        ParserDiagnostic,
        detect_compiler_toolchain,
        parse_header_selection,
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
    from .parse import (
        CompilerToolchain,
        ParseResult,
        ParserConfig,
        ParserDiagnostic,
        detect_compiler_toolchain,
        parse_header_selection,
    )

    exports = {
        "ActivationHeaderUpdateResult": ActivationHeaderUpdateResult,
        "CompilerToolchain": CompilerToolchain,
        "HeaderFile": HeaderFile,
        "HeaderSelection": HeaderSelection,
        "ParseResult": ParseResult,
        "ParserConfig": ParserConfig,
        "ParserDiagnostic": ParserDiagnostic,
        "detect_compiler_toolchain": detect_compiler_toolchain,
        "discover_headers": discover_headers,
        "find_all_headers": find_all_headers,
        "find_included_headers": find_included_headers,
        "parse_header_selection": parse_header_selection,
        "parse_activation_header": parse_activation_header,
        "print_update_report": print_update_report,
        "select_active_headers": select_active_headers,
        "update_activation_header": update_activation_header,
        "write_activation_header": write_activation_header,
    }
    return exports[name]
