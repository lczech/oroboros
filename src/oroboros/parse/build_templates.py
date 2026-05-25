from __future__ import annotations

"""Build semantic template parameter values from libclang cursors."""

from typing import TYPE_CHECKING, Any

from clang.cindex import CursorKind

from ..model import (
    CppNonTypeTemplateArgument,
    CppNonTypeTemplateParameter,
    CppTemplateParameter,
    CppTemplateTemplateArgument,
    CppTemplateTemplateParameter,
    CppTypeTemplateArgument,
    CppTypeTemplateParameter,
)
from .cursor_data import cursor_token_spellings, normalize_token_spellings
from .types import build_cpp_type, build_template_argument_from_spelling

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
            default=_build_type_template_parameter_default_argument(cursor),
            keyword=keyword,
            is_parameter_pack=is_parameter_pack,
        )

    if getattr(cursor, "kind", None) == CursorKind.TEMPLATE_NON_TYPE_PARAMETER:
        return CppNonTypeTemplateParameter(
            name=cursor.spelling,
            default=_build_non_type_template_parameter_default_argument(cursor),
            type=build_cpp_type(
                getattr(cursor, "type", None),
                context=context,
            ),
            is_parameter_pack=is_parameter_pack,
        )

    if getattr(cursor, "kind", None) == CursorKind.TEMPLATE_TEMPLATE_PARAMETER:
        return CppTemplateTemplateParameter(
            name=cursor.spelling,
            default=_build_template_template_parameter_default_argument(
                cursor,
                context=context,
            ),
            parameters=build_template_parameters(cursor, context=context),
            is_parameter_pack=is_parameter_pack,
        )

    return None


# ==================================================================================================
#     Parsing Helpers
# ==================================================================================================


def _build_type_template_parameter_default_argument(
    cursor: Any,
) -> CppTypeTemplateArgument | None:
    """Return one structured default type argument from a template type-parameter cursor."""

    default_spelling = _template_parameter_default_spelling(cursor, trim_trailing_closers=True)
    if default_spelling is None:
        return None

    default_argument = build_template_argument_from_spelling(default_spelling)
    if isinstance(default_argument, CppTypeTemplateArgument):
        return default_argument
    return CppTypeTemplateArgument()


def _build_non_type_template_parameter_default_argument(
    cursor: Any,
) -> CppNonTypeTemplateArgument | None:
    """Return one structured default value argument from a non-type template-parameter cursor."""

    default_spelling = _template_parameter_default_spelling(cursor)
    if default_spelling is None:
        return None

    return CppNonTypeTemplateArgument(value=default_spelling)


def _build_template_template_parameter_default_argument(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> CppTemplateTemplateArgument | None:
    """Return one structured default template-template argument from a parameter cursor."""

    default_spelling = _template_parameter_default_spelling(cursor, trim_trailing_closers=True)
    if default_spelling is None:
        return None

    default_cursor = _template_template_default_referenced_cursor(cursor)
    parameters = build_template_parameters(default_cursor, context=context) if default_cursor is not None else []
    return CppTemplateTemplateArgument(
        name=default_spelling,
        parameters=parameters,
    )


def _template_parameter_default_spelling(
    cursor: Any,
    *,
    trim_trailing_closers: bool = False,
) -> str | None:
    """Return one normalized default-argument spelling from a template-parameter cursor."""

    default_tokens = _template_parameter_default_tokens(cursor)
    if trim_trailing_closers:
        default_tokens = _trim_excess_template_parameter_closers(default_tokens)
    if not default_tokens:
        return None

    rendered = normalize_token_spellings(default_tokens)
    return rendered or None


def _template_parameter_default_tokens(cursor: Any) -> list[str]:
    """Return the token slice after the outermost default marker on one parameter cursor."""

    token_spellings = cursor_token_spellings(cursor)
    if "=" not in token_spellings:
        return []

    # Template-template parameters may contain inner `=` tokens on nested slots.
    default_index = len(token_spellings) - 1 - token_spellings[::-1].index("=")
    return token_spellings[default_index + 1 :]


def _trim_excess_template_parameter_closers(token_spellings: list[str]) -> list[str]:
    """Trim closing `>` tokens that belong to the enclosing template parameter list."""

    excess_closers = _count_excess_template_parameter_closers(token_spellings)
    if excess_closers <= 0:
        return token_spellings

    trimmed = list(token_spellings)
    while excess_closers > 0 and trimmed:
        last_token = trimmed[-1]
        if not last_token or set(last_token) != {">"}:
            break
        if len(last_token) <= excess_closers:
            excess_closers -= len(last_token)
            trimmed.pop()
            continue
        trimmed[-1] = ">" * (len(last_token) - excess_closers)
        excess_closers = 0

    return trimmed


def _count_excess_template_parameter_closers(token_spellings: list[str]) -> int:
    """Return how many trailing `>` characters exceed nested template openings."""

    opening_count = sum(len(token) for token in token_spellings if token and set(token) == {"<"})
    closing_count = sum(len(token) for token in token_spellings if token and set(token) == {">"})
    return max(0, closing_count - opening_count)


def _template_template_default_referenced_cursor(cursor: Any) -> Any | None:
    """Return the clang cursor referenced by one template-template default argument when known."""

    referenced_cursor = None
    for child_cursor in cursor.get_children():
        if getattr(child_cursor, "kind", None) != CursorKind.TEMPLATE_REF:
            continue
        referenced_cursor = getattr(child_cursor, "referenced", None)
    return referenced_cursor
