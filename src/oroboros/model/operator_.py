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
        "symbolic",
        "conversion",
        "allocation",
        "deallocation",
        "co_await",
    ]
    symbol: str | None = None
    conversion_type: CppType | None = None
    is_explicit: bool = False
    is_postfix: bool = False


@dataclass(slots=True)
class CppOperatorBind:
    """Store binding policy for exposing one operator declaration."""

    mode: Literal["auto", "dunder", "named"] | None = None


# ==================================================================================================
#     Predicates
# ==================================================================================================


_COMPARISON_OPERATOR_SYMBOLS = frozenset({"==", "!=", "<", "<=", ">", ">=", "<=>"})
_ARITHMETIC_OPERATOR_SYMBOLS = frozenset({"+", "-", "*", "/", "%"})
_BITWISE_OPERATOR_SYMBOLS = frozenset({"~", "&", "|", "^", "<<", ">>"})
_LOGICAL_OPERATOR_SYMBOLS = frozenset({"!", "&&", "||"})
_ASSIGNMENT_OPERATOR_SYMBOLS = frozenset({"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="})
_INCREMENT_DECREMENT_OPERATOR_SYMBOLS = frozenset({"++", "--"})


def is_symbolic_operator(operator: CppOperator | None) -> bool:
    """Return whether one operator is in the generic symbol-based family.

    This is the catch-all family for non-keyword overload spellings such as
    `+`, `-`, `*`, `/`, `%`, `==`, `!=`, `<`, `<=`, `>`, `>=`, `<=>`, `~`,
    `&`, `|`, `^`, `<<`, `>>`, `!`, `&&`, `||`, `=`, `+=`, `-=`, `*=`, `/=`,
    `%=`, `&=`, `|=`, `^=`, `<<=`, `>>=`, `++`, `--`, `()`, and `[]`.
    """

    return operator is not None and operator.kind == "symbolic"


def is_conversion_operator(operator: CppOperator | None) -> bool:
    """Return whether one operator is a conversion operator like `operator T`."""

    return operator is not None and operator.kind == "conversion"


def is_allocation_operator(operator: CppOperator | None) -> bool:
    """Return whether one operator is `operator new` or `operator new[]`."""

    return operator is not None and operator.kind == "allocation"


def is_deallocation_operator(operator: CppOperator | None) -> bool:
    """Return whether one operator is `operator delete` or `operator delete[]`."""

    return operator is not None and operator.kind == "deallocation"


def is_call_operator(operator: CppOperator | None) -> bool:
    """Return whether one operator overloads the `()` call syntax."""

    return is_symbolic_operator(operator) and operator.symbol == "()"


def is_index_operator(operator: CppOperator | None) -> bool:
    """Return whether one operator overloads the `[]` subscript syntax."""

    return is_symbolic_operator(operator) and operator.symbol == "[]"


def is_increment_decrement_operator(operator: CppOperator | None) -> bool:
    """Return whether one operator is `++` or `--`."""

    return is_symbolic_operator(operator) and operator.symbol in _INCREMENT_DECREMENT_OPERATOR_SYMBOLS


def is_comparison_operator(operator: CppOperator | None) -> bool:
    """Return whether one operator is one of `==`, `!=`, `<`, `<=`, `>`, `>=`, or `<=>`."""

    return is_symbolic_operator(operator) and operator.symbol in _COMPARISON_OPERATOR_SYMBOLS


def is_arithmetic_operator(operator: CppOperator | None) -> bool:
    """Return whether one operator is one of `+`, `-`, `*`, `/`, or `%`."""

    return is_symbolic_operator(operator) and operator.symbol in _ARITHMETIC_OPERATOR_SYMBOLS


def is_bitwise_operator(operator: CppOperator | None) -> bool:
    """Return whether one operator is one of `~`, `&`, `|`, `^`, `<<`, or `>>`."""

    return is_symbolic_operator(operator) and operator.symbol in _BITWISE_OPERATOR_SYMBOLS


def is_logical_operator(operator: CppOperator | None) -> bool:
    """Return whether one operator is one of `!`, `&&`, or `||`."""

    return is_symbolic_operator(operator) and operator.symbol in _LOGICAL_OPERATOR_SYMBOLS


def is_assignment_operator(operator: CppOperator | None) -> bool:
    """Return whether one operator is one of `=`, `+=`, `-=`, `*=`, `/=`, `%=`, `&=`, `|=`, `^=`, `<<=`, or `>>=`."""

    return is_symbolic_operator(operator) and operator.symbol in _ASSIGNMENT_OPERATOR_SYMBOLS
