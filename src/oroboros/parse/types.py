from __future__ import annotations

"""Translate clang type objects into the semantic C++ type model."""

from copy import deepcopy
import re
from typing import TYPE_CHECKING, Any

from clang.cindex import CursorKind, TypeKind

from ..model import (
    ArrayCppType,
    BuiltinCppType,
    CppNonTypeTemplateArgument,
    CppObservedTemplateInstance,
    CppTypeTemplateParameter,
    CppTemplateArgument,
    CppTypeTemplateArgument,
    CppType,
    FunctionCppType,
    LValueReferenceCppType,
    NamedCppType,
    PointerCppType,
    RValueReferenceCppType,
    TemplateInstanceCppType,
)
from ..model.template_ import _template_argument_key
from ..model.type import cpp_builtin_kind_from_spelling
from .cursor_data import cursor_source_location

if TYPE_CHECKING:
    from .build_model import BuildContext


# ==================================================================================================
#     Public Type Builder
# ==================================================================================================


def build_cpp_type(
    clang_type: Any,
    *,
    context: BuildContext | None = None,
    source_cursor: Any | None = None,
) -> CppType | None:
    """Convert one clang type object into the structured semantic type model."""

    if clang_type is None:
        return None

    return _build_cpp_type(
        clang_type,
        allow_canonical=True,
        context=context,
        source_cursor=source_cursor,
    )


def _build_cpp_type(
    clang_type: Any,
    *,
    allow_canonical: bool,
    context: BuildContext | None,
    source_cursor: Any | None,
) -> CppType | None:
    """Recursively convert one clang type while avoiding canonical recursion loops."""

    is_const = _call_optional_bool_method(clang_type, "is_const_qualified")

    builtin_kind = _clang_builtin_kind(clang_type)
    if builtin_kind is not None:
        return BuiltinCppType(kind=builtin_kind, is_const=is_const)

    if _type_kind_matches(clang_type, TypeKind.POINTER):
        return PointerCppType(
            pointee=_build_cpp_type(
                _call_optional_method(clang_type, "get_pointee"),
                allow_canonical=allow_canonical,
                context=context,
                source_cursor=source_cursor,
            ),
            is_const=is_const,
        )

    if _type_kind_matches(clang_type, TypeKind.LVALUEREFERENCE):
        return LValueReferenceCppType(
            referred=_build_cpp_type(
                _call_optional_method(clang_type, "get_pointee"),
                allow_canonical=allow_canonical,
                context=context,
                source_cursor=source_cursor,
            ),
            is_const=is_const,
        )

    if _type_kind_matches(clang_type, TypeKind.RVALUEREFERENCE):
        return RValueReferenceCppType(
            referred=_build_cpp_type(
                _call_optional_method(clang_type, "get_pointee"),
                allow_canonical=allow_canonical,
                context=context,
                source_cursor=source_cursor,
            ),
            is_const=is_const,
        )

    if _type_kind_matches(clang_type, *_ARRAY_KINDS):
        return ArrayCppType(
            element_type=_build_cpp_type(
                _call_optional_method(clang_type, "get_array_element_type"),
                allow_canonical=allow_canonical,
                context=context,
                source_cursor=source_cursor,
            ),
            extent=_get_array_extent(clang_type),
            is_const=is_const,
        )

    if _type_kind_matches(clang_type, *_FUNCTION_KINDS):
        return FunctionCppType(
            return_type=_build_cpp_type(
                _call_optional_method(clang_type, "get_result"),
                allow_canonical=allow_canonical,
                context=context,
                source_cursor=source_cursor,
            ),
            parameters=[
                _build_cpp_type(
                    parameter_type,
                    allow_canonical=allow_canonical,
                    context=context,
                    source_cursor=source_cursor,
                )
                for parameter_type in _call_optional_method(clang_type, "argument_types", [])
            ],
            is_variadic=_call_optional_bool_method(clang_type, "is_function_variadic"),
            is_const=is_const,
        )

    spelling = _normalize_name_type_spelling(
        _type_spelling(clang_type),
        is_const=is_const,
    )
    template_instance = _parse_template_instance_spelling(spelling, is_const=is_const)
    if template_instance is not None:
        # The current template fallback still parses structure from spelling.
        # Use any libclang-exposed template-argument types only to enrich that
        # temporary result with declaration links and canonical nested types.
        _enrich_fallback_type_from_clang(template_instance, clang_type, context)
        _record_observed_template_instance(
            template_instance,
            clang_type,
            context,
            source_cursor=source_cursor,
        )
        return template_instance

    canonical = None
    if allow_canonical:
        canonical_type = _call_optional_method(clang_type, "get_canonical")
        if canonical_type is not None and not _same_type_identity(clang_type, canonical_type):
            canonical = _build_cpp_type(
                canonical_type,
                allow_canonical=False,
                context=context,
                source_cursor=None,
            )

    named_type = NamedCppType(
        name=spelling,
        canonical=canonical,
        is_const=is_const,
    )
    _record_named_type_declaration_link(
        named_type,
        clang_type,
        context,
        source_cursor=source_cursor,
    )
    return named_type


