from __future__ import annotations

"""Walk libclang cursors and materialize semantic declaration nodes."""

from typing import TYPE_CHECKING, Any, Callable, Iterable, TypeVar

from clang.cindex import CursorKind

from ..model import (
    CppAlias,
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
from ..model.type import cpp_types_equivalent
from .build_facets import (
    build_alias_cpp_facet,
    build_class_cpp_facet,
    build_constructor_cpp_facet,
    build_enum_cpp_facet,
    build_enumerator_cpp_facet,
    build_field_cpp_facet,
    build_function_cpp_facet,
    build_method_cpp_facet,
    build_namespace_cpp_facet,
    build_parameter_cpp_facet,
    build_location_info,
    cursor_is_from_active_header,
    cursor_kind_name,
    cursor_source_location,
    cursor_usr,
    is_base_specifier_cursor,
)
if TYPE_CHECKING:
    from .build_model import BuildContext

_NodeT = TypeVar("_NodeT")


# ==================================================================================================
#     Cursor Walk
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Public Walk Entry Points
# ------------------------------------------------------------------------------


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
    """Visit the children of one materialized semantic declaration node."""

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

    namespace = _ensure_namespace(owner, cursor, context)
    if namespace is not None:
        visit_children(cursor.get_children(), namespace, context)


def _visit_declaration_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Materialize one supported declaration cursor by concrete cursor kind."""

    if _cursor_kind_matches(cursor, *_CLASS_CURSOR_KINDS):
        _process_class_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.ENUM_DECL):
        _process_enum_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.ENUM_CONSTANT_DECL):
        _process_enumerator_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.FUNCTION_DECL):
        _process_function_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.TYPE_ALIAS_DECL, CursorKind.TYPEDEF_DECL):
        _process_alias_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.CXX_METHOD):
        _process_method_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.CONSTRUCTOR):
        _process_constructor_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.FIELD_DECL):
        _process_field_cursor(cursor, owner, context)
        return

    if _cursor_kind_matches(cursor, CursorKind.PARM_DECL):
        _process_parameter_cursor(cursor, owner, context)
        return

    if _is_ignored_declaration_cursor(cursor):
        return

    _record_skipped_cursor_kind(cursor, context)


def _record_skipped_cursor_kind(cursor: Any, context: BuildContext) -> None:
    """Record one unsupported cursor kind in the parser summary."""

    context.skipped_kind_counts[cursor_kind_name(cursor)] += 1


# ==================================================================================================
#     Declaration Processing
# ==================================================================================================


def _process_class_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one class declaration and recurse into its children."""

    candidate_cpp = build_class_cpp_facet(cursor, context=context)
    existing = _lookup_registered_element(cursor, context, CppClass)
    if existing is not None:
        _merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        _merge_cpp_scalar(existing, "kind", candidate_cpp.kind, context, cursor)
        _merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
        _merge_class_bases(existing, candidate_cpp.bases, context, cursor)
        visit_children(cursor.get_children(), existing, context)
        return

    cls = CppClass(name=cursor.spelling, cpp=candidate_cpp)
    attached = _attach_node(owner, "add_class", cls)
    if attached is not None:
        _register_element_for_cursor(cursor, attached, context)
        visit_children(cursor.get_children(), attached, context)


def _process_enum_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one enum declaration and recurse into its children."""

    candidate_cpp = build_enum_cpp_facet(cursor, context=context)
    existing = _lookup_registered_element(cursor, context, CppEnum)
    if existing is not None:
        _merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        _merge_cpp_scalar(existing, "underlying_type", candidate_cpp.underlying_type, context, cursor)
        _merge_cpp_scalar(existing, "is_scoped", candidate_cpp.is_scoped, context, cursor)
        _merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
        visit_children(cursor.get_children(), existing, context)
        return

    enum_ = CppEnum(name=cursor.spelling, cpp=candidate_cpp)
    attached = _attach_node(owner, "add_enum", enum_)
    if attached is not None:
        _register_element_for_cursor(cursor, attached, context)
        visit_children(cursor.get_children(), attached, context)


def _process_enumerator_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one enumerator declaration."""

    candidate_cpp = build_enumerator_cpp_facet(cursor)
    existing = _lookup_registered_element(cursor, context, CppEnumerator)
    if existing is not None:
        _warn_unexpected_repeated_declaration(context, cursor, "enumerator")
        return

    enumerator = CppEnumerator(name=cursor.spelling, cpp=candidate_cpp)
    attached = _attach_node(owner, "add_enumerator", enumerator)
    if attached is not None:
        _register_element_for_cursor(cursor, attached, context)


def _process_function_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one free function declaration and recurse into its children."""

    candidate_cpp = build_function_cpp_facet(cursor, context=context)
    existing = _lookup_registered_element(cursor, context, CppFunction)
    if existing is not None:
        child_cursors = list(cursor.get_children())
        _merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        _merge_cpp_scalar(
            existing,
            "return_type",
            candidate_cpp.return_type,
            context,
            cursor,
            values_equivalent=cpp_types_equivalent,
        )
        _merge_cpp_scalar(existing, "is_noexcept", candidate_cpp.is_noexcept, context, cursor)
        _merge_callable_parameter_children(existing, child_cursors, context)
        _visit_non_parameter_children(child_cursors, existing, context)
        return

    function = CppFunction(name=cursor.spelling, cpp=candidate_cpp)
    attached = _attach_node(owner, "add_function", function)
    if attached is not None:
        _register_element_for_cursor(cursor, attached, context)
        visit_children(cursor.get_children(), attached, context)


def _process_alias_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one alias declaration."""

    candidate_cpp = build_alias_cpp_facet(cursor, context=context)
    existing = _lookup_registered_element(cursor, context, CppAlias)
    if existing is not None:
        _warn_unexpected_repeated_declaration(context, cursor, "alias")
        return

    alias = CppAlias(name=cursor.spelling, cpp=candidate_cpp)
    attached = _attach_node(owner, "add_alias", alias)
    if attached is not None:
        _register_element_for_cursor(cursor, attached, context)


def _process_method_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one method declaration and recurse into its children."""

    candidate_cpp = build_method_cpp_facet(cursor, context=context)
    existing = _lookup_registered_element(cursor, context, CppMethod)
    if existing is not None:
        child_cursors = list(cursor.get_children())
        _merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        _merge_cpp_scalar(
            existing,
            "return_type",
            candidate_cpp.return_type,
            context,
            cursor,
            values_equivalent=cpp_types_equivalent,
        )
        _merge_cpp_scalar(existing, "is_noexcept", candidate_cpp.is_noexcept, context, cursor)
        _merge_cpp_scalar(existing, "is_const", candidate_cpp.is_const, context, cursor)
        _merge_cpp_scalar(existing, "is_static", candidate_cpp.is_static, context, cursor)
        _merge_cpp_scalar(existing, "is_virtual", candidate_cpp.is_virtual, context, cursor)
        _merge_cpp_scalar(existing, "is_pure_virtual", candidate_cpp.is_pure_virtual, context, cursor)
        _merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
        _merge_callable_parameter_children(existing, child_cursors, context)
        _visit_non_parameter_children(child_cursors, existing, context)
        return

    method = CppMethod(name=cursor.spelling, cpp=candidate_cpp)
    attached = _attach_node(owner, "add_method", method)
    if attached is not None:
        _register_element_for_cursor(cursor, attached, context)
        visit_children(cursor.get_children(), attached, context)


def _process_constructor_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one constructor declaration and recurse into its children."""

    candidate_cpp = build_constructor_cpp_facet(cursor)
    existing = _lookup_registered_element(cursor, context, CppConstructor)
    if existing is not None:
        child_cursors = list(cursor.get_children())
        _merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        _merge_cpp_scalar(existing, "is_noexcept", candidate_cpp.is_noexcept, context, cursor)
        _merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
        _merge_callable_parameter_children(existing, child_cursors, context)
        _visit_non_parameter_children(child_cursors, existing, context)
        return

    constructor = CppConstructor(name=cursor.spelling, cpp=candidate_cpp)
    attached = _attach_node(owner, "add_constructor", constructor)
    if attached is not None:
        _register_element_for_cursor(cursor, attached, context)
        visit_children(cursor.get_children(), attached, context)


def _process_field_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one field declaration."""

    candidate_cpp = build_field_cpp_facet(cursor, context=context)
    existing = _lookup_registered_element(cursor, context, CppField)
    if existing is not None:
        _warn_unexpected_repeated_declaration(context, cursor, "field")
        return

    field = CppField(name=cursor.spelling, cpp=candidate_cpp)
    attached = _attach_node(owner, "add_field", field)
    if attached is not None:
        _register_element_for_cursor(cursor, attached, context)


def _process_parameter_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one parameter declaration."""

    candidate_cpp = build_parameter_cpp_facet(cursor, context=context)
    existing = _lookup_registered_element(cursor, context, CppParameter)
    if existing is not None:
        _warn_unexpected_repeated_declaration(context, cursor, "parameter")
        return

    parameter = CppParameter(name=cursor.spelling, cpp=candidate_cpp)
    attached = _attach_node(owner, "add_parameter", parameter)
    if attached is not None:
        _register_element_for_cursor(cursor, attached, context)


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
})

