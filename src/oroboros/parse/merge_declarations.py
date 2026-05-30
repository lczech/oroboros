from __future__ import annotations

"""High-level repeated-declaration merge helpers."""

from typing import TYPE_CHECKING, Any, Iterable

from clang.cindex import CursorKind

from ..model import (
    CppAlias,
    CppAliasTemplate,
    CppClass,
    CppClassTemplate,
    CppConstructor,
    CppDestructor,
    CppElement,
    CppEnum,
    CppEnumerator,
    CppFunction,
    CppFunctionTemplate,
    CppMethod,
    CppMethodTemplate,
    CppParameter,
    CppVariable,
)
from ..model.type import cpp_types_equivalent
from .extract_cpp_facets import extract_parameter_cpp_facet
from .cursor_data import cursor_is_from_active_header
from .element_registry import register_element_for_cursor
from .merge_properties import (
    merge_class_bases,
    merge_common_cpp_fields,
    merge_cpp_bool_enrichment,
    merge_cpp_scalar,
    merge_template_parameters,
    warn_unexpected_repeated_declaration,
)

if TYPE_CHECKING:
    from .build_model import BuildContext


# ==================================================================================================
#     Declaration Merges
# ==================================================================================================


def merge_class_declaration(
    existing: CppClass,
    candidate_cpp: Any,
    cursor: Any,
    context: BuildContext,
) -> None:
    """Enrich one repeated class declaration from its latest cursor."""

    merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
    merge_cpp_bool_enrichment(existing, "is_abstract", candidate_cpp.is_abstract)
    merge_cpp_scalar(existing, "kind", candidate_cpp.kind, context, cursor)
    merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)
    merge_class_bases(existing, candidate_cpp.bases, context, cursor)


def merge_constructor_declaration(
    existing: CppConstructor,
    candidate_cpp: Any,
    cursor: Any,
    context: BuildContext,
) -> None:
    """Enrich one repeated constructor declaration from its latest cursor."""

    merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
    merge_template_parameters(
        existing.cpp.template_parameters,
        candidate_cpp.template_parameters,
        context,
        cursor,
    )
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


def merge_templated_constructor_declaration(
    existing: CppConstructor,
    candidate_cpp: Any,
    template_cursor: Any,
    context: BuildContext,
) -> None:
    """Enrich one repeated templated-constructor declaration from its latest cursor."""

    merge_constructor_declaration(existing, candidate_cpp, template_cursor, context)


def merge_destructor_declaration(
    existing: CppDestructor,
    candidate_cpp: Any,
    cursor: Any,
    context: BuildContext,
) -> None:
    """Enrich one repeated destructor declaration from its latest cursor."""

    merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
    merge_cpp_scalar(existing, "is_virtual", candidate_cpp.is_virtual, context, cursor)
    merge_cpp_scalar(existing, "is_pure_virtual", candidate_cpp.is_pure_virtual, context, cursor)
    merge_cpp_bool_enrichment(existing, "is_deleted", candidate_cpp.is_deleted)
    merge_cpp_bool_enrichment(existing, "is_defaulted", candidate_cpp.is_defaulted)
    merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)


def merge_method_declaration(
    existing: CppMethod,
    candidate_cpp: Any,
    cursor: Any,
    context: BuildContext,
) -> None:
    """Enrich one repeated method declaration from its latest cursor."""

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


def merge_field_declaration(
    context: BuildContext,
    cursor: Any,
) -> None:
    """Handle one repeated field declaration."""

    warn_unexpected_repeated_declaration(context, cursor, "variable")


def merge_variable_declaration(
    existing: CppVariable,
    candidate_cpp: Any,
    cursor: Any,
    context: BuildContext,
) -> None:
    """Enrich one repeated variable declaration from its latest cursor."""

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


def merge_class_template_declaration(
    existing: CppClassTemplate,
    candidate_cpp: Any,
    cursor: Any,
    context: BuildContext,
) -> None:
    """Enrich one repeated class-template family from its latest cursor."""

    declaration = existing.declaration
    merge_class_declaration(declaration, candidate_cpp, cursor, context)
    merge_template_parameters(
        declaration.cpp.template_parameters,
        candidate_cpp.template_parameters,
        context,
        cursor,
    )