# ==================================================================================================
#     Spelling-Based Fallback Parsing
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Template Instance Spellings
# ------------------------------------------------------------------------------


def _parse_template_instance_spelling(
    spelling: str,
    *,
    is_const: bool,
) -> TemplateInstanceCppType | None:
    """Parse one simple template-instantiation spelling into a structured type."""

    normalized = spelling.strip()
    if not normalized.endswith(">") or "<" not in normalized:
        return None

    base_name, argument_text = _split_template_spelling(normalized)
    if base_name is None or argument_text is None:
        return None

    argument_spellings = _split_template_arguments(argument_text)
    if not argument_spellings:
        return None

    return TemplateInstanceCppType(
        template_name=base_name,
        arguments=[build_template_argument_from_spelling(argument_spelling) for argument_spelling in argument_spellings],
        is_const=is_const,
    )


def _build_type_from_spelling(spelling: str) -> CppType:
    """Build one fallback semantic type from a plain C++ spelling fragment."""

    normalized = spelling.strip()

    # Peel top-level wrapper constness before normalizing inner named-type spellings.
    if normalized.endswith(" const"):
        without_const = normalized[:-len(" const")].rstrip()

        if without_const.endswith("&&"):
            return RValueReferenceCppType(
                referred = _build_type_from_spelling(without_const[:-2]),
                is_const = True,
            )

        if without_const.endswith("&"):
            return LValueReferenceCppType(
                referred = _build_type_from_spelling(without_const[:-1]),
                is_const = True,
            )

        if without_const.endswith("*"):
            return PointerCppType(
                pointee = _build_type_from_spelling(without_const[:-1]),
                is_const = True,
            )

    if normalized.endswith("&&"):
        return RValueReferenceCppType(
            referred = _build_type_from_spelling(normalized[:-2]),
            is_const = False,
        )

    if normalized.endswith("&"):
        return LValueReferenceCppType(
            referred = _build_type_from_spelling(normalized[:-1]),
            is_const = False,
        )

    if normalized.endswith("*"):
        return PointerCppType(
            pointee = _build_type_from_spelling(normalized[:-1]),
            is_const = False,
        )

    is_const = normalized.startswith("const ") or normalized.endswith(" const")
    normalized = _normalize_name_type_spelling(normalized, is_const=is_const)

    template_instance = _parse_template_instance_spelling(normalized, is_const=is_const)
    if template_instance is not None:
        return template_instance

    builtin_kind = cpp_builtin_kind_from_spelling(normalized)
    if builtin_kind is not None:
        return BuiltinCppType(kind=builtin_kind, is_const=is_const)

    return NamedCppType(name=normalized, is_const=is_const)


def build_template_argument_from_spelling(spelling: str) -> CppTemplateArgument:
    """Build one structured template argument from one source spelling fragment."""

    normalized = spelling.strip()
    if _looks_like_non_type_template_argument(normalized):
        return CppNonTypeTemplateArgument(value=normalized)

    return CppTypeTemplateArgument(
        type=_build_type_from_spelling(normalized),
    )


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


