from __future__ import annotations

"""Walk libclang cursors and dispatch them into semantic model builders."""

from typing import TYPE_CHECKING, Any, Iterable

from clang.cindex import CursorKind

from ..model import CppElement
from .cursor_data import cursor_is_from_active_header, cursor_kind_name, is_base_specifier_cursor
from .merge_declarations import merge_common_cpp_fields, merge_cpp_scalar
from .element_registry import ensure_namespace
from .process_declarations import (
    process_alias_cursor,
    process_class_cursor,
    process_class_template_cursor,
    process_constructor_cursor,
    process_enum_cursor,
    process_enumerator_cursor,
    process_field_cursor,
    process_function_cursor,
    process_function_template_cursor,
    process_method_cursor,
    process_parameter_cursor,
    process_variable_cursor,
)

if TYPE_CHECKING:
    from .build_model import BuildContext


# ==================================================================================================
#     Cursor Walk
# ==================================================================================================


def visit_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Classify one clang cursor and route it to the right parser helper."""

    if not cursor_is_from_active_header(cursor, context.active_headers):
        return

    if _is_namespace_cursor(cursor):
        _visit_namespace_cursor(cursor, owner, context)
        return

    if _is_declaration_cursor(cursor):
        _visit_declaration_cursor(cursor, owner, context)
        return

    if _is_ignored_cursor(cursor):
        return

    _record_skipped_cursor_kind(cursor, context)


def visit_children(
    children: Iterable[Any],
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Visit the children of one materialized semantic declaration element."""

    for child in children:
        visit_cursor(child, owner, context)


# ------------------------------------------------------------------------------
#     Internal Walk Helpers
# ------------------------------------------------------------------------------


def _visit_namespace_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Materialize one namespace cursor and continue walking inside it."""

    namespace = ensure_namespace(
        owner,
        cursor,
        context,
        merge_common_cpp_fields=merge_common_cpp_fields,
        merge_cpp_scalar=merge_cpp_scalar,
    )
    if namespace is not None:
        visit_children(cursor.get_children(), namespace, context)


def _visit_declaration_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Materialize one supported declaration cursor by concrete cursor kind."""

    if _cursor_kind_matches(cursor, *_CLASS_CURSOR_KINDS):
        process_class_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.CLASS_TEMPLATE):
        process_class_template_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.ENUM_DECL):
        process_enum_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.ENUM_CONSTANT_DECL):
        process_enumerator_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.FUNCTION_DECL):
        process_function_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.FUNCTION_TEMPLATE):
        process_function_template_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.TYPE_ALIAS_DECL, CursorKind.TYPEDEF_DECL):
        process_alias_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.CXX_METHOD):
        process_method_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.CONSTRUCTOR):
        process_constructor_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.FIELD_DECL):
        process_field_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.VAR_DECL):
        process_variable_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.PARM_DECL):
        process_parameter_cursor(cursor, owner, context)
        return

    if _is_ignored_declaration_cursor(cursor):
        return

    _record_skipped_cursor_kind(cursor, context)


def _record_skipped_cursor_kind(cursor: Any, context: BuildContext) -> None:
    """Record one unsupported cursor kind in the parser summary."""

    context.skipped_kind_counts[cursor_kind_name(cursor)] += 1


# ==================================================================================================
#     Cursor Kind Classification
# ==================================================================================================


def _is_namespace_cursor(cursor: Any) -> bool:
    """Return whether one cursor is a namespace declaration."""

    return _cursor_kind_matches(cursor, CursorKind.NAMESPACE)


def _is_declaration_cursor(cursor: Any) -> bool:
    """Return whether one cursor should be treated as a declaration at a coarse level."""

    kind = getattr(cursor, "kind", None)
    if kind is None:
        return False
    return bool(kind.is_declaration())


def _is_reference_cursor(cursor: Any) -> bool:
    """Return whether one cursor is a non-owning reference/helper cursor."""

    kind = getattr(cursor, "kind", None)
    if kind is None:
        return False
    return bool(kind.is_reference())


def _is_ignored_cursor(cursor: Any) -> bool:
    """Return whether one cursor is intentionally ignored outside declaration dispatch."""

    return _is_reference_cursor(cursor) or is_base_specifier_cursor(cursor)


def _is_ignored_declaration_cursor(cursor: Any) -> bool:
    """Return whether one declaration cursor is handled structurally elsewhere."""

    return _cursor_kind_matches(cursor, *_IGNORED_DECLARATION_KINDS)


def _cursor_kind_matches(cursor: Any, *expected_kinds: Any) -> bool:
    """Return whether one cursor matches any expected libclang cursor kinds."""

    actual_kind = getattr(cursor, "kind", None)
    if actual_kind is None:
        return False
    return actual_kind in expected_kinds


_IGNORED_DECLARATION_KINDS = frozenset({
    CursorKind.CXX_BASE_SPECIFIER,
    CursorKind.CXX_ACCESS_SPEC_DECL,
    CursorKind.TEMPLATE_NON_TYPE_PARAMETER,
    CursorKind.TEMPLATE_TEMPLATE_PARAMETER,
    CursorKind.TEMPLATE_TYPE_PARAMETER,
})

_CLASS_CURSOR_KINDS = frozenset({CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL})
