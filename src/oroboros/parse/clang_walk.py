from __future__ import annotations

"""Walk libclang cursors and materialize semantic declaration nodes."""

from typing import TYPE_CHECKING, Any, Iterable, TypeVar

from clang.cindex import CursorKind

from ..model import (
    CppClass,
    CppConstructor,
    CppElement,
    CppEnum,
    CppEnumerator,
    CppField,
    CppFunction,
    CppMethod,
    CppNamespace,
    CppParameter,
)
from .build_facets import (
    build_class_cpp_facet,
    build_constructor_cpp_facet,
    build_enum_cpp_facet,
    build_enumerator_cpp_facet,
    build_field_cpp_facet,
    build_function_cpp_facet,
    build_method_cpp_facet,
    build_namespace_cpp_facet,
    build_parameter_cpp_facet,
    cursor_is_from_active_header,
    cursor_kind_name,
    cursor_usr,
    is_base_specifier_cursor,
)
if TYPE_CHECKING:
    from .build_model import ModuleBuildContext

_NodeT = TypeVar("_NodeT")


# ==================================================================================================
#     Cursor Walk
# ==================================================================================================


def visit_cursor(
    cursor: Any,
    owner: CppElement,
    context: ModuleBuildContext,
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
    context: ModuleBuildContext,
) -> None:
    """Visit the children of one materialized semantic declaration node."""

    for child in children:
        visit_cursor(child, owner, context)


def _visit_namespace_cursor(
    cursor: Any,
    owner: CppElement,
    context: ModuleBuildContext,
) -> None:
    """Materialize one namespace cursor and continue walking inside it."""

    namespace = _ensure_namespace(owner, cursor, context)
    if namespace is not None:
        visit_children(cursor.get_children(), namespace, context)


def _visit_declaration_cursor(
    cursor: Any,
    owner: CppElement,
    context: ModuleBuildContext,
) -> None:
    """Materialize one supported declaration cursor by concrete cursor kind."""

    if _cursor_kind_matches(cursor, *_CLASS_CURSOR_KINDS):
        existing = _lookup_registered_element(cursor, context, CppClass)
        if existing is not None:
            visit_children(cursor.get_children(), existing, context)
            return

        cls = CppClass(
            name=cursor.spelling,
            cpp=build_class_cpp_facet(cursor),
        )
        attached = _attach_node(owner, "add_class", cls)
        if attached is not None:
            _register_element_for_cursor(cursor, attached, context)
            visit_children(cursor.get_children(), attached, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.ENUM_DECL):
        existing = _lookup_registered_element(cursor, context, CppEnum)
        if existing is not None:
            visit_children(cursor.get_children(), existing, context)
            return

        enum_ = CppEnum(
            name=cursor.spelling,
            cpp=build_enum_cpp_facet(cursor),
        )
        attached = _attach_node(owner, "add_enum", enum_)
        if attached is not None:
            _register_element_for_cursor(cursor, attached, context)
            visit_children(cursor.get_children(), attached, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.ENUM_CONSTANT_DECL):
        existing = _lookup_registered_element(cursor, context, CppEnumerator)
        if existing is not None:
            return

        enumerator = CppEnumerator(
            name=cursor.spelling,
            cpp=build_enumerator_cpp_facet(cursor),
        )
        attached = _attach_node(owner, "add_enumerator", enumerator)
        if attached is not None:
            _register_element_for_cursor(cursor, attached, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.FUNCTION_DECL):
        existing = _lookup_registered_element(cursor, context, CppFunction)
        if existing is not None:
            visit_children(cursor.get_children(), existing, context)
            return

        function = CppFunction(
            name=cursor.spelling,
            cpp=build_function_cpp_facet(cursor),
        )
        attached = _attach_node(owner, "add_function", function)
        if attached is not None:
            _register_element_for_cursor(cursor, attached, context)
            visit_children(cursor.get_children(), attached, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.CXX_METHOD):
        existing = _lookup_registered_element(cursor, context, CppMethod)
        if existing is not None:
            visit_children(cursor.get_children(), existing, context)
            return

        method = CppMethod(
            name=cursor.spelling,
            cpp=build_method_cpp_facet(cursor),
        )
        attached = _attach_node(owner, "add_method", method)
        if attached is not None:
            _register_element_for_cursor(cursor, attached, context)
            visit_children(cursor.get_children(), attached, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.CONSTRUCTOR):
        existing = _lookup_registered_element(cursor, context, CppConstructor)
        if existing is not None:
            visit_children(cursor.get_children(), existing, context)
            return

        constructor = CppConstructor(
            name=cursor.spelling,
            cpp=build_constructor_cpp_facet(cursor),
        )
        attached = _attach_node(owner, "add_constructor", constructor)
        if attached is not None:
            _register_element_for_cursor(cursor, attached, context)
            visit_children(cursor.get_children(), attached, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.FIELD_DECL):
        existing = _lookup_registered_element(cursor, context, CppField)
        if existing is not None:
            return

        field = CppField(
            name=cursor.spelling,
            cpp=build_field_cpp_facet(cursor),
        )
        attached = _attach_node(owner, "add_field", field)
        if attached is not None:
            _register_element_for_cursor(cursor, attached, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.PARM_DECL):
        existing = _lookup_registered_element(cursor, context, CppParameter)
        if existing is not None:
            return

        parameter = CppParameter(
            name=cursor.spelling,
            cpp=build_parameter_cpp_facet(cursor),
        )
        attached = _attach_node(owner, "add_parameter", parameter)
        if attached is not None:
            _register_element_for_cursor(cursor, attached, context)
        return

    if _is_ignored_declaration_cursor(cursor):
        return

    _record_skipped_cursor_kind(cursor, context)