def _enrich_fallback_type_from_clang(
    cpp_type: CppType | None,
    clang_type: Any,
    context: BuildContext | None,
) -> None:
    """Attach declaration links and canonical info to one spelling-parsed fallback type."""
    # This is temporary, before we have more complete clang-based parsing for template instances.

    if cpp_type is None or clang_type is None:
        return

    if isinstance(cpp_type, NamedCppType):
        if context is not None:
            _record_named_type_declaration_link(cpp_type, clang_type, context)
        if cpp_type.canonical is None:
            canonical_type = _call_optional_method(clang_type, "get_canonical")
            if canonical_type is not None and not _same_type_identity(clang_type, canonical_type):
                cpp_type.canonical = _build_cpp_type(
                    canonical_type,
                    allow_canonical=False,
                    context=context,
                    source_cursor=None,
                )
        return

    if isinstance(cpp_type, PointerCppType):
        _enrich_fallback_type_from_clang(
            cpp_type.pointee,
            _call_optional_method(clang_type, "get_pointee"),
            context,
        )
        return

    if isinstance(cpp_type, LValueReferenceCppType | RValueReferenceCppType):
        _enrich_fallback_type_from_clang(
            cpp_type.referred,
            _call_optional_method(clang_type, "get_pointee"),
            context,
        )
        return

    if isinstance(cpp_type, ArrayCppType):
        _enrich_fallback_type_from_clang(
            cpp_type.element_type,
            _call_optional_method(clang_type, "get_array_element_type"),
            context,
        )
        return

    if isinstance(cpp_type, FunctionCppType):
        _enrich_fallback_type_from_clang(
            cpp_type.return_type,
            _call_optional_method(clang_type, "get_result"),
            context,
        )
        argument_types = list(_call_optional_method(clang_type, "argument_types", []))
        if len(argument_types) != len(cpp_type.parameters):
            return
        for parameter_type, argument_type in zip(
            cpp_type.parameters,
            argument_types,
            strict=True,
        ):
            _enrich_fallback_type_from_clang(parameter_type, argument_type, context)
        return

    if isinstance(cpp_type, TemplateInstanceCppType):
        template_argument_types = _template_argument_types(clang_type)
        if len(template_argument_types) != len(cpp_type.arguments):
            return
        for argument, template_argument_type in zip(
            cpp_type.arguments,
            template_argument_types,
            strict=True,
        ):
            _enrich_fallback_template_argument_from_clang(argument, template_argument_type, context)


def _enrich_fallback_template_argument_from_clang(
    argument: CppTemplateArgument,
    clang_type: Any,
    context: BuildContext | None,
) -> None:
    """Attach clang-exposed semantic detail to one spelling-parsed template argument."""

    if isinstance(argument, CppTypeTemplateArgument):
        _enrich_fallback_type_from_clang(argument.type, clang_type, context)
        return

    if isinstance(argument, CppNonTypeTemplateArgument):
        argument.type = _build_cpp_type(
            clang_type,
            allow_canonical=True,
            context=context,
            source_cursor=None,
        )


# ------------------------------------------------------------------------------
#     Template Spelling Splitting
# ------------------------------------------------------------------------------


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


def _template_argument_types(clang_type: Any) -> list[Any]:
    """Return clang template argument types when libclang exposes them."""

    get_argument_count = getattr(clang_type, "get_num_template_arguments", None)
    get_argument_type = getattr(clang_type, "get_template_argument_type", None)
    if not callable(get_argument_count) or not callable(get_argument_type):
        return []

    argument_count = get_argument_count()
    if not isinstance(argument_count, int) or argument_count < 0:
        return []

    argument_types: list[Any] = []
    for index in range(argument_count):
        argument_types.append(get_argument_type(index))

    return argument_types


def _looks_like_non_type_template_argument(spelling: str) -> bool:
    """Return whether one template-argument spelling looks like a value expression."""

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


# ==================================================================================================
#     Clang Type Introspection
# ==================================================================================================


def _clang_builtin_kind(clang_type: Any) -> str | None:
    """Return one semantic builtin kind for one clang builtin type."""

    actual_kind = getattr(clang_type, "kind", None)
    if actual_kind is None:
        return None

    return _CLANG_BUILTIN_KIND_MAP.get(actual_kind)


def _type_kind_matches(clang_type: Any, *expected_kinds: Any) -> bool:
    """Return whether one clang type matches any expected libclang type kinds."""

    actual_kind = getattr(clang_type, "kind", None)
    if actual_kind is None:
        return False
    return actual_kind in expected_kinds


