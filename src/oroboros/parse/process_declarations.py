from __future__ import annotations

"""Process concrete libclang declaration cursors into semantic model elements."""

from typing import TYPE_CHECKING, Any, Iterable

from clang.cindex import CursorKind

from ..model import (
    CppAlias,
    CppAliasTemplate,
    CppAliasTemplateDeclaration,
    CppClass,
    CppClassMembers,
    CppClassTemplate,
    CppClassTemplateDeclaration,
    CppConstructor,
    CppDestructor,
    CppElement,
    CppEnum,
    CppEnumerator,
    CppFunction,
    CppFunctionTemplate,
    CppFunctionTemplateDeclaration,
    CppMethod,
    CppMethodTemplate,
    CppMethodTemplateDeclaration,
    CppObservedTemplateInstance,
    CppParameter,
    CppTemplateArgument,
    CppVariable,
)
from ..model.template_ import _template_argument_key
from ..model.type import TemplateInstanceCppType
from ..model.type import cpp_types_equivalent
from .build_facets import (
    build_alias_cpp_facet,
    build_alias_template_declaration_cpp_facet,
    build_class_cpp_facet,
    build_class_template_declaration_cpp_facet,
    build_constructor_cpp_facet,
    build_destructor_cpp_facet,
    build_enum_cpp_facet,
    build_enumerator_cpp_facet,
    build_variable_cpp_facet,
    build_function_cpp_facet,
    build_function_template_declaration_cpp_facet,
    build_method_cpp_facet,
    build_method_template_declaration_cpp_facet,
    build_parameter_cpp_facet,
)
from .build_templates import build_template_parameters
from .cursor_data import cursor_source_location
from .merge_declarations import (
    describe_cursor_entity,
    merge_callable_parameter_children,
    merge_class_bases,
    merge_cpp_bool_enrichment,
    merge_common_cpp_fields,
    merge_cpp_scalar,
    merge_template_parameters,
    record_semantic_warning,
    warn_unexpected_repeated_declaration,
)
from .cursor_data import cursor_usr
from .element_registry import attach_element, lookup_registered_element, register_element_for_cursor
from .types import build_cpp_type

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


# ------------------------------------------------------------------------------
#     Class
# ------------------------------------------------------------------------------


def process_class_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one class declaration and recurse into its children."""

    if _handle_explicit_class_template_specialization(cursor, owner, context):
        return

    candidate_cpp = build_class_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppClass)
    if existing is not None:
        merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        merge_cpp_bool_enrichment(existing, "is_abstract", candidate_cpp.is_abstract)
        merge_cpp_scalar(existing, "kind", candidate_cpp.kind, context, cursor)
        merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
        merge_class_bases(existing, candidate_cpp.bases, context, cursor)
        _visit_children(cursor.get_children(), existing, context)
        return

    cls = CppClass(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_element(owner, "add_class", cls)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)
        _visit_children(cursor.get_children(), attached, context)


def process_constructor_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one constructor declaration and recurse into its children."""

    candidate_cpp = build_constructor_cpp_facet(cursor, context=context)
    constructor_name = _constructor_name_for_owner(owner, cursor)
    candidate_cpp.original_name = constructor_name
    existing = lookup_registered_element(cursor, context, CppConstructor)
    if existing is not None:
        child_cursors = list(cursor.get_children())
        merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        merge_cpp_scalar(existing, "special_member_kind", candidate_cpp.special_member_kind, context, cursor)
        merge_cpp_scalar(
            existing,
            "is_converting_constructor",
            candidate_cpp.is_converting_constructor,
            context,
            cursor,
        )
        merge_cpp_bool_enrichment(existing, "is_explicit", candidate_cpp.is_explicit)
        merge_cpp_scalar(existing, "is_noexcept", candidate_cpp.is_noexcept, context, cursor)
        merge_cpp_bool_enrichment(existing, "is_deleted", candidate_cpp.is_deleted)
        merge_cpp_bool_enrichment(existing, "is_defaulted", candidate_cpp.is_defaulted)
        merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
        merge_callable_parameter_children(
            existing,
            child_cursors,
            context,
            register_element_for_cursor=register_element_for_cursor,
        )
        visit_non_parameter_children(child_cursors, existing, context)
        apply_parameter_docs(existing)
        return

    constructor = CppConstructor(name=constructor_name, cpp=candidate_cpp)
    attached = attach_element(owner, "add_constructor", constructor)
    if attached is not None:
        _refresh_constructor_overload_indices(owner)
        register_element_for_cursor(cursor, attached, context)
        _visit_children(cursor.get_children(), attached, context)
        apply_parameter_docs(attached)


