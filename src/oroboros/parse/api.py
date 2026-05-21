from __future__ import annotations

"""Public parse-stage entrypoints."""

from pathlib import Path
from typing import Sequence

from ..headers import HeaderSelection
from .config import ParserConfig
from .build_model import build_module_from_clang
from .clang_driver import parse_with_clang
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
    )


def _parse_active_headers(
    headers: Sequence[Path],
    config: ParserConfig,
    *,
    known_project_headers: Sequence[Path] | None = None,
) -> ParseResult:
    """Parse one ordered active-header list into the semantic model."""

    normalized_headers = [Path(header).resolve() for header in headers]
    normalized_known_project_headers = (
        None
        if known_project_headers is None
        else [Path(header).resolve() for header in known_project_headers]
    )

    if not normalized_headers:
        return ParseResult()

    driver_result = parse_with_clang(normalized_headers, config)
    build_result = build_module_from_clang(
        driver_result.translation_unit,
        normalized_headers,
        config,
        known_project_headers=normalized_known_project_headers,
    )

    if config.validate_model:
        build_result.module.validate_tree()
        build_result.module.validate_semantics()

    return ParseResult(
        module=build_result.module,
        diagnostics=driver_result.diagnostics,
        warnings=build_result.warnings,
        skipped_kind_counts=build_result.skipped_kind_counts,
        headers=normalized_headers,
    )