_CLANG_BUILTIN_KIND_MAP: dict[Any, str] = {
    TypeKind.VOID: "void",
    TypeKind.NULLPTR: "nullptr_t",
    TypeKind.BOOL: "bool",
    TypeKind.CHAR_U: "char",
    TypeKind.UCHAR: "unsigned_char",
    TypeKind.CHAR16: "char16_t",
    TypeKind.CHAR32: "char32_t",
    TypeKind.USHORT: "unsigned_short",
    TypeKind.UINT: "unsigned_int",
    TypeKind.ULONG: "unsigned_long",
    TypeKind.ULONGLONG: "unsigned_long_long",
    TypeKind.CHAR_S: "char",
    TypeKind.SCHAR: "signed_char",
    TypeKind.WCHAR: "wchar_t",
    TypeKind.SHORT: "short",
    TypeKind.INT: "int",
    TypeKind.LONG: "long",
    TypeKind.LONGLONG: "long_long",
    TypeKind.FLOAT: "float",
    TypeKind.DOUBLE: "double",
    TypeKind.LONGDOUBLE: "long_double",
}

_ARRAY_KINDS = frozenset({TypeKind.CONSTANTARRAY, TypeKind.INCOMPLETEARRAY})
_FUNCTION_KINDS = frozenset({TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO})


def _type_kind_name(clang_type: Any) -> str:
    """Return one normalized libclang type-kind name.

    Libclang exposes these enum names in uppercase forms such as `POINTER`,
    `FUNCTIONPROTO`, and `LVALUEREFERENCE`. The parser mainly matches against
    the enum members themselves, while this helper keeps reporting and test
    fallbacks readable.
    """

    kind = getattr(clang_type, "kind", None)
    name = getattr(kind, "name", None)
    if name is not None:
        return str(name)
    return str(kind)


def _type_spelling(clang_type: Any) -> str:
    """Return one normalized type spelling string."""

    return str(getattr(clang_type, "spelling", "")).strip()


# ==================================================================================================
#     Declaration Recording
# ==================================================================================================


def _call_optional_method(clang_type: Any, method_name: str, default: Any = None) -> Any:
    """Call one optional libclang type method, returning a default when absent."""

    method = getattr(clang_type, method_name, None)
    if callable(method):
        return method()
    return default


def _call_optional_bool_method(clang_type: Any, method_name: str) -> bool:
    """Call one optional libclang type predicate and normalize it to `bool`."""

    return bool(_call_optional_method(clang_type, method_name, False))


def _record_named_type_declaration_link(
    cpp_type: NamedCppType,
    clang_type: Any,
    context: BuildContext | None,
    *,
    source_cursor: Any | None = None,
) -> None:
    """Capture one referenced declaration USR for a named type when available."""

    if context is None:
        return

    declaration_cursor = _call_optional_method(clang_type, "get_declaration")
    if declaration_cursor is None:
        return

    declaration_location = cursor_source_location(declaration_cursor)
    if declaration_location is not None:
        declaration_file = declaration_location.file.resolve()
        if (
            declaration_file not in context.active_headers
            and declaration_file in context.known_project_headers
        ):
            _record_inactive_project_type_reference_warning(
                cpp_type,
                declaration_location=declaration_location,
                source_cursor=source_cursor,
                context=context,
            )
            return

    declaration_usr = _cursor_usr(declaration_cursor)
    if declaration_usr is None:
        return

    from .build_model import PendingTypeDeclarationLink

    context.pending_type_declaration_links.append(
        PendingTypeDeclarationLink(
            cpp_type=cpp_type,
            declaration_usr=declaration_usr,
        )
    )
def _record_inactive_project_type_reference_warning(
    cpp_type: NamedCppType,
    *,
    declaration_location: Any,
    source_cursor: Any | None,
    context: BuildContext,
) -> None:
    """Warn when an active declaration references a known inactive project type."""

    use_location = cursor_source_location(source_cursor) if source_cursor is not None else None
    rendered_use_location = _format_source_location_for_warning(use_location)
    rendered_declaration_location = _format_source_location_for_warning(declaration_location)
    warning = (
        f"Active declaration at {rendered_use_location} references known project type "
        f"{cpp_type.name!r} from inactive header {rendered_declaration_location}; "
        "preserving the type spelling without materializing that declaration."
    )
    if warning not in context.semantic_warnings:
        context.semantic_warnings.append(warning)


def _format_source_location_for_warning(location: Any) -> str:
    """Render one optional source location into a short stable warning string."""

    if location is None:
        return "<unknown location>"
    return f"{location.file}:{location.line}:{location.column}"


