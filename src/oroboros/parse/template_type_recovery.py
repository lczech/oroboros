from __future__ import annotations

"""Recover structured template-instantiated types from C++ spellings.

This module turns spellings such as `std::vector<int>`, `Box<Pair<int, Widget>>`,
or `std::array<int, 4>` into structured template type objects when recovery is
simple enough to do conservatively.
"""

import re

from ..model import (
    BuiltinCppType,
    CppNonTypeTemplateArgument,
    CppTemplateArgument,
    CppType,
    CppTypeTemplateArgument,
    LValueReferenceCppType,
    NamedCppType,
    PointerCppType,
    RValueReferenceCppType,
    TemplateInstanceCppType,
)
from ..model.type import cpp_builtin_kind_from_spelling


def build_cpp_type_from_spelling(spelling: str) -> CppType:
    """Build one semantic C++ type from one source spelling fragment."""

    return _build_type_from_spelling(spelling)


def build_template_argument_from_spelling(spelling: str) -> CppTemplateArgument:
    """Build one structured template argument from one source spelling fragment."""

    normalized = spelling.strip()
    if _looks_like_non_type_template_argument(normalized):
        return CppNonTypeTemplateArgument(value=normalized)

    return CppTypeTemplateArgument(type=_build_type_from_spelling(normalized))


def _build_type_from_spelling(spelling: str) -> CppType:
    """Build one fallback semantic type from one plain C++ spelling fragment."""

    normalized = spelling.strip()
    wrapper_type = _build_wrapped_type_from_spelling(normalized)
    if wrapper_type is not None:
        return wrapper_type

    is_const = normalized.startswith("const ") or normalized.endswith(" const")
    normalized = _normalize_name_type_spelling(normalized, is_const=is_const)

    template_instance = _parse_template_instance_spelling(normalized, is_const=is_const)
    if template_instance is not None:
        return template_instance

    builtin_kind = cpp_builtin_kind_from_spelling(normalized)
    if builtin_kind is not None:
        return BuiltinCppType(kind=builtin_kind, is_const=is_const)

    return NamedCppType(name=normalized, is_const=is_const)


def _build_wrapped_type_from_spelling(spelling: str) -> CppType | None:
    """Build one top-level pointer/reference wrapper type from one spelling when present."""

    without_const, is_const = _strip_trailing_const(spelling)
    for suffix, wrapper_builder in _WRAPPER_BUILDERS:
        if not without_const.endswith(suffix):
            continue
        inner_spelling = without_const[:-len(suffix)]
        return wrapper_builder(_build_type_from_spelling(inner_spelling), is_const)
    return None


def _strip_trailing_const(spelling: str) -> tuple[str, bool]:
    """Strip one trailing top-level `const` qualifier from one spelling when present."""

    if spelling.endswith(" const"):
        return spelling[:-len(" const")].rstrip(), True
    return spelling, False


def _normalize_name_type_spelling(
    spelling: str,
    *,
    is_const: bool,
) -> str:
    """Normalize one named-type spelling so top-level const lives only in `is_const`."""

    normalized = spelling.strip()
    if not is_const:
        return normalized

    if normalized.startswith("const "):
        return normalized[len("const "):].strip()

    if normalized.endswith(" const"):
        return normalized[:-len(" const")].strip()

    return normalized


def _parse_template_instance_spelling(
    spelling: str,
    *,
    is_const: bool,
) -> TemplateInstanceCppType | None:
    """Parse one simple template-instantiation spelling into one structured type."""

    normalized = spelling.strip()
    if not normalized.endswith(">") or "<" not in normalized:
        return None

    base_name, argument_text = _split_template_spelling(normalized)
    if base_name is None or argument_text is None:
        return None

    argument_spellings = _split_template_arguments(argument_text)
    if not argument_spellings or not _template_argument_spellings_are_recoverable(argument_spellings):
        return None

    return TemplateInstanceCppType(
        template_name=base_name,
        arguments=[build_template_argument_from_spelling(spelling) for spelling in argument_spellings],
        is_const=is_const,
    )


