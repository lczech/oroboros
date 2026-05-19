from __future__ import annotations

"""Translate clang type objects into the semantic C++ type model."""

from typing import TYPE_CHECKING, Any

from clang.cindex import TypeKind

from ..model import (
    ArrayCppType,
    BuiltinCppType,
    CppType,
    FunctionCppType,
    LValueReferenceCppType,
    NamedCppType,
    PointerCppType,
    RValueReferenceCppType,
    TemplateInstanceCppType,
)
from ..model.type import cpp_builtin_kind_from_spelling

if TYPE_CHECKING:
    from .build_model import BuildContext


# ==================================================================================================
#     Public Type Builder
# ==================================================================================================


def build_cpp_type(
    clang_type: Any,
    *,
    context: BuildContext | None = None,
) -> CppType | None:
    """Convert one clang type object into the structured semantic type model."""

    if clang_type is None:
        return None

    return _build_cpp_type(
        clang_type,
        allow_canonical=True,
        context=context,
    )


def _build_cpp_type(
    clang_type: Any,
    *,
    allow_canonical: bool,
    context: BuildContext | None,
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
            ),
            is_const=is_const,
        )

    if _type_kind_matches(clang_type, TypeKind.LVALUEREFERENCE):
        return LValueReferenceCppType(
            referred=_build_cpp_type(
                _call_optional_method(clang_type, "get_pointee"),
                allow_canonical=allow_canonical,
                context=context,
            ),
            is_const=is_const,
        )

    if _type_kind_matches(clang_type, TypeKind.RVALUEREFERENCE):
        return RValueReferenceCppType(
            referred=_build_cpp_type(
                _call_optional_method(clang_type, "get_pointee"),
                allow_canonical=allow_canonical,
                context=context,
            ),
            is_const=is_const,
        )

    if _type_kind_matches(clang_type, *_ARRAY_KINDS):
        return ArrayCppType(
            element_type=_build_cpp_type(
                _call_optional_method(clang_type, "get_array_element_type"),
                allow_canonical=allow_canonical,
                context=context,
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
            ),
            parameters=[
                _build_cpp_type(
                    parameter_type,
                    allow_canonical=allow_canonical,
                    context=context,
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
        return template_instance

    canonical = None
    if allow_canonical:
        canonical_type = _call_optional_method(clang_type, "get_canonical")
        if canonical_type is not None and not _same_type_identity(clang_type, canonical_type):
            canonical = _build_cpp_type(
                canonical_type,
                allow_canonical=False,
                context=context,
            )

    named_type = NamedCppType(
        name=spelling,
        canonical=canonical,
        is_const=is_const,
    )
    _record_named_type_declaration_link(named_type, clang_type, context)
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
        arguments=[
            _build_type_from_spelling(argument_spelling)
            for argument_spelling in argument_spellings
        ],
        is_const=is_const,
    )


def _build_type_from_spelling(spelling: str) -> CppType:
    """Build one fallback semantic type from a plain C++ spelling fragment."""

    normalized = spelling.strip()
    is_const = normalized.startswith("const ") or normalized.endswith(" const")
    normalized = _normalize_name_type_spelling(normalized, is_const=is_const)

    if normalized.endswith("&&"):
        return RValueReferenceCppType(
            referred=_build_type_from_spelling(normalized[:-2]),
            is_const=is_const,
        )

    if normalized.endswith("&"):
        return LValueReferenceCppType(
            referred=_build_type_from_spelling(normalized[:-1]),
            is_const=is_const,
        )

    if normalized.endswith("*"):
        return PointerCppType(
            pointee=_build_type_from_spelling(normalized[:-1]),
            is_const=is_const,
        )

    template_instance = _parse_template_instance_spelling(normalized, is_const=is_const)
    if template_instance is not None:
        return template_instance

    builtin_kind = cpp_builtin_kind_from_spelling(normalized)
    if builtin_kind is not None:
        return BuiltinCppType(kind=builtin_kind, is_const=is_const)

    return NamedCppType(name=normalized, is_const=is_const)


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


# ==================================================================================================
#     Clang Type Introspection
# ==================================================================================================


def _clang_builtin_kind(clang_type: Any) -> str | None:
    """Return one semantic builtin kind for one clang builtin type."""

    actual_kind = getattr(clang_type, "kind", None)
    if actual_kind is not None:
        builtin_kind = _CLANG_BUILTIN_KIND_MAP.get(actual_kind)
        if builtin_kind is not None:
            return builtin_kind
    return _CLANG_BUILTIN_KIND_MAP.get(_type_kind_name(clang_type))


def _type_kind_matches(clang_type: Any, *expected_kinds: Any) -> bool:
    """Return whether one clang type matches any expected libclang type kinds."""

    actual_kind = getattr(clang_type, "kind", None)
    if actual_kind is None:
        return False
    return actual_kind in expected_kinds


# ==================================================================================================
#     Builtin Type Mapping
# ==================================================================================================


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
) -> None:
    """Capture one referenced declaration USR for a named type when available."""

    if context is None:
        return

    declaration_cursor = _call_optional_method(clang_type, "get_declaration")
    if declaration_cursor is None:
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
