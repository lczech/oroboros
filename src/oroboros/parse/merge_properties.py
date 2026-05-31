from __future__ import annotations

"""Low-level merge helpers for parsed declaration properties."""

from copy import deepcopy
from fnmatch import fnmatch
from pprint import pformat
from typing import TYPE_CHECKING, Any, Callable

from ..diagnostics import Diagnostic
from ..diagnostics.report import DiagnosticSeverity
from ..model import CppElement, CppLocationInfo, SourceLocation, format_element_scope
from .comment_structure import comment_preference_key, comments_are_equivalent, parse_cpp_doc
from .cursor_data import cursor_kind_name, cursor_source_location

if TYPE_CHECKING:
    from .build_model import BuildContext


# ==================================================================================================
#     Common Field Merges
# ==================================================================================================


def merge_common_cpp_fields(
    element: CppElement,
    candidate_cpp: Any,
    context: BuildContext,
    cursor: Any,
    *,
    merge_documentation: bool = True,
    merge_original_name: bool = True,
) -> None:
    """Merge common parsed fields from one repeated declaration into an element."""

    if merge_original_name:
        merge_cpp_scalar(element, "original_name", getattr(candidate_cpp, "original_name", None), context, cursor)
    merge_location_info(element.cpp.location, candidate_cpp.location)
    if hasattr(element.cpp, "availability"):
        merge_cpp_scalar(
            element,
            "availability",
            getattr(candidate_cpp, "availability", None),
            context,
            cursor,
        )
    if merge_documentation and hasattr(element.cpp, "doc"):
        merge_cpp_documentation(element, candidate_cpp, context, cursor)


def merge_cpp_documentation(
    element: CppElement,
    candidate_cpp: Any,
    context: BuildContext,
    cursor: Any,
) -> None:
    """Merge attached-comment provenance and parsed documentation conservatively."""

    candidate_doc = getattr(candidate_cpp, "doc", None)
    if candidate_doc is None:
        return

    current_doc = getattr(element.cpp, "doc", None)
    if current_doc is None:
        element.cpp.doc = deepcopy(candidate_doc)
        return

    merged_attached_comment = resolve_comment_conflict(
        existing_comment=current_doc.attached_comment,
        new_comment=candidate_doc.attached_comment,
        context=context,
        cursor=cursor,
        locations=_element_diagnostic_locations(element, cursor=cursor),
        entity=format_element_scope(element),
    )
    current_doc.attached_comment = merged_attached_comment
    current_doc.parsed = parse_cpp_doc(merged_attached_comment)

    if current_doc.clang_raw_comment is None and candidate_doc.clang_raw_comment is not None:
        current_doc.clang_raw_comment = candidate_doc.clang_raw_comment


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
        f"Conflicting parsed {field_name!r} for {format_element_scope(element)}; "
        "keeping the first value.",
        code="parse.merge.conflicting_scalar",
        locations=_element_diagnostic_locations(element, cursor=cursor),
        element_path=format_element_scope(element),
        detail=_build_value_conflict_detail(
            current_value,
            new_value,
            existing_label=f"existing parsed {field_name}",
            new_label=f"new parsed {field_name}",
            selected_summary="selected: existing",
        ),
    )


def merge_cpp_bool_enrichment(
    element: CppElement,
    field_name: str,
    new_value: bool,
) -> None:
    """Merge one boolean parsed field where `True` enriches earlier `False` values."""

    if not new_value:
        return

    current_value = bool(getattr(element.cpp, field_name, False))
    if current_value:
        return

    setattr(element.cpp, field_name, True)


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
        f"Conflicting parsed 'bases' for {format_element_scope(element)}; "
        "keeping the first value.",
        code="parse.merge.conflicting_bases",
        locations=_element_diagnostic_locations(element, cursor=cursor),
        element_path=format_element_scope(element),
        detail=_build_value_conflict_detail(
            element.cpp.bases,
            new_bases,
            existing_label="existing parsed bases",
            new_label="new parsed bases",
            selected_summary="selected: existing",
        ),
    )


