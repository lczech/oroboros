from __future__ import annotations

"""Public parse-stage entrypoints."""

from pathlib import Path
from typing import Sequence

from ..diagnostics import DiagnosticReport
from ..headers import HeaderSelection
from ..model import CppElement
from .config import ParserConfig
from .build_model import build_module_from_clang
from .clang_driver import parse_with_clang
from ..model.validation import collect_semantic_diagnostics, collect_tree_diagnostics
from .result import ParseResult


def parse_header_selection(
    selection: HeaderSelection,
    config: ParserConfig,
) -> ParseResult:
    """Parse one structured header selection into the semantic model."""

    return _parse_active_headers(
        selection.active_project_headers,
        config,
        known_project_headers=selection.known_project_headers,
        initial_report=selection.report,
    )


def _parse_active_headers(
    headers: Sequence[Path],
    config: ParserConfig,
    *,
    known_project_headers: Sequence[Path] | None = None,
    initial_report: DiagnosticReport | None = None,
) -> ParseResult:
    """Parse one ordered active-header list into the semantic model."""

    normalized_headers = [Path(header).resolve() for header in headers]
    normalized_known_project_headers = (
        None
        if known_project_headers is None
        else [Path(header).resolve() for header in known_project_headers]
    )
    report = initial_report.copy() if initial_report is not None else DiagnosticReport()

    if not normalized_headers:
        return ParseResult(report=report)

    driver_result = parse_with_clang(normalized_headers, config)
    build_result = build_module_from_clang(
        driver_result.translation_unit,
        normalized_headers,
        config,
        known_project_headers=normalized_known_project_headers,
    )
    report.extend(driver_result.diagnostics)
    report.extend(build_result.report.diagnostics)

    if config.validate_model and isinstance(build_result.module, CppElement):
        report.extend(collect_tree_diagnostics(build_result.module))
        report.extend(collect_semantic_diagnostics(build_result.module))

    return ParseResult(
        module=build_result.module,
        report=report,
        headers=normalized_headers,
    )
