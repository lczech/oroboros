from __future__ import annotations

"""Resolve one selected raw comment per declaration cursor before redeclaration merging.

This module handles comment attachment: For each clang cursor, it asks clang for
``raw_comment`` and also recovers nearby leading or trailing comment tokens from
the source file. It then reconciles those sources into one selected raw comment
for that cursor, preferring locally attached recovered comments when clang appears
to be reusing a stale comment from an earlier declaration of the same USR.

The selected raw comment is later parsed into ``CppDoc`` by ``comment_structure``,
and repeated declarations are still merged afterwards by the normal redeclaration
merge layer. In other words, this module chooses the best comment per cursor, while
later merge policy chooses among comments across declaration sites.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from clang.cindex import TokenKind

from ..diagnostics import Diagnostic
from ..model import SourceLocation
from .comment_structure import comment_preference_key, parse_cpp_doc
from .cursor_data import CursorTokenInfo, cursor_raw_comment, cursor_source_location, cursor_usr, file_cursor_tokens

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
class CursorCommentResolution:
    """Store the resolved comment decision for one declaration cursor occurrence."""

    location: SourceLocation | None = None
    clang_raw_comment: str | None = None
    selected_comment: str | None = None
    selected_doc: Any = None
    selection_reason: str = "missing"
    mismatch_warning: str | None = None
    mismatch_detail: str | None = None


def resolve_cursor_comment(cursor: Any, context: BuildContext | None) -> CursorCommentResolution:
    """Resolve the best raw comment for one cursor using clang plus token recovery."""

    raw_comment = cursor_raw_comment(cursor)
    location = cursor_source_location(cursor)
    fallback = CursorCommentResolution(
        location=location,
        clang_raw_comment=raw_comment,
        selected_comment=raw_comment,
        selected_doc=parse_cpp_doc(raw_comment),
        selection_reason="clang_raw_comment" if raw_comment is not None else "missing",
    )
    if context is None or context.translation_unit is None:
        return fallback

    recovered_candidates = recover_comment_candidates(cursor, context)
    if not recovered_candidates:
        if raw_comment is not None and _raw_comment_is_detached(cursor, context, raw_comment):
            resolution = CursorCommentResolution(
                location=location,
                clang_raw_comment=raw_comment,
                selected_comment=None,
                selected_doc=None,
                selection_reason="discarded_detached_clang_raw_comment",
                # Keep detached-comment discard itself, but do not warn for it:
                # blank-line-separated comments that clang still attaches as raw comments
                # turned out to produce too much noise without indicating a real problem.
                # mismatch_warning=_build_detached_warning(cursor, raw_comment),
                mismatch_warning=None,
            )
        else:
            resolution = fallback
    else:
        resolution = _select_comment_resolution(cursor, context, raw_comment, recovered_candidates)

    usr = cursor_usr(cursor)
    if usr is not None:
        context.usr_to_comments.setdefault(usr, []).append(resolution)
    if resolution.mismatch_warning is not None:
        context.report.add(
            Diagnostic(
                severity="warning",
                stage="parse",
                code="parse.comment_recovery.mismatch",
                message=resolution.mismatch_warning,
                detail=resolution.mismatch_detail,
                locations=[] if location is None else [location],
            )
        )
    return resolution


def recover_comment_candidates(cursor: Any, context: BuildContext) -> list[RecoveredCommentCandidate]:
    """Recover attached comment candidates for one cursor from token positions."""

    cursor_extent = getattr(cursor, "extent", None)
    cursor_location = getattr(cursor, "location", None)
    file_object = getattr(cursor_location, "file", None)
    file_name = getattr(file_object, "name", None)
    if cursor_extent is None or file_name is None:
        return []

    file_path = Path(file_name).resolve()
    tokens = file_cursor_tokens(file_path, context)
    if not tokens:
        return []

    start = cursor_extent.start
    end = cursor_extent.end
    start_line = int(getattr(start, "line", 0))
    start_offset = int(getattr(start, "offset", 0))
    end_line = int(getattr(end, "line", 0))
    end_offset = int(getattr(end, "offset", 0))

    candidates: list[RecoveredCommentCandidate] = []

    trailing = _recover_trailing_comment(
        tokens,
        start_line=start_line,
        end_line=end_line,
        end_offset=end_offset,
    )
    if trailing is not None:
        candidates.append(trailing)

    leading = _recover_leading_comment_group(tokens, start_line=start_line, start_offset=start_offset)
    if leading is not None:
        candidates.append(leading)

    # Stacked out-of-line member-template definitions can start at the last
    # `template <...>` prefix line instead of the first one. Recover comments
    # attached ahead of the whole template-prefix block in that common style.
    template_anchor = _template_prefix_block_start_anchor(tokens, start_offset=start_offset)
    if template_anchor is not None and template_anchor[1] != start_offset:
        leading = _recover_leading_comment_group(
            tokens,
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
    cursor: Any,
    context: BuildContext,
    clang_raw_comment: str | None,
    recovered_candidates: list[RecoveredCommentCandidate],
) -> CursorCommentResolution:
    """Select one final raw comment from clang and recovered candidates."""

    best_candidate = max(
        recovered_candidates,
        key=lambda candidate: (_candidate_attachment_rank(candidate), comment_preference_key(candidate.text)),
    )
    recovered_texts = {candidate.text for candidate in recovered_candidates}
    raw_matches_recovered = clang_raw_comment in recovered_texts if clang_raw_comment is not None else False

    selected_comment = clang_raw_comment
    selection_reason = "clang_raw_comment"
    mismatch_warning: str | None = None
    mismatch_detail: str | None = None

    if clang_raw_comment is None:
        selected_comment = best_candidate.text
        selection_reason = f"recovered_{best_candidate.kind}"
    elif raw_matches_recovered:
        selection_reason = f"clang_matches_recovered_{best_candidate.kind}"
    elif _should_prefer_recovered(cursor, context, clang_raw_comment, best_candidate.text):
        selected_comment = best_candidate.text
        selection_reason = f"recovered_{best_candidate.kind}"
        mismatch_warning = _build_mismatch_warning(cursor, clang_raw_comment, best_candidate.text)
        mismatch_detail = _build_mismatch_detail(clang_raw_comment, best_candidate.text)

    return CursorCommentResolution(
        location=cursor_source_location(cursor),
        clang_raw_comment=clang_raw_comment,
        selected_comment=selected_comment,
        selected_doc=parse_cpp_doc(selected_comment),
        selection_reason=selection_reason,
        mismatch_warning=mismatch_warning,
        mismatch_detail=mismatch_detail,
    )


# ==================================================================================================
#     Comment Provenance Checks
# ==================================================================================================


def _should_prefer_recovered(
    cursor: Any,
    context: BuildContext,
    clang_raw_comment: str,
    recovered_comment: str,
) -> bool:
    """Return whether recovered local attachment should override clang raw_comment."""

    if comment_preference_key(recovered_comment) > comment_preference_key(clang_raw_comment):
        return True

    is_definition = bool(getattr(cursor, "is_definition", lambda: False)())
    if is_definition:
        return True

    # If clang is reusing a raw comment that we already selected on an earlier
    # declaration of the same entity, treat that as evidence that the current
    # cursor's clang attachment is stale and prefer the locally recovered one.
    return _clang_raw_comment_was_already_selected_for_usr(cursor, context, clang_raw_comment)


def _clang_raw_comment_was_already_selected_for_usr(
    cursor: Any,
    context: BuildContext,
    clang_raw_comment: str,
) -> bool:
    """Return whether clang raw_comment was already selected on an earlier declaration."""

    usr = cursor_usr(cursor)
    if usr is None:
        return False

    prior_resolutions = context.usr_to_comments.get(usr, [])
    return any(resolution.selected_comment == clang_raw_comment for resolution in prior_resolutions)


def _raw_comment_is_detached(cursor: Any, context: BuildContext, raw_comment: str) -> bool:
    """Return whether clang raw_comment matches a nearby but detached leading comment group."""

    cursor_extent = getattr(cursor, "extent", None)
    cursor_location = getattr(cursor, "location", None)
    file_object = getattr(cursor_location, "file", None)
    file_name = getattr(file_object, "name", None)
    if cursor_extent is None or file_name is None:
        return False

    file_path = Path(file_name).resolve()
    tokens = file_cursor_tokens(file_path, context)
    if not tokens:
        return False

    start = cursor_extent.start
    start_line = int(getattr(start, "line", 0))
    start_offset = int(getattr(start, "offset", 0))

    preceding_index: int | None = None
    for index in range(len(tokens) - 1, -1, -1):
        if tokens[index].end_offset <= start_offset:
            preceding_index = index
            break

    if preceding_index is None:
        return False

    token = tokens[preceding_index]
    if token.kind != TokenKind.COMMENT:
        return False

    if token.spelling.lstrip().startswith("//"):
        group: list[CursorTokenInfo] = [token]
        index = preceding_index - 1
        while index >= 0:
            candidate = tokens[index]
            if candidate.kind != TokenKind.COMMENT:
                break
            if not candidate.spelling.lstrip().startswith("//"):
                break
            if _comment_has_code_before_same_line(tokens, index):
                break
            if candidate.end_line + 1 != group[0].start_line:
                break
            group.insert(0, candidate)
            index -= 1

        group_text = "\n".join(token.spelling.strip() for token in group)
        if group_text != raw_comment:
            return False
        return _comment_has_code_before_same_line(tokens, preceding_index) or group[-1].end_line < start_line - 1

    if token.spelling.strip() != raw_comment.strip():
        return False
    return _comment_has_code_before_same_line(tokens, preceding_index) or token.end_line < start_line - 1


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
        group: list[CursorTokenInfo] = [token]
        index = preceding_index - 1
        while index >= 0:
            candidate = tokens[index]
            if candidate.kind != TokenKind.COMMENT:
                break
            if not candidate.spelling.lstrip().startswith("//"):
                break
            if _comment_has_code_before_same_line(tokens, index):
                break
            if candidate.end_line + 1 != group[0].start_line:
                break
            group.insert(0, candidate)
            index -= 1

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


def _comment_has_code_before_same_line(tokens: list[CursorTokenInfo], index: int) -> bool:
    """Return whether one comment token is trailing after code on the same line."""

    comment_line = tokens[index].start_line
    for prior_index in range(index - 1, -1, -1):
        prior = tokens[prior_index]
        if prior.end_line < comment_line:
            return False
        return True
    return False


# ==================================================================================================
#     Warning Rendering
# ==================================================================================================


def _build_mismatch_warning(cursor: Any, clang_raw_comment: str, recovered_comment: str) -> str:
    """Render one warning about conflicting clang and recovered comment attachment."""

    spelling = getattr(cursor, "spelling", "") or "<anonymous>"
    return (
        f"Recovered attached comment for {spelling!r} differed from "
        "clang's attached raw comment; using the recovered comment."
    )


def _build_mismatch_detail(clang_raw_comment: str, recovered_comment: str) -> str:
    """Render one structured detail block for comment-recovery mismatches."""

    return "\n".join([
        "clang raw_comment:",
        clang_raw_comment,
        "",
        "recovered attached comment:",
        recovered_comment,
        "",
        "selected: recovered",
    ])


def _build_detached_warning(cursor: Any, clang_raw_comment: str) -> str:
    """Render one warning when clang attached a separated non-doc comment block."""

    spelling = getattr(cursor, "spelling", "") or "<anonymous>"
    return (
        f"Discarded clang-attached raw comment for {spelling!r} because "
        "token-based recovery found no attached comment block at that declaration site."
    )


def _candidate_attachment_rank(candidate: RecoveredCommentCandidate) -> tuple[int, int]:
    """Return one sortable attachment-strength key for recovered candidates."""

    if candidate.kind == "trailing":
        return (3, candidate.end_line - candidate.start_line + 1)
    if candidate.kind == "leading_block":
        return (2, candidate.end_line - candidate.start_line + 1)
    return (1, candidate.end_line - candidate.start_line + 1)
