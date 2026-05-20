from __future__ import annotations

"""Process concrete libclang declaration cursors into semantic model nodes."""

from typing import TYPE_CHECKING, Any, Iterable

from clang.cindex import CursorKind

from ..model import (
    CppAlias,
    CppClass,
    CppClassTemplate,
    CppClassTemplateDecl,
    CppConstructor,
    CppElement,
    CppEnum,
    CppEnumerator,
    CppField,
    CppFunction,
    CppFunctionTemplate,
    CppFunctionTemplateDecl,
    CppMethod,
    CppParameter,
)
from ..model.type import cpp_types_equivalent
from .build_facets import (
    build_alias_cpp_facet,
    build_class_cpp_facet,
    build_class_template_decl_cpp_facet,
    build_constructor_cpp_facet,
    build_enum_cpp_facet,
    build_enumerator_cpp_facet,
    build_field_cpp_facet,
    build_function_cpp_facet,
    build_function_template_decl_cpp_facet,
    build_method_cpp_facet,
    build_parameter_cpp_facet,
)
from .merge_declarations import (
    merge_callable_parameter_children,
    merge_class_bases,
    merge_common_cpp_fields,
    merge_cpp_scalar,
    merge_template_parameters,
    warn_unexpected_repeated_declaration,
)
from .node_registry import attach_node, lookup_registered_element, register_element_for_cursor

if TYPE_CHECKING:
    from .build_model import BuildContext


_TEMPLATE_PARAMETER_CURSOR_KINDS = frozenset({
    CursorKind.TEMPLATE_NON_TYPE_PARAMETER,
    CursorKind.TEMPLATE_TEMPLATE_PARAMETER,
    CursorKind.TEMPLATE_TYPE_PARAMETER,
})


# ==================================================================================================
#     Process Cursors
# ==================================================================================================


def process_class_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one class declaration and recurse into its children."""

    candidate_cpp = build_class_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppClass)
    if existing is not None:
        merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        merge_cpp_scalar(existing, "kind", candidate_cpp.kind, context, cursor)
        merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
        merge_class_bases(existing, candidate_cpp.bases, context, cursor)
        _visit_children(cursor.get_children(), existing, context)
        return

    cls = CppClass(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_node(owner, "add_class", cls)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)
        _visit_children(cursor.get_children(), attached, context)


def process_enum_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one enum declaration and recurse into its children."""

    candidate_cpp = build_enum_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppEnum)
    if existing is not None:
        merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        merge_cpp_scalar(existing, "underlying_type", candidate_cpp.underlying_type, context, cursor)
        merge_cpp_scalar(existing, "is_scoped", candidate_cpp.is_scoped, context, cursor)
        merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
        _visit_children(cursor.get_children(), existing, context)
        return

    enum_ = CppEnum(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_node(owner, "add_enum", enum_)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)
        _visit_children(cursor.get_children(), attached, context)


def process_class_template_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one class-template family and recurse into its declaration."""

    candidate_cpp = build_class_template_decl_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppClassTemplate)
    if existing is not None:
        declaration = existing.declaration
        child_cursors = list(cursor.get_children())
        merge_common_cpp_fields(declaration, candidate_cpp, context, cursor)
        merge_cpp_scalar(declaration, "kind", candidate_cpp.kind, context, cursor)
        merge_cpp_scalar(declaration, "visibility", candidate_cpp.visibility, context, cursor)
        merge_class_bases(declaration, candidate_cpp.bases, context, cursor)
        merge_template_parameters(
            declaration.cpp.template_parameters,
            candidate_cpp.template_parameters,
            context,
            cursor,
        )
        visit_non_template_parameter_children(child_cursors, declaration, context)
        return

    template = CppClassTemplate(
        name=cursor.spelling,
        declaration=CppClassTemplateDecl(
            name=cursor.spelling,
            cpp=candidate_cpp,
        ),
    )
    attached = attach_node(owner, "add_class_template", template)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)
        visit_non_template_parameter_children(
            cursor.get_children(),
            attached.declaration,
            context,
        )


def process_enumerator_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one enumerator declaration."""

    candidate_cpp = build_enumerator_cpp_facet(cursor)
    existing = lookup_registered_element(cursor, context, CppEnumerator)
    if existing is not None:
        warn_unexpected_repeated_declaration(context, cursor, "enumerator")
        return

    enumerator = CppEnumerator(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_node(owner, "add_enumerator", enumerator)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)


def process_function_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one free function declaration and recurse into its children."""

    candidate_cpp = build_function_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppFunction)
    if existing is not None:
        child_cursors = list(cursor.get_children())
        merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        merge_cpp_scalar(
            existing,
            "return_type",
            candidate_cpp.return_type,
            context,
            cursor,
            values_equivalent=cpp_types_equivalent,
        )
        merge_cpp_scalar(existing, "is_noexcept", candidate_cpp.is_noexcept, context, cursor)
        merge_callable_parameter_children(
            existing,
            child_cursors,
            context,
            register_element_for_cursor=register_element_for_cursor,
        )
        visit_non_parameter_children(child_cursors, existing, context)
        return

    function = CppFunction(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_node(owner, "add_function", function)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)
        _visit_children(cursor.get_children(), attached, context)


def process_alias_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one alias declaration."""

    candidate_cpp = build_alias_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppAlias)
    if existing is not None:
        warn_unexpected_repeated_declaration(context, cursor, "alias")
        return

    alias = CppAlias(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_node(owner, "add_alias", alias)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)