_CLASS_CURSOR_KINDS = frozenset({CursorKind.CLASS_DECL, CursorKind.STRUCT_DECL})


# ==================================================================================================
#     Namespace Reuse And Generic Attachment
# ==================================================================================================


def _ensure_namespace(
    owner: CppElement,
    cursor: Any,
    context: BuildContext,
) -> CppNamespace | None:
    """Return one existing or newly created namespace for one parser cursor."""

    candidate_cpp = build_namespace_cpp_facet(cursor)
    existing = _lookup_registered_element(cursor, context, CppNamespace)
    if existing is not None:
        _merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        _merge_cpp_scalar(existing, "is_inline", candidate_cpp.is_inline, context, cursor)
        return existing

    namespace_name = cursor.spelling
    existing_namespaces = getattr(owner, "namespaces", None)
    if namespace_name and existing_namespaces is not None:
        for namespace in existing_namespaces:
            if namespace.name == namespace_name:
                _merge_common_cpp_fields(namespace, candidate_cpp, context, cursor)
                _merge_cpp_scalar(namespace, "is_inline", candidate_cpp.is_inline, context, cursor)
                _register_element_for_cursor(cursor, namespace, context)
                return namespace

    namespace = CppNamespace(
        name=namespace_name,
        cpp=candidate_cpp,
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
    context: BuildContext,
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
    context: BuildContext,
) -> None:
    """Record one cursor USR to semantic element mapping for later reuse."""

    usr = cursor_usr(cursor)
    if usr is None:
        return

    context.usr_to_element.setdefault(usr, element)


