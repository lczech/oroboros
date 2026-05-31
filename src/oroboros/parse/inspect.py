from __future__ import annotations

"""Human-readable inspection helpers for parse-stage results."""

from collections import Counter
import sys
from typing import TextIO

from ..diagnostics import DiagnosticRenderOptions, format_report
from ..diagnostics.color import should_use_color, style_muted, style_severity, style_title
from ..model.inspect import format_tree, iter_subtree_elements, summarize_tree
from .config import ParserConfig
from .clang_driver import build_clang_arguments
from .result import ParseResult


def summarize_parse_result(parse_result: ParseResult, *, color: bool = False) -> str:
    """Return a compact summary of one parse result."""

    severity_counts = Counter(
        diagnostic.severity for diagnostic in parse_result.report.diagnostics
    )

    lines = [
        style_title("Parse summary:", color=color),
        f"  {style_muted('input headers:', color=color)} {len(parse_result.headers)}",
        f"  {style_muted('reported diagnostics:', color=color)} {len(parse_result.report.diagnostics)}",
        f"  {style_muted('clang diagnostics:', color=color)} {len(parse_result.report.by_stage('clang'))}",
        f"  {style_muted('non-clang diagnostics:', color=color)} {len(parse_result.report.diagnostics) - len(parse_result.report.by_stage('clang'))}",
    ]

    for severity in ("fatal", "error", "warning", "note"):
        lines.append(
            f"  {style_severity(f'{severity}s', severity, color=color)}: {severity_counts.get(severity, 0)}"
        )

    model_summary_lines = summarize_tree(parse_result.module).splitlines()
    lines.append(f"  {style_muted('model:', color=color)}")
    lines.extend(f"    {line.strip()}" for line in model_summary_lines[1:])
    return "\n".join(lines)


# ==================================================================================================
#     Format
# ==================================================================================================


def format_parser_config(
    config: ParserConfig,
    *,
    color: bool = False,
    include_clang_arguments: bool = False,
) -> str:
    """Render one parser config in a compact human-readable form."""

    lines = [style_title("Parser config:", color=color)]
    lines.append(f"  {style_muted('language:', color=color)} {config.language}")
    lines.append(
        f"  {style_muted('cxx standard:', color=color)} "
        f"{config.cxx_standard if config.cxx_standard is not None else style_muted('<unset>', color=color)}"
    )
    lines.append(
        f"  {style_muted('auto detect toolchain:', color=color)} "
        f"{config.auto_detect_toolchain}"
    )
    lines.append(
        f"  {style_muted('toolchain compiler:', color=color)} "
        f"{config.toolchain_compiler}"
    )
    lines.append(
        f"  {style_muted('resource dir:', color=color)} "
        f"{config.resource_dir if config.resource_dir is not None else style_muted('<unset>', color=color)}"
    )

    lines.extend(_format_path_list("include dirs", config.include_dirs, color=color))
    lines.extend(_format_path_list("system include dirs", config.system_include_dirs, color=color))
    lines.extend(_format_text_list("defines", config.defines, color=color))
    lines.extend(_format_text_list("undefines", config.undefines, color=color))
    lines.extend(_format_text_list("extra args", config.extra_args, color=color))
    lines.extend(_format_text_list("suppressed diagnostics", config.suppress_diagnostics, color=color))

    lines.append(
        f"  {style_muted('validate model:', color=color)} "
        f"{config.validate_model}"
    )
    lines.append(
        f"  {style_muted('warn std explicit specializations:', color=color)} "
        f"{config.warn_std_explicit_class_template_specializations}"
    )
    lines.append(
        f"  {style_muted('comment conflict policy:', color=color)} "
        f"{config.comment_conflict_policy}"
    )

    if include_clang_arguments:
        lines.extend(_format_text_list(
            "rendered clang args",
            build_clang_arguments(config),
            color=color,
        ))

    return "\n".join(lines)


def format_parse_result(
    parse_result: ParseResult,
    *,
    color: bool = False,
    include_headers: bool = True,
    include_tree: bool = True,
) -> str:
    """Render one parse result with headers, tree, and diagnostics."""

    sections: list[str] = [summarize_parse_result(parse_result, color=color)]

    if include_headers:
        header_lines = [style_title("Parser input headers:", color=color)]
        if parse_result.headers:
            header_lines.extend(f"  {header}" for header in parse_result.headers)
        else:
            header_lines.append(f"  {style_muted('<none>', color=color)}")
        sections.append("\n".join(header_lines))
    else:
        sections.append(f"{style_muted('Parser input headers:', color=color)} {len(parse_result.headers)}")

    if include_tree:
        tree_text = format_tree(parse_result.module, indent=1)
        tree_lines = [style_title("Semantic tree:", color=color)]
        if tree_text:
            tree_lines.extend(tree_text.splitlines())
        else:
            tree_lines.append(f"  {style_muted('<empty>', color=color)}")
        sections.append("\n".join(tree_lines))
    else:
        element_count = sum(1 for _ in iter_subtree_elements(parse_result.module))
        sections.append(f"{style_muted('Semantic tree:', color=color)} {element_count} elements")

    diagnostic_text = format_report(
        parse_result.report,
        options=DiagnosticRenderOptions(
            include_stage=False,
            include_code=True,
            include_detail=True,
            color=color,
        ),
    )
    sections.append(diagnostic_text)

    return "\n\n".join(sections)


# ==================================================================================================
#     Print
# ==================================================================================================


def print_parser_config(
    config: ParserConfig,
    *,
    stream: TextIO | None = None,
    color: bool | None = None,
    include_clang_arguments: bool = False,
) -> None:
    """Print one formatted parser config."""

    output_stream = stream if stream is not None else sys.stdout
    print(
        format_parser_config(
            config,
            color=should_use_color(output_stream, color=color),
            include_clang_arguments=include_clang_arguments,
        ),
        file=output_stream,
    )


def print_parse_result(
    parse_result: ParseResult,
    *,
    stream: TextIO | None = None,
    color: bool | None = None,
    include_headers: bool = False,
    include_tree: bool = False,
) -> None:
    """Print one formatted parse result."""

    output_stream = stream if stream is not None else sys.stdout
    print(
        format_parse_result(
            parse_result,
            color=should_use_color(output_stream, color=color),
            include_headers=include_headers,
            include_tree=include_tree,
        ),
        file=output_stream,
    )


def print_parse_summary(
    parse_result: ParseResult,
    *,
    stream: TextIO | None = None,
    color: bool | None = None,
) -> None:
    """Print one compact parse-result summary."""

    output_stream = stream if stream is not None else sys.stdout
    print(
        summarize_parse_result(
            parse_result,
            color=should_use_color(output_stream, color=color),
        ),
        file=output_stream,
    )


# ==================================================================================================
#     Helper Functions
# ==================================================================================================


def _format_path_list(
    label: str,
    values: list[object],
    *,
    color: bool,
) -> list[str]:
    """Render one path-like config field."""

    return _format_text_list(label, [str(value) for value in values], color=color)


def _format_text_list(
    label: str,
    values: list[str],
    *,
    color: bool,
) -> list[str]:
    """Render one list-valued config field."""

    lines = [f"  {style_muted(f'{label}:', color=color)}"]
    if values:
        lines.extend(f"    {value}" for value in values)
    else:
        lines.append(f"    {style_muted('<none>', color=color)}")
    return lines