def process_destructor_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one destructor declaration."""

    candidate_cpp = build_destructor_cpp_facet(cursor, context=context)
    destructor_name = _destructor_name_for_owner(owner, cursor)
    candidate_cpp.original_name = destructor_name
    existing = lookup_registered_element(cursor, context, CppDestructor)
    if existing is not None:
        merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        merge_cpp_scalar(existing, "is_virtual", candidate_cpp.is_virtual, context, cursor)
        merge_cpp_scalar(existing, "is_pure_virtual", candidate_cpp.is_pure_virtual, context, cursor)
        merge_cpp_bool_enrichment(existing, "is_deleted", candidate_cpp.is_deleted)
        merge_cpp_bool_enrichment(existing, "is_defaulted", candidate_cpp.is_defaulted)
        merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
        visit_non_parameter_children(cursor.get_children(), existing, context)
        return

    destructor = CppDestructor(name=destructor_name, cpp=candidate_cpp)
    attached = attach_element(owner, "add_destructor", destructor)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)
        visit_non_parameter_children(cursor.get_children(), attached, context)


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
        merge_cpp_scalar(existing, "operator", candidate_cpp.operator, context, cursor)
        merge_cpp_scalar(existing, "special_member_kind", candidate_cpp.special_member_kind, context, cursor)
        merge_cpp_scalar(existing, "is_noexcept", candidate_cpp.is_noexcept, context, cursor)
        merge_cpp_bool_enrichment(existing, "is_deleted", candidate_cpp.is_deleted)
        merge_cpp_scalar(existing, "is_const", candidate_cpp.is_const, context, cursor)
        merge_cpp_scalar(existing, "ref_qualifier", candidate_cpp.ref_qualifier, context, cursor)
        merge_cpp_scalar(existing, "is_static", candidate_cpp.is_static, context, cursor)
        merge_cpp_scalar(existing, "is_virtual", candidate_cpp.is_virtual, context, cursor)
        merge_cpp_scalar(existing, "is_pure_virtual", candidate_cpp.is_pure_virtual, context, cursor)
        merge_cpp_bool_enrichment(existing, "is_defaulted", candidate_cpp.is_defaulted)
        merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
        merge_callable_parameter_children(
            existing,
            child_cursors,
            context,
            register_element_for_cursor=register_element_for_cursor,
        )
        visit_non_parameter_children(child_cursors, existing, context)
        apply_parameter_docs(existing)
        return

    method = CppMethod(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_element(owner, "add_method", method)
    if attached is not None:
        _refresh_method_overload_indices(owner)
        register_element_for_cursor(cursor, attached, context)
        _visit_children(cursor.get_children(), attached, context)
        apply_parameter_docs(attached)


def process_field_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one instance-variable declaration."""

    candidate_cpp = build_variable_cpp_facet(cursor, context=context, kind="member_variable")
    existing = lookup_registered_element(cursor, context, CppVariable)
    if existing is not None:
        warn_unexpected_repeated_declaration(context, cursor, "variable")
        return

    variable = CppVariable(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_element(owner, "add_variable", variable)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)


