from __future__ import annotations

"""Recover structured template-instantiated types from C++ spellings.

This module turns spellings such as `std::vector<int>`, `Box<Pair<int, Widget>>`,
or `std::array<int, 4>` into structured template type objects when recovery is
simple enough to do conservatively.
"""

import re
from typing import Any, Callable, Sequence

from ..model import (
    BuiltinCppType,
    CppNonTypeTemplateArgument,
    CppOpaqueTemplateArgument,
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
    """Recover one semantic `CppType` from one plain C++ spelling fragment.

    This is the context-free entrypoint used when parser code only has text,
    such as template parameter defaults or direct recovery tests. It does
    conservative local recovery only, and falls back to simpler named types
    instead of claiming full C++ template semantics.
    """

    return _build_type_from_spelling(spelling)


def build_template_argument_from_spelling(spelling: str) -> CppTemplateArgument:
    """Recover one template argument from one source spelling fragment.

    The result here is intentionally best-effort: obvious literal NTTPs become
    non-type arguments, recoverable type shapes become type arguments, and
    anything with trusted boundaries but unclear semantics becomes an opaque
    argument instead of a guessed semantic kind.
    """

    normalized = spelling.strip()
    if _looks_like_non_type_template_argument(normalized):
        return CppNonTypeTemplateArgument(value=normalized)

    recovered_type = _build_type_from_spelling(normalized)
    if _is_ambiguous_template_argument_type(recovered_type):
        return CppOpaqueTemplateArgument(spelling=normalized)
    return CppTypeTemplateArgument(type=recovered_type)


def _recover_template_instance_type(
    spelling: str,
    *,
    is_const: bool,
    direct_argument_types: Sequence[Any] | None = None,
    build_type_argument_type: Callable[[Any], CppType | None] | None = None,
    build_non_type_annotation: Callable[[Any], CppType | None] | None = None,
) -> TemplateInstanceCppType | None:
    """Recover one `Name<Args...>` spelling into one structured template type.

    This is the central recovery step shared by pure spelling recovery and the
    clang-backed `build_cpp_type()` path. It first splits trustworthy argument
    boundaries from spelling, then optionally refines ambiguous arguments with
    direct clang template-argument types when the caller can provide them.
    """

    normalized = spelling.strip()
    if not normalized.endswith(">") or "<" not in normalized:
        return None

    base_name, argument_text = _split_template_spelling(normalized)
    if base_name is None or argument_text is None:
        return None

    argument_spellings = _split_template_arguments(argument_text)
    if not argument_spellings:
        return None

    arguments = [build_template_argument_from_spelling(arg_spelling) for arg_spelling in argument_spellings]
    _enrich_template_arguments_with_direct_types(
        arguments,
        direct_argument_types,
        build_type_argument_type=build_type_argument_type,
        build_non_type_annotation=build_non_type_annotation,
    )
    return TemplateInstanceCppType(
        template_name=base_name,
        arguments=arguments,
        is_const=is_const,
    )


def _build_type_from_spelling(spelling: str) -> CppType:
    """Recover one semantic type from one spelling without any clang identity.

    This helper is the recursive backbone behind the public spelling entrypoint
    and nested template-argument recovery. It handles wrappers, top-level const
    normalization, conservative template recovery, builtin lookup, and finally
    the named-type fallback when no richer structure is safe to claim.
    """

    normalized = spelling.strip()
    wrapper_type = _build_wrapped_type_from_spelling(normalized)
    if wrapper_type is not None:
        return wrapper_type

    is_const = normalized.startswith("const ") or normalized.endswith(" const")
    normalized = _normalize_name_type_spelling(normalized, is_const=is_const)

    template_instance = _recover_template_instance_type(normalized, is_const=is_const)
    if template_instance is not None:
        return template_instance

    builtin_kind = cpp_builtin_kind_from_spelling(normalized)
    if builtin_kind is not None:
        return BuiltinCppType(kind=builtin_kind, is_const=is_const)

    return NamedCppType(name=normalized, is_const=is_const)


def _build_wrapped_type_from_spelling(spelling: str) -> CppType | None:
    """Recover one top-level pointer/reference wrapper from one spelling.

    Template recovery needs this before named-type fallback so common spellings
    like `T const*` or `U&&` keep their outer wrapper shape even when the inner
    spelling later falls back to a named type or an opaque template argument.
    """

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


def _split_template_spelling(spelling: str) -> tuple[str | None, str | None]:
    """Split one outer template-instantiation spelling into name and arg text.

    This does not try to understand argument meaning; it only finds the outer
    `Name<...>` shell when that shell is trustworthy. Callers use it as the
    first gate before attempting any deeper template-argument recovery.
    """

    span = _find_outer_template_argument_span(spelling)
    if span is None:
        return None, None

    start_index, end_index = span
    base_name = spelling[:start_index].strip()
    argument_text = spelling[start_index + 1:end_index].strip()
    return base_name, argument_text


def _split_template_arguments(argument_text: str) -> list[str]:
    """Split one template argument list into top-level argument spellings.

    This is deliberately a boundary finder, not a full C++ template parser. It
    tracks nested delimiters and quoted strings so common cases stay
    recoverable, but returns failure when boundaries are suspicious rather than
    inventing a partial parse that later code might mistake for semantic truth.
    """

    if not argument_text:
        return []

    arguments: list[str] = []
    current: list[str] = []
    delimiter_stack: list[str] = []
    in_string: str | None = None
    escaped = False

    for character in argument_text:
        if in_string is not None:
            current.append(character)
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == in_string:
                in_string = None
            continue

        if character in {"'", '"'}:
            in_string = character
            current.append(character)
            continue

        if character in _OPEN_DELIMITERS:
            delimiter_stack.append(character)
            current.append(character)
            continue

        if character in _CLOSE_DELIMITERS:
            if not delimiter_stack:
                return []
            opener = delimiter_stack.pop()
            if _DELIMITER_PAIRS[opener] != character:
                return []
            current.append(character)
            continue

        if character == "," and not delimiter_stack:
            argument = "".join(current).strip()
            if argument:
                arguments.append(argument)
            current = []
            continue
        current.append(character)

    if in_string is not None or delimiter_stack:
        return []

    tail = "".join(current).strip()
    if tail:
        arguments.append(tail)

    return arguments


def _looks_like_non_type_template_argument(spelling: str) -> bool:
    """Return whether one argument spelling is an obvious literal-style NTTP.

    This narrow check exists to recognize the easy cases safely: integer,
    floating, char, string, boolean, and `nullptr` spellings. Anything less
    obvious is left for opaque-argument fallback or clang-backed refinement
    rather than guessed from spelling alone.
    """

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


def _is_ambiguous_template_argument_type(cpp_type: CppType) -> bool:
    """Return whether recovered type shape is too weak to claim a type argument.

    In practice this marks plain named spellings as ambiguous in the
    context-free path, because `Widget`, `N`, or `Box` cannot safely be
    classified from text alone. More precise callers can still refine these
    later with direct clang argument types.
    """

    return isinstance(cpp_type, NamedCppType)


def _enrich_template_arguments_with_direct_types(
    arguments: list[CppTemplateArgument],
    direct_argument_types: Sequence[Any] | None,
    *,
    build_type_argument_type: Callable[[Any], CppType | None] | None,
    build_non_type_annotation: Callable[[Any], CppType | None] | None,
) -> None:
    """Refine recovered arguments with direct clang template-argument types.

    This is the bridge between conservative spelling recovery and libclang's
    partial semantic knowledge. It upgrades opaque arguments into typed ones
    when clang proves the slot is a type, or keeps the original spelling as a
    non-type argument with an annotation when clang only supplies value-type info.
    """

    if direct_argument_types is None:
        return

    for index, direct_type in enumerate(direct_argument_types):
        if index >= len(arguments):
            break
        if direct_type is None:
            continue

        argument = arguments[index]

        if isinstance(argument, CppTypeTemplateArgument):
            if build_type_argument_type is None:
                continue
            refined_type = build_type_argument_type(direct_type)
            if _has_meaningful_type_information(refined_type):
                arguments[index] = CppTypeTemplateArgument(type=refined_type)
            continue

        if isinstance(argument, CppOpaqueTemplateArgument):
            if build_type_argument_type is None:
                continue
            refined_type = build_type_argument_type(direct_type)
            if not _has_meaningful_type_information(refined_type):
                continue

            if _opaque_spelling_matches_type_candidate(argument.spelling, refined_type):
                arguments[index] = CppTypeTemplateArgument(type=refined_type)
                continue

            annotation = (
                build_non_type_annotation(direct_type)
                if build_non_type_annotation is not None
                else refined_type
            )
            if _has_meaningful_type_information(annotation):
                arguments[index] = CppNonTypeTemplateArgument(
                    value=argument.spelling,
                    type=annotation,
                )
            continue

        if isinstance(argument, CppNonTypeTemplateArgument) and argument.type is None:
            annotation = (
                build_non_type_annotation(direct_type)
                if build_non_type_annotation is not None
                else None
            )
            if _has_meaningful_type_information(annotation):
                arguments[index] = CppNonTypeTemplateArgument(
                    value=argument.value,
                    type=annotation,
                )


def _has_meaningful_type_information(cpp_type: CppType | None) -> bool:
    """Return whether one refined clang-backed type carries usable semantic information."""

    if cpp_type is None:
        return False
    if isinstance(cpp_type, NamedCppType):
        return bool(cpp_type.name)
    return True


def _opaque_spelling_matches_type_candidate(spelling: str, cpp_type: CppType) -> bool:
    """Check whether clang-refined type info still matches one opaque spelling.

    Libclang may expose only a type object for a template slot, even when that
    slot could also be a non-type argument with an annotation type. This helper
    uses small local spelling checks to decide whether we should upgrade the
    opaque argument to a true type argument or keep its original value spelling.
    """

    normalized_spelling = _normalize_spelling(spelling)
    candidate_spellings = {_normalize_spelling(cpp_type.render())}

    if isinstance(cpp_type, NamedCppType):
        candidate_spellings.add(_terminal_name(_normalize_spelling(cpp_type.name)))
        if cpp_type.declaration is not None:
            candidate_spellings.add(_terminal_name(_normalize_spelling(cpp_type.declaration.qualified_name)))
    elif isinstance(cpp_type, TemplateInstanceCppType):
        candidate_spellings.add(_terminal_name(_normalize_spelling(cpp_type.template_name)))

    if normalized_spelling in candidate_spellings:
        return True
    return _terminal_name(normalized_spelling) in candidate_spellings


def _find_outer_template_argument_span(spelling: str) -> tuple[int, int] | None:
    """Return the outermost trailing `<...>` span for one template spelling.

    This is the structural guard that ensures we only treat a spelling as one
    template instantiation when the outer angle-bracket pair closes at the end
    of the fragment. If that shell is malformed or interrupted, callers bail
    out before attempting any argument-level recovery.
    """

    delimiter_stack: list[str] = []
    start_index: int | None = None
    in_string: str | None = None
    escaped = False

    for index, character in enumerate(spelling):
        if in_string is not None:
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == in_string:
                in_string = None
            continue

        if character in {"'", '"'}:
            in_string = character
            continue

        if character in _OPEN_DELIMITERS:
            if character == "<" and not delimiter_stack:
                start_index = index
            delimiter_stack.append(character)
            continue

        if character in _CLOSE_DELIMITERS:
            if not delimiter_stack:
                return None
            opener = delimiter_stack.pop()
            if _DELIMITER_PAIRS[opener] != character:
                return None
            if opener == "<" and not delimiter_stack:
                if start_index is None or index != len(spelling) - 1:
                    return None
                return start_index, index

    return None


def _normalize_spelling(spelling: str) -> str:
    """Normalize one recovered argument spelling for semantic comparisons."""

    return "".join(spelling.split())


def _terminal_name(spelling: str) -> str:
    """Return the terminal component of one normalized qualified spelling."""

    return spelling.split("::")[-1]


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

_DELIMITER_PAIRS = {
    "<": ">",
    "(": ")",
    "[": "]",
    "{": "}",
}
_OPEN_DELIMITERS = frozenset(_DELIMITER_PAIRS)
_CLOSE_DELIMITERS = frozenset(_DELIMITER_PAIRS.values())
