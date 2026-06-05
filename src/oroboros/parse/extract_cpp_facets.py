from __future__ import annotations

"""Extract parsed `.cpp` facet data from libclang cursors.

This module is the declaration-surface layer of the parser. It gathers the
facts that belong directly on semantic elements, such as locations, docs,
availability, surface types, and template-parameter signatures, while leaving
type translation and template observation details to their dedicated modules.
"""

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from ..model import CppClassBase, CppDocumentation, CppLocationInfo
from .extract_templates import extract_template_parameters
from .comment_recovery import resolve_cursor_comment
from .cursor_data import (
    cursor_alias_kind,
    cursor_alias_template_target_cursor,
    cursor_alias_template_target_type,
    cursor_alias_target_type,
    cursor_availability,
    cursor_bool_method,
    cursor_callable_is_defaulted,
    cursor_callable_is_deleted,
    cursor_class_kind,
    cursor_class_is_abstract,
    cursor_class_template_is_abstract,
    cursor_constructor_special_member_kind,
    cursor_enum_underlying_type,
    cursor_enum_value_spelling,
    cursor_field_bitfield_width,
    cursor_field_is_bitfield,
    cursor_field_is_mutable,
    cursor_has_explicit_specifier,
    cursor_is_converting_constructor,
    cursor_is_definition,
    cursor_is_noexcept,
    cursor_is_scoped_enum,
    cursor_linkage,
    cursor_namespace_is_inline,
    cursor_method_special_member_kind,
    cursor_operator,
    cursor_parameter_default_value,
    cursor_ref_qualifier,
    cursor_source_location,
    cursor_storage_class,
    cursor_tls_kind,
    cursor_type_is_const_qualified,
    cursor_visibility,
    is_base_specifier_cursor,
    is_struct_cursor,
)
from .template_observations import record_template_observation_hints_in_type
from .types import build_cpp_type

if TYPE_CHECKING:
    from .build_model import BuildContext


# ==================================================================================================
#     Facet Extraction
# ==================================================================================================


