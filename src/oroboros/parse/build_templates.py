from __future__ import annotations

"""Build semantic template parameter values from libclang cursors."""

from typing import TYPE_CHECKING, Any

from clang.cindex import CursorKind

from ..model import (
    CppNonTypeTemplateParameter,
    CppTemplateParameter,
    CppTemplateTemplateParameter,
    CppTypeTemplateParameter,
)
from .cursor_data import cursor_token_spellings
from .types import build_cpp_type

if TYPE_CHECKING:
    from .build_model import BuildContext


# ==================================================================================================
#     Template Parameter Builders
# ==================================================================================================


def build_template_parameters(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> list[CppTemplateParameter]:
    """Collect direct template parameter declarations from one template cursor."""

    parameters: list[CppTemplateParameter] = []
    for child_cursor in cursor.get_children():
        parameter = build_template_parameter(child_cursor, context=context)
        if parameter is not None:
            parameters.append(parameter)
    return parameters


def build_template_parameter(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> CppTemplateParameter | None:
    """Convert one libclang template-parameter cursor into the semantic model."""

    token_spellings = cursor_token_spellings(cursor)
    is_parameter_pack = "..." in token_spellings

    if getattr(cursor, "kind", None) == CursorKind.TEMPLATE_TYPE_PARAMETER:
        keyword = "class" if "class" in token_spellings else "typename"
        return CppTypeTemplateParameter(
            name=cursor.spelling,
            keyword=keyword,
            is_parameter_pack=is_parameter_pack,
        )

    if getattr(cursor, "kind", None) == CursorKind.TEMPLATE_NON_TYPE_PARAMETER:
        return CppNonTypeTemplateParameter(
            name=cursor.spelling,
            type=build_cpp_type(
                getattr(cursor, "type", None),
                context=context,
            ),
            is_parameter_pack=is_parameter_pack,
        )

    if getattr(cursor, "kind", None) == CursorKind.TEMPLATE_TEMPLATE_PARAMETER:
        return CppTemplateTemplateParameter(
            name=cursor.spelling,
            parameters=build_template_parameters(cursor, context=context),
            is_parameter_pack=is_parameter_pack,
        )

    return None