def process_function_template_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one function-template family and recurse into its declaration."""

    candidate_cpp = build_function_template_decl_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppFunctionTemplate)
    if existing is not None:
        declaration = existing.declaration
        child_cursors = list(cursor.get_children())
        merge_common_cpp_fields(declaration, candidate_cpp, context, cursor)
        merge_cpp_scalar(
            declaration,
            "return_type",
            candidate_cpp.return_type,
            context,
            cursor,
            values_equivalent=cpp_types_equivalent,
        )
        merge_cpp_scalar(declaration, "is_noexcept", candidate_cpp.is_noexcept, context, cursor)
        merge_cpp_scalar(declaration, "is_const", candidate_cpp.is_const, context, cursor)
        merge_cpp_scalar(declaration, "is_static", candidate_cpp.is_static, context, cursor)
        merge_cpp_scalar(declaration, "is_virtual", candidate_cpp.is_virtual, context, cursor)
        merge_cpp_scalar(declaration, "is_pure_virtual", candidate_cpp.is_pure_virtual, context, cursor)
        merge_template_parameters(
            declaration.cpp.template_parameters,
            candidate_cpp.template_parameters,
            context,
            cursor,
        )
        merge_callable_parameter_children(
            declaration,
            child_cursors,
            context,
            register_element_for_cursor=register_element_for_cursor,
        )
        visit_non_template_parameter_children(child_cursors, declaration, context)
        return

    template = CppFunctionTemplate(
        name=cursor.spelling,
        declaration=CppFunctionTemplateDecl(
            name=cursor.spelling,
            cpp=candidate_cpp,
        ),
    )
    attached = attach_node(owner, "add_function_template", template)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)
        visit_non_template_parameter_children(
            cursor.get_children(),
            attached.declaration,
            context,
        )


def process_method_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one method declaration and recurse into its children."""

    candidate_cpp = build_method_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppMethod)
    if existing is not None:
        child_cursors = list(cursor.get_children())
        merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        merge_cpp_scalar(
            existing,
            "return_type",
            candidate_cpp.return_type,
            context,
            cursor,
            values_equivalent=cpp_types_equivalent,
        )
        merge_cpp_scalar(existing, "is_noexcept", candidate_cpp.is_noexcept, context, cursor)
        merge_cpp_scalar(existing, "is_const", candidate_cpp.is_const, context, cursor)
        merge_cpp_scalar(existing, "is_static", candidate_cpp.is_static, context, cursor)
        merge_cpp_scalar(existing, "is_virtual", candidate_cpp.is_virtual, context, cursor)
        merge_cpp_scalar(existing, "is_pure_virtual", candidate_cpp.is_pure_virtual, context, cursor)
        merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
        merge_callable_parameter_children(
            existing,
            child_cursors,
            context,
            register_element_for_cursor=register_element_for_cursor,
        )
        visit_non_parameter_children(child_cursors, existing, context)
        return

    method = CppMethod(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_node(owner, "add_method", method)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)
        _visit_children(cursor.get_children(), attached, context)


def process_constructor_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one constructor declaration and recurse into its children."""

    candidate_cpp = build_constructor_cpp_facet(cursor)
    existing = lookup_registered_element(cursor, context, CppConstructor)
    if existing is not None:
        child_cursors = list(cursor.get_children())
        merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        merge_cpp_scalar(existing, "is_noexcept", candidate_cpp.is_noexcept, context, cursor)
        merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
        merge_callable_parameter_children(
            existing,
            child_cursors,
            context,
            register_element_for_cursor=register_element_for_cursor,
        )
        visit_non_parameter_children(child_cursors, existing, context)
        return

    constructor = CppConstructor(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_node(owner, "add_constructor", constructor)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)
        _visit_children(cursor.get_children(), attached, context)


def process_field_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one field declaration."""

    candidate_cpp = build_field_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppField)
    if existing is not None:
        warn_unexpected_repeated_declaration(context, cursor, "field")
        return

    field = CppField(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_node(owner, "add_field", field)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)


def process_parameter_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one parameter declaration."""

    candidate_cpp = build_parameter_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppParameter)
    if existing is not None:
        warn_unexpected_repeated_declaration(context, cursor, "parameter")
        return

    parameter = CppParameter(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_node(owner, "add_parameter", parameter)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)


def visit_non_parameter_children(
    child_cursors: Iterable[Any],
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Continue walking child cursors other than parameters."""

    for child_cursor in child_cursors:
        if getattr(child_cursor, "kind", None) == CursorKind.PARM_DECL:
            continue
        _visit_cursor(child_cursor, owner, context)


# ==================================================================================================
#     Helper Functions
# ==================================================================================================


def visit_non_template_parameter_children(
    child_cursors: Iterable[Any],
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Continue walking child cursors other than template-parameter helpers."""

    for child_cursor in child_cursors:
        if getattr(child_cursor, "kind", None) in _TEMPLATE_PARAMETER_CURSOR_KINDS:
            continue
        _visit_cursor(child_cursor, owner, context)


def _visit_children(
    child_cursors: Iterable[Any],
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Defer child walking to the main clang-walk module."""

    from .clang_walk import visit_children

    visit_children(child_cursors, owner, context)


def _visit_cursor(
    child_cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Defer one child visit to the main clang-walk module."""

    from .clang_walk import visit_cursor

    visit_cursor(child_cursor, owner, context)
