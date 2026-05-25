from __future__ import annotations

"""Build parsed `.cpp` facet data from libclang cursors."""

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from ..model import CppClassBase, CppLocationInfo
from .build_templates import build_template_parameters
from .comment_recovery import resolve_cursor_comment
from .cursor_data import (
    cursor_alias_kind,
    cursor_alias_template_target_cursor,
    cursor_alias_template_target_type,
    cursor_alias_target_type,
    cursor_bool_method,
    cursor_callable_is_defaulted,
    cursor_callable_is_deleted,
    cursor_class_kind,
    cursor_enum_underlying_type,
    cursor_enum_value_spelling,
    cursor_has_explicit_specifier,
    cursor_is_definition,
    cursor_is_noexcept,
    cursor_is_scoped_enum,
    cursor_linkage,
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
from .types import build_cpp_type

if TYPE_CHECKING:
    from .build_model import BuildContext


# ==================================================================================================
#     Facet Builders
# ==================================================================================================


def _comment_and_doc(cursor: Any, *, context: BuildContext | None = None) -> tuple[str | None, Any]:
    """Return one raw attached comment plus its normalized structured form."""

    resolution = resolve_cursor_comment(cursor, context)
    return resolution.selected_comment, resolution.selected_doc


def build_parameter_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed parameter facet from one clang cursor."""

    from ..model import CppParameterCppFacet

    return CppParameterCppFacet(
        original_name=cursor.spelling or None,
        type=build_cpp_type(
            getattr(cursor, "type", None),
            context=context,
            source_cursor=cursor,
        ),
        default_value=cursor_parameter_default_value(cursor),
        location=build_location_info(cursor),
    )


# ------------------------------------------------------------------------------
#     Namespace
# ------------------------------------------------------------------------------


def build_namespace_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed namespace facet from one clang cursor."""

    from ..model import CppNamespaceCppFacet
    raw_comment, doc = _comment_and_doc(cursor, context=context)

    return CppNamespaceCppFacet(
        original_name=cursor.spelling or None,
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
    )


# ------------------------------------------------------------------------------
#     Class
# ------------------------------------------------------------------------------


def build_class_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed class/struct facet from one clang cursor."""

    from ..model import CppClassCppFacet
    raw_comment, doc = _comment_and_doc(cursor, context=context)

    return CppClassCppFacet(
        original_name=cursor.spelling or None,
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
        kind=cursor_class_kind(cursor),
        visibility=cursor_visibility(cursor),
        bases=build_class_bases(cursor, context=context),
    )


def build_class_template_declaration_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed generic class-template declaration facet."""

    from ..model import CppClassTemplateDeclarationCppFacet
    raw_comment, doc = _comment_and_doc(cursor, context=context)

    return CppClassTemplateDeclarationCppFacet(
        original_name=cursor.spelling or None,
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
        kind=cursor_class_kind(cursor),
        visibility=cursor_visibility(cursor),
        bases=build_class_bases(cursor, context=context),
        template_parameters=build_template_parameters(cursor, context=context),
    )


def build_method_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed method facet from one clang cursor."""

    from ..model import CppMethodCppFacet
    raw_comment, doc = _comment_and_doc(cursor, context=context)
    return_type = build_cpp_type(
        getattr(cursor, "result_type", None),
        context=context,
        source_cursor=cursor,
    )

    return CppMethodCppFacet(
        original_name=cursor.spelling or None,
        operator=_build_operator_metadata(cursor, return_type),
        return_type=return_type,
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
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


def build_constructor_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed constructor facet from one clang cursor."""

    from ..model import CppConstructorCppFacet
    raw_comment, doc = _comment_and_doc(cursor, context=context)

    return CppConstructorCppFacet(
        original_name=cursor.spelling or None,
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
        is_explicit=cursor_has_explicit_specifier(cursor),
        is_noexcept=cursor_is_noexcept(cursor),
        is_deleted=cursor_callable_is_deleted(cursor, context=context),
        is_defaulted=cursor_callable_is_defaulted(cursor, context=context),
        visibility=cursor_visibility(cursor),
    )


def build_destructor_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed destructor facet from one clang cursor."""

    from ..model import CppDestructorCppFacet
    raw_comment, doc = _comment_and_doc(cursor, context=context)

    return CppDestructorCppFacet(
        original_name=cursor.spelling or None,
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
        is_virtual=cursor_bool_method(cursor, "is_virtual_method"),
        is_pure_virtual=cursor_bool_method(cursor, "is_pure_virtual_method"),
        is_deleted=cursor_callable_is_deleted(cursor, context=context),
        is_defaulted=cursor_callable_is_defaulted(cursor, context=context),
        visibility=cursor_visibility(cursor),
    )


def build_variable_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
    kind: str = "variable",
) -> Any:
    """Build one parsed variable facet from one clang cursor."""

    from ..model import CppVariableCppFacet
    raw_comment, doc = _comment_and_doc(cursor, context=context)

    return CppVariableCppFacet(
        original_name=cursor.spelling or None,
        type=build_cpp_type(
            getattr(cursor, "type", None),
            context=context,
            source_cursor=cursor,
        ),
        is_const=cursor_type_is_const_qualified(cursor),
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
        visibility=cursor_visibility(cursor),
        kind=kind,
        storage_class=cursor_storage_class(cursor),
        linkage=cursor_linkage(cursor),
        tls_kind=cursor_tls_kind(cursor),
    )


# ------------------------------------------------------------------------------
#     Function
# ------------------------------------------------------------------------------


def build_function_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed free-function facet from one clang cursor."""

    from ..model import CppFunctionCppFacet
    raw_comment, doc = _comment_and_doc(cursor, context=context)
    return_type = build_cpp_type(
        getattr(cursor, "result_type", None),
        context=context,
        source_cursor=cursor,
    )

    return CppFunctionCppFacet(
        original_name=cursor.spelling or None,
        operator=_build_operator_metadata(cursor, return_type),
        return_type=return_type,
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
        is_noexcept=cursor_is_noexcept(cursor),
        is_deleted=cursor_callable_is_deleted(cursor, context=context),
    )


def build_function_template_declaration_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed generic function-template declaration facet."""

    from ..model import CppFunctionTemplateDeclarationCppFacet
    raw_comment, doc = _comment_and_doc(cursor, context=context)
    return_type = build_cpp_type(
        getattr(cursor, "result_type", None),
        context=context,
        source_cursor=cursor,
    )

    return CppFunctionTemplateDeclarationCppFacet(
        original_name=cursor.spelling or None,
        operator=_build_operator_metadata(cursor, return_type),
        return_type=return_type,
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
        is_noexcept=cursor_is_noexcept(cursor),
        is_deleted=cursor_callable_is_deleted(cursor, context=context),
        template_parameters=build_template_parameters(cursor, context=context),
    )


def build_method_template_declaration_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed generic method-template declaration facet."""

    from ..model import CppMethodTemplateDeclarationCppFacet
    raw_comment, doc = _comment_and_doc(cursor, context=context)
    return_type = build_cpp_type(
        getattr(cursor, "result_type", None),
        context=context,
        source_cursor=cursor,
    )

    return CppMethodTemplateDeclarationCppFacet(
        original_name=cursor.spelling or None,
        operator=_build_operator_metadata(cursor, return_type),
        return_type=return_type,
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
        is_noexcept=cursor_is_noexcept(cursor),
        is_deleted=cursor_callable_is_deleted(cursor, context=context),
        is_const=cursor_bool_method(cursor, "is_const_method"),
        ref_qualifier=cursor_ref_qualifier(cursor),
        is_static=cursor_bool_method(cursor, "is_static_method"),
        is_virtual=cursor_bool_method(cursor, "is_virtual_method"),
        is_pure_virtual=cursor_bool_method(cursor, "is_pure_virtual_method"),
        template_parameters=build_template_parameters(cursor, context=context),
        visibility=cursor_visibility(cursor),
    )


# ------------------------------------------------------------------------------
#     Enum
# ------------------------------------------------------------------------------


def build_enum_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed enum facet from one clang cursor."""

    from ..model import CppEnumCppFacet
    raw_comment, doc = _comment_and_doc(cursor, context=context)

    return CppEnumCppFacet(
        original_name=cursor.spelling or None,
        underlying_type=build_cpp_type(
            cursor_enum_underlying_type(cursor),
            context=context,
            source_cursor=cursor,
        ),
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
        is_scoped=cursor_is_scoped_enum(cursor),
        visibility=cursor_visibility(cursor),
    )


def build_enumerator_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed enumerator facet from one clang cursor."""

    from ..model import CppEnumeratorCppFacet
    raw_comment, doc = _comment_and_doc(cursor, context=context)

    return CppEnumeratorCppFacet(
        original_name=cursor.spelling or None,
        value_spelling=cursor_enum_value_spelling(cursor),
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
    )


# ------------------------------------------------------------------------------
#     Alias
# ------------------------------------------------------------------------------


def build_alias_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed alias facet from one clang cursor."""

    from ..model import CppAliasCppFacet
    raw_comment, doc = _comment_and_doc(cursor, context=context)

    return CppAliasCppFacet(
        original_name=cursor.spelling or None,
        target=build_cpp_type(
            cursor_alias_target_type(cursor),
            context=context,
            source_cursor=cursor,
        ),
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
        visibility=cursor_visibility(cursor),
        kind=cursor_alias_kind(cursor),
    )


def build_alias_template_declaration_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed generic alias-template declaration facet."""

    from ..model import CppAliasTemplateDeclarationCppFacet

    raw_comment, doc = _comment_and_doc(cursor, context=context)
    target_cursor = cursor_alias_template_target_cursor(cursor)

    return CppAliasTemplateDeclarationCppFacet(
        original_name=cursor.spelling or None,
        target=build_cpp_type(
            cursor_alias_template_target_type(cursor),
            context=context,
            source_cursor=target_cursor if target_cursor is not None else cursor,
        ),
        location=build_location_info(cursor),
        comment=raw_comment,
        doc=doc,
        visibility=cursor_visibility(cursor),
        kind="using",
        template_parameters=build_template_parameters(cursor, context=context),
    )


# ==================================================================================================
#     Source Locations And Relationships
# ==================================================================================================


def build_location_info(cursor: Any) -> CppLocationInfo:
    """Convert one clang cursor location into the semantic provenance container."""

    location = cursor_source_location(cursor)
    if location is None:
        return CppLocationInfo()
    is_definition = cursor_is_definition(cursor)
    return CppLocationInfo(
        primary=location,
        declarations=[location],
        definition=location if is_definition else None,
    )


def build_class_bases(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> list[CppClassBase]:
    """Collect direct base-class relationships declared on one class cursor."""

    bases: list[CppClassBase] = []
    for child_cursor in cursor.get_children():
        if not is_base_specifier_cursor(child_cursor):
            continue

        base_type = build_cpp_type(
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
    """Build structured operator metadata for one function-like cursor."""

    operator = cursor_operator(cursor)
    if operator is None:
        return None

    if operator.kind == "conversion" and operator.conversion_type is None and return_type is not None:
        operator.conversion_type = deepcopy(return_type)
    return operator