def merge_function_declaration(
    existing: CppFunction,
    candidate_cpp: Any,
    cursor: Any,
    context: BuildContext,
) -> None:
    """Enrich one repeated free-function declaration from its latest cursor."""

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


def merge_parameter_declaration(
    context: BuildContext,
    cursor: Any,
) -> None:
    """Handle one repeated parameter declaration."""

    warn_unexpected_repeated_declaration(context, cursor, "parameter")


def merge_function_template_declaration(
    existing: CppFunctionTemplate,
    candidate_cpp: Any,
    cursor: Any,
    context: BuildContext,
) -> None:
    """Enrich one repeated function-template family from its latest cursor."""

    declaration = existing.declaration
    merge_function_declaration(declaration, candidate_cpp, cursor, context)
    merge_template_parameters(
        declaration.cpp.template_parameters,
        candidate_cpp.template_parameters,
        context,
        cursor,
    )


def merge_method_template_declaration(
    existing: CppMethodTemplate,
    candidate_cpp: Any,
    cursor: Any,
    context: BuildContext,
) -> None:
    """Enrich one repeated method-template family from its latest cursor."""

    declaration = existing.declaration
    merge_method_declaration(declaration, candidate_cpp, cursor, context)
    merge_template_parameters(
        declaration.cpp.template_parameters,
        candidate_cpp.template_parameters,
        context,
        cursor,
    )


def merge_enum_declaration(
    existing: CppEnum,
    candidate_cpp: Any,
    cursor: Any,
    context: BuildContext,
) -> None:
    """Enrich one repeated enum declaration from its latest cursor."""

    merge_common_cpp_fields(existing, candidate_cpp, context, cursor)
    merge_cpp_scalar(existing, "underlying_type", candidate_cpp.underlying_type, context, cursor)
    merge_cpp_scalar(existing, "is_scoped", candidate_cpp.is_scoped, context, cursor)
    merge_cpp_scalar(existing, "visibility", candidate_cpp.visibility, context, cursor)


def merge_enumerator_declaration(
    context: BuildContext,
    cursor: Any,
) -> None:
    """Handle one repeated enumerator declaration."""

    warn_unexpected_repeated_declaration(context, cursor, "enumerator")


def merge_alias_declaration(
    context: BuildContext,
    cursor: Any,
) -> None:
    """Handle one repeated alias declaration."""

    warn_unexpected_repeated_declaration(context, cursor, "alias")


def merge_alias_template_declaration(
    existing: CppAliasTemplate,
    candidate_cpp: Any,
    cursor: Any,
    context: BuildContext,
) -> None:
    """Enrich one repeated alias-template family from its latest cursor."""

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


def merge_callable_parameter_children(
    callable_element: Any,
    child_cursors: Iterable[Any],
    context: BuildContext,
) -> None:
    """Merge callable parameters positionally across repeated declarations."""

    parameter_cursors = [
        child_cursor
        for child_cursor in child_cursors
        if cursor_is_from_active_header(child_cursor, context.active_headers)
        and getattr(child_cursor, "kind", None) == CursorKind.PARM_DECL
    ]
    existing_parameters = list(getattr(callable_element, "parameters", []))

    if len(existing_parameters) != len(parameter_cursors):
        return

    for existing_parameter, parameter_cursor in zip(
        existing_parameters,
        parameter_cursors,
        strict=True,
    ):
        candidate_cpp = extract_parameter_cpp_facet(parameter_cursor, context=context)
        register_element_for_cursor(parameter_cursor, existing_parameter, context)
        merge_common_cpp_fields(
            existing_parameter,
            candidate_cpp,
            context,
            parameter_cursor,
            merge_documentation=False,
            merge_original_name=False,
        )
        merge_cpp_scalar(
            existing_parameter,
            "type",
            candidate_cpp.type,
            context,
            parameter_cursor,
            values_equivalent=cpp_types_equivalent,
        )
        merge_cpp_scalar(
            existing_parameter,
            "default_value",
            candidate_cpp.default_value,
            context,
            parameter_cursor,
        )