def _record_observed_template_instance(
    cpp_type: TemplateInstanceCppType,
    clang_type: Any,
    context: BuildContext | None,
    *,
    source_cursor: Any | None,
) -> None:
    """Attach one declaration-surface template instance observation to a parsed family."""

    if context is None:
        return

    _record_one_observed_template_instance(
        cpp_type,
        clang_type,
        context,
        source_cursor=source_cursor,
    )

    template_argument_types = _template_argument_types_with_canonical_fallback(clang_type)
    if len(template_argument_types) != len(cpp_type.arguments):
        return

    for argument, template_argument_type in zip(
        cpp_type.arguments,
        template_argument_types,
        strict=True,
    ):
        if not isinstance(argument, CppTypeTemplateArgument) or argument.type is None:
            continue
        _record_observed_template_instances_in_type(
            argument.type,
            template_argument_type,
            context,
            source_cursor=source_cursor,
        )


def _record_one_observed_template_instance(
    cpp_type: TemplateInstanceCppType,
    clang_type: Any,
    context: BuildContext,
    *,
    source_cursor: Any | None,
) -> None:
    """Record one concrete template instance at the current type node only."""

    template_cursor = _specialized_template_cursor(clang_type)
    source_template_cursor = _template_cursor_from_source_reference(
        cpp_type,
        source_cursor=source_cursor,
    )
    if (
        source_template_cursor is not None
        and (
            template_cursor is None
            or not _template_cursor_matches_spelled_name(template_cursor, cpp_type)
        )
    ):
        template_cursor = source_template_cursor
    if template_cursor is None:
        return

    template_usr = _cursor_usr(template_cursor)
    if template_usr is None:
        return

    template_family = context.usr_to_element.get(template_usr)
    if template_family is None or not hasattr(template_family, "declaration"):
        return

    declaration = getattr(template_family, "declaration", None)
    if declaration is None or not hasattr(declaration, "cpp"):
        return

    observed_instances = declaration.cpp.observed_instances
    complete_arguments = _complete_observed_template_arguments_from_clang(
        cpp_type.arguments,
        clang_type,
        declaration.cpp.template_parameters,
        context,
    )
    argument_key = _template_argument_key(complete_arguments)
    observation_location = cursor_source_location(source_cursor) if source_cursor is not None else None

    for observed_instance in observed_instances:
        if _template_argument_key(observed_instance.arguments) != argument_key:
            continue
        if observation_location is not None and observation_location not in observed_instance.locations:
            observed_instance.locations.append(observation_location)
        return

    observed_instances.append(
        CppObservedTemplateInstance(
            arguments=deepcopy(complete_arguments),
            locations=[] if observation_location is None else [observation_location],
        )
    )


def _template_cursor_from_source_reference(
    cpp_type: TemplateInstanceCppType,
    *,
    source_cursor: Any | None,
) -> Any | None:
    """Recover one template cursor from declaration-surface `TEMPLATE_REF` children."""

    if source_cursor is None:
        return None

    template_terminal_name = cpp_type.template_name.split("::")[-1].strip()
    for child_cursor in _call_optional_method(source_cursor, "get_children", []):
        if getattr(child_cursor, "kind", None) != CursorKind.TEMPLATE_REF:
            continue
        if child_cursor.spelling != template_terminal_name:
            continue
        referenced_cursor = getattr(child_cursor, "referenced", None)
        if getattr(referenced_cursor, "kind", None) in {
            CursorKind.TYPE_ALIAS_TEMPLATE_DECL,
            CursorKind.CLASS_TEMPLATE,
            CursorKind.FUNCTION_TEMPLATE,
        }:
            return referenced_cursor
    return None


def _template_cursor_matches_spelled_name(
    template_cursor: Any,
    cpp_type: TemplateInstanceCppType,
) -> bool:
    """Return whether one template cursor matches the source-spelled template name."""

    cursor_name = getattr(template_cursor, "spelling", "").strip()
    type_terminal_name = cpp_type.template_name.split("::")[-1].strip()
    return bool(cursor_name) and cursor_name == type_terminal_name