def process_variable_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one non-local `VAR_DECL` declaration."""

    attach_method_name = _variable_attach_method_name(owner)
    if attach_method_name is None:
        return

    candidate_cpp = build_variable_cpp_facet(
        cursor,
        context=context,
        kind="static_member_variable" if attach_method_name == "add_static_variable" else "variable",
    )
    existing = lookup_registered_element(cursor, context, CppVariable)
    if existing is not None:
        merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
        merge_cpp_scalar(
            existing,
            "type",
            candidate_cpp.type,
            context,
            cursor,
            values_equivalent=cpp_types_equivalent,
        )
        merge_cpp_scalar(existing, "is_const", candidate_cpp.is_const, context, cursor)
        merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
        merge_cpp_scalar(existing, "kind", candidate_cpp.kind, context, cursor)
        merge_cpp_scalar(existing, "storage_class", candidate_cpp.storage_class, context, cursor)
        merge_cpp_scalar(existing, "linkage", candidate_cpp.linkage, context, cursor)
        merge_cpp_scalar(existing, "tls_kind", candidate_cpp.tls_kind, context, cursor)
        merge_cpp_bool_enrichment(existing, "is_bitfield", candidate_cpp.is_bitfield)
        merge_cpp_scalar(existing, "bitfield_width", candidate_cpp.bitfield_width, context, cursor)
        merge_cpp_bool_enrichment(existing, "is_mutable", candidate_cpp.is_mutable)
        return

    variable = CppVariable(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_element(owner, attach_method_name, variable)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)


# ------------------------------------------------------------------------------
#     Class Template
# ------------------------------------------------------------------------------


def process_class_template_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one class-template family and recurse into its declaration."""

    candidate_cpp = build_class_template_declaration_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppClassTemplate)
    if existing is not None:
        declaration = existing.declaration
        child_cursors = list(cursor.get_children())
        merge_common_cpp_fields(declaration, candidate_cpp, context, cursor)
        merge_cpp_bool_enrichment(declaration, "is_abstract", candidate_cpp.is_abstract)
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
        declaration=CppClassTemplateDeclaration(
            name=cursor.spelling,
            cpp=candidate_cpp,
        ),
    )
    attached = attach_element(owner, "add_class_template", template)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)
        visit_non_template_parameter_children(
            cursor.get_children(),
            attached.declaration,
            context,
        )


def process_templated_constructor_cursor(
    template_cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one templated constructor under a class-like declaration."""

    candidate_cpp = build_constructor_cpp_facet(template_cursor, context=context)
    candidate_cpp.original_name = _constructor_name_for_owner(owner, template_cursor)
    candidate_cpp.template_parameters = build_template_parameters(template_cursor, context=context)

    existing = lookup_registered_element(template_cursor, context, CppConstructor)
    if existing is not None:
        child_cursors = list(template_cursor.get_children())
        merge_common_cpp_fields(existing, candidate_cpp, context, template_cursor)
        merge_cpp_scalar(existing, "special_member_kind", candidate_cpp.special_member_kind, context, template_cursor)
        merge_cpp_scalar(
            existing,
            "is_converting_constructor",
            candidate_cpp.is_converting_constructor,
            context,
            template_cursor,
        )
        merge_template_parameters(
            existing.cpp.template_parameters,
            candidate_cpp.template_parameters,
            context,
            template_cursor,
        )
        merge_cpp_scalar(existing, "is_noexcept", candidate_cpp.is_noexcept, context, template_cursor)
        merge_cpp_bool_enrichment(existing, "is_explicit", candidate_cpp.is_explicit)
        merge_cpp_bool_enrichment(existing, "is_deleted", candidate_cpp.is_deleted)
        merge_cpp_bool_enrichment(existing, "is_defaulted", candidate_cpp.is_defaulted)
        merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, template_cursor)
        register_element_for_cursor(template_cursor, existing, context)
        merge_callable_parameter_children(
            existing,
            child_cursors,
            context,
            register_element_for_cursor=register_element_for_cursor,
        )
        visit_non_parameter_children(child_cursors, existing, context)
        apply_parameter_docs(existing)
        return

    constructor = CppConstructor(
        name=_constructor_name_for_owner(owner, template_cursor),
        cpp=candidate_cpp,
    )
    attached = attach_element(owner, "add_constructor", constructor)
    if attached is not None:
        _refresh_constructor_overload_indices(owner)
        register_element_for_cursor(template_cursor, attached, context)
        _visit_children(template_cursor.get_children(), attached, context)
        apply_parameter_docs(attached)


# ------------------------------------------------------------------------------
#     Function
# ------------------------------------------------------------------------------


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
        merge_cpp_scalar(existing, "operator", candidate_cpp.operator, context, cursor)
        merge_cpp_scalar(existing, "is_noexcept", candidate_cpp.is_noexcept, context, cursor)
        merge_cpp_bool_enrichment(existing, "is_deleted", candidate_cpp.is_deleted)
        merge_callable_parameter_children(
            existing,
            child_cursors,
            context,
            register_element_for_cursor=register_element_for_cursor,
        )
        visit_non_parameter_children(child_cursors, existing, context)
        apply_parameter_docs(existing)
        return

    function = CppFunction(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_element(owner, "add_function", function)
    if attached is not None:
        _refresh_function_overload_indices(owner)
        register_element_for_cursor(cursor, attached, context)
        _visit_children(cursor.get_children(), attached, context)
        apply_parameter_docs(attached)


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
    attached = attach_element(owner, "add_parameter", parameter)
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


def apply_parameter_docs(callable_element: Any) -> None:
    """Copy callable-level parameter docs onto the owned parameter nodes."""

    cpp_doc = getattr(getattr(callable_element, "cpp", None), "doc", None)
    parameters = getattr(callable_element, "parameters", None)
    if cpp_doc is None or parameters is None:
        return

    parameter_docs = getattr(cpp_doc, "parameters", {})
    for parameter in parameters:
        if not parameter.name:
            parameter.cpp.doc = None
            continue
        parameter.cpp.doc = parameter_docs.get(parameter.name)


# ------------------------------------------------------------------------------
#     Function Template
# ------------------------------------------------------------------------------


def process_function_template_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one function-template family and recurse into its declaration."""

    child_cursors = list(cursor.get_children())
    constructor_owner = _templated_constructor_owner(cursor, owner, context)
    if constructor_owner is not None:
        process_templated_constructor_cursor(
            cursor,
            constructor_owner,
            context,
        )
        return

    method_template_owner = _templated_method_owner(cursor, owner, context)
    if method_template_owner is not None:
        process_method_template_cursor(
            cursor,
            method_template_owner,
            context,
        )
        return

    candidate_cpp = build_function_template_declaration_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppFunctionTemplate)
    if existing is not None:
        declaration = existing.declaration
        merge_common_cpp_fields(declaration, candidate_cpp, context, cursor)
        merge_cpp_scalar(
            declaration,
            "return_type",
            candidate_cpp.return_type,
            context,
            cursor,
            values_equivalent=cpp_types_equivalent,
        )
        merge_cpp_scalar(declaration, "operator", candidate_cpp.operator, context, cursor)
        merge_cpp_scalar(declaration, "is_noexcept", candidate_cpp.is_noexcept, context, cursor)
        merge_cpp_bool_enrichment(declaration, "is_deleted", candidate_cpp.is_deleted)
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
        apply_parameter_docs(declaration)
        return

    template = CppFunctionTemplate(
        name=cursor.spelling,
        declaration=CppFunctionTemplateDeclaration(
            name=cursor.spelling,
            cpp=candidate_cpp,
        ),
    )
    attached = attach_element(owner, "add_function_template", template)
    if attached is not None:
        _refresh_function_template_overload_indices(owner)
        register_element_for_cursor(cursor, attached, context)
        visit_non_template_parameter_children(
            child_cursors,
            attached.declaration,
            context,
        )
        apply_parameter_docs(attached.declaration)