def merge_template_parameters(
    existing_parameters: list[Any],
    new_parameters: list[Any],
    context: BuildContext,
    cursor: Any,
    *,
    entity: str | None = None,
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
        f"Conflicting parsed 'template_parameters' for {entity or describe_cursor_entity(cursor)}; "
        "keeping the first value.",
        code="parse.merge.conflicting_template_parameters",
        cursor=cursor,
        element_path=entity,
        detail=_build_value_conflict_detail(
            existing_parameters,
            new_parameters,
            existing_label="existing parsed template_parameters",
            new_label="new parsed template_parameters",
            selected_summary="selected: existing",
        ),
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


# ==================================================================================================
#     Diagnostics And Helpers
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
    locations: list[SourceLocation] | None = None,
    entity: str | None = None,
) -> str | None:
    """Resolve one repeated-declaration comment conflict using parser policy."""

    if new_comment is None:
        return existing_comment
    if existing_comment is None:
        return new_comment
    if comments_are_equivalent(existing_comment, new_comment):
        return existing_comment

    resolved_comment = _resolve_comment_conflict_value(existing_comment, new_comment, context=context)
    clear_winner = comment_preference_key(existing_comment)[:2] != comment_preference_key(new_comment)[:2]
    record_semantic_warning(
        context,
        f"Conflicting parsed comments for {entity or describe_cursor_entity(cursor)}; resolved via "
        f"`comment_conflict_policy={context.config.comment_conflict_policy}`.",
        code="parse.merge.preferred_comments" if clear_winner else "parse.merge.conflicting_comments",
        severity="note" if clear_winner else "warning",
        locations=locations,
        element_path=entity,
        detail=_build_comment_conflict_detail(
            existing_comment,
            new_comment,
            selected_summary=_describe_comment_conflict_selection(existing_comment, new_comment, resolved_comment),
        ),
    )
    return resolved_comment


def append_distinct_comments(existing_comment: str, new_comment: str) -> str:
    """Join two distinct comment blocks while avoiding exact duplication."""

    if comments_are_equivalent(existing_comment, new_comment) or new_comment in existing_comment:
        return existing_comment
    if existing_comment in new_comment:
        return new_comment
    return f"{existing_comment}\n\n{new_comment}"


def record_semantic_warning(
    context: BuildContext,
    warning: str,
    *,
    code: str = "parse.warning",
    severity: DiagnosticSeverity = "warning",
    cursor: Any | None = None,
    locations: list[Any] | None = None,
    element_path: str | None = None,
    detail: str | None = None,
) -> None:
    """Append one parser-level semantic diagnostic if it is not suppressed."""

    if any(fnmatch(code, pattern) for pattern in context.config.suppress_diagnostics):
        return

    diagnostic_locations = list(locations or [])
    if not diagnostic_locations and cursor is not None:
        location = cursor_source_location(cursor)
        if location is not None:
            diagnostic_locations.append(location)

    context.report.add(
        Diagnostic(
            severity=severity,
            stage="parse",
            code=code,
            message=warning,
            detail=detail,
            locations=diagnostic_locations,
            element_path=element_path,
        )
    )


def warn_unexpected_repeated_declaration(
    context: BuildContext,
    cursor: Any,
    declaration_kind: str,
    existing: CppElement | None = None,
) -> None:
    """Warn when a non-redeclarable declaration kind repeats by semantic identity."""

    locations = (
        _element_diagnostic_locations(existing, cursor=cursor)
        if existing is not None
        else None
    )
    record_semantic_warning(
        context,
        f"Encountered repeated {declaration_kind} declaration for {describe_cursor_entity(cursor)}; "
        "keeping the first declaration.",
        code=f"parse.repeated_{declaration_kind}_declaration",
        cursor=cursor if locations is None else None,
        locations=locations,
        element_path=format_element_scope(existing) if existing is not None else None,
    )


