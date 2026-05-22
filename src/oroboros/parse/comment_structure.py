from __future__ import annotations

"""Normalize one raw attached comment block into a structured ``CppDoc``.

This module assumes comment attachment has already been decided elsewhere. Its job
is to take one raw comment string, strip comment delimiters, normalize indentation,
recognize common Doxygen or Qt-style tags, and convert the result into the
structured documentation model used by Oroboros.

Known structural tags such as ``@brief``, ``@param``, ``@return``, ``@tparam``,
``@note``, and related variants are parsed into dedicated ``CppDoc`` fields. Plain
prose comments are split into brief and description paragraphs best-effort, and
unknown tags are preserved in the normalized prose instead of being discarded.
Inline markup and code blocks are also rendered into a Python-doc-friendly Markdown
style so later translation can reuse that normalized text directly.
"""

from collections.abc import Iterable
import re

from ..model import CppDoc


_RECOGNIZED_TAGS = frozenset({
    "brief",
    "deprecated",
    "details",
    "note",
    "param",
    "return",
    "returns",
    "retval",
    "sa",
    "see",
    "tparam",
    "warning",
})
_TAG_LINE_RE = re.compile(r"^\s*[@\\](?P<tag>\w+)\b(?P<body>.*)$")
_PARAM_RE = re.compile(r"^\s*(?:\[[^\]]+\]\s*)?(?P<name>\S+)(?:\s+(?P<body>.*))?$")
_CODE_START_RE = re.compile(r"^\s*[@\\]code(?:\{\.(?P<lang>[^}]+)\})?\s*$")
_CODE_END_RE = re.compile(r"^\s*[@\\]endcode\s*$")
_LINK_BLOCK_RE = re.compile(
    r"[@\\]link\s+(?P<body>.+?)\s+[@\\]endlink\b",
    re.DOTALL,
)
_REF_RE = re.compile(r"(?P<prefix>\s|^)[@\\]ref\s+(?P<target>\S+)")
_INLINE_CODE_RE = re.compile(r"(?P<prefix>\s|^)[@\\][cp]\s+(?P<target>\S+)")


# ==================================================================================================
#     Public API
# ==================================================================================================


def parse_cpp_doc(raw_comment: str | None) -> CppDoc | None:
    """Parse one clang-attached raw comment block into structured documentation."""

    if raw_comment is None:
        return None

    normalized_lines = _normalize_comment_lines(_strip_comment_delimiters(raw_comment))
    if not any(line.strip() for line in normalized_lines):
        return None

    return _parse_doc_sections(normalized_lines)


def comment_preference_key(raw_comment: str | None) -> tuple[int, int, int]:
    """Return one sortable preference key for choosing between raw comment blocks."""

    if raw_comment is None:
        return (0, 0, 0)

    stripped = raw_comment.strip()
    syntax_rank = _comment_syntax_rank(stripped)
    cpp_doc = parse_cpp_doc(raw_comment)
    structure_rank = _structured_doc_rank(cpp_doc)
    return (syntax_rank, structure_rank, len(stripped))


# ==================================================================================================
#     Comment Preference Ranking
# ==================================================================================================


def _comment_syntax_rank(raw_comment: str) -> int:
    """Return one coarse syntax-based documentation preference rank."""

    if raw_comment.startswith(("/**", "/*!", "///", "//!")):
        return 3
    if raw_comment.startswith("/*"):
        return 2
    if raw_comment.startswith("//"):
        return 1
    return 0


def _structured_doc_rank(cpp_doc: CppDoc | None) -> int:
    """Return one structured-content score for a parsed documentation block."""

    if cpp_doc is None:
        return 0

    return (
        len(cpp_doc.parameters)
        + len(cpp_doc.template_parameters)
        + len(cpp_doc.return_values)
        + len(cpp_doc.notes)
        + len(cpp_doc.warnings)
        + len(cpp_doc.see_also)
        + int(cpp_doc.returns is not None)
        + int(cpp_doc.deprecated is not None)
    )


# ==================================================================================================
#     Delimiter Stripping And Line Normalization
# ==================================================================================================


def _strip_comment_delimiters(raw_comment: str) -> list[str]:
    """Remove outer comment markers while preserving content line structure."""

    stripped = raw_comment.strip()
    if not stripped:
        return []

    if stripped.startswith("//"):
        return [_strip_line_comment_prefix(line) for line in stripped.splitlines()]

    return _strip_block_comment_delimiters(stripped)


def _strip_line_comment_prefix(line: str) -> str:
    """Strip one leading line-comment marker from a single comment line."""

    return re.sub(r"^\s*//[/!]?<? ?", "", line.rstrip())


def _strip_block_comment_delimiters(raw_comment: str) -> list[str]:
    """Strip one block-comment wrapper while preserving internal newlines."""

    lines = raw_comment.splitlines()
    if not lines:
        return []

    cleaned_lines: list[str] = []
    for index, line in enumerate(lines):
        current = line.rstrip()
        if index == 0:
            current = re.sub(r"^\s*/\*+[!<]?\s?", "", current)
        if index == len(lines) - 1:
            current = re.sub(r"\s*\*/\s*$", "", current)
        cleaned_lines.append(current)
    return cleaned_lines


