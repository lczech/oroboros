from __future__ import annotations

"""Build parsed `.cpp` facet data from libclang cursors."""

from typing import TYPE_CHECKING, Any

from ..model import CppClassBase, CppLocationInfo
from .build_templates import build_template_parameters
from .cursor_data import (
    cursor_alias_kind,
    cursor_alias_target_type,
    cursor_bool_method,
    cursor_class_kind,
    cursor_enum_underlying_type,
    cursor_enum_value_spelling,
    cursor_is_definition,
    cursor_is_noexcept,
    cursor_is_scoped_enum,
    cursor_raw_comment,
    cursor_source_location,
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


def build_namespace_cpp_facet(
    cursor: Any,
) -> Any:
    """Build one parsed namespace facet from one clang cursor."""

    from ..model import CppNamespaceCppFacet

    return CppNamespaceCppFacet(
        original_name=cursor.spelling or None,
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
    )


def build_alias_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed alias facet from one clang cursor."""

    from ..model import CppAliasCppFacet

    return CppAliasCppFacet(
        original_name=cursor.spelling or None,
        target=build_cpp_type(
            cursor_alias_target_type(cursor),
            context=context,
            source_cursor=cursor,
        ),
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        visibility=cursor_visibility(cursor),
        kind=cursor_alias_kind(cursor),
    )


def build_class_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed class/struct facet from one clang cursor."""

    from ..model import CppClassCppFacet

    return CppClassCppFacet(
        original_name=cursor.spelling or None,
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        kind="struct" if is_struct_cursor(cursor) else "class",
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

    return CppClassTemplateDeclarationCppFacet(
        original_name=cursor.spelling or None,
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        kind=cursor_class_kind(cursor),
        visibility=cursor_visibility(cursor),
        bases=build_class_bases(cursor, context=context),
        template_parameters=build_template_parameters(cursor, context=context),
    )


def build_enum_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed enum facet from one clang cursor."""

    from ..model import CppEnumCppFacet

    return CppEnumCppFacet(
        original_name=cursor.spelling or None,
        underlying_type=build_cpp_type(
            cursor_enum_underlying_type(cursor),
            context=context,
            source_cursor=cursor,
        ),
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        is_scoped=cursor_is_scoped_enum(cursor),
        visibility=cursor_visibility(cursor),
    )


def build_enumerator_cpp_facet(
    cursor: Any,
) -> Any:
    """Build one parsed enumerator facet from one clang cursor."""

    from ..model import CppEnumeratorCppFacet

    return CppEnumeratorCppFacet(
        original_name=cursor.spelling or None,
        value_spelling=cursor_enum_value_spelling(cursor),
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
    )


def build_function_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed free-function facet from one clang cursor."""

    from ..model import CppFunctionCppFacet

    return CppFunctionCppFacet(
        original_name=cursor.spelling or None,
        return_type=build_cpp_type(
            getattr(cursor, "result_type", None),
            context=context,
            source_cursor=cursor,
        ),
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        is_noexcept=cursor_is_noexcept(cursor),
    )


def build_function_template_declaration_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed generic function-template declaration facet."""

    from ..model import CppFunctionTemplateDeclarationCppFacet

    return CppFunctionTemplateDeclarationCppFacet(
        original_name=cursor.spelling or None,
        return_type=build_cpp_type(
            getattr(cursor, "result_type", None),
            context=context,
            source_cursor=cursor,
        ),
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        is_noexcept=cursor_is_noexcept(cursor),
        template_parameters=build_template_parameters(cursor, context=context),
        is_const=cursor_bool_method(cursor, "is_const_method"),
        is_static=cursor_bool_method(cursor, "is_static_method"),
        is_virtual=cursor_bool_method(cursor, "is_virtual_method"),
        is_pure_virtual=cursor_bool_method(cursor, "is_pure_virtual_method"),
    )


def build_method_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed method facet from one clang cursor."""

    from ..model import CppMethodCppFacet

    return CppMethodCppFacet(
        original_name=cursor.spelling or None,
        return_type=build_cpp_type(
            getattr(cursor, "result_type", None),
            context=context,
            source_cursor=cursor,
        ),
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        is_noexcept=cursor_is_noexcept(cursor),
        is_const=cursor_bool_method(cursor, "is_const_method"),
        is_static=cursor_bool_method(cursor, "is_static_method"),
        is_virtual=cursor_bool_method(cursor, "is_virtual_method"),
        is_pure_virtual=cursor_bool_method(cursor, "is_pure_virtual_method"),
        visibility=cursor_visibility(cursor),
    )


def build_constructor_cpp_facet(
    cursor: Any,
) -> Any:
    """Build one parsed constructor facet from one clang cursor."""

    from ..model import CppConstructorCppFacet

    return CppConstructorCppFacet(
        original_name=cursor.spelling or None,
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        is_noexcept=cursor_is_noexcept(cursor),
        visibility=cursor_visibility(cursor),
    )


def build_field_cpp_facet(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> Any:
    """Build one parsed field facet from one clang cursor."""

    from ..model import CppFieldCppFacet

    return CppFieldCppFacet(
        original_name=cursor.spelling or None,
        type=build_cpp_type(
            getattr(cursor, "type", None),
            context=context,
            source_cursor=cursor,
        ),
        location=build_location_info(cursor),
        comment=cursor_raw_comment(cursor),
        is_static=cursor_bool_method(cursor, "is_static_field"),
        visibility=cursor_visibility(cursor),
    )


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
        location=build_location_info(cursor),
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
