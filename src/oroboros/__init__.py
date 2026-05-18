"""Public package exports for Oroboros."""

from typing import TYPE_CHECKING, Any


__all__ = [
    "ActivationHeaderUpdateResult",
    "HeaderFile",
    "ParseResult",
    "ParserConfig",
    "ParserDiagnostic",
    "find_all_headers",
    "find_included_headers",
    "parse_headers",
    "parse_activation_header",
    "print_update_report",
    "update_activation_header",
    "write_activation_header",
]


if TYPE_CHECKING:
    from .find_headers import HeaderFile, find_all_headers, find_included_headers
    from .parse import ParseResult, ParserConfig, ParserDiagnostic, parse_headers
    from .select_headers import (
        ActivationHeaderUpdateResult,
        parse_activation_header,
        print_update_report,
        update_activation_header,
        write_activation_header,
    )


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from .find_headers import HeaderFile, find_all_headers, find_included_headers
    from .parse import ParseResult, ParserConfig, ParserDiagnostic, parse_headers
    from .select_headers import (
        ActivationHeaderUpdateResult,
        parse_activation_header,
        print_update_report,
        update_activation_header,
        write_activation_header,
    )

    exports = {
        "ActivationHeaderUpdateResult": ActivationHeaderUpdateResult,
        "HeaderFile": HeaderFile,
        "ParseResult": ParseResult,
        "ParserConfig": ParserConfig,
        "ParserDiagnostic": ParserDiagnostic,
        "find_all_headers": find_all_headers,
        "find_included_headers": find_included_headers,
        "parse_headers": parse_headers,
        "parse_activation_header": parse_activation_header,
        "print_update_report": print_update_report,
        "update_activation_header": update_activation_header,
        "write_activation_header": write_activation_header,
    }
    return exports[name]