def _resolve_facet_documentation(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> CppDocumentation | None:
    """Resolve the documentation values that should be written onto one parsed `.cpp` facet."""

    resolution = resolve_cursor_comment(cursor, context)
    if (
        resolution.selected_attached_comment is None
        and resolution.clang_raw_comment is None
        and resolution.selected_attached_doc is None
    ):
        return None

    return CppDocumentation(
        attached_comment=resolution.selected_attached_comment,
        clang_raw_comment=resolution.clang_raw_comment,
        parsed=resolution.selected_attached_doc,
    )


def extract_parameter_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed parameter facet from one clang cursor."""

    from ..model import CppParameterCppFacet

    return CppParameterCppFacet(
        original_name=cursor.spelling or None,
        type=_extract_surface_cpp_type(
            getattr(cursor, "type", None),
            context=context,
            source_cursor=cursor,
        ),
        default_value=cursor_parameter_default_value(cursor),
        location=extract_location_info(cursor),
    )


# ------------------------------------------------------------------------------
#     Namespace
# ------------------------------------------------------------------------------


def extract_namespace_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed namespace facet from one clang cursor."""

    from ..model import CppNamespaceCppFacet
    documentation = _resolve_facet_documentation(cursor, context=context)

    return CppNamespaceCppFacet(
        original_name=cursor.spelling or None,
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
        is_inline=cursor_namespace_is_inline(cursor),
    )


# ------------------------------------------------------------------------------
#     Class
# ------------------------------------------------------------------------------


def extract_class_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed class/struct facet from one clang cursor."""

    from ..model import CppClassCppFacet
    documentation = _resolve_facet_documentation(cursor, context=context)

    return CppClassCppFacet(
        original_name=cursor.spelling or None,
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
        is_abstract=cursor_class_is_abstract(cursor),
        kind=cursor_class_kind(cursor),
        visibility=cursor_visibility(cursor),
        bases=extract_class_bases(cursor, context=context),
    )


def extract_class_template_declaration_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed generic class-template declaration facet."""

    from ..model import CppClassTemplateDeclarationCppFacet
    documentation = _resolve_facet_documentation(cursor, context=context)

    return CppClassTemplateDeclarationCppFacet(
        original_name=cursor.spelling or None,
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
        is_abstract=cursor_class_template_is_abstract(cursor),
        kind=cursor_class_kind(cursor),
        visibility=cursor_visibility(cursor),
        bases=extract_class_bases(cursor, context=context),
        template_parameters=extract_template_parameters(cursor, context=context),
    )


def extract_method_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed method facet from one clang cursor."""

    from ..model import CppMethodCppFacet
    documentation = _resolve_facet_documentation(cursor, context=context)
    return_type = _extract_surface_cpp_type(
        getattr(cursor, "result_type", None),
        context=context,
        source_cursor=cursor,
    )

    return CppMethodCppFacet(
        original_name=cursor.spelling or None,
        operator=_build_operator_metadata(cursor, return_type),
        return_type=return_type,
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
        special_member_kind=cursor_method_special_member_kind(cursor),
        is_noexcept=cursor_is_noexcept(cursor),
        is_deleted=cursor_callable_is_deleted(cursor, context=context),
        is_const=cursor_bool_method(cursor, "is_const_method"),
        ref_qualifier=cursor_ref_qualifier(cursor),
        is_static=cursor_bool_method(cursor, "is_static_method"),
        is_virtual=cursor_bool_method(cursor, "is_virtual_method"),
        is_pure_virtual=cursor_bool_method(cursor, "is_pure_virtual_method"),
        is_defaulted=cursor_callable_is_defaulted(cursor, context=context),
        visibility=cursor_visibility(cursor),
    )


def extract_constructor_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed constructor facet from one clang cursor."""

    from ..model import CppConstructorCppFacet
    documentation = _resolve_facet_documentation(cursor, context=context)

    return CppConstructorCppFacet(
        original_name=cursor.spelling or None,
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
        special_member_kind=cursor_constructor_special_member_kind(cursor),
        is_converting_constructor=cursor_is_converting_constructor(cursor),
        is_explicit=cursor_has_explicit_specifier(cursor),
        is_noexcept=cursor_is_noexcept(cursor),
        is_deleted=cursor_callable_is_deleted(cursor, context=context),
        is_defaulted=cursor_callable_is_defaulted(cursor, context=context),
        visibility=cursor_visibility(cursor),
    )


def extract_destructor_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed destructor facet from one clang cursor."""

    from ..model import CppDestructorCppFacet
    documentation = _resolve_facet_documentation(cursor, context=context)

    return CppDestructorCppFacet(
        original_name=cursor.spelling or None,
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
        is_virtual=cursor_bool_method(cursor, "is_virtual_method"),
        is_pure_virtual=cursor_bool_method(cursor, "is_pure_virtual_method"),
        is_deleted=cursor_callable_is_deleted(cursor, context=context),
        is_defaulted=cursor_callable_is_defaulted(cursor, context=context),
        visibility=cursor_visibility(cursor),
    )


def extract_variable_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
    kind: str = "variable",
) -> Any:
    """Extract one parsed variable facet from one clang cursor."""

    from ..model import CppVariableCppFacet
    documentation = _resolve_facet_documentation(cursor, context=context)

    return CppVariableCppFacet(
        original_name=cursor.spelling or None,
        type=_extract_surface_cpp_type(
            getattr(cursor, "type", None),
            context=context,
            source_cursor=cursor,
        ),
        is_const=cursor_type_is_const_qualified(cursor),
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
        visibility=cursor_visibility(cursor),
        kind=kind,
        storage_class=cursor_storage_class(cursor),
        linkage=cursor_linkage(cursor),
        tls_kind=cursor_tls_kind(cursor),
        is_bitfield=cursor_field_is_bitfield(cursor),
        bitfield_width=cursor_field_bitfield_width(cursor),
        is_mutable=cursor_field_is_mutable(cursor),
    )


# ------------------------------------------------------------------------------
#     Function
# ------------------------------------------------------------------------------


def extract_function_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed free-function facet from one clang cursor."""

    from ..model import CppFunctionCppFacet
    documentation = _resolve_facet_documentation(cursor, context=context)
    return_type = _extract_surface_cpp_type(
        getattr(cursor, "result_type", None),
        context=context,
        source_cursor=cursor,
    )

    return CppFunctionCppFacet(
        original_name=cursor.spelling or None,
        operator=_build_operator_metadata(cursor, return_type),
        return_type=return_type,
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
        is_noexcept=cursor_is_noexcept(cursor),
        is_deleted=cursor_callable_is_deleted(cursor, context=context),
    )


def extract_function_template_declaration_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed generic function-template declaration facet."""

    from ..model import CppFunctionTemplateDeclarationCppFacet
    documentation = _resolve_facet_documentation(cursor, context=context)
    return_type = _extract_surface_cpp_type(
        getattr(cursor, "result_type", None),
        context=context,
        source_cursor=cursor,
    )

    return CppFunctionTemplateDeclarationCppFacet(
        original_name=cursor.spelling or None,
        operator=_build_operator_metadata(cursor, return_type),
        return_type=return_type,
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
        is_noexcept=cursor_is_noexcept(cursor),
        is_deleted=cursor_callable_is_deleted(cursor, context=context),
        template_parameters=extract_template_parameters(cursor, context=context),
    )


def extract_method_template_declaration_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed generic method-template declaration facet."""

    from ..model import CppMethodTemplateDeclarationCppFacet
    documentation = _resolve_facet_documentation(cursor, context=context)
    return_type = _extract_surface_cpp_type(
        getattr(cursor, "result_type", None),
        context=context,
        source_cursor=cursor,
    )

    return CppMethodTemplateDeclarationCppFacet(
        original_name=cursor.spelling or None,
        operator=_build_operator_metadata(cursor, return_type),
        return_type=return_type,
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
        special_member_kind=cursor_method_special_member_kind(cursor),
        is_noexcept=cursor_is_noexcept(cursor),
        is_deleted=cursor_callable_is_deleted(cursor, context=context),
        is_const=cursor_bool_method(cursor, "is_const_method"),
        ref_qualifier=cursor_ref_qualifier(cursor),
        is_static=cursor_bool_method(cursor, "is_static_method"),
        is_virtual=cursor_bool_method(cursor, "is_virtual_method"),
        is_pure_virtual=cursor_bool_method(cursor, "is_pure_virtual_method"),
        is_defaulted=cursor_callable_is_defaulted(cursor, context=context),
        template_parameters=extract_template_parameters(cursor, context=context),
        visibility=cursor_visibility(cursor),
    )


# ------------------------------------------------------------------------------
#     Enum
# ------------------------------------------------------------------------------


def extract_enum_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed enum facet from one clang cursor."""

    from ..model import CppEnumCppFacet
    documentation = _resolve_facet_documentation(cursor, context=context)

    return CppEnumCppFacet(
        original_name=cursor.spelling or None,
        underlying_type=build_cpp_type(
            cursor_enum_underlying_type(cursor),
            context=context,
            source_cursor=cursor,
        ),
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
        is_scoped=cursor_is_scoped_enum(cursor),
        visibility=cursor_visibility(cursor),
    )


def extract_enumerator_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed enumerator facet from one clang cursor."""

    from ..model import CppEnumeratorCppFacet
    documentation = _resolve_facet_documentation(cursor, context=context)

    return CppEnumeratorCppFacet(
        original_name=cursor.spelling or None,
        value_spelling=cursor_enum_value_spelling(cursor),
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
    )


# ------------------------------------------------------------------------------
#     Alias
# ------------------------------------------------------------------------------


def extract_alias_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed alias facet from one clang cursor."""

    from ..model import CppAliasCppFacet
    documentation = _resolve_facet_documentation(cursor, context=context)

    return CppAliasCppFacet(
        original_name=cursor.spelling or None,
        target=_extract_surface_cpp_type(
            cursor_alias_target_type(cursor),
            context=context,
            source_cursor=cursor,
        ),
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
        visibility=cursor_visibility(cursor),
        kind=cursor_alias_kind(cursor),
    )


def extract_alias_template_declaration_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Extract one parsed generic alias-template declaration facet."""

    from ..model import CppAliasTemplateDeclarationCppFacet

    documentation = _resolve_facet_documentation(cursor, context=context)
    target_cursor = cursor_alias_template_target_cursor(cursor)

    body_type = build_cpp_type(
        cursor_alias_template_target_type(cursor),
        context=context,
        source_cursor=target_cursor if target_cursor is not None else cursor,
    )

    return CppAliasTemplateDeclarationCppFacet(
        original_name=cursor.spelling or None,
        target=body_type,
        location=extract_location_info(cursor),
        doc=documentation,
        availability=cursor_availability(cursor),
        visibility=cursor_visibility(cursor),
        kind="using",
        template_parameters=extract_template_parameters(cursor, context=context),
    )


# ==================================================================================================
#     Source Locations And Relationships
# ==================================================================================================


def extract_location_info(cursor: Any) -> CppLocationInfo:
    """Extract one clang cursor location into the semantic provenance container."""

    location = cursor_source_location(cursor)
    if location is None:
        return CppLocationInfo()
    is_definition = cursor_is_definition(cursor)
    return CppLocationInfo(
        primary=location,
        declarations=[location],
        definition=location if is_definition else None,
    )


def extract_class_bases(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> list[CppClassBase]:
    """Extract direct base-class relationships declared on one class cursor."""

    bases: list[CppClassBase] = []
    for child_cursor in cursor.get_children():
        if not is_base_specifier_cursor(child_cursor):
            continue

        base_type = _extract_surface_cpp_type(
            getattr(child_cursor, "type", None),
            context=context,
            source_cursor=child_cursor,
        )
        if base_type is None:
            continue

        bases.append(
            CppClassBase(
                type=base_type,
                visibility=cursor_visibility(child_cursor),
                is_virtual=cursor_bool_method(child_cursor, "is_virtual_base"),
            )
        )

    return bases


def _build_operator_metadata(
    cursor: Any,
    return_type: Any,
) -> Any:
    """Extract structured operator metadata for one function-like cursor."""

    operator = cursor_operator(cursor)
    if operator is None:
        return None

    if operator.kind == "conversion" and operator.conversion_type is None and return_type is not None:
        operator.conversion_type = deepcopy(return_type)
    return operator


def _extract_surface_cpp_type(
    clang_type: Any,
    *,
    context: BuildContext | None,
    source_cursor: Any,
) -> Any:
    """Handle one declaration-surface type in the order this parser expects.

    Surface types are the places where we want both raw observation hints and
    the structured semantic `CppType`. This helper keeps that ordering explicit:
    first record any template spellings visible at the source surface, then
    build the actual semantic type tree from the same clang type.
    """

    record_template_observation_hints_in_type(
        clang_type,
        context=context,
        source_cursor=source_cursor,
    )
    return build_cpp_type(
        clang_type,
        context=context,
        source_cursor=source_cursor,
    )