def process_method_template_cursor(
    cursor: Any,
    owner: CppClassMembers,
    context: BuildContext,
) -> None:
    """Create or enrich one method-template family and recurse into its declaration."""

    child_cursors = list(cursor.get_children())
    candidate_cpp = build_method_template_declaration_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppMethodTemplate)
    if existing is not None:
        declaration = existing.declaration
        merge_common_cpp_fields(declaration, candidate_cpp, context, cursor)
        merge_cpp_scalar(
            declaration,
            "return_type",
            candidate_cpp.return_type,
            context,
            cursor,
            values_equivalent=cpp_types_equivalent,
        )
        merge_cpp_scalar(declaration, "operator", candidate_cpp.operator, context, cursor)
        merge_cpp_scalar(declaration, "special_member_kind", candidate_cpp.special_member_kind, context, cursor)
        merge_cpp_scalar(declaration, "is_noexcept", candidate_cpp.is_noexcept, context, cursor)
        merge_cpp_bool_enrichment(declaration, "is_deleted", candidate_cpp.is_deleted)
        merge_cpp_scalar(declaration, "is_const", candidate_cpp.is_const, context, cursor)
        merge_cpp_scalar(declaration, "ref_qualifier", candidate_cpp.ref_qualifier, context, cursor)
        merge_cpp_scalar(declaration, "is_static", candidate_cpp.is_static, context, cursor)
        merge_cpp_scalar(declaration, "is_virtual", candidate_cpp.is_virtual, context, cursor)
        merge_cpp_scalar(declaration, "is_pure_virtual", candidate_cpp.is_pure_virtual, context, cursor)
        merge_cpp_bool_enrichment(declaration, "is_defaulted", candidate_cpp.is_defaulted)
        merge_cpp_scalar(declaration, "visibility", candidate_cpp.visibility, context, cursor)
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
        apply_parameter_docs(declaration)
        return

    template = CppMethodTemplate(
        name=cursor.spelling,
        declaration=CppMethodTemplateDeclaration(
            name=cursor.spelling,
            cpp=candidate_cpp,
        ),
    )
    attached = attach_element(owner, "add_method_template", template)
    if attached is not None:
        _refresh_method_template_overload_indices(owner)
        register_element_for_cursor(cursor, attached, context)
        visit_non_template_parameter_children(
            child_cursors,
            attached.declaration,
            context,
        )
        apply_parameter_docs(attached.declaration)