# ==================================================================================================
#     Property Merging And Conflict Resolution
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Common Field Merging
# ------------------------------------------------------------------------------


def _merge_common_cpp_fields(
    element: CppElement,
    candidate_cpp: Any,
    context: BuildContext,
    cursor: Any,
    *,
    comment_field_name: str | None = "comment",
    merge_original_name: bool = True,
) -> None:
    """Merge common parsed fields from one repeated declaration into an element."""

    if merge_original_name:
        _merge_cpp_scalar(element, "original_name", getattr(candidate_cpp, "original_name", None), context, cursor)
    _merge_location_info(element.cpp.location, candidate_cpp.location)
    if comment_field_name is not None and hasattr(element.cpp, comment_field_name):
        merged_comment = _resolve_comment_conflict(
            existing_comment=getattr(element.cpp, comment_field_name),
            new_comment=getattr(candidate_cpp, comment_field_name, None),
            context=context,
            cursor=cursor,
        )
        setattr(element.cpp, comment_field_name, merged_comment)


def _merge_cpp_scalar(
    element: CppElement,
    field_name: str,
    new_value: Any,
    context: BuildContext,
    cursor: Any,
    *,
    values_equivalent: Callable[[Any, Any], bool] | None = None,
    warn_on_conflict: bool = True,
) -> None:
    """Merge one scalar parsed field conservatively and warn on disagreement."""

    if new_value is None:
        return

    current_value = getattr(element.cpp, field_name, None)
    if current_value is None:
        setattr(element.cpp, field_name, new_value)
        return

    equivalent = values_equivalent or _values_equal
    if equivalent(current_value, new_value):
        return

    if not warn_on_conflict:
        return

    _record_semantic_warning(
        context,
        f"Conflicting parsed {field_name!r} for {_describe_cursor_entity(cursor)} at "
        f"{_format_cursor_location(cursor)}; keeping the first value.",
    )


def _merge_class_bases(
    element: CppClass,
    new_bases: list[Any],
    context: BuildContext,
    cursor: Any,
) -> None:
    """Merge class base relationships conservatively across repeated declarations."""

    if not new_bases:
        return

    if not element.cpp.bases:
        element.cpp.bases.extend(new_bases)
        return

    if element.cpp.bases == new_bases:
        return

    _record_semantic_warning(
        context,
        f"Conflicting parsed 'bases' for {_describe_cursor_entity(cursor)} at "
        f"{_format_cursor_location(cursor)}; keeping the first value.",
    )


def _merge_location_info(existing: Any, new: Any) -> None:
    """Merge source provenance from one repeated declaration cursor."""

    if existing.primary is None and new.primary is not None:
        existing.primary = new.primary

    if new.definition is not None:
        existing.definition = new.definition
        existing.primary = new.definition

    for declaration_location in new.declarations:
        if declaration_location not in existing.declarations:
            existing.declarations.append(declaration_location)