def _record_observed_template_instances_in_type(
    cpp_type: CppType | None,
    clang_type: Any,
    context: BuildContext,
    *,
    source_cursor: Any | None,
) -> None:
    """Record nested template-instance observations reachable through one type node."""

    if cpp_type is None or clang_type is None:
        return

    if isinstance(cpp_type, TemplateInstanceCppType):
        _record_observed_template_instance(
            cpp_type,
            clang_type,
            context,
            source_cursor=source_cursor,
        )
        return

    if isinstance(cpp_type, PointerCppType):
        _record_observed_template_instances_in_type(
            cpp_type.pointee,
            _call_optional_method(clang_type, "get_pointee"),
            context,
            source_cursor=source_cursor,
        )
        return

    if isinstance(cpp_type, LValueReferenceCppType | RValueReferenceCppType):
        _record_observed_template_instances_in_type(
            cpp_type.referred,
            _call_optional_method(clang_type, "get_pointee"),
            context,
            source_cursor=source_cursor,
        )
        return

    if isinstance(cpp_type, ArrayCppType):
        _record_observed_template_instances_in_type(
            cpp_type.element_type,
            _call_optional_method(clang_type, "get_array_element_type"),
            context,
            source_cursor=source_cursor,
        )
        return

    if isinstance(cpp_type, FunctionCppType):
        _record_observed_template_instances_in_type(
            cpp_type.return_type,
            _call_optional_method(clang_type, "get_result"),
            context,
            source_cursor=source_cursor,
        )
        argument_types = list(_call_optional_method(clang_type, "argument_types", []))
        if len(argument_types) != len(cpp_type.parameters):
            return
        for parameter_type, argument_type in zip(
            cpp_type.parameters,
            argument_types,
            strict=True,
        ):
            _record_observed_template_instances_in_type(
                parameter_type,
                argument_type,
                context,
                source_cursor=source_cursor,
            )


def _complete_observed_template_arguments_from_clang(
    arguments: list[CppTemplateArgument],
    clang_type: Any,
    parameters: list[Any],
    context: BuildContext | None,
) -> list[CppTemplateArgument]:
    """Fill trailing observed type arguments from clang when source spelling omits defaults."""

    complete_arguments = list(arguments)
    clang_argument_types = _template_argument_types_with_canonical_fallback(clang_type)
    if len(clang_argument_types) <= len(complete_arguments):
        return complete_arguments

    missing_parameters = parameters[len(complete_arguments):]
    if len(missing_parameters) != len(clang_argument_types) - len(complete_arguments):
        return complete_arguments

    for parameter, clang_argument_type in zip(
        missing_parameters,
        clang_argument_types[len(complete_arguments):],
        strict=True,
    ):
        if not isinstance(parameter, CppTypeTemplateParameter):
            return complete_arguments

        complete_arguments.append(
            CppTypeTemplateArgument(
                type=_build_cpp_type(
                    clang_argument_type,
                    allow_canonical=True,
                    context=context,
                    source_cursor=None,
                )
            )
        )

    return complete_arguments


def _template_argument_types_with_canonical_fallback(clang_type: Any) -> list[Any]:
    """Return clang template argument types, falling back to the canonical type if needed."""

    argument_types = _template_argument_types(clang_type)
    canonical_type = _call_optional_method(clang_type, "get_canonical")
    if canonical_type is None or _same_type_identity(clang_type, canonical_type):
        return argument_types

    canonical_argument_types = _template_argument_types(canonical_type)
    if len(canonical_argument_types) > len(argument_types):
        return canonical_argument_types

    return argument_types


def _specialized_template_cursor(clang_type: Any) -> Any | None:
    """Return the generic template cursor behind one concrete template-instantiated type."""

    declaration_cursor = _call_optional_method(clang_type, "get_declaration")
    if declaration_cursor is None:
        return None

    specialized_template = getattr(declaration_cursor, "specialized_template", None)
    if specialized_template is not None:
        return specialized_template

    get_specialized_cursor_template = getattr(declaration_cursor, "get_specialized_cursor_template", None)
    if callable(get_specialized_cursor_template):
        return get_specialized_cursor_template()

    return None


def _cursor_usr(cursor: Any) -> str | None:
    """Return one cursor USR when libclang exposes one for the entity."""

    get_usr = getattr(cursor, "get_usr", None)
    if not callable(get_usr):
        return None

    usr = get_usr()
    if not usr:
        return None
    return str(usr)


def _get_array_extent(clang_type: Any) -> str | None:
    """Return the rendered extent of one clang array type, if any."""

    get_array_size = getattr(clang_type, "get_array_size", None)
    if callable(get_array_size):
        extent = get_array_size()
        if isinstance(extent, int) and extent >= 0:
            return str(extent)
    return None


# ==================================================================================================
#     Type Identity Helpers
# ==================================================================================================


def _same_type_identity(left: Any, right: Any) -> bool:
    """Return whether two clang type objects look like the same semantic type."""

    if left is right:
        return True
    return (
        _type_kind_name(left) == _type_kind_name(right)
        and _type_spelling(left) == _type_spelling(right)
    )