# ------------------------------------------------------------------------------
#     Enum
# ------------------------------------------------------------------------------


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
    attached = attach_element(owner, "add_enum", enum_)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)
        _visit_children(cursor.get_children(), attached, context)


def process_enumerator_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one enumerator declaration."""

    candidate_cpp = build_enumerator_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppEnumerator)
    if existing is not None:
        warn_unexpected_repeated_declaration(context, cursor, "enumerator")
        return

    enumerator = CppEnumerator(name=cursor.spelling, cpp=candidate_cpp)
    attached = attach_element(owner, "add_enumerator", enumerator)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)


# ------------------------------------------------------------------------------
#     Alias
# ------------------------------------------------------------------------------


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
    attached = attach_element(owner, "add_alias", alias)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)


def process_alias_template_cursor(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> None:
    """Create or enrich one alias-template family."""

    candidate_cpp = build_alias_template_declaration_cpp_facet(cursor, context=context)
    existing = lookup_registered_element(cursor, context, CppAliasTemplate)
    if existing is not None:
        declaration = existing.declaration
        merge_common_cpp_fields(declaration, candidate_cpp, context, cursor)
        merge_cpp_scalar(
            declaration,
            "target",
            candidate_cpp.target,
            context,
            cursor,
            values_equivalent=cpp_types_equivalent,
        )
        merge_cpp_scalar(declaration, "visibility", candidate_cpp.visibility, context, cursor)
        merge_cpp_scalar(declaration, "kind", candidate_cpp.kind, context, cursor)
        merge_template_parameters(
            declaration.cpp.template_parameters,
            candidate_cpp.template_parameters,
            context,
            cursor,
        )
        return

    template = CppAliasTemplate(
        name=cursor.spelling,
        declaration=CppAliasTemplateDeclaration(
            name=cursor.spelling,
            cpp=candidate_cpp,
        ),
    )
    attached = attach_element(owner, "add_alias_template", template)
    if attached is not None:
        register_element_for_cursor(cursor, attached, context)


# ==================================================================================================
#     Helper Functions
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Visitors
# ------------------------------------------------------------------------------


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


# ------------------------------------------------------------------------------
#     Naming
# ------------------------------------------------------------------------------


def _constructor_name_for_owner(
    owner: CppElement,
    cursor: Any,
) -> str:
    """Normalize one constructor name against the owning class-like declaration."""

    owner_name = getattr(owner, "name", "")
    if owner_name:
        return owner_name
    return cursor.spelling


def _destructor_name_for_owner(
    owner: CppElement,
    cursor: Any,
) -> str:
    """Normalize one destructor name against the owning class-like declaration."""

    owner_name = getattr(owner, "name", "")
    if owner_name:
        return f"~{owner_name}"
    spelling = cursor.spelling or ""
    return spelling


def _variable_attach_method_name(owner: CppElement) -> str | None:
    """Return how one parsed `VAR_DECL` should attach under the current owner."""

    from ..model import CppClassMembers, CppModule, CppNamespace

    if isinstance(owner, CppClassMembers):
        return "add_static_variable"

    if isinstance(owner, (CppModule, CppNamespace)):
        return "add_variable"

    return None


# ------------------------------------------------------------------------------
#     Explicit Class Template Specialization
# ------------------------------------------------------------------------------


def _handle_explicit_class_template_specialization(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> bool:
    """Fold one explicit class-template specialization into the template-family path."""

    specialization_type = _explicit_class_template_specialization_type(cursor, context)
    if specialization_type is None:
        return False

    template_family = _find_class_template_family_for_specialization(owner, cursor.spelling)
    if template_family is not None:
        _record_observed_class_template_specialization(
            template_family,
            specialization_type.arguments,
            cursor,
        )

    if _should_warn_about_explicit_class_template_specialization(owner, context):
        _warn_explicit_class_template_specialization(cursor, template_family, context)

    # The current model does not represent explicit class specializations as
    # full declaration trees. Keep their concrete arguments when we can, and
    # otherwise ignore the specialization instead of materializing a duplicate
    # plain class node.
    return True


def _explicit_class_template_specialization_type(
    cursor: Any,
    context: BuildContext,
) -> TemplateInstanceCppType | None:
    """Return the structured specialized type for one explicit specialization cursor."""

    cursor_type = getattr(cursor, "type", None)
    if cursor_type is None:
        return None

    cpp_type = build_cpp_type(
        cursor_type,
        context=context,
        source_cursor=cursor,
    )
    if not isinstance(cpp_type, TemplateInstanceCppType):
        return None

    if cpp_type.template_name.split("::")[-1] != cursor.spelling:
        return None
    return cpp_type


def _find_class_template_family_for_specialization(
    owner: CppElement,
    template_name: str,
) -> CppClassTemplate | None:
    """Return the already materialized class-template family for one specialization."""

    declarations = getattr(owner, "declarations", None)
    class_templates = getattr(declarations, "class_templates", None)
    if class_templates is None:
        return None

    for template in class_templates:
        if template.name == template_name:
            return template
    return None


def _record_observed_class_template_specialization(
    template: CppClassTemplate,
    arguments: list[CppTemplateArgument],
    cursor: Any,
) -> None:
    """Record one explicit specialization as an observed template instance."""

    observed_instances = template.declaration.cpp.observed_instances
    argument_key = _template_argument_key(arguments)
    observation_location = cursor_source_location(cursor)

    for observed_instance in observed_instances:
        if _template_argument_key(observed_instance.arguments) != argument_key:
            continue
        if observation_location is not None and observation_location not in observed_instance.locations:
            observed_instance.locations.append(observation_location)
        return

    observed_instances.append(
        CppObservedTemplateInstance(
            arguments=list(arguments),
            locations=[] if observation_location is None else [observation_location],
        )
    )


def _should_warn_about_explicit_class_template_specialization(
    owner: CppElement,
    context: BuildContext,
) -> bool:
    """Return whether one ignored explicit specialization should produce a warning."""

    if _owner_is_std_namespace(owner):
        return context.config.warn_std_explicit_class_template_specializations
    return True


def _owner_is_std_namespace(owner: CppElement) -> bool:
    """Return whether the current owning scope is the standard namespace."""

    return getattr(owner, "qualified_name", "") == "std"


def _warn_explicit_class_template_specialization(
    cursor: Any,
    template_family: CppClassTemplate | None,
    context: BuildContext,
) -> None:
    """Emit one actionable warning about unsupported explicit specialization bodies."""

    if template_family is None:
        family_hint = (
            "The primary template is not active in the current parsed model, so this "
            "specialization is ignored entirely."
        )
    else:
        family_hint = (
            f"The primary template family '{template_family.qualified_name}' is active, "
            "so its concrete arguments may still be observed."
        )

    record_semantic_warning(
        context,
        f"Explicit class-template specialization for {describe_cursor_entity(cursor)} "
        "is not modeled as its own specialized declaration tree yet. "
        f"{family_hint} We do currently not yet fully support binding this specialization as its own API surface.",
        code="parse.explicit_class_template_specialization_ignored",
        cursor=cursor,
    )


# ------------------------------------------------------------------------------
#     Miscellaneous
# ------------------------------------------------------------------------------


def _looks_like_templated_constructor(
    cursor: Any,
    owner: CppElement,
) -> bool:
    """Return whether one function-template cursor is actually a templated constructor."""

    if not isinstance(owner, CppClassMembers):
        return False

    spelling = cursor.spelling or ""
    if spelling == owner.name:
        return True

    return _strip_trailing_template_arguments(spelling) == owner.name


def _templated_constructor_owner(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> CppClassMembers | None:
    """Resolve the owning class-like element when one function-template cursor is a constructor."""

    if _looks_like_templated_constructor(cursor, owner):
        return owner if isinstance(owner, CppClassMembers) else None

    semantic_owner = _lookup_semantic_owner_for_cursor(cursor, context)
    if semantic_owner is None:
        return None

    if _looks_like_templated_constructor(cursor, semantic_owner):
        return semantic_owner

    return None


def _templated_method_owner(
    cursor: Any,
    owner: CppElement,
    context: BuildContext,
) -> CppClassMembers | None:
    """Resolve the owning class-like element when one function-template cursor is a method."""

    if isinstance(owner, CppClassMembers) and not _looks_like_templated_constructor(cursor, owner):
        return owner

    semantic_owner = _lookup_semantic_owner_for_cursor(cursor, context)
    if semantic_owner is None:
        return None

    if not _looks_like_templated_constructor(cursor, semantic_owner):
        return semantic_owner

    return None


def _lookup_semantic_owner_for_cursor(
    cursor: Any,
    context: BuildContext,
) -> CppClassMembers | None:
    """Return the parsed class-like semantic owner of one cursor when available."""

    semantic_parent = getattr(cursor, "semantic_parent", None)
    semantic_parent_usr = cursor_usr(semantic_parent)
    if semantic_parent_usr is None:
        return None

    semantic_owner = context.usr_to_element.get(semantic_parent_usr)
    if isinstance(semantic_owner, CppClassTemplate):
        return semantic_owner.declaration
    if isinstance(semantic_owner, CppClassMembers):
        return semantic_owner
    return None


def _strip_trailing_template_arguments(name: str) -> str:
    """Strip one trailing `<...>` suffix from a spelling when it is balanced."""

    if not name.endswith(">"):
        return name

    depth = 0
    for index in range(len(name) - 1, -1, -1):
        character = name[index]
        if character == ">":
            depth += 1
        elif character == "<":
            depth -= 1
            if depth == 0:
                return name[:index]

    return name


# ------------------------------------------------------------------------------
#     Overload Index Ordering
# ------------------------------------------------------------------------------


def _refresh_function_overload_indices(owner: CppElement) -> None:
    """Assign stable overload indices across one free-function sibling collection."""

    declarations = getattr(owner, "declarations", None)
    functions = getattr(declarations, "functions", None)
    if functions is not None:
        _assign_overload_indices(functions)


def _refresh_method_overload_indices(owner: CppElement) -> None:
    """Assign stable overload indices across one method sibling collection."""

    declarations = getattr(owner, "declarations", None)
    methods = getattr(declarations, "methods", None)
    if methods is not None:
        _assign_overload_indices(methods)


def _refresh_constructor_overload_indices(owner: CppElement) -> None:
    """Assign stable overload indices across one constructor sibling collection."""

    declarations = getattr(owner, "declarations", None)
    constructors = getattr(declarations, "constructors", None)
    if constructors is not None:
        _assign_overload_indices(constructors)


def _refresh_function_template_overload_indices(owner: CppElement) -> None:
    """Assign stable overload indices across one function-template sibling collection."""

    declarations = getattr(owner, "declarations", None)
    templates = getattr(declarations, "function_templates", None)
    if templates is not None:
        _assign_overload_indices(
            templates,
            declaration_getter=lambda template: getattr(template, "declaration", None),
        )


def _refresh_method_template_overload_indices(owner: CppElement) -> None:
    """Assign stable overload indices across one method-template sibling collection."""

    declarations = getattr(owner, "declarations", None)
    templates = getattr(declarations, "method_templates", None)
    if templates is not None:
        _assign_overload_indices(
            templates,
            declaration_getter=lambda template: getattr(template, "declaration", None),
        )


def _assign_overload_indices(
    elements: Iterable[Any],
    *,
    declaration_getter: Any | None = None,
) -> None:
    """Assign same-name overload indices in declaration order for one collection."""

    next_index_by_name: dict[str, int] = {}
    for element in elements:
        target = declaration_getter(element) if declaration_getter is not None else element
        if target is None:
            continue

        cpp = getattr(target, "cpp", None)
        name = getattr(target, "name", "")
        if cpp is None or not hasattr(cpp, "overload_index") or not name:
            continue

        overload_index = next_index_by_name.get(name, 0)
        cpp.overload_index = overload_index
        next_index_by_name[name] = overload_index + 1