def _normalize_comment_lines(lines: Iterable[str]) -> list[str]:
    """Normalize indentation and common block-comment formatting markers."""

    stripped_lines: list[str] = []
    for line in lines:
        current = line.rstrip()
        current = re.sub(r"^\s*\*<? ?", "", current)
        stripped_lines.append(current)

    normalized = _normalize_embedded_code_blocks(stripped_lines)

    indent_candidates = [
        len(line) - len(line.lstrip())
        for line in normalized
        if line.strip()
    ]
    if indent_candidates:
        common_indent = min(indent_candidates)
        normalized = [
            line[common_indent:] if len(line) >= common_indent else ""
            for line in normalized
        ]

    return [line.rstrip() for line in normalized]


# ==================================================================================================
#     Structured Tag Parsing
# ==================================================================================================


def _parse_doc_sections(lines: list[str]) -> CppDoc:
    """Parse normalized comment lines into one structured documentation object."""

    doc = CppDoc()
    prose_sections: list[str] = []

    current_tag: str | None = None
    current_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current_tag, current_lines

        paragraphs = _paragraphs_from_lines(current_lines)
        content = _join_sections(paragraphs)
        if content is None:
            current_tag = None
            current_lines = []
            return

        if current_tag is None:
            prose_sections.extend(paragraphs)
        elif current_tag == "brief":
            doc.brief = content
        elif current_tag == "deprecated":
            doc.deprecated = _append_optional_text(doc.deprecated, content)
        elif current_tag == "details":
            prose_sections.extend(paragraphs)
        elif current_tag == "note":
            doc.notes.append(content)
        elif current_tag == "warning":
            doc.warnings.append(content)
        elif current_tag == "see":
            doc.see_also.append(content)
        elif current_tag in {"return", "returns"}:
            doc.returns = content
        elif current_tag == "param":
            _record_named_doc(doc.parameters, content, allow_annotations=True)
        elif current_tag == "tparam":
            _record_named_doc(doc.template_parameters, content)
        elif current_tag == "retval":
            _record_named_doc(doc.return_values, content)

        current_tag = None
        current_lines = []

    for line in lines:
        tag_match = _TAG_LINE_RE.match(line)
        recognized_tag = None
        if tag_match is not None:
            candidate_tag = tag_match.group("tag").lower()
            if candidate_tag in _RECOGNIZED_TAGS:
                recognized_tag = _canonical_tag_name(candidate_tag)

        if recognized_tag is not None:
            flush_current()
            current_tag = recognized_tag
            body = tag_match.group("body").strip()
            current_lines = [body] if body else []
            continue

        if current_tag == "brief" and current_lines and not line.strip():
            flush_current()
            continue

        if tag_match is not None and current_tag is not None:
            flush_current()
        elif tag_match is not None and current_tag is None and current_lines:
            flush_current()

        current_lines.append(line)

    flush_current()

    if doc.brief is None and prose_sections:
        if prose_sections[0].startswith("```"):
            doc.description = _join_sections(prose_sections)
            return doc
        doc.brief = prose_sections[0]
        prose_sections = prose_sections[1:]

    doc.description = _join_sections(prose_sections)
    return doc


def _record_named_doc(target: dict[str, str], content: str, *, allow_annotations: bool = False) -> None:
    """Parse one normalized name-prefixed doc block and attach it to a target map."""

    lines = content.splitlines()
    first_line = lines[0] if lines else content
    match = _PARAM_RE.match(first_line)
    if match is None:
        target[""] = content
        return

    name = match.group("name")
    if not allow_annotations and name.startswith("[") and "]" in name:
        name = name.split("]", maxsplit=1)[1]
    body_lines: list[str] = []
    first_body = (match.group("body") or "").strip()
    if first_body:
        body_lines.append(first_body)
    if len(lines) > 1:
        body_lines.extend(lines[1:])
    body = "\n".join(body_lines).strip()
    target[name] = body


# ==================================================================================================
#     Paragraph And Section Helpers
# ==================================================================================================


def _collapse_lines(lines: list[str]) -> str | None:
    """Collapse one line sequence into paragraph-preserving prose."""

    return _join_sections(_paragraphs_from_lines(lines))


def _paragraphs_from_lines(lines: list[str]) -> list[str]:
    """Split one line sequence into normalized prose paragraphs."""

    sections: list[str] = []
    current_paragraph: list[str] = []
    current_code_block: list[str] | None = None

    for line in lines:
        stripped = line.strip()
        if current_code_block is not None:
            current_code_block.append(line.rstrip())
            if stripped.startswith("```"):
                sections.append("\n".join(current_code_block).rstrip())
                current_code_block = None
            continue

        if stripped.startswith("```"):
            if current_paragraph:
                sections.append(" ".join(current_paragraph))
                current_paragraph = []
            current_code_block = [line.rstrip()]
            continue

        if not stripped:
            if current_paragraph:
                sections.append(" ".join(current_paragraph))
                current_paragraph = []
            continue
        current_paragraph.append(stripped)

    if current_code_block:
        sections.append("\n".join(current_code_block).rstrip())

    if current_paragraph:
        sections.append(" ".join(current_paragraph))

    return sections


