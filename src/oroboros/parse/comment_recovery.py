from __future__ import annotations

"""Resolve one selected attached comment per declaration cursor before redeclaration merging.

This module owns comment attachment for parsed declarations. For each clang cursor,
it recovers nearby leading or trailing comment tokens from the source file and
selects one locally attached comment block when available.

Libclang's ``raw_comment`` is preserved only as provenance. It is intentionally
not used as an attachment source because it can become stale or over-attached
across declarations and even across files in one combined translation unit.

The selected attached comment is later parsed into ``CppParsedDoc`` by ``comment_structure``,
and repeated declarations are still merged afterwards by the normal redeclaration
merge layer. In other words, this module chooses the best local comment per cursor,
while later merge policy chooses among comments across declaration sites.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from clang.cindex import TokenKind

from ..model import CppParsedDoc, SourceLocation
from .comment_structure import comment_preference_key, parse_cpp_doc
from .cursor_data import CursorTokenInfo, cursor_raw_comment, cursor_source_location, file_cursor_tokens

if TYPE_CHECKING:
    from .build_model import BuildContext


# ==================================================================================================
#     Recovery Data
# ==================================================================================================


@dataclass(slots=True)
class RecoveredCommentCandidate:
    """Store one recovered attached-comment candidate for a declaration cursor."""

    text: str
    kind: Literal["leading_line_group", "leading_block", "trailing"]
    start_line: int
    end_line: int
    start_offset: int
    end_offset: int


@dataclass(slots=True)
class CursorCommentSearchContext:
    """Store one cursor's file-local token search data for comment recovery."""

    tokens: list[CursorTokenInfo]
    start_line: int
    start_offset: int
    end_line: int
    end_offset: int


@dataclass(slots=True)
class CursorCommentResolution:
    """Store the resolved comment decision for one declaration cursor occurrence."""

    location: SourceLocation | None = None
    clang_raw_comment: str | None = None
    selected_attached_comment: str | None = None
    selected_attached_doc: CppParsedDoc | None = None
    selection_reason: str = "missing"


def resolve_cursor_comment(cursor: Any, context: BuildContext | None) -> CursorCommentResolution:
    """Resolve the best locally attached comment for one cursor."""

    clang_raw_comment = cursor_raw_comment(cursor)
    location = cursor_source_location(cursor)
    resolution = CursorCommentResolution(
        location=location,
        clang_raw_comment=clang_raw_comment,
        selected_attached_comment=None,
        selected_attached_doc=None,
        selection_reason="missing",
    )
    if context is None or context.translation_unit is None:
        return resolution

    recovered_candidates = recover_comment_candidates(cursor, context)
    if recovered_candidates:
        resolution = _select_comment_resolution(recovered_candidates, resolution)
    return resolution


def recover_comment_candidates(cursor: Any, context: BuildContext) -> list[RecoveredCommentCandidate]:
    """Recover attached comment candidates for one cursor from token positions."""

    search_context = _build_cursor_comment_search_context(cursor, context)
    if search_context is None:
        return []

    candidates: list[RecoveredCommentCandidate] = []

    trailing = _recover_trailing_comment(
        search_context.tokens,
        start_line=search_context.start_line,
        end_line=search_context.end_line,
        end_offset=search_context.end_offset,
    )
    if trailing is not None:
        candidates.append(trailing)

    leading = _recover_leading_comment_group(
        search_context.tokens,
        start_line=search_context.start_line,
        start_offset=search_context.start_offset,
    )
    if leading is not None:
        candidates.append(leading)

    # Stacked out-of-line member-template definitions can start at the last
    # `template <...>` prefix line instead of the first one. Recover comments
    # attached ahead of the whole template-prefix block in that common style.
    template_anchor = _template_prefix_block_start_anchor(
        search_context.tokens,
        start_offset=search_context.start_offset,
    )
    if template_anchor is not None and template_anchor[1] != search_context.start_offset:
        leading = _recover_leading_comment_group(
            search_context.tokens,
            start_line=template_anchor[0],
            start_offset=template_anchor[1],
        )
        if leading is not None:
            candidates.append(leading)

    return candidates


# ==================================================================================================
#     Comment Selection
# ==================================================================================================


def _select_comment_resolution(
    recovered_candidates: list[RecoveredCommentCandidate],
    resolution: CursorCommentResolution,
) -> CursorCommentResolution:
    """Select one final attached comment from recovered local candidates."""

    best_candidate = max(
        recovered_candidates,
        key=lambda candidate: (_candidate_attachment_rank(candidate), comment_preference_key(candidate.text)),
    )
    resolution.selected_attached_comment = best_candidate.text
    resolution.selected_attached_doc = parse_cpp_doc(best_candidate.text)
    resolution.selection_reason = f"recovered_{best_candidate.kind}"
    return resolution


def _build_cursor_comment_search_context(
    cursor: Any,
    context: BuildContext,
) -> CursorCommentSearchContext | None:
    """Return one cursor's local token search data for comment recovery."""

    cursor_extent = getattr(cursor, "extent", None)
    cursor_location = getattr(cursor, "location", None)
    file_object = getattr(cursor_location, "file", None)
    file_name = getattr(file_object, "name", None)
    if cursor_extent is None or file_name is None:
        return None

    file_path = Path(file_name).resolve()
    tokens = file_cursor_tokens(file_path, context)
    if not tokens:
        return None

    start = cursor_extent.start
    end = cursor_extent.end
    return CursorCommentSearchContext(
        tokens=tokens,
        start_line=int(getattr(start, "line", 0)),
        start_offset=int(getattr(start, "offset", 0)),
        end_line=int(getattr(end, "line", 0)),
        end_offset=int(getattr(end, "offset", 0)),
    )


