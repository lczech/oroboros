from __future__ import annotations

"""Human-readable inspection helpers for parse-stage results."""

from collections import Counter
import sys
from typing import TextIO

from ..diagnostics import DiagnosticRenderOptions, format_report
from ..diagnostics.color import should_use_color, style_muted, style_severity, style_title
from ..model.inspect import format_tree, summarize_tree
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
        f"  {style_muted('parser/header/validation diagnostics:', color=color)} {len(parse_result.report.diagnostics) - len(parse_result.report.by_stage('clang'))}",
    ]

    for severity in ("fatal", "error", "warning", "note"):
        lines.append(
            f"  {style_severity(f'{severity}s', severity, color=color)}: {severity_counts.get(severity, 0)}"
        )

    model_summary_lines = summarize_tree(parse_result.module).splitlines()
    lines.append(f"  {style_muted('model:', color=color)}")
    lines.extend(f"    {line.strip()}" for line in model_summary_lines[1:])
    return "\n".join(lines)


def format_parse_result(parse_result: ParseResult, *, color: bool = False) -> str:
    """Render one parse result with headers, tree, and diagnostics."""

    header_lines = [style_title("Parser input headers:", color=color)]
    if parse_result.headers:
        header_lines.extend(f"  {header}" for header in parse_result.headers)
    else:
        header_lines.append(f"  {style_muted('<none>', color=color)}")

    tree_text = format_tree(parse_result.module, indent=1)
    tree_lines = [style_title("Semantic tree:", color=color)]
    if tree_text:
        tree_lines.extend(tree_text.splitlines())
    else:
        tree_lines.append(f"  {style_muted('<empty>', color=color)}")

    diagnostic_text = format_report(
        parse_result.report,
        options=DiagnosticRenderOptions(
            include_stage=False,
            include_code=True,
            include_detail=True,
            color=color,
        ),
    )

    return "\n\n".join([
        summarize_parse_result(parse_result, color=color),
        "\n".join(header_lines),
        "\n".join(tree_lines),
        diagnostic_text,
    ])


def print_parse_result(
    parse_result: ParseResult,
    *,
    stream: TextIO | None = None,
    color: bool | None = None,
) -> None:
    """Print one formatted parse result."""

    output_stream = stream if stream is not None else sys.stdout
    print(
        format_parse_result(
            parse_result,
            color=should_use_color(output_stream, color=color),
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
