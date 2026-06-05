from __future__ import annotations

"""Translate clang type objects into the semantic C++ type model.

This module walks libclang types such as pointers, references, arrays,
functions, and named declarations, then assembles the corresponding semantic
type objects with canonical-type and declaration-link information.
"""

from typing import TYPE_CHECKING, Any

from clang.cindex import TypeKind

from ..diagnostics import Diagnostic
from ..model import (
    ArrayCppType,
    BuiltinCppType,
    CppNonTypeTemplateArgument,
    CppTypeTemplateArgument,
    CppType,
    FunctionCppType,
    LValueReferenceCppType,
    NamedCppType,
    PointerCppType,
    RValueReferenceCppType,
)
from .cursor_data import cursor_source_location
from .template_type_recovery import (
    _normalize_name_type_spelling,
    _recover_template_instance_type,
)

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
    """Convert one libclang type into one semantic `CppType` tree.

    This is the main entrypoint used while extracting declaration-surface
    information such as parameter, return, field, base, and alias-target
    types. It keeps the clang-backed orchestration here, then delegates any
    spelling-driven template recovery to `template_type_recovery.py`.
    """

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
    """Recursively translate one clang type node into the semantic type model.

    This helper does the real work behind `build_cpp_type()`: wrapper kinds,
    builtin kinds, template-instantiation recovery, canonical fallback, and
    declaration-link recording. The `allow_canonical` flag prevents infinite
    loops when canonical types point back at the same semantic shape.
    """

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
    if "<" in spelling:
        # Build the structured TemplateInstanceCppType from spelling.  Falls through to
        # NamedCppType for zero-argument spellings such as Box<> (no arguments to split).
        template_instance = _recover_template_instance_type(
            spelling,
            is_const=is_const,
            direct_argument_types=_template_argument_types(clang_type),
            build_type_argument_type=lambda direct_type: _build_cpp_type(
                direct_type,
                allow_canonical=allow_canonical,
                context=context,
                source_cursor=source_cursor,
            ),
            build_non_type_annotation=lambda direct_type: _build_cpp_type(
                direct_type,
                allow_canonical=True,
                context=context,
                source_cursor=None,
            ),
        )
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


def _template_argument_types(clang_type: Any) -> list[Any]:
    """Collect direct clang template-argument types from one libclang type.

    The template recovery layer uses these values to refine ambiguous spelling
    recovery, for example upgrading an opaque `Widget` argument into a real
    type argument when libclang proves that slot is typed. Missing entries are
    acceptable; recovery falls back to spelling-only behavior when needed.
    """

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
#     Declaration Linking
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
    """Record the declaration target for one named-type fallback when available.

    This runs only after richer wrapper and template recovery paths have
    already had their chance. It lets later stages resolve simple named type
    references back to parsed declarations without doing broader semantic
    reconstruction from spelling alone.
    """

    if context is None:
        return

    declaration_cursor = _call_optional_method(clang_type, "get_declaration")
    if declaration_cursor is None:
        return

    declaration_location = cursor_source_location(declaration_cursor)
    must_resolve_in_active_headers = False
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
        must_resolve_in_active_headers = declaration_file in context.active_headers

    declaration_usr = _cursor_usr(declaration_cursor)
    if declaration_usr is None:
        return

    from .build_model import PendingTypeDeclarationLink

    context.pending_type_declaration_links.append(
        PendingTypeDeclarationLink(
            cpp_type=cpp_type,
            declaration_usr=declaration_usr,
            declaration_cursor=declaration_cursor,
            source_location=cursor_source_location(source_cursor) if source_cursor is not None else None,
            declaration_location=declaration_location,
            must_resolve_in_active_headers=must_resolve_in_active_headers,
        )
    )


def _record_inactive_project_type_reference_warning(
    cpp_type: NamedCppType,
    *,
    declaration_location: Any,
    source_cursor: Any | None,
    context: BuildContext,
) -> None:
    """Warn when active code points at a known but inactive project declaration.

    The parser still preserves the source spelling as a named type, but this
    warning makes the dropped semantic link visible to the user. That keeps the
    active-header boundary explicit instead of silently pretending the target
    declaration was never discovered.
    """

    use_location = cursor_source_location(source_cursor) if source_cursor is not None else None
    warning = (
        f"Active declaration references known project type {cpp_type.name!r} "
        "from an inactive project header; "
        "preserving the type spelling without materializing that declaration."
    )
    locations = []
    if use_location is not None:
        locations.append(use_location)
    if declaration_location is not None:
        locations.append(declaration_location)
    context.report.add(
        Diagnostic(
            severity="warning",
            stage="parse",
            code="parse.inactive_project_type_reference",
            message=warning,
            locations=locations,
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
