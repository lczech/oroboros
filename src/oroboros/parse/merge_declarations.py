from __future__ import annotations

"""Merge and warning helpers for repeated clang declarations."""

from typing import TYPE_CHECKING, Any, Callable, Iterable

from clang.cindex import CursorKind

from ..model import CppElement
from ..model.type import cpp_types_equivalent
from .build_facets import build_parameter_cpp_facet
from .comments import parse_cpp_doc
from .cursor_data import cursor_is_from_active_header, cursor_kind_name, cursor_source_location

if TYPE_CHECKING:
    from .build_model import BuildContext


# ==================================================================================================
#     Merge CPP
# ==================================================================================================


def merge_common_cpp_fields(
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
        merge_cpp_scalar(element, "original_name", getattr(candidate_cpp, "original_name", None), context, cursor)
    merge_location_info(element.cpp.location, candidate_cpp.location)
    if comment_field_name is not None and hasattr(element.cpp, comment_field_name):
        merged_comment = resolve_comment_conflict(
            existing_comment=getattr(element.cpp, comment_field_name),
            new_comment=getattr(candidate_cpp, comment_field_name, None),
            context=context,
            cursor=cursor,
        )
        setattr(element.cpp, comment_field_name, merged_comment)
        if hasattr(element.cpp, "doc"):
            element.cpp.doc = parse_cpp_doc(merged_comment)


def merge_cpp_scalar(
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

    equivalent = values_equivalent or values_equal
    if equivalent(current_value, new_value):
        return

    if not warn_on_conflict:
        return

    record_semantic_warning(
        context,
        f"Conflicting parsed {field_name!r} for {describe_cursor_entity(cursor)} at "
        f"{format_cursor_location(cursor)}; keeping the first value.",
    )


def merge_class_bases(
    element: Any,
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

    record_semantic_warning(
        context,
        f"Conflicting parsed 'bases' for {describe_cursor_entity(cursor)} at "
        f"{format_cursor_location(cursor)}; keeping the first value.",
    )


def merge_template_parameters(
    existing_parameters: list[Any],
    new_parameters: list[Any],
    context: BuildContext,
    cursor: Any,
) -> None:
    """Merge parsed template parameter lists conservatively across redeclarations."""

    if not new_parameters:
        return

    if not existing_parameters:
        existing_parameters.extend(new_parameters)
        return

    if existing_parameters == new_parameters:
        return

    record_semantic_warning(
        context,
        f"Conflicting parsed 'template_parameters' for {describe_cursor_entity(cursor)} at "
        f"{format_cursor_location(cursor)}; keeping the first value.",
    )


def merge_location_info(existing: Any, new: Any) -> None:
    """Merge source provenance from one repeated declaration cursor."""

    if existing.primary is None and new.primary is not None:
        existing.primary = new.primary

    if new.definition is not None:
        existing.definition = new.definition
        existing.primary = new.definition

    for declaration_location in new.declarations:
        if declaration_location not in existing.declarations:
            existing.declarations.append(declaration_location)


def merge_callable_parameter_children(
    callable_element: Any,
    child_cursors: Iterable[Any],
    context: BuildContext,
    *,
    register_element_for_cursor: Any,
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
        candidate_cpp = build_parameter_cpp_facet(parameter_cursor, context=context)
        register_element_for_cursor(parameter_cursor, existing_parameter, context)
        merge_common_cpp_fields(
            existing_parameter,
            candidate_cpp,
            context,
            parameter_cursor,
            comment_field_name=None,
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


# ==================================================================================================
#     Helper Functions
# ==================================================================================================


def values_equal(left: Any, right: Any) -> bool:
    """Return whether two parsed scalar values are equal."""

    return left == right


def resolve_comment_conflict(
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

    record_semantic_warning(
        context,
        f"Conflicting parsed comments for {describe_cursor_entity(cursor)} at "
        f"{format_cursor_location(cursor)}; resolved via "
        f"`comment_conflict_policy={context.config.comment_conflict_policy}`.",
    )

    if context.config.comment_conflict_policy == "first":
        return existing_comment
    if context.config.comment_conflict_policy == "last":
        return new_comment
    if context.config.comment_conflict_policy == "append":
        return append_distinct_comments(existing_comment, new_comment)
    if len(new_comment) > len(existing_comment):
        return new_comment
    return existing_comment


def append_distinct_comments(existing_comment: str, new_comment: str) -> str:
    """Join two distinct comment blocks while avoiding exact duplication."""

    if new_comment in existing_comment:
        return existing_comment
    if existing_comment in new_comment:
        return new_comment
    return f"{existing_comment}\n\n{new_comment}"


def record_semantic_warning(context: BuildContext, warning: str) -> None:
    """Append one parser-level semantic warning if it is not already present."""

    if warning not in context.semantic_warnings:
        context.semantic_warnings.append(warning)


def warn_unexpected_repeated_declaration(
    context: BuildContext,
    cursor: Any,
    declaration_kind: str,
) -> None:
    """Warn when a non-redeclarable declaration kind repeats by semantic identity."""

    record_semantic_warning(
        context,
        f"Encountered repeated {declaration_kind} declaration for {describe_cursor_entity(cursor)} at "
        f"{format_cursor_location(cursor)}; keeping the first declaration.",
    )


def describe_cursor_entity(cursor: Any) -> str:
    """Render one short human-readable cursor description for warnings."""

    spelling = getattr(cursor, "spelling", None) or "<anonymous>"
    return f"{cursor_kind_name(cursor)} {spelling!r}"


def format_cursor_location(cursor: Any) -> str:
    """Render one short source-location string for warnings."""

    location = cursor_source_location(cursor)
    return format_source_location(location)


def format_source_location(location: Any) -> str:
    """Render one source-location object into a stable short string."""

    if location is None:
        return "<unknown location>"
    return f"{location.file}:{location.line}:{location.column}"
