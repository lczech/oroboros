"""Public header discovery and selection exports."""

from .find_headers import discover_headers, find_all_headers, find_included_headers
from .model import HeaderFile, HeaderSelection
from .select_headers import (
    ActivationHeaderUpdateResult,
    parse_activation_header,
    print_update_report,
    select_active_headers,
    update_activation_header,
    write_activation_header,
)

__all__ = [
    "ActivationHeaderUpdateResult",
    "HeaderFile",
    "HeaderSelection",
    "discover_headers",
    "find_all_headers",
    "find_included_headers",
    "parse_activation_header",
    "print_update_report",
    "select_active_headers",
    "update_activation_header",
    "write_activation_header",
]