def _join_sections(sections: list[str]) -> str | None:
    """Join normalized prose sections with paragraph breaks."""

    filtered = [section for section in sections if section]
    if not filtered:
        return None
    return "\n\n".join(filtered)


# ==================================================================================================
#     Inline Markup And Code Blocks
# ==================================================================================================


def _normalize_inline_markup(text: str) -> str:
    """Normalize common inline Doxygen-style markup into readable prose."""

    normalized = _LINK_BLOCK_RE.sub(_replace_link_block, text)
    normalized = _REF_RE.sub(
        lambda match: _replace_inline_target(match, wrapper=None),
        normalized,
    )
    normalized = _INLINE_CODE_RE.sub(
        lambda match: _replace_inline_target(match, wrapper="code"),
        normalized,
    )
    return normalized


def _normalize_embedded_code_blocks(lines: list[str]) -> list[str]:
    """Normalize `@code` blocks into fenced Markdown code blocks."""

    normalized: list[str] = []
    in_code_block = False
    in_indented_code_block = False
    pending_code_blanks = 0

    for line in lines:
        if in_code_block:
            if _CODE_END_RE.match(line) is not None:
                normalized.append("```")
                in_code_block = False
                continue
            normalized.append(line.rstrip())
            continue

        if in_indented_code_block:
            if not line.strip():
                pending_code_blanks += 1
                continue
            if _is_indented_code_line(line):
                normalized.extend([""] * pending_code_blanks)
                pending_code_blanks = 0
                normalized.append(_strip_indented_code_prefix(line))
                continue
            pending_code_blanks = 0
            normalized.append("```")
            in_indented_code_block = False

        if not in_code_block and not in_indented_code_block:
            code_match = _CODE_START_RE.match(line)
            if code_match is not None:
                language = code_match.group("lang") or "cpp"
                normalized.append(f"```{language}")
                in_code_block = True
                continue
            if _can_start_indented_code_block(normalized, line):
                normalized.append("```")
                normalized.append(_strip_indented_code_prefix(line))
                in_indented_code_block = True
                pending_code_blanks = 0
                continue
            normalized.append(_normalize_inline_markup(line))
            continue

    if in_code_block or in_indented_code_block:
        normalized.append("```")

    return normalized


# ==================================================================================================
#     Code Block Detection
# ==================================================================================================


def _can_start_indented_code_block(normalized: list[str], line: str) -> bool:
    """Return whether one line should start a Markdown-style indented code block."""

    if not _is_indented_code_line(line):
        return False
    return not normalized or not normalized[-1].strip()


def _is_indented_code_line(line: str) -> bool:
    """Return whether one line uses a Markdown-style code-block indent."""

    if line.startswith("\t"):
        return True
    return _leading_indent_width(line) >= 4 and bool(line.strip())


def _strip_indented_code_prefix(line: str) -> str:
    """Remove one required code-block indentation level from a line."""

    if line.startswith("\t"):
        return line[1:].rstrip()

    if _leading_indent_width(line) >= 4:
        return line[4:].rstrip()

    return line.rstrip()


def _leading_indent_width(line: str) -> int:
    """Measure simple leading indentation width for one comment line."""

    width = 0
    for char in line:
        if char == " ":
            width += 1
            continue
        if char == "\t":
            width += 4
            continue
        break
    return width


# ==================================================================================================
#     Inline Markup Rendering
# ==================================================================================================


def _replace_link_block(match: re.Match[str]) -> str:
    """Render one `@link ... @endlink` block into simple readable prose."""

    body = " ".join(match.group("body").split())
    if not body:
        return ""

    parts = body.split(maxsplit=1)
    target = parts[0]
    label = parts[1] if len(parts) > 1 else ""
    if label:
        return f"{label} ({target})"
    return target


def _canonical_tag_name(tag: str) -> str:
    """Map supported Doxygen aliases onto one canonical internal tag name."""

    if tag == "returns":
        return "return"
    if tag == "sa":
        return "see"
    return tag


def _append_optional_text(existing: str | None, new_text: str) -> str:
    """Append one doc fragment onto an optional paragraph string."""

    if existing is None:
        return new_text
    return f"{existing}\n\n{new_text}"


def _replace_inline_target(match: re.Match[str], wrapper: str | None) -> str:
    """Normalize one inline target while preserving trailing punctuation."""

    target = match.group("target")
    body, suffix = _split_trailing_punctuation(target)
    if wrapper == "code":
        rendered = f"`{body}`"
    else:
        rendered = body
    return f"{match.group('prefix')}{rendered}{suffix}"


def _split_trailing_punctuation(text: str) -> tuple[str, str]:
    """Split off punctuation that should remain outside normalized inline markup."""

    stripped = text.rstrip(".,;:!?)")
    suffix = text[len(stripped):]
    if stripped:
        return stripped, suffix
    return text, ""