def _merge_callable_parameter_children(
    callable_element: Any,
    child_cursors: Iterable[Any],
    context: BuildContext,
) -> None:
    """Merge callable parameters positionally across repeated declarations."""

    parameter_cursors = [
        child_cursor
        for child_cursor in child_cursors
        if cursor_is_from_active_header(child_cursor, context.active_headers)
        and _cursor_kind_matches(child_cursor, CursorKind.PARM_DECL)
    ]
    existing_parameters = list(getattr(callable_element, "parameters", []))

    if len(existing_parameters) != len(parameter_cursors):
        return

    for existing_parameter, parameter_cursor in zip(
        existing_parameters,
        parameter_cursors,
        strict=True,
    ):
        candidate_cpp = build_parameter_cpp_facet(parameter_cursor, context=context)
        _register_element_for_cursor(parameter_cursor, existing_parameter, context)
        _merge_common_cpp_fields(
            existing_parameter,
            candidate_cpp,
            context,
            parameter_cursor,
            comment_field_name=None,
            merge_original_name=False,
        )
        _merge_cpp_scalar(
            existing_parameter,
            "type",
            candidate_cpp.type,
            context,
            parameter_cursor,
            values_equivalent=cpp_types_equivalent,
        )


def _visit_non_parameter_children(
    child_cursors: Iterable[Any],
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Continue walking child cursors other than parameters."""

    for child_cursor in child_cursors:
        if _cursor_kind_matches(child_cursor, CursorKind.PARM_DECL):
            continue
        visit_cursor(child_cursor, owner, context)


def _values_equal(left: Any, right: Any) -> bool:
    """Return whether two parsed scalar values are equal."""

    return left == right


# ------------------------------------------------------------------------------
#     Comment Conflict Resolution
# ------------------------------------------------------------------------------


def _resolve_comment_conflict(
    *,
    existing_comment: str | None,
    new_comment: str | None,
    context: BuildContext,
    cursor: Any,
) -> str | None:
    """Resolve one repeated-declaration comment conflict using parser policy."""

    if new_comment is None:
        return existing_comment
    if existing_comment is None:
        return new_comment
    if existing_comment == new_comment:
        return existing_comment

    _record_semantic_warning(
        context,
        f"Conflicting parsed comments for {_describe_cursor_entity(cursor)} at "
        f"{_format_cursor_location(cursor)}; resolved via "
        f"`comment_conflict_policy={context.config.comment_conflict_policy}`.",
    )

    if context.config.comment_conflict_policy == "first":
        return existing_comment
    if context.config.comment_conflict_policy == "last":
        return new_comment
    if context.config.comment_conflict_policy == "append":
        return _append_distinct_comments(existing_comment, new_comment)
    if len(new_comment) > len(existing_comment):
        return new_comment
    return existing_comment


def _append_distinct_comments(existing_comment: str, new_comment: str) -> str:
    """Join two distinct comment blocks while avoiding exact duplication."""

    if new_comment in existing_comment:
        return existing_comment
    if existing_comment in new_comment:
        return new_comment
    return f"{existing_comment}\n\n{new_comment}"


# ==================================================================================================
#     Warning Rendering
# ==================================================================================================


def _record_semantic_warning(context: BuildContext, warning: str) -> None:
    """Append one parser-level semantic warning if it is not already present."""

    if warning not in context.semantic_warnings:
        context.semantic_warnings.append(warning)


def _warn_unexpected_repeated_declaration(
    context: BuildContext,
    cursor: Any,
    declaration_kind: str,
) -> None:
    """Warn when a non-redeclarable declaration kind repeats by semantic identity."""

    _record_semantic_warning(
        context,
        f"Encountered repeated {declaration_kind} declaration for {_describe_cursor_entity(cursor)} at "
        f"{_format_cursor_location(cursor)}; keeping the first declaration.",
    )


def _describe_cursor_entity(cursor: Any) -> str:
    """Render one short human-readable cursor description for warnings."""

    spelling = getattr(cursor, "spelling", None) or "<anonymous>"
    return f"{cursor_kind_name(cursor)} {spelling!r}"


def _format_cursor_location(cursor: Any) -> str:
    """Render one short source-location string for warnings."""

    location = cursor_source_location(cursor)
    return _format_source_location(location)


def _format_source_location(location: Any) -> str:
    """Render one source-location object into a stable short string."""

    if location is None:
        return "<unknown location>"
    return f"{location.file}:{location.line}:{location.column}"
