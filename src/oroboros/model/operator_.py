from __future__ import annotations

"""Structured operator metadata used by function-like declarations."""

from dataclasses import dataclass
from typing import Literal

from .type import CppType


# ==================================================================================================
#     Operators
# ==================================================================================================


@dataclass(slots=True)
class CppOperator:
    """Store parsed C++ facts for one overloaded operator declaration."""

    kind: Literal[
        "punctuation",
        "conversion",
        "allocation",
        "deallocation",
        "co_await",
    ]
    symbol: str | None = None
    conversion_type: CppType | None = None
    is_postfix: bool = False


@dataclass(slots=True)
class CppOperatorBind:
    """Store binding policy for exposing one operator declaration."""

    mode: Literal["auto", "dunder", "named"] | None = None