def _recover_trailing_comment(
    tokens: list[CursorTokenInfo],
    *,
    start_line: int,
    end_line: int,
    end_offset: int,
) -> RecoveredCommentCandidate | None:
    """Recover one same-line trailing comment token after the declaration extent."""

    # Only treat line-local declaration trailers as docs. Multi-line extents such as
    # namespaces, classes, or function bodies should not attach closing `// namespace ...`
    # comments from the end of the scope.
    if start_line != end_line:
        return None

    for token in tokens:
        if token.start_offset < end_offset:
            continue
        if token.kind != TokenKind.COMMENT:
            if token.start_line > end_line:
                break
            continue
        if token.start_line != end_line:
            break
        return RecoveredCommentCandidate(
            text=token.spelling.strip(),
            kind="trailing",
            start_line=token.start_line,
            end_line=token.end_line,
            start_offset=token.start_offset,
            end_offset=token.end_offset,
        )
    return None


def _recover_leading_comment_group(
    tokens: list[CursorTokenInfo],
    *,
    start_line: int,
    start_offset: int,
) -> RecoveredCommentCandidate | None:
    """Recover one leading comment group immediately preceding the declaration."""

    preceding_index: int | None = None
    for index in range(len(tokens) - 1, -1, -1):
        if tokens[index].end_offset <= start_offset:
            preceding_index = index
            break

    if preceding_index is None:
        return None

    token = tokens[preceding_index]
    if token.kind != TokenKind.COMMENT or _comment_has_code_before_same_line(tokens, preceding_index):
        return None

    if token.spelling.lstrip().startswith("//"):
        if token.end_line != start_line - 1:
            return None
        group, _ = _collect_contiguous_line_comment_group(tokens, preceding_index)

        return RecoveredCommentCandidate(
            text="\n".join(token.spelling.strip() for token in group),
            kind="leading_line_group",
            start_line=group[0].start_line,
            end_line=group[-1].end_line,
            start_offset=group[0].start_offset,
            end_offset=group[-1].end_offset,
        )

    if token.end_line < start_line - 1:
        return None

    return RecoveredCommentCandidate(
        text=token.spelling.strip(),
        kind="leading_block",
        start_line=token.start_line,
        end_line=token.end_line,
        start_offset=token.start_offset,
        end_offset=token.end_offset,
    )


def _template_prefix_block_start_anchor(
    tokens: list[CursorTokenInfo],
    *,
    start_offset: int,
) -> tuple[int, int] | None:
    """Return the first token of one contiguous leading template-prefix block."""

    start_index = next(
        (index for index, token in enumerate(tokens) if token.start_offset == start_offset),
        None,
    )
    if start_index is None or tokens[start_index].spelling != "template":
        return None

    earliest_index = start_index
    previous_index = start_index - 1

    while previous_index >= 0 and tokens[previous_index].spelling == ">":
        depth = 0
        match_index: int | None = None
        for token_index in range(previous_index, -1, -1):
            spelling = tokens[token_index].spelling
            if spelling == ">":
                depth += 1
            elif spelling == "<":
                depth -= 1
                if depth == 0:
                    match_index = token_index
                    break

        if match_index is None or match_index == 0 or tokens[match_index - 1].spelling != "template":
            break

        earliest_index = match_index - 1
        previous_index = earliest_index - 1

    anchor = tokens[earliest_index]
    return (anchor.start_line, anchor.start_offset)


def _collect_contiguous_line_comment_group(
    tokens: list[CursorTokenInfo],
    end_index: int,
) -> tuple[list[CursorTokenInfo], int]:
    """Collect one contiguous preceding `//` comment group ending at one token index."""

    group: list[CursorTokenInfo] = [tokens[end_index]]
    group_start_index = end_index
    candidate_index = end_index - 1
    while candidate_index >= 0:
        candidate = tokens[candidate_index]
        if candidate.kind != TokenKind.COMMENT:
            break
        if not candidate.spelling.lstrip().startswith("//"):
            break
        if _comment_has_code_before_same_line(tokens, candidate_index):
            break
        if candidate.end_line + 1 != group[0].start_line:
            break
        group.insert(0, candidate)
        group_start_index = candidate_index
        candidate_index -= 1
    return group, group_start_index


def _comment_has_code_before_same_line(tokens: list[CursorTokenInfo], index: int) -> bool:
    """Return whether one comment token is trailing after code on the same line."""

    comment_line = tokens[index].start_line
    for prior_index in range(index - 1, -1, -1):
        prior = tokens[prior_index]
        if prior.end_line < comment_line:
            return False
        return True
    return False


def _candidate_attachment_rank(candidate: RecoveredCommentCandidate) -> tuple[int, int]:
    """Return one sortable attachment-strength key for recovered candidates."""

    if candidate.kind == "trailing":
        return (3, candidate.end_line - candidate.start_line + 1)
    if candidate.kind == "leading_block":
        return (2, candidate.end_line - candidate.start_line + 1)
    return (1, candidate.end_line - candidate.start_line + 1)
