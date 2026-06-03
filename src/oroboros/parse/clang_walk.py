from __future__ import annotations

"""Walk libclang cursors and dispatch them into semantic model builders."""

from typing import TYPE_CHECKING, Any, Iterable

from clang.cindex import CursorKind

from ..model import CppElement
from .cursor_data import cursor_is_from_active_header, cursor_kind_name, is_base_specifier_cursor
from .merge_properties import merge_common_cpp_fields, merge_cpp_scalar
from .element_registry import (
    ensure_namespace,
    record_skipped_cursor_example,
    resolve_semantic_owner,
)
from . import process_cursors

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
        for child_cursor in cursor.get_children():
            visit_cursor(
                child_cursor,
                resolve_semantic_owner(child_cursor, namespace, context),
                context,
            )


def _visit_declaration_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Materialize one supported declaration cursor by concrete cursor kind."""

    if _cursor_kind_matches(cursor, *_CLASS_CURSOR_KINDS):
        process_cursors.process_class_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.CLASS_TEMPLATE):
        process_cursors.process_class_template_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.ENUM_DECL):
        process_cursors.process_enum_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.ENUM_CONSTANT_DECL):
        process_cursors.process_enumerator_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.FUNCTION_DECL):
        process_cursors.process_function_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.FUNCTION_TEMPLATE):
        process_cursors.process_function_template_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.TYPE_ALIAS_TEMPLATE_DECL):
        process_cursors.process_alias_template_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.TYPE_ALIAS_DECL, CursorKind.TYPEDEF_DECL):
        process_cursors.process_alias_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.CXX_METHOD):
        process_cursors.process_method_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.CONVERSION_FUNCTION):
        process_cursors.process_method_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.CONSTRUCTOR):
        process_cursors.process_constructor_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.DESTRUCTOR):
        process_cursors.process_destructor_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.FIELD_DECL):
        process_cursors.process_field_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.VAR_DECL):
        process_cursors.process_variable_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.PARM_DECL):
        process_cursors.process_parameter_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.FRIEND_DECL):
        _visit_friend_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.LINKAGE_SPEC):
        _visit_linkage_spec_cursor(cursor, owner, context)
        return

    if _is_ignored_declaration_cursor(cursor):
        return

    _record_skipped_cursor_kind(cursor, context)


def _record_skipped_cursor_kind(cursor: Any, context: BuildContext) -> None:
    """Record one unsupported cursor kind in the parser summary."""

    context.skipped_kind_counts[cursor_kind_name(cursor)] += 1
    record_skipped_cursor_example(cursor, context)


def _visit_friend_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Visit the child declarations nested under one friend wrapper cursor."""

    for child_cursor in cursor.get_children():
        visit_cursor(
            child_cursor,
            resolve_semantic_owner(child_cursor, owner, context),
            context,
        )


def _visit_linkage_spec_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Visit the declarations nested under one linkage-spec wrapper cursor."""

    for child_cursor in cursor.get_children():
        visit_cursor(
            child_cursor,
            resolve_semantic_owner(child_cursor, owner, context),
            context,
        )


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

    return (
        _is_reference_cursor(cursor)
        or is_base_specifier_cursor(cursor)
        or _cursor_kind_matches(cursor, CursorKind.COMPOUND_STMT)
    )


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
    # Partial specializations are not separately bindable; the primary template is always
    # the binding target. The compiler selects the right specialization at each call site.
    CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION,
    # Scope-local `using foo::bar;` re-exports are intentionally unmodeled for now.
    CursorKind.USING_DECLARATION,
    # Namespace aliases/directives affect lookup/spelling, not the bindable surface itself.
    CursorKind.NAMESPACE_ALIAS,
    CursorKind.USING_DIRECTIVE,
    # Compile-time-only declaration forms are intentionally unmodeled for now.
    CursorKind.STATIC_ASSERT,
    CursorKind.CONCEPT_DECL,
    CursorKind.MODULE_IMPORT_DECL,
    # Declarations whose kind libclang does not expose through its C API.
    CursorKind.UNEXPOSED_DECL,
    # Objective-C declarations are out of scope for Oroboros.
    CursorKind.OBJC_CATEGORY_DECL,
    CursorKind.OBJC_CATEGORY_IMPL_DECL,
    CursorKind.OBJC_CLASS_METHOD_DECL,
    CursorKind.OBJC_DYNAMIC_DECL,
    CursorKind.OBJC_IMPLEMENTATION_DECL,
    CursorKind.OBJC_INSTANCE_METHOD_DECL,
    CursorKind.OBJC_INTERFACE_DECL,
    CursorKind.OBJC_IVAR_DECL,
    CursorKind.OBJC_PROPERTY_DECL,
    CursorKind.OBJC_PROTOCOL_DECL,
    CursorKind.OBJC_SYNTHESIZE_DECL,
})

_CLASS_CURSOR_KINDS = frozenset({CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL, CursorKind.UNION_DECL})
