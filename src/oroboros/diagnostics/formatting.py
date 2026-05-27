from __future__ import annotations

"""Formatting helpers for structured diagnostics."""

from collections import OrderedDict
from dataclasses import dataclass, replace
import sys
from typing import Iterable, TextIO

from .color import should_use_color, style_location, style_muted, style_severity, style_title
from .report import Diagnostic, DiagnosticReport


@dataclass(frozen=True, slots=True)
class DiagnosticRenderOptions:
    """Control how diagnostics are formatted for human-readable output."""

    include_stage: bool = True
    include_code: bool = True
    include_detail: bool = False
    color: bool = False

    def with_overrides(self, **changes: bool) -> "DiagnosticRenderOptions":
        """Return one copy with selected rendering flags adjusted."""

        return replace(self, **changes)


def format_diagnostic(
    diagnostic: Diagnostic,
    *,
    options: DiagnosticRenderOptions | None = None,
) -> str:
    """Render one diagnostic as a structured multi-line block."""

    render_options = options or DiagnosticRenderOptions()
    lines = (
        [_format_location(location, options=render_options) for location in diagnostic.locations]
        if diagnostic.locations
        else ["<unknown location>"]
    )
    if diagnostic.model_path is not None:
        lines.append(f"  {style_muted('model:', color=render_options.color)} {diagnostic.model_path}")

    label_parts = [diagnostic.severity]
    if render_options.include_stage:
        label_parts.append(diagnostic.stage)
    if render_options.include_code:
        label_parts.append(diagnostic.code)

    label = "/".join(label_parts)
    lines.append(f"  {style_severity(label, diagnostic.severity, color=render_options.color)}: {diagnostic.message}")
    if render_options.include_detail and diagnostic.detail is not None:
        lines.extend(_format_detail(diagnostic.detail, options=render_options))
    return "\n".join(lines)


def format_diagnostics(
    diagnostics: Iterable[Diagnostic],
    *,
    title: str = "Diagnostics:",
    options: DiagnosticRenderOptions | None = None,
) -> str:
    """Render one ordered diagnostic collection as grouped blocks."""

    render_options = options or DiagnosticRenderOptions()
    diagnostic_list = list(diagnostics)
    if not diagnostic_list:
        return f"{style_title(title, color=render_options.color)} {style_muted('none', color=render_options.color)}"

    return "\n\n".join(
        [
            style_title(title, color=render_options.color),
            *[
                format_diagnostic(
                    diagnostic,
                    options=render_options,
                )
                for diagnostic in diagnostic_list
            ],
        ]
    )


def format_report(
    report: DiagnosticReport,
    *,
    stage_titles: dict[str, str] | None = None,
    options: DiagnosticRenderOptions | None = None,
) -> str:
    """Render one full report grouped by diagnostic stage."""

    render_options = options or DiagnosticRenderOptions(include_detail=True)
    titles = {
        "headers": "Header diagnostics:",
        "clang": "Clang diagnostics:",
        "parse": "Parser diagnostics:",
        "validation": "Validation diagnostics:",
    }
    if stage_titles is not None:
        titles.update(stage_titles)

    if not report.diagnostics:
        return (
            f"{style_title('Diagnostics:', color=render_options.color)} "
            f"{style_muted('none', color=render_options.color)}"
        )

    grouped: OrderedDict[str, list[Diagnostic]] = OrderedDict()
    for stage in ("headers", "clang", "parse", "validation"):
        diagnostics = report.by_stage(stage)
        if diagnostics:
            grouped[stage] = diagnostics

    sections = [
        format_diagnostics(
            diagnostics,
            title=titles[stage],
            options=render_options.with_overrides(include_stage=False),
        )
        for stage, diagnostics in grouped.items()
    ]
    return "\n\n".join(sections)


def print_diagnostics(
    diagnostics: Iterable[Diagnostic],
    *,
    stream: TextIO | None = None,
    title: str = "Diagnostics:",
    options: DiagnosticRenderOptions | None = None,
    color: bool | None = None,
) -> None:
    """Print one ordered diagnostic collection with optional terminal color."""

    output_stream = stream if stream is not None else sys.stdout
    render_options = _resolve_print_options(
        output_stream,
        color=color,
        options=options,
        default_options=DiagnosticRenderOptions(),
    )
    print(
        format_diagnostics(
            diagnostics,
            title=title,
            options=render_options,
        ),
        file=output_stream,
    )


def print_report(
    report: DiagnosticReport,
    *,
    stream: TextIO | None = None,
    stage_titles: dict[str, str] | None = None,
    options: DiagnosticRenderOptions | None = None,
    color: bool | None = None,
) -> None:
    """Print one full diagnostic report with optional terminal color."""

    output_stream = stream if stream is not None else sys.stdout
    render_options = _resolve_print_options(
        output_stream,
        color=color,
        options=options,
        default_options=DiagnosticRenderOptions(include_detail=True),
    )
    print(
        format_report(
            report,
            stage_titles=stage_titles,
            options=render_options,
        ),
        file=output_stream,
    )


def _resolve_print_options(
    stream: TextIO,
    *,
    color: bool | None,
    options: DiagnosticRenderOptions | None,
    default_options: DiagnosticRenderOptions,
) -> DiagnosticRenderOptions:
    render_options = options or default_options
    return render_options.with_overrides(color=should_use_color(stream, color=color))


def _format_location(location, *, options: DiagnosticRenderOptions) -> str:
    return style_location(f"{location.file}:{location.line}:{location.column}", color=options.color)


def _format_detail(detail: str, *, options: DiagnosticRenderOptions) -> list[str]:
    lines = [f"  {style_muted('detail:', color=options.color)}"]
    lines.extend(f"    {line}" for line in detail.splitlines())
    return lines