def _template_argument_spellings_are_recoverable(argument_spellings: list[str]) -> bool:
    """Return whether all recovered argument spellings are safe for simple structural parsing."""

    for spelling in argument_spellings:
        if not spelling.strip():
            return False
        if any(character in spelling for character in "()[]{}'\""):
            return False
    return True


def _split_template_spelling(spelling: str) -> tuple[str | None, str | None]:
    """Split one `Name<Args...>` spelling into base name and inner argument text."""

    depth = 0
    start_index = None
    for index, character in enumerate(spelling):
        if character == "<":
            if depth == 0:
                start_index = index
            depth += 1
        elif character == ">":
            depth -= 1
            if depth == 0 and start_index is not None:
                base_name = spelling[:start_index].strip()
                argument_text = spelling[start_index + 1:index].strip()
                if index != len(spelling) - 1:
                    return None, None
                return base_name, argument_text

    return None, None


def _split_template_arguments(argument_text: str) -> list[str]:
    """Split one template argument list text into top-level argument spellings."""

    arguments: list[str] = []
    current: list[str] = []
    depth = 0

    for character in argument_text:
        if character == "<":
            depth += 1
        elif character == ">":
            depth -= 1
        elif character == "," and depth == 0:
            argument = "".join(current).strip()
            if argument:
                arguments.append(argument)
            current = []
            continue
        current.append(character)

    tail = "".join(current).strip()
    if tail:
        arguments.append(tail)

    return arguments


def _looks_like_non_type_template_argument(spelling: str) -> bool:
    """Return whether one template-argument spelling looks like one value expression."""

    normalized = spelling.strip()
    if not normalized:
        return False

    if normalized in {"true", "false", "nullptr"}:
        return True

    if _INTEGER_LITERAL_RE.fullmatch(normalized):
        return True

    if _FLOAT_LITERAL_RE.fullmatch(normalized):
        return True

    if _CHAR_LITERAL_RE.fullmatch(normalized):
        return True

    if _STRING_LITERAL_RE.fullmatch(normalized):
        return True

    return False


_INTEGER_LITERAL_RE = re.compile(
    r"""
    [+-]?
    (?:
        0[xX][0-9A-Fa-f]+ |
        0[bB][01]+ |
        0[0-7]* |
        [1-9][0-9]*
    )
    (?:[uU](?:ll|LL|l|L)?|(?:ll|LL|l|L)[uU]?)?
    """,
    re.VERBOSE,
)

_FLOAT_LITERAL_RE = re.compile(
    r"""
    [+-]?
    (?:
        (?:[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)? |
        [0-9]+[eE][+-]?[0-9]+
    )
    [fFlL]?
    """,
    re.VERBOSE,
)

_CHAR_LITERAL_RE = re.compile(r"(?:u8|u|U|L)?'(?:\\.|[^'\\])+'")
_STRING_LITERAL_RE = re.compile(r'(?:u8|u|U|L)?\"(?:\\.|[^\"\\])*\"')


def _build_pointer_type(inner: CppType, is_const: bool) -> PointerCppType:
    """Wrap one inner type in one pointer type."""

    return PointerCppType(pointee=inner, is_const=is_const)


def _build_lvalue_reference_type(inner: CppType, is_const: bool) -> LValueReferenceCppType:
    """Wrap one inner type in one lvalue-reference type."""

    return LValueReferenceCppType(referred=inner, is_const=is_const)


def _build_rvalue_reference_type(inner: CppType, is_const: bool) -> RValueReferenceCppType:
    """Wrap one inner type in one rvalue-reference type."""

    return RValueReferenceCppType(referred=inner, is_const=is_const)


_WRAPPER_BUILDERS = (
    ("&&", _build_rvalue_reference_type),
    ("&", _build_lvalue_reference_type),
    ("*", _build_pointer_type),
)
