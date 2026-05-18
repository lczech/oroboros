from __future__ import annotations

"""Human-readable inspection helpers for parse-stage results."""

from collections import Counter
import sys
from typing import Iterable, TextIO

from ..model.inspect import format_tree, summarize_tree
from .result import ParseResult, ParserDiagnostic


def format_diagnostics(diagnostics: Iterable[ParserDiagnostic]) -> str:
    """Render parser diagnostics as readable lines."""

    lines = [
        _format_diagnostic(diagnostic)
        for diagnostic in diagnostics
    ]
    if not lines:
        return "Clang diagnostics: none"

    return "\n".join(["Clang diagnostics:"] + [f"  {line}" for line in lines])


def summarize_parse_result(parse_result: ParseResult) -> str:
    """Return a compact summary of one parse result."""

    severity_counts = Counter(diagnostic.severity for diagnostic in parse_result.diagnostics)

    lines = [
        "Parse summary:",
        f"  input headers: {len(parse_result.headers)}",
        f"  clang diagnostics: {len(parse_result.diagnostics)}",
        f"  parser warnings: {len(parse_result.warnings)}",
    ]

    for severity in ("fatal", "error", "warning", "note"):
        lines.append(f"  {severity}s: {severity_counts.get(severity, 0)}")

    model_summary_lines = summarize_tree(parse_result.module).splitlines()
    lines.append("  model:")
    lines.extend(f"    {line.strip()}" for line in model_summary_lines[1:])
    return "\n".join(lines)


def format_parse_result(parse_result: ParseResult) -> str:
    """Render one parse result with headers, tree, diagnostics, and warnings."""

    header_lines = ["Parser input headers:"]
    if parse_result.headers:
        header_lines.extend(f"  {header}" for header in parse_result.headers)
    else:
        header_lines.append("  <none>")

    tree_text = format_tree(parse_result.module, indent=1)
    tree_lines = ["Semantic tree:"]
    if tree_text:
        tree_lines.extend(tree_text.splitlines())
    else:
        tree_lines.append("  <empty>")

    diagnostic_text = format_diagnostics(parse_result.diagnostics)

    warning_lines = ["Parser warnings:"]
    if parse_result.warnings:
        warning_lines.extend(f"  {warning}" for warning in parse_result.warnings)
    else:
        warning_lines.append("  none")

    return "\n\n".join([
        summarize_parse_result(parse_result),
        "\n".join(header_lines),
        "\n".join(tree_lines),
        diagnostic_text,
        "\n".join(warning_lines),
    ])


def print_parse_result(
    parse_result: ParseResult,
    *,
    stream: TextIO | None = None,
) -> None:
    """Print one formatted parse result."""

    output_stream = stream if stream is not None else sys.stdout
    print(format_parse_result(parse_result), file=output_stream)


def print_parse_summary(
    parse_result: ParseResult,
    *,
    stream: TextIO | None = None,
) -> None:
    """Print one compact parse-result summary."""

    output_stream = stream if stream is not None else sys.stdout
    print(summarize_parse_result(parse_result), file=output_stream)


def _format_diagnostic(diagnostic: ParserDiagnostic) -> str:
    """Format one parser diagnostic as a single readable line."""

    if diagnostic.location is None:
        location = "<unknown location>"
    else:
        location = (
            f"{diagnostic.location.file}:{diagnostic.location.line}:"
            f"{diagnostic.location.column}"
        )
    return f"[{diagnostic.severity}] {location}: {diagnostic.message}"