def describe_cursor_entity(cursor: Any) -> str:
    """Render one short human-readable cursor description for warnings."""

    spelling = getattr(cursor, "spelling", None) or "<anonymous>"
    return f"{cursor_kind_name(cursor)} {spelling!r}"


def _element_diagnostic_locations(
    element: CppElement,
    *,
    cursor: Any | None = None,
) -> list[SourceLocation]:
    """Return one unique provenance list for diagnostics about one semantic element."""

    location_info = getattr(getattr(element, "cpp", None), "location", None)
    return _location_info_diagnostic_locations(location_info, cursor=cursor)


def _location_info_diagnostic_locations(
    location_info: Any,
    *,
    cursor: Any | None = None,
) -> list[SourceLocation]:
    """Return unique declaration/definition locations plus an optional cursor site."""

    locations: list[SourceLocation] = []
    if isinstance(location_info, CppLocationInfo):
        if location_info.primary is not None:
            locations.append(location_info.primary)
        if location_info.definition is not None:
            locations.append(location_info.definition)
        locations.extend(location_info.declarations)

    cursor_location = cursor_source_location(cursor) if cursor is not None else None
    if cursor_location is not None:
        locations.append(cursor_location)
    return _unique_source_locations(locations)


def _unique_source_locations(locations: list[SourceLocation]) -> list[SourceLocation]:
    """Preserve source order while removing duplicate locations."""

    unique_locations: list[SourceLocation] = []
    seen_keys: set[tuple[str, int, int]] = set()
    for location in locations:
        key = (str(location.file), location.line, location.column)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_locations.append(location)
    return unique_locations


def _resolve_comment_conflict_value(
    existing_comment: str,
    new_comment: str,
    *,
    context: BuildContext,
) -> str:
    """Return the resolved comment text for one repeated-declaration conflict."""

    if context.config.comment_conflict_policy == "first":
        return existing_comment
    if context.config.comment_conflict_policy == "last":
        return new_comment
    if context.config.comment_conflict_policy == "append":
        return append_distinct_comments(existing_comment, new_comment)
    if context.config.comment_conflict_policy == "structured":
        if comment_preference_key(new_comment) > comment_preference_key(existing_comment):
            return new_comment
        return existing_comment
    if len(new_comment) > len(existing_comment):
        return new_comment
    return existing_comment


def _build_comment_conflict_detail(
    existing_comment: str,
    new_comment: str,
    *,
    selected_summary: str,
) -> str:
    """Render one structured detail block for repeated-declaration comment conflicts."""

    return "\n".join([
        "existing parsed comment:",
        existing_comment,
        "",
        "new parsed comment:",
        new_comment,
        "",
        selected_summary,
    ])


def _build_value_conflict_detail(
    existing_value: Any,
    new_value: Any,
    *,
    existing_label: str,
    new_label: str,
    selected_summary: str | None = None,
) -> str:
    """Render one structured detail block for two conflicting parsed values."""

    lines = [
        f"{existing_label}:",
        _render_detail_value(existing_value),
        "",
        f"{new_label}:",
        _render_detail_value(new_value),
    ]
    if selected_summary is not None:
        lines.extend([
            "",
            selected_summary,
        ])
    return "\n".join(lines)


def _describe_comment_conflict_selection(existing_comment: str, new_comment: str, resolved_comment: str) -> str:
    """Return one concise summary of which comment outcome was selected."""

    if resolved_comment == existing_comment:
        return "selected: existing"
    if resolved_comment == new_comment:
        return "selected: new"
    return "selected: merged"


def _render_detail_value(value: Any) -> str:
    """Render one parsed value for stable multi-line diagnostic detail output."""

    return pformat(value, sort_dicts=False, width=100)
