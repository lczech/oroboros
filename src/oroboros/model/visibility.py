from __future__ import annotations

"""Shared C++ visibility values for semantic model objects."""

from enum import StrEnum


# ==================================================================================================
#     Visibility
# ==================================================================================================


class CppVisibility(StrEnum):
    """Enumerate the standard C++ declaration visibility levels."""

    PUBLIC = "public"
    PROTECTED = "protected"
    PRIVATE = "private"
