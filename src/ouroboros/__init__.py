"""Public package exports for Ouroboros."""

from typing import TYPE_CHECKING, Any


__all__ = ["HeaderFile", "find_all_headers", "find_included_headers"]


if TYPE_CHECKING:
    from .find_headers import HeaderFile, find_all_headers, find_included_headers


def __getattr__(name: str) -> Any:
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from .find_headers import HeaderFile, find_all_headers, find_included_headers

    exports = {
        "HeaderFile": HeaderFile,
        "find_all_headers": find_all_headers,
        "find_included_headers": find_included_headers,
    }
    return exports[name]