def _record_skipped_cursor_kind(cursor: Any, context: ModuleBuildContext) -> None:
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


# ------------------------------------------------------------------------------
#     Cursor Kind Matching
# ------------------------------------------------------------------------------


def _cursor_kind_matches(cursor: Any, *expected_kinds: Any) -> bool:
    """Return whether one cursor matches any expected libclang cursor kinds."""

    actual_kind = getattr(cursor, "kind", None)
    if actual_kind is None:
        return False
    return actual_kind in expected_kinds


_IGNORED_DECLARATION_KINDS = frozenset({
    CursorKind.CXX_BASE_SPECIFIER,
    CursorKind.CXX_ACCESS_SPEC_DECL,
})

_CLASS_CURSOR_KINDS = frozenset({CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL})


# ==================================================================================================
#     Node Attachment
# ==================================================================================================


def _ensure_namespace(
    owner: CppElement,
    cursor: Any,
    context: ModuleBuildContext,
) -> CppNamespace | None:
    """Return one existing or newly created namespace for one parser cursor."""

    existing = _lookup_registered_element(cursor, context, CppNamespace)
    if existing is not None:
        return existing

    namespace_name = cursor.spelling
    existing_namespaces = getattr(owner, "namespaces", None)
    if existing_namespaces is not None:
        for namespace in existing_namespaces:
            if namespace.name == namespace_name:
                _register_element_for_cursor(cursor, namespace, context)
                return namespace

    namespace = CppNamespace(
        name=namespace_name,
        cpp=build_namespace_cpp_facet(cursor),
    )
    attached = _attach_node(owner, "add_namespace", namespace)
    if attached is not None:
        _register_element_for_cursor(cursor, attached, context)
    return attached


def _attach_node(
    owner: CppElement,
    attach_method_name: str,
    node: _NodeT,
) -> _NodeT | None:
    """Attach one node through the named owner `add_*` helper when available."""

    attach = getattr(owner, attach_method_name, None)
    if attach is None:
        return None
    return attach(node)


def _lookup_registered_element(
    cursor: Any,
    context: ModuleBuildContext,
    expected_type: type[_NodeT],
) -> _NodeT | None:
    """Return the previously materialized element for one cursor USR, if any."""

    usr = cursor_usr(cursor)
    if usr is None:
        return None

    element = context.usr_to_element.get(usr)
    if isinstance(element, expected_type):
        return element
    return None


def _register_element_for_cursor(
    cursor: Any,
    element: CppElement,
    context: ModuleBuildContext,
) -> None:
    """Record one cursor USR to semantic element mapping for later reuse."""

    usr = cursor_usr(cursor)
    if usr is None:
        return

    context.usr_to_element.setdefault(usr, element)
