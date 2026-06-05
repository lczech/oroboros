from __future__ import annotations

"""Extract semantic template declaration data from libclang cursors.

This module handles template declaration parameters and default arguments declared on
templates, for example `template <class T, int N = 4, template <class> class W = Box>`.
"""

from typing import TYPE_CHECKING, Any

from clang.cindex import CursorKind

from ..model import (
    CppNonTypeTemplateArgument,
    CppNonTypeTemplateParameter,
    CppTemplateTemplateArgument,
    CppTemplateParameter,
    CppTemplateTemplateParameter,
    CppTypeTemplateArgument,
    CppTypeTemplateParameter,
)
from .cursor_data import cursor_token_spellings, normalize_token_spellings
from .template_type_recovery import build_cpp_type_from_spelling
from .types import build_cpp_type

if TYPE_CHECKING:
    from .build_model import BuildContext


# ==================================================================================================
#     Template Parameter Extraction
# ==================================================================================================


def extract_template_parameters(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> list[CppTemplateParameter]:
    """Collect the direct parameter slots declared on one template cursor.

    This is the template-declaration side of the parser, used when building the
    generic signature for class, function, method, and alias templates. It
    walks only the declared parameter list here; concrete template uses are
    handled later by template type recovery and observation recording.
    """

    parameters: list[CppTemplateParameter] = []
    for child_cursor in cursor.get_children():
        parameter = extract_template_parameter(child_cursor, context=context)
        if parameter is not None:
            parameters.append(parameter)
    return parameters


def extract_template_parameter(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> CppTemplateParameter | None:
    """Convert one libclang template-parameter cursor into one semantic slot.

    This helper classifies the three declaration kinds separately: type,
    non-type, and template-template parameters. It is called only while
    materializing template declarations, so any default-argument recovery here
    should respect the declared parameter kind instead of guessing from use-site text.
    """

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
            default=_build_non_type_template_parameter_default_argument(
                cursor,
                context=context,
            ),
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
            parameters=extract_template_parameters(cursor, context=context),
            is_parameter_pack=is_parameter_pack,
        )

    return None


# ==================================================================================================
#     Parsing Helpers
# ==================================================================================================


def _build_type_template_parameter_default_argument(
    cursor: Any,
) -> CppTypeTemplateArgument | None:
    """Recover one default type argument declared on a type template parameter.

    This path has stronger context than general template-argument recovery: the
    parameter declaration already tells us the default must be a type. We still
    reuse spelling-based type recovery for the inner structure, but we wrap the
    result directly as a semantic type argument instead of allowing an opaque slot.
    """

    default_spelling = _template_parameter_default_spelling(cursor, trim_trailing_closers=True)
    if default_spelling is None:
        return None

    return CppTypeTemplateArgument(
        type=build_cpp_type_from_spelling(default_spelling),
    )


def _build_non_type_template_parameter_default_argument(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> CppNonTypeTemplateArgument | None:
    """Recover one default value argument declared on a non-type template parameter.

    Here the declaration already guarantees that the default is a value rather
    than a type. We therefore keep the source spelling as the value expression
    and separately ask `build_cpp_type()` for the declared slot type when
    libclang exposes it.
    """

    default_spelling = _template_parameter_default_spelling(cursor)
    if default_spelling is None:
        return None

    return CppNonTypeTemplateArgument(
        value=default_spelling,
        type=build_cpp_type(
            getattr(cursor, "type", None),
            context=context,
        ),
    )


def _build_template_template_parameter_default_argument(
    cursor: Any,
    *,
    context: BuildContext | None = None,
) -> CppTemplateTemplateArgument | None:
    """Recover one default template-template argument from its parameter cursor.

    Unlike ordinary type defaults, this path is driven by the referenced
    template family cursor when libclang exposes one. That lets the parser keep
    the default family name plus its inner parameter signature without doing
    broader semantic reconstruction from plain spelling alone.
    """

    default_spelling = _template_parameter_default_spelling(cursor, trim_trailing_closers=True)
    if default_spelling is None:
        return None

    default_cursor = _template_template_default_referenced_cursor(cursor)
    parameters = extract_template_parameters(default_cursor, context=context) if default_cursor is not None else []
    return CppTemplateTemplateArgument(
        name=default_spelling,
        parameters=parameters,
    )


def _template_parameter_default_spelling(
    cursor: Any,
    *,
    trim_trailing_closers: bool = False,
) -> str | None:
    """Render the source spelling for one declared template default argument.

    The parameter builders above all share this helper because libclang does
    not hand us one clean “default argument” node here. Instead we slice and
    normalize the relevant token range, then let the parameter-kind-specific
    builders decide how that spelling should be interpreted.
    """

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
